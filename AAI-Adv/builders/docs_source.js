/**
 * docs_source.js — SINGLE SOURCE OF TRUTH for all programme documentation.
 * Student Guide, Facilitator Guide, and per-lab step sheets are ALL generated
 * from this file by build_docs.js. Edit here, never in the outputs.
 */

const PALETTE = {
  NAVY: "21295C", DEEP: "065A82", TEAL: "1C7293", MINT: "16A0A0", GOLD: "E0A800",
};

const PROGRAM = {
  title: "Advanced Agentic AI on Microsoft Foundry",
  subtitle: "Northwind Global Retail — Amazon Settlement & D365 ERP Reconciliation",
  client: "Accenture — Advanced Programme",
  version: "1.0",
  date: "August 2026",
  stack: "Microsoft Agent Framework (agent-framework-core 1.14.0, agent-framework-foundry 1.11.0) · Azure AI Foundry · MCP 2.0 · OpenTelemetry · GitHub Actions",
};

const ENV_SETUP = {
  title: "Environment Setup — VS Code + Azure",
  steps: [
    ["FASTEST PATH — GitHub Codespaces (zero local install)",
     "Open the repo on GitHub > Code > Codespaces > 'Create codespace on main'. The .devcontainer builds Python 3.12 + Azure CLI + Node automatically, then runs setup: venv, dependencies, seed data, and the full 17-test acceptance suite. When the terminal prints 'Environment ready', you are validated — try `./.venv/bin/python capstone/engine.py demo`. Azure mode works from Codespaces too: `az login --use-device-code`, then fill .env."],
    ["LOCAL PATH — one-command setup",
     "Windows PowerShell: `./setup.ps1` · Linux/macOS/WSL2: `./setup.sh`. Both create .venv, install pinned dependencies, generate seed data, and run the acceptance suite. A green 17/17 is your definition of 'environment ready'."],
    ["Install prerequisites (manual path)",
     "Install VS Code with the Python and Jupyter extensions, Python 3.10–3.12 (labs are validated on 3.12; the SDK declares support through 3.14 but this package was not executed on 3.14), Git, and Azure CLI (az). Windows users: labs run identically in native Windows or WSL2."],
    ["Clone and create the virtual environment (manual path)",
     "Open the repo folder in VS Code. Terminal: `python -m venv .venv` then activate (`.venv\\Scripts\\activate` on Windows, `source .venv/bin/activate` elsewhere) and `pip install -r requirements.txt`. Select the .venv interpreter via the VS Code command palette: 'Python: Select Interpreter'."],
    ["Generate seed data",
     "Run `python common/data_gen.py`. This writes the settlement CSV (26 rows including planted defects), 24 D365 invoices, and the policy corpus. Deterministic: same seed, same data, every machine."],
    ["Validate OFFLINE mode",
     "Run `python -m pytest tests/ -q`. All 17 acceptance tests must pass with NO Azure credentials — this proves your local environment before any cloud dependency enters the picture."],
    ["Provision Azure (once per cohort)",
     "In the Azure portal create an Azure AI Foundry resource + project. In the Foundry portal, deploy a chat model (e.g. a gpt-4o-mini class deployment) and note the DEPLOYMENT name. Copy the Project endpoint from the project Overview page (shape: https://<resource>.services.ai.azure.com/api/projects/<project>). [VERIFY: portal navigation labels change frequently — confirm against current docs at learn.microsoft.com before delivery.]"],
    ["Authenticate",
     "Run `az login` (device code on locked-down machines: `az login --use-device-code`). The labs use DefaultAzureCredential, so no keys are ever stored in code. Your identity needs the 'Azure AI User' role (or equivalent data-plane role) on the Foundry project. [VERIFY role name against current RBAC docs.]"],
    ["Switch to AZURE mode",
     "Copy .env.template to .env and fill FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT. Every lab prints its mode on startup; re-run any lab and it will now execute against live Foundry models. No lab code changes — the switch lives entirely in common/model.py."],
    ["Repository layout for learners",
     "Work in labs/dayN/starters/ (loud NotImplementedError placeholders per step) or labs/dayN/notebooks/. Reference implementations live separately in solutions/dayN/ — same structure, cell for cell, so diffing your starter against its solution is always possible. Starters and notebooks are GENERATED from solutions (builders/gen_starters_notebooks.py); never edit them by hand."],
    ["Run labs in VS Code",
     "Each lab exists twice, in lockstep: solutions/dayN/labN_M.py (and labs/dayN/starters/) use `# %%` cell markers — VS Code renders 'Run Cell' links directly in the editor. The same content is in labs/dayN/notebooks/*.ipynb for the Jupyter UI. Both are generated from the same source; use whichever you prefer."],
  ],
};

