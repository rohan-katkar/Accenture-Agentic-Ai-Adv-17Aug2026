# ==========================================================================
# STARTER FILE - Day 2 Lab 2 - Building External System Integration Tools
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

# LAB TITLE: Day 2 Lab 2 - Building External System Integration Tools
# %% [markdown]
# ## Day 2 · Lab 2 — Building External System Integration Tools
#
# **Duration:** 45 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# The agent needs to look things up in the ERP. The question is *how*.
#
# | Approach | What your security architect says |
# |---|---|
# | Give the model a database connection string | no |
# | Let the model write SQL you execute | no |
# | **Expose named tools with typed signatures** | yes |
#
# A tool is a function with a declared name, declared parameters and a declared
# return shape. The model chooses *which* tool and *what arguments*. It never
# chooses *what the tool does*. That boundary is the entire security argument, and
# it is what MCP formalises for cross-process tool calling.
#
# ### What you build
#
# Four tools the reconciliation graph needs, plus a registry that enforces a
# permission model and logs every invocation.
#
# ### Prerequisites
# Day 2 Lab 1 complete.

# %%
"""Day 2 Lab 2 - Building External System Integration Tools."""

from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import SEED_DIR, settings                   # noqa: E402
from shared.telemetry import configure, get_logger, log_event  # noqa: E402

configure(level=settings.log_level, logfile="d2lab02_audit.log")
log = get_logger("day2.lab2")

# %% [markdown]
# ### Step 1 — A tool registry with a permission model
#
# Three properties every enterprise tool layer needs, and which a bare Python
# function does not give you:
#
# 1. **A declared schema** — so the model knows what arguments are legal
# 2. **A permission class** — `read` tools are safe to call speculatively;
#    `write` tools move money and must never be called without an approved state
# 3. **An audit record per invocation** — arguments in, outcome out, duration
#
# > **The rule to state plainly:** a `write` tool is never invoked by a model
# > choosing to invoke it. It is invoked by *your code*, after your state machine
# > has reached a state that authorises it. The model may recommend; the graph
# > decides. Day 3 hardens this further with security holds.

