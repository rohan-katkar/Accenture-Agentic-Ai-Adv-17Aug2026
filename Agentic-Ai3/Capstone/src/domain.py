"""
Capstone/src/domain.py
======================
Pure business logic for order-to-cash reconciliation. No I/O beyond loading the
ledgers, no framework imports, no model calls.

WHY THIS IS A PACKAGE AND NOT AN IMPORT OF THE LAB FILES
--------------------------------------------------------
The labs are teaching scripts: they print, they assert, they narrate. Importing
one executes it. That is correct for a lab and wrong for a deployable component.

So the Capstone re-expresses the same logic as an importable package. That
introduces a drift risk - two copies of the priority rules - and we close it the
only honest way: `tests/test_acceptance.py` asserts that this package reproduces
the SAME ten end states the Day 1 labs produce. If the two ever disagree, the
acceptance suite fails.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Literal

from shared.config import SEED_DIR, settings

# ---------------------------------------------------------------------------
# End states. Six from the specification, plus one the specification omits.
# ---------------------------------------------------------------------------
EndState = Literal[
    "OPEN",                     # 1 uploaded, not matched
    "PARTIAL_MATCH",            # 2 matched with a variance
    "CLOSED",                   # 3 fully matched, or within tolerance
    "UAC",                      # 4 un-applied cash: payer known, invoice unknown
    "UIC",                      # 5 un-identified cash: payer unknown
    "QUERY",                    # 6 needs a human decision
    "REJECTED_SECURITY_HOLD",   # + Day 3: a guardrail blocked the item
]

ReasonCode = Literal["D01", "D02", "D03", "D04", "D05", "UNKNOWN"]

END_STATE_OWNER: dict[str, str] = {
    "OPEN": "system",
    "PARTIAL_MATCH": "Deductions analyst",
    "CLOSED": "-",
    "UAC": "Cash Application",
    "UIC": "Treasury",
    "QUERY": "Human-in-the-loop queue",
    "REJECTED_SECURITY_HOLD": "Security review queue",
}

# NOTE on money. This package uses float for arithmetic to stay consistent with
# the labs, and rounds at every posting boundary. A production ERP integration
# uses decimal.Decimal end to end. `to_decimal` exists so the posting layer can
# convert at the boundary rather than pretending the problem is solved.
TOLERANCE_USD: float = settings.write_off_tolerance_usd


def to_decimal(value: float) -> Decimal:
    """Convert to Decimal at a posting boundary. See the note above."""
    return Decimal(str(round(value, 2)))


# ---------------------------------------------------------------------------
# Ledgers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OpenItem:
    invoice_no: str
    customer_name: str
    po_number: str
    delivery_no: str
    invoice_date: str
    amount_usd: float


@dataclass(frozen=True)
class BankTransaction:
    txn_id: str
    value_date: str
    customer_name_raw: str
    amount_usd: float
    reference_text: str
    payment_method: str


@dataclass(frozen=True)
class DeductionCode:
    reason_code: str
    category: str
    description: str
    owning_team: str
    sla_days: int


def load_open_items(path: Path | None = None) -> list[OpenItem]:
    with open(path or SEED_DIR / "erp_ar_open.csv", newline="", encoding="utf-8") as fh:
        return [
            OpenItem(r["invoice_no"], r["customer_name"], r["po_number"],
                     r["delivery_no"], r["invoice_date"], float(r["amount_usd"]))
            for r in csv.DictReader(fh) if r["status"] == "OPEN"
        ]


def load_bank_transactions(path: Path | None = None) -> list[BankTransaction]:
    with open(path or SEED_DIR / "bank_statement.csv", newline="", encoding="utf-8") as fh:
        return [
            BankTransaction(r["txn_id"], r["value_date"], r["customer_name_raw"],
                            float(r["amount_usd"]), r["reference_text"], r["payment_method"])
            for r in csv.DictReader(fh)
        ]


def load_deduction_codes(path: Path | None = None) -> dict[str, DeductionCode]:
    with open(path or SEED_DIR / "deduction_codes.csv", newline="", encoding="utf-8") as fh:
        return {
            r["reason_code"]: DeductionCode(
                r["reason_code"], r["category"], r["description"],
                r["owning_team"], int(r["sla_days"]))
            for r in csv.DictReader(fh)
        }


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
# Hand-built alias table. In production, customer identity resolution is its own
# component - fuzzy matching over master data with a human-curated alias table
# behind it. This is not that, and it must not be presented as that.
CUSTOMER_ALIASES = {
    "acme corporation": "Acme Corp", "acme corp": "Acme Corp",
    "globex industries": "Globex Industries",
    "initech llc": "Initech LLC", "initech": "Initech LLC",
    "soylent corp": "Soylent Corp", "umbrella health": "Umbrella Health",
    "stark industries": "Stark Industries", "hooli inc": "Hooli Inc",
    "wayne enterprises": "Wayne Enterprises",
}

INVOICE_RE = re.compile(r"\bINV[-\s]?(\d{3,6})\b", re.IGNORECASE)
PO_RE = re.compile(r"\bPO[-\s]?(\d{3,6})\b", re.IGNORECASE)
DELIVERY_RE = re.compile(r"\bDEL[-\s]?(\d{3,6})\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Invoice lines inside a remittance. A regex, deliberately: INV-1102 is a rigid
# pattern, and a model that returns INV-1120 posts cash to the wrong invoice.
REMIT_LINE_RE = re.compile(
    r"\b(INV[-\s]?\d{3,6})\b(?:.*?(\d{4}-\d{2}-\d{2}))?.*?([\d,]+\.\d{2})",
    re.IGNORECASE)


def normalise_customer(raw: str) -> str:
    return CUSTOMER_ALIASES.get(raw.strip().lower(), raw.strip())


def extract_identifiers(reference: str) -> dict[str, str | None]:
    inv, po = INVOICE_RE.search(reference), PO_RE.search(reference)
    dlv, dt = DELIVERY_RE.search(reference), DATE_RE.search(reference)
    return {
        "invoice_no": f"INV-{inv.group(1)}" if inv else None,
        "po_number": f"PO-{po.group(1)}" if po else None,
        "delivery_no": f"DEL-{dlv.group(1)}" if dlv else None,
        "invoice_date": dt.group(1) if dt else None,
    }


def parse_remittance_lines(text: str) -> list[dict]:
    """Extract structured invoice lines from remittance prose."""
    out: list[dict] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        m = REMIT_LINE_RE.search(line)
        if not m:
            continue
        invoice_no = m.group(1).upper().replace(" ", "-")
        if invoice_no in seen:
            continue
        seen.add(invoice_no)
        out.append({"invoice_no": invoice_no, "invoice_date": m.group(2),
                    "amount_usd": float(m.group(3).replace(",", ""))})
    return out


# ---------------------------------------------------------------------------
# Priority matching rules 1-6
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MatchResult:
    priority: int
    match_type: str          # "2-way" | "3-way"
    invoice_no: str
    erp_amount_usd: float
    rationale: str


RuleFn = Callable[[dict, list[OpenItem], dict], "MatchResult | None"]


def _p1(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    po = bank["identifiers"]["po_number"]
    if not po:
        return None
    for item in ar:
        if item.customer_name == bank["customer"] and item.po_number == po:
            return MatchResult(1, "2-way", item.invoice_no, item.amount_usd,
                               f"customer + PO {po} -> {item.invoice_no}")
    return None


def _p2(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    dlv = bank["identifiers"]["delivery_no"]
    if not dlv:
        return None
    for item in ar:
        if item.customer_name == bank["customer"] and item.delivery_no == dlv:
            return MatchResult(2, "2-way", item.invoice_no, item.amount_usd,
                               f"customer + delivery {dlv} -> {item.invoice_no}")
    return None


def _p3(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    ident = bank["identifiers"]
    if not (ident["invoice_no"] and ident["invoice_date"]):
        return None
    for item in ar:
        if (item.customer_name == bank["customer"]
                and item.invoice_no == ident["invoice_no"]
                and item.invoice_date == ident["invoice_date"]):
            return MatchResult(3, "2-way", item.invoice_no, item.amount_usd,
                               f"customer + invoice + date {ident['invoice_date']}")
    return None


def _p4(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    inv = bank["identifiers"]["invoice_no"]
    if not inv:
        return None
    for item in ar:
        if item.customer_name == bank["customer"] and item.invoice_no == inv:
            return MatchResult(4, "2-way", item.invoice_no, item.amount_usd,
                               f"customer + invoice {inv}")
    return None


def _p5(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:
    for entry in remit.get("invoices", []):
        for item in ar:
            if (item.invoice_no == entry.get("invoice_no")
                    and item.customer_name == bank["customer"]
                    and item.invoice_date == entry.get("invoice_date")):
                return MatchResult(5, "3-way", item.invoice_no, item.amount_usd,
                                   "bank + ERP + remittance incl. invoice date")
    return None


def _p6(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:
    for entry in remit.get("invoices", []):
        for item in ar:
            if item.invoice_no == entry.get("invoice_no") and item.customer_name == bank["customer"]:
                return MatchResult(6, "3-way", item.invoice_no, item.amount_usd,
                                   "bank + ERP + remittance, no date constraint")
    return None


PRIORITY_RULES: list[RuleFn] = [_p1, _p2, _p3, _p4, _p5, _p6]


def match_payment(customer_raw: str, reference: str, remittance_text: str,
                  ar: list[OpenItem]) -> MatchResult | None:
    """Evaluate priorities 1..6 in order. First hit wins.

    A rule does NOT compare amounts. A short payment must still match its
    invoice, or the deduction can never be identified. Matching and variance
    analysis are separate steps; collapsing them silently drops every deduction.
    """
    bank = {
        "customer": normalise_customer(customer_raw),
        "identifiers": extract_identifiers(reference or ""),
    }
    remit = {"invoices": parse_remittance_lines(remittance_text)}
    for rule in PRIORITY_RULES:
        result = rule(bank, ar, remit)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# Variance classification
# ---------------------------------------------------------------------------
VarianceClass = Literal["exact", "within_tolerance", "short_payment", "overpayment"]


def classify_variance(received: float, billed: float,
                      tolerance: float = TOLERANCE_USD) -> tuple[float, VarianceClass]:
    variance = round(received - billed, 2)
    if abs(variance) < 0.005:
        return variance, "exact"
    if abs(variance) <= tolerance:
        return variance, "within_tolerance"
    return variance, ("short_payment" if variance < 0 else "overpayment")


def classify_exception(customer_raw: str) -> Literal["UAC", "UIC"]:
    """UAC if the payer is identifiable, UIC if not.

    SPECIFICATION CONFLICT (gap S2): the end-state table defines UAC as "no
    invoice AND no remittance advice"; Example D defines it as "customer
    identified, invoice unknown". We implement Example D, because payer
    identifiability is what decides whether Cash Application or Treasury owns
    the item. Recorded as an open question, not silently chosen.
    """
    return "UAC" if customer_raw.strip() else "UIC"
