"""
Capstone Web Application — Analyst Review Console
=================================================
Run:  streamlit run Capstone/webapp/app_analyst_console.py

WHAT IT IS FOR
--------------
The automation's real output is not the CLOSED items - nobody looks at those.
It is the exception queues, and this is the screen the people who work them use.

Four queues, four different owners:
    AWAITING_HUMAN          suspended mid-graph; a decision resumes it
    QUERY                   needs judgement; no reason code available
    UAC / UIC               cash application and treasury
    REJECTED_SECURITY_HOLD  security review

The Decide tab is the one that matters: an analyst supplies an action, their
name and a rationale, and the graph RESUMES from the exact node that suspended.
Attribution is mandatory - "a human approved it" is not an audit trail.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "00_Program").is_dir():
        REPO = _p
        sys.path.insert(0, str(_p))
        break
else:  # pragma: no cover
    st.error("Could not locate the repository root (the folder containing 00_Program).")
    st.stop()

from shared.telemetry import configure  # noqa: E402

configure(level="ERROR")

from Capstone.src.batch import pending, resume_transaction, run_batch  # noqa: E402
from Capstone.src.domain import END_STATE_OWNER, load_deduction_codes  # noqa: E402

st.set_page_config(page_title="Reconciliation — Analyst Console",
                   page_icon="◆", layout="wide")

NAVY, DEEP, TEAL, MINT, GOLD = "#21295C", "#065A82", "#1C7293", "#16A0A0", "#E0A800"
STATE_COLOUR = {
    "CLOSED": "#1E7B4D", "PARTIAL_MATCH": GOLD, "UAC": DEEP, "UIC": "#8B2E3C",
    "QUERY": TEAL, "AWAITING_HUMAN": "#7A4FBF", "REJECTED_SECURITY_HOLD": "#8B2E3C",
}

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2rem; }}
  h1, h2, h3 {{ font-family: Cambria, Georgia, serif; color: {NAVY}; }}
  code, pre {{ font-family: Consolas, monospace; }}
</style>
""", unsafe_allow_html=True)

DB = str(REPO / "capstone_state.sqlite")

# ---------------------------------------------------------------------------
st.title("Automated Payment & Reconciliation")
st.caption("Analyst review console · the exception queues, not the happy path")

if "result" not in st.session_state:
    st.session_state.result = None
if "resumed" not in st.session_state:
    st.session_state.resumed = {}

with st.sidebar:
    st.title("Batch control")
    hitl = st.checkbox("Human-in-the-loop", value=True,
                       help="When on, low-confidence deductions SUSPEND for a decision "
                            "instead of terminating as QUERY.")
    if st.button("Run batch", type="primary", use_container_width=True):
        with st.spinner("Processing payments…"):
            st.session_state.result = run_batch(db_path=DB, hitl=hitl)
            st.session_state.resumed = {}
    st.divider()
    st.caption(f"Checkpoint store\n\n`{Path(DB).name}`")
    st.caption("Each payment has its own `thread_id`. A shared one would mean "
               "resuming one transaction resumes whichever ran last.")

result = st.session_state.result
if result is None:
    st.info("Run a batch from the sidebar to populate the queues.")
    st.stop()

# --- headline metrics -------------------------------------------------------
outcomes = result.outcomes
closed = [o for o in outcomes if o["end_state"] == "CLOSED"]
awaiting = [o for o in outcomes if o["end_state"] == "AWAITING_HUMAN"]
coded = [o for o in outcomes if o.get("reason_code") not in (None, "-", "UNKNOWN")]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Transactions", result.total)
c2.metric("Straight-through", f"{len(closed) / max(result.total, 1):.0%}",
          f"{len(closed)} closed, no human")
c3.metric("Coded & routed", f"{len(coded) / max(result.total, 1):.0%}",
          f"{len(coded)} with an owner and SLA", delta_color="off")
c4.metric("Awaiting decision", len(awaiting),
          "suspended mid-graph" if awaiting else None, delta_color="off")

