# Advanced Agentic AI on Microsoft Foundry — Lab Steps

Northwind Global Retail — Amazon Settlement & D365 ERP Reconciliation

> Generated from builders/docs_source.js — do not edit by hand.


## Day 1

### Lab 1.1 — Multi-Agent Topology Setup (Planner–Executor & ReAct) (75 min)

**Objective.** Build the basic multi-agent graph: a Planner (Supervisor) agent decomposes the settlement-processing request; a ReAct Executor parses CSV records; state persists between agent turns.

**Concepts.** Executor + @handler pattern; WorkflowBuilder edges; ctx.set_state/get_state (synchronous, key-value); Agent(client=...) construction; offline/Azure client factory.

**Files.** `labs/day1/starters/lab1_1.py` (build here) · `solutions/day1/lab1_1.py` · `labs/day1/notebooks/lab1_1.ipynb`

1. **Planner Agent (Supervisor).** Create an Agent with planner instructions. The offline stub returns the same JSON schema a live model is instructed to produce, so downstream code is identical in both modes.
2. **Executor node (ReAct over CSV).** Reason step validates each row; Act step emits a normalized record. parse_money() must handle the accounting-negative '(12.50)' planted in row 9 (defect D5).
3. **Wire the state graph.** WorkflowBuilder(start_executor=planner).add_edge(planner, executor).build(); run and assert 26 rows parse with zero rejects.

**Named failure modes.**
- TypeError: set_state() missing 'value' — the API is set_state(key, value), and it is SYNCHRONOUS (no await). This exact bug is corrections C1/C2.
- json.loads fails on the planner reply — in Azure mode the model wrapped JSON in markdown fences; tighten the instructions ('respond ONLY with JSON').
- 25 rows instead of 26 — DictReader consumed the header twice or the duplicate row (D3) was dropped prematurely; do not dedupe at ingestion.

**Stretch.** Add a third node that computes per-file totals, and route it via add_fan_in_edges from both existing nodes.

**Checkpoint.** Script prints 'LAB 1.1 PASS'; the D5 negative promo appears in the parsed records.

### Lab 1.2 — Standardizing Tooling with MCP (75 min)

**Objective.** Expose the mock D365 ERP as an MCP server, validate its JSON Schema contracts over a real stdio session, and bind it to the executor agent.

**Concepts.** MCPServer (mcp 2.0) with @server.tool(); stdio transport; tools/list contracts; MCPStdioTool binding to an Agent.

**Files.** `labs/day1/starters/lab1_2.py` (build here) · `solutions/day1/lab1_2.py` · `labs/day1/notebooks/lab1_2.ipynb`

1. **Protocol-level contract validation.** Open a raw ClientSession against the server subprocess, list tools, assert the search_invoice contract requires order_id:string, then call the tool — a genuine IPC round trip.
2. **Bind the MCP server to the agent.** MCPStdioTool(name='d365', command=...) passed to Agent(tools=...). In Azure mode the model chooses to call search_invoice and must quote 1141.95 for NW-1017; offline validates the protocol layer only (tool CHOICE requires a live model).

**Named failure modes.**
- AttributeError: 'Tool' object has no attribute 'inputSchema' — mcp 2.0 renamed it input_schema (snake_case). Correction C3.
- Server hangs on start — the server file printed to stdout before the protocol handshake; stdio transport requires a clean stdout (log to stderr).
- FileNotFoundError for invoices.json — run common/data_gen.py first.

**Stretch.** Add a get_invoice_history tool with a date-range contract and re-run the introspection assertion.

**Checkpoint.** Contracts set == {search_invoice, post_ledger_entry, list_open_invoices}; 'LAB 1.2 PASS'.

### Lab 1.3 — Contract & Policy Grounding (Foundry IQ pattern) (60 min)

**Objective.** Ground fee-threshold answers in the vendor-agreement corpus via hybrid retrieval, with a prompt-injection guardrail on retrieved passages.

**Concepts.** Hybrid search (keyword + vector-style score); grounded prompting with verbatim citation; XPIA (indirect prompt injection) quarantine.

**Files.** `labs/day1/starters/lab1_3.py` (build here) · `solutions/day1/lab1_3.py` · `labs/day1/notebooks/lab1_3.ipynb`

1. **Build the corpus.** One chunk per policy paragraph.
2. **Hybrid retrieval scorer.** 0.5 x keyword-cosine + 0.5 x character-3gram-cosine — the same weighted-hybrid shape Foundry IQ returns.
3. **Injection guardrail.** Retrieved text is UNTRUSTED input. Scan for instruction-like payloads before it enters the prompt; quarantine matches.
4. **Grounded query end to end.** The agent must quote the $500 clause verbatim and cite the source file.

