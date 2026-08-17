"""Seed data generator — Northwind Global Retail reconciliation domain.

Generates deterministic (seeded) fixtures:
  data/settlements/settlement_2026_08_batch<k>.csv   Amazon Seller Central style
  data/invoices/invoices.json                        D365 open invoices
  data/policies/amazon_fee_schedule.md               grounding corpus
  data/policies/return_policy.md

PLANTED DEFECTS (deliberate, documented — labs teach real debugging):
  D1  Order NW-1017: fba_fee overstated by $612.40  -> must HITL-escalate ($ rule)
  D2  Order NW-1023: 6.2% variance on a small total -> must HITL-escalate (% rule)
  D3  Order NW-1031: duplicate settlement row       -> idempotency test (Day 3.4)
  D4  Order NW-1034: order id missing from D365     -> unmatched-exception path
  D5  Row 9: promo_discount written as "(12.50)"    -> accounting-negative parse
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

RULE_DOLLAR = 500.00   # HITL if abs variance > $500
RULE_PCT = 5.0         # HITL if variance pct > 5%


def generate(n_orders: int = 25, seed: int = 42) -> dict:
    rng = random.Random(seed)
    (DATA / "settlements").mkdir(parents=True, exist_ok=True)
    (DATA / "invoices").mkdir(parents=True, exist_ok=True)
    (DATA / "policies").mkdir(parents=True, exist_ok=True)

    rows, invoices = [], []
    for i in range(n_orders):
        oid = f"NW-{1010 + i}"
        asin = f"B0{rng.randint(10**6, 10**7 - 1)}X"
        gross = round(rng.uniform(80, 4000), 2)
        fba = round(gross * rng.uniform(0.08, 0.15), 2)
        promo = round(gross * rng.uniform(0.0, 0.05), 2)
        comm = round(gross * 0.15, 2)
        net = round(gross - fba - promo - comm, 2)

        invoice_amt = net  # clean match by default
        if oid == "NW-1017":                       # D1: dollar-rule breach
            fba = round(fba + 612.40, 2)
            net = round(gross - fba - promo - comm, 2)
        if oid == "NW-1023":                       # D2: percent-rule breach
            invoice_amt = round(net * 1.062, 2)
        if oid == "NW-1012":                       # D6: unallocated promo (8% gross)
            promo = round(gross * 0.08, 2)
            net = round(gross - fba - promo - comm, 2)
            invoice_amt = net

        promo_repr = f"({promo:.2f})" if i == 9 else f"{promo:.2f}"  # D5
        rows.append([oid, asin, f"{gross:.2f}", f"{fba:.2f}", promo_repr, f"{comm:.2f}", f"{net:.2f}"])
        if oid != "NW-1034":                       # D4: missing invoice
            invoices.append({"invoice_id": f"INV-{7000 + i}", "order_id": oid,
                             "amount": invoice_amt, "status": "open",
                             "customer": "Amazon EU S.a r.l."})

    dup = next(r for r in rows if r[0] == "NW-1031")  # D3: duplicate row
    rows.append(list(dup))

    csv_path = DATA / "settlements" / "settlement_2026_08_batch1.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "asin", "gross_amount", "fba_fee", "promo_discount", "commission", "net_amount"])
        w.writerows(rows)

    inv_path = DATA / "invoices" / "invoices.json"
    inv_path.write_text(json.dumps(invoices, indent=2))

    (DATA / "policies" / "amazon_fee_schedule.md").write_text(
        "# Amazon Seller Fee Schedule (Northwind vendor agreement extract)\n\n"
        "FBA storage fees above USD 500 per settlement line require manual review "
        "by the vendor finance team before posting.\n\n"
        "Commission is fixed at 15% of gross for category 'Home & Kitchen'.\n\n"
        "Promotional discounts exceeding 5% of gross must reference a signed "
        "promo agreement ID.\n"
    )
    (DATA / "policies" / "return_policy.md").write_text(
        "# Return & Credit Policy (extract)\n\n"
        "Credit memos for damaged goods must be posted within 30 days of the "
        "carrier scan date.\n\n"
        "Disputed FBA fee variances greater than 5% of invoice value are "
        "escalated to a human reviewer per SOX control NW-FIN-07.\n"
    )
    return {"csv": str(csv_path), "invoices": str(inv_path), "orders": n_orders,
            "rows_written": len(rows), "invoices_written": len(invoices)}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
