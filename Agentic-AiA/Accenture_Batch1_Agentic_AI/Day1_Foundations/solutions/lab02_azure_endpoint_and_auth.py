# LAB TITLE: Day 1 Lab 2 - Azure AI Endpoint Integration and Client Authentication
# %% [markdown]
# ## Day 1 · Lab 2 — Azure AI Endpoint Integration & Client Authentication
#
# **Duration:** 40 minutes  **Difficulty:** Foundation
#
# ### Why this lab exists
#
# Two things break agentic projects at the enterprise gate, and neither is model
# quality:
#
# 1. **Authentication.** A key works on a laptop and fails in the pipeline because
#    production uses managed identity and nobody wrote the seam for it.
# 2. **Coupling.** Fifteen files each construct their own SDK client. The SDK
#    ships a breaking change. Fifteen files break.
#
# This lab builds the seam. From here to the Capstone, **no lab constructs an SDK
# client** — every one of them calls `get_chat_client()`.
#
# ### Prerequisites
#
# | Item | Detail |
# |---|---|
# | Lab 1 | complete |
# | `.env` | at repo root, from `00_Program/.env.example` |
# | Azure | an Azure OpenAI / Foundry chat deployment (or `LAB_OFFLINE_MODE=true`) |
#
# ### Trainer note — say this explicitly
#
# The `model=` parameter takes the **deployment name**, not the model family
# name. A deployment named `gpt4o-prod` must be passed as `gpt4o-prod`. This one
# fact is the single largest source of Day 1 support tickets.