**Named failure modes.**
- Answer paraphrases instead of quoting — offline stub quotes by design; in Azure mode strengthen instructions ('quote the governing clause verbatim'). Paraphrase-vs-quote was a recurring Batch 1 defect.
- Guardrail misses 'ignore all previous instructions' — single-adjective regex; see correction C6 in Lab 2.3 where the red-team benchmark caught exactly this.
- Top passage is the return policy, not the fee schedule — query terms too generic; inspect the per-chunk scores.

**Stretch.** AZURE: upload the two policy files to a Foundry IQ hybrid index and swap hybrid_search for the index query; the guardrail and assertions stay unchanged.

**Checkpoint.** '$500' appears in the grounded answer with a source citation; injection test quarantined; 'LAB 1.3 PASS'.

### Lab 1.4 — Azure Infrastructure Blueprinting & HITL Logic (90 min)

**Objective.** Emit a Bicep blueprint (queues, container runtime, managed identity) and build a functional HITL trigger: variance > $500 or > 5% pauses the graph into a human review queue.

**Concepts.** ctx.request_info() pause; @response_handler resume; run(responses={id: value}); Bicep resource graph.

**Files.** `labs/day1/starters/lab1_4.py` (build here) · `solutions/day1/lab1_4.py` · `labs/day1/notebooks/lab1_4.ipynb`

1. **Emit the Bicep blueprint.** Structurally lint-checked (balanced braces, four required resource types). Deploy with `az deployment group create -g <rg> -f infra/main.bicep`.
2. **HITL escalation trigger.** VarianceGate pauses via request_info(ReviewRequest, response_type=str) and also writes the escalation to the review-queue file (Azure mode: azure-storage-queue).
3. **Simulated execution.** Low variance flows through; $612.40 (planted defect D1, order NW-1017) pauses; responding 'approved' resumes into on_review; 6.2% (D2, NW-1023) pauses on the percent rule.

**Named failure modes.**
- ValueError: response handler ctx annotation rejected — caused by `from __future__ import annotations` (PEP 563). Remove the future import from any module defining @response_handler. Correction C4 — this one cost real debugging time.
- Outputs non-empty while paused — you yielded before requesting info; a paused record must produce NO output until the response arrives.
- request_id mismatch on resume — read the id from get_request_info_events(), never reconstruct it.

**Stretch.** Add a second response type (dict with reviewer notes) and a second @response_handler for it.

**Checkpoint.** Pause on NW-1017, resume to human_approved, pause on NW-1023; 'LAB 1.4 PASS'.

## Day 2

### Lab 2.1 — Asynchronous State Graph & Execution Loops (90 min)

**Objective.** Full Ingestion -> Extraction -> Matching orchestration with conditional edge routing and a loop-exit condition on unallocated promotional discounts.

**Concepts.** add_edge(condition=...); self-loop with exit cap; fan-out from a single handler via multiple send_message calls.

**Files.** `labs/day2/starters/lab2_1.py` (build here) · `solutions/day2/lab2_1.py` · `labs/day2/notebooks/lab2_1.ipynb`

1. **Node definitions.** Ingestion fans out 10 order messages; Extraction normalizes and flags promos > 5% of gross as unallocated; PromoResolver retries with a hard cap; Matching computes variance against D365.
2. **Conditional edge routing.** Unallocated promos route to the resolver (which self-loops while unresolved); clean records go straight to matching. MAX_PROMO_RETRIES = 3 is the loop exit — without it, planted defect D6 (NW-1012, 8% promo) circulates forever.

**Named failure modes.**
- Workflow raises max-iterations — your self-loop condition never flips; verify the resolver mutates a COPY and re-evaluates promo_unallocated.
- 0 records exercised the retry loop — you regenerated data without defect D6, or filtered it out during extraction. Correction C5: the original dataset made this lab silently happy-path.
- Framework warns 'Self-loop detected' — expected; the warning is the framework telling you to have an exit condition, which you do.

**Stretch.** Replace the retry cap with exponential backoff and a dead-letter output node.

**Checkpoint.** 10 orders complete; NW-1012 exits the loop at 3 retries with a manual-memo note; 'LAB 2.1 PASS'.

### Lab 2.2 — Multimodal Exception Handling & Logic Apps Integration (75 min)

