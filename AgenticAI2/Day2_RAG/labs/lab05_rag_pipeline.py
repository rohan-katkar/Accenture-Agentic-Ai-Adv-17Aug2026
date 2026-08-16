# ==========================================================================
# STARTER FILE - Day 2 Lab 5 - Assembling the Multi-Node RAG Pipeline
# ==========================================================================
# There are 2 blank(s) to complete, each marked with a TODO.
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

# LAB TITLE: Day 2 Lab 5 - Assembling the Multi-Node RAG Pipeline
# %% [markdown]
# ## Day 2 · Lab 5 — Assembling the Multi-Node RAG Pipeline
#
# **Duration:** 55 minutes  **Difficulty:** Advanced
#
# ### Why this lab exists
#
# You now have four components: a rule engine (Day 1), a searchable corpus
# (Lab 1), a tool registry (Lab 2), a retrieval node (Lab 3) and a grounded
# extraction node (Lab 4). This lab makes them one workflow and — critically —
# **measures the delta against the Day 1 baseline you froze.**
#
# ### The graph you are building
#
# ```
#   START → ingest → remittance_search → rule_engine* → variance_analysis
#                          │                                    │
#                    (3-way now                          ┌──────┴───────┐
#                     possible)                       short          other
#                                                        │              │
#                                             classify_deduction        │
#                                                        │              │
#                                                  route_on_confidence  │
#                                                   │           │       │
#                                              open_dispute   QUERY     │
#                                                   └───────────┴───────┘
#                                                            │
#                                                        finalise → END
# ```
#
# **`remittance_search` runs BEFORE `rule_engine`.** That ordering is the whole
# reason BNK-1008 becomes matchable: priority rules 5 and 6 are 3-way rules, and a
# 3-way match needs the remittance parsed before matching is attempted.
#
# ### Prerequisites
# Day 1 complete, Day 2 Labs 1–4 complete. Run Day 2 Lab 1 first — this reads its collection.

# %%
"""Day 2 Lab 5 - Assembling the Multi-Node RAG Pipeline."""

from __future__ import annotations

import csv
import operator
import re
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        ROOT = _p
        sys.path.insert(0, str(_p))
        break

sys.path.insert(0, str(ROOT / "Day1_Foundations" / "solutions"))
sys.path.insert(0, str(Path(__file__).parent if "__file__" in globals() else Path.cwd()))

from langgraph.graph import END, START, StateGraph            # noqa: E402

from shared.config import SEED_DIR, settings                  # noqa: E402
from shared.telemetry import configure, get_logger, log_event, new_run_id, trace_node  # noqa: E402

configure(level=settings.log_level, logfile="d2lab05_audit.log")
log = get_logger("day2.lab5")

# Reuse, do not duplicate. Drift between lab files is a real defect source.
#
# NOTE: this is a CROSS-DAY import. The Day 1 rule engine is imported unchanged,
# which is the point of Step 3 below - yesterday's code runs today untouched.
# The guard exists because a bare ImportError here is baffling: it looks like a
# Day 2 problem when it is actually a missing or renamed Day 1 file.
try:
    from lab04_nodes_and_routing import (        # Day 1  # noqa: E402
        AR_OPEN, node_rule_engine, normalise_customer, route_after_matching,
        route_after_variance, route_exception_type,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        f"Could not import the Day 1 rule engine ({exc}).\n"
        f"Expected: {ROOT / 'Day1_Foundations' / 'solutions' / 'lab04_nodes_and_routing.py'}\n"
        "This lab reuses Day 1 Lab 4 rather than duplicating it. Complete Day 1 first, "
        "or restore that file from the package."
    ) from exc
from lab02_integration_tools import registry     # Day 2  # noqa: E402
from lab03_semantic_search_node import node_remittance_search  # noqa: E402
from lab04_grounded_prompt_nodes import node_classify_deduction  # noqa: E402

TOLERANCE_USD = settings.write_off_tolerance_usd
CONFIDENCE_FLOOR = 0.60   # below this, a human decides — see Step 4

# %% [markdown]
# ### Step 1 — The extended state
#
# Day 1's schema plus the fields Day 2 produces. Note `remittance_evidence` keeps
# provenance — chunk IDs and distances — not just the text. When a dispute is
# challenged six weeks later, "which chunk of which document did this come from"
# is the question you have to answer.