# %%
"""Day 1 Lab 2 - Azure AI Endpoint Integration and Client Authentication."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import settings                      # noqa: E402
from shared.telemetry import configure, get_logger, log_event  # noqa: E402

configure(level=settings.log_level, logfile="lab02_audit.log")
log = get_logger("day1.lab2")

# %% [markdown]
# ### Step 1 — Inspect resolved configuration
#
# `shared/config.py` is the only place that reads `os.environ`. It loads the real
# process environment first, then `.env`, then defaults — so a trainer can
# override a dead key with one `export` without editing any file.
#
# Note what `describe()` does with the key: it masks it. Configuration echo is a
# routine way secrets end up in a screen recording of a training session.

# %%
print("RESOLVED LAB CONFIGURATION")
print("=" * 72)
print(settings.describe())
print("=" * 72)
print(f"\nPath A ready (Azure OpenAI endpoint + key) : {settings.path_a_ready}")
print(f"Path B ready (Foundry project SDK enabled) : {settings.path_b_ready}")
print(f"Offline mode                               : {settings.offline_mode}")

if not (settings.path_a_ready or settings.offline_mode):
    print("\nNo credentials found. The lab will run against the offline stub.")
    print("That is fine for the plumbing; model behaviour needs Path A.")

# %% [markdown]
# ### Step 2 — The static token credential adapter
#
# Azure SDKs authenticate through a **credential object**, not a raw string. The
# contract is small: expose `get_token(*scopes)` returning something with
# `.token` and `.expires_on` (POSIX seconds).
#
# `StaticTokenCredential` satisfies that contract with a fixed token. Its purpose
# is to let a key-based classroom exercise the *same code path* as an
# identity-based production deployment.
#
# > **Production guidance, stated plainly:** this adapter is a teaching and
# > break-glass construct. Shipping it means a non-rotating secret held in process
# > memory with no revocation story. Production uses `DefaultAzureCredential` or
# > `ManagedIdentityCredential`. Put that sentence in your architecture decision
# > record, not just in your notes.

# %%
from shared.foundry_client import StaticTokenCredential  # noqa: E402

demo = StaticTokenCredential("demo-token-value-not-a-real-secret", ttl_seconds=1800)

# <<<BLANK hint="Call demo.get_token() with scope 'https://cognitiveservices.azure.com/.default' and store it in `token`">
token = demo.get_token("https://cognitiveservices.azure.com/.default")
# >>>

print(f"token type   : {type(token).__name__}")
print(f"token value  : {token.token[:12]}... (truncated for display)")
print(f"expires_on   : {token.expires_on}  (~{(token.expires_on - int(time.time())) // 60} min from now)")
print("\nThe SDK never sees a string. It sees an object it can re-query when the")
print("token nears expiry - which is exactly why managed identity slots in later")
print("with no change to calling code.")

# %% [markdown]
# ### Step 3 — Acquire a chat client through the seam
#
# `get_chat_client()` picks a backend and caches it:
#
# | Condition | Backend chosen |
# |---|---|
# | `LAB_OFFLINE_MODE=true` | deterministic offline stub, no network |
# | `USE_FOUNDRY_PROJECT_SDK=true` + project endpoint | Path B, Foundry project SDK |
# | endpoint + key present | **Path A, Azure OpenAI** — the teaching path |
# | nothing configured | offline stub, with a warning |
#
# Path B **probes** for its accessor rather than hard-coding one, and fails with
# the installed package version if no known shape works. That is not defensive
# programming for its own sake — see the version risk register in
# `00_Program/VERSION_RISK_REGISTER.md`.

# %%
from shared.foundry_client import get_chat_client  # noqa: E402

client = get_chat_client()
print(f"Active backend: {client.backend_name}\n")

# %% [markdown]
# ### Step 4 — First grounded call, in the business domain
#
# We do not ask the model a toy question. From the first call, the prompt looks
# like the system you are actually building: a remittance note in, a deduction
# classification out.
#
# Two prompt properties to point at:
#
# - **`temperature=0.0`.** Financial classification is not a creative task. A
#   non-deterministic reason code is an audit finding.
# - **A closed code set in the system prompt.** The model chooses from D01–D05 or
#   says `UNKNOWN`. It is never invited to invent `D07`.

# %%
SYSTEM = (
    "You are an accounts receivable deduction classifier for an enterprise O2C "
    "process. Classify the customer's stated reason for a short payment into "
    "exactly one code:\n"
    "  D01 Pricing Issue    - contracted price differs from billed price\n"
    "  D02 Freight Claim    - unauthorised shipping or handling charge\n"
    "  D03 Damage Claim     - goods received broken, corrupted or unusable\n"
    "  D04 Tax Difference   - exemption claimed or sales tax variance\n"
    "  D05 Discount Taken   - early-payment discount taken outside terms\n"
    "If the text does not support any code, answer UNKNOWN. Never invent a code."
)

REMITTANCE = (
    "Invoice INV-810 for 10,000.00. We are remitting 9,500.00. Five units arrived "
    "crushed and unusable at our Newark dock on 27 February; photographs went to "
    "your quality team. We have withheld 500.00 pending a credit note."
)

# <<<BLANK hint="Call client.complete() with SYSTEM and REMITTANCE at temperature 0.0; store in `answer`">
answer = client.complete(SYSTEM, REMITTANCE, temperature=0.0)
# >>>

print("MODEL RESPONSE")
print("-" * 72)
print(answer)
print("-" * 72)

# %% [markdown]
# ### Step 5 — Free text is not an integration contract
#
# Step 4 returned prose. Prose cannot be posted to an ERP.
#
# `complete_json()` hardens the instruction, then parses defensively — models wrap
# JSON in markdown fences even when told not to, and doing that unwrap in one
# place beats debugging it in five labs.
#
# > **This is still not enough.** Parsing is not validating. `json.loads` will
# > happily accept `{"reason_code": "D99", "confidence": "very high"}`. On Day 2
# > you replace this with a Pydantic contract that rejects both. Say that out
# > loud now so nobody ships `parse_json_loose` to production.

# %%
structured = client.complete_json(
    SYSTEM + "\nReturn keys: reason_code, category, confidence (0-1 float), evidence (verbatim quote).",
    REMITTANCE,
    temperature=0.0,
)

print("STRUCTURED RESPONSE")
for key, value in structured.items():
    print(f"  {key:<14} {value}")

code = structured.get("reason_code")
print(f"\nAsserting reason_code is a legal value... ", end="")
assert code in {"D01", "D02", "D03", "D04", "D05", "UNKNOWN"}, f"illegal code {code!r}"
print("pass")
if code != "D03":
    print(f"NOTE: expected D03 (Damage). Got {code}. On the offline stub this is")
    print("      keyword-driven; on Path A investigate the prompt before the model.")

log_event(log, "classification_complete", backend=client.backend_name,
          reason_code=code, confidence=structured.get("confidence"))

# %% [markdown]
# ### Step 6 — Latency is a design input, not a footnote
#
# The Capstone graph makes several model calls per payment. If each costs 900 ms,
# a 5,000-payment nightly batch spends over an hour inside the model alone.
#
# Measure it now, because the number determines architecture: which nodes must be
# deterministic Python (fast, free, auditable) and which genuinely need a model.

# %%
samples = []
for i in range(3):
    t0 = time.perf_counter()
    client.complete("Reply with exactly one word: ACK", "ping", max_tokens=5)
    samples.append((time.perf_counter() - t0) * 1000)
    print(f"  call {i + 1}: {samples[-1]:8.1f} ms")

mean_ms = sum(samples) / len(samples)
print(f"\nmean {mean_ms:.1f} ms  |  min {min(samples):.1f} ms  |  max {max(samples):.1f} ms")
print(f"Projected model time for a 5,000-payment batch at 2 calls each: "
      f"{mean_ms * 2 * 5000 / 1000 / 60:.1f} minutes (serial).")
print("\nDesign consequence: the priority-matching rules in the Capstone are")
print("deterministic Python, NOT model calls. The model is reserved for the one")
print("job it is uniquely good at - reading unstructured remittance prose.")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] `settings.describe()` prints a masked key, never the raw value.
# - [ ] `StaticTokenCredential.get_token()` returns an object with `.token` and `.expires_on`.
# - [ ] `get_chat_client()` reports a backend and you can name which of the four rules selected it.
# - [ ] The structured call returns a legal reason code and the assertion passes.
# - [ ] You have a measured mean latency figure written down.
#
# ### Discussion — 5 minutes
#
# 1. Your organisation's production deployment: key vault, managed identity, or
#    workload identity federation? Which class in `shared/foundry_client.py`
#    changes, and how many labs would you have to touch? (Answer: one, and zero.)
# 2. `temperature=0.0` reduces variance. It does not eliminate it. What is your
#    control when the same remittance classifies as D01 on Monday and D03 on
#    Tuesday? (Day 3 answers this with evidence-grounded output and audit replay.)
# 3. The latency number you just measured — does it fit your batch window?
#
# ### Business impact
#
# The credential seam is what makes the difference between a demo and a deployable
# component. Most agentic pilots that stall at the enterprise gate stall on
# identity, network egress and secret handling — not on model quality. Building
# the seam on the first afternoon means the security review is a conversation
# about an existing design, rather than a request to rewrite one.
