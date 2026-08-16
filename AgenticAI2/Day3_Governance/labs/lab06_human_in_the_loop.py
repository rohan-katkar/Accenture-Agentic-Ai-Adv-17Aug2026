# ==========================================================================
# STARTER FILE - Day 3 Lab 6 - Human-In-The-Loop and Durable State
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

# LAB TITLE: Day 3 Lab 6 - Human-In-The-Loop and Durable State
# %% [markdown]
# ## Day 3 · Lab 6 — Human-In-The-Loop & Durable State
#
# **Duration:** 50 minutes  **Difficulty:** Advanced
#
# > **This lab is the remediation for gap G3.** It was identified as missing
# > during a review of the course against what the Capstone actually requires.
# > Without it, learners can *route* to `QUERY` but not *resume* from it, and the
# > Capstone architecture cannot be implemented as drawn.
#
# ### Why this lab exists
#
# Every `QUERY` you have produced so far is a dead end. The transaction terminates
# with `requires_human = True` and nothing happens. That is not a workflow step —
# it is a shrug.
#
# The Capstone needs two things no Day 1–3 lab has taught:
#
# | Capability | Mechanism | Acceptance criterion it unblocks |
# |---|---|---|
# | Survive process death | a **checkpointer** persists state after every node | #5 |
# | Suspend for a human, then resume | `interrupt()` and `Command(resume=...)` | #6 |
#
# ### The misconception to clear first
#
# `interrupt()` does **not** block a thread waiting for an analyst to come back
# from lunch. It suspends the graph, persists the state, and returns control. The
# analyst might respond in four hours or four days. Your process is not sitting
# there holding a connection open.
#
# ### Prerequisites
# Day 3 Labs 1–5 complete. `langgraph-checkpoint-sqlite` installed.

# %%
"""Day 3 Lab 6 - Human-In-The-Loop and Durable State."""

from __future__ import annotations

import operator
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Literal, TypedDict

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        ROOT = _p
        sys.path.insert(0, str(_p))
        break

from langgraph.graph import END, START, StateGraph              # noqa: E402

from shared.config import settings                              # noqa: E402
from shared.telemetry import configure, get_logger, log_event, new_run_id  # noqa: E402

configure(level=settings.log_level, logfile="d3lab06_audit.log")
log = get_logger("day3.lab6")

# %% [markdown]
# ### Step 1 — Verify the APIs exist on your installed version
#
# `interrupt` and `Command` are post-0.2 LangGraph. This is a **version-sensitive
# surface** — check it on the delivery machine rather than assuming.
#
# We prefer `SqliteSaver` because durability is the point of Step 6. `MemorySaver`
# works for the suspend/resume mechanics but cannot demonstrate surviving process
# death, and the lab says so rather than glossing over it.

# %%
try:
    from langgraph.types import Command, interrupt  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        f"langgraph.types.interrupt is not available ({exc}).\n"
        "This lab needs LangGraph 0.2.60 or newer. Run "
        "00_Program/verify_environment.py — it checks this import explicitly."
    ) from exc

DURABLE = True
try:
    from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

    DURABLE = False
    print("SqliteSaver unavailable — falling back to MemorySaver.")
    print("Suspend/resume still works. Step 6 (surviving process death) does NOT.")
    print("Install with: pip install langgraph-checkpoint-sqlite\n")

print(f"interrupt / Command : available")
print(f"durable checkpoints : {DURABLE}")

# %% [markdown]
# ### Step 2 — State, with the analyst's decision recorded
#
# Two fields matter for audit and are easy to forget:
#
# - `decided_by` — **who** made the call. "A human approved it" is not an audit
#   trail; "J. Okonkwo approved it at 14:02" is.
# - `decision_rationale` — **why**. The same field the automated path carries in
#   its `cause`. A human decision is not exempt from explaining itself.

