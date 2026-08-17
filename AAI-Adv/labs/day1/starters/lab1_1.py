# %% [markdown]
# # Lab 1.1 — Multi-Agent Topology Setup (Planner–Executor & ReAct)
# **Northwind Global Retail** | Microsoft Agent Framework
#
# Build a Planner (Supervisor) that decomposes a settlement-file request and a
# ReAct-style Executor that parses CSV records, wired as a state graph with
# persisted state between turns.
#
# Runs OFFLINE by default; set FOUNDRY_PROJECT_ENDPOINT + FOUNDRY_MODEL_DEPLOYMENT
# in .env to run against live Azure AI Foundry models.

# %%
from __future__ import annotations
import asyncio, csv, json, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import (Agent, Executor, WorkflowBuilder, WorkflowContext,
                          handler, make_chat_client, MODE)

print(f"Running in {MODE.upper()} mode")

# %% [markdown]
# ## Step 1 — Planner Agent (Supervisor)
# The Planner receives "process this settlement file" and returns a JSON plan.
# In Azure mode a live LLM plans; offline, a deterministic stub emits the same
# schema so downstream code is identical.

# %%
# ------------------------------------------------------------------
# TODO — implement Step 1: Planner Agent (Supervisor)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Planner Agent (Supervisor)")

# %% [markdown]
# ## Step 2 — Executor node (ReAct pattern over CSV rows)
# ReAct = interleaved Reason -> Act. Here each row triggers a *reason* step
# (should this row be parsed? is the promo field well-formed?) followed by an
# *act* step (emit a normalized record). Note defect D5: row 9 encodes the
# promo discount as an accounting-negative "(12.50)".

# %%
# ------------------------------------------------------------------
# TODO — implement Step 2: Executor node (ReAct pattern over CSV rows)
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: Executor node (ReAct pattern over CSV rows)")

# %% [markdown]
# ## Step 3 — Wire the state graph: Supervisor -> Executor

# %%
async def main() -> dict:
    plan_node = PlannerNode(id="planner")
    exec_node = CsvExecutorNode(id="csv_executor")

    workflow = (
        WorkflowBuilder(start_executor=plan_node, name="lab1_1_topology")
        .add_edge(plan_node, exec_node)
        .build()
    )
    result = await workflow.run("settlement_2026_08_batch1.csv")
    out = result.get_outputs()[0]
    print(f"Plan steps: {[s['task'] for s in out['plan']['plan']]}")
    print(f"Parsed {out['parsed']} rows; rejected: {out['rejected']}")
    print("Sample record:", out["records"][0])
    assert out["parsed"] == 26, f"expected 26 rows, got {out['parsed']}"
    assert out["rejected"] == [], "no rows should reject once parse_money handles ()"
    assert any(r["promo_discount"] < 0 for r in out["records"]), "D5 negative promo parsed"
    print("LAB 1.1 PASS")
    return out

if __name__ == "__main__":
    asyncio.run(main())
