# LAB TITLE: Day 1 Lab 5 - Compiling and Invoking the LangGraph Engine
# %% [markdown]
# ## Day 1 · Lab 5 — Compiling & Invoking the LangGraph Engine
#
# **Duration:** 55 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# Labs 3 and 4 produced a schema and a set of functions. This lab assembles them
# into a **compiled state machine** — a graph with a declared topology that can be
# visualised, checkpointed, resumed and replayed.
#
# That last property is the whole reason we are not writing an `if/elif` chain.
# Any Python programmer can express this control flow with conditionals. What they
# cannot easily get is a topology that is inspectable *as data*, a run that can be
# suspended and resumed mid-flight, and a durable trail of every state transition.
#
# ### What you build
#
# ```
#              START
#                │
#           [ ingest ]
#                │
#         [ rule_engine ]
#                │
#        route_after_matching  ── exception ──► [ classify_exception ] ──► END
#                │
#             matched
#                │
#       [ variance_analysis ]
#                │
#        route_after_variance
#          │      │      │       │
#      closed  tolerance short  over
#          │      │      │       │
#          └──────┴──► [ finalise ] ◄──┴───┘
#                          │
#                         END
# ```
#
# ### Prerequisites
# Labs 1–4 complete. `langgraph` installed. No Azure calls in this lab.

# %%
"""Day 1 Lab 5 - Compiling and Invoking the LangGraph Engine."""

from __future__ import annotations

import csv
import operator
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from langgraph.graph import END, START, StateGraph          # noqa: E402

from shared.config import SEED_DIR, settings                # noqa: E402
from shared.telemetry import configure, get_logger, log_event, new_run_id, trace_node  # noqa: E402

configure(level=settings.log_level, logfile="lab05_audit.log")
log = get_logger("day1.lab5")

TOLERANCE_USD = settings.write_off_tolerance_usd

# Reuse the engine built in Lab 4 rather than duplicating it. If you renamed the
# file, adjust the import - drift between lab files is a real defect source.
sys.path.insert(0, str(Path(__file__).parent if "__file__" in globals() else Path.cwd()))
from lab04_nodes_and_routing import (  # noqa: E402
    AR_OPEN, node_rule_engine, normalise_customer, route_after_matching,
    route_after_variance, route_exception_type,
)

# %% [markdown]
# ### Step 1 — Declare the graph state
#
# Same schema as Lab 3, with the reducers made explicit. `trace` accumulates;
# everything else replaces. LangGraph reads these annotations to decide how to
# merge each node's return value.

# %%
class GraphState(TypedDict, total=False):
    run_id: str
    txn_id: str
    bank_customer_raw: str
    bank_amount_usd: float
    bank_reference: str
    value_date: str
    remittance_parsed: dict

    matched_invoice: str
    matched_priority: int
    match_type: str
    erp_amount_usd: float
    variance_usd: float

    end_state: Literal["OPEN", "PARTIAL_MATCH", "CLOSED", "UAC", "UIC", "QUERY"]
    requires_human: bool
    write_off_usd: float
    dispute_usd: float

    trace: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

# %% [markdown]
# ### Step 2 — Write the nodes
#
# Every node obeys the same contract: **take state, return a partial dict.**
# Wrapping each one in `trace_node` means the audit trail is produced by the
# framework rather than remembered by the developer.

# %%
def node_ingest(state: GraphState) -> dict:
    """Normalise the inbound bank record and mark it OPEN."""
    with trace_node(log, "ingest", state["run_id"], txn_id=state["txn_id"]) as out:
        customer = normalise_customer(state.get("bank_customer_raw", ""))
        out["customer_resolved"] = customer or "<unresolved>"
        out["amount_usd"] = state.get("bank_amount_usd")
        return {
            "end_state": "OPEN",
            "trace": [f"ingest: {state['txn_id']} {state.get('bank_amount_usd', 0):,.2f} "
                      f"from {customer or '<unknown sender>'}"],
        }


def node_matching(state: GraphState) -> dict:
    """Delegate to the Lab 4 priority engine."""
    with trace_node(log, "rule_engine", state["run_id"], txn_id=state["txn_id"]) as out:
        result = node_rule_engine(dict(state))
        out["priority"] = result.get("matched_priority", 0)
        out["invoice"] = result.get("matched_invoice", "-")
        return result