# %%
class HitlState(TypedDict, total=False):
    run_id: str
    txn_id: str
    bank_amount_usd: float
    erp_amount_usd: float
    variance_usd: float
    matched_invoice: str
    reason_code: str
    reason_confidence: float
    reason_evidence: str

    # --- human decision ---
    decided_by: str
    decision_rationale: str
    decision_action: str          # assign_code | reject_deduction | escalate

    end_state: Literal["PARTIAL_MATCH", "CLOSED", "QUERY", "WRITTEN_OFF"]
    requires_human: bool
    trace: Annotated[list[str], operator.add]

# %% [markdown]
# ### Step 3 — The interrupt node
#
# `interrupt(payload)` does two things:
#
# 1. On first execution it **raises out of the graph**, persisting state. The
#    payload is surfaced to the caller — it is the "ask" shown to the analyst.
# 2. On resume it **returns the value** supplied via `Command(resume=...)`, and
#    execution continues from this exact line.
#
# So the same line is both the question and the answer, depending on which pass
# you are on. That is unusual and worth pausing on.
#
# > **Design the payload as the analyst's screen.** They need the variance, the
# > evidence, and the specific question — not a state dump. If you find yourself
# > passing the whole state, you have not decided what the human is actually
# > being asked.

# %%
def node_human_review(state: HitlState) -> dict:
    """Suspend for an analyst decision, then resume from this exact point."""
    # ------------------------------------------------------------------
    # TODO (Blank 1): Call interrupt() with a payload containing txn_id, variance_usd, matched_invoice, reason_evidence, and an 'ask' string plus the list of legal options. Store the returned value in `decision`.
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 1 - see the TODO above")

    action = decision.get("action", "escalate")
    log_event(log, "human_decision_received", txn_id=state["txn_id"],
              action=action, decided_by=decision.get("decided_by"))

    return {
        "decision_action": action,
        "decided_by": decision.get("decided_by", "unknown"),
        "decision_rationale": decision.get("rationale", ""),
        "reason_code": decision.get("reason_code", state.get("reason_code", "UNKNOWN")),
        "requires_human": False,
        "trace": [f"human_review: {action} by {decision.get('decided_by', 'unknown')} "
                  f"— {decision.get('rationale', 'no rationale given')}"],
    }

# %% [markdown]
# ### Step 4 — The rest of the graph
#
# Three outcomes from a human decision. Note that `escalate` loops back to
# `QUERY` — a human is allowed to say "not my call", and the workflow must have
# somewhere to put that.

# %%
def node_assess(state: HitlState) -> dict:
    variance = state.get("variance_usd", 0.0)
    return {"requires_human": True,
            "trace": [f"assess: {state['txn_id']} short by {abs(variance):,.2f}, "
                      f"no reason code — needs a human"]}


def route_decision(state: HitlState) -> str:
    return state.get("decision_action", "escalate")


def node_apply_code(state: HitlState) -> dict:
    return {"end_state": "PARTIAL_MATCH",
            "trace": [f"apply_code: dispute opened, code {state.get('reason_code')} "
                      f"for {abs(state.get('variance_usd', 0)):,.2f}"]}


def node_reject_deduction(state: HitlState) -> dict:
    return {"end_state": "WRITTEN_OFF",
            "trace": [f"reject_deduction: deduction rejected, "
                      f"{abs(state.get('variance_usd', 0)):,.2f} written back to the customer"]}


def node_escalate(state: HitlState) -> dict:  # noqa: ARG001
    return {"end_state": "QUERY", "requires_human": True,
            "trace": ["escalate: returned to the review queue at a higher tier"]}


def build_graph(checkpointer):
    b = StateGraph(HitlState)
    b.add_node("assess", node_assess)
    b.add_node("human_review", node_human_review)
    b.add_node("apply_code", node_apply_code)
    b.add_node("reject_deduction", node_reject_deduction)
    b.add_node("escalate", node_escalate)

    b.add_edge(START, "assess")
    b.add_edge("assess", "human_review")
    b.add_conditional_edges("human_review", route_decision,
                            {"assign_code": "apply_code",
                             "reject_deduction": "reject_deduction",
                             "escalate": "escalate"})
    for terminal in ("apply_code", "reject_deduction", "escalate"):
        b.add_edge(terminal, END)

    # ------------------------------------------------------------------
    # TODO (Blank 2): Compile the builder with checkpointer=checkpointer — without it, interrupt() has nowhere to persist state and resume is impossible
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 2 - see the TODO above")