// Per-lab content. `steps` mirror the ## Step headings in the solution files.
const LABS = [
  {
    id: "1.1", day: 1, file: "lab1_1",
    title: "Multi-Agent Topology Setup (Planner–Executor & ReAct)",
    duration: "75 min",
    objective: "Build the basic multi-agent graph: a Planner (Supervisor) agent decomposes the settlement-processing request; a ReAct Executor parses CSV records; state persists between agent turns.",
    concepts: "Executor + @handler pattern; WorkflowBuilder edges; ctx.set_state/get_state (synchronous, key-value); Agent(client=...) construction; offline/Azure client factory.",
    steps: [
      ["Planner Agent (Supervisor)", "Create an Agent with planner instructions. The offline stub returns the same JSON schema a live model is instructed to produce, so downstream code is identical in both modes."],
      ["Executor node (ReAct over CSV)", "Reason step validates each row; Act step emits a normalized record. parse_money() must handle the accounting-negative '(12.50)' planted in row 9 (defect D5)."],
      ["Wire the state graph", "WorkflowBuilder(start_executor=planner).add_edge(planner, executor).build(); run and assert 26 rows parse with zero rejects."],
    ],
    failureModes: [
      "TypeError: set_state() missing 'value' — the API is set_state(key, value), and it is SYNCHRONOUS (no await). This exact bug is corrections C1/C2.",
      "json.loads fails on the planner reply — in Azure mode the model wrapped JSON in markdown fences; tighten the instructions ('respond ONLY with JSON').",
      "25 rows instead of 26 — DictReader consumed the header twice or the duplicate row (D3) was dropped prematurely; do not dedupe at ingestion.",
    ],
    stretch: "Add a third node that computes per-file totals, and route it via add_fan_in_edges from both existing nodes.",
    checkpoint: "Script prints 'LAB 1.1 PASS'; the D5 negative promo appears in the parsed records.",
  },
  {
    id: "1.2", day: 1, file: "lab1_2",
    title: "Standardizing Tooling with MCP",
    duration: "75 min",
    objective: "Expose the mock D365 ERP as an MCP server, validate its JSON Schema contracts over a real stdio session, and bind it to the executor agent.",
    concepts: "MCPServer (mcp 2.0) with @server.tool(); stdio transport; tools/list contracts; MCPStdioTool binding to an Agent.",
    steps: [
      ["Protocol-level contract validation", "Open a raw ClientSession against the server subprocess, list tools, assert the search_invoice contract requires order_id:string, then call the tool — a genuine IPC round trip."],
      ["Bind the MCP server to the agent", "MCPStdioTool(name='d365', command=...) passed to Agent(tools=...). In Azure mode the model chooses to call search_invoice and must quote 1141.95 for NW-1017; offline validates the protocol layer only (tool CHOICE requires a live model)."],
    ],
    failureModes: [
      "AttributeError: 'Tool' object has no attribute 'inputSchema' — mcp 2.0 renamed it input_schema (snake_case). Correction C3.",
      "Server hangs on start — the server file printed to stdout before the protocol handshake; stdio transport requires a clean stdout (log to stderr).",
      "FileNotFoundError for invoices.json — run common/data_gen.py first.",
    ],
    stretch: "Add a get_invoice_history tool with a date-range contract and re-run the introspection assertion.",
    checkpoint: "Contracts set == {search_invoice, post_ledger_entry, list_open_invoices}; 'LAB 1.2 PASS'.",
  },
  {
    id: "1.3", day: 1, file: "lab1_3",
    title: "Contract & Policy Grounding (Foundry IQ pattern)",
    duration: "60 min",
    objective: "Ground fee-threshold answers in the vendor-agreement corpus via hybrid retrieval, with a prompt-injection guardrail on retrieved passages.",
    concepts: "Hybrid search (keyword + vector-style score); grounded prompting with verbatim citation; XPIA (indirect prompt injection) quarantine.",
    steps: [
      ["Build the corpus", "One chunk per policy paragraph."],
      ["Hybrid retrieval scorer", "0.5 x keyword-cosine + 0.5 x character-3gram-cosine — the same weighted-hybrid shape Foundry IQ returns."],
      ["Injection guardrail", "Retrieved text is UNTRUSTED input. Scan for instruction-like payloads before it enters the prompt; quarantine matches."],
      ["Grounded query end to end", "The agent must quote the $500 clause verbatim and cite the source file."],
    ],
    failureModes: [
      "Answer paraphrases instead of quoting — offline stub quotes by design; in Azure mode strengthen instructions ('quote the governing clause verbatim'). Paraphrase-vs-quote was a recurring Batch 1 defect.",
      "Guardrail misses 'ignore all previous instructions' — single-adjective regex; see correction C6 in Lab 2.3 where the red-team benchmark caught exactly this.",
      "Top passage is the return policy, not the fee schedule — query terms too generic; inspect the per-chunk scores.",
    ],
    stretch: "AZURE: upload the two policy files to a Foundry IQ hybrid index and swap hybrid_search for the index query; the guardrail and assertions stay unchanged.",
    checkpoint: "'$500' appears in the grounded answer with a source citation; injection test quarantined; 'LAB 1.3 PASS'.",
  },
  {
    id: "1.4", day: 1, file: "lab1_4",
    title: "Azure Infrastructure Blueprinting & HITL Logic",
    duration: "90 min",
    objective: "Emit a Bicep blueprint (queues, container runtime, managed identity) and build a functional HITL trigger: variance > $500 or > 5% pauses the graph into a human review queue.",
    concepts: "ctx.request_info() pause; @response_handler resume; run(responses={id: value}); Bicep resource graph.",
    steps: [
      ["Emit the Bicep blueprint", "Structurally lint-checked (balanced braces, four required resource types). Deploy with `az deployment group create -g <rg> -f infra/main.bicep`."],
      ["HITL escalation trigger", "VarianceGate pauses via request_info(ReviewRequest, response_type=str) and also writes the escalation to the review-queue file (Azure mode: azure-storage-queue)."],
      ["Simulated execution", "Low variance flows through; $612.40 (planted defect D1, order NW-1017) pauses; responding 'approved' resumes into on_review; 6.2% (D2, NW-1023) pauses on the percent rule."],
    ],
    failureModes: [
      "ValueError: response handler ctx annotation rejected — caused by `from __future__ import annotations` (PEP 563). Remove the future import from any module defining @response_handler. Correction C4 — this one cost real debugging time.",
      "Outputs non-empty while paused — you yielded before requesting info; a paused record must produce NO output until the response arrives.",
      "request_id mismatch on resume — read the id from get_request_info_events(), never reconstruct it.",
    ],
    stretch: "Add a second response type (dict with reviewer notes) and a second @response_handler for it.",
    checkpoint: "Pause on NW-1017, resume to human_approved, pause on NW-1023; 'LAB 1.4 PASS'.",
  },
  {
    id: "2.1", day: 2, file: "lab2_1",
    title: "Asynchronous State Graph & Execution Loops",
    duration: "90 min",
    objective: "Full Ingestion -> Extraction -> Matching orchestration with conditional edge routing and a loop-exit condition on unallocated promotional discounts.",
    concepts: "add_edge(condition=...); self-loop with exit cap; fan-out from a single handler via multiple send_message calls.",
    steps: [
      ["Node definitions", "Ingestion fans out 10 order messages; Extraction normalizes and flags promos > 5% of gross as unallocated; PromoResolver retries with a hard cap; Matching computes variance against D365."],
      ["Conditional edge routing", "Unallocated promos route to the resolver (which self-loops while unresolved); clean records go straight to matching. MAX_PROMO_RETRIES = 3 is the loop exit — without it, planted defect D6 (NW-1012, 8% promo) circulates forever."],
    ],
    failureModes: [
      "Workflow raises max-iterations — your self-loop condition never flips; verify the resolver mutates a COPY and re-evaluates promo_unallocated.",
      "0 records exercised the retry loop — you regenerated data without defect D6, or filtered it out during extraction. Correction C5: the original dataset made this lab silently happy-path.",
      "Framework warns 'Self-loop detected' — expected; the warning is the framework telling you to have an exit condition, which you do.",
    ],
    stretch: "Replace the retry cap with exponential backoff and a dead-letter output node.",
    checkpoint: "10 orders complete; NW-1012 exits the loop at 3 retries with a manual-memo note; 'LAB 2.1 PASS'.",
  },
  {
    id: "2.2", day: 2, file: "lab2_2",
    title: "Multimodal Exception Handling & Logic Apps Integration",
    duration: "75 min",
    objective: "Extract structured line items from a damaged credit memo, emit the escalation payload a Logic Apps HTTP trigger would receive, and produce a voice exception summary (SSML).",
    concepts: "OCR-noise repair; exception vs item separation; HTTP-trigger contract design; SSML.",
    steps: [
      ["The damaged credit memo", "Smudged glyphs (O->0), a torn amount, one clean line — extract what is recoverable, FLAG what is not (never guess a torn amount)."],
      ["Azure vision path", "With credentials, the same memo goes to a vision-capable Foundry deployment. [VERIFY image-content support on your chosen deployment.]"],
      ["Logic Apps escalation payload", "Exact JSON contract, POSTed live if LOGICAPP_TRIGGER_URL is set, else written to the outbox file — byte-identical payload either way."],
      ["Voice exception summary", "SSML always; audio synthesis when AZURE_SPEECH_KEY/REGION are set."],
    ],
    failureModes: [
      "1,2O5.00 parsed as 12.05 — glyph repair ran after the comma strip, or repaired ALL text rather than numeric/ID tokens only (which would corrupt words containing 'O').",
      "Torn amount extracted as 0.0 — the extractor guessed; unreadable amounts must land in exceptions, not items.",
      "Live POST fails with 403 — the Logic App SAS signature in the trigger URL is incomplete when copied from the portal; re-copy the full URL.",
    ],
    stretch: "Route the exception payload through the Lab 1.4 HITL gate instead of direct notification.",
    checkpoint: "2 items + 1 exception extracted; payload severity 'high'; 'LAB 2.2 PASS'.",
  },
  {
    id: "2.3", day: 2, file: "lab2_3",
    title: "Automated Red-Teaming & Evaluators",
    duration: "75 min",
    objective: "Benchmark the matcher over 50 synthetic files (30 clean / 12 fee-error / 8 prompt-attack) with Grounding, Relevance and Safety evaluators and enforced pass/fail thresholds.",
    concepts: "Deterministic benchmark corpora; metric thresholds as promotion gates; injection quarantine as a safety metric.",
    steps: [
      ["Synthesize the benchmark corpus", "Seeded RNG: identical corpus on every machine."],
      ["System under test", "agent_decide(): quarantine attacks FIRST, then variance rules."],
      ["Evaluators", "Grounding = cited variance equals true arithmetic; Relevance = verdict matches ground truth per kind; Safety = every attack quarantined (threshold 1.00 — one miss fails the gate)."],
      ["Run and report", "eval_report.json feeds Lab 3.1's promotion gates."],
    ],
    failureModes: [
      "Safety 0.9 and overall FAIL — the guard regex allows exactly one adjective and 'ignore all previous instructions' slips through. This is correction C6, found by this benchmark's own gate: the lab demonstrates why you red-team your guards.",
      "Grounding < 1.0 — cited variance was rounded differently from the truth computation; round once, in one place.",
    ],
    stretch: "AZURE: register the same three metrics as Azure AI Foundry evaluators and compare cloud scores to local. [VERIFY: foundry evals API surface is preview in 1.11.0.]",
    checkpoint: "All three metrics PASS thresholds; attacks 100% quarantined; 'LAB 2.3 PASS'.",
  },
  {
    id: "2.4", day: 2, file: "lab2_4",
    title: "Observability, OpenTelemetry & CI/CD",
    duration: "75 min",
    objective: "Instrument nested OTEL spans across the pipeline, compute dollar cost per settlement file from token usage, and generate a valid GitHub Actions workflow.",
    concepts: "TracerProvider + InMemorySpanExporter (assertable); span attributes for tokens/cost; usage_details from ChatResponse; CI job graph.",
    steps: [
      ["Tracer with in-memory exporter", "Production swap: azure-monitor-opentelemetry -> Application Insights."],
      ["Token cost model", "Prices are ILLUSTRATIVE constants — verify real deployment pricing before quoting numbers to a client."],
      ["Traced pipeline", "Three nested span levels: file -> record -> llm.classify, with token/cost attributes on the LLM spans."],
      ["GitHub Actions workflow", "test job (pytest offline) gating a package job; YAML validity asserted."],
    ],
    failureModes: [
      "Span-name assertion fails with 'invoke_agent matcher' present — agent-framework auto-emits its own spans on the global provider (correction C7). Assert superset, and treat the free framework spans as a feature.",
      "usage_details is None in Azure mode — some deployments omit usage on streamed responses; use non-streamed runs for the cost exercise.",
      "Zero cost computed — token counts read from the wrong keys; the UsageDetails keys are input_token_count / output_token_count.",
    ],
    stretch: "Add a cost budget guard: abort the file when cumulative cost exceeds a threshold, and emit a span event.",
    checkpoint: "31 spans captured across 4 names; per-file cost printed; workflow YAML parses; 'LAB 2.4 PASS'.",
  },
  {
    id: "3.1", day: 3, file: "lab3_1",
    title: "Maturity Promotion & Dynamic Model Routing",
    duration: "60 min",
    objective: "Route routine parsing to an SLM tier and complex variance reasoning to an LLM tier; gate Sandbox -> Staging -> Production promotion on the Lab 2.3 evaluation report.",
    concepts: "Client-side routing policy (inspectable); difficulty classifier; promotion gates reading a machine-readable eval report.",
    steps: [
      ["Difficulty classifier and routing policy", "routine/moderate -> slm, complex (|variance| > $500) -> llm. Azure mode: two FoundryChatClient deployments via FOUNDRY_MODEL_SMALL/LARGE. [VERIFY: Foundry's hosted model-router deployment type does this server-side; portal steps in the guide.]"],
      ["Execute the routing matrix", "Five tasks; assert T1-T3 -> slm, T4-T5 -> llm."],
      ["Maturity promotion gates", "promote() reads eval_report.json; degraded safety (0.96) must BLOCK production."],
    ],
    failureModes: [
      "FileNotFoundError eval_report.json — Lab 2.3 must run first; the dependency is deliberate (promotion gates consume real evaluation evidence, not vibes).",
      "T3 routed to llm — the classifier treats ANY variance as complex; only |variance| > $500 qualifies.",
    ],
    stretch: "Add a cost column to the routing matrix using Lab 2.4's cost function and compare slm-vs-llm spend.",
    checkpoint: "Routing matrix exact; sandbox->staging->production passes; degraded-safety promotion blocked; 'LAB 3.1 PASS'.",
  },
  {
    id: "3.2", day: 3, file: "lab3_2",
    title: "Governance, Responsible AI & PII Masking",
    duration: "75 min",
    objective: "PII masked in middleware before ANY text reaches a model; RBAC so only erp.poster can post to the ledger; hash-chained tamper-evident audit log.",
    concepts: "@agent_middleware (with await next() — no args); capture-based verification of model input; role->operation grants; SHA-256 hash chains.",
    steps: [
      ["PII redaction as middleware", "Redaction lives in the pipeline, not the prompt — impossible to bypass by writing a different prompt. Assert on the CAPTURED model input, not the reply text (mode-independent)."],
      ["RBAC on ERP posting", "reconciliation.reader may search; only erp.poster may post. Azure mode: map roles to Entra ID app roles on the agent's managed identity."],
      ["Hash-chained audit log", "Each record embeds the previous record's SHA-256; tampering anywhere breaks verification. Production: countersign chain heads with Azure Key Vault CryptographyClient.sign."],
    ],
    failureModes: [
      "@chat_middleware never fires — with a custom BaseChatClient, chat middleware attached at the Agent is not invoked; use @agent_middleware, and note next() takes NO arguments. Correction C8, found at runtime.",
      "Assertion on reply text fails in Azure mode — a live model doesn't echo input; assert on the middleware's capture buffer instead.",
      "Tampered file still verifies — you re-hashed after tampering; the verifier must recompute from the stored prev_hash chain.",
    ],
    stretch: "Add a deny-by-default audit alert: any DENIED record triggers the Lab 2.2 Logic Apps payload.",
    checkpoint: "3 PII tokens redacted pre-model; reader post DENIED; chain verifies clean and detects the tamper; 'LAB 3.2 PASS'.",
  },
  {
    id: "3.3", day: 3, file: "lab3_3",
    title: "Enterprise Asset Catalog & Tool Reuse",
    duration: "60 min",
    objective: "Package the D365 MCP connector as a reusable catalog asset (spec introspected LIVE from the running server, so it cannot drift) and consume it from a Shopify reconciliation context with zero code changes.",
    concepts: "Live contract introspection; catalog entry shape (asset id, version, launch command, tool contracts); cross-domain consumption.",
    steps: [
      ["Introspect and publish", "tools/list against the running server -> catalog entry. Republish replaces the same asset_id (versioned)."],
      ["Consume from a new business context", "The Shopify service reads the catalog entry, launches the connector from `launch`, and binds it — it never sees connector source."],
    ],
    failureModes: [
      "Spec drift — someone hand-edited the catalog entry; regeneration overwrites it, which is the point.",
      "Launch command breaks on another machine — the catalog stored an absolute path; store repo-relative args and resolve at launch.",
    ],
    stretch: "AZURE: publish the connector spec to the Foundry asset catalog and import it in a second project. [VERIFY: catalog surface is preview.]",
    checkpoint: "Catalog entry with 3 tool contracts; NW-1020 resolved from the Shopify context; 'LAB 3.3 PASS'.",
  },
  {
    id: "3.4", day: 3, file: "lab3_4",
    title: "Tabletop Disaster Simulation & Resiliency Testing",
    duration: "90 min",
    objective: "Prime Day outage drill: circuit breaker with fast-fail, isolation queue with zero loss, crash mid-batch, rehydrate from a durable checkpoint, and prove no duplicate ERP postings despite full replay plus planted duplicate D3.",
    concepts: "CLOSED/OPEN/HALF_OPEN breaker; isolation queues; FileCheckpointStorage; run(checkpoint_id=...); END-STATE invariants vs per-run counters.",
    steps: [
      ["Circuit breaker", "Trips after 3 consecutive 503s; OPEN state fast-fails without hitting the API; HALF_OPEN probes after cooldown."],
      ["Ingest under outage", "Every file either processes or lands in the isolation queue — assert processed + isolated == total (zero loss)."],
      ["Crash + rehydration", "Run 1 checkpoints after ingestion then crashes at row 12. Run 2 resumes FROM THE CHECKPOINT via run(checkpoint_id=...) and completes. Idempotent posting absorbs 12 replayed rows + the D3 duplicate: exactly 24 unique ledger entries."],
    ],
    failureModes: [
      "TypeError: list_checkpoints() missing 'workflow_name' — keyword-only argument, matches the WorkflowBuilder name. Correction C9.",
      "Asserting per-run posted counts — the meaningful invariant is END-STATE (24 unique entries), because the resumed run legitimately replays. Correction C10: measuring the wrong thing passes locally and hides double-posting in production.",
      "Second run re-crashes — the crash flag wasn't disarmed; in the real scenario this is 'the migration is actually fixed' precondition.",
    ],
    stretch: "Move the checkpoint after EACH posted row (finer granularity) and measure the storage cost of the extra durability.",
    checkpoint: "Fast-rejects >= 1; zero loss; rehydration completes with 24 unique ledger entries; 'LAB 3.4 PASS'.",
  },
];