**Objective.** Extract structured line items from a damaged credit memo, emit the escalation payload a Logic Apps HTTP trigger would receive, and produce a voice exception summary (SSML).

**Concepts.** OCR-noise repair; exception vs item separation; HTTP-trigger contract design; SSML.

**Files.** `labs/day2/starters/lab2_2.py` (build here) · `solutions/day2/lab2_2.py` · `labs/day2/notebooks/lab2_2.ipynb`

1. **The damaged credit memo.** Smudged glyphs (O->0), a torn amount, one clean line — extract what is recoverable, FLAG what is not (never guess a torn amount).
2. **Azure vision path.** With credentials, the same memo goes to a vision-capable Foundry deployment. [VERIFY image-content support on your chosen deployment.]
3. **Logic Apps escalation payload.** Exact JSON contract, POSTed live if LOGICAPP_TRIGGER_URL is set, else written to the outbox file — byte-identical payload either way.
4. **Voice exception summary.** SSML always; audio synthesis when AZURE_SPEECH_KEY/REGION are set.

**Named failure modes.**
- 1,2O5.00 parsed as 12.05 — glyph repair ran after the comma strip, or repaired ALL text rather than numeric/ID tokens only (which would corrupt words containing 'O').
- Torn amount extracted as 0.0 — the extractor guessed; unreadable amounts must land in exceptions, not items.
- Live POST fails with 403 — the Logic App SAS signature in the trigger URL is incomplete when copied from the portal; re-copy the full URL.

**Stretch.** Route the exception payload through the Lab 1.4 HITL gate instead of direct notification.

**Checkpoint.** 2 items + 1 exception extracted; payload severity 'high'; 'LAB 2.2 PASS'.

### Lab 2.3 — Automated Red-Teaming & Evaluators (75 min)

**Objective.** Benchmark the matcher over 50 synthetic files (30 clean / 12 fee-error / 8 prompt-attack) with Grounding, Relevance and Safety evaluators and enforced pass/fail thresholds.

**Concepts.** Deterministic benchmark corpora; metric thresholds as promotion gates; injection quarantine as a safety metric.

**Files.** `labs/day2/starters/lab2_3.py` (build here) · `solutions/day2/lab2_3.py` · `labs/day2/notebooks/lab2_3.ipynb`

1. **Synthesize the benchmark corpus.** Seeded RNG: identical corpus on every machine.
2. **System under test.** agent_decide(): quarantine attacks FIRST, then variance rules.
3. **Evaluators.** Grounding = cited variance equals true arithmetic; Relevance = verdict matches ground truth per kind; Safety = every attack quarantined (threshold 1.00 — one miss fails the gate).
4. **Run and report.** eval_report.json feeds Lab 3.1's promotion gates.

**Named failure modes.**
- Safety 0.9 and overall FAIL — the guard regex allows exactly one adjective and 'ignore all previous instructions' slips through. This is correction C6, found by this benchmark's own gate: the lab demonstrates why you red-team your guards.
- Grounding < 1.0 — cited variance was rounded differently from the truth computation; round once, in one place.

**Stretch.** AZURE: register the same three metrics as Azure AI Foundry evaluators and compare cloud scores to local. [VERIFY: foundry evals API surface is preview in 1.11.0.]

**Checkpoint.** All three metrics PASS thresholds; attacks 100% quarantined; 'LAB 2.3 PASS'.

### Lab 2.4 — Observability, OpenTelemetry & CI/CD (75 min)

**Objective.** Instrument nested OTEL spans across the pipeline, compute dollar cost per settlement file from token usage, and generate a valid GitHub Actions workflow.

**Concepts.** TracerProvider + InMemorySpanExporter (assertable); span attributes for tokens/cost; usage_details from ChatResponse; CI job graph.

**Files.** `labs/day2/starters/lab2_4.py` (build here) · `solutions/day2/lab2_4.py` · `labs/day2/notebooks/lab2_4.ipynb`

1. **Tracer with in-memory exporter.** Production swap: azure-monitor-opentelemetry -> Application Insights.
2. **Token cost model.** Prices are ILLUSTRATIVE constants — verify real deployment pricing before quoting numbers to a client.
3. **Traced pipeline.** Three nested span levels: file -> record -> llm.classify, with token/cost attributes on the LLM spans.
4. **GitHub Actions workflow.** test job (pytest offline) gating a package job; YAML validity asserted.

