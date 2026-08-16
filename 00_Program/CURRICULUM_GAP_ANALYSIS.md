# Curriculum & Specification Gap Analysis

**Source reviewed:** `Accenture_Batch_1_Detailed.pdf` (Days 1–3 + unified Capstone 01/02)
**Reviewed against:** what the Capstone actually requires to be buildable.

Two categories. **S-gaps** are ambiguities or omissions in the client's business
specification — the client decides, we do not invent. **G-gaps** are things the
Capstone needs that no Day 1–3 lab teaches — ours to fix.

---

## S-gaps — business specification

### S1 · No end state for an overpayment · SEVERITY: HIGH

The six end states cover exact match, variance, unapplied and unidentified cash.
None describes a payment **exceeding** the invoice value.

- Not `PARTIAL_MATCH` — that describes a shortfall.
- Not `CLOSED` — the excess is unapplied.
- Not `UAC` — the payer and the invoice are both known.

**In the build:** seed transaction `BNK-1010` pays \$12,000 against an \$11,000
invoice, deliberately, to surface this. It is routed to `QUERY` and the trace
says `SPECIFICATION GAP` in plain text.

**Recommendation:** ask the client whether they want a seventh state
(`OVERPAYMENT` / `UNAPPLIED_CREDIT`) or a documented rule folding it into `UAC`.
Either is defensible. Silently choosing one is not.

---

### S2 · `UAC` is defined two different ways in the same document · SEVERITY: MEDIUM

| Location | Test implied |
|---|---|
| End-state table, row 4 | "No invoice details in Bank Statement **and** No Remittance Advice" |
| Example D, Case 1 | "Customer identified, invoice unknown" |

These are different tests. A payment from a known customer *with* a remittance
that lacks invoice detail satisfies the second and fails the first.

**In the build:** we implement the **Example D** reading — payer-identifiability
is the operationally useful test, because it decides whether Cash Application or
Treasury owns the item. Documented in `route_exception_type()` and flagged on
Day 1 slide 6.

---

### S3 · One-to-many cash application is undefined · SEVERITY: HIGH

The six priority rules are written as one-payment-to-one-invoice. Real remittances
frequently settle several invoices with one transfer.

**In the build:** `BNK-1008` remits \$15,000 covering `INV-1102` (\$9,000) and
`INV-1103` (\$6,000). The 3-way rule fires correctly at priority 5, matches the
first invoice, and then computes a \$6,000 "overpayment" — because the rule has no
concept of split application. Surfaced explicitly in Day 2 Lab 5, Step 7.

**Recommendation:** split application needs its own state fields
(`applications: list[{invoice_no, applied_usd}]`) and its own end state, or an
explicit client decision to exclude it from scope. This was found in week one at
zero cost; found in UAT it is a re-architecture.

---

### S4 · No currency or FX handling · SEVERITY: MEDIUM

Every amount in the specification is USD. Multi-currency AR needs a rate source,
a rate date convention, and an FX-variance treatment distinct from a deduction.

**In the build:** not implemented. Raised as a Day 1 Lab 5 stretch goal
(`node_currency_check`) so learners see where it would attach.

---

### S5 · No idempotency or replay position · SEVERITY: HIGH (operational)

Nothing in the specification says what happens when a nightly batch is re-run, or
when a process dies after posting to the ERP but before the state is recorded.

**In the build:** `create_dispute` carries a content-derived idempotency key and
Day 2 Lab 2 proves that two identical authorised writes produce one dispute.
Day 2 Lab 1 proves ingestion is idempotent for the same reason.

---

## G-gaps — curriculum

### G1 · Structured-output validation is never taught · SEVERITY: HIGH · **CLOSED**

Days 1–3 as scoped parse model JSON defensively. Parsing is not validating:
`json.loads` accepts `{"reason_code": "D99", "confidence": "very high"}`.

**Remediation shipped:** Day 2 Lab 4 replaces `complete_json()` with a Pydantic
`DeductionFinding` contract plus a verbatim-substring grounding check. Five real
failure payloads are rejected in front of the class before the model is trusted.

---

### G2 · MCP tools are in the architecture but in no lab · SEVERITY: MEDIUM · **PARTIALLY CLOSED**

The Capstone stack names Model Context Protocol tools for ERP and ledger access.
No Day 1–3 lab teaches them.

**Remediation shipped:** Day 2 Lab 2 builds the *concept* end to end — a tool
registry with typed schemas, a read/write permission model, refusal of
unauthorised writes, refusal of hallucinated tool names, and a per-invocation
audit ledger. `registry.catalogue()` emits the exact schema shape a
function-calling API expects.

**Still open:** an actual MCP server/client transport lab. Recommend a 45-minute
addition to Day 3, or an explicit statement to the client that MCP is
architectural context rather than a hands-on outcome.

---

### G3 · Human-in-the-loop is required by the Capstone and taught nowhere · SEVERITY: HIGH · **OPEN**

The `QUERY` end state is defined as "user queried for more information". Making a
graph *actually* suspend, persist, and resume on human input requires LangGraph's
`interrupt` plus a checkpointer. Neither appears in any Day 1–3 lab as scoped.

**Partially mitigated:** Day 1 Lab 5 includes a checkpointer stretch goal, and
`verify_environment.py` checks that `langgraph.types.interrupt` is importable and
warns if not. `langgraph-checkpoint-sqlite` is pinned in `requirements.txt`.

**Recommendation:** a dedicated 50-minute lab. Without it, learners reach the
Capstone able to *route* to `QUERY` but not to *resume* from it, which means the
Capstone's own architecture diagram cannot be implemented as drawn. **This is the
highest-priority remaining gap.**

---

### G4 · Scaffolding jump from Day 2 Lab 5 to the Capstone · SEVERITY: MEDIUM · **OPEN**

Day 2 Lab 5 ends with a 13-node graph over 10 transactions in memory. The Capstone
expects a deployable service with persistence, batch handling, and a review UI.

**Partially mitigated:** the Streamlit consoles give learners a working UI pattern,
and the tool registry gives a persistence seam.

**Recommendation:** a short bridging lab covering batch orchestration and durable
state, or an explicit scoping statement that the Capstone is delivered as a guided
build rather than an independent one.

---

## Priority order for remediation

| Rank | Gap | Effort | Consequence if left |
|---|---|---|---|
| 1 | **G3** human-in-the-loop | ~50 min lab | Capstone architecture is not implementable as drawn |
| 2 | **S3** one-to-many application | client decision + ~2h build | Silent mis-posting on real remittances |
| 3 | **S1** overpayment end state | client decision | Undefined behaviour on a common real case |
| 4 | **G4** capstone scaffolding | ~40 min bridging lab | Capstone-day time overrun |
| 5 | **G2** real MCP transport | ~45 min lab | Architecture claim unsupported by hands-on work |
| 6 | **S4** currency / FX | scoping decision | Blocks multi-region rollout only |