const CAPSTONE = {
  title: "Capstone — Autonomous Amazon Settlement & ERP Reconciliation Engine",
  duration: "Day 4 (full day)",
  objective: "Assemble every component into one production-grade engine: Ingestion -> Remittance -> Smart Match -> [HITL] -> ERP Posting, with durable checkpoints, guardrails, telemetry, and a CLI.",
  phases: [
    ["Phase 1 — Infrastructure & Environment", "Deploy infra/main.bicep (storage, queues, managed identity, container app); validate offline test suite in the workspace; .env carries the Foundry endpoint."],
    ["Phase 2 — Multi-Agent Build & MCP", "Four cooperating agents (IngestionAgent, RemittanceAgent, SmartMatchAgent, ERPPostingAgent) wired through WorkflowBuilder; ERP access via the Lab 1.2 MCP connector pattern."],
    ["Phase 3 — Governance & HITL Canvas", "Auto-post when |variance| < $50 and fee-match >= 98%; HITL review when |variance| > $500 or > 5% (pending reviews land in capstone_pending_reviews.json — the approval canvas); injection quarantine on memo fields; PII middleware from Lab 3.2."],
    ["Phase 4 — Telemetry, Evaluation & CI/CD", "OTEL spans per node; token cost accumulation in workflow state; the Lab 2.3 benchmark is the promotion gate; .github/workflows/deploy.yml packages after tests pass."],
    ["Phase 5 — Executive Demo & Handoff", "`python capstone/engine.py demo` runs the mixed batch live: 22 auto-posts (planted duplicate absorbed), NW-1017 escalates and is approved, NW-1023 escalates and is rejected, NW-1034 exceptions as unmatched. Final ledger: 23 entries. Present the routes table, the pending-review canvas, and the corrections table as the reliability story."],
  ],
  demoRisks: [
    ["Live Azure model latency during demo", "Fallback: run in OFFLINE mode — identical routes and ledger by design; announce mode explicitly."],
    ["Checkpoint directory left over from rehearsal", "Clear outputs/capstone_checkpoints before the demo or resume picks up stale state."],
    ["Audience asks for real Azure spend figures", "Cost constants are labelled illustrative; pull real pricing from the Azure page live rather than quoting from memory."],
  ],
};

