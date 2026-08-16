# ==========================================================================
# STARTER FILE - Day 1 Lab 3 - Building the State Memory Schema
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

# LAB TITLE: Day 1 Lab 3 - Building the State Memory Schema
# %% [markdown]
# ## Day 1 · Lab 3 — Building the State Memory Schema
#
# **Duration:** 40 minutes  **Difficulty:** Foundation → Core
#
# ### Why this lab exists
#
# A chatbot's memory is a list of messages. An **agentic workflow's** memory is a
# typed record that every node reads and writes. That record is the contract
# between nodes — and in a financial system it is also the audit object.
#
# Get the schema wrong and every downstream node compensates with defensive
# `.get()` calls and silent defaults. That is how a reconciliation engine ends up
# posting `None` as an amount.
#
# ### The distinction that anchors Day 1
#
# | | Chatbot | Autonomous agent | **State machine** |
# |---|---|---|---|
# | Memory | message list | scratchpad, model-managed | **typed record, code-managed** |
# | Next step chosen by | user | the model | **your routing function** |
# | Reproducible | no | rarely | **yes, given the same state** |
# | Auditable | transcript only | reasoning trace, unstable | **every transition, replayable** |
# | Fits a controlled financial process | no | no | **yes** |
#
# We build state machines in this course. Not because agents are uninteresting,
# but because *"the model decided"* is not an acceptable answer to an auditor
# asking why USD 500 was written off.
#
# ### Prerequisites
# Labs 1–2 complete. No Azure calls in this lab — it is pure typing and data.

