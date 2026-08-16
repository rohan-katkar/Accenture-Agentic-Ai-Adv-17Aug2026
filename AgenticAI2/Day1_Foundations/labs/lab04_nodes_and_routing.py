# ==========================================================================
# STARTER FILE - Day 1 Lab 4 - Execution Nodes and Dynamic Branching Rules
# ==========================================================================
# There are 3 blank(s) to complete, each marked with a TODO.
# Work top to bottom. Run the file after each blank - it fails loudly at the
# next unfinished blank it REACHES, which tells you where you are.
#
# Blanks are numbered by position in the file, not by execution order. A blank
# inside a function defined early but called late is reached after a later one,
# so the file may halt at blank 2 before blank 1. That is expected.
#
# Stuck? The completed file is in ../solutions/ - but try for ten minutes
# first. The debugging is the lesson.
# ==========================================================================

# LAB TITLE: Day 1 Lab 4 - Execution Nodes and Dynamic Branching Rules
# %% [markdown]
# ## Day 1 · Lab 4 — Execution Nodes & Dynamic Branching Rules
#
# **Duration:** 50 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# This is where the business rules become code. You implement the six-level
# priority matching engine from the specification, and the routing function that
# decides which branch of the graph a payment takes.
#
# ### The design decision worth defending in a review
#
# **The rule engine is deterministic Python. It is not a model call.**
#
# Ask the room why, before you tell them. The answers you are looking for:
#
# | Reason | Consequence if you used a model instead |
# |---|---|
# | Reproducible | same input, same output, every time — auditable |
# | Free | 5,000 payments/night × 2 calls each ≈ hours of latency and real spend |
# | Explainable | "Priority 4 matched on customer + invoice" beats "the model thought so" |
# | Testable | a rule table is unit-testable; a prompt is not, in the same sense |
#
# The model is reserved for the one job it is uniquely good at — reading
# unstructured remittance prose. That is Day 2. Everything structured stays in
# Python. **This split is the single most important architectural point of the
# whole course.**
#
# ### Prerequisites
# Labs 1–3 complete. No Azure calls in this lab.

# %%
"""Day 1 Lab 4 - Execution Nodes and Dynamic Branching Rules."""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import SEED_DIR, settings                # noqa: E402
from shared.telemetry import configure, get_logger, log_event, new_run_id  # noqa: E402

configure(level=settings.log_level, logfile="lab04_audit.log")
log = get_logger("day1.lab4")

TOLERANCE_USD = settings.write_off_tolerance_usd  # 10.00 per specification

# %% [markdown]
# ### Step 1 — Load the ERP open-items ledger
#
# In production this is a SQL query against the AR sub-ledger, reached through an
# MCP tool so the agent never touches the database directly. Here it is a CSV with
# the identical column shape, so the swap is a one-function change.

# %%
@dataclass(frozen=True)
class OpenItem:
    invoice_no: str
    customer_name: str
    po_number: str
    delivery_no: str
    invoice_date: str
    amount_usd: float


def load_open_items() -> list[OpenItem]:
    with open(SEED_DIR / "erp_ar_open.csv", newline="", encoding="utf-8") as fh:
        return [
            OpenItem(r["invoice_no"], r["customer_name"], r["po_number"],
                     r["delivery_no"], r["invoice_date"], float(r["amount_usd"]))
            for r in csv.DictReader(fh) if r["status"] == "OPEN"
        ]


AR_OPEN = load_open_items()
print(f"{len(AR_OPEN)} open AR items loaded\n")
print(f"{'INVOICE':<12}{'CUSTOMER':<22}{'PO':<12}{'DELIVERY':<12}{'DATE':<13}{'AMOUNT':>11}")
print("-" * 82)
for item in AR_OPEN:
    print(f"{item.invoice_no:<12}{item.customer_name:<22}{item.po_number:<12}"
          f"{item.delivery_no:<12}{item.invoice_date:<13}{item.amount_usd:>11,.2f}")

# %% [markdown]
# ### Step 2 — Normalisation: the unglamorous 80%
#
# `"ACME CORPORATION"` and `"Acme Corp"` are the same customer. `"INV-808 PAYMENT"`
# contains an invoice number. Bank narrative fields are free text typed by whoever
# initiated the transfer.
#
# Almost every real reconciliation failure traces back to this step, not to the
# matching logic. Budget for it accordingly in your own estimates.
#
# > **Honesty flag:** the alias map below is hand-built. In production, customer
# > identity resolution is its own component — usually fuzzy matching over a
# > master data list, often with a human-curated alias table behind it. Do not
# > present the five lines below as a production identity-resolution strategy.