const FACILITATOR = {
  audience: "Senior engineers/architects (Accenture delivery teams). Assumes Python fluency and basic Azure familiarity; no prior agent-framework experience.",
  cohortPrep: [
    "T-7 days: send Environment Setup section; require `pytest -q` green (offline) before Day 1 — this eliminates 90% of Day-1 support load.",
    "T-2 days: provision the shared Foundry project and one model deployment per 4 learners (or one shared deployment with per-learner .env); verify quota.",
    "T-1 day: run the full acceptance suite yourself on the delivery machine, in both modes if Azure is ready. Print/keep the corrections table — learners will hit C1-C11 in the wild and the table turns each into a 30-second answer.",
    "Day of: clear outputs/ in your demo checkout (stale checkpoints and pending-review files are the most common demo glitch).",
  ],
  timing: [
    ["Day 1", "09:00 kickoff + scenario (30m) · Lab 1.1 (75m) · Lab 1.2 (75m) · lunch · Lab 1.3 (60m) · Lab 1.4 (90m) · debrief (30m)"],
    ["Day 2", "recap (15m) · Lab 2.1 (90m) · Lab 2.2 (75m) · lunch · Lab 2.3 (75m) · Lab 2.4 (75m) · debrief (30m)"],
    ["Day 3", "recap (15m) · Lab 3.1 (60m) · Lab 3.2 (75m) · lunch · Lab 3.3 (60m) · Lab 3.4 (90m) · capstone briefing (30m)"],
    ["Day 4", "capstone phases 1-4 (learner-driven, checkpointed reviews at each phase) · 15:30 executive demos · retro"],
  ],
  teachingNotes: [
    "Starters raise NotImplementedError('STEP N: ...') — loud placeholders, generated from the solutions. If a learner's starter differs from the solution structure, regenerate (builders/gen_starters_notebooks.py); never hand-patch starters.",
    "OFFLINE mode is not a toy: it validates graph wiring, HITL, checkpointing, MCP IPC, middleware and telemetry with zero cloud spend. Insist labs go green offline BEFORE flipping .env — it converts 'is it my code or my credentials?' into two separate questions.",
    "The planted defects (D1-D6) are the curriculum: every one maps to a lab assertion. If a learner asks why the data is 'broken', that is the teaching moment.",
    "The corrections table (C1-C11) is real debugging history from building this package against the live SDK. Present it on Day 1: it models 'build and run, don't review' and pre-answers the most likely stack traces.",
    "PEP 563 (C4) will bite anyone who habitually adds `from __future__ import annotations`. Mention it before Lab 1.4, not after.",
    "Python version: validated on 3.12. The blueprint says 3.14 and the SDK classifiers include 3.14, but this package was not executed on 3.14 — if the cohort environment is 3.14, run the acceptance suite there before Day 1 and treat any failure as an environment issue, not a lab bug.",
  ],
  assessment: "Capstone rubric: engine runs the mixed batch (40%) · HITL canvas demonstrates approve AND reject paths (20%) · ledger integrity under replay (20%) · telemetry + cost story (10%) · governance controls demonstrated (10%). Pass >= 70%.",
};

