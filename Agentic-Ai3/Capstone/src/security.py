"""
Capstone/src/security.py
========================
Guardrails and the permissioned tool boundary, packaged from Day 3 Labs 1-2 and
Day 2 Lab 2.

THE ARCHITECTURAL CONTROL, RESTATED
-----------------------------------
The strongest defence here is not a filter. It is that the model cannot
authorise a write. `ToolRegistry.invoke` refuses any `write` tool unless the
caller passes `allow_write=True`, and only the graph does that, and only from a
state that justifies it.

A successful prompt injection therefore corrupts a *recommendation*. It does not
move money, because the model was never holding that authority to give away.
"""

from __future__ import annotations

import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from shared.telemetry import get_logger, log_event

log = get_logger(__name__)

Severity = Literal["block", "flag"]


@dataclass(frozen=True)
class SecurityFinding:
    control: str
    severity: Severity
    detail: str        # WHAT matched - never the payload itself
    position: int
    node: str = "input_guardrail"

    def as_dict(self) -> dict:
        return {"control": self.control, "severity": self.severity,
                "detail": self.detail, "position": self.position, "node": self.node}


# ===========================================================================
# 1. Input gate
# ===========================================================================
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)


def normalise(text: str) -> str:
    """NFKC-fold, strip zero-width characters, collapse whitespace, lower-case.

    Closes homoglyph, zero-width and whitespace evasions for free. Note the
    result is ONE line, so detection patterns must not anchor on ^.
    """
    folded = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)
    return " ".join(folded.split()).lower()


INPUT_RULES: list[tuple[str, re.Pattern, Severity, str]] = [
    ("instruction_override",
     re.compile(r"\b(ignore|disregard|forget|override)\b[^.]{0,30}\b"
                r"(previous|prior|above|earlier|all)\b[^.]{0,20}\b"
                r"(instruction|rule|prompt|direction|system)"),
     "block", "instruction-override phrasing"),
    ("role_injection",
     re.compile(r"(?:^|\s)(system|assistant|developer)\s*[:>]|"
                r"\[(system|assistant|inst)\]|<\|?(im_start|system)\|?>"),
     "block", "fake role or turn marker"),
    ("authority_claim",
     re.compile(r"\b(as an? (administrator|admin|authorised agent)|"
                r"you are (now|hereby) (authorised|permitted)|"
                r"per (company|internal) policy[, ]+(approve|close|waive))\b"),
     "block", "fabricated authority claim"),
    ("action_directive",
     re.compile(r"\b(approve|close|waive|write off|release|mark)\b[^.]{0,25}"
                r"\b(in full|immediately|without review|the full amount)\b"),
     "block", "directive to take a financial action"),
    ("prompt_structure_mimicry",
     re.compile(r"\b(your (instructions|system prompt|rules) (are|is))\b|"
                r"\bnew (instruction|rule)s? follow\b"),
     "block", "text redefining the prompt"),
    ("code_fence_or_encoding",
     re.compile(r"```|\bbase64\b|\beval\(|\bexec\(|%[0-9a-f]{2}%[0-9a-f]{2}"),
     "flag", "code fence or encoding marker"),
]


def scan_input(text: str, *, source: str = "-") -> list[SecurityFinding]:
    subject = normalise(text or "")
    findings: list[SecurityFinding] = []
    for control, pattern, severity, detail in INPUT_RULES:
        m = pattern.search(subject)
        if m:
            findings.append(SecurityFinding(control, severity, detail, m.start()))
    if findings:
        log_event(log, "input_guardrail_fired", source=source,
                  controls=[f.control for f in findings],
                  blocked=any(f.severity == "block" for f in findings))
    return findings


def is_blocking(findings: list[SecurityFinding] | list[dict]) -> bool:
    return any((f.severity if isinstance(f, SecurityFinding) else f.get("severity")) == "block"
               for f in findings)


# ===========================================================================
# 2. Output gate
# ===========================================================================
@dataclass(frozen=True)
class RedactionRule:
    name: str
    pattern: re.Pattern
    cls: str            # secret | financial | identity
    keep_tail: int      # 0 = replace entirely


OUTPUT_RULES = [
    RedactionRule("api_key_openai", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "secret", 0),
    RedactionRule("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b"), "secret", 0),
    RedactionRule("azure_key", re.compile(r"\b[a-f0-9]{32}\b"), "secret", 0),
    RedactionRule("connection_string",
                  re.compile(r"\b(AccountKey|Password|Pwd)=[^;\s]{8,}", re.I), "secret", 0),
    RedactionRule("payment_card", re.compile(r"\b(?:\d[ -]?){13,16}\d\b"), "financial", 4),
    RedactionRule("bank_account", re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}\b"), "financial", 4),
    RedactionRule("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,26}\b"), "financial", 4),
    RedactionRule("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "identity", 0),
    RedactionRule("us_tax_id", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "identity", 4),
]


