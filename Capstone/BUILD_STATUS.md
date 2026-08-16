# Capstone — Build Status

**Deck and facilitation guide: BUILT.** `src/`, `webapp/` and the build guide: **not yet produced.**

## The blocker is cleared

This build was previously blocked on gap **G3** (human-in-the-loop). **G3 is now
closed** by `Day3_Governance/solutions/lab06_human_in_the_loop.py`, which teaches
LangGraph `interrupt()` plus a durable `SqliteSaver` checkpointer.

Acceptance criteria **5** (a run survives process death and resumes) and **6**
(`QUERY` suspends and resumes on human input) — declared on slide 5 of the
Capstone deck — are now reachable. Lab 6 demonstrates both, including resuming
from a freshly constructed graph object with analyst attribution intact.

## What remains

| Item | Notes |
|---|---|
| `src/` | Assembly of the Day 3 secured 16-node pipeline with batch orchestration |
| `webapp/` | Analyst review console for the `QUERY` and `REJECTED_SECURITY_HOLD` queues |
| Build guide | Step-by-step capstone walkthrough against the seven acceptance criteria |

Remaining open items are specification decisions for the client, not blockers:
**S1** (no overpayment end state), **S3** (one-to-many cash application) and
**S4** (currency/FX). See `00_Program/CURRICULUM_GAP_ANALYSIS.md`.
