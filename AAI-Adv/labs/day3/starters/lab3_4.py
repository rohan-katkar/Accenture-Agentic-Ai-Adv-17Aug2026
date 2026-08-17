# %% [markdown]
# # Lab 3.4 — Tabletop Disaster Simulation & Resiliency Testing
# Prime Day scenario: the Amazon Seller Central API starts failing mid-spike
# and a schema migration lands simultaneously. The system must:
#   1. Trip a **circuit breaker** after N consecutive failures and route new
#      files to a safe **isolation queue** (no data loss),
#   2. Never produce **duplicate ERP postings** — exercised with planted
#      defect D3 (NW-1031 appears twice in the settlement file),
#   3. **Rehydrate state from a checkpoint** after a simulated node crash and
#      finish the batch — using agent-framework FileCheckpointStorage.

# %%
import asyncio, csv, json, shutil, sys, time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import (Executor, WorkflowBuilder, WorkflowContext,
                          FileCheckpointStorage, handler)
from common.d365_store import D365Store

OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)
CKPT_DIR = OUT / "checkpoints"

# %% [markdown]
# ## Step 1 — Circuit breaker around the flaky upstream API

# %%
# ------------------------------------------------------------------
# TODO — implement Step 1: Circuit breaker around the flaky upstream API
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Circuit breaker around the flaky upstream API")

# %% [markdown]
# ## Step 2 — Ingest under outage: breaker + isolation queue (no loss)

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: Ingest under outage: breaker + isolation queue (no loss)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: Ingest under outage: breaker + isolation queue (no loss)")

# %% [markdown]
# ## Step 3 — Crash + rehydration with durable checkpoints
# The workflow checkpoints after ingestion. A crash is injected in the posting
# node on first run; the second run resumes FROM THE CHECKPOINT (not from the
# file) and completes. Idempotent posting absorbs the duplicate row (D3).

# %%
# ------------------------------------------------------------------
# TODO — implement Step 3: Crash + rehydration with durable checkpoints
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 3: Crash + rehydration with durable checkpoints")

# %%
async def main():
    # --- circuit breaker + isolation ------------------------------------
    files = [f"prime_day_{i:02d}.csv" for i in range(10)]
    r = ingest_under_outage(files)
    print("Outage drill:", json.dumps(r, indent=2))
    assert r["fast_rejects"] >= 1, "breaker must fast-fail while OPEN"
    assert len(r["processed"]) + len(r["isolated"]) == len(files), "zero loss"
    iso_lines = (OUT / "isolation_queue.jsonl").read_text().splitlines()
    assert len(iso_lines) == len(r["isolated"]), "every isolated file is queued"

    # --- crash + rehydrate ------------------------------------------------
    if CKPT_DIR.exists():
        shutil.rmtree(CKPT_DIR)
    CKPT_DIR.mkdir(parents=True)
    storage = FileCheckpointStorage(CKPT_DIR)
    store = D365Store()                       # survives across both runs
    ingest = BatchIngest(id="ingest")
    post = PostingNode(id="post", store=store)

    def build():
        return (WorkflowBuilder(start_executor=ingest, checkpoint_storage=storage,
                                name="lab3_4_resiliency")
                .add_edge(ingest, post).build())

    try:
        await build().run("settlement_2026_08_batch1.csv")
        raise AssertionError("first run must crash")
    except RuntimeError as e:
        print(f"CRASH as planned: {e}")

    ckpts = await storage.list_checkpoints(workflow_name="lab3_4_resiliency")
    assert ckpts, "a checkpoint must exist from before the crash"
    latest = max(ckpts, key=lambda c: c.timestamp)
    print(f"Rehydrating from checkpoint {latest.checkpoint_id[:8]}… "
          f"(iteration {latest.iteration_count})")

    CRASH["armed"] = False                    # migration fixed; resume
    result = await build().run(checkpoint_id=latest.checkpoint_id)
    out = result.get_outputs()[0]
    print("Recovery result:", out)
    assert out["batch_size"] == 26
    # C10: the invariant is END-STATE, not per-run counts. Run 1 posted rows
    # 0-11 before crashing; the resumed run replays ALL rows. Idempotency must
    # absorb 12 replayed posts + the planted D3 duplicate (13 total) and the
    # ledger must hold exactly 24 unique entries (25 orders - NW-1034 missing).
    assert out["duplicates_ignored"] == 13, f"12 replays + 1 D3 dup, got {out['duplicates_ignored']}"
    assert len(store.ledger) == 24, f"ledger must hold 24 unique entries, got {len(store.ledger)}"
    assert len({e["order_id"] for e in store.ledger}) == 24, "no duplicate ERP postings"
    print(f"Ledger integrity: {len(store.ledger)} unique entries after crash+replay+dup")
    print("LAB 3.4 PASS")

if __name__ == "__main__":
    asyncio.run(main())
