/* =====================================================================
   content_day1.js  —  SINGLE SOURCE OF TRUTH for the Day 1 deck.

   Slide bodies and speaker notes live here and nowhere else. build_deck.js
   reads this file and renders. If a fact changes, it changes once.

   Speaker-note convention, so a substitute trainer can deliver cold:
     WHY .......... why this slide exists in the flow
     SAY .......... the spoken line, in delivery language
     ASK .......... the question to put to the room
     WATCH ........ the misconception to catch
     TIME ......... minutes on this slide
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
    title: "Foundations of Agentic AI, Azure Infrastructure & State Machines",
    subtitle: "Day 1 of 3 · followed by the Automated Payment & Reconciliation capstone",
    footer: "Order-to-Cash · LangGraph · Azure AI Foundry",
    notes: `WHY: Sets the contract for the day and signals that this is an engineering course anchored in a real finance process, not an LLM tour.

SAY: "Over three days you will build one system, not fifteen disconnected exercises. By 17:00 today you will have a working cash-application engine that reads a bank statement, matches payments against open receivables using six priority rules, and routes every exception to the right team — with a complete audit trail. Days 2 and 3 make it read unstructured remittance documents and survive a security review."

SAY: "The domain is order-to-cash because it has the two properties that make agentic AI hard and worth doing: the data is genuinely messy, and getting it wrong moves real money."

ASK: "Show of hands — who has touched LangGraph before? Who works with the O2C or AR process today?" Use the split to calibrate how much finance context to add.

WATCH: Anyone expecting a prompt-engineering course. Reset that expectation now, kindly: "We write about twenty prompts across three days. We write a lot more Python."

TIME: 3 min`,
  },

  /* ---------------------------------------------------------------- 2 */
  {
    layout: "flow",
    title: "The three-day arc",
    subtitle: "One system, built in layers. Each day is load-bearing for the next.",
    steps: [
      { n: "1", h: "Foundations & Architecture", b: "State machines, typed state, deterministic rule engine, telemetry, credentials. Handles structured matching end to end." },
      { n: "2", h: "RAG & Tool-Augmented Agents", b: "Vector search over remittance documents, grounded extraction, function calling. Unlocks the 3-way match and deduction reason codes." },
      { n: "3", h: "Governance & Observability", b: "Prompt injection defence, output redaction, security holds, audit replay. Makes it survivable in production." },
      { n: "★", h: "Capstone", b: "Unified rule engine plus deduction identification and cash application, as one deployable workflow." },
    ],
    notes: `WHY: People retain a course better when they can see where each piece lands. This slide is the map they will mentally return to.

SAY: "Notice the ordering. We do not start with the model. We start with the control flow and the audit trail, because those are what make a model call safe to put near money."

SAY: "Day 1 alone will already process a majority of a realistic payment file. That surprises people. The model is not the bulk of the value — it is the part that handles what structured logic cannot."

ASK: "If Day 1 handles most of the volume, why bother with Days 2 and 3?" Let them answer. The answer you want: the remainder is where the analyst time actually goes, and unhandled exceptions are what kill an automation programme's credibility.

WATCH: Do not let anyone leave thinking Day 1 is preamble. Today's output is a working system.

TIME: 3 min`,
  },

  /* ---------------------------------------------------------------- 3 */
  {
    layout: "statement",
    kicker: "THE BUSINESS PROBLEM",
    headline: "Corporate customers almost never pay the way your ERP expects.",
    support: "They pay one lump sum against a dozen invoices. They withhold money for damaged goods without telling you which invoice. They quote their own purchase-order number instead of yours. Someone wires money with a blank reference field.",
    notes: `WHY: Grounds the whole course in the actual mess. Engineers who have never sat with a cash-application team assume this is a tidy join on invoice number.

SAY: "If every customer paid one invoice, in full, quoting your invoice number, this course would not exist. A SQL join would do it. Everything we build over three days exists because of the four behaviours on this slide."

SAY: "Walk through them slowly. Lump-sum payments break the one-to-one assumption. Deductions break the amount-equality assumption. Customer PO references break the identifier assumption. Blank metadata breaks the identity assumption. Each one takes out a different guarantee your code wanted to rely on."

ASK: "For those who work in finance operations — what is the fifth behaviour I have not listed?" You will usually get: partial payments across periods, currency and FX differences, or payments from a parent entity settling a subsidiary's invoices. All are real. Note them on the whiteboard; they become stretch goals.

WATCH: Engineers who say "we would just mandate a payment reference." Gently: your customer's AP department does not work for you.

TIME: 4 min`,
  },

  /* ---------------------------------------------------------------- 4 */
  {
    layout: "cards3",
    title: "Three master data sources, three different problems",
    cards: [
      { icon: "◫", h: "Bank Statement", b: "Confirmed money in. Trustworthy amounts, unreliable narrative text. The customer name is whatever the payer typed.", tag: "STRUCTURED · MESSY TEXT" },
      { icon: "▤", h: "ERP Accounts Receivable", b: "Open invoices, PO numbers, delivery notes, dates, amounts. Clean and authoritative — this is your ground truth.", tag: "STRUCTURED · CLEAN" },
      { icon: "✉", h: "Remittance Advice", b: "PDFs, emails, scanned attachments. Contains the invoice breakdown and the reason for every deduction. No schema at all.", tag: "UNSTRUCTURED" },
    ],
    footnote: "The reason for a deduction exists only in the third source — and only in prose.",
    notes: `WHY: This slide explains the entire architecture in advance. Each source's shape determines the tool you reach for.

SAY: "Three sources, three completely different engineering problems. The bank statement is structured but its text fields are free-form. The ERP is clean and is your ground truth. The remittance advice has no schema whatsoever — it is a human writing to another human."

SAY: "Here is the line to remember all week: the reason a customer withheld five hundred dollars exists in exactly one place, and that place is prose. No amount of SQL will get it out. That is the whole business case for retrieval-augmented generation on Day 2 — not that RAG is fashionable, but that this specific fact lives in an unstructured document."

ASK: "Which of these three would you attack with a language model?" Push until they land on: only the third, and only for the parts that are genuinely prose.

WATCH: The instinct to send everything through the model 'because it can handle it'. Latency, cost and auditability all say otherwise. We quantify this in Lab 2.

TIME: 4 min`,
  },

  /* ---------------------------------------------------------------- 5 */
  {
    layout: "compare",
    title: "Chatbot vs. autonomous agent vs. state machine",
    subtitle: "Three architectures. Only one of them belongs near a general ledger.",
    columns: [
      {
        h: "Chatbot", tint: "MUTED",
        rows: ["Memory: a list of messages", "Next step chosen by: the user", "Reproducible: no", "Audit artifact: a transcript", "Fits a controlled finance process: no"],
      },
      {
        h: "Autonomous agent", tint: "TEAL",
        rows: ["Memory: model-managed scratchpad", "Next step chosen by: the model", "Reproducible: rarely", "Audit artifact: an unstable reasoning trace", "Fits a controlled finance process: no"],
      },
      {
        h: "State machine", tint: "NAVY",
        rows: ["Memory: a typed record you define", "Next step chosen by: your routing function", "Reproducible: yes, given the same state", "Audit artifact: every transition, replayable", "Fits a controlled finance process: yes"],
      },
    ],
    notes: `WHY: This is the intellectual centre of Day 1. Everything downstream follows from choosing the third column.

SAY: "Read across the rows, not down the columns. The differences that matter are who chooses the next step, and what you can hand an auditor afterwards."

SAY: "'The model decided' is not an acceptable answer to an auditor asking why five hundred dollars was written off. That single sentence is why we build state machines in this course."

ASK: "Where is the autonomous-agent column genuinely the right answer?" Good answers: open-ended research, exploratory code, anything where the space of next steps is not enumerable in advance. Bad answer: 'anywhere, it is more flexible.'

WATCH: This is not an argument that agents are bad. It is an argument about fit. Say that explicitly, or you will lose the people who came in excited about agents.

SAY: "One more thing — the third column is not a rejection of AI. The model still does the job it is uniquely good at. It just does not get to choose the control flow."

TIME: 6 min`,
  },

  /* ---------------------------------------------------------------- 6 */
  {
    layout: "table",
    title: "The six end states",
    subtitle: "Every payment terminates in exactly one of these. The state determines who owns the follow-up.",
    head: ["#", "End state", "Meaning", "Owner"],
    colW: [0.5, 2.0, 5.3, 2.7],
    rows: [
      ["1", "OPEN", "Uploaded, not yet matched to AR or remittance", "System"],
      ["2", "PARTIAL MATCH", "Matched, but with a variance", "Deductions analyst"],
      ["3", "CLOSED", "Fully matched, or variance within tolerance", "— settled —"],
      ["4", "UAC", "Un-applied Cash: payer known, invoice unknown", "Cash Application"],
      ["5", "UIC", "Un-identified Cash: payer unknown", "Treasury"],
      ["6", "QUERY", "Low confidence or an edge case; needs judgement", "Human-in-the-loop queue"],
    ],
    callout: "GAP: there is no end state for an overpayment. Seed transaction BNK-1010 pays $12,000 against an $11,000 invoice. Raise this with the client rather than inventing a state.",
    notes: `WHY: The end states are the schema, the report, and the operating model all at once. Learners must know them cold before Lab 3.

SAY: "Put the owner column in front of the finance people in the room and watch them nod. The end state is not a technical label — it decides whose queue the item lands in tomorrow morning."

SAY: "UAC versus UIC trips everyone up. The test is one question: do we know who paid? If yes, Cash Application posts it on account and chases an allocation. If no, Treasury has to go to the bank before anything can post at all. Different team, different SLA, different cost."

SAY (the gap, deliberately): "Now the honest part. The specification defines six states and none of them describes an overpayment. Our seed data has one — twelve thousand dollars against an eleven thousand dollar invoice. It is not PARTIAL MATCH, because that describes a shortfall. It is not CLOSED, because a thousand dollars is sitting unapplied. We route it to QUERY and we flag it as an open question. Do not paper over a specification gap; find it in week one, not in production."

ASK: "How many end states does your current process actually have?" The answer is usually more than six, and usually undocumented.

WATCH: Also flag the smaller inconsistency: the end-state table defines UAC as 'no invoice details AND no remittance advice', while Example D in the same document defines it as 'customer identified, invoice unknown'. Those are different tests. We implement the second reading. Log it as a question.

TIME: 7 min`,
  },

  /* ---------------------------------------------------------------- 7 */
  {
    layout: "table",
    title: "The six priority rules",
    subtitle: "Evaluated in order. First match wins. Order encodes evidential strength, not convenience.",
    head: ["Pri", "Bank evidence", "Matched against", "Type"],
    colW: [0.7, 4.0, 4.1, 1.7],
    rows: [
      ["1", "Customer + PO number + amount", "ERP: customer + PO → invoice", "2-way"],
      ["2", "Customer + delivery number + amount", "ERP: customer + delivery → invoice", "2-way"],
      ["3", "Customer + invoice + invoice date + amount", "ERP: same four fields", "2-way"],
      ["4", "Customer + invoice number + amount", "ERP: customer + invoice", "2-way"],
      ["5", "Customer bank payment", "ERP + remittance: customer + PO + invoice + date", "3-way"],
      ["6", "Customer bank payment", "ERP + remittance: customer + PO + invoice", "3-way"],
    ],
    callout: "Rules 5 and 6 need the remittance document parsed. They are written and tested on Day 1, but return nothing until Day 2. That is deliberate scaffolding — and it is why BNK-1008 stays unmatched this afternoon.",
    notes: `WHY: These six rules are the core deliverable of Lab 4. The class implements them directly from this slide.

SAY: "Why is PO number priority one and invoice number priority four? Because a customer quoting their own purchase order is being unambiguous about which commercial commitment they are settling. Your invoice number is your identifier; their PO is theirs. When they use theirs, they are telling you something more specific."

SAY (the one they will get wrong): "Look closely at what a rule does NOT do. It does not check that the amounts are equal. A short payment must still match its invoice — otherwise you can never work out what was deducted. Matching and variance analysis are two separate steps. Collapsing them is the single most common design error in cash application, and it produces a system that silently drops every deduction."

ASK: "What happens when two rules could both match?" Answer: they cannot, by construction — evaluation stops at the first hit. But record WHICH rule fired, because that is your evidence trail.

WATCH: Someone will ask why this is not a model call. Hold that question for slide 9 — it lands harder there.

TIME: 8 min`,
  },

  /* ---------------------------------------------------------------- 8 */
  {
    layout: "worked",
    title: "Worked example: a short payment",
    subtitle: "BNK-1002 · the transaction you will trace through every lab today",
    steps: [
      { k: "Bank statement", v: "ACME CORPORATION · $9,500.00 · reference \"PO-5541\"" },
      { k: "Normalisation", v: "\"ACME CORPORATION\" → \"Acme Corp\"; extract PO-5541 from free text" },
      { k: "Priority 1 fires", v: "customer + PO-5541 → invoice INV-810, billed $10,000.00" },
      { k: "Variance", v: "$9,500.00 − $10,000.00 = −$500.00 · beyond the $10 tolerance" },
      { k: "Remittance says", v: "\"Five units arrived crushed and unusable… we have withheld $500.00\"" },
      { k: "Reason code", v: "D03 Damage Claim · Quality team owns it · 10-day SLA" },
      { k: "Outcome", v: "Apply $9,500 · open a $500 dispute · end state PARTIAL MATCH" },
    ],
    notes: `WHY: One concrete transaction, carried through every abstraction, is worth more than three abstract explanations.

SAY: "This one payment exercises almost the whole system. Keep it in your head — it appears in Lab 1's telemetry demo, Lab 4's rule engine, Lab 5's compiled graph, and it is the first document we retrieve on Day 2."

SAY: "Notice the normalisation step. 'ACME CORPORATION' and 'Acme Corp' are the same customer, and no rule fires until you resolve that. In my experience most real reconciliation failures trace back to this step, not to the matching logic. Budget for it in your estimates."

SAY (pointing at the remittance line): "Everything above that line is deterministic Python. That line and the one below it need a language model, because the reason lives in prose. That is the split we defend for the rest of the course."

ASK: "What is the cost of getting the reason code wrong — of calling this D01 Pricing instead of D03 Damage?" Answer: it goes to the wrong team, sits in the wrong queue, misses its SLA, and the customer chases you. Wrong-but-confident is worse than 'I don't know'.

TIME: 6 min`,
  },

  /* ---------------------------------------------------------------- 9 */
  {
    layout: "statement",
    kicker: "THE ARCHITECTURAL DECISION",
    headline: "The rule engine is deterministic Python. It is not a model call.",
    support: "Reproducible · free · explainable · unit-testable. The model is reserved for the one job it is uniquely good at: reading unstructured remittance prose. Everything structured stays in code.",
    notes: `WHY: If they take one thing away from three days, it should be this. Give it its own slide and its own silence.

ASK FIRST, before revealing the support text: "We have a language model available. Why on earth would we hand-write six matching rules instead of describing them in a prompt?" Take answers for a full minute.

SAY: "Four reasons, and they compound. Reproducible: same input, same output, every time — which is what auditable means. Free: five thousand payments a night at two calls each is real latency and real spend, for a task a regex does perfectly. Explainable: 'priority four matched on customer plus invoice' beats 'the model thought so' in every conversation you will ever have with a controller. Testable: a rule table has unit tests; a prompt does not, in the same sense."

SAY: "In Lab 2 you will measure your own endpoint's latency and multiply it out. Do not take my word for the cost argument — take your own number."

WATCH: This is not anti-AI. Say so. "We use the model precisely where it beats code, and nowhere else. That discipline is what makes the system deployable."

TIME: 5 min`,
  },

  /* --------------------------------------------------------------- 10 */
  {
    layout: "cards4",
    title: "The technical stack, and what each piece is actually for",
    cards: [
      { icon: "◆", h: "LangGraph", b: "State machine. Controls flow, branches for 2-way and 3-way matches, and suspends for human input on QUERY.", tag: "ORCHESTRATION" },
      { icon: "◈", h: "Azure AI Foundry", b: "Model endpoint and identity. Parses unstructured remittance PDFs and emails; maps prose to reason codes D01–D05.", tag: "MODEL + IDENTITY" },
      { icon: "◇", h: "MCP tools", b: "Structured, permissioned tool calls into ERP SQL and bank ledger files — without exposing the database to the agent.", tag: "INTEGRATION" },
      { icon: "◉", h: "Guardrails & observability", b: "Blocks hallucinated match keys, prevents mis-posting, and logs complete reasoning traces for audit.", tag: "CONTROL" },
    ],
    notes: `WHY: Resolves the orchestration question directly, and pre-empts the 'which framework owns what' confusion that stalls architecture reviews.

SAY: "This answers a question that comes up in every one of these engagements: is LangGraph or Foundry the orchestrator? They are not competitors here. LangGraph owns control flow. Foundry owns the model endpoint and identity. They sit at different layers."

SAY: "MCP deserves a sentence. The agent never gets a database connection. It gets a tool with a defined signature that returns defined data. That boundary is what your security architect will ask about first, and 'we gave the LLM read access to the AR tables' is not an answer that survives the meeting."

FLAG HONESTLY: "MCP appears in the capstone architecture but is not taught in Days 1 to 3 as written. Neither is human-in-the-loop, which the QUERY state requires. We flag both as curriculum gaps rather than discovering them on capstone day — see the gap analysis in your programme folder."

WATCH: Do not let this become a tools slide. Each row is a layer with a job.

TIME: 5 min`,
  },

  /* --------------------------------------------------------------- 11 */
  {
    layout: "code",
    title: "The state schema is the contract",
    subtitle: "A typed record every node reads and writes. Get this wrong and every downstream node compensates with defensive .get() calls.",
    code: `class ReconciliationState(TypedDict, total=False):
    run_id: str                 # correlation across the whole run
    txn_id: str

    bank_customer_raw: str      # exactly as the payer typed it
    bank_amount_usd: float      # Decimal in production - see note
    bank_reference: str

    matched_invoice: str        # written by the rule engine
    matched_priority: int       # WHICH rule fired = the evidence trail
    variance_usd: float

    reason_code: ReasonCode     # Literal["D01".."D05","UNKNOWN"]
    end_state: EndState         # Literal of the six terminal states

    trace: Annotated[list[str], operator.add]   # accumulates
    errors: Annotated[list[str], operator.add]`,
    bullets: [
      "total=False — nodes populate fields progressively; requiring all keys up front forces placeholder lies",
      "Literal types make a typo like \"CLOSSED\" a type error, not a midnight incident",
      "The audit trail lives IN the state. If it is not in the state, it did not happen",
      "float here for readability; decimal.Decimal in production — 0.1 + 0.2 != 0.3 in binary floating point",
    ],
    notes: `WHY: Lab 3 is this slide. Learners write this schema themselves.

SAY: "A chatbot's memory is a list of messages. A state machine's memory is a typed record that every node reads and writes. That record is the contract between nodes, and in a financial system it is also the audit object."

SAY on Annotated: "This is the detail that bites people. By default, LangGraph replaces a field when a node returns it. For end_state, replace is correct — the last writer wins. For trace, replace is a bug: node B wipes node A's entry. The Annotated reducer says append instead. Get it wrong and your audit trail contains only the last node's line, and nobody notices until an audit asks for the full path."

SAY on money: "Say this out loud with me — float is wrong for money. We use it in the labs because it reads better on a projector. Your production integration uses Decimal. I am telling you this now so it does not slip through silently."

ASK: "Should the full remittance text live in the state? It could be forty kilobytes, and every checkpoint persists the whole state." There is no single right answer. Naming the trade-off is the skill.

TIME: 7 min`,
  },

  /* --------------------------------------------------------------- 12 */
  {
    layout: "code",
    title: "Nodes and conditional edges",
    subtitle: "A node takes state and returns a partial dict. A router takes state and returns a label. That is the whole API surface.",
    code: `def node_rule_engine(state: GraphState) -> dict:
    for rule in PRIORITY_RULES:                # 1..6, first hit wins
        result = rule(bank, AR_OPEN, remit)
        if result:
            return {                           # PARTIAL dict, never the whole state
                "matched_invoice":  result.invoice_no,
                "matched_priority": result.priority,
                "variance_usd":     bank_amt - result.erp_amount,
                "trace": [f"priority {result.priority} - {result.rationale}"],
            }
    return {"matched_priority": 0, "trace": ["no rule matched"]}

def route_after_matching(state) -> str:        # pure read. no mutation, no model
    return "matched" if state.get("matched_priority") else "exception"

builder.add_conditional_edges(
    "rule_engine", route_after_matching,
    {"matched": "variance_analysis", "exception": "classify_exception"})`,
    bullets: [
      "Return only the keys you changed — returning the whole state makes reducers meaningless",
      "A router must not mutate state and must not call a model; it reads a decision already made",
      "A label the mapping does not cover is a runtime error — silent fall-through in a payment system is how money goes missing",
      "Write the trace line in business language. The analyst reads it at 08:00, not your variable names",
    ],
    notes: `WHY: Labs 4 and 5 are this slide. It is the smallest complete statement of the LangGraph programming model.

SAY: "Three API calls do all the work: add_node registers a unit of work, add_edge is an unconditional transition, add_conditional_edges chooses at runtime. That is genuinely the whole surface."

SAY: "Two habits to build now because they pay off in the capstone. First, return a partial dict. Second, write the trace line for a human being who does not work in engineering."

DEMO IF TIME: Delete one key from the conditional mapping and run it. The error is loud and specific. Say: "That is LangGraph refusing to guess. In a payment system, that refusal is a feature."

ASK: "Any Python programmer can write this control flow with if/elif. What does the compiled graph actually buy you?" Push past 'it looks nicer' to: inspectable topology as data, checkpoint and resume, per-node observability, and a routing surface you can unit-test on its own.

TIME: 7 min`,
  },

  /* --------------------------------------------------------------- 13 */
  {
    layout: "cards3",
    title: "Telemetry before intelligence",
    cards: [
      { icon: "①", h: "One JSON object per line", b: "Log Analytics and jq both ingest it with no custom parser. A sentence is not a data structure.", tag: "MACHINE-PARSEABLE" },
      { icon: "②", h: "One run_id across every node", b: "Correlation is what turns a pile of events into an audit trail you can replay.", tag: "CORRELATED" },
      { icon: "③", h: "Automatic key redaction", b: "api_key, authorization, bank_account masked recursively at the logging boundary — the earliest point a secret can escape.", tag: "SAFE BY DEFAULT" },
    ],
    footnote: "Lab 1 builds the audit trail before Lab 5 builds the agent. That ordering is deliberate.",
    notes: `WHY: Justifies why Lab 1 is about logging when everyone came for AI. Do not skip the justification — you will lose the room otherwise.

SAY: "When an automated cash application credits the wrong customer at two in the morning, the first question finance asks is not 'is the model any good'. It is 'show me what the system saw, and why it decided that'. A print statement cannot answer that. So we build the audit trail before we build the agent."

SAY: "The redaction is deliberately blunt — it keys off the field name, recursively, at any depth. Blunt is correct for a control that must never silently fail."

ASK: "Where does name-based redaction fail?" Answer you want: free-text. A remittance note that quotes a bank account number sails straight through, because the field is called remittance_text. Day 3 builds the content-based control that catches it.

SAY: "One more framing for the finance people: the cost driver in O2C automation is not the model, it is exception-handling labour. Teams that cannot explain an automated posting escalate it to a human, and the automation rate collapses. Traces are what let an analyst confirm a decision in seconds instead of reproducing it."

TIME: 5 min`,
  },

  /* --------------------------------------------------------------- 14 */
  {
    layout: "code",
    title: "Credentials: build the seam on day one",
    subtitle: "Azure SDKs authenticate through a credential object, not a string. That indirection is what lets a key-based classroom become an identity-based production deployment with no change to calling code.",
    code: `class StaticTokenCredential:
    """Satisfies the azure.core TokenCredential protocol with a fixed token."""
    def get_token(self, *scopes, **kwargs) -> AccessToken:
        return AccessToken(self._token, int(time.time()) + self._ttl)

# No lab ever constructs an SDK client. Every lab calls this:
client = get_chat_client()      # -> offline stub | Azure OpenAI | Foundry project SDK`,
    bullets: [
      "PRODUCTION: DefaultAzureCredential or ManagedIdentityCredential — never a static token",
      "model= takes the DEPLOYMENT name, not the model family name. This is the #1 day-one support ticket",
      "One seam means an SDK breaking change costs one file, not fifteen labs",
      "Offline mode runs every lab with a deterministic stub — for dry runs, air-gapped rooms and dead-key mornings",
    ],
    notes: `WHY: Authentication and coupling are what stall agentic pilots at the enterprise gate — not model quality. Building the seam on the first afternoon means the security review is a conversation about an existing design rather than a request to rewrite one.

SAY: "The static token adapter is a teaching and break-glass construct. Shipping it to production means a non-rotating secret in process memory with no revocation story. Put that sentence in your architecture decision record, not just in your notes."

SAY (the ticket): "Say this with me: model equals the deployment name. If your deployment is called gpt4o-prod, you pass gpt4o-prod. Not gpt-4o. This one fact accounts for more day-one support tickets than everything else combined."

FLAG HONESTLY: "The Foundry project SDK has changed shape across its preview line. Our client probes for a working accessor rather than hard-coding one, and fails loudly with the installed version number if none works. Do not present any single Foundry call signature to a client as settled — verify it against current Microsoft Learn docs on the delivery machine. There is a version risk register in your programme folder listing exactly what to re-check."

TIME: 6 min`,
  },

  /* --------------------------------------------------------------- 15 */
  {
    layout: "flow",
    title: "Day 1 laboratory sequence",
    subtitle: "Five labs, roughly 3 hours 40 minutes. Each one is a component of the same system.",
    steps: [
      { n: "1", h: "Environment & telemetry · 35 min", b: "Verify dependencies. Build the JSON-lines logger with automatic redaction and correlated run tracing." },
      { n: "2", h: "Endpoint & authentication · 40 min", b: "The credential adapter and the model seam. Classify a real remittance note. Measure your endpoint latency." },
      { n: "3", h: "State memory schema · 40 min", b: "TypedDict, Literal end states, reducers, and a runtime validator. Load ten real bank rows." },
      { n: "4", h: "Nodes & branching rules · 50 min", b: "Implement all six priority rules and the routing functions. Measure the structured match rate." },
      { n: "5", h: "Compile & invoke · 55 min", b: "Assemble the graph, invoke it, stream it, and freeze the Day 1 baseline metrics." },
    ],
    notes: `WHY: Learners work better when they can see the shape of the afternoon and know that nothing is throwaway.

SAY: "Every lab ships in two forms: a starter file with numbered blanks, and the complete solution. Both are also Jupyter notebooks if you prefer that. The starter fails loudly at the next unfinished blank, which is how you know where you are."

SAY: "Try each blank for ten minutes before you open the solution. The debugging is the lesson — particularly in Lab 4, where a wrong customer-normalisation returns an empty match and no error at all."

SAY: "Lab 4 depends on Lab 3's schema; Lab 5 imports Lab 4's rule engine directly. If you fall behind, take the solution file for the previous lab and keep moving. Do not silently drop out of the sequence."

WATCH: Lab 1 is the canary. If chromadb or langgraph failed to install, you find out at 09:40 rather than at 14:30 tomorrow with twenty people waiting.

TIME: 3 min`,
  },

  /* --------------------------------------------------------------- 16 */
  {
    layout: "stats",
    title: "Two numbers, and why conflating them overstates the business case",
    stats: [
      { big: "Match rate", small: "A priority rule found an invoice. Measured from your own run of Lab 4." },
      { big: "Straight-through", small: "Closed with no human touch. Always the lower number. Measured from Lab 5." },
    ],
    body: "A payment can match its invoice perfectly and still need a human. BNK-1002 matches on priority 1 and still raises a $500 damage dispute. Report both numbers, always. Freeze them before any automation target is agreed.",
    notes: `WHY: This is the measurement discipline that separates a credible programme from an overstated one. It also protects the learners in their own client conversations.

SAY: "You will produce both numbers yourself this afternoon, from the seed data. I am deliberately not putting figures on this slide, because the number that matters is the one you measure — and on your own client's data it will be different."

SAY: "Here is the failure mode. Someone reports the match rate to a steering committee, calls it automation, and commits to improving it. Then the deductions queue does not shrink, because matching was never the bottleneck. Reporting the higher number is the most common way an automation business case gets overstated."

SAY (the important one): "Any automation target — thirty percent, fifty percent, whatever the number is — is a measurement problem before it is a training outcome. You cannot improve a percentage against a baseline that does not exist. Freeze the baseline first. That is a week of instrumentation, not a slide."

DEMO: In the web console, drag the tolerance slider from ten dollars to five hundred. Straight-through jumps. Ask what just happened. Answer: you improved a metric by writing off a customer's damage claim without recording that they made one. The metric alone will not tell you that.

TIME: 6 min`,
  },

  /* --------------------------------------------------------------- 17 */
  {
    layout: "cards4",
    title: "Open questions we are carrying forward",
    subtitle: "Flagged deliberately. A specification gap found in week one is cheap; found in production it is not.",
    cards: [
      { icon: "!", h: "No overpayment end state", b: "BNK-1010 pays $12,000 against $11,000. Fits none of the six states. Routed to QUERY pending a client decision.", tag: "SPEC GAP" },
      { icon: "!", h: "UAC defined two ways", b: "The end-state table and Example D give different tests. We implement the Example D reading and log the question.", tag: "SPEC CONFLICT" },
      { icon: "!", h: "Human-in-the-loop not taught", b: "The QUERY state needs interrupt and a checkpointer. Neither appears in Days 1–3 as written.", tag: "CURRICULUM GAP" },
      { icon: "!", h: "MCP not taught", b: "MCP tools are in the capstone architecture but in no Day 1–3 lab. Same for Pydantic-validated structured output.", tag: "CURRICULUM GAP" },
    ],
    notes: `WHY: Naming what is unresolved builds more trust than pretending everything is settled, and it protects the delivery from a capstone-day surprise.

SAY: "I want to be direct about four things this course does not yet resolve. Two are gaps in the business specification, and two are gaps in the curriculum as written."

SAY: "The specification gaps are the client's to decide, not ours to invent. We route the overpayment to QUERY, we implement one reading of UAC, and we write both down as questions. That is the professional move."

SAY: "The curriculum gaps are ours. The capstone's QUERY state requires LangGraph's interrupt mechanism and a durable checkpointer, and no Day 1 to 3 lab teaches them. Same for MCP tools, and same for Pydantic-validated structured output — the labs currently parse JSON defensively, which is not the same as validating it. Full detail is in the gap analysis in your programme folder, with a recommended remediation for each."

WATCH: Deliver this as competence, not apology. Finding four specific, sourced gaps before delivery is what a training architect is for.

TIME: 4 min`,
  },

  /* --------------------------------------------------------------- 18 */
  {
    layout: "closing",
    kicker: "END OF DAY 1",
    headline: "You have a working cash-application engine.",
    points: [
      "Six priority rules, deterministic and unit-tested",
      "A compiled state machine with an inspectable topology",
      "Correlated JSON audit trails with automatic secret redaction",
      "A credential seam that survives the move to managed identity",
      "Two frozen baseline metrics, measured rather than asserted",
    ],
    next: "Tomorrow: BNK-1008 still has no match and BNK-1002 still has no reason code. Both live in an unstructured remittance document. That is Day 2 — vector search, grounded extraction, and tool-augmented graphs.",
    notes: `WHY: Close on the artifact, not the concepts. People remember what they built.

SAY: "Before you leave, write down two numbers: your match rate and your straight-through rate. Bring them tomorrow. Every claim we make on Day 2 gets measured against them."

SAY: "Two transactions are unfinished on purpose. BNK-1008 has fifteen thousand dollars and a bank reference that just says 'remittance attached' — the money is real, the match is impossible with structured data alone. BNK-1002 has a five hundred dollar deduction with no reason code, so it sits in a queue nobody can action. Both are solved tomorrow, and both are solved by reading a document."

ASK: "Overnight, think about one thing: which parts of your own O2C process look like BNK-1008?"

WATCH: If anyone is behind on labs, point them to the solutions folder and the notebooks. Nobody starts Day 2 without a compiled graph — Day 2 builds directly on top of it.

TIME: 4 min`,
  },
];

module.exports = { PALETTE, FONT, slides };
