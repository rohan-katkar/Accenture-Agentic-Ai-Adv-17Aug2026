# Capstone Build Guide — Automated Payment & Reconciliation System

**Duration:** one day (approximately 6 hours including review)
**Prerequisites:** Days 1–3 complete, including **Day 3 Lab 6** (human-in-the-loop)

---

## 1. What you are building

One deployable workflow that unifies **Capstone 01** (configurable rule engine)
and **Capstone 02** (deduction identification and cash application).

Nothing here is new. You have written every component. The capstone is assembly
plus two additions that a demo does not need and a deployment does:

| Addition | Mechanism | Unblocks |
|---|---|---|
| Survive process death | a **checkpointer** persists state after every node | criterion 5 |
| Suspend for a human, then resume | `interrupt()` and `Command(resume=…)` | criterion 6 |

---

## 2. Package layout

```
Capstone/
├── src/
│   ├── domain.py      end states, ledgers, priority rules 1–6, variance logic
│   ├── security.py    input gate, output redaction, error envelopes, tool registry
│   ├── pipeline.py    the 19-node graph, HITL interrupt, checkpointing
│   ├── batch.py       batch orchestration, resume, export
│   └── cli.py         command-line entrypoint
├── tests/
│   └── test_acceptance.py   the seven criteria, executable
├── webapp/
│   └── app_analyst_console.py
└── docs/
    └── BUILD_GUIDE.md  (this file)
```

### Why `src/` is a package and not an import of the lab files

The labs are **teaching scripts**: they print, they assert, they narrate.
Importing one executes it. That is correct for a lab and wrong for a deployable
component.

So the Capstone re-expresses the same logic as an importable package. That
introduces a **drift risk** — two copies of the priority rules — and we close it
the only honest way available: **acceptance criterion 2 asserts that the package
reproduces the same ten end states the labs produce.** If the two ever diverge,
the suite fails.

---

## 3. Run it

```bash
# process the batch (QUERY suspends for a human)
python3 -m Capstone.src.cli run

# terminate QUERY instead of suspending
python3 -m Capstone.src.cli run --no-hitl

# resume a batch that died partway
python3 -m Capstone.src.cli run --resume-from BNK-1004

# list suspended transactions
python3 -m Capstone.src.cli pending

# resume one, with attribution
python3 -m Capstone.src.cli resume "<thread_id>" \
    --action assign_code --reason-code D01 \
    --by "J. Okonkwo (Deductions)" \
    --rationale "Customer confirmed a contracted price variance by phone."

# the seven acceptance criteria
python3 Capstone/tests/test_acceptance.py

# the analyst console
streamlit run Capstone/webapp/app_analyst_console.py
```

> **Prerequisite:** run `Day2_RAG/solutions/lab01_vector_ingestion.py` once. It
> builds the remittance corpus the pipeline retrieves from. Without it,
> BNK-1002 loses its reason code and BNK-1008 loses its 3-way match.

---

## 4. The seven acceptance criteria

Declared **before** the build, on slide 5 of the Capstone deck. Declaring the
expectation first is what separates a test from a demo.

| # | Criterion | Evidence required |
|---|---|---|
| 1 | All six priority rules implemented and evaluated in order | unit tests per rule; matched priority recorded in state |
| 2 | Every transaction terminates in a declared end state | no transaction finishes as `OPEN`; distribution reported |
| 3 | Deduction reasons grounded in verbatim evidence | citation check passes; `UNKNOWN` where no reason is stated |
| 4 | No write executes without graph authorisation | audit ledger **shows refused writes** |
| 5 | A run survives process death and resumes | kill mid-batch; resume; no duplicate ERP postings |
| 6 | `QUERY` suspends and resumes on human input | analyst decision recorded; graph continues from the same state |
| 7 | Any single payment reconstructable from the log alone | `run_id` trace: rule fired, evidence chunk, model output, outcome |

**Criterion 4 deserves a second read.** Its evidence is not "no unauthorised
write succeeded". It is "the audit ledger *shows* refused writes". Absence of
evidence is not evidence of control — if nothing was ever refused, you have
demonstrated that nobody tested it.

All seven pass in the packaged build.

---

## 5. Measured results

From a real run of `python3 -m Capstone.src.cli run`:

| Metric | Value |
|---|---|
| Transactions | 10 |
| Straight-through (`CLOSED`, no human) | 4/10 = 40% |
| Requires a human | 6/10 = 60% |
| Failed | 0 |

