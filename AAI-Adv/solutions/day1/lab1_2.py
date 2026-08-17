# %% [markdown]
# # Lab 1.2 — Standardizing Tooling with Model Context Protocol (MCP)
# Expose the mock **Dynamics 365 ERP** invoice API as an MCP server, inspect the
# JSON Schema contracts it publishes, and bind it to the Lab 1.1 executor agent.
#
# Two validation layers:
#   A. Protocol-level: connect with a raw MCP client, list tools, call one.
#   B. Agent-level: attach the server to an Agent via MCPStdioTool. (In OFFLINE
#      mode the stub client cannot *decide* to call tools — that requires a live
#      LLM — so agent-level tool invocation is exercised in AZURE mode; the
#      protocol layer is fully validated either way.)

# %%
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))

from common.model import Agent, MCPStdioTool, make_chat_client, MODE, foundry_configured

SERVER_CMD = f"{sys.executable} {ROOT / 'tools' / 'mcp_d365_server.py'}"
print(f"Mode: {MODE} | MCP server cmd: {SERVER_CMD}")

# %% [markdown]
# ## Step 1 — Protocol-level contract validation
# A raw MCP stdio client session lists the published tools. The JSON Schema for
# each tool (`input_schema`; wire name inputSchema) is the *contract* other agents program against —
# order_id: string, amount: number, etc.

# %%
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def validate_contracts() -> dict:
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "tools" / "mcp_d365_server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            contracts = {t.name: t.input_schema for t in tools.tools}
            print("Published tools:", list(contracts))
            print("search_invoice contract:",
                  json.dumps(contracts["search_invoice"], indent=2))

            # Call the tool through the protocol — this is a real IPC round trip.
            res = await session.call_tool("search_invoice", {"order_id": "NW-1017"})
            payload = json.loads(res.content[0].text)
            print("search_invoice(NW-1017) ->", payload)
            assert payload["order_id"] == "NW-1017" and payload["status"] == "open"

            res2 = await session.call_tool("search_invoice", {"order_id": "NW-9999"})
            assert json.loads(res2.content[0].text)["status"] == "not_found"

            res3 = await session.call_tool("post_ledger_entry",
                                           {"order_id": "NW-1010", "amount": 131.67})
            assert json.loads(res3.content[0].text)["status"] == "posted"
            return contracts

# %% [markdown]
# ## Step 2 — Bind the MCP server to the ReAct executor agent
# `MCPStdioTool` spawns the server as a subprocess and exposes its tools to the
# agent's function-calling loop. With a live Foundry model the agent decides
# when to call `search_invoice`; the assertion below checks the invoice amount
# appears in the final answer.

# %%
async def agent_with_mcp() -> None:
    d365 = MCPStdioTool(
        name="d365",
        command=SERVER_CMD,
        description="Dynamics 365 ERP invoice search and ledger posting",
    )
    agent = Agent(
        client=make_chat_client(),
        name="react_executor",
        instructions=(
            "You reconcile Amazon settlements for Northwind. Use the d365 tools "
            "to look up invoices before answering. Quote amounts exactly."
        ),
        tools=d365,
    )
    reply = await agent.run("What is the open invoice amount for order NW-1017?")
    print("Agent reply:", reply.text)
    if foundry_configured():
        assert "1141.95" in reply.text, "live model should quote the invoice amount"


async def main():
    contracts = await validate_contracts()
    assert set(contracts) == {"search_invoice", "post_ledger_entry", "list_open_invoices"}
    if foundry_configured():
        await agent_with_mcp()
        print("Agent-level MCP invocation validated against live Foundry model.")
    else:
        print("OFFLINE: protocol contracts validated; agent-level tool choice "
              "requires a live model (set .env and re-run for full path).")
    print("LAB 1.2 PASS")

if __name__ == "__main__":
    asyncio.run(main())
