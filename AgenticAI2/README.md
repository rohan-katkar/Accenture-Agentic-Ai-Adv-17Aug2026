# Accenture Batch 1 — Agentic AI Foundation

Production-ready courseware for a 3-day programme plus a unified capstone, built
around a single running system: an **order-to-cash payment reconciliation engine**
using LangGraph for orchestration and Azure AI Foundry for model access.

Every lab, deck slide and web application operates on the same seed data and the
same growing codebase. Nothing is a throwaway exercise.

---

## Build status

| Component | Status |
|---|---|
| Day 0 — Kickoff & environment setup | **complete** — deck + facilitation guide |
| Shared platform (`shared/`) | **complete, executed** |
| Day 1 — Foundations & Architecture | **complete, executed** — deck, 5 labs, web app |
| Day 2 — RAG, Vector Search & Tools | **complete, executed** — 5 labs, web app |
| Day 3 — Governance & Observability | **complete, executed** — deck, guide, 6 labs |
| Capstone — Payment & Reconciliation | **complete, executed** — deck, guide, `src/`, tests (7/7), console |
| Gap remediation lab (HITL, gap G3) | **complete** — Day 3 Lab 6; capstone now unblocked |

> **Design-locked** means the deck and facilitation guide were written before the
> labs, so scope, narrative and acceptance criteria are agreed first. Their
> lab-referencing slides describe *intended* labs. Both files carry a build-status
> warning at the top of their content source. Re-run `build_all.sh` and re-check
> those slides once the labs land.

Every lab in Days 1–2 was **run to completion** during the build. The Day 1
baseline is enforced as a known-answer regression test.

---

## Quick start

```bash
bash setup.sh          # macOS / Linux / WSL / Azure ML compute
.\setup.ps1            # Windows PowerShell
```

Creates a virtual environment, installs the pinned dependencies, writes `.env`
from the template, builds the Day 2 vector corpus, and runs the verifier.

**Four supported environments** — local VS Code, local Jupyter, GitHub Codespaces,
and an Azure ML compute instance. Full instructions, a decision matrix and
troubleshooting: **`00_Program/LAB_ENVIRONMENT_GUIDE.md`** (also shipped as
`Lab_Environment_Guide.docx` for the printed trainer pack).

Prefer to do it by hand:

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r 00_Program/requirements.txt
cp 00_Program/.env.example .env                        # then edit it
python 00_Program/verify_environment.py                # 0 = ready, 1 = blocked, 2 = warnings
```

**No Azure credentials?** Set `LAB_OFFLINE_MODE=true` in `.env`. Every lab runs
end to end against a deterministic stub. Read the honesty labels in
`00_Program/VERSION_RISK_REGISTER.md` section D before quoting any number
produced that way.

---

## Layout

```
.devcontainer/       Codespaces / Dev Containers image, post-create bootstrap
.vscode/             interpreter paths, 5 debug configurations, extension list
setup.sh setup.ps1   one-command bootstrap (bash / PowerShell)
environment.yml      conda environment for Azure ML compute instances
00_Program/          environment guide, requirements, .env template, verifier,
                     risk register, gap analysis, Assumptions & Decisions Register (.xlsx)
shared/              config, telemetry, model seam, vector-store seam, seed data
Day1_Foundations/    deck (.pptx) · facilitation guide (.docx) · labs/ · solutions/ · notebooks/ · webapp/
Day2_RAG/            deck · guide · labs/ · solutions/ · notebooks/ · webapp/
Day3_Governance/     deck · guide · labs/ · solutions/ · notebooks/
Capstone/            deck · guide · src/ · tests/ · webapp/ · docs/BUILD_GUIDE.md
_builders/           content sources and generator scripts
```

### Regenerate everything

```bash
bash _builders/build_all.sh      # labs + decks + guides + register + validation
```

### Validate the labs

```bash
python3 _builders/validate_labs.py             # structure and derivation
python3 _builders/validate_labs.py --execute   # also run every solution and starter
```

2,473 checks across 16 solutions, 16 starters and 32 notebooks: syntax, required
sections, blank balance and hints, starter derivation, notebook schema, bootstrap
cells, cross-day imports, seed-data references, and execution. It runs as the last
step of `build_all.sh`, so a broken lab fails the build rather than a classroom.

### How lab files are produced

You edit **one** file per lab — the solution in `<Day>/solutions/`. Everything
else is generated:

```bash
python _builders/build_labs.py
```

| Generated | From | How |
|---|---|---|
| `labs/labNN.py` | the solution | `# <<<BLANK hint="...">` blocks become numbered TODOs |
| `notebooks/labNN.ipynb` | the starter | `# %%` / `# %% [markdown]` cell markers |
| `notebooks/labNN_solution.ipynb` | the solution | same |

Four artifacts, one source. Notebook-versus-solution drift is structurally
impossible rather than merely discouraged.

Decks and facilitation guides work the same way. `_builders/content_dayN.js`
holds every slide body and speaker note; two renderers consume it.

```bash
node _builders/build_deck.js  content_day1.js Day1_Foundations/Day1_Foundations_Deck.pptx
node _builders/build_guide.js content_day1.js Day1_Foundations/Day1_Facilitation_Guide.docx "Day 1"
```

The guide parses the `WHY / SAY / ASK / WATCH / TIME` convention out of the
speaker notes into a delivery script, and totals the speaking time. Deck and
guide are generated from one file, so the classic drift pair — a figure fixed on
a slide but stale in the guide — cannot happen.