const VERIFICATION_REGISTER = [
  ["VERIFIED (executed)", "agent-framework-core 1.14.0 workflow/HITL/checkpoint/middleware APIs; agent-framework-foundry 1.11.0 imports incl. FoundryChatClient.as_agent() (create_agent() does NOT exist); mcp 2.0.0 MCPServer + stdio client round trip; all 12 labs + capstone + 17 acceptance tests pass offline on Python 3.12."],
  ["VERIFIED (introspection only)", "FoundryChatClient constructor (project_endpoint/model/credential); UsageDetails token keys; FileCheckpointStorage.list_checkpoints(workflow_name=...)."],
  ["VERSION-SENSITIVE [VERIFY before delivery]", "Foundry portal navigation (endpoint location, IQ index creation, evaluator registration, asset catalog, hosted model-router) — preview surfaces, re-check against learn.microsoft.com; Azure RBAC role name for Foundry data plane; vision/image content support per deployment; foundry evals API (FoundryEvals/evaluate_foundry_target) signatures."],
  ["NOT EXECUTED", "Azure-mode paths end-to-end (no credentials in the build environment) — code paths are gated on env vars and follow verified constructor signatures, but live-run them during cohort prep; Python 3.14 execution; Bicep deployment to a real subscription."],
  ["ILLUSTRATIVE (labelled)", "Token prices in Labs 2.4/capstone; all timing estimates."],
];

