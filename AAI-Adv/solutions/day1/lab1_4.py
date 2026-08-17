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
BICEP = """// Northwind reconciliation platform — Lab 1.4 blueprint
// Deploy: az deployment group create -g <rg> -f main.bicep
param location string = resourceGroup().location
param baseName string = 'nwrecon'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${baseName}sa${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false }
}

resource queueSvc 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource reviewQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueSvc
  name: 'human-review'
}

resource ingestQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueSvc
  name: 'raw-settlements'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-agents-mi'
  location: location
}

resource aca 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-agents'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    configuration: { activeRevisionsMode: 'Single' }
    template: {
      containers: [ { name: 'agents', image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest',
                      resources: { cpu: json('0.5'), memory: '1Gi' } } ]
    }
  }
}

output reviewQueueName string = reviewQueue.name
output managedIdentityId string = identity.id
"""

INFRA = ROOT / "infra"
INFRA.mkdir(exist_ok=True)
(INFRA / "main.bicep").write_text(BICEP)

# Structural lint: balanced braces, required resources present.
assert BICEP.count("{") == BICEP.count("}"), "unbalanced braces in Bicep"
for required in ["storageAccounts", "queues", "userAssignedIdentities", "containerApps"]:
    assert required in BICEP, f"missing resource: {required}"
print(f"Bicep blueprint written: {INFRA/'main.bicep'} ({len(BICEP.splitlines())} lines)")

# %% [markdown]
# ## Step 2 — HITL escalation trigger in the graph

# %%
@dataclass
class ReviewRequest:
    order_id: str
    variance_usd: float
    variance_pct: float
    reason: str

def breaches_policy(variance_usd: float, variance_pct: float) -> str | None:
    if abs(variance_usd) > RULE_DOLLAR:
        return f"abs variance ${abs(variance_usd):.2f} > ${RULE_DOLLAR:.0f}"
    if abs(variance_pct) > RULE_PCT:
        return f"variance {abs(variance_pct):.1f}% > {RULE_PCT:.0f}%"
    return None


class VarianceGate(Executor):
    """Pauses execution and emits to the human review queue on breach."""

    @handler
    async def check(self, rec: dict, ctx: WorkflowContext[None, dict]) -> None:
        reason = breaches_policy(rec["variance_usd"], rec["variance_pct"])
        if reason is None:
            await ctx.yield_output({"order_id": rec["order_id"], "route": "auto_post"})
            return
        # Simulated queue emit (Azure mode: azure-storage-queue send_message).
        (ROOT / "outputs").mkdir(exist_ok=True)
        with (ROOT / "outputs" / "human_review_queue.jsonl").open("a") as q:
            q.write(json.dumps({"order_id": rec["order_id"], "reason": reason}) + "\n")
        await ctx.request_info(
            ReviewRequest(rec["order_id"], rec["variance_usd"], rec["variance_pct"], reason),
            response_type=str,
        )

    @response_handler
    async def on_review(self, req: ReviewRequest, decision: str,
                        ctx: WorkflowContext[None, dict]) -> None:
        # NOTE (C4): `from __future__ import annotations` (PEP 563 string
        # annotations) breaks response_handler signature validation in
        # agent-framework 1.14.0 — do NOT use the future import in modules
        # that define @response_handler methods.
        await ctx.yield_output({"order_id": req.order_id,
                                "route": f"human_{decision}",
                                "reason": req.reason})

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
