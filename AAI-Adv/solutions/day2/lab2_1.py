# %% [markdown]
# # Lab 2.1 — Asynchronous State Graph & Execution Loops
# Full settlement orchestration: **Ingestion -> Extraction -> Matching**, with
# conditional edge routing (matched vs unmatched vs retry) and a **loop-exit
# condition** that stops infinite retries on unallocated promotional discounts.
#
# NOTE: no `from __future__ import annotations` here — PEP 563 string
# annotations break agent-framework handler signature validation (C4).

# %%
import asyncio, csv, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import Executor, WorkflowBuilder, WorkflowContext, handler
from common.d365_store import D365Store

MAX_PROMO_RETRIES = 3  # loop-exit condition

# %% [markdown]
# ## Step 1 — Node definitions

# %%
def parse_money(raw: str) -> float:
    raw = raw.strip()
    return -float(raw[1:-1]) if raw.startswith("(") and raw.endswith(")") else float(raw)


class IngestionNode(Executor):
    @handler
    async def run(self, filename: str, ctx: WorkflowContext[dict]) -> None:
        path = ROOT / "data" / "settlements" / filename
        rows = list(csv.DictReader(path.open()))
        for row in rows[:10]:                       # brief: 10 sample orders
            await ctx.send_message({"raw": row, "retries": 0})


class ExtractionNode(Executor):
    @handler
    async def run(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        r = msg["raw"]
        rec = {
            "order_id": r["order_id"],
            "net_amount": parse_money(r["net_amount"]),
            "promo_discount": parse_money(r["promo_discount"]),
            "gross": parse_money(r["gross_amount"]),
            "retries": msg["retries"],
        }
        # "Unallocated" promo: discount > 5% of gross without an agreement id
        rec["promo_unallocated"] = rec["promo_discount"] > 0.05 * rec["gross"]
        await ctx.send_message(rec)


class PromoResolver(Executor):
    """Retry loop target. Each pass simulates a lookup for a promo agreement.
    Loop-exit: after MAX_PROMO_RETRIES the record is force-routed to exceptions
    instead of circulating forever (the classic Day-2 infinite-loop bug)."""
    @handler
    async def run(self, rec: dict, ctx: WorkflowContext[dict]) -> None:
        rec = dict(rec)
        rec["retries"] += 1
        if rec["retries"] >= MAX_PROMO_RETRIES:
            rec["promo_unallocated"] = False        # give up: mark for manual memo
            rec["promo_note"] = f"unresolved after {rec['retries']} retries -> manual memo"
        await ctx.send_message(rec)


class MatchingNode(Executor):
    def __init__(self, id: str, store: D365Store):
        super().__init__(id=id)
        self.store = store

    @handler
    async def run(self, rec: dict, ctx: WorkflowContext[None, dict]) -> None:
        inv = self.store.find_invoice(rec["order_id"])
        if inv is None:
            await ctx.yield_output({**rec, "status": "unmatched_no_invoice"})
            return
        variance = round(inv["amount"] - rec["net_amount"], 2)
        pct = round(abs(variance) / inv["amount"] * 100, 2) if inv["amount"] else 0.0
        status = "matched" if abs(variance) < 0.01 else "variance"
        await ctx.yield_output({**rec, "status": status,
                                "variance_usd": variance, "variance_pct": pct})

# %% [markdown]
# ## Step 2 — Conditional edge routing
# Extraction fans out on a predicate: unallocated promos loop through the
# resolver; clean records go straight to matching. The resolver feeds back into
# extraction? No — that re-parses. It feeds FORWARD into matching once resolved,
# and back to ITSELF while retrying, which is where the exit condition bites.

# %%
async def main():
    store = D365Store()
    ingest = IngestionNode(id="ingest")
    extract = ExtractionNode(id="extract")
    resolver = PromoResolver(id="promo_resolver")
    match = MatchingNode(id="match", store=store)

    wf = (
        WorkflowBuilder(start_executor=ingest, name="lab2_1_orchestration",
                        max_iterations=50)
        .add_edge(ingest, extract)
        .add_edge(extract, resolver,
                  condition=lambda rec: rec.get("promo_unallocated", False))
        .add_edge(extract, match,
                  condition=lambda rec: not rec.get("promo_unallocated", False))
        .add_edge(resolver, resolver,        # self-loop while unresolved
                  condition=lambda rec: rec.get("promo_unallocated", False))
        .add_edge(resolver, match,
                  condition=lambda rec: not rec.get("promo_unallocated", False))
        .build()
    )

    result = await wf.run("settlement_2026_08_batch1.csv")
    outs = result.get_outputs()
    print(f"Processed {len(outs)} orders end-to-end")
    by_status = {}
    for o in outs:
        by_status.setdefault(o["status"], []).append(o["order_id"])
    for k, v in sorted(by_status.items()):
        print(f"  {k:22s} {v}")

    assert len(outs) == 10, "10 sample orders must complete"
    retried = [o for o in outs if o.get("promo_note")]
    for o in retried:
        assert o["retries"] == MAX_PROMO_RETRIES, "loop must exit at the cap"
    assert len(retried) >= 1, "planted defect D6 (NW-1012) must exercise the retry loop"
    print(f"Loop-exit verified on {len(retried)} unallocated-promo record(s): "
          f"{[o['order_id'] for o in retried]}")
    print("LAB 2.1 PASS")

if __name__ == "__main__":
    asyncio.run(main())
