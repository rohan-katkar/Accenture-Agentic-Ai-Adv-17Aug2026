"""
Capstone/src/batch.py
=====================
Batch orchestration with durable state.

The difference between ten transactions in a script and five thousand overnight:

  * a run must SURVIVE process death and resume, not restart. Restarting is not
    merely slow - it risks re-posting to an ERP.
  * a single bad payment must not take down the batch.
  * suspended (human-review) items must be resumable independently, days later.

`thread_id` is the checkpointer key and it is ONE PER PAYMENT. A shared thread_id
means resuming one transaction resumes whichever ran last: silent, and very
unpleasant.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

from shared.telemetry import get_logger, log_event, new_run_id

from .domain import BankTransaction, load_bank_transactions
from .pipeline import build_pipeline, initial_state
from .security import to_envelope

log = get_logger(__name__)


def make_checkpointer(db_path: str | Path):
    """Prefer durable SQLite. Fall back to memory with an explicit warning.

    Returns (context_manager_or_none, saver_or_none, durable_flag). SqliteSaver
    is a context manager in current LangGraph; MemorySaver is not.
    """
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        return SqliteSaver.from_conn_string(str(db_path)), True
    except ImportError:
        from langgraph.checkpoint.memory import MemorySaver

        log_event(log, "checkpointer_fallback", level=30,
                  detail="langgraph-checkpoint-sqlite absent; runs will NOT survive "
                         "process death. pip install langgraph-checkpoint-sqlite")
        return _NullContext(MemorySaver()), False


class _NullContext:
    """Lets MemorySaver be used with the same `with` syntax as SqliteSaver."""

    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def __enter__(self) -> Any:
        return self._obj

    def __exit__(self, *exc: Any) -> bool:
        return False


@dataclass
class BatchResult:
    run_id: str
    total: int = 0
    completed: int = 0
    suspended: int = 0
    failed: int = 0
    outcomes: list[dict] = field(default_factory=list)

    @property
    def distribution(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for o in self.outcomes:
            counts[o["end_state"]] = counts.get(o["end_state"], 0) + 1
        return dict(sorted(counts.items()))

    def summary(self) -> str:
        closed = self.distribution.get("CLOSED", 0)
        lines = [
            f"run_id            : {self.run_id}",
            f"transactions      : {self.total}",
            f"completed         : {self.completed}",
            f"suspended (human) : {self.suspended}",
            f"failed            : {self.failed}",
            "",
            "END STATE DISTRIBUTION",
        ]
        lines += [f"  {k:<24}{v}" for k, v in self.distribution.items()]
        if self.total:
            lines += ["",
                      f"straight-through (CLOSED, no human) : {closed}/{self.total} "
                      f"= {closed / self.total:.0%}",
                      f"requires a human                    : "
                      f"{self.total - closed}/{self.total} = {(self.total - closed) / self.total:.0%}"]
        return "\n".join(lines)


def run_batch(transactions: list[BankTransaction] | None = None, *,
              db_path: str | Path = "capstone_state.sqlite",
              hitl: bool = True, run_id: str | None = None,
              resume_from: str | None = None) -> BatchResult:
    """Process a batch. Returns per-transaction outcomes.

    `resume_from` skips every transaction up to and including that txn_id, which
    is how you continue a batch that died partway. Because each payment has its
    own thread_id and every write is idempotent, re-running an already-processed
    transaction is a no-op rather than a duplicate posting.
    """
    txns = transactions if transactions is not None else load_bank_transactions()
    rid = run_id or new_run_id("batch")
    result = BatchResult(run_id=rid, total=0)

    if resume_from:
        try:
            start = [t.txn_id for t in txns].index(resume_from) + 1
            log_event(log, "batch_resuming", run_id=rid, after=resume_from, skipped=start)
            txns = txns[start:]
        except ValueError:
            log_event(log, "resume_marker_not_found", level=30, marker=resume_from)

    ctx, durable = make_checkpointer(db_path)
    log_event(log, "batch_started", run_id=rid, count=len(txns), durable=durable, hitl=hitl)

    with ctx as saver:
        graph = build_pipeline(saver)
        for txn in txns:
            result.total += 1
            config = {"configurable": {"thread_id": f"{rid}::{txn.txn_id}"}}
            try:
                final = graph.invoke(initial_state(txn, run_id=rid, hitl=hitl), config)
            except Exception as exc:  # noqa: BLE001 - one bad payment must not kill the batch
                envelope = to_envelope(exc, "INTERNAL")
                result.failed += 1
                result.outcomes.append({
                    "txn_id": txn.txn_id, "end_state": "FAILED",
                    "error_code": envelope.code,
                    "correlation_id": envelope.correlation_id,
                    "thread_id": config["configurable"]["thread_id"],
                })
                log_event(log, "transaction_failed", level=40, run_id=rid,
                          txn_id=txn.txn_id, correlation_id=envelope.correlation_id)
                continue

            interrupts = final.get("__interrupt__", [])
            if interrupts:
                result.suspended += 1
                payload = getattr(interrupts[0], "value", {})
                result.outcomes.append({
                    "txn_id": txn.txn_id, "end_state": "AWAITING_HUMAN",
                    "thread_id": config["configurable"]["thread_id"],
                    "ask": payload,
                })
                continue

            result.completed += 1
            result.outcomes.append({
                "txn_id": txn.txn_id,
                "end_state": final.get("end_state", "?"),
                "owner": final.get("owner", "-"),
                "matched_invoice": final.get("matched_invoice"),
                "matched_priority": final.get("matched_priority"),
                "variance_usd": final.get("variance_usd"),
                "reason_code": final.get("reason_code"),
                "dispute_id": final.get("dispute_id"),
                "write_off_usd": final.get("write_off_usd"),
                "security_flags": len(final.get("security_flags", [])),
                "thread_id": config["configurable"]["thread_id"],
                "trace": final.get("trace", []),
            })

    # NOTE: BatchResult already carries run_id, so splatting asdict() alongside
    # an explicit run_id= duplicates the keyword. Exclude both heavy and
    # already-named fields rather than relying on remembering the collision.
    log_event(log, "batch_finished", **{
        k: v for k, v in asdict(result).items() if k != "outcomes"})
    return result


def resume_transaction(thread_id: str, decision: dict, *,
                       db_path: str | Path = "capstone_state.sqlite") -> dict:
    """Resume one suspended payment with an analyst's decision.

    `decision` must carry: action, decided_by, rationale, and reason_code when
    the action is assign_code. Attribution is not optional - "a human approved
    it" is not an audit trail.
    """
    from langgraph.types import Command

    ctx, _ = make_checkpointer(db_path)
    config = {"configurable": {"thread_id": thread_id}}
    with ctx as saver:
        graph = build_pipeline(saver)
        final = graph.invoke(Command(resume=decision), config)
    log_event(log, "transaction_resumed", thread_id=thread_id,
              action=decision.get("action"), end_state=final.get("end_state"))
    return final


def pending(db_path: str | Path = "capstone_state.sqlite",
            thread_ids: list[str] | None = None) -> Iterator[dict]:
    """Yield suspended threads and the question each is waiting on."""
    if not thread_ids:
        return
    ctx, _ = make_checkpointer(db_path)
    with ctx as saver:
        graph = build_pipeline(saver)
        for tid in thread_ids:
            snapshot = graph.get_state({"configurable": {"thread_id": tid}})
            if snapshot.next:
                yield {"thread_id": tid, "waiting_on": list(snapshot.next),
                       "state": dict(snapshot.values)}


def export_outcomes(result: BatchResult, path: str | Path) -> Path:
    """Write one JSON object per line. jq-queryable, no custom parser needed."""
    out = Path(path)
    with out.open("w", encoding="utf-8") as fh:
        for o in result.outcomes:
            fh.write(json.dumps({**o, "run_id": result.run_id}, default=str) + "\n")
    return out
