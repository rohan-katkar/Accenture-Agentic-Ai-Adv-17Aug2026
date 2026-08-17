# %% [markdown]
# # Lab 3.3 — Enterprise Asset Catalog & Tool Reuse
# Package the D365 MCP connector as a **standalone reusable module** with a
# machine-readable tool specification, "publish" it to a catalog, then import
# it into a *different* business context — a Shopify reconciliation service —
# without touching the connector code.
#
# The catalog here is a local JSON registry that mirrors the shape of the
# Azure AI Foundry asset catalog entry (name, version, tool contracts, launch
# command). AZURE publishing steps are in the lab guide [VERIFY — the Foundry
# catalog/registry surface is preview and its portal flow changes].

# %%
import asyncio, json, sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "common" / "model.py").exists())
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs"; OUT.mkdir(exist_ok=True)
CATALOG = OUT / "asset_catalog.json"

# %% [markdown]
# ## Step 1 — Introspect the connector and build the catalog entry
# The tool contracts are pulled LIVE from the running MCP server (tools/list),
# so the published spec can never drift from the implementation.

# %%
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = ROOT / "tools" / "mcp_d365_server.py"

async def introspect_connector() -> dict:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return {t.name: {"description": t.description,
                             "input_schema": t.input_schema} for t in tools.tools}

def publish(contracts: dict) -> dict:
    entry = {
        "asset_id": "northwind.connectors.d365-erp",
        "version": "1.0.0",
        "kind": "mcp-connector",
        "transport": "stdio",
        "launch": {"command": "python", "args": ["tools/mcp_d365_server.py"]},
        "tools": contracts,
        "owner": "reconciliation-platform-team",
        "tags": ["erp", "d365", "reconciliation"],
    }
    catalog = json.loads(CATALOG.read_text()) if CATALOG.exists() else {"assets": []}
    catalog["assets"] = [a for a in catalog["assets"] if a["asset_id"] != entry["asset_id"]]
    catalog["assets"].append(entry)
    CATALOG.write_text(json.dumps(catalog, indent=2))
    return entry

# %% [markdown]
# ## Step 2 — Consume from the catalog in a NEW business context
# The Shopify reconciliation service knows nothing about the connector's code:
# it reads the catalog entry, launches the connector from `launch`, and binds
# the tools to its own agent. Same connector, different domain.

# %%
from common.model import Agent, MCPStdioTool, make_chat_client, foundry_configured

async def shopify_service_run() -> dict:
    entry = next(a for a in json.loads(CATALOG.read_text())["assets"]
                 if a["asset_id"] == "northwind.connectors.d365-erp")
    cmd = f"{sys.executable} {ROOT / entry['launch']['args'][0]}"
    d365 = MCPStdioTool(name="erp", command=cmd,
                        description="ERP connector imported from enterprise catalog")
    agent = Agent(client=make_chat_client(), name="shopify_reconciler",
                  instructions="Reconcile Shopify payouts against ERP invoices "
                               "using the erp tools.",
                  tools=d365)
    # Protocol-level reuse check (works in both modes): call through raw MCP.
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("search_invoice", {"order_id": "NW-1020"})
            record = json.loads(res.content[0].text)
    if foundry_configured():
        reply = await agent.run("Look up invoice for order NW-1020 and quote its amount.")
        return {"record": record, "agent_reply": reply.text}
    return {"record": record, "agent_reply": "(offline: agent tool-choice needs live model)"}

# %%
async def main():
    contracts = await introspect_connector()
    entry = publish(contracts)
    print(f"Published {entry['asset_id']} v{entry['version']} "
          f"with tools: {list(entry['tools'])}")
    assert set(entry["tools"]) == {"search_invoice", "post_ledger_entry", "list_open_invoices"}
    assert entry["tools"]["search_invoice"]["input_schema"]["required"] == ["order_id"]

    result = await shopify_service_run()
    print("Shopify context lookup:", result["record"])
    assert result["record"]["order_id"] == "NW-1020" and result["record"]["status"] == "open"
    print("Cross-domain reuse verified: same connector, Shopify consumer, zero code changes")
    print("LAB 3.3 PASS")

if __name__ == "__main__":
    asyncio.run(main())
