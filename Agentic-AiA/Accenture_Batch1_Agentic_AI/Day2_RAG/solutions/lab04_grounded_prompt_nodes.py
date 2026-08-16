# LAB TITLE: Day 2 Lab 4 - Building Grounded Prompt Nodes
# %% [markdown]
# ## Day 2 · Lab 4 — Building Grounded Prompt Nodes
#
# **Duration:** 55 minutes  **Difficulty:** Core → Advanced
#
# ### Why this lab exists
#
# Lab 3 retrieved text. This lab turns text into a **posting decision** — and that
# is the point at which a language model's output starts moving money.
#
# Two controls stand between the two, and most implementations have neither:
#
# | Control | What it prevents |
# |---|---|
# | **Evidence grounding** | the model answering from world knowledge instead of the document |
# | **Schema validation** | the model returning `D99`, `"very high"`, or a missing field |
#
# > **Closing a flagged gap.** Day 1 used `complete_json()`, which *parses*
# > defensively. Parsing is not validating: `json.loads` happily accepts
# > `{"reason_code": "D99", "confidence": "very high"}`. This lab replaces it with
# > a Pydantic contract that rejects both. Pydantic-validated structured output was
# > identified as missing from the course as originally scoped — this lab is the
# > remediation.
#
# ### Prerequisites
# Day 2 Labs 1–3 complete. `pydantic` installed.

# %%
"""Day 2 Lab 4 - Building Grounded Prompt Nodes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import settings                             # noqa: E402
from shared.foundry_client import get_chat_client, parse_json_loose  # noqa: E402
from shared.telemetry import configure, get_logger, log_event, trace_node  # noqa: E402

configure(level=settings.log_level, logfile="d2lab04_audit.log")
log = get_logger("day2.lab4")

client = get_chat_client()
print(f"chat backend: {client.backend_name}")
if client.backend_name == "offline-stub":
    print("NOTE: the offline stub is keyword-driven. The validation machinery below\n"
          "      is fully exercised, but model *behaviour* needs Path A.")

# %% [markdown]
# ### Step 1 — The data contract
#
# Everything the downstream graph relies on is declared here, and anything the
# model returns that violates it is rejected before it can reach a posting node.
#
# Read the validators as business rules, because that is what they are:
#
# - a reason code outside D01–D05 or `UNKNOWN` is not a value, it is a defect
# - `confidence` must be a float in [0, 1] — `"very high"` is not a number
# - **`evidence` must be a verbatim substring of the retrieved text.** This is the
#   grounding control expressed as code. A model that paraphrases, summarises or
#   invents its citation fails validation, and there is no polite way for it to
#   fabricate a quote that happens to appear in the source document.

# %%
LEGAL_CODES = ("D01", "D02", "D03", "D04", "D05", "UNKNOWN")


class DeductionFinding(BaseModel):
    """The contract between the model and the reconciliation graph."""

    reason_code: Literal["D01", "D02", "D03", "D04", "D05", "UNKNOWN"]
    category: str = Field(min_length=2, max_length=60)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(default="", max_length=400)
    deducted_amount_usd: float | None = None

    @field_validator("category")
    @classmethod
    def category_not_placeholder(cls, v: str) -> str:
        if v.strip().lower() in {"n/a", "none", "unknown category", "-"}:
            raise ValueError("category must be a real classification, not a placeholder")
        return v.strip()

    @field_validator("deducted_amount_usd")
    @classmethod
    def amount_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("deducted_amount_usd must be expressed as a positive magnitude")
        return v

    def check_grounded(self, source_text: str) -> None:
        """Reject a citation that does not literally appear in the source.

        Called separately from field validation because it needs the retrieved
        document, which Pydantic does not have access to during model_validate.
        """
        # <<<BLANK hint="Exempt UNKNOWN (it makes no claim). Require non-empty evidence for any coded finding. Then normalise whitespace on BOTH the evidence and the source, lower-case both, and raise ValueError unless the evidence is a substring of the source">
        if self.reason_code == "UNKNOWN":
            return                                   # no claim, nothing to ground
        if not self.evidence.strip():
            raise ValueError("a coded finding must cite evidence")
        needle = " ".join(self.evidence.split()).lower()
        haystack = " ".join(source_text.split()).lower()
        if needle not in haystack:
            raise ValueError(
                "evidence is not a verbatim quote from the retrieved document — "
                f"model returned: {self.evidence[:90]!r}")
        # >>>


print("DeductionFinding contract:")
for name, field in DeductionFinding.model_fields.items():
    print(f"  {name:<22} {field.annotation}")

# %% [markdown]
# ### Step 2 — Prove the contract rejects what it should
#
# Before trusting it with model output, feed it the four failure modes you will
# actually see in production.

# %%
BAD_PAYLOADS = [
    ({"reason_code": "D99", "category": "Invented", "confidence": 0.9, "evidence": "x"},
     "code outside the legal set"),
    ({"reason_code": "D03", "category": "Damage", "confidence": "very high", "evidence": "x"},
     "confidence is not a number"),
    ({"reason_code": "D03", "category": "Damage", "confidence": 1.8, "evidence": "x"},
     "confidence out of range"),
    ({"reason_code": "D03", "category": "n/a", "confidence": 0.7, "evidence": "x"},
     "placeholder category"),
    ({"category": "Damage", "confidence": 0.7, "evidence": "x"},
     "required field missing"),
]

for payload, why in BAD_PAYLOADS:
    try:
        DeductionFinding.model_validate(payload)
        print(f"  ACCEPTED (!!)  {why}   <- the contract has a hole")
    except ValidationError as exc:
        first = exc.errors()[0]
        print(f"  rejected       {why:<32} :: {first['msg'][:52]}")

print("\nEvery one of these is a real thing a model returns. Not hypothetical.")

# %% [markdown]
# ### Step 3 — The grounded prompt
#
# Four instructions carry the weight. Each one exists because of a specific
# failure observed in practice:
#
# 1. **Answer only from the document.** Blocks world knowledge leaking in.
# 2. **Quote verbatim.** Makes the citation checkable — see `check_grounded`.
# 3. **`UNKNOWN` is a valid answer.** Removes the pressure to produce *something*.
# 4. **Never invent a code.** Closes the enumeration.
#
# > Note instruction 3 particularly. A model asked "which of these five codes
# > applies?" will pick one, because the question presupposes that one does. Making
# > `UNKNOWN` explicitly legitimate is what lets BNK-1009 come back honest.

# %%
GROUNDED_SYSTEM = """You are an accounts receivable deduction classifier.