# %%
class RagState(TypedDict, total=False):
    run_id: str
    txn_id: str
    bank_customer_raw: str
    bank_amount_usd: float
    bank_reference: str
    value_date: str

    # --- Day 2 additions ---
    remittance_found: bool
    remittance_text: str
    remittance_evidence: list[dict]
    remittance_parsed: dict          # structured invoice lines, for 3-way matching

    matched_invoice: str
    matched_priority: int
    match_type: str
    erp_amount_usd: float
    variance_usd: float

    reason_code: str
    reason_confidence: float
    reason_evidence: str
    reason_validation_problems: list[str]

    dispute_id: str
    dispute_usd: float
    write_off_usd: float
    end_state: Literal["OPEN", "PARTIAL_MATCH", "CLOSED", "UAC", "UIC", "QUERY"]
    requires_human: bool

    trace: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

# %% [markdown]
# ### Step 2 — Parse invoice lines out of the remittance
#
# The 3-way rules need *structured* invoice references, not prose. This is a
# deliberate design choice worth defending:
#
# > **Invoice numbers are extracted with a regular expression, not a model.**
# > `INV-1102` is a rigid pattern. A regex extracts it deterministically, for free,
# > with a testable failure mode. A model extracts it probabilistically, with
# > latency, cost, and a small chance of returning `INV-1120`. Transposed digits in
# > an invoice number post cash to the wrong invoice.
# >
# > The model's job on Day 2 is the *reason* — the part that is genuinely prose.
# > That split is the same one we defended on Day 1, applied one level deeper.

# %%
INVOICE_LINE_RE = re.compile(
    r"\b(INV[-\s]?\d{3,6})\b(?:.*?(\d{4}-\d{2}-\d{2}))?.*?([\d,]+\.\d{2})",
    re.IGNORECASE)


def node_parse_remittance(state: RagState) -> dict:
    """Extract structured invoice lines from retrieved remittance text."""
    txn_id = state.get("txn_id", "-")
    with trace_node(log, "parse_remittance", state.get("run_id", "-"), txn_id=txn_id) as out:
        text = state.get("remittance_text", "")
        if not text:
            out["invoices_found"] = 0
            return {"remittance_parsed": {}, "trace": ["parse_remittance: no text to parse"]}

        invoices: list[dict] = []
        seen: set[str] = set()
        for line in text.splitlines():
            match = INVOICE_LINE_RE.search(line)
            if not match:
                continue
            invoice_no = match.group(1).upper().replace(" ", "-")
            if invoice_no in seen:
                continue
            seen.add(invoice_no)
            invoices.append({
                "invoice_no": invoice_no,
                "invoice_date": match.group(2),
                "amount_usd": float(match.group(3).replace(",", "")),
            })

        out["invoices_found"] = len(invoices)
        return {
            "remittance_parsed": {"invoices": invoices},
            "trace": [f"parse_remittance: {len(invoices)} invoice line(s) extracted "
                      f"— {', '.join(i['invoice_no'] for i in invoices) or 'none'}"],
        }

# %% [markdown]
# ### Step 3 — Reordered ingest and matching
#
# `ingest` → `remittance_search` → `parse_remittance` → `rule_engine`.
#
# The rule engine is **unchanged from Day 1**. Rules 5 and 6 were written on Day 1
# and returned `None` because `remit["invoices"]` was empty. Now it is populated,
# and they fire. That is what good scaffolding looks like: yesterday's code runs
# today without modification.

# %%
def node_ingest(state: RagState) -> dict:
    with trace_node(log, "ingest", state["run_id"], txn_id=state["txn_id"]) as out:
        customer = normalise_customer(state.get("bank_customer_raw", ""))
        out["customer_resolved"] = customer or "<unresolved>"
        return {"end_state": "OPEN",
                "trace": [f"ingest: {state['txn_id']} {state.get('bank_amount_usd', 0):,.2f} "
                          f"from {customer or '<unknown sender>'}"]}


def node_matching(state: RagState) -> dict:
    with trace_node(log, "rule_engine", state["run_id"], txn_id=state["txn_id"]) as out:
        result = node_rule_engine(dict(state))
        out["priority"] = result.get("matched_priority", 0)
        out["match_type"] = result.get("match_type")
        return result


def node_variance(state: RagState) -> dict:
    variance = state.get("variance_usd", 0.0)
    if abs(variance) < 0.005:
        note = "exact match"
    elif abs(variance) <= TOLERANCE_USD:
        note = f"within {TOLERANCE_USD:,.2f} tolerance"
    elif variance < 0:
        note = f"short payment of {abs(variance):,.2f}"
    else:
        note = f"OVERPAYMENT of {variance:,.2f} — no end state defined in spec"
    return {"trace": [f"variance_analysis: {note}"]}

