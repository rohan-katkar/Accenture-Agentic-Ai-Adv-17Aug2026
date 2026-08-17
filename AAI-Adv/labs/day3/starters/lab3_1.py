# %% [markdown]
# # Lab 3.1 — Maturity Level Promotion & Dynamic Model Routing
# Two production-lifecycle controls:
#   1. **Model router**: routine line-item parsing -> lightweight SLM deployment;
#      complex fee-variance reasoning -> advanced LLM deployment. Offline the
#      router selects between two OfflineChatClient personas and records the
#      routing matrix; in Azure mode the same router selects between two real
#      Foundry deployment names (env: FOUNDRY_MODEL_SMALL / FOUNDRY_MODEL_LARGE).
#      [VERIFY: Azure AI Foundry also offers a hosted "model router" deployment
#      type that does this server-side — the portal steps are in the lab guide;
#      this lab builds the client-side router so the policy is inspectable.]
#   2. **Maturity promotion gates**: Sandbox -> Staging -> Production transitions
#      allowed only when the Lab 2.3 evaluation report clears the thresholds.

# %%
import asyncio, json, os, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import Agent, make_chat_client, MODE, foundry_configured
print(f"Mode: {MODE}")
OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)

# %% [markdown]
# ## Step 1 — Task-difficulty classifier and routing policy

# %%
# ------------------------------------------------------------------
# TODO — implement Step 1: Task-difficulty classifier and routing policy
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Task-difficulty classifier and routing policy")

# %% [markdown]
# ## Step 2 — Execute the routing matrix

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: Execute the routing matrix
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: Execute the routing matrix")

# %% [markdown]
# ## Step 3 — Maturity promotion gates driven by the eval report

# %%
# ------------------------------------------------------------------
# TODO — implement Step 3: Maturity promotion gates driven by the eval report
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 3: Maturity promotion gates driven by the eval report")

# %%
async def main():
    matrix = await run_matrix()
    print(json.dumps(matrix, indent=2))
    routed = {m["task"]: m["routed_to"] for m in matrix}
    assert routed == {"T1": "slm", "T2": "slm", "T3": "slm", "T4": "llm", "T5": "llm"}

    report_path = OUT / "eval_report.json"
    assert report_path.exists(), "run Lab 2.3 first — promotion gates read its report"
    metrics = json.loads(report_path.read_text())["report"]["metrics"]

    level = "sandbox"
    for _ in range(2):
        level, blockers = promote(level, metrics)
        print(f"promotion -> {level}" + (f" BLOCKED: {blockers}" if blockers else ""))
    assert level == "production", "eval report passes both gates"

    weak = dict(metrics, safety=0.96)
    lvl2, blockers = promote("staging", weak)
    assert lvl2 == "staging" and blockers, "safety<1.0 must block production"
    print("Gate correctly blocked promotion with degraded safety:", blockers)

    (OUT / "routing_matrix.json").write_text(json.dumps(matrix, indent=2))
    print("LAB 3.1 PASS")

if __name__ == "__main__":
    asyncio.run(main())
