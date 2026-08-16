# LAB TITLE: Day 3 Lab 3 - Real-Time Audit and Transition Logging
# %% [markdown]
# ## Day 3 · Lab 3 — Real-Time Audit & Transition Logging
#
# **Duration:** 40 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# You have been writing audit records since Day 1 Lab 1. This lab tests them
# against the four questions an auditor actually asks, in roughly this order:
#
# | # | Question | What it needs |
# |---|---|---|
# | 1 | Reconstruct one payment | every transition for one `txn_id`, ordered, with durations |
# | 2 | Justify one decision | which rule fired, which chunk, what the model returned |
# | 3 | List what was refused | blocked writes, hallucinated tools, held transactions |
# | 4 | Replay a run | same inputs → same outcome |
#
# Question 3 is the one teams forget. An audit ledger listing only successes tells
# you nothing about what the system **declined** to do — which is most of what a
# control is for.
#
# Question 4 is where honesty is required, and Step 6 deals with it.
#
# ### Prerequisites
# Day 3 Labs 1–2 complete.

# %%
"""Day 3 Lab 3 - Real-Time Audit and Transition Logging."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import settings                             # noqa: E402
from shared.telemetry import configure, get_logger, log_event, new_run_id  # noqa: E402

configure(level=settings.log_level, logfile="d3lab03_audit.log")
log = get_logger("day3.lab3")

# %% [markdown]
# ### Step 1 — The transition record
#
# A log line says *something happened*. A **transition record** says *the system
# moved from state A to state B, in node N, because of C*.
#
# The `cause` field is the one that answers question 2. Without it you have a
# timeline; with it you have an explanation. It is also the field people leave out,
# because at the moment of writing the code the cause feels obvious.

# %%
@dataclass
class Transition:
    run_id: str
    txn_id: str
    seq: int
    node: str
    from_state: str
    to_state: str
    cause: str                      # WHY — the field that makes it an explanation
    outcome: str                    # executed | refused | held | error
    duration_ms: float
    evidence_ref: str | None = None  # chunk id, rule name, dispute id
    ts: float = field(default_factory=time.time)


class AuditLedger:
    """Append-only transition store. In production this is a database table."""

    def __init__(self) -> None:
        self._records: list[Transition] = []
        self._seq: Counter[str] = Counter()

    def record(self, run_id: str, txn_id: str, node: str, from_state: str,
               to_state: str, cause: str, *, outcome: str = "executed",
               duration_ms: float = 0.0, evidence_ref: str | None = None) -> Transition:
        self._seq[txn_id] += 1
        t = Transition(run_id, txn_id, self._seq[txn_id], node, from_state,
                       to_state, cause, outcome, round(duration_ms, 2), evidence_ref)
        self._records.append(t)
        log_event(log, "state_transition", **{k: v for k, v in asdict(t).items() if k != "ts"})
        return t

    def for_txn(self, txn_id: str) -> list[Transition]:
        return sorted((r for r in self._records if r.txn_id == txn_id), key=lambda r: r.seq)

    def refusals(self) -> list[Transition]:
        """Question 3: what did the system decline to do?"""
        # <<<BLANK hint="Return every record whose outcome is 'refused' or 'held' — these are the negative-evidence lines an auditor needs">
        return [r for r in self._records if r.outcome in {"refused", "held"}]
        # >>>

    def all(self) -> list[Transition]:
        return list(self._records)


ledger = AuditLedger()

# %% [markdown]
# ### Step 2 — Record a realistic run
#
# Three transactions with genuinely different shapes: a clean coded deduction, a
# security hold, and a refusal. Together they exercise all four audit questions.

# %%
run = new_run_id("d3l3")

# --- BNK-1002: clean path, ends in a coded dispute ---
ledger.record(run, "BNK-1002", "ingest", "-", "OPEN",
              "bank row read from statement file", duration_ms=1.2)
ledger.record(run, "BNK-1002", "input_guardrail", "OPEN", "OPEN",
              "0 findings on remittance text", duration_ms=0.4)
ledger.record(run, "BNK-1002", "remittance_search", "OPEN", "OPEN",
              "2 chunks within threshold 0.92", duration_ms=18.7,
              evidence_ref="BNK-1002::01::a3f2b1c9d0")
ledger.record(run, "BNK-1002", "rule_engine", "OPEN", "MATCHED",
              "priority 1: customer + PO-5541 -> INV-810", duration_ms=2.1,
              evidence_ref="rule_p1_customer_po")
ledger.record(run, "BNK-1002", "classify_deduction", "MATCHED", "CODED",
              "D03 at confidence 0.85, citation verified verbatim", duration_ms=412.0,
              evidence_ref="BNK-1002::01::a3f2b1c9d0")
ledger.record(run, "BNK-1002", "output_guardrail", "CODED", "CODED",
              "0 items masked", duration_ms=0.3)
ledger.record(run, "BNK-1002", "open_dispute", "CODED", "PARTIAL_MATCH",
              "graph-authorised write, 500.00 to Quality, SLA 10d", duration_ms=6.4,
              evidence_ref="DSP-1001")

# --- BNK-4001: injection attempt, held ---
ledger.record(run, "BNK-4001", "ingest", "-", "OPEN", "bank row read", duration_ms=1.1)
ledger.record(run, "BNK-4001", "input_guardrail", "OPEN", "REJECTED_SECURITY_HOLD",
              "instruction_override: instruction-override phrasing @ 84",
              outcome="held", duration_ms=0.5, evidence_ref="instruction_override")

# --- BNK-4002: model recommended a write the graph did not authorise ---
ledger.record(run, "BNK-4002", "ingest", "-", "OPEN", "bank row read", duration_ms=1.0)
ledger.record(run, "BNK-4002", "classify_deduction", "OPEN", "UNCODED",
              "UNKNOWN: remittance states no reason", duration_ms=388.0)
ledger.record(run, "BNK-4002", "tool_registry", "UNCODED", "UNCODED",
              "create_dispute refused: write not authorised in this state",
              outcome="refused", duration_ms=0.1, evidence_ref="create_dispute")
ledger.record(run, "BNK-4002", "query", "UNCODED", "QUERY",
              "routed to human review: no reason code available", duration_ms=0.6)

print(f"{len(ledger.all())} transitions recorded across 3 transactions.")

# %% [markdown]
# ### Step 3 — Question 1: reconstruct one payment
#
# The auditor names a transaction. You produce the ordered path with durations and
# evidence references. No narrative, no reconstruction from memory.

# %%
def reconstruct(txn_id: str) -> None:
    records = ledger.for_txn(txn_id)
    print(f"\nTRANSACTION {txn_id} — {len(records)} transitions, run {records[0].run_id}")
    print(f"{'#':<3}{'NODE':<20}{'FROM':<12}{'TO':<24}{'MS':>8}  CAUSE")
    print("-" * 108)
    for r in records:
        print(f"{r.seq:<3}{r.node:<20}{r.from_state:<12}{r.to_state:<24}"
              f"{r.duration_ms:>8}  {r.cause[:44]}")
    total = sum(r.duration_ms for r in records)
    print(f"{'':<59}{total:>8}  TOTAL")


reconstruct("BNK-1002")
reconstruct("BNK-4001")

# %% [markdown]
# ### Step 4 — Question 2: justify one decision
#
# "Why was $500 disputed against INV-810 as a damage claim?"
#
# The answer is assembled from `cause` and `evidence_ref`, not written by hand.
# Every link in the chain points at something inspectable.

# %%
def justify(txn_id: str) -> None:
    records = ledger.for_txn(txn_id)
    print(f"\nDECISION CHAIN — {txn_id}")
    print("-" * 76)
    # <<<BLANK hint="Print only the transitions that carry an evidence_ref - those are the links an auditor can actually open and inspect">
    for r in records:
        if r.evidence_ref:
            print(f"  {r.node:<20} {r.cause}")
            print(f"  {'':<20} evidence -> {r.evidence_ref}")
    # >>>


justify("BNK-1002")
print("""
Each evidence reference resolves to something you can open: a rule function, a
chunk in the vector store, a dispute record. "The model decided" appears nowhere,
because at no point did the model decide - it recommended, and the graph acted.""")

# %% [markdown]
# ### Step 5 — Question 3: what did the system refuse to do?
#
# The negative evidence. This is the report that demonstrates your controls are
# **live** rather than merely present in the codebase.
#
# > If this report is empty, you have not proved your controls work. You have
# > proved nobody tested them.

# %%
refused = ledger.refusals()
print(f"REFUSALS AND HOLDS — {len(refused)} record(s)")
print(f"{'TXN':<12}{'NODE':<20}{'OUTCOME':<10}CAUSE")
print("-" * 96)
for r in refused:
    print(f"{r.txn_id:<12}{r.node:<20}{r.outcome:<10}{r.cause[:52]}")

by_outcome = Counter(r.outcome for r in ledger.all())
print(f"\nOutcome distribution: {dict(by_outcome)}")
print("""
Two lines, two different controls, and neither is visible in a success-only log:
  - BNK-4001 was HELD by the input guardrail before any model call was made.
  - BNK-4002 had a write REFUSED because the graph had not authorised it.