def node_variance(state: GraphState) -> dict:
    """Describe the variance in business terms. No decision is taken here."""
    with trace_node(log, "variance_analysis", state["run_id"], txn_id=state["txn_id"]) as out:
        variance = state.get("variance_usd", 0.0)
        out["variance_usd"] = variance
        if abs(variance) < 0.005:
            note = "exact match"
        elif abs(variance) <= TOLERANCE_USD:
            note = f"within {TOLERANCE_USD:,.2f} tolerance"
        elif variance < 0:
            note = f"short payment of {abs(variance):,.2f}"
        else:
            note = f"OVERPAYMENT of {variance:,.2f} - no end state defined in spec"
        return {"trace": [f"variance_analysis: {note}"]}


def node_close(state: GraphState) -> dict:  # noqa: ARG001
    return {"end_state": "CLOSED", "trace": ["close: fully applied, invoice closed"]}


def node_tolerance_write_off(state: GraphState) -> dict:
    amount = abs(state.get("variance_usd", 0.0))
    return {
        "end_state": "CLOSED",
        "write_off_usd": round(amount, 2),
        "trace": [f"tolerance: {amount:,.2f} auto-written off, invoice closed"],
    }


def node_short_payment(state: GraphState) -> dict:
    """Short payment: apply the cash, open a dispute for the balance.

    Day 2 inserts the RAG classification that assigns a D-code here. Today the
    dispute is opened without a reason, and `requires_human` stays True until a
    reason exists. Not knowing why is itself a routable state.
    """
    shortfall = abs(state.get("variance_usd", 0.0))
    return {
        "end_state": "PARTIAL_MATCH",
        "dispute_usd": round(shortfall, 2),
        "requires_human": True,
        "trace": [f"short_payment: applied {state.get('erp_amount_usd', 0) - shortfall:,.2f}, "
                  f"dispute raised for {shortfall:,.2f} (reason code pending - Day 2)"],
    }


def node_overpayment(state: GraphState) -> dict:
    """The gap case. Routed to QUERY rather than forced into an ill-fitting state."""
    excess = state.get("variance_usd", 0.0)
    return {
        "end_state": "QUERY",
        "requires_human": True,
        "trace": [f"overpayment: {excess:,.2f} received above invoice value. "
                  f"SPECIFICATION GAP - no end state defined. Routed to QUERY."],
    }


def node_classify_exception(state: GraphState) -> dict:
    """No rule matched: UAC if the sender is identifiable, UIC if not."""
    with trace_node(log, "classify_exception", state["run_id"], txn_id=state["txn_id"]) as out:
        kind = route_exception_type(dict(state))
        out["exception_type"] = kind
        if kind == "uac":
            return {"end_state": "UAC", "requires_human": True,
                    "trace": ["exception: sender identified, no invoice reference -> "
                              "Un-applied Cash, owned by Cash Application"]}
        return {"end_state": "UIC", "requires_human": True,
                "trace": ["exception: sender not identifiable -> Un-identified Cash, "
                          "owned by Treasury"]}


def node_finalise(state: GraphState) -> dict:
    """Terminal node. In production this posts to the ERP through an MCP tool."""
    with trace_node(log, "finalise", state["run_id"], txn_id=state["txn_id"]) as out:
        out["end_state"] = state.get("end_state")
        out["requires_human"] = state.get("requires_human", False)
        return {"trace": [f"finalise: end state {state.get('end_state')}, "
                          f"human review {'REQUIRED' if state.get('requires_human') else 'not required'}"]}

# %% [markdown]
# ### Step 3 — Assemble the graph
#
# Three API calls do all the work:
#
# | Call | Meaning |
# |---|---|
# | `add_node(name, fn)` | register a unit of work |
# | `add_edge(a, b)` | unconditional transition |
# | `add_conditional_edges(a, router, mapping)` | transition chosen at runtime |
#
# `add_conditional_edges` takes the **router function** and a mapping from the
# label it returns to a destination node. A label the mapping does not cover is a
# runtime error — which is the behaviour you want. Silent fall-through in a
# payment system is how money goes missing.

# %%
builder = StateGraph(GraphState)

builder.add_node("ingest", node_ingest)
builder.add_node("rule_engine", node_matching)
builder.add_node("variance_analysis", node_variance)
builder.add_node("close", node_close)
builder.add_node("tolerance_write_off", node_tolerance_write_off)
builder.add_node("short_payment", node_short_payment)
builder.add_node("overpayment", node_overpayment)
builder.add_node("classify_exception", node_classify_exception)
builder.add_node("finalise", node_finalise)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "rule_engine")

