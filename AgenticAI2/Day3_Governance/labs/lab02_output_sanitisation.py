# ==========================================================================
# STARTER FILE - Day 3 Lab 2 - Output Sanitisation and Masking Gates
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

# LAB TITLE: Day 3 Lab 2 - Output Sanitisation and Masking Gates
# %% [markdown]
# ## Day 3 · Lab 2 — Output Sanitisation & Masking Gates
#
# **Duration:** 45 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# Lab 1 was about what goes **in**. This is about what comes **out** — and it is
# the one auditors ask about first, because a disclosure is reportable and a
# blocked prompt is not.
#
# ### The gap in what you already built
#
# Day 1 Lab 1 gave you redaction that keys off the **field name**, recursively:
# `api_key`, `authorization`, `bank_account`. Blunt, deterministic, and correct
# for a control that must never silently fail.
#
# Now ask where it fails. A remittance note reading *"remit to account
# 0012-9981-4420"* sails straight through, because the field is called
# `remittance_text` and there is nothing suspicious about that name.
#
# | Control | Keys off | Catches | Misses |
# |---|---|---|---|
# | Day 1 — name-based | the key | secrets in known fields | anything in free text |
# | **Day 3 — content-based** | the value | account numbers, cards, keys in prose | semantically leaked context |
#
# You need both. Neither is sufficient alone.
#
# ### Prerequisites
# Day 3 Lab 1 complete. No Azure calls.

# %%
"""Day 3 Lab 2 - Output Sanitisation and Masking Gates."""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import settings                             # noqa: E402
from shared.telemetry import configure, get_logger, log_event   # noqa: E402

configure(level=settings.log_level, logfile="d3lab02_audit.log")
log = get_logger("day3.lab2")

# %% [markdown]
# ### Step 1 — Content patterns
#
# Each pattern has a **class**, which decides what happens to the match:
#
# | Class | Action | Rationale |
# |---|---|---|
# | `secret` | replace entirely | an API key has no analytical value; there is no safe partial |
# | `financial` | mask, keep last 4 | analysts genuinely need to reconcile "the account ending 4420" |
# | `identity` | mask, keep domain/shape | enough to correlate, not enough to identify |
#
# > **Masking is not the same as deletion, and the difference is operational.**
# > Delete an account number and your analyst cannot match the remittance to the
# > bank feed. Keep the last four and they can. Choose per class, deliberately —
# > "redact everything" is a control that gets worked around.

# %%
@dataclass(frozen=True)
class RedactionRule:
    name: str
    pattern: re.Pattern
    cls: str          # secret | financial | identity
    keep_tail: int    # characters preserved at the end, 0 = replace entirely


RULES = [
    RedactionRule("api_key_openai", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "secret", 0),
    RedactionRule("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b"), "secret", 0),
    RedactionRule("azure_key", re.compile(r"\b[a-f0-9]{32}\b"), "secret", 0),
    RedactionRule("connection_string",
                  re.compile(r"\b(AccountKey|Password|Pwd)=[^;\s]{8,}", re.I), "secret", 0),
    RedactionRule("payment_card",
                  re.compile(r"\b(?:\d[ -]?){13,16}\d\b"), "financial", 4),
    RedactionRule("bank_account",
                  re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}\b"), "financial", 4),
    RedactionRule("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,26}\b"), "financial", 4),
    RedactionRule("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "identity", 0),
    RedactionRule("us_tax_id", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "identity", 4),
]

# %% [markdown]
# ### Step 2 — The redaction function
#
# Returns the cleaned text **and** an inventory of what was removed. The inventory
# is what goes to the audit log; the text is what goes to the user.
#
# Note it records the rule name and a count — never the matched value. Same
# discipline as Lab 1: a control that logs the secret has moved the leak, not
# stopped it.

# %%
def redact(text: str) -> tuple[str, list[dict]]:
    """Mask sensitive content. Returns (clean_text, inventory)."""
    inventory: list[dict] = []
    clean = text

    for rule in RULES:
        # ------------------------------------------------------------------
        # TODO (Blank 1): Find every match of rule.pattern in `clean`. For each, build the replacement: if rule.keep_tail is 0 use f'[REDACTED:{rule.name}]', otherwise mask all but the last keep_tail characters with '*'. Replace in `clean` and append a dict with rule, cls and count to `inventory`.
        # ------------------------------------------------------------------
        raise NotImplementedError("Lab blank 1 - see the TODO above")

    if inventory:
        log_event(log, "output_redacted",
                  rules=[i["rule"] for i in inventory],
                  total=sum(i["count"] for i in inventory))
    return clean, inventory