**Named failure modes.**
- Span-name assertion fails with 'invoke_agent matcher' present — agent-framework auto-emits its own spans on the global provider (correction C7). Assert superset, and treat the free framework spans as a feature.
- usage_details is None in Azure mode — some deployments omit usage on streamed responses; use non-streamed runs for the cost exercise.
- Zero cost computed — token counts read from the wrong keys; the UsageDetails keys are input_token_count / output_token_count.

**Stretch.** Add a cost budget guard: abort the file when cumulative cost exceeds a threshold, and emit a span event.

**Checkpoint.** 31 spans captured across 4 names; per-file cost printed; workflow YAML parses; 'LAB 2.4 PASS'.

## Day 3

### Lab 3.1 — Maturity Promotion & Dynamic Model Routing (60 min)

**Objective.** Route routine parsing to an SLM tier and complex variance reasoning to an LLM tier; gate Sandbox -> Staging -> Production promotion on the Lab 2.3 evaluation report.

**Concepts.** Client-side routing policy (inspectable); difficulty classifier; promotion gates reading a machine-readable eval report.

**Files.** `labs/day3/starters/lab3_1.py` (build here) · `solutions/day3/lab3_1.py` · `labs/day3/notebooks/lab3_1.ipynb`

1. **Difficulty classifier and routing policy.** routine/moderate -> slm, complex (|variance| > $500) -> llm. Azure mode: two FoundryChatClient deployments via FOUNDRY_MODEL_SMALL/LARGE. [VERIFY: Foundry's hosted model-router deployment type does this server-side; portal steps in the guide.]
2. **Execute the routing matrix.** Five tasks; assert T1-T3 -> slm, T4-T5 -> llm.
3. **Maturity promotion gates.** promote() reads eval_report.json; degraded safety (0.96) must BLOCK production.

**Named failure modes.**
- FileNotFoundError eval_report.json — Lab 2.3 must run first; the dependency is deliberate (promotion gates consume real evaluation evidence, not vibes).
- T3 routed to llm — the classifier treats ANY variance as complex; only |variance| > $500 qualifies.

**Stretch.** Add a cost column to the routing matrix using Lab 2.4's cost function and compare slm-vs-llm spend.

**Checkpoint.** Routing matrix exact; sandbox->staging->production passes; degraded-safety promotion blocked; 'LAB 3.1 PASS'.

### Lab 3.2 — Governance, Responsible AI & PII Masking (75 min)

**Objective.** PII masked in middleware before ANY text reaches a model; RBAC so only erp.poster can post to the ledger; hash-chained tamper-evident audit log.

**Concepts.** @agent_middleware (with await next() — no args); capture-based verification of model input; role->operation grants; SHA-256 hash chains.

**Files.** `labs/day3/starters/lab3_2.py` (build here) · `solutions/day3/lab3_2.py` · `labs/day3/notebooks/lab3_2.ipynb`

1. **PII redaction as middleware.** Redaction lives in the pipeline, not the prompt — impossible to bypass by writing a different prompt. Assert on the CAPTURED model input, not the reply text (mode-independent).
2. **RBAC on ERP posting.** reconciliation.reader may search; only erp.poster may post. Azure mode: map roles to Entra ID app roles on the agent's managed identity.
3. **Hash-chained audit log.** Each record embeds the previous record's SHA-256; tampering anywhere breaks verification. Production: countersign chain heads with Azure Key Vault CryptographyClient.sign.

**Named failure modes.**
- @chat_middleware never fires — with a custom BaseChatClient, chat middleware attached at the Agent is not invoked; use @agent_middleware, and note next() takes NO arguments. Correction C8, found at runtime.
- Assertion on reply text fails in Azure mode — a live model doesn't echo input; assert on the middleware's capture buffer instead.
- Tampered file still verifies — you re-hashed after tampering; the verifier must recompute from the stored prev_hash chain.

**Stretch.** Add a deny-by-default audit alert: any DENIED record triggers the Lab 2.2 Logic Apps payload.

**Checkpoint.** 3 PII tokens redacted pre-model; reader post DENIED; chain verifies clean and detects the tamper; 'LAB 3.2 PASS'.

### Lab 3.3 — Enterprise Asset Catalog & Tool Reuse (60 min)

**Objective.** Package the D365 MCP connector as a reusable catalog asset (spec introspected LIVE from the running server, so it cannot drift) and consume it from a Shopify reconciliation context with zero code changes.

**Concepts.** Live contract introspection; catalog entry shape (asset id, version, launch command, tool contracts); cross-domain consumption.

**Files.** `labs/day3/starters/lab3_3.py` (build here) · `solutions/day3/lab3_3.py` · `labs/day3/notebooks/lab3_3.ipynb`

1. **Introspect and publish.** tools/list against the running server -> catalog entry. Republish replaces the same asset_id (versioned).
2. **Consume from a new business context.** The Shopify service reads the catalog entry, launches the connector from `launch`, and binds it — it never sees connector source.

**Named failure modes.**
- Spec drift — someone hand-edited the catalog entry; regeneration overwrites it, which is the point.
- Launch command breaks on another machine — the catalog stored an absolute path; store repo-relative args and resolve at launch.

**Stretch.** AZURE: publish the connector spec to the Foundry asset catalog and import it in a second project. [VERIFY: catalog surface is preview.]

**Checkpoint.** Catalog entry with 3 tool contracts; NW-1020 resolved from the Shopify context; 'LAB 3.3 PASS'.

### Lab 3.4 — Tabletop Disaster Simulation & Resiliency Testing (90 min)

**Objective.** Prime Day outage drill: circuit breaker with fast-fail, isolation queue with zero loss, crash mid-batch, rehydrate from a durable checkpoint, and prove no duplicate ERP postings despite full replay plus planted duplicate D3.

**Concepts.** CLOSED/OPEN/HALF_OPEN breaker; isolation queues; FileCheckpointStorage; run(checkpoint_id=...); END-STATE invariants vs per-run counters.

**Files.** `labs/day3/starters/lab3_4.py` (build here) · `solutions/day3/lab3_4.py` · `labs/day3/notebooks/lab3_4.ipynb`

1. **Circuit breaker.** Trips after 3 consecutive 503s; OPEN state fast-fails without hitting the API; HALF_OPEN probes after cooldown.
2. **Ingest under outage.** Every file either processes or lands in the isolation queue — assert processed + isolated == total (zero loss).
3. **Crash + rehydration.** Run 1 checkpoints after ingestion then crashes at row 12. Run 2 resumes FROM THE CHECKPOINT via run(checkpoint_id=...) and completes. Idempotent posting absorbs 12 replayed rows + the D3 duplicate: exactly 24 unique ledger entries.

**Named failure modes.**
- TypeError: list_checkpoints() missing 'workflow_name' — keyword-only argument, matches the WorkflowBuilder name. Correction C9.
- Asserting per-run posted counts — the meaningful invariant is END-STATE (24 unique entries), because the resumed run legitimately replays. Correction C10: measuring the wrong thing passes locally and hides double-posting in production.
- Second run re-crashes — the crash flag wasn't disarmed; in the real scenario this is 'the migration is actually fixed' precondition.

**Stretch.** Move the checkpoint after EACH posted row (finer granularity) and measure the storage cost of the extra durability.

**Checkpoint.** Fast-rejects >= 1; zero loss; rehydration completes with 24 unique ledger entries; 'LAB 3.4 PASS'.

## Capstone — Capstone — Autonomous Amazon Settlement & ERP Reconciliation Engine (Day 4 (full day))

Assemble every component into one production-grade engine: Ingestion -> Remittance -> Smart Match -> [HITL] -> ERP Posting, with durable checkpoints, guardrails, telemetry, and a CLI.

**Phase 1 — Infrastructure & Environment.** Deploy infra/main.bicep (storage, queues, managed identity, container app); validate offline test suite in the workspace; .env carries the Foundry endpoint.

**Phase 2 — Multi-Agent Build & MCP.** Four cooperating agents (IngestionAgent, RemittanceAgent, SmartMatchAgent, ERPPostingAgent) wired through WorkflowBuilder; ERP access via the Lab 1.2 MCP connector pattern.

**Phase 3 — Governance & HITL Canvas.** Auto-post when |variance| < $50 and fee-match >= 98%; HITL review when |variance| > $500 or > 5% (pending reviews land in capstone_pending_reviews.json — the approval canvas); injection quarantine on memo fields; PII middleware from Lab 3.2.

**Phase 4 — Telemetry, Evaluation & CI/CD.** OTEL spans per node; token cost accumulation in workflow state; the Lab 2.3 benchmark is the promotion gate; .github/workflows/deploy.yml packages after tests pass.

**Phase 5 — Executive Demo & Handoff.** `python capstone/engine.py demo` runs the mixed batch live: 22 auto-posts (planted duplicate absorbed), NW-1017 escalates and is approved, NW-1023 escalates and is rejected, NW-1034 exceptions as unmatched. Final ledger: 23 entries. Present the routes table, the pending-review canvas, and the corrections table as the reliability story.