| Artifact | Slides | Speaker-note chars | Speaking time |
|---|---|---|---|
| Day 0 Kickoff | 12 | — | 57 min |
| Day 1 | 18 | 21,203 | 93 min |
| Day 2 | 13 | 14,724 | 70 min |
| Day 3 | 13 | 16,503 | 80 min |
| Capstone | 12 | 14,668 | 71 min |

---

## Running the labs

```bash
# starter (blanks to fill)
python Day1_Foundations/labs/lab01_environment_and_telemetry.py

# complete
python Day1_Foundations/solutions/lab01_environment_and_telemetry.py

# notebooks
jupyter lab Day1_Foundations/notebooks/
```

Labs are **order-dependent within a day**. Day 1 Lab 5 imports Lab 4's rule
engine; Day 2 Lab 5 imports Labs 2, 3 and 4. Day 2 Lab 3 onward requires Day 2
Lab 1 to have run at least once, because it reads the collection Lab 1 builds.

## Running the web applications

```bash
streamlit run Day1_Foundations/webapp/app_reconciliation_console.py
streamlit run Day2_RAG/webapp/app_remittance_explorer.py
streamlit run Capstone/webapp/app_analyst_console.py
```

## Running the capstone

```bash
python3 -m Capstone.src.cli run          # process the batch (QUERY suspends)
python3 -m Capstone.src.cli pending      # list suspended transactions
python3 -m Capstone.src.cli resume "<thread_id>" --action assign_code \
    --reason-code D01 --by "J. Okonkwo" --rationale "confirmed by phone"
python3 Capstone/tests/test_acceptance.py   # the seven criteria — 7/7 pass
```

Run `Day2_RAG/solutions/lab01_vector_ingestion.py` once first — it builds the
remittance corpus the pipeline retrieves from.

See `Capstone/docs/BUILD_GUIDE.md` for the package layout and the reasoning
behind `src/` being a package rather than an import of the lab files.

---

## The running example

Ten bank transactions in `shared/seed_data/`, engineered so that every priority
rule and every end state fires — including the ones the specification does not
handle.

| Txn | What it teaches | Day 1 | Day 2 |
|---|---|---|---|
| BNK-1001 | the happy path, priority 4 | CLOSED | CLOSED |
| BNK-1002 | short payment + damage deduction | PARTIAL_MATCH | PARTIAL_MATCH + code D03 |
| BNK-1003 | tolerance auto-write-off | CLOSED | CLOSED |
| BNK-1004 | payer known, invoice unknown | UAC | UAC |
| BNK-1005 | blank sender — nothing to work with | UIC | UIC |
| BNK-1006 | delivery-number match, priority 2 | CLOSED | CLOSED |
| BNK-1007 | dated invoice match, priority 3 | CLOSED | CLOSED |
| BNK-1008 | needs the remittance parsed (3-way) | UAC | 3-way match → exposes gap S3 |
| BNK-1009 | short pay, remittance gives no reason | PARTIAL_MATCH | QUERY (correctly declines to guess) |
| BNK-1010 | **overpayment — gap S1** | QUERY | QUERY |

Measured Day 1 baseline: **70% match rate, 40% straight-through.** These two
numbers are different and conflating them is the most common way an O2C
automation business case is overstated.

---

## Read these before you deliver

| Document | Why |
|---|---|
| `00_Program/Assumptions_and_Decisions_Register.xlsx` | the governance artifact for a client sponsor: assumptions, open questions, version risks, evidence classification, build inventory |
| `00_Program/VERSION_RISK_REGISTER.md` | which claims are stable, which are assumptions, which are courseware inventions, and what to re-verify |
| `00_Program/CURRICULUM_GAP_ANALYSIS.md` | five specification gaps and four curriculum gaps, with severity and remediation priority |

One entry deserves calling out on its own: **`owning_team` and `sla_days` per
deduction code are a courseware invention**, not client specification. They exist
so learners see that a code alone is not actionable — routing is. Replace them
with the client's real ownership matrix before any client-facing use.

**Two things to know before you stand up in front of the room:**

1. **Path B (`azure-ai-projects`) is not settled.** Its client accessor has changed
   shape across releases. `shared/foundry_client.py` probes rather than assumes,
   and fails loudly with the installed version. Teach Path A (`openai` SDK's
   `AzureOpenAI`); demonstrate Path B and flag it.
2. **Gap G3 is closed.** Day 3 Lab 6 teaches `interrupt()` plus a durable
   `SqliteSaver` checkpointer, so `QUERY` suspends and resumes with the analyst's
   name and rationale attached. Capstone acceptance criteria 5 and 6 are now
   reachable. Install `langgraph-checkpoint-sqlite` or Lab 6 falls back to
   `MemorySaver` and cannot demonstrate durability.

---

## Design conventions

- **Deterministic Python for anything structured; the model only for prose.**
  Priority rules, arithmetic and invoice-number extraction are all code. The model
  classifies deduction *reasons* and nothing else.
- **Every seam is one file.** Credentials, model access and the vector store each
  have exactly one module. An SDK breaking change costs one file, not fifteen labs.
- **Audit trails are produced by the framework, not remembered by the developer.**
- **Gaps are surfaced, never papered over.** Where the specification is silent or
  contradicts itself, the code says so in plain text and the register records it.