End-state distribution: `CLOSED` 4 · `PARTIAL_MATCH` 1 · `QUERY` 2 · `UAC` 1 ·
`UIC` 1 · `AWAITING_HUMAN` 1.

These reproduce the frozen Day 1–3 baseline exactly, which is what criterion 2
checks. **Figures were produced on the offline stub with a lexical embedder** —
re-measure on Path A and state the backend alongside any number you publish.

---

## 6. Architecture, layer by layer

| Layer | Component | Job |
|---|---|---|
| Orchestration | LangGraph | control flow, 2-way/3-way branching, `interrupt` for `QUERY` |
| Document intelligence | Azure AI Foundry + Chroma | parse remittance prose, map to D01–D05 with verbatim grounding |
| Integration | tool registry (MCP-shaped) | typed, permissioned calls into ERP data |
| Control | guardrails + observability | block injection, redact output, log refusals |

### The architectural control, stated plainly

**The model cannot authorise a write.** `ToolRegistry.invoke` refuses any `write`
tool unless the caller passes `allow_write=True`, and only the graph does that,
and only from a state that justifies it.

A successful prompt injection therefore corrupts a *recommendation*. It does not
move money, because the model was never holding that authority to give away.
This containment costs nothing at runtime — it was paid for at design time, on
Day 1, by choosing a state machine over an agent that acts.

---

## 7. Open items carried into the capstone

These are **client decisions**, not implementation defects. The system surfaces
each one rather than papering over it.

| ID | Gap | How the build handles it |
|---|---|---|
| **S1** | No end state for an overpayment | BNK-1010 (+$1,000) routes to `QUERY`; the trace says `SPECIFICATION GAP S1` |
| **S3** | One-to-many cash application undefined | BNK-1008 settles two invoices with one payment; priority 5 matches the first and reports a false overpayment |
| **S2** | `UAC` defined two ways in the source | implements the Example D reading (payer identifiability); documented in `classify_exception` |
| **S4** | No currency or FX handling | not implemented; all amounts are USD |

Full detail and remediation priority: `00_Program/CURRICULUM_GAP_ANALYSIS.md`.

---

## 8. Operational realities before you deploy

1. **Latency budget.** Model calls dominate. Measure your endpoint (Day 2 Lab 2),
   multiply by volume and calls-per-payment, and check it fits your batch window
   *before* designing anything else. If it doesn't, the answer is fewer model
   calls, not a faster model.

2. **Partial failure.** A batch that dies at transaction 4,000 must resume, not
   restart — restarting risks re-posting to an ERP. Idempotency keys on
   `create_dispute` make a replay a no-op; criterion 5 proves it.

3. **Queue capacity.** Every `QUERY`, `UAC` and `AWAITING_HUMAN` lands in a human
   queue. If the exception rate exceeds the team's capacity, automation has moved
   the bottleneck rather than removed it. **Model the exception queue before you
   model the happy path** — this is what sinks programmes.

4. **Checkpoint hygiene.** Every checkpoint persists the *whole* state. If
   `remittance_text` holds 40 KB of PDF, that is 40 KB per node per payment. And
   checkpoints contain customer data: they need a retention policy and something
   that deletes them. A checkpoint store with no deletion story is a compliance
   finding that looks like plumbing.

5. **`thread_id` must be unique per payment.** A shared one means resuming one
   transaction resumes whichever ran last — silent, and very unpleasant.

6. **Money is `float` here, `Decimal` in production.** `to_decimal()` exists in
   `domain.py` so the posting layer converts at the boundary. This is a courseware
   simplification, not a design position.

---

## 9. What to report to a steering committee

Three pairs of numbers. Reporting only the left column is how a business case
gets overstated.

| Flattering | Honest partner |
|---|---|
| Match rate — a rule found an invoice | Straight-through — closed with no human |
| Straight-through | Coded & routed — exceptions made actionable |
| Catch rate — attacks blocked | False positives — legitimate items wrongly blocked |

Also report **what the system refused to do**: blocked writes, hallucinated tool
names, held transactions. It is the only direct evidence your controls are live,
and it costs nothing extra — the records are already being written.

And name the baseline. An automation target is a measurement problem before it is
a training outcome; you cannot improve a percentage against a baseline that does
not exist.
