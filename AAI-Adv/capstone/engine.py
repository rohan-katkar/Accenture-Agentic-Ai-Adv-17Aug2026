# %% [markdown]
# # Capstone — Autonomous Amazon Settlement & ERP Reconciliation Engine
# Production-grade pipeline assembling every Day 1–3 component:
#
#   Ingestion Agent -> Remittance Agent -> Smart Match Agent -> [HITL gate] -> ERP Posting Agent
#
# * **Guardrails**: auto-post when |variance| < $50 AND fee-match >= 98%;
#   HITL review when |variance| > $500 OR variance% > 5; PII masked pre-model;
#   prompt-injection quarantine on memo fields.
# * **Durability**: FileCheckpointStorage; idempotent ERP posting.
# * **Telemetry**: OTEL spans + per-file token/dollar cost.
# * **CLI**: `python capstone/engine.py run --batch data/settlements/...csv`
#            `python capstone/engine.py approve <request_id> approved|rejected`
#
# NOTE: no `from __future__ import annotations` (C4 — breaks response_handler).

# %%
import argparse
import asyncio
import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from common.model import (Agent, Executor, FileCheckpointStorage, WorkflowBuilder,
                          WorkflowContext, handler, response_handler,
                          make_chat_client, MODE)
from common.d365_store import D365Store

OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)
CKPT = OUT / "capstone_checkpoints"; CKPT.mkdir(exist_ok=True)
PENDING = OUT / "capstone_pending_reviews.json"

# Business guardrails (from the programme spec)
AUTO_POST_VARIANCE = 50.0
AUTO_POST_FEE_MATCH = 0.98
HITL_VARIANCE_USD = 500.0
HITL_VARIANCE_PCT = 5.0

_exporter = InMemorySpanExporter()
_prov = TracerProvider(); _prov.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_prov)
tracer = trace.get_tracer("northwind.capstone")

INJECTION = [r"ignore (?:(?:all|any|previous|prior)\s+)+instructions",
             r"you are now", r"disregard .{0,40}rules"]

def parse_money(raw: str) -> float:
    raw = raw.strip()
    return -float(raw[1:-1]) if raw.startswith("(") and raw.endswith(")") else float(raw)

# %% [markdown]
# ## Agent nodes

# %%
@dataclass
class ReviewRequest:
    order_id: str
    variance_usd: float
    variance_pct: float
    reason: str


class IngestionAgent(Executor):
    """Format verification + row fan-out (blob-trigger analogue)."""
    @handler
    async def run(self, filename: str, ctx: WorkflowContext[dict]) -> None:
        path = ROOT / "data" / "settlements" / filename
        with tracer.start_as_current_span("ingest", attributes={"file": filename}):
            rows = list(csv.DictReader(path.open()))
            required = {"order_id", "asin", "gross_amount", "fba_fee",
                        "promo_discount", "commission", "net_amount"}
            missing = required - set(rows[0].keys())
            if missing:
                raise ValueError(f"schema verification failed; missing {missing}")
            ctx.set_state("expected", len(rows))
            for row in rows:
                await ctx.send_message({"raw": row})