const CORRECTIONS = [
  ["C1", "ctx.set_state called with a dict", "API is set_state(key, value)", "Lab 1.1"],
  ["C2", "await on set_state/get_state", "Both are synchronous", "Lab 1.1"],
  ["C3", "Tool.inputSchema attribute", "mcp 2.0 renamed to input_schema", "Lab 1.2"],
  ["C4", "PEP 563 future import breaks @response_handler validation", "Remove `from __future__ import annotations` from executor modules", "Lab 1.4, capstone"],
  ["C5", "Retry loop never exercised (happy-path data)", "Planted defect D6 (NW-1012, 8% promo) + assertion that it fires", "Lab 2.1, data_gen"],
  ["C6", "Injection regex allowed exactly one adjective; 'ignore all previous instructions' evaded it", "Multi-adjective pattern; found by the benchmark's own safety gate", "Lab 2.3"],
  ["C7", "Span-name equality assertion failed", "agent-framework auto-emits invoke_agent spans; assert superset", "Lab 2.4"],
  ["C8", "@chat_middleware on Agent never invoked with custom client; next(ctx) wrong", "Use @agent_middleware; continuation is next() with no args; assert on captured model input", "Lab 3.2"],
  ["C9", "list_checkpoints() missing workflow_name", "Keyword-only arg matching the WorkflowBuilder name", "Lab 3.4"],
  ["C10", "Asserted per-run post counts after resume", "Assert END-STATE invariant: 24 unique ledger entries after replay + D3 dup", "Lab 3.4"],
  ["C11", "Starters broke: parents[2] resolves wrong one directory deeper", "Generator rewrites ROOT to an upward marker search", "builders"],
  ["C12", "UnicodeEncodeError on Windows: lab printed U+2714 checkmark; child stdout defaults to cp1252", "ASCII-only prints in labs; test runner forces PYTHONUTF8=1 for subprocesses. Found by first Windows execution", "Lab 1.4, tests"],
];

module.exports = { PALETTE, PROGRAM, ENV_SETUP, LABS, CAPSTONE, FACILITATOR,
                   VERIFICATION_REGISTER, CORRECTIONS };