Put this table in a steering report. It is the only direct evidence that the
control set is doing anything.""")

# %% [markdown]
# ### Step 6 — Question 4: replay, and where honesty is required
#
# Deterministic nodes replay exactly: same input, same output, every time. You can
# re-run `rule_engine` on the same state in a year and get the same answer.
#
# **Model nodes do not**, even at `temperature=0`. Providers update models, and a
# deployment name is not a version pin you control.
#
# So replay means **recording the model's actual output as part of the state**, not
# re-calling the model and hoping. If the model output is not persisted, your run
# is not reproducible and you should say so rather than implying otherwise.

# %%
REPLAYABLE = {
    "ingest": ("deterministic", "re-reads the same row"),
    "input_guardrail": ("deterministic", "regex over fixed rules"),
    "remittance_search": ("conditional", "same vectors -> same neighbours, IF the corpus is unchanged"),
    "rule_engine": ("deterministic", "pure function of state"),
    "classify_deduction": ("NOT replayable", "model output must be PERSISTED, not recomputed"),
    "output_guardrail": ("deterministic", "regex over fixed rules"),
    "open_dispute": ("deterministic", "idempotency key makes the retry a no-op"),
}

print(f"{'NODE':<22}{'REPLAY':<18}NOTE")
print("-" * 92)
for node, (kind, note) in REPLAYABLE.items():
    print(f"{node:<22}{kind:<18}{note}")

print("""
One node out of seven is not replayable, and it is the one that assigns the
reason code. The mitigation is not clever: persist reason_code, reason_confidence
and reason_evidence in the state, and replay from those rather than re-calling.

