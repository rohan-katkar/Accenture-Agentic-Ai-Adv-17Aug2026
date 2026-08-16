"""
Capstone/src/pipeline.py
========================
The unified reconciliation workflow: Capstone 01 (configurable rule engine) and
Capstone 02 (deduction identification and cash application) as one graph.

    START -> ingest -> retrieve -> input_guardrail
                                      |
                    +-----------------+------------------+
                 block                flag              clear
                    |                  |                 |
             security_hold             +---> rule_engine <+
                    |                              |
                    |                    matched / exception
                    |                        |         |
                    |               variance_analysis  classify_exception
                    |                        |               |
                    |     closed / tolerance / short / over  |
                    |         |       |        |       |     |
                    |       close  tolerance   |   overpayment
                    |                          |
                    |                 classify_deduction
                    |                          |
                    |                  output_guardrail
                    |                          |
                    |              dispute / query / human_review
                    |                    |       |        |
                    |            open_dispute  query  (interrupt -> resume)
                    +--------------------+-------+--------+
                                         |
                                     finalise -> END

Two things distinguish this from the Day 3 graph:
  * a CHECKPOINTER, so a run survives process death        (criterion 5)
  * a HUMAN_REVIEW interrupt node, so QUERY resumes        (criterion 6)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from shared.config import settings
from shared.foundry_client import get_chat_client, parse_json_loose
from shared.telemetry import get_logger, log_event, trace_node

from .domain import (
    END_STATE_OWNER, TOLERANCE_USD, OpenItem, classify_exception,
    classify_variance, load_deduction_codes, load_open_items, match_payment,
    normalise_customer, parse_remittance_lines,
)
from .security import ToolRegistry, is_blocking, redact, scan_input, to_envelope

log = get_logger(__name__)

CONFIDENCE_FLOOR = 0.60           # assumption A-03; see the register
RELEVANCE_THRESHOLD = 0.92        # assumption A-02

AR_OPEN: list[OpenItem] = load_open_items()
CODES = load_deduction_codes()
DISPUTES: list[dict] = []
registry = ToolRegistry()


# ===========================================================================
# Tools
# ===========================================================================
@registry.register(
    name="lookup_open_invoices",
    description="Return open AR invoices for a customer.",
    parameters={"customer_name": "Exact ERP customer name",
                "invoice_no": "Invoice number, or empty string for all"},
    permission="read")
def lookup_open_invoices(customer_name: str, invoice_no: str = "") -> list[dict]:
    hits = [i for i in AR_OPEN if i.customer_name == customer_name]
    if invoice_no:
        hits = [i for i in hits if i.invoice_no == invoice_no]
    return [{"invoice_no": i.invoice_no, "po_number": i.po_number,
             "invoice_date": i.invoice_date, "amount_usd": i.amount_usd} for i in hits]


@registry.register(
    name="create_dispute",
    description="Open a deduction dispute. WRITE OPERATION.",
    parameters={"invoice_no": "Invoice", "amount_usd": "Disputed amount",
                "reason_code": "D01-D05", "evidence": "Verbatim supporting text"},
    permission="write")
def create_dispute(invoice_no: str, amount_usd: str,
                   reason_code: str, evidence: str) -> dict:
    """Idempotent by content-derived key.

    If the process dies after the ERP write but before the state is
    checkpointed, the retry must not create a second dispute. This is the
    at-least-once delivery problem and it is not hypothetical in a nightly batch
    that can be re-run.
    """
    key = f"{invoice_no}:{reason_code}:{float(amount_usd):.2f}"
    for existing in DISPUTES:
        if existing["idempotency_key"] == key:
            return {**existing, "created": False, "note": "already exists - no-op"}

    code = CODES.get(reason_code.upper())
    if code is None:
        raise ValueError(f"unknown reason code {reason_code!r}; legal codes are D01-D05")

    record = {
        "dispute_id": f"DSP-{len(DISPUTES) + 1001}", "idempotency_key": key,
        "invoice_no": invoice_no, "amount_usd": round(float(amount_usd), 2),
        "reason_code": code.reason_code, "owning_team": code.owning_team,
        "sla_days": code.sla_days, "evidence": (evidence or "")[:280], "status": "OPEN",
    }
    DISPUTES.append(record)
    return {**record, "created": True}


# ===========================================================================
# State
# ===========================================================================
class ReconciliationState(TypedDict, total=False):
    run_id: str
    txn_id: str
    bank_customer_raw: str
    bank_amount_usd: float
    bank_reference: str
    value_date: str

    remittance_found: bool
    remittance_text: str
    remittance_evidence: list[dict]
    remittance_parsed: dict

    matched_invoice: str
    matched_priority: int
    match_type: str
    erp_amount_usd: float
    variance_usd: float
    variance_class: str

    reason_code: str
    reason_confidence: float
    reason_evidence: str

    security_flags: Annotated[list[dict], operator.add]
    security_blocked: bool

    decided_by: str
    decision_rationale: str
    decision_action: str

    dispute_id: str
    dispute_usd: float
    write_off_usd: float
    end_state: Literal["OPEN", "PARTIAL_MATCH", "CLOSED", "UAC", "UIC",
                       "QUERY", "REJECTED_SECURITY_HOLD"]
    owner: str
    requires_human: bool

    trace: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

    # Routing switch. When no checkpointer is attached, interrupt() has nowhere
    # to persist, so route_on_confidence sends QUERY to a terminal node instead
    # of the human_review interrupt. Declared here because LangGraph drops keys
    # that are not part of the schema.
    _hitl_enabled: bool


# ===========================================================================
# Retrieval
# ===========================================================================
def _retrieve(txn_id: str, query: str) -> list[dict]:
    """Filtered, distance-gated retrieval. Empty list means NO EVIDENCE."""
    try:
        from shared.foundry_client import get_embedder
        from shared.vectorstore import get_collection

        collection = get_collection("remittance_advice")
        if collection.count() == 0:
            return []
        embed = get_embedder()
        res = collection.query(query_embeddings=embed([query]),
                               n_results=3, where={"txn_id": txn_id})
        return [{"chunk_id": cid, "text": doc, "distance": round(dist, 4)}
                for cid, doc, dist in zip(res["ids"][0], res["documents"][0],
                                          res["distances"][0])
                if dist <= RELEVANCE_THRESHOLD]
    except Exception as exc:  # noqa: BLE001 - retrieval is best-effort
        log_event(log, "retrieval_failed", level=30, txn_id=txn_id, error=str(exc))
        return []


# ===========================================================================
# Nodes
# ===========================================================================
def node_ingest(state: ReconciliationState) -> dict:
    customer = normalise_customer(state.get("bank_customer_raw", ""))
    return {"end_state": "OPEN", "requires_human": False,
            "trace": [f"ingest: {state['txn_id']} {state.get('bank_amount_usd', 0):,.2f} "
                      f"from {customer or '<unknown sender>'}"]}


def node_retrieve(state: ReconciliationState) -> dict:
    """Retrieve remittance evidence, or accept a supplied document.

    `remittance_text` set by the caller is honoured. That is how a batch feeds a
    document it already has, and how the acceptance suite injects a payload
    without polluting the shared vector corpus.
    """
    txn_id = state.get("txn_id", "-")
    supplied = state.get("remittance_text")
    if supplied:
        return {"remittance_found": True,
                "remittance_parsed": {"invoices": parse_remittance_lines(supplied)},
                "remittance_evidence": [{"chunk_id": "supplied", "text": supplied,
                                         "distance": 0.0}],
                "trace": ["retrieve: remittance supplied by the caller"]}

    variance_hint = state.get("variance_usd", 0.0)
    query = ("reason the customer withheld or deducted part of the payment"
             if variance_hint < 0 else
             "invoice numbers and amounts covered by this payment")
    chunks = _retrieve(txn_id, query)
    if not chunks:
        return {"remittance_found": False, "remittance_evidence": [],
                "trace": [f"retrieve: no chunk within {RELEVANCE_THRESHOLD} for {txn_id}"]}

    text = "\n\n---\n\n".join(c["text"] for c in chunks)
    return {"remittance_found": True, "remittance_text": text,
            "remittance_evidence": chunks,
            "remittance_parsed": {"invoices": parse_remittance_lines(text)},
            "trace": [f"retrieve: {len(chunks)} chunk(s), best distance {chunks[0]['distance']}"]}


def node_input_guardrail(state: ReconciliationState) -> dict:
    text = state.get("remittance_text", "") or ""
    if not text:
        return {"trace": ["input_guardrail: no remittance text to scan"]}
    findings = scan_input(text, source=state.get("txn_id", "-"))
    blocked = is_blocking(findings)
    return {"security_flags": [f.as_dict() for f in findings], "security_blocked": blocked,
            "trace": [f"input_guardrail: {len(findings)} finding(s), "
                      f"{'BLOCKED' if blocked else 'flagged' if findings else 'clear'}"]}


def node_security_hold(state: ReconciliationState) -> dict:
    blocking = [f for f in state.get("security_flags", []) if f.get("severity") == "block"]
    return {"end_state": "REJECTED_SECURITY_HOLD", "requires_human": True,
            "owner": END_STATE_OWNER["REJECTED_SECURITY_HOLD"],
            "trace": [f"security_hold: BLOCKED by {', '.join(f['control'] for f in blocking)}. "
                      "No model call was made, no write was attempted."]}


def node_flagged(state: ReconciliationState) -> dict:
    controls = ", ".join(f["control"] for f in state.get("security_flags", []))
    return {"requires_human": True,
            "trace": [f"flagged: proceeding under review — {controls}"]}


def node_rule_engine(state: ReconciliationState) -> dict:
    with trace_node(log, "rule_engine", state.get("run_id", "-"),
                    txn_id=state.get("txn_id")) as out:
        result = match_payment(state.get("bank_customer_raw", ""),
                               state.get("bank_reference", ""),
                               state.get("remittance_text", ""), AR_OPEN)
        if result is None:
            out["priority"] = 0
            return {"matched_priority": 0, "match_type": "none",
                    "trace": ["rule_engine: no priority rule matched"]}
        variance = round(state.get("bank_amount_usd", 0.0) - result.erp_amount_usd, 2)
        out["priority"], out["invoice"] = result.priority, result.invoice_no
        return {"matched_invoice": result.invoice_no, "matched_priority": result.priority,
                "match_type": result.match_type, "erp_amount_usd": result.erp_amount_usd,
                "variance_usd": variance,
                "trace": [f"rule_engine: priority {result.priority} — {result.rationale}"]}


def node_variance(state: ReconciliationState) -> dict:
    variance, kind = classify_variance(state.get("bank_amount_usd", 0.0),
                                       state.get("erp_amount_usd", 0.0))
    note = {"exact": "exact match",
            "within_tolerance": f"within {TOLERANCE_USD:,.2f} tolerance",
            "short_payment": f"short payment of {abs(variance):,.2f}",
            "overpayment": f"OVERPAYMENT of {variance:,.2f} — gap S1, no end state defined"}[kind]
    return {"variance_class": kind, "trace": [f"variance_analysis: {note}"]}


GROUNDED_SYSTEM = """You are an accounts receivable deduction classifier.