db_path = str(Path(tempfile.gettempdir()) / "d3lab06_hitl.sqlite")

# %% [markdown]
# ### Step 5 — Suspend
#
# `thread_id` is the key the checkpointer stores state under. **One thread per
# payment.** Get this wrong — a shared thread_id — and resuming one transaction
# resumes whichever ran last, which is a silent and extremely unpleasant bug.
#
# The first `invoke` returns a state containing `__interrupt__` rather than a
# finished result. That is the graph telling you it is waiting.

# %%
TXN = {
    "run_id": new_run_id("d3l6"),
    "txn_id": "BNK-1009",
    "bank_amount_usd": 8700.00,
    "erp_amount_usd": 9000.00,
    "variance_usd": -300.00,
    "matched_invoice": "INV-1180",
    "reason_code": "UNKNOWN",
    "reason_confidence": 0.0,
    "reason_evidence": "",
    "trace": [],
}

config = {"configurable": {"thread_id": TXN["txn_id"]}}

if DURABLE:
    with SqliteSaver.from_conn_string(db_path) as saver:
        graph = build_graph(saver)
        suspended = graph.invoke(TXN, config)
        snapshot = graph.get_state(config)
        next_nodes = snapshot.next
else:
    saver = MemorySaver()
    graph = build_graph(saver)
    suspended = graph.invoke(TXN, config)
    snapshot = graph.get_state(config)
    next_nodes = snapshot.next

print(f"Graph suspended. Next node(s) waiting: {next_nodes}\n")
interrupts = suspended.get("__interrupt__", [])
if interrupts:
    payload = interrupts[0].value
    print("THE ANALYST'S SCREEN (the interrupt payload)")
    print("-" * 68)
    for key, value in payload.items():
        print(f"  {key:<18} {value}")
else:
    print("No __interrupt__ key — check that the checkpointer was passed to compile().")

print(f"\nState is persisted under thread_id={TXN['txn_id']!r}.")
print("No thread is blocked. The analyst may respond in four minutes or four days.")

# %% [markdown]
# ### Step 6 — Resume, in a *fresh* graph object
#
# This is the part that matters. We rebuild the graph from scratch — a new
# `StateGraph`, a new compile — and resume from the checkpoint. Nothing is carried
# in memory from Step 5.
#
# With `SqliteSaver` this genuinely simulates a process restart: the state came
# off disk. That is Capstone acceptance criterion #5.

# %%
ANALYST_DECISION = {
    "action": "assign_code",
    "reason_code": "D01",
    "decided_by": "J. Okonkwo (Deductions)",
    "rationale": "Customer confirmed by phone that the 300.00 relates to a "
                 "contracted price variance on the February order.",
}

if DURABLE:
    with SqliteSaver.from_conn_string(db_path) as saver2:
        graph2 = build_graph(saver2)          # FRESH graph object
        final = graph2.invoke(Command(resume=ANALYST_DECISION), config)
else:
    graph2 = build_graph(saver)               # same MemorySaver - not a real restart
    final = graph2.invoke(Command(resume=ANALYST_DECISION), config)

print(f"BNK-1009 → {final['end_state']}\n")
for i, line in enumerate(final["trace"], 1):
    print(f"  {i}. {line}")

print(f"\n  decided_by         : {final.get('decided_by')}")
print(f"  decision_rationale : {final.get('decision_rationale')}")
print(f"  reason_code        : {final.get('reason_code')}")
print(f"  requires_human     : {final.get('requires_human')}")