Say this plainly to an auditor. "We record the model's output so the decision can
be re-examined" is a defensible position. "Our system is fully reproducible" is
not, and it will not survive the follow-up question.""")

# %% [markdown]
# ### Step 7 — Export the audit trail
#
# JSON Lines, one record per line — the same shape as Day 1's telemetry, and for
# the same reason: Log Analytics and `jq` both ingest it without a custom parser.

# %%
export_path = Path("d3lab03_transitions.jsonl")
with export_path.open("w", encoding="utf-8") as fh:
    for r in ledger.all():
        fh.write(json.dumps(asdict(r), default=str) + "\n")

lines = export_path.read_text(encoding="utf-8").splitlines()
print(f"Exported {len(lines)} transitions to {export_path}")
print("\nAn auditor's queries, without writing a parser:")
print('  jq \'select(.txn_id=="BNK-1002")\' d3lab03_transitions.jsonl')
print('  jq \'select(.outcome=="refused" or .outcome=="held")\' d3lab03_transitions.jsonl')
print('  jq \'select(.duration_ms > 100) | {node, duration_ms}\' d3lab03_transitions.jsonl')

parsed = [json.loads(line) for line in lines]
assert len(parsed) == len(ledger.all()), "export lost records"
assert all("cause" in p for p in parsed), "cause field missing from export"
print(f"\nVerified: {len(parsed)} records round-trip, all carry a cause.")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] `reconstruct("BNK-1002")` produces the ordered path with durations.
# - [ ] `justify()` links every decision to an inspectable evidence reference.
# - [ ] `refusals()` returns both the held transaction and the refused write.
# - [ ] You can name which node is not replayable, and the mitigation.
# - [ ] The JSONL export round-trips and every record carries a `cause`.
#
# ### Discussion — 8 minutes
#
# 1. `remittance_search` is marked "conditional" — same vectors give same
#    neighbours only if the corpus is unchanged. What is your corpus versioning
#    story? Most teams have none.
# 2. How long must these records be retained, under what policy, and what deletes
#    them? A vector store and an audit ledger with no deletion story are both
#    compliance findings.
# 3. If your regulator asked for a full reconstruction of one payment from six
#    months ago, what is missing today?
#
# ### Business impact
#
# Question 3 is the commercially valuable one. Teams routinely spend a control
# review defending what their system does; the strongest evidence is a short table
# of what it refused to do. It costs nothing extra to produce — the records are
# already being written — and it changes the tenor of the conversation.