def redact(text: str) -> tuple[str, list[dict]]:
    """Mask sensitive content. Returns (clean_text, inventory).

    Secrets are replaced entirely - there is no safe partial of an API key.
    Financial values keep the last four, because an analyst genuinely needs to
    reconcile "the account ending 4420". Masking is not deletion, and the
    difference is operational.
    """
    inventory: list[dict] = []
    clean = text or ""
    for rule in OUTPUT_RULES:
        matches = list(rule.pattern.finditer(clean))
        if not matches:
            continue
        for m in matches:
            found = m.group(0)
            replacement = (f"[REDACTED:{rule.name}]" if rule.keep_tail == 0
                           else "*" * max(0, len(found) - rule.keep_tail) + found[-rule.keep_tail:])
            clean = clean.replace(found, replacement)
        inventory.append({"rule": rule.name, "cls": rule.cls, "count": len(matches)})
    if inventory:
        log_event(log, "output_redacted", rules=[i["rule"] for i in inventory])
    return clean, inventory


# ===========================================================================
# 3. Error envelopes
# ===========================================================================
SAFE_MESSAGES = {
    "UPSTREAM_AUTH": "The document service could not be reached. Support has been notified.",
    "UPSTREAM_TIMEOUT": "The request took too long. Please retry.",
    "VALIDATION": "The response could not be validated and was discarded.",
    "INTERNAL": "An unexpected error occurred. Support has been notified.",
}


@dataclass
class ErrorEnvelope:
    code: str
    correlation_id: str
    message: str

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "correlation_id": self.correlation_id,
                          "message": self.message}}


def to_envelope(exc: Exception, code: str = "INTERNAL") -> ErrorEnvelope:
    """Log the detail internally (redacted); return a code and a correlation ID.

    A raw exception can carry your endpoint, deployment name and a partial token.
    We redact even on the internal path - log aggregators get breached too.
    """
    correlation_id = f"err-{uuid.uuid4().hex[:12]}"
    detail, _ = redact(f"{type(exc).__name__}: {exc}")
    log_event(log, "error_captured", level=40,
              correlation_id=correlation_id, code=code, detail=detail)
    return ErrorEnvelope(code, correlation_id, SAFE_MESSAGES.get(code, SAFE_MESSAGES["INTERNAL"]))


# ===========================================================================
# 4. Permissioned tool boundary
# ===========================================================================
Permission = Literal["read", "write"]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, str]
    permission: Permission
    fn: Callable[..., Any]

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": {"type": "object",
                           "properties": {k: {"type": "string", "description": v}
                                          for k, v in self.parameters.items()},
                           "required": list(self.parameters)}}}


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
        tool = self.tools.get(name)
        if tool is None:
            self._audit(name, arguments, ok=False, ms=0.0, run_id=run_id,
                        outcome="tool_not_found")
            return {"ok": False, "error": f"no such tool: {name}",
                    "available": sorted(self.tools)}

        if tool.permission == "write" and not allow_write:
            self._audit(name, arguments, ok=False, ms=0.0, run_id=run_id,
                        outcome="write_refused")
            return {"ok": False,
                    "error": f"'{name}' is a write tool and this call was not authorised"}

        started = time.perf_counter()
        try:
            payload, ok = tool.fn(**arguments), True
        except Exception as exc:  # noqa: BLE001
            payload, ok = f"{type(exc).__name__}: {exc}", False
        elapsed = (time.perf_counter() - started) * 1000

        self._audit(name, arguments, ok=ok, ms=elapsed, run_id=run_id,
                    outcome="executed" if ok else "raised")
        return {"ok": ok, "result" if ok else "error": payload}

    def _audit(self, name: str, arguments: dict, *, ok: bool, ms: float,
               run_id: str, outcome: str) -> dict:
        """Every ATTEMPT is recorded, including the ones that never ran.

        A refused write and a hallucinated tool name are the two most
        interesting lines in an audit ledger. Success-only logging hides them.
        """
        record = {"tool": name, "arguments": arguments, "ok": ok, "outcome": outcome,
                  "duration_ms": round(ms, 2), "run_id": run_id}
        self.audit.append(record)
        log_event(log, "tool_invoked", **record)
        return record

    def refusals(self) -> list[dict]:
        return [r for r in self.audit if r["outcome"] in {"write_refused", "tool_not_found"}]