# %%
Permission = Literal["read", "write"]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, str]
    permission: Permission
    fn: Callable[..., Any]
    call_count: int = 0
    total_ms: float = 0.0

    def schema(self) -> dict:
        """The description shape a function-calling API expects."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {k: {"type": "string", "description": v}
                                   for k, v in self.parameters.items()},
                    "required": list(self.parameters),
                },
            },
        }


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)

    def register(self, name: str, description: str,
                 parameters: dict[str, str], permission: Permission):
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = Tool(name, description, parameters, permission, fn)
            return fn
        return decorator

    def invoke(self, name: str, arguments: dict, *,
               allow_write: bool = False, run_id: str = "-") -> dict:
        """Call a tool by name. Returns a uniform envelope, never a bare value."""
        tool = self.tools.get(name)
        if tool is None:
            # The model hallucinated a tool. Refuse loudly, do not improvise.
            self._audit(name, arguments, ok=False, ms=0.0, run_id=run_id,
                        outcome="tool_not_found")
            log_event(log, "tool_not_found", level=40, tool=name, run_id=run_id)
            return {"ok": False, "error": f"no such tool: {name}",
                    "available": sorted(self.tools)}

        # ------------------------------------------------------------------
        # TODO (Blank 1): If tool.permission == 'write' and allow_write is False, log a refusal and return {'ok': False, 'error': ...} without calling fn
        # ------------------------------------------------------------------
        raise NotImplementedError("Lab blank 1 - see the TODO above")

        started = time.perf_counter()
        try:
            result = tool.fn(**arguments)
            ok, payload = True, result
        except TypeError as exc:
            ok, payload = False, f"bad arguments: {exc}"
        except Exception as exc:  # noqa: BLE001
            ok, payload = False, f"{type(exc).__name__}: {exc}"

        elapsed = (time.perf_counter() - started) * 1000
        tool.call_count += 1
        tool.total_ms += elapsed

        record = self._audit(name, arguments, ok=ok, ms=elapsed, run_id=run_id,
                             outcome="executed" if ok else "raised")
        log_event(log, "tool_invoked", **record)
        return {"ok": ok, "result" if ok else "error": payload}

    def _audit(self, name: str, arguments: dict, *, ok: bool, ms: float,
               run_id: str, outcome: str) -> dict:
        """Every attempt is recorded - including the ones that never ran.

        A refused write and a hallucinated tool name are the two most
        interesting lines in an audit ledger. If they are only visible as a
        return value, they are invisible to the auditor.
        """
        record = {"tool": name, "arguments": arguments, "ok": ok,
                  "outcome": outcome, "duration_ms": round(ms, 2), "run_id": run_id}
        self.audit.append(record)
        return record

    def catalogue(self) -> list[dict]:
        return [t.schema() for t in self.tools.values()]


registry = ToolRegistry()

# %% [markdown]
# ### Step 2 — Load the ERP data the tools will serve
#
# CSV today, a SQL view tomorrow. The tool signature does not change, which is the
# point of putting the boundary here.

# %%
with open(SEED_DIR / "erp_ar_open.csv", newline="", encoding="utf-8") as fh:
    AR_ROWS = [r for r in csv.DictReader(fh) if r["status"] == "OPEN"]

with open(SEED_DIR / "deduction_codes.csv", newline="", encoding="utf-8") as fh:
    CODE_ROWS = list(csv.DictReader(fh))

DISPUTES: list[dict] = []   # stands in for the deductions sub-ledger

print(f"{len(AR_ROWS)} open AR items, {len(CODE_ROWS)} deduction codes loaded")

# %% [markdown]
# ### Step 3 — Tool 1: look up open invoices
#
# Read-only. Returns a list, never a single record, even when one match is
# expected — because "exactly one" is an assumption and assumptions belong in the
# caller, where they can be checked.

# %%
@registry.register(
    name="lookup_open_invoices",
    description=("Return open accounts-receivable invoices for a customer. "
                 "Optionally narrow by invoice number or purchase-order number."),
    parameters={
        "customer_name": "Exact ERP customer name, e.g. 'Acme Corp'",
        "invoice_no": "Invoice number such as 'INV-810', or empty string for all",
    },
    permission="read",
)
def lookup_open_invoices(customer_name: str, invoice_no: str = "") -> list[dict]:
    hits = [r for r in AR_ROWS if r["customer_name"] == customer_name]
    if invoice_no:
        hits = [r for r in hits if r["invoice_no"] == invoice_no]
    return [{"invoice_no": r["invoice_no"], "po_number": r["po_number"],
             "invoice_date": r["invoice_date"], "amount_usd": float(r["amount_usd"])}
            for r in hits]


# %% [markdown]
# ### Step 4 — Tool 2: compute the applied/withheld split
#
# Deliberately **not** a model call. Arithmetic on money is the last thing you
# want a probabilistic system doing. Ask the room why this is a tool at all rather
# than inline code: the answer is that the model needs to *invoke* it to reason
# about the result, and a tool boundary gives you the audit record.

# %%
@registry.register(
    name="calculate_balance",
    description=("Compute the variance between an amount received and an amount "
                 "billed, and classify it as exact, within-tolerance, short or over."),
    parameters={
        "amount_received": "Amount actually received, as a decimal string",
        "amount_billed": "Amount originally billed, as a decimal string",
    },
    permission="read",
)
def calculate_balance(amount_received: str, amount_billed: str) -> dict:
    received, billed = float(amount_received), float(amount_billed)
    variance = round(received - billed, 2)
    tolerance = settings.write_off_tolerance_usd

    if abs(variance) < 0.005:
        classification = "exact"
    elif abs(variance) <= tolerance:
        classification = "within_tolerance"
    elif variance < 0:
        classification = "short_payment"
    else:
        classification = "overpayment"

    return {
        "amount_received": received, "amount_billed": billed,
        "variance_usd": variance, "abs_variance_usd": abs(variance),
        "classification": classification, "tolerance_usd": tolerance,
    }


# %% [markdown]
# ### Step 5 — Tool 3: resolve a deduction reason code
#
# Returns the owning team and the SLA alongside the code. The code alone is not
# actionable; the owning team is what routes the work.

# %%
@registry.register(
    name="lookup_reason_code",
    description="Return the category, owning team and SLA for a deduction code D01-D05.",
    parameters={"reason_code": "One of D01, D02, D03, D04, D05"},
    permission="read",
)
def lookup_reason_code(reason_code: str) -> dict:
    for row in CODE_ROWS:
        if row["reason_code"] == reason_code.strip().upper():
            return {"reason_code": row["reason_code"], "category": row["category"],
                    "description": row["description"],
                    "owning_team": row["owning_team"], "sla_days": int(row["sla_days"])}
    raise ValueError(f"unknown reason code {reason_code!r}; legal codes are D01-D05")


# %% [markdown]
# ### Step 6 — Tool 4: create a dispute (WRITE)
#
# This one moves money into a deductions queue. It carries `permission="write"`,
# which means the registry refuses it unless the caller explicitly authorises the
# call. You will watch that refusal fire in Step 7.
#
# Note the idempotency key. If the graph crashes after the ERP write but before
# the state is checkpointed, the retry must not create a second dispute. This is
# the "at-least-once delivery" problem, and it is not hypothetical in a nightly
# batch that can be re-run.

# %%
@registry.register(
    name="create_dispute",
    description=("Open a deduction dispute against an invoice. WRITE OPERATION - "
                 "creates a record in the deductions sub-ledger."),
    parameters={
        "invoice_no": "Invoice the deduction is claimed against",
        "amount_usd": "Disputed amount as a decimal string",
        "reason_code": "Deduction code D01-D05",
        "evidence": "Verbatim supporting text from the remittance advice",
    },
    permission="write",
)
def create_dispute(invoice_no: str, amount_usd: str,
                   reason_code: str, evidence: str) -> dict:
    key = f"{invoice_no}:{reason_code}:{float(amount_usd):.2f}"
    # ------------------------------------------------------------------
    # TODO (Blank 2): Scan DISPUTES for a record whose idempotency_key equals `key`; if found, return it with created=False and a 'no-op' note instead of creating a duplicate
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 2 - see the TODO above")

    detail = lookup_reason_code(reason_code)
    record = {
        "dispute_id": f"DSP-{len(DISPUTES) + 1001}",
        "idempotency_key": key,
        "invoice_no": invoice_no,
        "amount_usd": round(float(amount_usd), 2),
        "reason_code": reason_code,
        "owning_team": detail["owning_team"],
        "sla_days": detail["sla_days"],
        "evidence": evidence[:280],
        "status": "OPEN",
    }
    DISPUTES.append(record)
    return {**record, "created": True}


# %% [markdown]
# ### Step 7 — Exercise the registry
#
# Six calls: four that should succeed, one hallucinated tool, one unauthorised
# write. Read each envelope.

# %%
print("TOOL CATALOGUE (this is what a function-calling API receives)")
print("-" * 78)
for schema in registry.catalogue():
    fn = schema["function"]
    perm = registry.tools[fn["name"]].permission.upper()
    print(f"  [{perm:<5}] {fn['name']}({', '.join(fn['parameters']['properties'])})")
    print(f"           {fn['description'][:76]}")

print("\nINVOCATIONS")
print("-" * 78)

calls = [
    ("lookup_open_invoices", {"customer_name": "Acme Corp", "invoice_no": "INV-810"}, False),
    ("calculate_balance", {"amount_received": "9500.00", "amount_billed": "10000.00"}, False),
    ("lookup_reason_code", {"reason_code": "D03"}, False),
    ("lookup_reason_code", {"reason_code": "D99"}, False),          # bad argument
    ("delete_all_invoices", {"confirm": "yes"}, False),             # hallucinated tool
    ("create_dispute", {"invoice_no": "INV-810", "amount_usd": "500.00",
                        "reason_code": "D03",
                        "evidence": "Five units arrived crushed and unusable"}, False),
]

for name, args, allow_write in calls:
    envelope = registry.invoke(name, args, allow_write=allow_write, run_id="d2l2")
    status = "OK  " if envelope["ok"] else "FAIL"
    body = envelope.get("result", envelope.get("error"))
    print(f"  [{status}] {name}")
    print(f"           {json.dumps(body, default=str)[:110]}")

# %% [markdown]
# ### Step 8 — The authorised write
#
# Same tool, same arguments, one difference: the caller is the graph, and the
# graph has reached a state that authorises the write. Then call it a second time
# to prove the idempotency key works.

# %%
print("Authorised write (allow_write=True):")
first = registry.invoke("create_dispute", {
    "invoice_no": "INV-810", "amount_usd": "500.00", "reason_code": "D03",
    "evidence": "Five units arrived crushed and unusable at our Newark dock",
}, allow_write=True, run_id="d2l2")
print(f"  created={first['result']['created']}  id={first['result']['dispute_id']}  "
      f"team={first['result']['owning_team']}  SLA={first['result']['sla_days']}d")

print("\nRetry the identical call (simulating a crash-and-resume):")
second = registry.invoke("create_dispute", {
    "invoice_no": "INV-810", "amount_usd": "500.00", "reason_code": "D03",
    "evidence": "Five units arrived crushed and unusable at our Newark dock",
}, allow_write=True, run_id="d2l2")
print(f"  created={second['result']['created']}  id={second['result']['dispute_id']}  "
      f"note={second['result'].get('note')}")

assert len(DISPUTES) == 1, "idempotency key failed - a duplicate dispute was created"
print(f"\nDisputes in the sub-ledger: {len(DISPUTES)}. Exactly one. Correct.")

# %% [markdown]
# ### Step 9 — The audit ledger
#
# Every invocation, in order, with duration. This is what you hand an auditor who
# asks which systems the automation touched and with what arguments.

# %%
print(f"{'#':<3}{'TOOL':<24}{'OUTCOME':<18}{'MS':>7}  ARGUMENTS")
print("-" * 100)
for i, rec in enumerate(registry.audit, 1):
    print(f"{i:<3}{rec['tool']:<24}{rec['outcome']:<18}{rec['duration_ms']:>7}  "
          f"{json.dumps(rec['arguments'], default=str)[:40]}")

print("""
Lines 4, 5 and 6 are the ones that matter. A tool the model invented, a write it
was not allowed to make, and a bad argument - all recorded, none executed. An
audit ledger that only lists successful calls tells you nothing about what the
system REFUSED to do, which is most of what a control is for.""")

print(f"\n{'TOOL':<24}{'CALLS':>7}{'TOTAL MS':>10}{'PERMISSION':>12}")
print("-" * 55)
for tool in registry.tools.values():
    print(f"{tool.name:<24}{tool.call_count:>7}{tool.total_ms:>10.2f}{tool.permission:>12}")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] The unauthorised `create_dispute` call is refused **without** running the function.
# - [ ] The hallucinated `delete_all_invoices` returns the list of real tools instead of erroring out.
# - [ ] `lookup_reason_code("D99")` fails with a clear message, not a `KeyError` traceback.
# - [ ] Exactly one dispute exists after two identical authorised writes.
#
# ### Stretch goal — connect this to real function calling
#
# `registry.catalogue()` already emits the schema shape an OpenAI-compatible
# `tools=` parameter expects. Pass it to a chat completion, let the model choose a
# tool, and route the choice back through `registry.invoke`. Keep `allow_write`
# hard-wired to `False` on that path. **Note:** MCP formalises exactly this
# boundary for cross-process tools, and it appears in the capstone architecture
# but in no Day 1–3 lab as written — see the gap analysis.
#
# ### Discussion — 8 minutes
#
# 1. Why does `calculate_balance` exist as a tool rather than as inline code?
# 2. `create_dispute` is refused unless the caller authorises it. Where does that
#    authorisation come from in the compiled graph, and who reviews it?
# 3. Your ERP: which of these four would be a REST call, which a stored procedure,
#    and which would need a batch file? Does the tool signature change? (It should not.)
#
# ### Business impact
#
# The tool boundary is what makes an agentic workflow reviewable by a security
# team. "The model has read access to the AR tables" ends the conversation. "The
# model may call four named functions, three read-only, and every call is logged
# with its arguments" starts a different one.
