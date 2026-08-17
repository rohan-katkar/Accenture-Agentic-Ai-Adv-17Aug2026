# %% [markdown]
# # Lab 1.4 — Azure Infrastructure Blueprinting & HITL Logic
# Two deliverables:
#   1. `infra/main.bicep` — storage queues, container runtime, managed identity.
#      (Blueprint is emitted and lint-checked structurally; deploying it needs a
#      real subscription — steps in the lab guide.)
#   2. A **functional HITL escalation trigger** in Microsoft Agent Framework:
#      variance > $500 OR > 5%  ->  the graph PAUSES and emits a request to the
#      human review queue; the run resumes only when a reviewer responds.
#
# HITL mechanism (VERIFIED by execution on agent-framework-core 1.14.0):
#   ctx.request_info(data, response_type=T)  pauses at this node
#   result.get_request_info_events()         exposes pending requests
#   workflow.run(responses={request_id: v})  resumes into @response_handler

# %%
import asyncio, json, sys
from dataclasses import dataclass
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import (Executor, WorkflowBuilder, WorkflowContext,
                          handler, response_handler)
from common.data_gen import RULE_DOLLAR, RULE_PCT

# %% [markdown]
# ## Step 1 — Emit the Bicep blueprint

# %%
# ------------------------------------------------------------------
# TODO — implement Step 1: Emit the Bicep blueprint
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Emit the Bicep blueprint")

# %% [markdown]
# ## Step 2 — HITL escalation trigger in the graph

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: HITL escalation trigger in the graph
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: HITL escalation trigger in the graph")

# %% [markdown]
# ## Step 3 — Simulated execution: pause at high-variance nodes, then resume

# %%
async def main():
    gate = VarianceGate(id="variance_gate")
    wf = WorkflowBuilder(start_executor=gate, name="lab1_4_hitl").build()

    # Case A: low variance -> flows straight through.
    r = await wf.run({"order_id": "NW-1010", "variance_usd": 12.0, "variance_pct": 0.4})
    assert r.get_outputs()[0]["route"] == "auto_post"
    print("NW-1010: auto_post (no pause)")

    # Case B: dollar-rule breach -> graph pauses.
    r = await wf.run({"order_id": "NW-1017", "variance_usd": 612.40, "variance_pct": 3.9})
    pending = r.get_request_info_events()
    assert r.get_outputs() == [] and len(pending) == 1, "graph must pause, not output"
    req = pending[0]
    print(f"PAUSED at {req.data.order_id}: {req.data.reason} (request {req.request_id[:8]}…)")

    # Human reviewer responds -> run resumes into the response handler.
    resumed = await wf.run(responses={req.request_id: "approved"})
    out = resumed.get_outputs()[0]
    assert out == {"order_id": "NW-1017", "route": "human_approved",
                   "reason": "abs variance $612.40 > $500"}
    print("RESUMED:", out)

    # Case C: percent-rule breach.
    r = await wf.run({"order_id": "NW-1023", "variance_usd": 70.4, "variance_pct": 6.2})
    assert len(r.get_request_info_events()) == 1
    print("NW-1023: paused on percent rule [OK]")
    print("LAB 1.4 PASS")

if __name__ == "__main__":
    asyncio.run(main())
