/* =====================================================================
   content_capstone.js — SINGLE SOURCE OF TRUTH for the Capstone deck.

   !! BUILD STATUS WARNING !!
   The Capstone BUILD (src/, webapp/, guide) is not yet produced, and it has a
   BLOCKING dependency: gap G3 (human-in-the-loop). This deck is design-locked
   ahead of the build so scope, architecture and acceptance criteria are agreed
   first. Re-verify every reference against the built artifacts before delivery.
   ===================================================================== */

const PALETTE = {
  NAVY: "21295C", DEEP: "065A82", TEAL: "1C7293",
  MINT: "16A0A0", GOLD: "E0A800",
  INK: "1A1A2E", BODY: "3C4257", MUTED: "6B7280",
  PAPER: "FFFFFF", WASH: "F2F6F9", LINE: "D7E1EA",
};

const FONT = { HEAD: "Cambria", BODY: "Calibri", MONO: "Consolas" };

const slides = [
  /* ---------------------------------------------------------------- 1 */
  {
    layout: "title",
    kicker: "ACCENTURE BATCH 1 · AGENTIC AI FOUNDATION",
    title: "Automated Payment & Reconciliation System",
    subtitle: "Capstone · unifying the configurable rule engine with deduction identification and cash application",
    footer: "LangGraph · Azure AI Foundry · MCP · Human-in-the-loop",
    notes: `WHY: The capstone is not a new project. It is the assembly of three days of components into something deployable, and framing it that way removes most of the anxiety in the room.

SAY: "Nothing here is new. You have built every component. The capstone joins Capstone 01 — the configurable rule engine — with Capstone 02 — deduction identification and cash application — into one workflow, and then adds the two things a demo does not need and a deployment does: durable state and a human in the loop."

SAY: "Be clear about what changes. Days 1 to 3 processed ten transactions in memory, one at a time, in a script. The capstone handles a batch, survives a crash, and suspends for a human decision without losing its place."

ASK: "What breaks first when you go from ten transactions in memory to five thousand overnight?" Good answers: model latency, state persistence, partial-failure recovery, and the exception queue overwhelming the team.

WATCH: If gap G3 has not been remediated, say so in this first five minutes. Do not let the room discover it at the human-in-the-loop step.

TIME: 4 min`,
  },

  /* ---------------------------------------------------------------- 2 */
  {
    layout: "flow",
    title: "What you already have",
    subtitle: "Three days of components. The capstone is assembly plus two additions.",
    steps: [
      { n: "1", h: "From Day 1 — the engine", b: "Six priority rules, typed state, conditional routing, a compiled graph with an inspectable topology, and correlated JSON audit trails." },
      { n: "2", h: "From Day 2 — the intelligence", b: "Chunked and metadata-filtered remittance corpus, distance-gated retrieval, Pydantic-validated grounded extraction, and a permissioned tool registry." },
      { n: "3", h: "From Day 3 — the controls", b: "Input gates, output redaction, REJECTED_SECURITY_HOLD as an end state, and full transition auditing including refusals." },
      { n: "★", h: "New in the capstone", b: "Durable checkpointing so a run survives a crash, and human-in-the-loop suspend-and-resume so QUERY is actionable rather than terminal." },
    ],
    notes: `WHY: Lowers perceived scope. People arrive at a capstone expecting to build from scratch and are relieved to see it is integration.

SAY: "Read the fourth row carefully, because it is the only genuinely new engineering. Everything above it you have written and run."

SAY: "Durable checkpointing means the graph writes its state after every node. If the process dies at transaction four thousand of five thousand, you resume at four thousand and one rather than re-running the batch — which matters enormously when re-running means re-posting to an ERP."

SAY: "Human-in-the-loop means QUERY stops being a dead end. Today your QUERY transactions terminate with requires_human set to true and nothing happens. In the capstone the graph SUSPENDS at that point, persists, waits for an analyst decision, and then resumes exactly where it stopped, with all its state intact."

FLAG IF UNREMEDIATED: "Both of those depend on LangGraph's checkpointer and interrupt mechanism, which no Day 1 to 3 lab teaches. That is gap G3. If the remediation lab has not been delivered, we walk through it together now rather than pretending it is assumed knowledge."

TIME: 5 min`,
  },

  /* ---------------------------------------------------------------- 3 */
  {
    layout: "statement",
    kicker: "THE BUSINESS PROBLEM, RESTATED",
    headline: "Manual reconciliation consumes hundreds of hours, drives cash-posting errors, and leaves disputes unresolved.",
    support: "The capstone automates the end-to-end payment lifecycle: bank statement in, matched and coded posting out, with every exception routed to a named owner and every decision traceable to its evidence.",
    notes: `WHY: Reconnects to the client's own framing before diving into architecture. Engineers drift towards the graph; the sponsor cares about the queue.

SAY: "That headline is the client's language, from the source specification. Notice it names three costs, not one: labour hours, error rate, and unresolved disputes. Those are three different budgets and three different owners."

SAY: "Notice also what it does not say. It does not promise a percentage. Every number in this programme has been measured rather than asserted, and that discipline is what makes the business case survive scrutiny."

ASK: "Of those three costs, which does your Day 2 work actually reduce?" Push them: mostly the third and second, not the first. Coding and routing a deduction does not remove the analyst — it removes the analyst's research time and gets the dispute to the right team inside SLA.

SAY: "If you brief a sponsor on this, lead with unresolved disputes. It is the cost they feel most and measure least."

TIME: 5 min`,
  },

  /* ---------------------------------------------------------------- 4 */
  {
    layout: "cards4",
    title: "The capstone architecture, layer by layer",
    cards: [
      { icon: "◆", h: "LangGraph", b: "Execution flow, branching for 2-way and 3-way matches, and interruption handling for the QUERY state.", tag: "ORCHESTRATION" },
      { icon: "◈", h: "Agentic RAG + Foundry", b: "Parses unstructured PDFs, emails and scanned remittances; maps prose to reason codes D01–D05 with verbatim grounding.", tag: "DOCUMENT INTELLIGENCE" },
      { icon: "◇", h: "MCP tools", b: "Structured, permissioned calls into ERP SQL and bank ledger files — without exposing the database to the agent.", tag: "INTEGRATION" },
      { icon: "◉", h: "Guardrails & observability", b: "Prevents hallucinated match keys and mis-posting; logs complete reasoning traces for financial audit.", tag: "CONTROL" },
    ],
    notes: `WHY: This is the client's own stack diagram, and it is worth confirming that each layer now maps to code the learners have written.

SAY: "This is the architecture from the source specification, and by now every box maps to something in your repository. LangGraph is your compiled graph. Agentic RAG is Day 2, Labs 1 and 4. Guardrails are Day 3."

SAY on MCP, honestly: "The MCP box is the one to be precise about. You have built the tool BOUNDARY — typed schemas, read and write permissions, refusal of unauthorised writes, per-call audit. What you have not built is an actual MCP client and server over a transport. That is gap G2. The concept transfers; the wire protocol is an exercise."

SAY on the fourth box: "'Prevents hallucinated match keys' is doing a lot of work in that sentence. Concretely it means two things you already built: invoice numbers come from a regular expression rather than a model, and any cited evidence must be a verbatim substring of the retrieved document."

ASK: "Which layer would you expect to fail first under production load?" Usually the second — model latency across a batch — which is why Day 2 Lab 2 had them measure it.

TIME: 6 min`,
  },

  /* ---------------------------------------------------------------- 5 */
  {
    layout: "table",
    title: "Acceptance criteria",
    subtitle: "Declared before the build. This is what 'done' means.",
    head: ["#", "Criterion", "Evidence required"],
    colW: [0.7, 5.6, 5.6],
    rows: [
      ["1", "All six priority rules implemented and evaluated in order", "unit tests per rule; the matched priority recorded in state"],
      ["2", "Every transaction terminates in a declared end state", "no transaction finishes as OPEN; distribution reported"],
      ["3", "Deduction reasons grounded in verbatim evidence", "citation check passes; UNKNOWN where no reason is stated"],
      ["4", "No write executes without graph authorisation", "audit ledger shows refused writes; no unauthorised call succeeds"],
      ["5", "A run survives process death and resumes", "kill mid-batch; resume; no duplicate ERP postings"],
      ["6", "QUERY suspends and resumes on human input", "analyst decision recorded; graph continues from the same state"],
      ["7", "Any single payment reconstructable from the log alone", "run_id trace: rule fired, evidence chunk, model output, outcome"],
    ],
    callout: "Criteria 5 and 6 depend on durable checkpointing and LangGraph interrupt — gap G3. If that remediation has not landed, criteria 5 and 6 cannot be met and the capstone scope must be restated honestly rather than quietly reduced.",
    notes: `WHY: Pre-declared acceptance criteria are what turn a capstone from an open-ended build into an assessable deliverable. This slide is close to a client artifact.

SAY: "Seven criteria, declared before anyone writes code. Each one has an evidence column, because 'it works' is not an acceptance criterion — 'here is the artifact that proves it' is."

SAY on criterion 4: "Note the evidence for criterion four. It is not 'no unauthorised write succeeded'. It is 'the audit ledger SHOWS refused writes'. Absence of evidence is not evidence of control. If nothing was ever refused, you have not demonstrated the control fires — you have demonstrated nobody tested it."

SAY on criterion 5: "Killing the process mid-batch and resuming without duplicate postings is the criterion that separates a demo from something you would run against a real ERP. It exercises the idempotency keys you built in Day 2 Lab 2."

SAY on the callout, plainly: "Criteria five and six are blocked on gap G3. If the human-in-the-loop remediation has not been delivered, the correct response is to restate the capstone scope out loud — deliver criteria one to four and seven, and record five and six as deferred. Quietly dropping them is how a programme loses credibility."

TIME: 7 min`,
  },

  /* ---------------------------------------------------------------- 6 */
  {
    layout: "code",
    title: "Durable state and the human-in-the-loop pause",
    subtitle: "The two additions the capstone needs. Both are LangGraph mechanisms, neither is taught in Days 1–3 as scoped.",
    code: `from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

graph = builder.compile(checkpointer=SqliteSaver.from_conn_string("recon.db"))
config = {"configurable": {"thread_id": txn_id}}   # one thread per payment

def node_human_review(state):
    decision = interrupt({                 # graph SUSPENDS here and persists
        "txn_id":   state["txn_id"],
        "variance": state["variance_usd"],
        "evidence": state.get("reason_evidence", ""),
        "ask":      "Assign a reason code, or reject the deduction.",
    })
    return {"reason_code": decision["reason_code"], "requires_human": False}

graph.invoke(Command(resume={"reason_code": "D03"}), config)   # later, resumes here`,
    bullets: [
      "thread_id per payment — the checkpointer keys durable state on it, so resume targets one transaction",
      "interrupt() suspends and persists; it does not block a thread waiting for input",
      "Command(resume=...) continues from the exact node, with all prior state intact",
      "VERSION-SENSITIVE: interrupt and Command are post-0.2 LangGraph. verify_environment.py checks the import and warns if absent",
    ],
    notes: `WHY: This is the gap-G3 content in its minimum viable form. If the remediation lab has not been built, this slide plus a live walkthrough is the fallback.

SAY: "Two imports and four concepts. The checkpointer persists state after every node. The thread_id scopes that state to one payment. interrupt suspends the graph and writes it down. Command resumes it."

SAY on the second bullet, because it is the common misconception: "interrupt does NOT block a thread waiting for an analyst to come back from lunch. It suspends the graph, persists the state, and returns control. The analyst might respond in four hours or four days. Your process is not sitting there holding a connection open."

SAY on the fourth bullet: "Be careful here. These are post-0.2 APIs and the surface has moved. Your environment verifier imports langgraph.types.interrupt specifically and warns if it is absent. Check the verifier output on the delivery machine before you teach this — do not present a signature you have not run."

DEMO IF POSSIBLE: invoke a graph, hit the interrupt, inspect graph.get_state(config), then resume with a Command. Seeing the suspended state on disk is what makes it click.

TIME: 8 min`,
  },

  /* ---------------------------------------------------------------- 7 */
  {
    layout: "worked",
    title: "One payment, all three days, end to end",
    subtitle: "BNK-1002 · every control it passes through",
    steps: [
      { k: "ingest", v: "ACME CORPORATION → Acme Corp · $9,500.00 · ref \"PO-5541\"" },
      { k: "input guardrail", v: "remittance text scanned for injection patterns · clear" },
      { k: "remittance_search", v: "2 chunks, filtered to txn_id, best distance 0.88, within threshold" },
      { k: "parse_remittance", v: "regex extracts INV-810 — deterministic, never a model call" },
      { k: "rule_engine", v: "priority 1 · customer + PO-5541 → INV-810, billed $10,000.00" },
      { k: "classify_deduction", v: "D03 Damage · 0.85 · citation verified verbatim against source" },
      { k: "output guardrail", v: "response scanned for PII and secrets · clear" },
      { k: "open_dispute (write)", v: "graph-authorised · DSP-1001 · Quality · SLA 10d · idempotency key set" },
      { k: "checkpoint", v: "state persisted · thread_id BNK-1002 · resumable" },
    ],
    notes: `WHY: The single most satisfying slide of the programme. One transaction, nine steps, every control the learners built.

SAY: "This is the transaction you first met in Day 1, Lab 1, as a line in a telemetry demo. Nine steps later it is a coded, routed, audited, resumable piece of work with a named owner and an SLA."

SAY: "Count the controls it passed. Input gate. Distance gate. Metadata filter. Deterministic extraction for the structured parts. Schema validation. Verbatim grounding. Output gate. Write authorisation. Idempotency key. Nine controls, and only one of them involved a language model making a judgement."

SAY, and let it land: "That ratio is the point of the whole programme. The model does one job — reading prose — and everything around it is deterministic, testable and auditable. Teams that invert that ratio build systems that demo beautifully and fail controls testing."

ASK: "Which single step would you strengthen first with more budget?" Most answers converge on classify_deduction, which is correct — it is the only probabilistic step, which is why it already carries two independent controls.

TIME: 6 min`,
  },

  /* ---------------------------------------------------------------- 8 */
  {
    layout: "table",
    title: "The ten-transaction reference set",
    subtitle: "Your regression suite. Expected outcomes are known and enforced by verify_environment.py.",
    head: ["Txn", "What it exercises", "Expected end state"],
    colW: [1.5, 6.6, 3.8],
    rows: [
      ["BNK-1001", "priority 4, exact match — the happy path", "CLOSED"],
      ["BNK-1002", "priority 1, short pay, D03 damage claim, dispute raised", "PARTIAL_MATCH"],
      ["BNK-1003", "variance inside the $10 tolerance, auto-write-off", "CLOSED"],
      ["BNK-1004", "payer known, no invoice reference", "UAC"],
      ["BNK-1005", "blank sender, blank reference — nothing to work with", "UIC"],
      ["BNK-1006", "priority 2, delivery-number match", "CLOSED"],
      ["BNK-1007", "priority 3, invoice plus date", "CLOSED"],
      ["BNK-1008", "priority 5, 3-way match — exposes split application (S3)", "QUERY"],
      ["BNK-1009", "short pay, remittance states no reason — declines to guess", "QUERY"],
      ["BNK-1010", "overpayment — no end state defined (S1)", "QUERY"],
    ],
    callout: "Freeze this table. Any change to the rules, the threshold or the prompt that moves a row is a regression until proven otherwise. verify_environment.py fails the build if the Day 1 baseline drifts.",
    notes: `WHY: Hands learners a working regression suite and models the discipline of a known-answer test.

SAY: "Ten transactions, ten known outcomes. This is not sample data — it is a regression suite, and it is wired into the environment verifier as a known-answer test. If someone tunes a threshold and BNK-1003 stops closing, the verifier fails before anyone reaches a classroom."

SAY on rows 8, 9 and 10: "Three of your ten expected outcomes are QUERY, and two of those are QUERY because the SPECIFICATION is incomplete rather than because the code is. That is a thirty percent human-touch rate driven by open design questions. Take that number to the client — it quantifies exactly what those two decisions are worth."

SAY on row 9: "BNK-1009 is the row I would defend hardest in a review. The system could easily produce a confident reason code from that remittance. It declines. Lower automation rate, higher correctness rate, and the only honest outcome."

ASK: "Which row would you add to this set for your own organisation?" Multi-currency, parent-pays-subsidiary, and credit notes are the usual answers, and all three are real gaps.

TIME: 7 min`,
  },

  /* ---------------------------------------------------------------- 9 */
  {
    layout: "cards3",
    title: "From ten transactions to a nightly batch",
    cards: [
      { icon: "◷", h: "Latency budget", b: "Model calls dominate. Measure yours from Day 2 Lab 2, multiply by volume and calls-per-payment, and check it fits the window before you design anything else.", tag: "THROUGHPUT" },
      { icon: "◫", h: "Partial failure", b: "A batch that dies at transaction 4,000 must resume, not restart. Checkpoint per thread_id; idempotency keys on every write.", tag: "RECOVERY" },
      { icon: "◉", h: "Queue capacity", b: "Every QUERY and UAC lands in a human queue. If the exception rate exceeds the team's capacity, automation has moved the bottleneck rather than removed it.", tag: "OPERATIONS" },
    ],
    footnote: "The third card is the one that sinks programmes. Model the exception queue before you model the happy path.",
    notes: `WHY: The operational reality that separates a capstone that would deploy from one that would not.

SAY on the first card: "You measured your endpoint latency on Day 2. Multiply it by five thousand payments and two calls each and see whether it fits your batch window. If it does not, the answer is not a faster model — it is fewer model calls, which means pushing more work into deterministic Python."

SAY on the second card: "Restarting a five-thousand-payment batch is not merely slow. It risks re-posting to an ERP. Your idempotency keys are what make a restart survivable, and this is where they stop being an academic nicety."

SAY on the third card, which is the one that matters: "I have seen more automation programmes stall here than anywhere else. Suppose you automate seventy percent and route thirty percent to exceptions. If your team could previously handle a hundred percent at low speed, and now faces thirty percent that are all genuinely hard, you may have made their day worse. The easy work left; the residue is concentrated."

ASK: "Who sizes the exception queue in your organisation, and when?" Usually nobody, and usually after go-live.

TIME: 6 min`,
  },

  /* --------------------------------------------------------------- 10 */
  {
    layout: "compare",
    title: "What to report to a steering committee",
    subtitle: "Three pairs of numbers. Reporting only the left-hand column is how a business case gets overstated.",
    columns: [
      {
        h: "The flattering number", tint: "MUTED",
        rows: ["Match rate: a rule found an invoice", "Straight-through: closed with no human", "Catch rate: attacks the gate blocked", "Automation: share not touched by a person", "All four: easy to move by lowering a bar"],
      },
      {
        h: "The honest partner", tint: "TEAL",
        rows: ["Straight-through: closed with no human", "Coded and routed: exceptions made actionable", "False positives: legitimate items wrongly blocked", "Correctness: decisions that were right", "All four: harder to move, harder to fake"],
      },
      {
        h: "What to actually say", tint: "NAVY",
        rows: ["Report: both numbers, always, side by side", "Report: the frozen baseline they are measured against", "Report: the backend and data that produced them", "Report: the open design questions still outstanding", "Report: what the system refused to do"],
      },
    ],
    notes: `WHY: The measurement discipline of the whole programme, consolidated into one slide learners can photograph and reuse.

SAY: "You have met this pattern three times: Day 1, Day 2 and Day 3. Here it is in one place. Every flattering metric in the left column has an honest partner in the middle, and every one of them can be improved by making the system worse."

SAY, with the example: "Raise the write-off tolerance from ten dollars to five hundred and your straight-through rate jumps. You have not automated anything. You have written off customers' damage claims without recording that they made one. The metric will not tell you that. The middle column will."

SAY on the third column: "Reporting the backend matters more than people expect. If a number came from an offline stub with a lexical embedder, it is not a retrieval-quality result, and putting it on a slide without that label is how a pilot gets committed to a target it cannot hit."

SAY on the last row: "'What the system refused to do' belongs in a steering report. Refused writes, held transactions, declined classifications. It is the only direct evidence your controls are live."

ASK: "Which of these does your current reporting already include?" Usually one, occasionally two.

TIME: 6 min`,
  },

  /* --------------------------------------------------------------- 11 */
  {
    layout: "stats",
    title: "The measurement discipline, one last time",
    stats: [
      { big: "Freeze first", small: "A percentage target is meaningless without a baseline measured on the client's own payment file, before training begins." },
      { big: "Measure, don't assert", small: "Every number in this programme was computed from a reproducible run. None was estimated, and none was carried over from a vendor deck." },
    ],
    body: "An automation target is a measurement problem before it is a training outcome. You cannot improve a percentage against a baseline that does not exist — and a baseline is a week of instrumentation, not a slide. The Day 1 baseline in this repository is enforced as a known-answer test precisely so it cannot quietly drift.",
    notes: `WHY: The single most transferable idea in the programme, and the one that most protects learners professionally.

SAY: "If you take one thing from three days, take this. Someone will ask you to commit to an automation percentage before anyone has measured anything. The correct answer is not a number. It is: 'give me a week with your payment file and I will tell you where you are, and then we can talk about where we could get to.'"

SAY: "That answer is harder to give and it is the one that keeps you credible eighteen months later, when the programme is being reviewed against whatever was promised at the start."

SAY: "Notice what this repository does about it. The Day 1 baseline — seventy percent match, forty percent straight-through — is not written in a document where it can rot. It is a known-answer test in verify_environment.py. If someone changes a rule and the distribution moves, the build tells them before a classroom does."

ASK: "Who in your organisation currently owns the baseline for the O2C process?" The answer is often nobody, and that is the most valuable thing anyone takes home.

TIME: 5 min`,
  },

  /* --------------------------------------------------------------- 12 */
  {
    layout: "closing",
    kicker: "CAPSTONE · CLOSE",
    headline: "One system, three days, every decision traceable to its evidence.",
    points: [
      "Six priority rules with 2-way and 3-way matching, deterministic and unit-tested",
      "Grounded deduction classification that declines to guess when the document says nothing",
      "A permissioned tool boundary where the model can recommend but never authorise",
      "Security gates, held transactions, and an audit trail that records refusals",
      "Durable state and a human in the loop — QUERY as a workflow step, not a dead end",
    ],
    next: "Take three things back: the two-numbers habit, the deterministic-versus-model split, and the four open questions. The questions are part of the deliverable — a specification gap found in week one is cheap, and the same gap found in UAT is a re-architecture.",
    notes: `WHY: Close on transferable judgement rather than on the tool stack. In six months they will not remember the API; they should remember the habits.

SAY: "Three things go home with you, and none of them is a framework."

SAY: "First, the two-numbers habit. Every flattering metric has an honest partner and only one of them reaches the slide. Report both, every time, and name the baseline."

SAY: "Second, the split. Deterministic Python for anything structured; the model only for prose. In this system the model did exactly one job — reading a customer's explanation — and everything else was code you can test. That ratio is what makes an agentic system deployable rather than merely impressive."

SAY: "Third, the open questions. Overpayment, split application, human-in-the-loop, MCP transport. You found four specific, sourced gaps in a specification that looked complete. That is not a caveat to the deliverable. On a real engagement it IS a large part of the deliverable, and it is the work a client cannot do for themselves."

ASK, finally: "What is the first thing you change on Monday?" Go round the room. It is the best close available and it surfaces where the real gaps are.

TIME: 6 min`,
  },
];

module.exports = { PALETTE, FONT, slides };