# %% [markdown]
# ### Step 3 — Run it on a realistic leaky response
#
# This is not a contrived string. Every element here is something that genuinely
# ends up in an LLM response: quoted document content, an echoed configuration
# value, and a contact address pulled from the remittance header.

# %%
LEAKY = """Deduction classified as D03 (Damage Claim), confidence 0.85.

Supporting evidence from the remittance: "Five units arrived crushed. Please
remit the credit to account 0012-9981-4420 and confirm to
accounts.payable@acmecorp.example."

Debug context: endpoint=https://eastus.api.example.com AccountKey=Zm9vYmFyc2VjcmV0
auth=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdef
trace_key=9f8e7d6c5b4a39281706f5e4d3c2b1a0
Card on file for refund: 4111 1111 1111 1111"""

clean, inventory = redact(LEAKY)

print("BEFORE")
print("-" * 76)
print(LEAKY)
print("\nAFTER")
print("-" * 76)
print(clean)

print("\nREDACTION INVENTORY (this is what goes to the audit log)")
print("-" * 76)
for item in inventory:
    print(f"  {item['rule']:<22}{item['cls']:<12}{item['count']} match(es)")

# %% [markdown]
# ### Step 4 — Prove the Day 1 gap is real
#
# Run the **same** payload through Day 1's name-based redaction. It is inside a
# field called `remittance_text`, so nothing fires.
#
# This is not a criticism of Day 1's control — it is correct for what it does. It
# is a demonstration that the two controls cover different ground.

# %%
from shared.telemetry import _scrub  # noqa: E402  - name-based redaction from Day 1

record = {"txn_id": "BNK-1002", "api_key": "sk-live-abcdef1234567890abcdef",
          "remittance_text": "remit to account 0012-9981-4420 per our note"}

name_based = _scrub(record)
print("NAME-BASED (Day 1):")
print(f"  api_key         -> {name_based['api_key']}")
print(f"  remittance_text -> {name_based['remittance_text']}")

content_based, _ = redact(record["remittance_text"])
print(f"\nCONTENT-BASED (Day 3):")
print(f"  remittance_text -> {content_based}")

print("""
Day 1 caught the secret because the KEY was called api_key. It missed the account
number because the key was called remittance_text and nothing about that name is
suspicious. Day 3 catches it because it inspects the VALUE.

Neither control is redundant. Ship both.""")

# %% [markdown]
# ### Step 5 — Structured error envelopes
#
# The leak everybody forgets. A raw exception can carry your endpoint, your
# deployment name and sometimes a partial token. If that reaches a user-facing
# message, a support ticket or a log aggregator, it is a disclosure.
#
# The fix: the caller gets an **error code and a correlation ID**. The detail goes
# to the internal log, keyed on that ID. An engineer with log access can resolve
# it in seconds; anyone else gets nothing useful to an attacker.

# %%
@dataclass
class ErrorEnvelope:
    code: str
    correlation_id: str
    message: str          # safe, generic, user-facing

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "correlation_id": self.correlation_id,
                          "message": self.message}}


SAFE_MESSAGES = {
    "UPSTREAM_AUTH": "The document service could not be reached. Support has been notified.",
    "UPSTREAM_TIMEOUT": "The request took too long. Please retry.",
    "VALIDATION": "The response could not be validated and was discarded.",
    "INTERNAL": "An unexpected error occurred. Support has been notified.",
}


def to_envelope(exc: Exception, code: str = "INTERNAL") -> ErrorEnvelope:
    """Log the detail internally; return only a code and a correlation ID."""
    correlation_id = f"err-{uuid.uuid4().hex[:12]}"
    # ------------------------------------------------------------------
    # TODO (Blank 2): Redact the exception text BEFORE it reaches the internal log - log aggregators get breached too. Use redact() on f'{type(exc).__name__}: {exc}'
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 2 - see the TODO above")
    log_event(log, "error_captured", level=40,
              correlation_id=correlation_id, code=code, detail=detail)
    return ErrorEnvelope(code, correlation_id, SAFE_MESSAGES.get(code, SAFE_MESSAGES["INTERNAL"]))


