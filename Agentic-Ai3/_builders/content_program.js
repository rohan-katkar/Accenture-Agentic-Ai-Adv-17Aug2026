/* =====================================================================
   content_program.js — SINGLE SOURCE OF TRUTH for the Day 0 kickoff deck.

   Purpose: the 45 minutes before Day 1 Lab 1. Orientation, environment setup,
   how the lab files work, and an honest statement of what is and is not built.

   Deliver this the afternoon BEFORE Day 1 if you can. Environment problems
   found at 16:00 the day before cost nothing; the same problems found at 09:40
   on Day 1 cost the room an hour.
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
    title: "Programme Kickoff & Environment Setup",
    subtitle: "Day 0 · 45 minutes · everything working before Lab 1 starts",
    footer: "Python 3.11+ · LangGraph · Azure AI Foundry · ChromaDB",
    notes: `WHY: Environment problems are the single largest destroyer of training-day momentum, and they are entirely preventable if you run this session the day before.

SAY: "This is the boring session that makes the next three days work. By the end of it every laptop in this room runs the verifier cleanly, and nobody spends Day 1 morning fighting pip."

SAY: "If you cannot get Azure credentials sorted today, that is fine and you will still do every lab. There is a full offline mode. I will show you how it works and, more importantly, what you may and may not claim from results produced that way."

ASK: "Who is on Windows, who is on macOS, who is on a locked-down corporate build?" The third group is the one to sit with. Corporate proxies and blocked PyPI mirrors are the usual blocker, not the code.

WATCH: Deliver this the AFTERNOON BEFORE Day 1 if at all possible. A problem found at 16:00 on Day 0 costs nothing. The same problem at 09:40 on Day 1 costs twenty people an hour.

TIME: 3 min`,
  },

  /* ---------------------------------------------------------------- 2 */
  {
    layout: "flow",
    title: "What you will build",
    subtitle: "One system across three days plus a capstone. Nothing here is a throwaway exercise.",
    steps: [
      { n: "1", h: "Day 1 — Foundations & Architecture", b: "A cash-application engine: six priority rules, typed state, a compiled state machine, correlated audit trails. Handles structured matching end to end." },
      { n: "2", h: "Day 2 — RAG & Tool-Augmented Agents", b: "Reads the unstructured remittance documents structured logic cannot. Vector search, grounded extraction, a permissioned tool boundary." },
      { n: "3", h: "Day 3 — Governance & Observability", b: "Prompt-injection defence, output redaction, security holds, audit replay. Makes it survivable in production." },
      { n: "★", h: "Capstone — Payment & Reconciliation", b: "Unifies the rule engine with deduction identification and cash application, adds durable state and a human in the loop." },
    ],
    notes: `WHY: People work harder when they can see that every lab is a component of one thing rather than fifteen disconnected exercises.

SAY: "Every lab builds a piece of the same system. Day 2 imports Day 1's rule engine unchanged. The capstone assembles all of it. If you fall behind, take the solution file for the previous lab and keep moving - do not silently drop out of the sequence, because the next day builds on top."

SAY: "The domain is order-to-cash because it has the two properties that make agentic AI both hard and worth doing: the data is genuinely messy, and getting it wrong moves real money."

ASK: "Who works with the O2C, accounts receivable or cash application process today?" Their questions will be the best ones all week, and you want to know who they are before Day 1.

WATCH: Anyone expecting a prompt-engineering course. Reset it kindly and now: "We write about twenty prompts across three days. We write a great deal more Python."

TIME: 4 min`,
  },

  /* ---------------------------------------------------------------- 3 */
  {
    layout: "table",
    title: "The ten transactions you will live with",
    subtitle: "Seed data engineered so every priority rule and every end state fires — including the ones the specification does not handle.",
    head: ["Txn", "What it teaches", "Day 1", "Day 2"],
    colW: [1.5, 5.6, 2.4, 2.4],
    rows: [
      ["BNK-1001", "priority 4, exact match — the happy path", "CLOSED", "CLOSED"],
      ["BNK-1002", "short payment, damage deduction, dispute raised", "PARTIAL_MATCH", "+ code D03"],
      ["BNK-1003", "variance inside the $10 tolerance", "CLOSED", "CLOSED"],
      ["BNK-1004", "payer known, invoice unknown", "UAC", "UAC"],
      ["BNK-1005", "blank sender — nothing to work with", "UIC", "UIC"],
      ["BNK-1008", "needs the remittance parsed for a 3-way match", "UAC", "3-way, exposes a gap"],
      ["BNK-1009", "short pay, remittance states no reason", "PARTIAL_MATCH", "QUERY — declines to guess"],
      ["BNK-1010", "overpayment — no end state exists for it", "QUERY", "QUERY"],
    ],
    callout: "This is a regression suite, not sample data. verify_environment.py enforces the Day 1 outcomes as a known-answer test — if a tuned threshold moves a row, the build fails before a classroom does.",
    notes: `WHY: Introducing the data on Day 0 means Day 1 Lab 3 does not stop to explain it, and it seeds the two most interesting findings early.

SAY: "Ten payments. Memorise BNK-1002 - it appears in almost every lab and it is the transaction we trace end to end on the capstone slide."

SAY on BNK-1009 and BNK-1010: "Two of these are deliberately unresolvable. BNK-1009's remittance says 'amount adjusted per internal review' - a customer declining to give a reason. BNK-1010 pays a thousand dollars MORE than the invoice, and the specification defines no end state for an overpayment. Both are real gaps we found in the source document, and we surface them rather than papering over them."

ASK: "Which row looks most like a payment you actually see?" Finance people will point at BNK-1008 or BNK-1004 immediately.

WATCH: The customer names are synthetic. State that explicitly - there is no real client data anywhere in this package.

TIME: 5 min`,
  },

  /* ---------------------------------------------------------------- 4 */
  {
    layout: "code",
    title: "Setup, in four commands",
    subtitle: "Do this now, together, before anyone leaves the room.",
    code: `python -m venv .venv && source .venv/bin/activate
# Windows:  .venv\\Scripts\\activate

pip install -r 00_Program/requirements.txt

cp 00_Program/.env.example .env          # then edit it

python 00_Program/verify_environment.py  # 0 = ready · 1 = blocked · 2 = warnings`,
    bullets: [
      "Python 3.11 or 3.12. The verifier refuses anything older and tells you so",
      "Use a virtual environment — chromadb and langgraph both pin transitive dependencies",
      "No credentials? Set LAB_OFFLINE_MODE=true and every lab still runs end to end",
      "Corporate proxy blocking PyPI is the usual blocker. Sort it today, not on Day 1",
    ],
    notes: `WHY: Doing this together, in the room, is the entire value of Day 0. Sending it as a pre-read means half the room arrives unconfigured.

SAY: "Run these four commands now. I will walk round. Do not skip the virtual environment - chromadb and langgraph both pin transitive dependencies and they will fight whatever is already in your system Python."

SAY on the exit codes: "The verifier returns 0, 1 or 2 and the difference matters. Zero means go. One means something is genuinely broken and you cannot start. Two means it works but there are things you should know before you make claims about the results - almost always that you are running offline."

WATCH: The three failure modes in order of frequency: no virtual environment, a corporate proxy blocking PyPI, and Python 3.10 or older on a locked corporate build. The third one needs IT and it needs them today.

DEMO: Run the verifier yourself on the projector, including deliberately with a broken .env, so the room recognises the output when they hit it.

TIME: 8 min`,
  },

  /* ---------------------------------------------------------------- 5 */
  {
    layout: "compare",
    title: "Three ways to run every lab",
    subtitle: "Chosen automatically by shared/foundry_client.py. You do not construct an SDK client anywhere.",
    columns: [
      {
        h: "Offline", tint: "MUTED",
        rows: ["Trigger: LAB_OFFLINE_MODE=true", "Model: deterministic keyword stub", "Embeddings: hashed bag-of-words, lexical", "Network: none at all", "Use for: dry runs, air-gapped rooms, dead keys"],
      },
      {
        h: "Path A — Azure OpenAI", tint: "TEAL",
        rows: ["Trigger: endpoint + key in .env", "Model: your chat deployment via the openai SDK", "Embeddings: your embedding deployment", "Stability: high, api_version pins behaviour", "Use for: THIS IS THE TEACHING PATH"],
      },
      {
        h: "Path B — Foundry project SDK", tint: "NAVY",
        rows: ["Trigger: USE_FOUNDRY_PROJECT_SDK=true", "Model: via AIProjectClient", "Resolves: connections and deployments centrally", "Stability: accessor has moved between releases", "Use for: demonstrate and flag, do not rely on"],
      },
    ],
    notes: `WHY: Sets expectations about which path is authoritative, and gets the version-risk disclosure said out loud before anyone builds on it.

SAY on offline: "Offline mode is not a degraded toy. Every lab runs end to end. What it cannot do is support a claim about model behaviour or retrieval QUALITY. The embedder is hashed bag-of-words - lexical, not semantic. 'Short paid' and 'underpaid' share no tokens and will not retrieve each other, though a real embedding model places them close together."

SAY, and mean it: "If a number leaves this room on a slide, the backend that produced it goes next to it. That is not pedantry - it is how a pilot avoids being committed to a target it structurally cannot hit."

SAY on Path B, honestly: "The azure-ai-projects client accessor has changed shape across its preview line and GA. Our client PROBES known shapes rather than hard-coding one, and fails loudly with the installed version number if none work. I am not going to present a single Path B signature as settled fact. Path A is what we teach; Path B is what we demonstrate and flag."

FLAG: Point them at 00_Program/VERSION_RISK_REGISTER.md. Every stale-able surface is listed with a confidence rating and a re-check action.

TIME: 6 min`,
  },

  /* ---------------------------------------------------------------- 6 */
  {
    layout: "cards4",
    title: "How the lab files work",
    subtitle: "Four artifacts per lab. You edit one; the other three are generated from it.",
    cards: [
      { icon: "◧", h: "solutions/labNN.py", b: "The complete, runnable lab. This is the ONLY hand-maintained file. Every other artifact is derived from it.", tag: "SOURCE OF TRUTH" },
      { icon: "◨", h: "labs/labNN.py", b: "The starter. Marked blocks become numbered TODOs with a hint. Fails loudly at the next unfinished blank it reaches.", tag: "WHAT YOU WORK IN" },
      { icon: "◫", h: "notebooks/labNN.ipynb", b: "The same starter as a notebook, with a bootstrap cell that puts the repo root on sys.path.", tag: "IF YOU PREFER JUPYTER" },
      { icon: "◪", h: "notebooks/..._solution.ipynb", b: "The complete lab as a notebook. Try each blank for ten minutes before opening it — the debugging is the lesson.", tag: "WHEN YOU ARE STUCK" },
    ],
    footnote: "One source, four artifacts. A fix applied to the solution but not the notebook is the most common defect in shipped lab packages — here it is structurally impossible.",
    notes: `WHY: Learners need to know which file to open and why there are four. It also lets you make the anti-drift point, which is a transferable engineering habit.

SAY: "Open the starter. Work top to bottom. It raises NotImplementedError at the next unfinished blank it reaches, which is how you know where you are."

SAY, because this trips people: "Blanks are numbered by POSITION IN THE FILE, not by execution order. A blank inside a function that is defined early but called late is reached after a later one. So a file can halt at blank 2 before blank 1. That is expected and the starter header says so."

SAY on the anti-drift point: "Notice what this buys us. Four artifacts, one hand-maintained file. If a figure changes, it changes once. The classic training-package defect - a fix applied to the solution but not the notebook - cannot happen here by construction. Steal the pattern."

SAY: "Try each blank for ten minutes before you open the solution. Particularly in Day 1 Lab 4, where a wrong customer-normalisation returns an empty match and no error at all - which is exactly the failure mode you will meet in production."

TIME: 5 min`,
  },

  /* ---------------------------------------------------------------- 7 */
  {
    layout: "cards3",
    title: "What the verifier actually checks",
    cards: [
      { icon: "①", h: "Packages and interpreter", b: "Imports every dependency rather than reading pip list — a package can be installed and still fail to import. Flags the Capstone-only checkpoint package separately.", tag: "BLOCKING" },
      { icon: "②", h: "Seed data and known answers", b: "Row counts, remittance-to-transaction links, and a known-answer test: all ten Day 1 end states must reproduce exactly.", tag: "BLOCKING" },
      { icon: "③", h: "Backends and version risks", b: "Which model path is live, whether the embedder is semantic or lexical, and which version-sensitive surfaces need re-checking today.", tag: "WARNINGS" },
    ],
    footnote: "Exit 2 means every lab will run, but read the warnings — each one changes what you may claim in the room.",
    notes: `WHY: The verifier is the trainer's most useful tool and it is usually run once and forgotten. Explaining what it does earns it a second run.

SAY on the second card: "The known-answer test is the part I would steal for your own projects. Ten transactions, ten expected end states, checked on every run. If someone tunes the relevance threshold and BNK-1003 stops closing, the build tells them before a classroom does."

SAY on the third card: "Read the warnings rather than skimming past them. 'Offline embedder in use' is not noise - it means any retrieval-quality statement you make today is unsupported."

TRAINER: Run this on the delivery laptop the MORNING OF each session, not just once at setup. Keys expire, deployments get deleted, and a corporate image update can break a native wheel overnight.

ASK: "What is your equivalent of a known-answer test at work?" Most teams have none, and it is the cheapest quality control available.

TIME: 5 min`,
  },

  /* ---------------------------------------------------------------- 8 */
  {
    layout: "table",
    title: "Troubleshooting — the five you will actually hit",
    subtitle: "In descending order of frequency, from building and running this package.",
    head: ["Symptom", "Cause", "Fix"],
    colW: [3.6, 4.2, 4.1],
    rows: [
      ["DeploymentNotFound on the first model call", "model= was given the model family name, not the deployment name", "Pass the deployment name exactly as it appears in the Foundry portal"],
      ["ModuleNotFoundError: shared", "Lab launched from a directory the bootstrap could not resolve", "Run from the repository root, or use the file as shipped — it walks up to find 00_Program"],
      ["Day 2 Lab 3 exits: collection is empty", "Day 2 Lab 1 was skipped; it builds the corpus", "Run Day 2 Lab 1 once, then re-run Lab 3"],
      ["Retrieval returns nothing sensible", "Offline lexical embedder, not a semantic one", "Expected. Switch to Path A for any retrieval-quality claim"],
      ["Starter halts at blank 2 before blank 1", "Blanks are numbered by file position, not execution order", "Expected. Fill both; the header explains it"],
    ],
    callout: "None of these is a code defect. All five are documented, four are printed as actionable error messages by the code itself, and the fifth is stated in the starter header.",
    notes: `WHY: Pre-empting the top five support tickets saves more classroom time than any other slide in this deck.

SAY on row 1: "This is the single most common issue across every Azure OpenAI project I have seen. If your deployment is called gpt4o-prod, you pass gpt4o-prod. Not gpt-4o. Write it down."

SAY on row 3: "Day 2 Lab 3 onward reads the collection Lab 1 builds. If you skip Lab 1 the lab exits with a message telling you exactly that - it does not fail mysteriously. That is deliberate: error messages are part of the courseware."

SAY on row 4: "Worth repeating because it is the one people misread as a bug. Lexical retrieval genuinely does return odd neighbours. It is not broken; it is the honest limit of a stub."

TRAINER: Keep this slide open on a second screen during labs. You will point at it repeatedly.

TIME: 5 min`,
  },

  /* ---------------------------------------------------------------- 9 */
  {
    layout: "cards4",
    title: "What is built, and what is not",
    subtitle: "Stated up front. Full detail in the Assumptions & Decisions Register.",
    cards: [
      { icon: "✓", h: "Day 1 — complete", b: "Deck, facilitation guide, 5 labs with starters and notebooks, reconciliation console. Every solution executed and passing.", tag: "BUILT + RUN" },
      { icon: "✓", h: "Day 2 — complete", b: "Deck, guide, 5 labs, remittance explorer. Run against real ChromaDB. All 1,559 validation checks pass.", tag: "BUILT + RUN" },
      { icon: "◐", h: "Day 3 — deck only", b: "Deck and guide are design-locked ahead of the labs so the control set is agreed first. Labs not yet built.", tag: "DESIGN LOCKED" },
      { icon: "!", h: "Capstone — blocked", b: "Deck and guide built. The build is blocked on gap G3: human-in-the-loop is required and taught in no Day 1–3 lab.", tag: "BLOCKED ON G3" },
    ],
    notes: `WHY: Say this on Day 0 rather than letting the room discover it on Day 3. Stating build status up front reads as competence; discovering it late reads as a mess.

SAY: "I want to be straight with you about the state of this package. Days 1 and 2 are complete and every lab has been executed. Day 3's deck and guide exist but its labs do not yet. The capstone build is blocked on a specific, documented gap."

SAY on gap G3: "The capstone's QUERY state - a payment that needs a human decision - requires LangGraph's interrupt mechanism and a durable checkpointer so the graph can suspend and resume. Neither is taught in Days 1 to 3 as originally scoped. So as things stand you can ROUTE to QUERY but you cannot RESUME from it, which means the capstone architecture cannot be implemented as drawn. The recommendation on record is a fifty-minute remediation lab before capstone day."

SAY: "There is a register with every open item, its severity and its remediation priority. That register is part of the deliverable, not a caveat to it."

WATCH: Deliver this as competence, not apology. Finding and documenting four specific, sourced gaps before delivery is exactly what a training architect is for.

TIME: 5 min`,
  },

  /* --------------------------------------------------------------- 10 */
  {
    layout: "cards3",
    title: "The governance artifacts",
    cards: [
      { icon: "▣", h: "Assumptions & Decisions Register", b: "Six sheets: assumptions, open questions, version risks, evidence classification, lab inventory. The workbook you hand a client sponsor.", tag: "XLSX" },
      { icon: "◈", h: "Version Risk Register", b: "Every technical surface that can go stale, with a confidence rating and a re-check action before delivery.", tag: "MARKDOWN" },
      { icon: "◉", h: "Curriculum Gap Analysis", b: "Five specification gaps and four curriculum gaps, severity-ranked with a remediation recommendation for each.", tag: "MARKDOWN" },
    ],
    footnote: "One entry to read before you quote anything: owning_team and sla_days per deduction code are a COURSEWARE INVENTION, not client specification. Replace them with the client's real ownership matrix.",
    notes: `WHY: These artifacts are what separate courseware from a slide pack, and learners should see the pattern even if they never open the files again.

SAY: "Every factual claim in this package is classified as one of four things: measured, client-specified, an assumption, or a courseware invention. That classification is in the Evidence Register sheet, and it is the discipline I most want you to steal."

SAY on the footnote: "Here is a worked example. The owning team and SLA attached to each deduction code - Quality owns damage claims with a ten-day SLA, and so on - are NOT in the client's specification. I invented them so you could see that a reason code alone is not actionable; routing is what makes it work. They are labelled as an invention in the register. If they reached a client deliverable unlabelled, that would be a fabricated credential."

SAY: "The measurement position is also in there: this courseware makes no productivity claim and asserts no automation target. Both are measurement problems requiring a baseline frozen on the client's own payment file before training begins."

TIME: 4 min`,
  },

  /* --------------------------------------------------------------- 11 */
  {
    layout: "statement",
    kicker: "THE HABIT TO BRING WITH YOU",
    headline: "Every flattering metric has an honest partner, and only one of them reaches the slide.",
    support: "Match rate and straight-through. Straight-through and coded-and-routed. Catch rate and false positives. The same shape appears on all three days. Report both, name the baseline, and state which backend produced the number.",
    notes: `WHY: Planting this on Day 0 means it lands as recognition rather than novelty each time it recurs.

SAY: "You will meet this three times over three days, and I am telling you now so you notice the pattern rather than the individual instances."

SAY: "Day 1: your match rate will be seventy percent and your straight-through rate forty percent. Both are true. They describe different things. Someone who reports only the first and calls it automation has overstated the business case by nearly half."

SAY: "Day 2: straight-through will barely move, and the day is still valuable - because it converts undifferentiated exception work into coded, routed, SLA-bearing work. That benefit is structurally invisible to a straight-through metric."

SAY: "Day 3: a filter with a perfect catch rate and a four percent false-positive rate gets switched off within a month, and then the catch rate is zero while the dashboard still shows green."

ASK: "Where does this pattern already show up in your own reporting?" It always does, and usually nobody has named it.

TIME: 4 min`,
  },

  /* --------------------------------------------------------------- 12 */
  {
    layout: "closing",
    kicker: "READY FOR DAY 1",
    headline: "Verifier green, virtual environment active, seed data understood.",
    points: [
      "python 00_Program/verify_environment.py returns 0 or 2 — and you have read the warnings",
      "You know which backend you are on and what that licenses you to claim",
      "You know which file to open: labs/ to work in, solutions/ when genuinely stuck",
      "You have skimmed the README and know where the two registers live",
      "You know BNK-1002 — you will meet it in almost every lab",
    ],
    next: "Day 1 opens with telemetry, not with a model. We build the audit trail before we build the agent, because when an automated posting credits the wrong customer at 2 a.m., the first question is not \"is the model good\" — it is \"show me what the system saw, and why it decided that.\"",
    notes: `WHY: A concrete readiness checklist, and a hook into Day 1 that explains why the first lab is about logging when everyone came for AI.

SAY: "Before you leave, get a green verifier. If yours is red, stay behind and we will fix it now. Do not go home planning to sort it in the morning."

SAY on the closing hook: "Day 1 Lab 1 is about structured logging, and some of you will wonder why. Here is why. When an automated cash application credits the wrong customer at two in the morning, finance does not ask whether the model is any good. They ask you to show them what the system saw and why it decided that. A print statement cannot answer that question. So we build the audit trail before we build the agent."

ASK: "Any blockers I should know about tonight?" Then go round the room individually rather than waiting for hands - the person with the broken corporate build will not volunteer.

WATCH: Collect the names of anyone still red. Those are the people to arrive early for on Day 1.

TIME: 3 min`,
  },
];

module.exports = { PALETTE, FONT, slides };