# <<<BLANK hint="add_conditional_edges from 'rule_engine' using route_after_matching, mapping 'matched'->'variance_analysis' and 'exception'->'classify_exception'">
builder.add_conditional_edges(
    "rule_engine",
    route_after_matching,
    {"matched": "variance_analysis", "exception": "classify_exception"},
)
# >>>

builder.add_conditional_edges(
    "variance_analysis",
    route_after_variance,
    {
        "closed": "close",
        "tolerance_write_off": "tolerance_write_off",
        "short_payment": "short_payment",
        "overpayment": "overpayment",
    },
)

for terminal in ("close", "tolerance_write_off", "short_payment", "overpayment", "classify_exception"):
    builder.add_edge(terminal, "finalise")
builder.add_edge("finalise", END)

graph = builder.compile()
print("Graph compiled.\n")

# %% [markdown]
# ### Step 4 — The topology is data, and that is the point
#
# A compiled graph exposes its own structure. You can render it, diff it between
# releases, and hand it to an architecture review board as an artifact rather than
# as a description. Try getting that from a nested `if` statement.
#
# `draw_mermaid()` may not exist on every LangGraph version, so we guard it. The
# ASCII fallback is not a consolation prize — it is what you paste into a ticket.

# %%
try:
    print(graph.get_graph().draw_mermaid())
except Exception as exc:  # noqa: BLE001
    log_event(log, "mermaid_unavailable", error=str(exc))
    print(f"(draw_mermaid unavailable on this version: {exc})\n")
    print("""START -> ingest -> rule_engine
rule_engine --matched--> variance_analysis
rule_engine --exception--> classify_exception
variance_analysis --closed--> close
variance_analysis --tolerance_write_off--> tolerance_write_off
variance_analysis --short_payment--> short_payment
variance_analysis --overpayment--> overpayment
{close, tolerance_write_off, short_payment, overpayment, classify_exception} -> finalise -> END""")

# %% [markdown]
# ### Step 5 — Invoke: one transaction, full trace
#
# `graph.invoke(initial_state)` runs to completion and returns the final merged
# state. Watch the `trace` list: it is the complete narrative of the decision, in
# business language, assembled by the graph rather than by a developer remembering
# to log.

# %%
with open(SEED_DIR / "bank_statement.csv", newline="", encoding="utf-8") as fh:
    BANK_ROWS = list(csv.DictReader(fh))


def initial_state(row: dict[str, str]) -> GraphState:
    return {
        "run_id": new_run_id("d1l5"),
        "txn_id": row["txn_id"],
        "bank_customer_raw": row["customer_name_raw"],
        "bank_amount_usd": float(row["amount_usd"]),
        "bank_reference": row["reference_text"],
        "value_date": row["value_date"],
        "trace": [],
        "errors": [],
    }


demo = next(r for r in BANK_ROWS if r["txn_id"] == "BNK-1002")

# <<<BLANK hint="Invoke the compiled graph with initial_state(demo) and store the result in `final`">
final = graph.invoke(initial_state(demo))
# >>>

print(f"TRANSACTION {final['txn_id']}   final state: {final['end_state']}\n")
for i, line in enumerate(final["trace"], 1):
    print(f"  {i}. {line}")
print(f"\n  matched invoice : {final.get('matched_invoice')}")
print(f"  priority        : {final.get('matched_priority')}")
print(f"  variance        : {final.get('variance_usd'):,.2f}")
print(f"  dispute raised  : {final.get('dispute_usd', 0):,.2f}")
print(f"  human required  : {final.get('requires_human')}")

# %% [markdown]
# ### Step 6 — Stream: watch the state machine move
#
# `invoke()` returns the destination. `stream()` shows the journey — one event per
# node as it completes. This is what a live operations console consumes, and it is
# what the Day 1 web application renders.

# %%
print("STREAMING BNK-1004 (the UAC case)\n")
for step, update in enumerate(graph.stream(initial_state(
        next(r for r in BANK_ROWS if r["txn_id"] == "BNK-1004"))), 1):
    for node_name, payload in update.items():
        changed = {k: v for k, v in payload.items() if k != "trace"}
        print(f"  step {step}: [{node_name}]")
        if changed:
            for k, v in changed.items():
                print(f"            {k} = {v}")
        for line in payload.get("trace", []):
            print(f"            trace: {line}")

