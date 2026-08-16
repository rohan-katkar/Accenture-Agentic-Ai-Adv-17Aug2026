# ==========================================================================
# STARTER FILE - Day 1 Lab 1 - Environment Setup and Enterprise Telemetry
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

# LAB TITLE: Day 1 Lab 1 - Environment Setup and Enterprise Telemetry
# %% [markdown]
# ## Day 1 · Lab 1 — Environment Setup & Enterprise Telemetry
#
# **Duration:** 35 minutes  **Difficulty:** Foundation
#
# ### Why this lab exists
#
# Every agentic system you build in this course posts money. When an automated
# cash application credits the wrong customer, the first question Finance asks is
# not *"is the model good?"* — it is *"show me what the system saw, and why it
# decided that."*
#
# A `print()` statement cannot answer that question. A structured, correlated,
# machine-parseable event stream can. So we build the audit trail **before** we
# build the agent. That ordering is deliberate and it is the whole point of
# starting here.
#
# ### What you will have at the end
#
# 1. A verified Python environment with every dependency the next 14 labs need.
# 2. A JSON-lines logger that redacts secrets automatically.
# 3. A correlated run trace you can filter with `jq` — the shape an auditor wants.
#
# ### Prerequisites
#
# | Item | Detail |
# |---|---|
# | Python | 3.11 or 3.12 |
# | Install | `pip install -r 00_Program/requirements.txt` |
# | Config | copy `00_Program/.env.example` to `.env` at the repo root |
# | Azure | not required for this lab — telemetry is entirely local |
#
# ### Trainer note
#
# Run this lab yourself on the delivery laptop the morning of the session. It is
# the canary: if `chromadb` or `langgraph` failed to install, this is where you
# find out — not at 14:30 on Day 2 with twenty people waiting.

# %%
"""Day 1 Lab 1 - Environment Setup and Enterprise Telemetry."""

from __future__ import annotations

import importlib
import json
import logging
import sys
from pathlib import Path

# --- make `from shared...` work no matter where this file was launched from ---
_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

# %% [markdown]
# ### Step 1 — Verify the dependency surface
#
# We check imports, not `pip list`. A package can be installed and still fail to
# import (wrong architecture, broken native wheel, shadowed by a local file named
# `chromadb.py`). Importing is the only honest test.
#
# `langgraph-checkpoint-sqlite` is checked separately: it is the package that
# makes Human-In-The-Loop possible in the Capstone, and it is the one people most
# often skip because no Day 1 lab appears to need it.

# %%
REQUIRED = [
    ("langgraph", "State machine orchestration - Days 1, 2, 3, Capstone"),
    ("openai", "Azure OpenAI access - all model calls"),
    ("pydantic", "Typed data contracts - Day 2 onward"),
    ("chromadb", "Vector store - Day 2, Capstone"),
    ("pandas", "ERP / bank ledger handling - all days"),
    ("streamlit", "Lab web applications - all days"),
]
OPTIONAL = [
    ("azure.ai.projects", "Foundry project SDK - optional Path B"),
    ("azure.identity", "Managed identity credentials - optional Path B"),
    ("langgraph.checkpoint.sqlite", "Durable checkpoints - REQUIRED by the Capstone"),
    ("pypdf", "PDF remittance parsing - Day 2 stretch goal"),
]


def check(modules: list[tuple[str, str]], label: str) -> list[str]:
    """Import each module and report. Returns the list that failed."""
    print(f"\n{label}")
    print("-" * 72)
    failed: list[str] = []
    for name, purpose in modules:
        try:
            mod = importlib.import_module(name)
            version = getattr(mod, "__version__", "")
            print(f"  OK    {name:<32} {version:<12} {purpose}")
        except Exception as exc:  # noqa: BLE001 - we want the reason, whatever it is
            failed.append(name)
            print(f"  FAIL  {name:<32} {'':<12} {type(exc).__name__}: {exc}")
    return failed


print(f"Python {sys.version.split()[0]}")
missing_required = check(REQUIRED, "REQUIRED PACKAGES")
missing_optional = check(OPTIONAL, "OPTIONAL PACKAGES")

if missing_required:
    print("\n*** STOP. Required packages are missing. ***")
    print("    pip install -r 00_Program/requirements.txt")
if "langgraph.checkpoint.sqlite" in missing_optional:
    print("\n*** WARNING: langgraph-checkpoint-sqlite is absent.")
    print("    Day 1-3 will run. The Capstone Human-In-The-Loop step will not.")
    print("    pip install langgraph-checkpoint-sqlite")

# %% [markdown]
# ### Step 2 — Configure structured telemetry
#
# `shared/telemetry.py` installs a formatter that renders every log record as one
# JSON object on one line. Three properties matter:
#
# | Property | Why Finance cares |
# |---|---|
# | One line per event | Log Analytics and `jq` both ingest it with no custom parser |
# | UTC ISO-8601 timestamps | Reconciliation across regions needs one clock |
# | Automatic key redaction | An API key in a log file is a reportable incident |
#
# Call `configure()` **once**, at process entry. Calling it inside a node gives
# you duplicated handlers and every line printed four times.

# %%
from shared.telemetry import configure, get_logger, log_event, new_run_id, trace_node  # noqa: E402

# ------------------------------------------------------------------
# TODO (Blank 1): Call configure() with level 'INFO' and logfile 'lab01_audit.log'
# ------------------------------------------------------------------
raise NotImplementedError("Lab blank 1 - see the TODO above")

log = get_logger("day1.lab1")
log_event(log, "environment_verified",
          python=sys.version.split()[0],
          missing_required=missing_required,
          missing_optional=missing_optional)

