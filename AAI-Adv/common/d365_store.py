"""Mock Microsoft Dynamics 365 ERP invoice store.

Backs both the MCP server (Lab 1.2 / capstone) and direct matcher nodes.
Ledger posting is idempotent by (order_id, amount) key — this is what the
Day 3.4 resiliency lab exercises against duplicate settlement rows (defect D3).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVOICES = ROOT / "data" / "invoices" / "invoices.json"


class D365Store:
    def __init__(self, invoices_path: Path = INVOICES):
        self._invoices = {r["order_id"]: r for r in json.loads(Path(invoices_path).read_text())}
        self._ledger: dict[tuple[str, float], dict] = {}
        self._lock = threading.Lock()

    # -- query -----------------------------------------------------------
    def find_invoice(self, order_id: str) -> dict | None:
        return self._invoices.get(order_id)

    # -- command ----------------------------------------------------------
    def post_ledger_entry(self, order_id: str, amount: float, memo: str = "") -> dict:
        """Idempotent post: re-posting the same (order_id, amount) is a no-op."""
        key = (order_id, round(float(amount), 2))
        with self._lock:
            if key in self._ledger:
                return {"status": "duplicate_ignored", "entry": self._ledger[key]}
            entry = {"order_id": order_id, "amount": key[1], "memo": memo,
                     "entry_no": f"GL-{len(self._ledger) + 1:05d}"}
            self._ledger[key] = entry
            return {"status": "posted", "entry": entry}

    @property
    def ledger(self) -> list[dict]:
        return list(self._ledger.values())
