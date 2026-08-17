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

# ------------------------------------------------------------------
# TODO — implement Step 1: Introspect the connector and build the catalog entry
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 1: Introspect the connector and build the catalog entry")

# %% [markdown]
# ## Step 2 — Consume from the catalog in a NEW business context
# The Shopify reconciliation service knows nothing about the connector's code:
# it reads the catalog entry, launches the connector from `launch`, and binds
# the tools to its own agent. Same connector, different domain.

# %%
from common.model import Agent, MCPStdioTool, make_chat_client, foundry_configured

# ------------------------------------------------------------------
# TODO — implement Step 2: Consume from the catalog in a NEW business context
# The assertions in the final cell define 'done'. Named failure
# modes and hints are in the lab guide for this step.
# ------------------------------------------------------------------
raise NotImplementedError("STEP 2: Consume from the catalog in a NEW business context")

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
