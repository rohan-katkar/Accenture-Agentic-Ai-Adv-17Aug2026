"""
Day 1 Web Application - Reconciliation Console
==============================================
Run:  streamlit run Day1_Foundations/webapp/app_reconciliation_console.py

WHAT IT IS FOR
--------------
Labs 1-5 print to a terminal. A terminal is fine for an engineer and useless for
the O2C process owner sitting in the room. This console renders the same compiled
graph as an operations screen, so the business stakeholder can see:

    - which priority rule fired, and on what evidence
    - where the money went: applied, written off, disputed, or unapplied
    - the full state transition trail for any single payment
    - the two headline metrics, recomputed live

TEACHING USE (10 minutes, end of Day 1)
---------------------------------------
Open it, run the batch, then use the Rule Workbench to change the write-off
tolerance from 10.00 to 500.00. BNK-1002's 500.00 damage deduction silently
becomes an auto-write-off, straight-through jumps, and nobody is told a customer
claimed damaged goods. That is the lesson: an automation metric can be improved
by writing money off, and the metric alone will not tell you.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# --- repository root on sys.path ---
_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "00_Program").is_dir():
        REPO = _p
        sys.path.insert(0, str(_p))
        break
else:  # pragma: no cover
    st.error("Could not locate the repository root (the folder containing 00_Program).")
    st.stop()

sys.path.insert(0, str(REPO / "Day1_Foundations" / "solutions"))

from shared.config import SEED_DIR  # noqa: E402
from shared.telemetry import configure, new_run_id  # noqa: E402

configure(level="WARNING")  # keep the browser console quiet

st.set_page_config(page_title="O2C Reconciliation Console", page_icon="◆", layout="wide")

NAVY, DEEP, TEAL, MINT, GOLD = "#21295C", "#065A82", "#1C7293", "#16A0A0", "#E0A800"

STATE_COLOUR = {
    "CLOSED": "#1E7B4D", "PARTIAL_MATCH": GOLD, "UAC": DEEP,
    "UIC": "#8B2E3C", "QUERY": TEAL, "OPEN": "#6B7280",
}

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2rem; }}
  h1, h2, h3 {{ font-family: Cambria, Georgia, serif; color: {NAVY}; }}
  .metric-card {{ background:#F4F7FA; border-radius:10px; padding:14px 18px; }}
  code {{ font-family: Consolas, monospace; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Graph construction (cached - compiling per rerun would be wasteful)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def build_graph():
    import lab05_compile_langgraph as engine  # noqa: PLC0415
    return engine.graph


@st.cache_data(show_spinner=False)
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(SEED_DIR / name)


def run_batch(rows: list[dict], tolerance: float) -> list[dict]:
    """Execute the compiled graph over every bank row at a given tolerance."""
    import lab04_nodes_and_routing as rules  # noqa: PLC0415
    import lab05_compile_langgraph as engine  # noqa: PLC0415

    original = rules.TOLERANCE_USD
    rules.TOLERANCE_USD = tolerance
    engine.TOLERANCE_USD = tolerance
    try:
        graph = build_graph()
        return [
            graph.invoke({
                "run_id": new_run_id("ui"),
                "txn_id": r["txn_id"],
                "bank_customer_raw": r["customer_name_raw"],
                "bank_amount_usd": float(r["amount_usd"]),
                "bank_reference": r["reference_text"],
                "value_date": r["value_date"],
                "trace": [], "errors": [],
            })
            for r in rows
        ]
    finally:
        rules.TOLERANCE_USD = original
        engine.TOLERANCE_USD = original


# ---------------------------------------------------------------------------
# Sidebar - the rule workbench
# ---------------------------------------------------------------------------
st.sidebar.title("Rule Workbench")
st.sidebar.caption("Change a business rule and watch the metrics move.")

tolerance = st.sidebar.slider(
    "Auto write-off tolerance (USD)", min_value=0.0, max_value=750.0,
    value=10.0, step=5.0,
    help="Variances at or below this value are written off with no human review.",
)

if tolerance > 100:
    st.sidebar.warning(
        f"At {tolerance:,.0f} USD you are writing off genuine customer deductions "
        "without recording why. Straight-through will rise. Root-cause visibility "
        "will disappear. This is the trade-off to discuss with the process owner."
    )

st.sidebar.divider()
st.sidebar.markdown("**Data sources**")
st.sidebar.caption(
    "`bank_statement.csv` - 10 inbound payments\n\n"
    "`erp_ar_open.csv` - 9 open AR items\n\n"
    "`remittance/` - 5 unstructured advices (used from Day 2)"
)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Order-to-Cash Reconciliation Console")
st.caption("Day 1 · the compiled LangGraph state machine from Lab 5, rendered as an operations screen")

with open(SEED_DIR / "bank_statement.csv", newline="", encoding="utf-8") as fh:
    bank_rows = list(csv.DictReader(fh))

results = run_batch(bank_rows, tolerance)

closed = [r for r in results if r["end_state"] == "CLOSED"]
matched = [r for r in results if r.get("matched_priority")]
human = [r for r in results if r.get("requires_human")]
written_off = sum(r.get("write_off_usd", 0.0) for r in results)
disputed = sum(r.get("dispute_usd", 0.0) for r in results)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Match rate", f"{len(matched) / len(results):.0%}", f"{len(matched)} of {len(results)}")
c2.metric("Straight-through", f"{len(closed) / len(results):.0%}", f"{len(closed)} of {len(results)}")
c3.metric("Written off", f"${written_off:,.2f}",
          delta="no reason recorded" if written_off else None, delta_color="off")
c4.metric("In dispute", f"${disputed:,.2f}", f"{len(human)} items need a human", delta_color="off")

st.info(
    "**Match rate and straight-through are different numbers.** A payment can match "
    "its invoice perfectly and still need a human — BNK-1002 matches and still raises "
    "a $500 damage dispute. Reporting only the higher number is the most common way "
    "an automation business case gets overstated."
)

tab_batch, tab_detail, tab_ledger, tab_topology = st.tabs(
    ["Batch results", "Transaction detail", "Source ledgers", "Graph topology"]
)

# --- Batch results -----------------------------------------------------------
with tab_batch:
    frame = pd.DataFrame([{
        "Txn": r["txn_id"],
        "End state": r["end_state"],
        "Priority": r.get("matched_priority") or "",
        "Invoice": r.get("matched_invoice", "—"),
        "Paid": r["bank_amount_usd"],
        "Billed": r.get("erp_amount_usd", 0.0),
        "Variance": r.get("variance_usd", 0.0),
        "Written off": r.get("write_off_usd", 0.0),
        "Dispute": r.get("dispute_usd", 0.0),
        "Human": "yes" if r.get("requires_human") else "",
    } for r in results])

    def shade(row: pd.Series) -> list[str]:
        colour = STATE_COLOUR.get(row["End state"], "#FFFFFF")
        return [f"background-color: {colour}22"] * len(row)

    st.dataframe(
        frame.style.apply(shade, axis=1).format({
            "Paid": "${:,.2f}", "Billed": "${:,.2f}", "Variance": "${:,.2f}",
            "Written off": "${:,.2f}", "Dispute": "${:,.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

    left, right = st.columns([2, 3])
    with left:
        st.subheader("End-state distribution")
        counts = frame["End state"].value_counts()
        st.bar_chart(counts, color=DEEP)
    with right:
        st.subheader("Where the exceptions sit")
        st.markdown("""