Use ONLY the REMITTANCE EVIDENCE provided. The "evidence" field must be a
VERBATIM substring copied from it. If the evidence states no reason, return
reason_code "UNKNOWN" with confidence 0.0 and an empty evidence string - UNKNOWN
is a correct and valuable answer. Never return a code outside:
  D01 Pricing Issue  D02 Freight Claim  D03 Damage Claim
  D04 Tax Difference D05 Discount Taken

Return one JSON object with keys: reason_code, category, confidence, evidence."""


def node_classify_deduction(state: ReconciliationState) -> dict:
    """Grounded extraction. Fails SAFE to UNKNOWN rather than raising."""
    evidence_text = state.get("remittance_text", "") or ""
    if not evidence_text:
        return {"reason_code": "UNKNOWN", "reason_confidence": 0.0,
                "trace": ["classify_deduction: no evidence — cannot classify"]}

    try:
        from pydantic import BaseModel, Field, ValidationError, field_validator

        class Finding(BaseModel):
            reason_code: Literal["D01", "D02", "D03", "D04", "D05", "UNKNOWN"]
            category: str = Field(min_length=2, max_length=60)
            confidence: float = Field(ge=0.0, le=1.0)
            evidence: str = Field(default="", max_length=400)

            @field_validator("category")
            @classmethod
            def not_placeholder(cls, v: str) -> str:
                if v.strip().lower() in {"n/a", "none", "-"}:
                    raise ValueError("category must be a real classification")
                return v.strip()

        client = get_chat_client()
        raw = client.complete(GROUNDED_SYSTEM,
                              f'REMITTANCE EVIDENCE:\n"""\n{evidence_text}\n"""',
                              temperature=0.0)
        finding = Finding.model_validate(parse_json_loose(raw))

        # Grounding: a citation must appear verbatim in the source.
        if finding.reason_code != "UNKNOWN":
            needle = " ".join(finding.evidence.split()).lower()
            haystack = " ".join(evidence_text.split()).lower()
            if not needle or needle not in haystack:
                raise ValueError("evidence is not a verbatim quote from the source")

        return {"reason_code": finding.reason_code,
                "reason_confidence": finding.confidence,
                "reason_evidence": finding.evidence,
                "trace": [f"classify_deduction: {finding.reason_code} "
                          f"({finding.category}) at confidence {finding.confidence}"]}

    except (ValidationError, ValueError) as exc:
        log_event(log, "classification_rejected", level=30,
                  txn_id=state.get("txn_id"), problem=str(exc)[:160])
        return {"reason_code": "UNKNOWN", "reason_confidence": 0.0, "reason_evidence": "",
                "trace": [f"classify_deduction: rejected ({type(exc).__name__}) "
                          "— failing safe to UNKNOWN"]}
    except Exception as exc:  # noqa: BLE001
        envelope = to_envelope(exc, "UPSTREAM_TIMEOUT")
        return {"reason_code": "UNKNOWN", "reason_confidence": 0.0,
                "errors": [f"{envelope.code}:{envelope.correlation_id}"],
                "trace": [f"classify_deduction: upstream error "
                          f"{envelope.correlation_id} — failing safe to UNKNOWN"]}


def node_output_guardrail(state: ReconciliationState) -> dict:
    evidence = state.get("reason_evidence", "") or ""
    if not evidence:
        return {"trace": ["output_guardrail: nothing to sanitise"]}
    clean, inventory = redact(evidence)
    flags = [{"control": f"redaction:{i['rule']}", "severity": "flag",
              "detail": f"{i['count']} {i['cls']} match(es) masked",
              "node": "output_guardrail"} for i in inventory]
    return {"reason_evidence": clean, "security_flags": flags,
            "trace": [f"output_guardrail: {sum(i['count'] for i in inventory)} item(s) masked"
                      if inventory else "output_guardrail: clean"]}


def node_open_dispute(state: ReconciliationState) -> dict:
    """WRITE. Authorised by the GRAPH, never chosen by the model."""
    shortfall = abs(state.get("variance_usd", 0.0))
    envelope = registry.invoke("create_dispute", {
        "invoice_no": state.get("matched_invoice", ""),
        "amount_usd": f"{shortfall:.2f}",
        "reason_code": state.get("reason_code", "UNKNOWN"),
        "evidence": state.get("reason_evidence", ""),
    }, allow_write=True, run_id=state.get("run_id", "-"))

    if not envelope["ok"]:
        return {"end_state": "QUERY", "requires_human": True,
                "owner": END_STATE_OWNER["QUERY"],
                "errors": [f"dispute creation failed: {envelope['error']}"],
                "trace": [f"open_dispute: FAILED — {envelope['error']} — routed to QUERY"]}

    rec = envelope["result"]
    return {"end_state": "PARTIAL_MATCH", "dispute_id": rec["dispute_id"],
            "dispute_usd": rec["amount_usd"], "requires_human": False,
            "owner": rec["owning_team"],
            "trace": [f"open_dispute: {rec['dispute_id']} for {rec['amount_usd']:,.2f} "
                      f"code {rec['reason_code']} → {rec['owning_team']} "
                      f"(SLA {rec['sla_days']}d)"]}


def node_human_review(state: ReconciliationState) -> dict:
    """SUSPEND for an analyst decision, then resume from this exact line.

    interrupt() does not block a thread. It persists state and returns control.
    The analyst may respond in four minutes or four days.
    """
    from langgraph.types import interrupt

    decision = interrupt({
        "txn_id": state.get("txn_id"),
        "variance_usd": state.get("variance_usd"),
        "matched_invoice": state.get("matched_invoice"),
        "reason_evidence": state.get("reason_evidence") or "(none on file)",
        "security_flags": state.get("security_flags", []),
        "ask": "Assign a deduction reason code, reject the deduction, or escalate.",
        "options": ["assign_code", "reject_deduction", "escalate"],
    })

    action = decision.get("action", "escalate")
    log_event(log, "human_decision", txn_id=state.get("txn_id"), action=action,
              decided_by=decision.get("decided_by"))
    return {"decision_action": action,
            "decided_by": decision.get("decided_by", "unknown"),
            "decision_rationale": decision.get("rationale", ""),
            "reason_code": decision.get("reason_code", state.get("reason_code", "UNKNOWN")),
            "requires_human": False,
            "trace": [f"human_review: {action} by {decision.get('decided_by', 'unknown')} "
                      f"— {decision.get('rationale', 'no rationale given')}"]}


def node_apply_human_code(state: ReconciliationState) -> dict:
    return node_open_dispute(state)


def node_reject_deduction(state: ReconciliationState) -> dict:
    return {"end_state": "CLOSED", "requires_human": False, "owner": "-",
            "write_off_usd": round(abs(state.get("variance_usd", 0.0)), 2),
            "trace": ["reject_deduction: deduction rejected by analyst, balance written back"]}


def node_close(state: ReconciliationState) -> dict:  # noqa: ARG001
    return {"end_state": "CLOSED", "requires_human": False, "owner": "-",
            "trace": ["close: fully applied, invoice closed"]}


def node_tolerance(state: ReconciliationState) -> dict:
    amount = abs(state.get("variance_usd", 0.0))
    return {"end_state": "CLOSED", "requires_human": False, "owner": "-",
            "write_off_usd": round(amount, 2),
            "trace": [f"tolerance: {amount:,.2f} auto-written off"]}


def node_overpayment(state: ReconciliationState) -> dict:
    return {"end_state": "QUERY", "requires_human": True, "owner": END_STATE_OWNER["QUERY"],
            "trace": [f"overpayment: {state.get('variance_usd', 0):,.2f} above invoice value. "
                      "SPECIFICATION GAP S1 — no end state defined. Routed to QUERY."]}


def node_exception(state: ReconciliationState) -> dict:
    kind = classify_exception(state.get("bank_customer_raw", ""))
    return {"end_state": kind, "requires_human": True, "owner": END_STATE_OWNER[kind],
            "trace": [f"exception: {'payer identified, no invoice reference' if kind == 'UAC' else 'payer not identifiable'} → {kind}"]}


def node_finalise(state: ReconciliationState) -> dict:
    end_state = state.get("end_state", "OPEN")
    return {"owner": state.get("owner") or END_STATE_OWNER.get(end_state, "-"),
            "trace": [f"finalise: {end_state} · owner "
                      f"{state.get('owner') or END_STATE_OWNER.get(end_state, '-')} · "
                      f"{len(state.get('security_flags', []))} security finding(s)"]}


# ===========================================================================
# Routers
# ===========================================================================
def route_security(state: ReconciliationState) -> str:
    flags = state.get("security_flags", [])
    if is_blocking(flags):
        return "security_hold"
    return "flagged" if flags else "clear"


def route_after_matching(state: ReconciliationState) -> str:
    return "matched" if state.get("matched_priority") else "exception"


def route_after_variance(state: ReconciliationState) -> str:
    return {"exact": "closed", "within_tolerance": "tolerance",
            "short_payment": "short_payment",
            "overpayment": "overpayment"}[state.get("variance_class", "exact")]


def route_on_confidence(state: ReconciliationState) -> str:
    """Coded and confident -> post. Otherwise a human decides.

    `human_review` is reachable only when a checkpointer is attached, because
    interrupt() needs somewhere to persist. Without one, we route to a terminal
    QUERY instead of failing at runtime.
    """
    code = state.get("reason_code", "UNKNOWN")
    if code != "UNKNOWN" and state.get("reason_confidence", 0.0) >= CONFIDENCE_FLOOR:
        return "dispute"
    return "human_review" if state.get("_hitl_enabled") else "query"


def node_query(state: ReconciliationState) -> dict:
    why = ("no reason stated in the remittance" if state.get("reason_code") == "UNKNOWN"
           else f"confidence {state.get('reason_confidence', 0):.2f} below {CONFIDENCE_FLOOR}")
    return {"end_state": "QUERY", "requires_human": True, "owner": END_STATE_OWNER["QUERY"],
            "trace": [f"query: human review required — {why}"]}


def route_human_decision(state: ReconciliationState) -> str:
    return state.get("decision_action", "escalate")


# ===========================================================================
# Build
# ===========================================================================
def _add_node_checked(builder: StateGraph, name: str, fn) -> None:
    """add_node with a guard against the node-name / state-key collision.

    LangGraph keys nodes and state fields in the same namespace. Newer versions
    raise `ValueError: '<name>' is already being used as a state key`; older
    versions accept it SILENTLY, so the same code works on one machine and fails
    on another. Check explicitly rather than depending on the installed version.

    Convention: a NODE is an action (`security_hold`); a STATE FIELD is a fact
    (`security_blocked`).
    """
    if name in set(ReconciliationState.__annotations__):
        raise ValueError(
            f"node name {name!r} collides with a state key of the same name. "
            "Rename one - nodes are actions, state fields are facts."
        )
    builder.add_node(name, fn)


def build_pipeline(checkpointer: Any | None = None):
    """Compile the workflow. Pass a checkpointer to enable durability and HITL."""
    b = StateGraph(ReconciliationState)

    for name, fn in [
        ("ingest", node_ingest), ("retrieve", node_retrieve),
        ("input_guardrail", node_input_guardrail), ("security_hold", node_security_hold),
        ("flagged", node_flagged), ("rule_engine", node_rule_engine),
        ("variance_analysis", node_variance), ("classify_deduction", node_classify_deduction),
        ("output_guardrail", node_output_guardrail), ("open_dispute", node_open_dispute),
        ("human_review", node_human_review), ("apply_human_code", node_apply_human_code),
        ("reject_deduction", node_reject_deduction), ("query", node_query),
        ("close", node_close), ("tolerance", node_tolerance),
        ("overpayment", node_overpayment), ("classify_exception", node_exception),
        ("finalise", node_finalise),
    ]:
        _add_node_checked(b, name, fn)

    b.add_edge(START, "ingest")
    b.add_edge("ingest", "retrieve")
    b.add_edge("retrieve", "input_guardrail")
    b.add_conditional_edges("input_guardrail", route_security,
                            {"security_hold": "security_hold", "flagged": "flagged",
                             "clear": "rule_engine"})
    b.add_edge("flagged", "rule_engine")
    b.add_edge("security_hold", "finalise")
    b.add_conditional_edges("rule_engine", route_after_matching,
                            {"matched": "variance_analysis", "exception": "classify_exception"})
    b.add_conditional_edges("variance_analysis", route_after_variance,
                            {"closed": "close", "tolerance": "tolerance",
                             "short_payment": "classify_deduction",
                             "overpayment": "overpayment"})
    b.add_edge("classify_deduction", "output_guardrail")
    b.add_conditional_edges("output_guardrail", route_on_confidence,
                            {"dispute": "open_dispute", "query": "query",
                             "human_review": "human_review"})
    b.add_conditional_edges("human_review", route_human_decision,
                            {"assign_code": "apply_human_code",
                             "reject_deduction": "reject_deduction",
                             "escalate": "query"})
    for terminal in ("close", "tolerance", "open_dispute", "apply_human_code",
                     "reject_deduction", "query", "overpayment", "classify_exception"):
        b.add_edge(terminal, "finalise")
    b.add_edge("finalise", END)

    return b.compile(checkpointer=checkpointer) if checkpointer else b.compile()


def initial_state(txn: Any, *, run_id: str, hitl: bool = False,
                  remittance_text: str | None = None) -> ReconciliationState:
    state: ReconciliationState = {
        "run_id": run_id, "txn_id": txn.txn_id,
        "bank_customer_raw": txn.customer_name_raw,
        "bank_amount_usd": txn.amount_usd,
        "bank_reference": txn.reference_text,
        "value_date": txn.value_date,
        "trace": [], "errors": [], "security_flags": [],
    }
    if remittance_text:
        state["remittance_text"] = remittance_text
    if hitl:
        state["_hitl_enabled"] = True
    return state
