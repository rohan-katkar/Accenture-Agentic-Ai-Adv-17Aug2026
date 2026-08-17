"""common/model.py — SINGLE ISOLATION POINT for version-sensitive SDK surface.

All imports from `agent_framework` / `agent_framework.foundry` that could move
between SDK versions are re-exported from here. If Microsoft ships a breaking
change, this is the ONLY file that should need edits.

VERIFICATION REGISTER (probed against installed packages on 2026-08-16):
  agent-framework-core    == 1.14.0   [VERIFIED by import + smoke run]
  agent-framework-foundry == 1.11.0   [VERIFIED by import]
  Python                  >= 3.10 supported (3.10–3.14 per package classifiers)

VERIFIED facts (introspection + executed smoke tests):
  * Workflow pattern: Executor subclass + @handler(msg, ctx) + WorkflowBuilder(
        start_executor=...).add_edge(...).build();  await wf.run(msg)
  * HITL: await ctx.request_info(data, response_type=T) pauses the graph;
        pending requests via result.get_request_info_events();
        resume via wf.run(responses={request_id: value});
        the reply lands in a @response_handler method on the SAME executor.
  * Checkpointing: WorkflowBuilder(checkpoint_storage=FileCheckpointStorage(dir))
        and wf.run(checkpoint_id=..., checkpoint_storage=...) for rehydration.
  * Agents: Agent(client=<chat client>, instructions=..., tools=[...])
        FoundryChatClient(project_endpoint=..., model=..., credential=...).as_agent(...)
        -> as_agent() EXISTS in foundry 1.11.0; create_agent() DOES NOT.
  * MCP: MCPStdioTool(name=..., command=...) / MCPStreamableHTTPTool for
        attaching MCP servers as agent tools.
  * Offline extension point: subclass BaseChatClient, implement
        _inner_get_response(messages=, stream=, options=, **kw) -> ChatResponse.

VERSION-SENSITIVE / [VERIFY] before delivery on a fresh SDK:
  * agent_framework.observability exposes ObservabilitySettings et al. in this
    version; there is NO setup_observability() function here. Labs therefore
    use vanilla opentelemetry-sdk for tracing (stable public API).
  * FoundryEvals / evaluate_foundry_target signatures (foundry preview surface).
"""
from __future__ import annotations

import os

# ---- Core workflow primitives (VERIFIED) -----------------------------------
from agent_framework import (  # noqa: F401
    Agent,
    BaseChatClient,
    ChatResponse,
    Executor,
    FileCheckpointStorage,
    InMemoryCheckpointStorage,
    MCPStdioTool,
    MCPStreamableHTTPTool,
    Message,
    UsageDetails,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    handler,
    response_handler,
    tool,
)

# ---- Foundry integration (VERIFIED imports; network use requires Azure) ----
try:
    from agent_framework.foundry import FoundryChatClient  # noqa: F401
    FOUNDRY_AVAILABLE = True
except Exception:  # pragma: no cover - only hit if foundry pkg missing
    FoundryChatClient = None  # type: ignore
    FOUNDRY_AVAILABLE = False


def foundry_configured() -> bool:
    """True when the environment carries enough config to talk to Azure.

    Required env vars (see .env.template):
      FOUNDRY_PROJECT_ENDPOINT  e.g. https://<res>.services.ai.azure.com/api/projects/<proj>
      FOUNDRY_MODEL_DEPLOYMENT  e.g. gpt-4o-mini (your deployment name)
    Credential comes from DefaultAzureCredential (az login / managed identity).
    """
    return bool(
        FOUNDRY_AVAILABLE
        and os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        and os.getenv("FOUNDRY_MODEL_DEPLOYMENT")
    )


def make_chat_client():
    """Return a live FoundryChatClient when configured, else the offline stub.

    Every lab calls this ONE factory, so switching between offline and Azure
    modes never requires touching lab code.
    """
    if foundry_configured():
        from azure.identity import DefaultAzureCredential  # lazy: azure mode only

        return FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL_DEPLOYMENT"],
            credential=DefaultAzureCredential(),
        )
    from common.offline_client import OfflineChatClient

    return OfflineChatClient()


MODE = "azure" if foundry_configured() else "offline"
