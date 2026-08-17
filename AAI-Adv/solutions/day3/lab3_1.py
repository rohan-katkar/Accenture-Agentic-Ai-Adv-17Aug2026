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
def difficulty(task: dict) -> str:
    """Cheap heuristic classifier — the router's decision input."""
    if task["type"] == "parse_line":
        return "routine"
    if task["type"] == "variance_reasoning" and abs(task.get("variance", 0)) > 500:
        return "complex"
    return "routine" if task.get("variance", 0) == 0 else "moderate"

ROUTING_POLICY = {"routine": "slm", "moderate": "slm", "complex": "llm"}


def make_router():
    """Returns route(task) -> (tier, agent). Client construction isolated here."""
    if foundry_configured():
        from azure.identity import DefaultAzureCredential
        from agent_framework.foundry import FoundryChatClient
        cred = DefaultAzureCredential()
        ep = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
        clients = {
            "slm": FoundryChatClient(project_endpoint=ep, credential=cred,
                    model=os.environ.get("FOUNDRY_MODEL_SMALL",
                                         os.environ["FOUNDRY_MODEL_DEPLOYMENT"])),
            "llm": FoundryChatClient(project_endpoint=ep, credential=cred,
                    model=os.environ.get("FOUNDRY_MODEL_LARGE",
                                         os.environ["FOUNDRY_MODEL_DEPLOYMENT"])),
        }
    else:
        clients = {"slm": make_chat_client(), "llm": make_chat_client()}
    agents = {tier: Agent(client=c, name=f"{tier}_worker",
                          instructions=f"You are the {tier.upper()} tier worker.")
              for tier, c in clients.items()}

    def route(task: dict):
        tier = ROUTING_POLICY[difficulty(task)]
        return tier, agents[tier]
    return route

# %% [markdown]
# ## Step 2 — Execute the routing matrix

# %%
TASKS = [
    {"id": "T1", "type": "parse_line", "payload": "NW-1010 row"},
    {"id": "T2", "type": "parse_line", "payload": "NW-1011 row"},
    {"id": "T3", "type": "variance_reasoning", "variance": 12.0},
    {"id": "T4", "type": "variance_reasoning", "variance": 612.4},
    {"id": "T5", "type": "variance_reasoning", "variance": -750.0},
]

async def run_matrix() -> list[dict]:
    route = make_router()
    matrix = []
    for t in TASKS:
        tier, agent = route(t)
        resp = await agent.run(f"task {t['id']}: variance={t.get('variance', 0)}")
        matrix.append({"task": t["id"], "difficulty": difficulty(t),
                       "routed_to": tier, "reply_head": resp.text[:40]})
    return matrix

# %% [markdown]
# ## Step 3 — Maturity promotion gates driven by the eval report

# %%
LEVELS = ["sandbox", "staging", "production"]
GATES = {  # minimum eval scores to ENTER each level
    "staging":    {"grounding": 0.95, "relevance": 0.90, "safety": 1.00},
    "production": {"grounding": 0.98, "relevance": 0.95, "safety": 1.00},
}

def promote(current: str, metrics: dict) -> tuple[str, list[str]]:
    """Attempt one promotion step; returns (new_level, blockers)."""
    nxt = LEVELS[min(LEVELS.index(current) + 1, len(LEVELS) - 1)]
    if nxt == current:
        return current, []
    blockers = [f"{k}: {metrics.get(k, 0):.3f} < {thr:.2f}"
                for k, thr in GATES[nxt].items() if metrics.get(k, 0) < thr]
    return (nxt if not blockers else current), blockers

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