| End state | Owner | What they do next |
|---|---|---|
| `CLOSED` | — | nothing; invoice settled |
| `PARTIAL_MATCH` | Deductions analyst | validate the claim, issue or reject a credit |
| `UAC` | Cash Application | chase the customer for an allocation |
| `UIC` | Treasury | investigate with the bank; nothing can post yet |
| `QUERY` | Human-In-The-Loop queue | judgement call, then resume the workflow |
""")
        st.warning(
            "**BNK-1010 is an overpayment ($1,000 above invoice).** The source "
            "specification defines no end state for it. We route it to `QUERY` rather "
            "than force it into `PARTIAL_MATCH`. Raise this with the client — it is a "
            "genuine gap, not an implementation detail."
        )

# --- Transaction detail ------------------------------------------------------
with tab_detail:
    pick = st.selectbox("Transaction", [r["txn_id"] for r in results], index=1)
    chosen = next(r for r in results if r["txn_id"] == pick)

    a, b = st.columns([2, 3])
    with a:
        st.markdown("#### Facts")
        st.markdown(f"""
- **Payer (bank narrative):** `{chosen.get('bank_customer_raw') or '—blank—'}`
- **Reference:** `{chosen.get('bank_reference') or '—blank—'}`
- **Value date:** {chosen.get('value_date')}
- **Amount received:** ${chosen['bank_amount_usd']:,.2f}
- **Matched invoice:** {chosen.get('matched_invoice', '—')}
- **Priority rule fired:** {chosen.get('matched_priority') or '— none —'}
- **Match type:** {chosen.get('match_type', '—')}
""")
        colour = STATE_COLOUR.get(chosen["end_state"], NAVY)
        st.markdown(
            f"<div class='metric-card' style='border-left:6px solid {colour}'>"
            f"<b>End state:</b> {chosen['end_state']}<br>"
            f"<b>Human review:</b> {'REQUIRED' if chosen.get('requires_human') else 'not required'}"
            f"</div>", unsafe_allow_html=True)

    with b:
        st.markdown("#### State transition trail")
        st.caption("Produced by the graph, not by a developer remembering to log. "
                   "This is the object an auditor reads.")
        for i, line in enumerate(chosen.get("trace", []), 1):
            st.markdown(f"**{i}.** {line}")

        remit = SEED_DIR / "remittance"
        candidate = next((p for p in remit.glob(f"{pick}_*.txt")), None)
        if candidate:
            with st.expander("Remittance advice on file (parsed from Day 2 onward)"):
                st.code(candidate.read_text(encoding="utf-8"), language="text")
                st.caption(
                    "Day 1 cannot read this. Every fact in it is invisible to the "
                    "structured rules — which is precisely the Day 2 business case."
                )

# --- Source ledgers ----------------------------------------------------------
with tab_ledger:
    st.subheader("Bank statement")
    st.dataframe(load_csv("bank_statement.csv"), use_container_width=True, hide_index=True)
    st.subheader("ERP accounts receivable — open items")
    st.dataframe(load_csv("erp_ar_open.csv"), use_container_width=True, hide_index=True)
    st.subheader("Deduction reason codes")
    st.dataframe(load_csv("deduction_codes.csv"), use_container_width=True, hide_index=True)

# --- Topology ----------------------------------------------------------------
with tab_topology:
    st.subheader("Compiled graph topology")
    st.caption("A state machine can describe itself. An if/elif chain cannot — that is "
               "the architectural argument for LangGraph, stated concretely.")
    try:
        st.code(build_graph().get_graph().draw_mermaid(), language="text")
    except Exception as exc:  # noqa: BLE001
        st.caption(f"draw_mermaid unavailable on this LangGraph version ({exc}). Static view:")
        st.code("""START -> ingest -> rule_engine
rule_engine --matched--> variance_analysis
rule_engine --exception--> classify_exception
variance_analysis --closed--> close
variance_analysis --tolerance_write_off--> tolerance_write_off
variance_analysis --short_payment--> short_payment
variance_analysis --overpayment--> overpayment
{close, tolerance_write_off, short_payment, overpayment, classify_exception}
    -> finalise -> END""", language="text")

    st.markdown("""
#### Priority rules, in evaluation order

| # | Bank evidence | Match type | Status |
|---|---|---|---|
| 1 | customer + PO + amount | 2-way | live |
| 2 | customer + delivery number + amount | 2-way | live |
| 3 | customer + invoice + invoice date + amount | 2-way | live |
| 4 | customer + invoice + amount | 2-way | live |
| 5 | bank + ERP + remittance, with invoice date | 3-way | **needs Day 2** |
| 6 | bank + ERP + remittance, no date | 3-way | **needs Day 2** |

Rules 5 and 6 are written and unit-tested but return `None` while no remittance
document has been parsed. That is deliberate scaffolding, not an omission —
BNK-1008 stays unmatched today for exactly this reason.
""")

st.divider()
st.caption("Accenture Batch 1 · Agentic AI Foundation · Day 1 · offline-capable, no Azure calls required")
