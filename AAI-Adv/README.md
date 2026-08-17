# Advanced Agentic AI on Microsoft Foundry — Lab Package
**Northwind Global Retail · Amazon Settlement ↔ D365 ERP Reconciliation**
Accenture Advanced Programme · v1.2 · August 2026

## Quickstart

**GitHub Codespaces (recommended — zero install):** Code > Codespaces >
Create codespace. The devcontainer builds everything and runs the full
acceptance suite automatically; "Environment ready" = validated.

**Local, one command:**
```bash
./setup.sh          # Linux / macOS / WSL2 / Codespaces terminal
./setup.ps1         # Windows PowerShell
```
Both end by running the 17-test acceptance suite — all must pass OFFLINE.
Then: `python capstone/engine.py demo` (venv active).

## Switching to live Azure AI Foundry
Copy `.env.template` → `.env`, fill `FOUNDRY_PROJECT_ENDPOINT` and
`FOUNDRY_MODEL_DEPLOYMENT`, run `az login`. Every lab prints its mode on
startup; the switch lives entirely in `common/model.py` — no lab code changes.

## Repository map
```
common/        model.py (SDK isolation layer + verification register),
               offline_client.py, data_gen.py, d365_store.py
tools/         mcp_d365_server.py — MCP stdio server (3 ERP tools)
labs/day1..3/  starters/ labN_M.py (build here) · notebooks/ (same content, Jupyter)
solutions/day1..3/  reference implementations (# %% cells) — generated FROM these
capstone/      engine.py — 4-agent engine + CLI (run/demo/approve)
infra/         main.bicep · .github/workflows/deploy.yml
builders/      docs_source.js (SINGLE SOURCE) · build_docs.js ·
               gen_starters_notebooks.py (starters/notebooks FROM solutions)
docs/          STUDENT_GUIDE.docx · FACILITATOR_GUIDE.docx · LAB_STEPS.md ·
               ENVIRONMENT_SETUP.md · VERIFICATION_REGISTER.md
tests/         test_acceptance.py — the definition of "package complete"
```

## Regeneration (single source of truth)
- Docs: `node builders/build_docs.js` (all guides from `docs_source.js`)
- Starters + notebooks: `python builders/gen_starters_notebooks.py` (from solutions/)
- Data: `python common/data_gen.py` (seeded, deterministic)

## Verification status (summary — full register in docs/)
Executed & green on Python 3.12: all 12 labs, capstone demo, 17/17 tests, offline.
`FoundryChatClient.as_agent()` verified to exist (`create_agent()` does not).
Azure-mode paths follow verified constructor signatures but were **not
live-executed** in the build environment (no credentials); run them during
cohort prep. Portal navigation steps are flagged `[VERIFY]` — preview surfaces.