You will be given REMITTANCE EVIDENCE retrieved from a customer's payment advice.
Classify the customer's stated reason for withholding payment.

RULES — all four are mandatory:
1. Use ONLY the REMITTANCE EVIDENCE provided. Do not use outside knowledge and do
   not infer a reason the document does not state.
2. The "evidence" field must be a VERBATIM substring copied from the evidence
   text. Do not paraphrase, summarise or reformat it.
3. If the evidence does not state a reason, return reason_code "UNKNOWN" with
   confidence 0.0 and an empty evidence string. UNKNOWN is a correct, valuable
   answer. It is not a failure.
4. Never return a code outside this list:
   D01 Pricing Issue    - contracted price differs from the billed price
   D02 Freight Claim    - unauthorised shipping or handling charge
   D03 Damage Claim     - goods received broken, corrupted or unusable
   D04 Tax Difference   - exemption claimed or sales tax variance
   D05 Discount Taken   - early-payment discount taken outside terms

Return a single JSON object with keys: reason_code, category, confidence,
evidence, deducted_amount_usd."""

# %% [markdown]
# ### Step 4 — The extraction function
#
# Model call, parse, validate, ground-check. Any failure returns a safe `UNKNOWN`
# rather than raising — because a graph node that raises on a malformed model
# response takes down the whole nightly batch for one bad payment.
#
# **One retry, then stop.** Retrying forever on a model that keeps returning the
# same malformed shape burns budget and hides the problem.

# %%
def extract_deduction(evidence_text: str, *, run_id: str = "-",
                      txn_id: str = "-") -> tuple[DeductionFinding, list[str]]:
    """Return a validated finding plus the list of validation problems seen."""
    problems: list[str] = []
    user_prompt = f"REMITTANCE EVIDENCE:\n\"\"\"\n{evidence_text}\n\"\"\""

    for attempt in (1, 2):
        try:
            raw = client.complete(GROUNDED_SYSTEM, user_prompt, temperature=0.0)
            payload = parse_json_loose(raw)

            # <<<BLANK hint="Validate `payload` into a DeductionFinding, then call finding.check_grounded(evidence_text), and return (finding, problems)">
            finding = DeductionFinding.model_validate(payload)
            finding.check_grounded(evidence_text)
            log_event(log, "extraction_ok", run_id=run_id, txn_id=txn_id,
                      attempt=attempt, reason_code=finding.reason_code)
            return finding, problems
            # >>>

        except ValidationError as exc:
            detail = "; ".join(f"{e['loc']}: {e['msg']}" for e in exc.errors()[:3])
            problems.append(f"attempt {attempt} schema: {detail}")
        except ValueError as exc:            # includes the grounding failure
            problems.append(f"attempt {attempt} grounding: {exc}")

        log_event(log, "extraction_rejected", level=30, run_id=run_id,
                  txn_id=txn_id, attempt=attempt, problem=problems[-1])

    # Two failures. Fail SAFE, not silent: UNKNOWN routes the item to a human.
    return DeductionFinding(reason_code="UNKNOWN", category="Unclassified",
                            confidence=0.0, evidence=""), problems

# %% [markdown]
# ### Step 5 — Run it on the real cases
#
# Three transactions with genuinely different evidence quality. The interesting
# result is the third.

# %%
CASES = {
    "BNK-1002": ("Note from AP: Five units arrived crushed and unusable at our Newark "
                 "dock on 27 February. Photographs were sent to your quality team. We "
                 "have withheld USD 500.00 pending credit note. Please do not treat "
                 "this as a pricing dispute."),
    "BNK-1009": ("Comment: Amount adjusted per internal review. Balance under "
                 "evaluation by our procurement group. Further detail to follow "
                 "separately."),
    "BNK-1010": ("Comment: Payment released against INV-1201. Our system shows an "
                 "additional 1,000.00 applied in error from a duplicate approval run. "
                 "Please advise on disposition of the excess."),
}

for txn_id, evidence in CASES.items():
    finding, problems = extract_deduction(evidence, run_id="d2l4", txn_id=txn_id)
    print(f"\n{txn_id}")
    print(f"  reason_code   : {finding.reason_code}")
    print(f"  category      : {finding.category}")
    print(f"  confidence    : {finding.confidence}")
    print(f"  evidence      : {finding.evidence[:70]!r}")
    print(f"  amount        : {finding.deducted_amount_usd}")
    if problems:
        print("  validation problems encountered:")
        for p in problems:
            print(f"    - {p}")

# %% [markdown]
# ### Step 6 — The BNK-1009 test, stated plainly
#
# BNK-1009's remittance says *"Amount adjusted per internal review."* That is not
# a deduction reason. It is a customer declining to give one.
#
# The correct output is `UNKNOWN`, which routes the transaction to `QUERY` and a
# human. Anything else is a fabricated reason code with an SLA attached, sitting
# in a team's queue, based on nothing.
#
# > **Say this to the room:** a system that returns `UNKNOWN` on BNK-1009 has a
# > lower automation rate and a *higher* correctness rate than one that guesses.
# > Those two numbers move in opposite directions, and only one of them shows up in
# > a steering-committee slide. Report both.

# %%
finding, _ = extract_deduction(CASES["BNK-1009"], run_id="d2l4", txn_id="BNK-1009")
if finding.reason_code == "UNKNOWN":
    print("PASS — BNK-1009 returned UNKNOWN. The system declined to guess.")
else:
    print(f"REVIEW — BNK-1009 returned {finding.reason_code}.")
    print("  On the offline stub this is keyword-driven and may fire on stray words.")
    print("  On Path A, investigate the prompt before blaming the model: the most")
    print("  common cause is instruction 3 being weakened or dropped.")

# %% [markdown]
# ### Step 7 — Watch the grounding check catch a fabricated citation
#
# We bypass the model and hand the validator a finding whose quote never appears
# in the source. This is what a hallucinated citation looks like from the outside,
# and it is why the check exists.

# %%
fabricated = DeductionFinding(
    reason_code="D01", category="Pricing Issue", confidence=0.94,
    evidence="the agreed contract price was 95.00 per unit, not 110.00")

try:
    fabricated.check_grounded(CASES["BNK-1002"])
    print("Grounding check PASSED — which would be a bug.")
except ValueError as exc:
    print(f"Grounding check rejected the finding:\n  {exc}")

print("""
Nothing in that quote appears in Acme's remittance. It is fluent, specific,
plausible, and entirely invented. No amount of prompt engineering reliably
prevents this. A verbatim-substring check does — and it costs one line.""")

# %% [markdown]
# ### Step 8 — The node
#
# Wrap it in the standard node contract so Lab 5 can drop it into the graph.

# %%
def node_classify_deduction(state: dict) -> dict:
    """Classify the deduction reason from retrieved remittance evidence."""
    txn_id = state.get("txn_id", "-")
    run_id = state.get("run_id", "-")

    with trace_node(log, "classify_deduction", run_id, txn_id=txn_id) as out:
        if not state.get("remittance_found"):
            out["outcome"] = "no_evidence"
            return {"reason_code": "UNKNOWN", "reason_confidence": 0.0,
                    "trace": ["classify_deduction: no remittance evidence — cannot classify"]}

        evidence_text = state.get("remittance_text", "")
        finding, problems = extract_deduction(evidence_text, run_id=run_id, txn_id=txn_id)
        out["reason_code"] = finding.reason_code
        out["confidence"] = finding.confidence

        trace = [f"classify_deduction: {finding.reason_code} ({finding.category}) "
                 f"at confidence {finding.confidence}"]
        if problems:
            trace.append(f"classify_deduction: {len(problems)} validation rejection(s) "
                         f"before settling — see audit log")
        return {
            "reason_code": finding.reason_code,
            "reason_confidence": finding.confidence,
            "reason_evidence": finding.evidence,
            "reason_validation_problems": problems,
            "trace": trace,
        }


demo = node_classify_deduction({
    "run_id": "d2l4", "txn_id": "BNK-1002",
    "remittance_found": True, "remittance_text": CASES["BNK-1002"],
})
print(json.dumps({k: v for k, v in demo.items() if k != "trace"}, indent=2, default=str))
for line in demo["trace"]:
    print(f"  trace: {line}")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] All five bad payloads are rejected by the Pydantic contract.
# - [ ] `extract_deduction` returns a validated `DeductionFinding` for BNK-1002.
# - [ ] BNK-1009 returns `UNKNOWN` (or you can explain why the offline stub did not).
# - [ ] The fabricated citation is caught by `check_grounded`.
# - [ ] You can articulate the difference between parsing JSON and validating it.
#
# ### Discussion — 10 minutes
#
# 1. `check_grounded` requires a verbatim substring. What legitimate model output
#    would it wrongly reject? (Re-typed whitespace, corrected OCR, a quote spanning
#    a chunk boundary.) How would you loosen it *without* letting fabrication through?
# 2. We fail safe to `UNKNOWN` after two attempts. What is the operational cost of
#    that choice, and who absorbs it?
# 3. `confidence` comes from the model. Is that a probability? (No. It is a number
#    the model produced because we asked for one. Treat it as a routing signal, not
#    a calibrated estimate — and never label it as a percentage to a business user.)
#
# ### Business impact
#
# This is the node that determines whether the automation is trustworthy. Every
# other component can be correct and one fabricated reason code still produces a
# customer credit nobody agreed to. The two controls here — grounding and schema
# validation — are cheap to build and are the difference between a pilot that
# passes controls testing and one that does not.