raw = RuntimeError(
    "401 Unauthorized calling https://eastus.api.example.com/openai/deployments/"
    "gpt4o-prod/chat/completions?api-version=2024-10-21 "
    "with api-key=9f8e7d6c5b4a39281706f5e4d3c2b1a0")

print("RAW EXCEPTION — what a naive handler would surface:")
print(f"  {raw}\n")

envelope = to_envelope(raw, "UPSTREAM_AUTH")
print("ENVELOPE — what the caller receives:")
print(json.dumps(envelope.to_dict(), indent=2))
print("""
Gone from the caller's view: the endpoint, the deployment name, the API version
and the key. Retained: a correlation ID that resolves to the full (redacted)
detail in the internal log. Note we redact the detail even on the INTERNAL path —
log aggregators get breached too.""")

# %% [markdown]
# ### Step 6 — What content-based redaction does NOT catch
#
# Be precise about the limit, because this is the slide your security architect
# will push on.
#
# The gate matches **shapes**. It cannot detect a leak that has no shape: a model
# summarising another customer's remittance in fluent prose, with no account
# number, no key and no email. Nothing here fires.
#
# The control for that is not a regex. It is the **metadata filter** you built on
# Day 2 Lab 1 — the retrieval never returns another customer's chunk in the first
# place. Data segregation at retrieval time, not redaction at output time.

# %%
SEMANTIC_LEAK = (
    "For context, another customer on this account group recently withheld a "
    "substantial sum over a quality dispute at their east-coast distribution "
    "centre, and their controller indicated further deductions were likely.")

clean_leak, inv = redact(SEMANTIC_LEAK)
print(f"redaction findings : {inv or 'none'}")
print(f"text unchanged     : {clean_leak == SEMANTIC_LEAK}")
print("""
Nothing fired, and nothing should have — there is no pattern to match. Yet this
discloses another customer's commercial position.

Controls do not compose by stacking more of the same kind. Output redaction
catches SHAPES. Retrieval filtering prevents ACCESS. You need the second one for
this, and you already built it on Day 2.""")

# %% [markdown]
# ### Step 7 — The node

# %%
def node_output_guardrail(state: dict) -> dict:
    """Redact model-facing output before it leaves the workflow."""
    evidence = state.get("reason_evidence", "") or ""
    if not evidence:
        return {"trace": ["output_guardrail: nothing to sanitise"]}

    clean, inventory = redact(evidence)
    flags = [{"control": f"redaction:{i['rule']}", "severity": "flag",
              "detail": f"{i['count']} {i['cls']} match(es) masked",
              "node": "output_guardrail"} for i in inventory]
    return {
        "reason_evidence": clean,
        "security_flags": flags,
        "trace": [f"output_guardrail: {sum(i['count'] for i in inventory)} item(s) masked"
                  if inventory else "output_guardrail: clean"],
    }


for label, text in [("clean", "Five units arrived crushed and unusable"),
                    ("leaky", "Credit account 0012-9981-4420, contact ap@acme.example")]:
    out = node_output_guardrail({"txn_id": "DEMO", "reason_evidence": text})
    print(f"{label:<7} {out['trace'][0]}")
    print(f"        -> {out['reason_evidence']}")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] `redact()` replaces secrets entirely and masks financial values to the last 4.
# - [ ] The inventory records rule names and counts, never matched values.
# - [ ] You can demonstrate the Day 1 name-based gap with the `remittance_text` example.
# - [ ] The error envelope discloses only a code and a correlation ID.
# - [ ] You can name a leak that neither gate catches, and the control that does.
#
# ### Discussion — 8 minutes
#
# 1. `azure_key` matches any 32-character hex string. What legitimate content is
#    that shape? (Git SHAs, MD5 checksums, some document IDs.) Is the false
#    positive acceptable here, given the class is `secret`?
# 2. Financial values keep the last four digits. Who decided four? Under what
#    policy? Is four safe for a six-digit sort code?
# 3. Your production error handling today: pick one exception path and trace what
#    a user would actually see. Most teams find something they would rather not
#    have disclosed.
#
# ### Business impact
#
# Disclosure is the failure mode with a regulatory reporting obligation attached.
# Everything else on Day 3 degrades a decision; this one creates a notifiable
# event. Both gates together cost microseconds and are deterministic — there is no
# cost argument against shipping them, only an attention argument, which is why
# they are usually missing.