# %%
"""Day 1 Lab 3 - Building the State Memory Schema."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import SEED_DIR, settings                # noqa: E402
from shared.telemetry import configure, get_logger, log_event  # noqa: E402

configure(level=settings.log_level, logfile="lab03_audit.log")
log = get_logger("day1.lab3")

# %% [markdown]
# ### Step 1 — The six end states are the schema, not a report
#
# The business specification defines six terminal states. Encoding them as a
# `Literal` type means a typo like `"CLOSSED"` is a static type error, not a
# midnight production incident.
#
# | State | Meaning | Who owns the follow-up |
# |---|---|---|
# | `OPEN` | uploaded, not yet matched | system |
# | `PARTIAL_MATCH` | matched with a variance | Deductions analyst |
# | `CLOSED` | fully matched (or within tolerance) | nobody — done |
# | `UAC` | Un-applied Cash: customer known, invoice unknown | Cash application |
# | `UIC` | Un-identified Cash: sender unknown | Treasury |
# | `QUERY` | low confidence, needs a human | Human-In-The-Loop queue |
#
# > **Design flag for the class — read this carefully.** The source specification
# > has no end state for an **overpayment**. Transaction `BNK-1010` in the seed
# > data pays 12,000.00 against an 11,000.00 invoice. Under the six states as
# > written, it is not `PARTIAL_MATCH` (that describes a short payment) and it is
# > not `CLOSED` (1,000.00 is unapplied). We surface this deliberately rather than
# > silently inventing a seventh state. Capture it as an open design question for
# > the client — it is exactly the kind of gap a pilot finds in week one.

# %%
EndState = Literal["OPEN", "PARTIAL_MATCH", "CLOSED", "UAC", "UIC", "QUERY"]
ReasonCode = Literal["D01", "D02", "D03", "D04", "D05", "UNKNOWN"]

END_STATE_OWNER: dict[str, str] = {
    "OPEN": "system",
    "PARTIAL_MATCH": "Deductions analyst",
    "CLOSED": "-",
    "UAC": "Cash application",
    "UIC": "Treasury",
    "QUERY": "Human-In-The-Loop queue",
}

for state, owner in END_STATE_OWNER.items():
    print(f"  {state:<15} -> {owner}")

# %% [markdown]
# ### Step 2 — Define the state schema
#
# `TypedDict` gives static checking with zero runtime cost: at execution time the
# object is an ordinary `dict`, which is what LangGraph merges between nodes.
#
# Three conventions worth naming as you write it:
#
# 1. **`total=False`** — nodes populate fields progressively. Requiring every key
#    up front would force every node to invent placeholder values.
# 2. **Money as `float` here, `Decimal` in production.** `0.1 + 0.2 != 0.3` in
#    binary floating point. This course uses `float` for readability and applies
#    explicit rounding at posting boundaries; a real ERP integration uses
#    `decimal.Decimal`. Say this out loud — do not let it pass silently.
# 3. **The audit trail lives *in* the state.** `trace` accumulates; it is not a
#    side channel. If it is not in the state, it did not happen.

# %%
class ReconciliationState(TypedDict, total=False):
    """The single source of truth passed between every node in the graph."""

    # --- identity / correlation ---
    run_id: str
    txn_id: str

    # --- inputs: bank statement ---
    bank_customer_raw: str
    bank_amount_usd: float
    bank_reference: str
    value_date: str

    # --- inputs: unstructured remittance (populated Day 2) ---
    remittance_text: str
    remittance_found: bool

    # --- matching results (Day 1 Lab 4 onward) ---
    matched_invoice: str
    matched_priority: int
    match_type: Literal["2-way", "3-way", "none"]
    erp_amount_usd: float
    variance_usd: float

    # --- deduction handling (Day 2) ---
    reason_code: ReasonCode
    reason_confidence: float
    reason_evidence: str

    # --- security posture (Day 3) ---
    security_flags: list[str]
    security_hold: bool

    # --- terminal outcome ---
    end_state: EndState
    requires_human: bool

    # --- audit ---
    trace: list[str]
    errors: list[str]


print("ReconciliationState fields:")
for name, hint in ReconciliationState.__annotations__.items():
    print(f"  {name:<22} {hint}")
print(f"\nTotal: {len(ReconciliationState.__annotations__)} fields.")

# %% [markdown]
# ### Step 3 — Build an initial state from a real bank row
#
# We read from `shared/seed_data/bank_statement.csv` — the same file the Capstone
# uses. Learners work with the real domain from lab three onward, not a
# `{"foo": "bar"}` placeholder.
#
# Note the missing values. `BNK-1005` has no customer name and no reference. That
# is not bad test data; that is a wire transfer with blank metadata, and it is
# the reason the `UIC` state exists.

# %%
def load_bank_rows() -> list[dict[str, str]]:
    with open(SEED_DIR / "bank_statement.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def make_initial_state(row: dict[str, str], run_id: str) -> ReconciliationState:
    """Convert one CSV row into a well-formed initial state.

    Every field this function does not know is left absent rather than set to a
    guessed default. Absence is honest; a guessed default is a lie downstream
    nodes will believe.
    """
    # ------------------------------------------------------------------
    # TODO (Blank 1): Return a ReconciliationState with run_id, txn_id, bank_customer_raw, bank_amount_usd (float), bank_reference, value_date, end_state 'OPEN', requires_human False, and empty trace/errors/security_flags lists
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 1 - see the TODO above")


rows = load_bank_rows()
states = [make_initial_state(r, run_id=f"day1-{r['txn_id']}") for r in rows]

print(f"{'TXN':<10}{'CUSTOMER':<24}{'AMOUNT':>12}  {'REFERENCE':<28}STATE")
print("-" * 88)
for s in states:
    cust = s["bank_customer_raw"] or "<BLANK>"
    ref = s["bank_reference"] or "<BLANK>"
    print(f"{s['txn_id']:<10}{cust:<24}{s['bank_amount_usd']:>12,.2f}  {ref:<28}{s['end_state']}")

print("\nBNK-1005 has no customer and no reference. That row is the UIC case.")
print("BNK-1004 has a customer but no reference. That row is the UAC case.")

# %% [markdown]
# ### Step 4 — Reducers: how two nodes write the same field without a fight
#
# LangGraph merges each node's returned dict into the running state. The default
# merge is **replace**. For a scalar like `end_state` that is what you want.
#
# For an accumulating field like `trace` it is a bug: node B's trace would wipe
# node A's. `Annotated[list[str], operator.add]` tells LangGraph to **append**
# instead of replace.
#
# Getting this wrong produces the classic symptom: the audit trail contains only
# the last node's entry, and nobody notices until an audit asks for the full path.

# %%
import operator  # noqa: E402


class TracedState(TypedDict, total=False):
    """Same idea as ReconciliationState, with reducer semantics made explicit."""

    txn_id: str
    end_state: EndState                       # replace - last writer wins (correct)
    # ------------------------------------------------------------------
    # TODO (Blank 2): Annotate `trace` as list[str] with operator.add so entries accumulate
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 2 - see the TODO above")
    errors: Annotated[list[str], operator.add]


def simulate_merge(base: dict[str, Any], update: dict[str, Any],
                   accumulating: set[str]) -> dict[str, Any]:
    """Illustrative stand-in for LangGraph's merge, so the rule is visible."""
    merged = dict(base)
    for key, value in update.items():
        if key in accumulating and isinstance(value, list):
            merged[key] = merged.get(key, []) + value
        else:
            merged[key] = value
    return merged