# %% [markdown]
# ### Step 4 — Confidence routing
#
# A classified deduction is not automatically an actionable one. Three outcomes:
#
# | Condition | Route | Rationale |
# |---|---|---|
# | code is `UNKNOWN` | `QUERY` | the document gave no reason; a human must ask |
# | confidence < 0.60 | `QUERY` | the evidence was weak; do not post on weak evidence |
# | otherwise | `open_dispute` | evidence is grounded and specific |
#
# > **The floor is an assumption, not a finding.** 0.60 was chosen for this
# > courseware, not derived from measurement. Calibrating it properly means
# > labelling a sample of real deductions, measuring the error rate at several
# > thresholds, and picking the point where the cost of a wrong code equals the
# > cost of an unnecessary human review. Record it in the assumptions register and
# > do not let it reach production unexamined.

# %%
def route_on_confidence(state: RagState) -> str:
    code = state.get("reason_code", "UNKNOWN")
    confidence = state.get("reason_confidence", 0.0)
    # ------------------------------------------------------------------
    # TODO (Blank 1): Return 'query' when code is 'UNKNOWN' or confidence < CONFIDENCE_FLOOR, else 'dispute'
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 1 - see the TODO above")


def node_open_dispute(state: RagState) -> dict:
    """Apply the cash, open a coded dispute for the balance. WRITE operation."""
    txn_id = state.get("txn_id", "-")
    with trace_node(log, "open_dispute", state.get("run_id", "-"), txn_id=txn_id) as out:
        shortfall = abs(state.get("variance_usd", 0.0))

        # allow_write=True: the GRAPH authorises this, having reached a state
        # where a grounded, sufficiently-confident reason code exists. The model
        # did not choose to call it. See Day 2 Lab 2, Step 6.
        envelope = registry.invoke("create_dispute", {
            "invoice_no": state.get("matched_invoice", ""),
            "amount_usd": f"{shortfall:.2f}",
            "reason_code": state.get("reason_code", "UNKNOWN"),
            "evidence": state.get("reason_evidence", ""),
        }, allow_write=True, run_id=state.get("run_id", "-"))

        if not envelope["ok"]:
            out["dispute_created"] = False
            return {"end_state": "QUERY", "requires_human": True,
                    "errors": [f"dispute creation failed: {envelope['error']}"],
                    "trace": [f"open_dispute: FAILED — {envelope['error']} — routed to QUERY"]}

        record = envelope["result"]
        out["dispute_id"] = record["dispute_id"]
        return {
            "end_state": "PARTIAL_MATCH",
            "dispute_id": record["dispute_id"],
            "dispute_usd": record["amount_usd"],
            "requires_human": False,   # coded and routed; the owning team picks it up
            "trace": [f"open_dispute: {record['dispute_id']} for {record['amount_usd']:,.2f} "
                      f"code {record['reason_code']} → {record['owning_team']} "
                      f"(SLA {record['sla_days']}d)"],
        }


def node_query(state: RagState) -> dict:
    code = state.get("reason_code", "UNKNOWN")
    confidence = state.get("reason_confidence", 0.0)
    why = ("no reason stated in the remittance" if code == "UNKNOWN"
           else f"confidence {confidence:.2f} below floor {CONFIDENCE_FLOOR}")
    return {"end_state": "QUERY", "requires_human": True,
            "trace": [f"query: routed to human review — {why}"]}


def node_close(state: RagState) -> dict:  # noqa: ARG001
    return {"end_state": "CLOSED", "trace": ["close: fully applied, invoice closed"]}


def node_tolerance(state: RagState) -> dict:
    amount = abs(state.get("variance_usd", 0.0))
    return {"end_state": "CLOSED", "write_off_usd": round(amount, 2),
            "trace": [f"tolerance: {amount:,.2f} auto-written off"]}


def node_overpayment(state: RagState) -> dict:
    excess = state.get("variance_usd", 0.0)
    return {"end_state": "QUERY", "requires_human": True,
            "trace": [f"overpayment: {excess:,.2f} above invoice value. "
                      f"SPECIFICATION GAP — no end state defined. Routed to QUERY."]}


def node_exception(state: RagState) -> dict:
    kind = route_exception_type(dict(state))
    if kind == "uac":
        return {"end_state": "UAC", "requires_human": True,
                "trace": ["exception: payer identified, no invoice reference → UAC"]}
    return {"end_state": "UIC", "requires_human": True,
            "trace": ["exception: payer not identifiable → UIC"]}


def node_finalise(state: RagState) -> dict:
    return {"trace": [f"finalise: end state {state.get('end_state')}, "
                      f"human review "
                      f"{'REQUIRED' if state.get('requires_human') else 'not required'}"]}