# %% [markdown]
# ### Step 3 — Prove that redaction works
#
# This is not decoration. Day 3 spends a full lab on data leakage; the control
# starts here, at the logging boundary, because that is the earliest point at
# which a secret can escape the process.
#
# Watch what happens to `api_key` and `bank_account` in the output below. The
# redaction is driven by **key name**, recursively, at any depth. That is a
# deliberately blunt instrument — blunt is correct for a control that must never
# silently fail.

# %%
log_event(
    log, "credential_bundle_received",
    tenant="accenture-batch1",
    api_key="sk-live-THIS-MUST-NEVER-APPEAR-IN-A-LOG",
    nested={"authorization": "Bearer eyJhbGciOi...", "region": "eastus"},
    customer={"name": "Acme Corp", "bank_account": "0012-9981-4420"},
)
print("\n^ Confirm: api_key, authorization and bank_account all read ***REDACTED***")
print("  region, tenant and customer name survived. Redaction is targeted, not blanket.\n")

# %% [markdown]
# ### Step 4 — Correlate a run
#
# A single event is trivia. A **correlated sequence** is an audit trail.
#
# `new_run_id()` mints one identifier for one payment's journey. `trace_node()`
# wraps a unit of work and emits `node_enter` / `node_exit` with a duration, or
# `node_error` if it raises. Every record carries the same `run_id`.
#
# That is exactly the pattern the Capstone reconciliation graph uses — you are
# writing the observability layer three days before you need it.

# %%
run_id = new_run_id("recon")
print(f"Simulating one payment through three nodes. run_id = {run_id}\n")

with trace_node(log, "ingest", run_id, txn_id="BNK-1002", source="bank_statement.csv") as out:
    out["records_read"] = 1
    out["amount_usd"] = 9500.00

with trace_node(log, "rule_engine", run_id, txn_id="BNK-1002") as out:
    # ------------------------------------------------------------------
    # TODO (Blank 2): Record priority=1, match_type='2-way', matched_invoice='INV-810' in `out`
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 2 - see the TODO above")
    out["variance_usd"] = -500.00   # bank minus ERP: negative = short payment

with trace_node(log, "deduction_engine", run_id, txn_id="BNK-1002") as out:
    out["reason_code"] = "D03"
    out["end_state"] = "PARTIAL_MATCH"

# %% [markdown]
# ### Step 5 — Failures must be as traceable as successes
#
# A node that raises still has to leave a record. If the only evidence of a
# failure is a stack trace on someone's terminal, the failure is invisible to the
# audit. `trace_node` logs `node_error` with the exception type and the elapsed
# time, **then re-raises** — it observes, it does not swallow.

# %%
try:
    with trace_node(log, "erp_post", run_id, txn_id="BNK-1002"):
        raise ConnectionError("ERP SOAP endpoint returned 503")
except ConnectionError as exc:
    print(f"\nException surfaced to caller as expected: {exc}")
    print("A node_error record was written before the raise propagated.\n")

# %% [markdown]
# ### Step 6 — Read the trail back
#
# The file `lab01_audit.log` now holds the full run. Because every line is JSON,
# you can query it without writing a parser.
#
# On the command line an auditor would run:
#
# ```bash
# cat lab01_audit.log | jq 'select(.run_id=="recon-...") | {ts, message, node, duration_ms}'
# ```
#
# Below we do the same thing in Python so the lab has no shell dependency.

# %%
audit_path = Path("lab01_audit.log")
if audit_path.exists():
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    this_run = [r for r in records if r.get("run_id") == run_id]

    print(f"{len(records)} total events; {len(this_run)} belong to run {run_id}\n")
    print(f"{'EVENT':<16}{'NODE':<20}{'MS':>8}  DETAIL")
    print("-" * 78)
    for r in this_run:
        detail = {k: v for k, v in r.items()
                  if k not in {"ts", "level", "logger", "message", "run_id", "node", "duration_ms"}}
        print(f"{r['message']:<16}{r.get('node', ''):<20}"
              f"{r.get('duration_ms', ''):>8}  {json.dumps(detail) if detail else ''}")

    total_ms = sum(r.get("duration_ms", 0) for r in this_run if r["message"] == "node_exit")
    print(f"\nSuccessful node time for this run: {total_ms:.2f} ms")
    print("In production this number is the SLA metric Operations is measured on.")
else:
    print("lab01_audit.log not found - did Blank 1 pass a logfile argument?")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] Every REQUIRED package reports `OK`.
# - [ ] `api_key`, `authorization` and `bank_account` all print `***REDACTED***`.
# - [ ] `lab01_audit.log` exists and every line parses as JSON.
# - [ ] One `run_id` links ingest → rule_engine → deduction_engine → erp_post.
# - [ ] The failing node produced `node_error` **and** the exception reached your code.
#
# ### Discussion — 5 minutes, whole room
#
# 1. Your current production Python services: could you reconstruct a single
#    request's path across services from the logs alone? What is missing?
# 2. Redaction here keys off the *field name*. Name a payload where that fails.
#    (Hint: a free-text remittance note that quotes an account number.) What
#    control catches that instead? — you build it on Day 3.
# 3. Who in your organisation would be the consumer of this trail: SRE, Internal
#    Audit, or the O2C process owner? The answer changes what you log.
#
# ### Business impact
#
# In a live O2C automation, the cost driver is not the model — it is **exception
# handling labour**. Teams that cannot explain an automated posting escalate it to
# a human, and the automation rate collapses. Structured, correlated traces are
# what let an analyst confirm a decision in seconds instead of reproducing it.
# Treat this lab as the foundation of the automation-rate number, not as plumbing.
