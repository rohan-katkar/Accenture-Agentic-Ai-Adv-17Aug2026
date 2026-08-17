"""Deterministic offline chat client.

Lets every lab execute end-to-end with NO Azure credentials, so students can
validate graph wiring, HITL, checkpointing, MCP, and telemetry locally before
switching to live Foundry models by filling in .env.

Design rules (learned the hard way in Batch 1):
  * QUOTE source data verbatim in replies — never paraphrase — so acceptance
    tests can assert on exact substrings.
  * Deterministic: same input -> same output. No randomness.
  * Report plausible token usage so the Day 2 cost lab produces numbers.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from agent_framework import BaseChatClient, ChatResponse, Message, UsageDetails


def _estimate_tokens(text: str) -> int:
    # Heuristic (~4 chars/token). Labeled APPROXIMATE everywhere it surfaces.
    return max(1, len(text) // 4)


class OfflineChatClient(BaseChatClient):
    """Rule-based responder for the Northwind reconciliation domain."""

    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ):
        async def _go() -> ChatResponse:
            prompt = messages[-1].text if messages else ""
            system = messages[0].text if len(messages) > 1 else ""
            reply = self._respond(system, prompt)
            return ChatResponse(
                messages=Message("assistant", [reply]),
                model="offline-deterministic-v1",
                usage_details=UsageDetails(
                    input_token_count=_estimate_tokens(system + prompt),
                    output_token_count=_estimate_tokens(reply),
                ),
            )

        return _go()

    # ------------------------------------------------------------------ rules
    def _respond(self, system: str, prompt: str) -> str:
        p = prompt.lower()

        # Planner behaviour: decompose a settlement-processing request.
        if "plan" in p and ("settlement" in p or ".csv" in p):
            fname = _first_filename(prompt) or "settlement.csv"
            return json.dumps(
                {
                    "plan": [
                        {"step": 1, "task": "ingest", "input": fname},
                        {"step": 2, "task": "extract", "fields": ["order_id", "asin", "fba_fee", "promo_discount", "commission", "net_amount"]},
                        {"step": 3, "task": "match", "target": "d365_open_invoices"},
                        {"step": 4, "task": "post_or_escalate", "rule": "variance>500 or pct>5 -> HITL"},
                    ]
                }
            )

        # Grounded policy answers: QUOTE the retrieved passage verbatim.
        m = re.search(r"CONTEXT:\n(.*?)\nQUESTION:", prompt, re.S)
        if m:
            passage = m.group(1).strip().splitlines()[0].strip()
            return f'Per the vendor agreement: "{passage}" [source: grounded index]'

        # Variance classification for matcher agents.
        m = re.search(r"variance[=:\s]+\$?(-?\d+(?:\.\d+)?)", p)
        if m:
            v = abs(float(m.group(1)))
            verdict = "ESCALATE" if v > 500 else "AUTO_POST"
            return json.dumps({"verdict": verdict, "variance": v, "reason": f"abs variance {v:.2f} vs $500 threshold"})

        # PII masking demo.
        if "redact" in p or "mask" in p:
            masked = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL_REDACTED]", prompt)
            masked = re.sub(r"\+?\d[\d\s().-]{8,}\d", "[PHONE_REDACTED]", masked)
            return masked

        return f"[offline] acknowledged: {prompt[:120]}"


def _first_filename(text: str) -> str | None:
    m = re.search(r"[\w./-]+\.(?:csv|pdf|json)", text)
    return m.group(0) if m else None