st.info(
    "**Straight-through and coded-and-routed are different numbers.** A coded "
    "`PARTIAL_MATCH` with an owner and an SLA is a work item; an uncoded one is a "
    "research project. Both count identically in a straight-through metric — which "
    "is why that metric alone understates what the deduction engine is worth."
)

tab_queues, tab_decide, tab_detail, tab_accept = st.tabs(
    ["Queues", "Decide", "Transaction detail", "Acceptance criteria"])

# --------------------------------------------------------------- Queues ----
with tab_queues:
    frame = pd.DataFrame([{
        "Txn": o["txn_id"],
        "End state": o["end_state"],
        "Owner": o.get("owner") or END_STATE_OWNER.get(o["end_state"], "-"),
        "Invoice": o.get("matched_invoice") or "—",
        "Priority": o.get("matched_priority") or "",
        "Variance": o.get("variance_usd") or 0.0,
        "Code": o.get("reason_code") or "—",
        "Dispute": o.get("dispute_id") or "—",
        "Flags": o.get("security_flags", 0),
    } for o in outcomes])

    def shade(row: pd.Series) -> list[str]:
        return [f"background-color: {STATE_COLOUR.get(row['End state'], '#FFFFFF')}22"] * len(row)

    st.dataframe(frame.style.apply(shade, axis=1).format({"Variance": "${:,.2f}"}),
                 use_container_width=True, hide_index=True)

    left, right = st.columns([2, 3])
    with left:
        st.subheader("Queue depth by owner")
        st.bar_chart(frame["Owner"].value_counts(), color=DEEP)
    with right:
        st.subheader("Who does what next")
        st.markdown("""
| End state | Owner | Next action |
|---|---|---|
| `CLOSED` | — | nothing; settled |
| `PARTIAL_MATCH` | Deductions team per code | validate the claim, issue or reject a credit |
| `AWAITING_HUMAN` | Deductions analyst | **decide here** — the graph resumes |
| `QUERY` | Review queue | judgement call |
| `UAC` | Cash Application | chase the customer for an allocation |
| `UIC` | Treasury | investigate with the bank before anything posts |
| `REJECTED_SECURITY_HOLD` | Security review | assess the blocked document |
""")
        st.warning(
            "**BNK-1010 is an overpayment** and **BNK-1008 settles two invoices with "
            "one payment.** Neither has a defined end state in the source specification "
            "(gaps S1 and S3). Both route to `QUERY` rather than being forced into an "
            "ill-fitting state. These are client decisions, not implementation details."
        )

# --------------------------------------------------------------- Decide ----
with tab_decide:
    st.subheader("Suspended transactions")
    threads = [o["thread_id"] for o in awaiting]

    if not threads:
        st.success("Nothing awaiting a decision. Enable human-in-the-loop and re-run "
                   "to see a suspension.")
    else:
        items = list(pending(DB, threads))
        for item in items:
            state = item["state"]
            txn = state.get("txn_id", "?")
            with st.container(border=True):
                a, b = st.columns([3, 2])
                with a:
                    st.markdown(f"### {txn}")
                    st.markdown(f"""
- **Waiting on:** `{', '.join(item['waiting_on'])}`
- **Invoice:** {state.get('matched_invoice', '—')}
- **Variance:** ${state.get('variance_usd', 0):,.2f}
- **Model's reason code:** `{state.get('reason_code', 'UNKNOWN')}`
  (confidence {state.get('reason_confidence', 0):.2f})
""")
                    st.caption("Evidence on file")
                    st.code(state.get("reason_evidence") or
                            (state.get("remittance_text") or "(none on file)")[:400],
                            language="text")

                with b:
                    action = st.selectbox(
                        "Action", ["assign_code", "reject_deduction", "escalate"],
                        key=f"act-{txn}")
                    codes = load_deduction_codes()
                    reason = st.selectbox(
                        "Reason code", list(codes), key=f"code-{txn}",
                        format_func=lambda c: f"{c} — {codes[c].category}",
                        disabled=action != "assign_code")
                    who = st.text_input("Your name", key=f"who-{txn}",
                                        placeholder="required — attribution is not optional")
                    why = st.text_area("Rationale", key=f"why-{txn}", height=80,
                                       placeholder="required — a human decision explains itself")

                    if st.button("Submit decision", key=f"go-{txn}",
                                 type="primary", use_container_width=True):
                        if not who.strip() or not why.strip():
                            st.error("Name and rationale are both required. "
                                     "\"A human approved it\" is not an audit trail.")
                        else:
                            decision = {"action": action, "decided_by": who.strip(),
                                        "rationale": why.strip()}
                            if action == "assign_code":
                                decision["reason_code"] = reason
                            with st.spinner("Resuming the graph…"):
                                final = resume_transaction(item["thread_id"],
                                                           decision, db_path=DB)
                            st.session_state.resumed[txn] = final
                            st.success(f"{txn} resumed → **{final.get('end_state')}** "
                                       f"(owner {final.get('owner', '-')})")

            if txn in st.session_state.resumed:
                final = st.session_state.resumed[txn]
                with st.expander(f"{txn} — trace after resume", expanded=True):
                    for i, line in enumerate(final.get("trace", []), 1):
                        st.markdown(f"**{i}.** {line}")