# %% [markdown]
# ### Step 7 — Full batch and the honest baseline
#
# Run all ten. The distribution across end states is the number that matters to
# the business: it is the **structured-data straight-through rate**, measured
# rather than asserted.

# %%
summary: dict[str, list[str]] = {}
outcomes = []
for row in BANK_ROWS:
    result = graph.invoke(initial_state(row))
    outcomes.append(result)
    summary.setdefault(result["end_state"], []).append(result["txn_id"])

print(f"{'TXN':<10}{'END STATE':<16}{'INVOICE':<11}{'VARIANCE':>11}  HUMAN")
print("-" * 60)
for r in outcomes:
    print(f"{r['txn_id']:<10}{r['end_state']:<16}{r.get('matched_invoice', '-'):<11}"
          f"{r.get('variance_usd', 0):>11,.2f}  {'YES' if r.get('requires_human') else ''}")

print("\nDISTRIBUTION")
print("-" * 60)
for state_name in ["CLOSED", "PARTIAL_MATCH", "UAC", "UIC", "QUERY", "OPEN"]:
    ids = summary.get(state_name, [])
    print(f"  {state_name:<16}{len(ids):>3}  {', '.join(ids) if ids else '-'}")

auto = len(summary.get("CLOSED", []))
touch = sum(len(v) for k, v in summary.items() if k != "CLOSED")
print(f"\nStraight-through (CLOSED, no human)  : {auto}/{len(outcomes)} = {auto / len(outcomes):.0%}")
print(f"Requires human touch                : {touch}/{len(outcomes)} = {touch / len(outcomes):.0%}")
print("""
FREEZE THESE TWO NUMBERS. They are the Day 1 baseline against which every
later improvement is measured. Day 2 adds remittance understanding and should
move BNK-1002 (reason code), BNK-1008 (3-way match) and BNK-1009 (QUERY, with a
documented reason rather than a guess). Measure the delta - do not assert it.
""")

log_event(log, "lab05_complete", total=len(outcomes), straight_through=auto)

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] `graph.compile()` succeeds with no missing-edge error.
# - [ ] BNK-1002 finishes as `PARTIAL_MATCH` with a 500.00 dispute.
# - [ ] BNK-1004 → `UAC`, BNK-1005 → `UIC`, BNK-1010 → `QUERY` (overpayment).
# - [ ] `graph.stream()` emits one event per node.
# - [ ] You have written down the straight-through percentage.
#
# ### Stretch goals
#
# 1. Remove the `"overpayment"` key from the `variance_analysis` mapping and run
#    BNK-1010. Read the error carefully — that is LangGraph refusing to guess.
# 2. Add a `node_currency_check` that routes any non-USD payment to a new `FX`
#    branch. Notice you touch three places: node, router, mapping.
# 3. Compile with `checkpointer=MemorySaver()` and invoke with
#    `config={"configurable": {"thread_id": "demo"}}`. Inspect `graph.get_state`.
#    *This is the mechanism the Capstone uses for Human-In-The-Loop — and note
#    that it is not otherwise taught in Days 1–3. Flagged as a curriculum gap;
#    see the gap analysis in `00_Program/`.*
#
# ### Discussion — 10 minutes
#
# 1. What does the compiled graph give you that an `if/elif` chain does not?
#    Push past "it looks nicer" to: inspectable topology, checkpoint/resume,
#    per-node observability, and a testable routing surface.
# 2. `node_finalise` currently only logs. When it posts to a real ERP, what
#    happens if the post succeeds and the process dies before the state is
#    recorded? (Idempotency keys. Have the conversation now, not in production.)
# 3. Which nodes here will *ever* need a model? Only the ones reading unstructured
#    text. Everything else stays deterministic — and that is a cost, latency and
#    audit decision, not a purity argument.
#
# ### Business impact
#
# You now have a working cash-application engine that handles structured matching
# end to end, with a full audit trail and a measured baseline. In a real
# engagement this is roughly the artifact that ends discovery: it proves the
# priority rules are implementable, quantifies exactly how much of the volume
# structured logic can absorb, and scopes the remainder — the unstructured
# remittance work — with evidence rather than estimate.