# %%
CUSTOMER_ALIASES = {
    "acme corporation": "Acme Corp",
    "acme corp": "Acme Corp",
    "globex industries": "Globex Industries",
    "initech llc": "Initech LLC",
    "initech": "Initech LLC",
    "soylent corp": "Soylent Corp",
    "umbrella health": "Umbrella Health",
    "stark industries": "Stark Industries",
    "hooli inc": "Hooli Inc",
    "wayne enterprises": "Wayne Enterprises",
}

INVOICE_RE = re.compile(r"\bINV[-\s]?(\d{3,6})\b", re.IGNORECASE)
PO_RE = re.compile(r"\bPO[-\s]?(\d{3,6})\b", re.IGNORECASE)
DELIVERY_RE = re.compile(r"\bDEL[-\s]?(\d{3,6})\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def normalise_customer(raw: str) -> str:
    """Resolve a bank narrative name to a canonical ERP customer name."""
    # ------------------------------------------------------------------
    # TODO (Blank 1): Lower-case and strip `raw`, look it up in CUSTOMER_ALIASES, return the raw value unchanged if absent
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 1 - see the TODO above")


def extract_identifiers(reference: str) -> dict[str, str | None]:
    """Pull structured identifiers out of a free-text bank reference."""
    inv = INVOICE_RE.search(reference)
    po = PO_RE.search(reference)
    dlv = DELIVERY_RE.search(reference)
    dt = DATE_RE.search(reference)
    return {
        "invoice_no": f"INV-{inv.group(1)}" if inv else None,
        "po_number": f"PO-{po.group(1)}" if po else None,
        "delivery_no": f"DEL-{dlv.group(1)}" if dlv else None,
        "invoice_date": dt.group(1) if dt else None,
    }


for sample in ["INV-808 PAYMENT", "PO-5541", "DEL-7712",
               "INV-955 DTD 2026-02-18", "REMITTANCE ATTACHED", ""]:
    print(f"  {sample!r:<28} -> {extract_identifiers(sample)}")

print()
for name in ["ACME CORPORATION", "Acme Corp", "Wayne Enterprises", "Cyberdyne Systems", ""]:
    print(f"  {name!r:<24} -> {normalise_customer(name)!r}")

# %% [markdown]
# ### Step 3 — The six priority rules
#
# The specification evaluates priorities **in order** and stops at the first hit.
# Order is not arbitrary: a PO number is a stronger identifier than an invoice
# number alone, because a customer quoting their own PO is unambiguous about which
# commercial commitment they are settling.
#
# | Priority | Bank fields | Match type |
# |---|---|---|
# | 1 | customer + PO + amount | 2-way |
# | 2 | customer + delivery number + amount | 2-way |
# | 3 | customer + invoice + invoice date + amount | 2-way |
# | 4 | customer + invoice + amount | 2-way |
# | 5 | bank payment vs ERP **and** remittance: customer + PO + invoice + date | 3-way |
# | 6 | bank payment vs ERP **and** remittance: customer + PO + invoice | 3-way |
#
# **Priorities 5 and 6 need the remittance document**, which we do not parse until
# Day 2. Today the rule functions are written and unit-tested; they simply return
# `None` while `remittance` is empty. That is deliberate scaffolding, not an
# omission — call it out so nobody thinks the lab is incomplete.
#
# Note also what a rule does **not** do: it does not compare amounts for equality.
# A short payment must still *match* an invoice — otherwise you can never identify
# what was deducted. Amount handling belongs in the variance step, not the match
# step. Getting this wrong is the most common design error in cash application.

# %%
@dataclass
class MatchResult:
    priority: int
    match_type: str
    invoice_no: str
    erp_amount_usd: float
    rationale: str


RuleFn = Callable[[dict[str, Any], list[OpenItem], dict[str, Any]], MatchResult | None]


def rule_p1_customer_po(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    ident = bank["identifiers"]
    if not ident["po_number"]:
        return None
    for item in ar:
        if item.customer_name == bank["customer"] and item.po_number == ident["po_number"]:
            return MatchResult(1, "2-way", item.invoice_no, item.amount_usd,
                               f"customer + PO {ident['po_number']} -> {item.invoice_no}")
    return None


def rule_p2_customer_delivery(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    ident = bank["identifiers"]
    if not ident["delivery_no"]:
        return None
    for item in ar:
        if item.customer_name == bank["customer"] and item.delivery_no == ident["delivery_no"]:
            return MatchResult(2, "2-way", item.invoice_no, item.amount_usd,
                               f"customer + delivery {ident['delivery_no']} -> {item.invoice_no}")
    return None


def rule_p3_customer_invoice_date(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
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


def rule_p4_customer_invoice(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:  # noqa: ARG001
    """Priority 4: customer name + invoice number. The most common real match."""
    ident = bank["identifiers"]
    if not ident["invoice_no"]:
        return None
    # ------------------------------------------------------------------
    # TODO (Blank 2): Scan `ar` for an item whose customer_name equals bank['customer'] and invoice_no equals ident['invoice_no']; return MatchResult(4, '2-way', ...) or None
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 2 - see the TODO above")


def rule_p5_three_way_dated(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:
    """3-way: bank + ERP + remittance, including invoice date.

    Returns None until Day 2 populates `remit`. Scaffolding, not omission.
    """
    if not remit.get("invoices"):
        return None
    for entry in remit["invoices"]:
        for item in ar:
            if (item.invoice_no == entry.get("invoice_no")
                    and item.customer_name == bank["customer"]
                    and item.invoice_date == entry.get("invoice_date")):
                return MatchResult(5, "3-way", item.invoice_no, item.amount_usd,
                                   "bank + ERP + remittance incl. invoice date")
    return None


def rule_p6_three_way(bank: dict, ar: list[OpenItem], remit: dict) -> MatchResult | None:
    """3-way without the date constraint."""
    if not remit.get("invoices"):
        return None
    for entry in remit["invoices"]:
        for item in ar:
            if item.invoice_no == entry.get("invoice_no") and item.customer_name == bank["customer"]:
                return MatchResult(6, "3-way", item.invoice_no, item.amount_usd,
                                   "bank + ERP + remittance, no date constraint")
    return None


PRIORITY_RULES: list[RuleFn] = [
    rule_p1_customer_po, rule_p2_customer_delivery, rule_p3_customer_invoice_date,
    rule_p4_customer_invoice, rule_p5_three_way_dated, rule_p6_three_way,
]

# %% [markdown]
# ### Step 4 — The rule engine node
#
# A **node** in LangGraph is a plain function: state in, partial state out. It
# returns only the keys it changed; LangGraph merges the rest.
#
# Two habits to build now, because they pay off in the Capstone:
#
# - Return a *partial* dict, never the whole state. Returning the whole state
#   makes reducers meaningless and merges unpredictable.
# - Write a `trace` line describing the decision **in business language**. That
#   line is what the analyst reads at 08:00, not your variable names.

# %%
def node_rule_engine(state: dict) -> dict:
    """Evaluate priorities 1..6 in order and stop at the first match."""
    bank = {
        "customer": normalise_customer(state.get("bank_customer_raw", "")),
        "amount": state.get("bank_amount_usd", 0.0),
        "identifiers": extract_identifiers(state.get("bank_reference", "")),
    }
    remit = state.get("remittance_parsed", {})

    for rule in PRIORITY_RULES:
        result = rule(bank, AR_OPEN, remit)
        if result is None:
            continue
        variance = round(bank["amount"] - result.erp_amount_usd, 2)
        log_event(log, "match_found", node="rule_engine", run_id=state.get("run_id"),
                  txn_id=state.get("txn_id"), priority=result.priority,
                  invoice=result.invoice_no, variance_usd=variance)
        return {
            "matched_invoice": result.invoice_no,
            "matched_priority": result.priority,
            "match_type": result.match_type,
            "erp_amount_usd": result.erp_amount_usd,
            "variance_usd": variance,
            "trace": [f"rule_engine: priority {result.priority} - {result.rationale}"],
        }

    log_event(log, "no_match", node="rule_engine", run_id=state.get("run_id"),
              txn_id=state.get("txn_id"), customer=bank["customer"])
    return {
        "matched_priority": 0,
        "match_type": "none",
        "trace": ["rule_engine: no priority rule matched"],
    }

# %% [markdown]
# ### Step 5 — The routing function
#
# A routing function takes state and returns a **string label**. It must not
# mutate state, and it must not call a model. It is a pure read of a decision that
# has already been made and recorded.
#
# The exception branch encodes the specification's distinction precisely:
#
# - customer resolved, no invoice → **UAC** (Un-applied Cash)
# - customer not resolvable → **UIC** (Un-identified Cash)
#
# > **Specification inconsistency, flag it to the client.** The end-state table
# > defines UAC as *"No Invoice details in Bank Statement **and** No Remittance
# > Advice."* Example D then describes UAC as *"customer identified, invoice
# > unknown."* Those are different tests. We implement the Example D reading —
# > whether the customer is identifiable is the operationally useful distinction,
# > because it determines whether Cash Application or Treasury owns the item. Log
# > this as an open question rather than silently choosing.

# %%
def route_after_matching(state: dict) -> str:
    """Return the next branch label: 'matched' or 'exception'."""
    # ------------------------------------------------------------------
    # TODO (Blank 3): Return 'matched' when state['matched_priority'] is truthy, otherwise 'exception'
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 3 - see the TODO above")


def route_exception_type(state: dict) -> str:
    """Distinguish UAC from UIC on one test: is the payer identifiable?

    UAC (Un-applied Cash)  - we know WHO paid, not WHAT for. Cash Application
                             posts it on account and chases the allocation.
    UIC (Un-identified Cash) - we do not know who paid. Treasury investigates
                             with the bank before anything can post at all.

    The test is deliberately payer-identifiability rather than
    "is this customer in open AR". A named customer with no open items is still
    UAC: the cash is applied on account, and a credit balance is a normal
    outcome. Routing it to Treasury would waste an investigation.
    """
    raw = state.get("bank_customer_raw", "").strip()
    if not raw:
        return "uic"
    resolved = normalise_customer(raw)
    in_open_ar = resolved in {item.customer_name for item in AR_OPEN}
    log_event(log, "exception_classified", node="classify_exception",
              txn_id=state.get("txn_id"), payer=resolved, in_open_ar=in_open_ar)
    return "uac"


def route_after_variance(state: dict) -> str:
    """CLOSED, tolerance write-off, or a deduction that needs a reason."""
    variance = state.get("variance_usd", 0.0)
    if abs(variance) < 0.005:
        return "closed"
    if abs(variance) <= TOLERANCE_USD:
        return "tolerance_write_off"
    if variance < 0:
        return "short_payment"
    return "overpayment"   # <-- the gap flagged in Lab 3; no end state defined for it

# %% [markdown]
# ### Step 6 — Run every seed transaction through the engine
#
# Ten transactions, chosen to exercise every branch. Read the output row by row
# with the class and name the branch each one takes before revealing it.

# %%
def build_state(row: dict[str, str]) -> dict:
    return {
        "run_id": new_run_id("lab04"),
        "txn_id": row["txn_id"],
        "bank_customer_raw": row["customer_name_raw"],
        "bank_amount_usd": float(row["amount_usd"]),
        "bank_reference": row["reference_text"],
        "value_date": row["value_date"],
        "trace": [],
    }


with open(SEED_DIR / "bank_statement.csv", newline="", encoding="utf-8") as fh:
    bank_rows = list(csv.DictReader(fh))

print(f"{'TXN':<10}{'CUSTOMER':<20}{'PAID':>10}{'PRI':>4} {'INVOICE':<10}"
      f"{'ERP AMT':>10}{'VARIANCE':>10}  ROUTE")
print("-" * 96)

results = []
for row in bank_rows:
    state = build_state(row)
    state.update(node_rule_engine(state))

    branch = route_after_matching(state)
    if branch == "matched":
        detail = route_after_variance(state)
    else:
        detail = route_exception_type(state).upper()

    results.append((state, branch, detail))
    print(f"{state['txn_id']:<10}{normalise_customer(state['bank_customer_raw'])[:19]:<20}"
          f"{state['bank_amount_usd']:>10,.2f}{state.get('matched_priority', 0):>4} "
          f"{state.get('matched_invoice', '-'):<10}"
          f"{state.get('erp_amount_usd', 0):>10,.2f}{state.get('variance_usd', 0):>10,.2f}"
          f"  {branch}/{detail}")

# %% [markdown]
# ### Step 7 — Read the results out loud
#
# Walk these with the room. Each line is a teaching moment.

# %%
print("""
BNK-1001  Acme, INV-808, 10,000 paid vs 10,000 billed
          -> priority 4, variance 0.00, CLOSED. The happy path.

BNK-1002  ACME CORPORATION, PO-5541, 9,500 paid vs 10,000 billed
          -> priority 1 (PO beats invoice), variance -500.00, SHORT PAYMENT.
          Note the alias resolved. Note also that it matched despite the amount
          differing - matching and variance are separate concerns.

BNK-1003  Globex, INV-902, 9,995 paid vs 10,000 billed
          -> priority 4, variance -5.00, within the 10.00 tolerance -> write-off.
          Nobody spends analyst time on 5 dollars.

BNK-1004  Wayne Enterprises, no reference
          -> no rule matched, customer named -> UAC. Cash Application owns it.

BNK-1005  blank sender, blank reference
          -> no rule matched, no customer -> UIC. Treasury owns it.

BNK-1006  Initech, DEL-7712 -> priority 2, exact -> CLOSED. Delivery-number match.

BNK-1007  Soylent, INV-955 with a date -> priority 3 beats priority 4 because the
          date is present and adds confidence. Same invoice either way; the
          recorded priority tells the auditor which evidence was used.

BNK-1008  Umbrella Health, 15,000, reference says 'REMITTANCE ATTACHED'
          -> NO MATCH TODAY. It needs the 3-way rule, and 3-way needs the
          remittance document parsed. Day 2 fixes this. This transaction is your
          live demonstration of why RAG is on the syllabus at all.

BNK-1009  Stark, INV-1180, 8,700 vs 9,000 -> priority 4, variance -300.00,
          SHORT PAYMENT. The remittance gives no reason, so Day 2 routes it to
          QUERY rather than guessing a code.

BNK-1010  Hooli, INV-1201, 12,000 vs 11,000 -> priority 4, variance +1,000.00,
          OVERPAYMENT. There is no end state for this in the specification.
          Do not paper over it. Raise it.
""")

matched = sum(1 for _, b, _ in results if b == "matched")
clean = sum(1 for _, b, d in results if b == "matched" and d in {"closed", "tolerance_write_off"})
print(f"MATCH RATE         : {matched}/{len(results)} = {matched / len(results):.0%}  "
      "(a rule found an invoice)")
print(f"STRAIGHT-THROUGH   : {clean}/{len(results)} = {clean / len(results):.0%}  "
      "(closed with no human touch)")
print("""
These are TWO DIFFERENT NUMBERS and conflating them is the most common way an
automation business case gets overstated. A payment can match an invoice and
still need a human - BNK-1002 matched perfectly and still raised a 500.00
dispute. Report both, always. Lab 5 recomputes straight-through from the
compiled graph; the figures must agree.

The unmatched remainder is the work that needs unstructured document
understanding - which is the business case for Day 2, quantified rather than
asserted.""")

log_event(log, "lab04_complete", total=len(results), matched=matched)

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] `normalise_customer("ACME CORPORATION")` returns `"Acme Corp"`.
# - [ ] `rule_p4_customer_invoice` matches BNK-1001 to INV-808.
# - [ ] `route_after_matching` sends BNK-1004 and BNK-1005 to `exception`.
# - [ ] BNK-1005 routes to `uic`, BNK-1004 to `uac`, and you can say why.
# - [ ] You can state the matched-count figure and explain what the gap represents.
#
# ### Discussion — 8 minutes
#
# 1. BNK-1002 matched on PO even though the amount differed. Defend that design to
#    a controller who says "if the amount is wrong it isn't a match."
# 2. The tolerance is 10.00 flat. What breaks when invoices range from 200 to
#    2,000,000? (Sketch a tiered or percentage tolerance and name its risk.)
# 3. Priority 3 and priority 4 return the same invoice for BNK-1007. Why record
#    which rule fired?
# 4. Your own O2C process: how many of these six priorities exist today, and who
#    owns changing them?
#
# ### Business impact
#
# The matched percentage you just measured is the *straight-through processing
# rate for structured data*. It is the honest baseline, and it is the number to
# freeze **before** any automation target is agreed. Any percentage-improvement
# claim without a frozen baseline is unmeasurable — the target has to be defined
# against a number that already exists, not against an aspiration.
