"""MCP server mocking the Microsoft Dynamics 365 ERP invoice API.

Verified against mcp==2.0.0 (MCPServer replaces the 1.x FastMCP class; the
decorator API — @server.tool() — and run("stdio") are equivalent).

Exposes three tools over stdio:
  search_invoice(order_id)                 -> open invoice record or not_found
  post_ledger_entry(order_id, amount, memo)-> idempotent GL post
  list_open_invoices(limit)                -> first N open invoices

JSON Schema contracts for payload exchange are auto-derived from the Python
type hints by the MCP SDK and served to clients via tools/list.

Run standalone:      python tools/mcp_d365_server.py
Consumed by agents:  MCPStdioTool(name="d365", command="python tools/mcp_d365_server.py")
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server import MCPServer

from common.d365_store import D365Store

server = MCPServer(
    name="d365-erp-mock",
    instructions="Mock Dynamics 365 ERP for Northwind reconciliation labs.",
)
_store = D365Store()


@server.tool()
def search_invoice(order_id: str) -> str:
    """Search D365 open invoices by Amazon order id (e.g. NW-1017)."""
    inv = _store.find_invoice(order_id)
    return json.dumps(inv if inv else {"status": "not_found", "order_id": order_id})


@server.tool()
def post_ledger_entry(order_id: str, amount: float, memo: str = "") -> str:
    """Post a verified reconciliation entry to the GL. Idempotent on (order_id, amount)."""
    return json.dumps(_store.post_ledger_entry(order_id, amount, memo))


@server.tool()
def list_open_invoices(limit: int = 5) -> str:
    """Return up to `limit` open invoices."""
    rows = [v for v in _store._invoices.values()][: max(1, min(limit, 50))]
    return json.dumps(rows)


if __name__ == "__main__":
    server.run("stdio")