ACCUM = {"trace", "errors"}
state: dict[str, Any] = {"txn_id": "BNK-1002", "end_state": "OPEN", "trace": [], "errors": []}
state = simulate_merge(state, {"trace": ["ingest: read 1 bank row"]}, ACCUM)
state = simulate_merge(state, {"trace": ["rules: priority 1 matched INV-810"],
                               "end_state": "PARTIAL_MATCH"}, ACCUM)
state = simulate_merge(state, {"trace": ["deduction: D03 damage, variance 500.00"]}, ACCUM)

print(f"end_state (replaced) : {state['end_state']}")
print("trace (accumulated)  :")
for line in state["trace"]:
    print(f"    - {line}")
assert len(state["trace"]) == 3, "trace should hold all three entries - check the reducer"
print("\nAll three trace entries survived. Without the reducer, only the last would.")

# %% [markdown]
# ### Step 5 — A schema is only useful if something enforces it
#
# `TypedDict` is checked by mypy or Pyright, not at runtime. In a lab with no type
# checker in the loop, an invalid state flows straight through.
#
# So we write an explicit runtime validator. This is the honest version of "typed
# state": static hints for the developer, an assertion gate for the pipeline.
# Day 2 replaces this hand-written validator with Pydantic, which does both.

# %%
@dataclass
class ValidationIssue:
    txn_id: str
    field: str
    problem: str


LEGAL_END_STATES = {"OPEN", "PARTIAL_MATCH", "CLOSED", "UAC", "UIC", "QUERY"}


def validate(state: ReconciliationState) -> list[ValidationIssue]:
    """Runtime gate. Returns every problem found, not just the first."""
    issues: list[ValidationIssue] = []
    txn = state.get("txn_id", "<unknown>")

    if not state.get("txn_id"):
        issues.append(ValidationIssue(txn, "txn_id", "missing - state is not correlatable"))

    amount = state.get("bank_amount_usd")
    if amount is None:
        issues.append(ValidationIssue(txn, "bank_amount_usd", "missing"))
    elif not isinstance(amount, (int, float)):
        issues.append(ValidationIssue(txn, "bank_amount_usd", f"not numeric: {type(amount).__name__}"))
    elif amount <= 0:
        issues.append(ValidationIssue(txn, "bank_amount_usd", f"non-positive: {amount}"))

    end_state = state.get("end_state")
    if end_state not in LEGAL_END_STATES:
        issues.append(ValidationIssue(txn, "end_state", f"illegal value {end_state!r}"))

    if state.get("end_state") == "PARTIAL_MATCH" and not state.get("reason_code"):
        issues.append(ValidationIssue(txn, "reason_code",
                                      "PARTIAL_MATCH requires a deduction reason code"))
    return issues


good = states[0]
bad: ReconciliationState = {"txn_id": "BNK-9999", "bank_amount_usd": -50.0,
                            "end_state": "CLOSSED", "trace": []}  # type: ignore[typeddict-item]

for label, candidate in (("valid state", good), ("corrupted state", bad)):
    found = validate(candidate)
    print(f"\n{label}: {len(found)} issue(s)")
    for issue in found:
        print(f"    {issue.txn_id}  {issue.field:<20} {issue.problem}")

log_event(log, "schema_validation_demo",
          valid_issue_count=len(validate(good)), invalid_issue_count=len(validate(bad)))
print("\nNote the typo 'CLOSSED' was caught. A static checker would have caught it")
print("at author time. Belt and braces: both controls, because money moves here.")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] `ReconciliationState` compiles and lists its fields.
# - [ ] All ten bank rows convert into initial states with `end_state == "OPEN"`.
# - [ ] The `trace` assertion passes with three accumulated entries.
# - [ ] The corrupted state produces at least two validation issues.
# - [ ] You can explain, unprompted, why `bank_amount_usd` should be `Decimal` in production.
#
# ### Discussion — 8 minutes
#
# 1. Should `remittance_text` live in the state at all? It could be 40 KB of PDF
#    text, and every checkpoint persists the whole state. Argue both sides.
#    (There is no single right answer — it is a storage-versus-replayability
#    trade-off, and naming it is the skill.)
# 2. The overpayment gap from Step 1: propose a seventh end state, or argue that
#    an existing one should absorb it. Write your answer down — the Capstone
#    revisits it with real money attached.
# 3. Which of these fields would you refuse to persist in a checkpoint under GDPR
#    or your firm's data-retention policy?
#
# ### Business impact
#
# The state schema is the integration contract between the AI workflow and the
# ERP. Every field here maps to something a cash-application analyst can see and
# act on. Teams that skip this step and pass free-form dictionaries between nodes
# report the same failure mode: the pilot works on ten transactions and becomes
# unmaintainable at a thousand, because no one can say what shape the data is
# supposed to be.