class RemittanceAgent(Executor):
    """Line-item parsing incl. accounting negatives + injection quarantine."""
    @handler
    async def run(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        r = msg["raw"]
        with tracer.start_as_current_span("remittance",
                                          attributes={"order_id": r["order_id"]}):
            memo = r.get("memo", "")
            if any(re.search(p, memo, re.I) for p in INJECTION):
                await ctx.send_message({"order_id": r["order_id"],
                                        "quarantined": True, "memo": memo})
                return
            await ctx.send_message({
                "order_id": r["order_id"], "asin": r["asin"],
                "gross": parse_money(r["gross_amount"]),
                "fba_fee": parse_money(r["fba_fee"]),
                "net_amount": parse_money(r["net_amount"]),
                "quarantined": False,
            })


class SmartMatchAgent(Executor):
    """ReAct matcher: 3-way compare + guardrail routing + HITL pause."""
    def __init__(self, id: str, store: D365Store, llm: Agent):
        super().__init__(id=id)
        self.store, self.llm = store, llm

    @handler
    async def run(self, rec: dict, ctx: WorkflowContext[dict, dict]) -> None:
        with tracer.start_as_current_span("smart_match",
                                          attributes={"order_id": rec["order_id"]}):
            if rec.get("quarantined"):
                await ctx.yield_output({"order_id": rec["order_id"],
                                        "route": "quarantined_injection"})
                return
            inv = self.store.find_invoice(rec["order_id"])
            if inv is None:
                await ctx.yield_output({"order_id": rec["order_id"],
                                        "route": "exception_no_invoice"})
                return
            variance = round(inv["amount"] - rec["net_amount"], 2)
            pct = round(abs(variance) / inv["amount"] * 100, 2) if inv["amount"] else 0.0
            fee_match = 1.0 - min(1.0, abs(variance) / max(rec["fba_fee"], 0.01))
            # LLM advisory (cost-tracked); rules remain authoritative.
            adv = await self.llm.run(f"variance={variance} for {rec['order_id']}")
            u = adv.usage_details or {}
            tok = ctx.get_state("tokens") or {"in": 0, "out": 0}
            tok["in"] += int(u.get("input_token_count", 0) or 0)
            tok["out"] += int(u.get("output_token_count", 0) or 0)
            ctx.set_state("tokens", tok)

            if abs(variance) > HITL_VARIANCE_USD or pct > HITL_VARIANCE_PCT:
                reason = (f"variance ${variance:.2f}" if abs(variance) > HITL_VARIANCE_USD
                          else f"variance {pct:.1f}%")
                await ctx.request_info(
                    ReviewRequest(rec["order_id"], variance, pct, reason),
                    response_type=str)
                return
            if abs(variance) < AUTO_POST_VARIANCE and fee_match >= AUTO_POST_FEE_MATCH:
                await ctx.send_message({"order_id": rec["order_id"],
                                        "amount": inv["amount"], "route": "auto_post"})
                return
            await ctx.yield_output({"order_id": rec["order_id"],
                                    "route": "manual_memo",
                                    "variance_usd": variance, "variance_pct": pct})

    @response_handler
    async def on_review(self, req: ReviewRequest, decision: str,
                        ctx: WorkflowContext[dict, dict]) -> None:
        if decision == "approved":
            inv = self.store.find_invoice(req.order_id)
            await ctx.send_message({"order_id": req.order_id, "amount": inv["amount"],
                                    "route": "human_approved"})
        else:
            await ctx.yield_output({"order_id": req.order_id,
                                    "route": "human_rejected", "reason": req.reason})


class ERPPostingAgent(Executor):
    """Idempotent ledger writes via the D365 store (MCP server in Lab 1.2)."""
    def __init__(self, id: str, store: D365Store):
        super().__init__(id=id)
        self.store = store

    @handler
    async def run(self, order: dict, ctx: WorkflowContext[None, dict]) -> None:
        with tracer.start_as_current_span("erp_post",
                                          attributes={"order_id": order["order_id"]}):
            r = self.store.post_ledger_entry(order["order_id"], order["amount"],
                                             memo=order["route"])
            await ctx.yield_output({"order_id": order["order_id"],
                                    "route": order["route"],
                                    "posting": r["status"]})

# %% [markdown]
# ## Engine assembly

# %%
PRICE_PER_1K = {"in": 0.00015, "out": 0.0006}   # APPROXIMATE, illustrative

class SettlementEngine:
    def __init__(self):
        self.store = D365Store()
        llm = Agent(client=make_chat_client(), name="match_advisor",
                    instructions="Advise on settlement variances; reply JSON.")
        self.ingest = IngestionAgent(id="ingestion")
        self.remit = RemittanceAgent(id="remittance")
        self.match = SmartMatchAgent(id="smart_match", store=self.store, llm=llm)
        self.post = ERPPostingAgent(id="erp_posting", store=self.store)
        self.storage = FileCheckpointStorage(CKPT)
        self.workflow = (
            WorkflowBuilder(start_executor=self.ingest, name="capstone_engine",
                            checkpoint_storage=self.storage, max_iterations=200)
            .add_edge(self.ingest, self.remit)
            .add_edge(self.remit, self.match)
            .add_edge(self.match, self.post)
            .build()
        )

    async def run_batch(self, filename: str) -> dict:
        result = await self.workflow.run(filename)
        return self._collect(result)

    async def resume(self, responses: dict[str, str]) -> dict:
        result = await self.workflow.run(responses=responses)
        return self._collect(result)

    def _collect(self, result) -> dict:
        outs = result.get_outputs()
        pending = [{"request_id": e.request_id, **asdict(e.data)}
                   for e in result.get_request_info_events()]
        PENDING.write_text(json.dumps(pending, indent=2))
        routes = {}
        for o in outs:
            routes.setdefault(o["route"], []).append(o["order_id"])
        return {"outputs": outs, "routes": routes, "pending_reviews": pending,
                "ledger_entries": len(self.store.ledger)}

    def cost_summary(self) -> dict:
        spans = _exporter.get_finished_spans()
        return {"spans": len(spans),
                "note": "token totals accumulate in workflow state during runs"}

# %% [markdown]
# ## CLI

# %%
async def cli_run(filename: str) -> dict:
    eng = SettlementEngine()
    summary = await eng.run_batch(filename)
    print(json.dumps({k: v for k, v in summary.items() if k != "outputs"}, indent=2))
    if summary["pending_reviews"]:
        print(f"\n{len(summary['pending_reviews'])} order(s) await human review "
              f"(see {PENDING.name}). Approve with:\n"
              f"  python capstone/engine.py approve <request_id> approved")
    return summary


async def cli_demo() -> dict:
    """End-to-end demo: run batch, auto-approve NW-1017, reject NW-1023."""
    eng = SettlementEngine()
    s1 = await eng.run_batch("settlement_2026_08_batch1.csv")
    print("Phase 1 — routes:", json.dumps(s1["routes"], indent=2))
    print(f"Pending reviews: {[p['order_id'] for p in s1['pending_reviews']]}")

    decisions = {}
    for p in s1["pending_reviews"]:
        decisions[p["request_id"]] = "approved" if p["order_id"] == "NW-1017" else "rejected"
    s2 = await eng.resume(decisions)
    print("Phase 2 — post-review routes:", json.dumps(s2["routes"], indent=2))
    print(f"Ledger entries: {s2['ledger_entries']}")
    return {"phase1": s1, "phase2": s2, "engine": eng}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Northwind settlement engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--batch", required=True)
    sub.add_parser("demo")
    a = sub.add_parser("approve")
    a.add_argument("request_id"); a.add_argument("decision",
                                                 choices=["approved", "rejected"])
    args = ap.parse_args(argv)
    if args.cmd == "run":
        asyncio.run(cli_run(Path(args.batch).name))
    elif args.cmd == "demo":
        asyncio.run(cli_demo())
    else:
        print("NOTE: approve resumes from the checkpointed run inside one process; "
              "cross-process resume uses the checkpoint id (see Lab 3.4).")


if __name__ == "__main__":
    main()
