"""
shared/telemetry.py
===================
Structured logging for agentic workflows.

WHY THIS EXISTS (the Day 1 theory point, in code):
    print() produces a sentence. An agent produces a *sequence of state
    transitions*. When a payment posts to the wrong GL account at 2 a.m., the
    auditor does not want a sentence - they want the ordered, machine-parseable
    record of which node saw which state and why it branched the way it did.

Every log line here is a single-line JSON object. That is deliberate:
    - Azure Monitor / Log Analytics ingests it without a custom parser.
    - `cat run.log | jq 'select(.node=="rule_engine")'` works out of the box.
    - Financial audit needs replayability, and JSON lines replay.

Nothing in this module calls Azure. It writes to stdout and optionally to a
file. Wiring it to Application Insights is a post-course exercise; the shape of
the record is what matters pedagogically.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

_CONFIGURED = False

# Fields that must never reach a log sink in plaintext. Day 3 extends this list.
REDACT_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "bank_account",
    "account_number",
    "ssn",
    "tax_id",
}


def _scrub(value: Any) -> Any:
    """Recursively mask values whose key looks sensitive."""
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if k.lower() in REDACT_KEYS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


class JsonLineFormatter(logging.Formatter):
    """Renders each record as one JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(_scrub(extra))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(level: str = "INFO", logfile: str | None = None) -> None:
    """Install the JSON formatter on the root logger. Safe to call repeatedly."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonLineFormatter())
    root.addHandler(stream)

    if logfile:
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setFormatter(JsonLineFormatter())
        root.addHandler(file_handler)

    # Third-party libraries are chatty; keep the audit trail readable.
    for noisy in ("httpx", "httpcore", "urllib3", "chromadb", "azure"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, message: str, /, level: int = logging.INFO, **context: Any) -> None:
    """Emit a structured event.

    Usage:
        log_event(log, "match_evaluated", node="rule_engine", priority=4,
                  txn_id="BNK-1001", outcome="CLOSED")
    """
    logger.log(level, message, extra={"context": context})


# ---------------------------------------------------------------------------
# Run correlation + node timing. This is what makes a trace auditable: every
# record inside a run carries the same run_id, and every node reports duration.
# ---------------------------------------------------------------------------

def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@contextmanager
def trace_node(logger: logging.Logger, node: str, run_id: str, **context: Any) -> Iterator[dict]:
    """Time a graph node and log entry/exit as two correlated records.

    Yields a mutable dict; anything you put in it is logged on exit. That is how
    a node reports its decision without needing a second logging call.
    """
    started = time.perf_counter()
    result: dict[str, Any] = {}
    log_event(logger, "node_enter", node=node, run_id=run_id, **context)
    try:
        yield result
    except Exception as exc:  # noqa: BLE001 - we re-raise after recording
        log_event(
            logger,
            "node_error",
            level=logging.ERROR,
            node=node,
            run_id=run_id,
            error_type=type(exc).__name__,
            error=str(exc),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        raise
    else:
        log_event(
            logger,
            "node_exit",
            node=node,
            run_id=run_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            **result,
        )