# %% [markdown]
# ### Step 5 — Assemble
#
# Compare this with the Day 1 graph. Four nodes added, one edge reordered. The
# Day 1 nodes are untouched. That is the payoff for having built a state machine
# rather than a script.

# %%
builder = StateGraph(RagState)

for name, fn in [
    ("ingest", node_ingest),
    ("remittance_search", node_remittance_search),
    ("parse_remittance", node_parse_remittance),
    ("rule_engine", node_matching),
    ("variance_analysis", node_variance),
    ("classify_deduction", node_classify_deduction),
    ("open_dispute", node_open_dispute),
    ("query", node_query),
    ("close", node_close),
    ("tolerance", node_tolerance),
    ("overpayment", node_overpayment),
    ("classify_exception", node_exception),
    ("finalise", node_finalise),
]:
    builder.add_node(name, fn)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "remittance_search")     # RAG runs BEFORE matching
builder.add_edge("remittance_search", "parse_remittance")
builder.add_edge("parse_remittance", "rule_engine")

builder.add_conditional_edges("rule_engine", route_after_matching,
                              {"matched": "variance_analysis",
                               "exception": "classify_exception"})

builder.add_conditional_edges("variance_analysis", route_after_variance,
                              {"closed": "close",
                               "tolerance_write_off": "tolerance",
                               "short_payment": "classify_deduction",
                               "overpayment": "overpayment"})

# ------------------------------------------------------------------
# TODO (Blank 2): add_conditional_edges from 'classify_deduction' using route_on_confidence, mapping 'dispute'->'open_dispute' and 'query'->'query'
# ------------------------------------------------------------------
raise NotImplementedError("Lab blank 2 - see the TODO above")

for terminal in ("close", "tolerance", "open_dispute", "query",
                 "overpayment", "classify_exception"):
    builder.add_edge(terminal, "finalise")
builder.add_edge("finalise", END)

graph = builder.compile()
print("RAG pipeline compiled — 13 nodes.\n")
try:
    print(graph.get_graph().draw_mermaid())
except Exception as exc:  # noqa: BLE001
    print(f"(draw_mermaid unavailable: {exc})")

# %% [markdown]
# ### Step 6 — Trace BNK-1002 end to end
#
# The transaction you have followed since Day 1 Lab 1. Today it acquires a reason
# code, an owning team and an SLA.

# %%
with open(SEED_DIR / "bank_statement.csv", newline="", encoding="utf-8") as fh:
    BANK_ROWS = list(csv.DictReader(fh))


def initial_state(row: dict[str, str]) -> RagState:
    return {"run_id": new_run_id("d2l5"), "txn_id": row["txn_id"],
            "bank_customer_raw": row["customer_name_raw"],
            "bank_amount_usd": float(row["amount_usd"]),
            "bank_reference": row["reference_text"],
            "value_date": row["value_date"], "trace": [], "errors": []}


demo = graph.invoke(initial_state(next(r for r in BANK_ROWS if r["txn_id"] == "BNK-1002")))
print(f"BNK-1002 → {demo['end_state']}\n")
for i, line in enumerate(demo["trace"], 1):
    print(f"  {i}. {line}")

# %% [markdown]
# ### Step 7 — The 3-way match fires, and immediately exposes a deeper gap
#
# Fifteen thousand dollars sat in `UAC` all of Day 1. The bank reference said only
# "REMITTANCE ATTACHED" — no invoice, no PO, nothing for rules 1 to 4 to match on.
# Now the remittance is parsed, rules 5 and 6 have something to work with, and
# priority 5 fires with a genuine 3-way match.
#
# Then read the variance line. This does **not** end in a clean close, and the
# reason is worth more to the client than a clean close would have been.

# %%
umbrella = graph.invoke(initial_state(next(r for r in BANK_ROWS if r["txn_id"] == "BNK-1008")))
print(f"BNK-1008 → {umbrella['end_state']}  "
      f"(Day 1 outcome was UAC, $15,000 unapplied)\n")
for i, line in enumerate(umbrella["trace"], 1):
    print(f"  {i}. {line}")
print(f"\n  match_type      : {umbrella.get('match_type')}")
print(f"  matched_invoice : {umbrella.get('matched_invoice')}")
print(f"  priority        : {umbrella.get('matched_priority')}")
print(f"  parsed invoices : {umbrella.get('remittance_parsed', {}).get('invoices')}")