assert final["end_state"] == "PARTIAL_MATCH", "resume did not reach the expected end state"
assert final.get("decided_by") == ANALYST_DECISION["decided_by"], "attribution lost on resume"
print(f"""
Verified. The graph resumed inside node_human_review, on the exact line that
suspended, with every earlier field intact — and it did so from a graph object
that did not exist when the interrupt fired.
{"State came off disk. This is Capstone acceptance criterion #5." if DURABLE
 else "NOTE: MemorySaver in use — this did NOT survive process death."}""")

# %% [markdown]
# ### Step 7 — The other two decisions
#
# A human is allowed to reject the deduction, or to say "not my call". Both need
# somewhere to go. Run them on their own threads.

# %%
for label, decision, expected in [
    ("reject", {"action": "reject_deduction", "decided_by": "J. Okonkwo",
                "rationale": "No supporting evidence; customer withdrew the claim."},
     "WRITTEN_OFF"),
    ("escalate", {"action": "escalate", "decided_by": "J. Okonkwo",
                  "rationale": "Above my authority limit; routing to the controller."},
     "QUERY"),
]:
    thread = {"configurable": {"thread_id": f"{TXN['txn_id']}-{label}"}}
    if DURABLE:
        with SqliteSaver.from_conn_string(db_path) as s3:
            g = build_graph(s3)
            g.invoke({**TXN, "trace": []}, thread)
            out = g.invoke(Command(resume=decision), thread)
    else:
        g = build_graph(saver)
        g.invoke({**TXN, "trace": []}, thread)
        out = g.invoke(Command(resume=decision), thread)

    print(f"{label:<10} → {out['end_state']:<14} (expected {expected})")
    assert out["end_state"] == expected, f"{label} routed to {out['end_state']}"

print("\nAll three decision paths verified on separate threads.")

# %% [markdown]
# ### Step 8 — What this unblocks, and what it costs
#
# Capstone acceptance criteria 5 and 6 are now reachable. Two operational
# consequences to name before anyone ships this.

# %%
print("""
UNBLOCKED
  #5  a run survives process death and resumes  -> checkpointer
  #6  QUERY suspends and resumes on human input -> interrupt + Command

COSTS TO NAME BEFORE SHIPPING
  1. Every checkpoint persists the WHOLE state. If remittance_text holds 40 KB of
     PDF text, you are writing 40 KB per node per payment. Decide what belongs in
     state versus what belongs behind a reference — and note this is exactly the
     trade-off flagged as an open question back in Day 1 Lab 3.

  2. Checkpoints contain customer data. They need a retention policy and
     something that deletes them. A checkpoint store with no deletion story is a
     compliance finding, and it is easy to overlook because it looks like plumbing.

  3. A suspended thread is an open work item. If suspensions arrive faster than
     analysts clear them, you have moved the bottleneck rather than removed it.
     Model the queue before you model the happy path.

  4. thread_id must be unique per payment. A shared thread_id means resuming one
     transaction resumes whichever ran last — silent, and very unpleasant.""")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] The first `invoke` returns `__interrupt__` and `get_state().next` names the waiting node.
# - [ ] The payload reads like an analyst's screen, not a state dump.
# - [ ] Resume works from a **freshly built** graph object.
# - [ ] `decided_by` and `decision_rationale` survive into the final state.
# - [ ] All three decision paths reach their expected end states on separate threads.
# - [ ] You can explain why `interrupt()` does not block a thread.
#
# ### Discussion — 10 minutes
#
# 1. What belongs in a checkpointed state and what belongs behind a reference?
#    Argue both sides for `remittance_text`.
# 2. Should a `REJECTED_SECURITY_HOLD` be releasable by an analyst using this same
#    mechanism? What new risk does that create? (You have just built a way for a
#    human to override a security control. Who may do that, and who reviews it?)
# 3. Two analysts open the same suspended transaction and both submit a decision.
#    What happens? What should?
#
# ### Business impact
#
# This is what makes `QUERY` a workflow step rather than a shrug. Without it, every
# exception is a dead end and the automation's real output is a list of things
# somebody else has to do in another system. With it, the human decision is part of
# the audited workflow — attributed, reasoned, and resumable — which is the
# difference between an automation and a triage tool.
