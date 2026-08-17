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
# ------------------------------------------------------------------
# TODO — implement Step 1: Node definitions
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Node definitions")

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