# ---------------------------------------------------- Transaction detail ---
with tab_detail:
    pick = st.selectbox("Transaction", [o["txn_id"] for o in outcomes])
    chosen = next(o for o in outcomes if o["txn_id"] == pick)
    resumed = st.session_state.resumed.get(pick)

    a, b = st.columns([2, 3])
    with a:
        st.markdown("#### Outcome")
        st.markdown(f"""
- **End state:** `{(resumed or chosen).get('end_state', chosen['end_state'])}`
- **Owner:** {(resumed or chosen).get('owner', chosen.get('owner', '—'))}
- **Matched invoice:** {chosen.get('matched_invoice', '—')}
- **Priority rule:** {chosen.get('matched_priority') or '— none —'}
- **Variance:** ${chosen.get('variance_usd') or 0:,.2f}
- **Reason code:** `{chosen.get('reason_code') or '—'}`
- **Dispute:** {chosen.get('dispute_id') or '—'}
- **Thread:** `{chosen.get('thread_id', '—')}`
""")
    with b:
        st.markdown("#### State transition trail")
        st.caption("Produced by the graph, not by a developer remembering to log. "
                   "This is what an auditor reads.")
        trace = (resumed or chosen).get("trace", chosen.get("trace", []))
        for i, line in enumerate(trace, 1):
            st.markdown(f"**{i}.** {line}")
        if not trace:
            st.caption("No trace — this transaction is still suspended.")

# --------------------------------------------------- Acceptance criteria ---
with tab_accept:
    st.subheader("The seven acceptance criteria")
    st.caption("Declared on Capstone deck slide 5, before the build. "
               "Run `python3 Capstone/tests/test_acceptance.py` for the executable suite.")
    st.markdown("""
| # | Criterion | Evidence required |
|---|---|---|
| 1 | All six priority rules implemented and evaluated in order | unit tests per rule; matched priority recorded in state |
| 2 | Every transaction terminates in a declared end state | no transaction finishes as `OPEN`; distribution reported |
| 3 | Deduction reasons grounded in verbatim evidence | citation check passes; `UNKNOWN` where no reason is stated |
| 4 | No write executes without graph authorisation | audit ledger **shows refused writes** |
| 5 | A run survives process death and resumes | kill mid-batch; resume; no duplicate ERP postings |
| 6 | `QUERY` suspends and resumes on human input | analyst decision recorded; graph continues from the same state |
| 7 | Any single payment reconstructable from the log alone | `run_id` trace: rule fired, evidence chunk, model output, outcome |
""")
    st.info(
        "**Criterion 4's evidence is not \"no unauthorised write succeeded\".** It is "
        "\"the audit ledger *shows* refused writes\". Absence of evidence is not "
        "evidence of control — if nothing was ever refused, you have demonstrated "
        "that nobody tested it."
    )

st.divider()
st.caption("Accenture Batch 1 · Agentic AI Foundation · Capstone · "
           "Automated Payment & Reconciliation System")