print("""
NOTE FOR THE TRAINER — do not let this pass as a clean win.
The remittance covers TWO invoices (INV-1102 for 9,000 and INV-1103 for 6,000)
totalling exactly 15,000. Our rule engine returns the FIRST matching invoice and
computes variance against that one alone, so the variance looks wrong.

This is a genuine limitation of the six priority rules as specified: they are
written as one-payment-to-one-invoice. Real remittances are frequently
one-payment-to-many-invoices. The specification does not define split
application. Add it to the open questions list alongside the overpayment gap —
it is the same class of finding, and it is worth more to the client than a
demo that glosses over it.""")

# %% [markdown]
# ### Step 8 — Full batch, and the measured delta
#
# The whole point of freezing the Day 1 baseline was to be able to do this.

# %%
DAY1_BASELINE = {
    "BNK-1001": "CLOSED", "BNK-1002": "PARTIAL_MATCH", "BNK-1003": "CLOSED",
    "BNK-1004": "UAC", "BNK-1005": "UIC", "BNK-1006": "CLOSED",
    "BNK-1007": "CLOSED", "BNK-1008": "UAC", "BNK-1009": "PARTIAL_MATCH",
    "BNK-1010": "QUERY",
}

results = [graph.invoke(initial_state(row)) for row in BANK_ROWS]

print(f"{'TXN':<10}{'DAY 1':<16}{'DAY 2':<16}{'CODE':<9}{'CONF':>6}  CHANGE")
print("-" * 82)
changed = 0
for r in results:
    day1 = DAY1_BASELINE[r["txn_id"]]
    day2 = r["end_state"]
    mark = ""
    if day1 != day2:
        changed += 1
        mark = f"{day1} → {day2}"
    print(f"{r['txn_id']:<10}{day1:<16}{day2:<16}"
          f"{r.get('reason_code', '-'):<9}{r.get('reason_confidence', 0):>6.2f}  {mark}")

d1_closed = sum(1 for v in DAY1_BASELINE.values() if v == "CLOSED")
d2_closed = sum(1 for r in results if r["end_state"] == "CLOSED")
d1_human = len(DAY1_BASELINE) - d1_closed
d2_human = sum(1 for r in results if r.get("requires_human"))
coded = sum(1 for r in results if r.get("reason_code") not in (None, "UNKNOWN", "-"))

print(f"""
MEASURED DELTA (10 transactions)
--------------------------------------------------------------------------
straight-through (CLOSED)   Day 1 {d1_closed}/10 = {d1_closed*10}%   ->   Day 2 {d2_closed}/10 = {d2_closed*10}%
require a human             Day 1 {d1_human}/10 = {d1_human*10}%   ->   Day 2 {d2_human}/10 = {d2_human*10}%
deductions coded + routed   Day 1 0/10 = 0%   ->   Day 2 {coded}/10 = {coded*10}%
end states changed          {changed}

READ THIS CAREFULLY. Straight-through may barely move. That is not failure.
Day 2's value is NOT in closing more invoices without a human - it is in
converting undifferentiated exception work into CODED, ROUTED, SLA-bearing work.

A PARTIAL_MATCH with code D03, owner Quality and a 10-day SLA is a different
economic object from a PARTIAL_MATCH that says only "500.00 short". The first
is a work item. The second is a research project. Both count identically in a
straight-through metric, which is exactly why that metric alone is the wrong
way to justify Day 2.""")

log_event(log, "lab05_complete", day2_closed=d2_closed, coded=coded, changed=changed)

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] The pipeline compiles with 13 nodes and both conditional routers wired.
# - [ ] BNK-1002 ends `PARTIAL_MATCH` with code D03 and a dispute ID.
# - [ ] BNK-1008 matches 3-way — and you can explain why its variance is misleading.
# - [ ] BNK-1009 ends `QUERY`, not a guessed code.
# - [ ] You have written down the Day 1 → Day 2 delta for all three metrics.
#
# ### Discussion — 10 minutes
#
# 1. `remittance_search` runs before `rule_engine`, so *every* transaction pays the
#    retrieval cost even when priority 4 would have matched instantly. Defend the
#    ordering, then propose a cheaper one. (Hint: a conditional edge that only
#    retrieves when rules 1–4 miss. What does that cost you in deduction coverage?)
# 2. BNK-1008 exposed one-to-many application. Sketch the state fields you would
#    need to apply one payment across several invoices.
# 3. The confidence floor is 0.60 by assertion. Design the experiment that would
#    replace that assertion with a measurement.
#
# ### Business impact
#
# Day 2 does not primarily raise the automation rate. It changes the *nature* of
# the remaining work: from "an analyst opens a PDF and works out what happened" to
# "a coded item lands in the owning team's queue with its evidence attached."
# That is where the labour saving actually comes from, and it is invisible to a
# straight-through metric — which is why the measurement discipline from Day 1
# matters more than any single number in this lab.
