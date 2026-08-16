# Version Risk & Evidence Register

**Programme:** Accenture Batch 1 — Agentic AI Foundation
**Purpose:** every claim in this courseware that could go stale, with what to re-check and how.

Re-run `python 00_Program/verify_environment.py` on the delivery machine before
each session. It exercises the surfaces listed below and reports which are live.

---

## A. Version-sensitive technical surfaces

| # | Surface | Risk | Confidence in courseware as written | Action before delivery |
|---|---|---|---|---|
| A1 | **`azure-ai-projects` client accessor** | The method used to obtain a chat client from `AIProjectClient` has appeared in more than one shape across the package's preview line and GA. | **LOW — do not present a single signature as settled.** | `shared/foundry_client.py` *probes* known accessor shapes and raises with the installed version if none work. Verify against current Microsoft Learn on the delivery machine. Teach Path A. |
| A2 | **`openai` `AzureOpenAI` client** | Stable surface. `api_version` string still pins server behaviour. | HIGH | Confirm the `api_version` in `.env` is one your resource accepts. |
| A3 | **`model=` parameter semantics** | Takes the *deployment* name, not the model family name. | HIGH | No action. Say it out loud in Lab 2 — it is the top day-one ticket. |
| A4 | **LangGraph `StateGraph` / `add_conditional_edges`** | Core API, stable across the 0.2–1.x line used here. | HIGH | Verified running on 0.2.60+ and on 1.2.x during the build. |
| A5 | **LangGraph `interrupt` / `Command` (HITL)** | Post-0.2 API. Required by the Capstone `QUERY` state. Not exercised in Days 1–3 as originally scoped. | MEDIUM | `verify_environment.py` imports `langgraph.types.interrupt` and warns if absent. See gap G3. |
| A6 | **`chromadb` client construction & embedding functions** | Changed shape at the 0.5 → 1.0 boundary. | MEDIUM | Labs pass embeddings **explicitly** and never rely on Chroma's default embedding function, which sidesteps most of the churn. Built and tested against 1.5.9. |
| A7 | **Chroma default embedding function** | Downloads a local ONNX model on first use — a surprise network call and an unpinned model. | N/A — avoided by design | Do not reintroduce it. Explained in Day 2 Lab 1, Step 5. |
| A8 | **Pydantic v2 `field_validator`** | v1 syntax (`@validator`) is incompatible. | HIGH | Pinned `pydantic>=2.9,<3`. |
| A9 | **`draw_mermaid()` on compiled graphs** | Availability varies by LangGraph version. | MEDIUM | Every call is wrapped with an ASCII fallback. No lab depends on it. |

---

## B. Evidence classification for factual claims

| # | Claim made in the courseware | Status | Basis |
|---|---|---|---|
| B1 | The six end states, six priority rules, and codes D01–D05 | **Client-specified** | Taken directly from `Accenture_Batch_1_Detailed.pdf`. Not independently verified against a live Accenture process. |
| B2 | $10 auto-write-off tolerance | **Client-specified** | Stated in the source document (Example C). |
| B3 | Owning team and SLA per deduction code (Quality/10d, Pricing Desk/5d, etc.) | **COURSEWARE INVENTION — clearly labelled** | Not in the source document. Added so learners see that a code alone is not actionable; routing is. **Replace with the client's real ownership matrix before any client-facing use.** |
| B4 | Relevance distance threshold 0.92 | **Assumption, documented as such** | Chosen against this corpus and this embedder. Day 2 Lab 3 tells learners to calibrate rather than inherit it. |
| B5 | Confidence floor 0.60 for dispute-vs-query routing | **Assumption, documented as such** | Not derived from measurement. Day 2 Lab 5 specifies the experiment that would replace it. |
| B6 | Day 1 baseline: 70% match rate, 40% straight-through | **Measured, reproducible** | Computed from the 10-row seed file. Enforced as a known-answer test in `verify_environment.py`. |
| B7 | Day 2 delta: straight-through unchanged, 1/10 coded | **Measured on the offline stub** | Reproducible offline. Figures on a live model will differ; re-measure and re-state. |
| B8 | Customer names (Acme, Globex, Umbrella Health, etc.) | **Synthetic** | Deliberately fictional placeholder entities. No real customer data anywhere in the package. |
| B9 | Latency figures in Day 2 Lab 2 | **Learner-measured, not asserted** | Lab 2 has learners measure their own endpoint. No latency number is claimed by the courseware. |
| B10 | Any productivity or automation-uplift percentage | **NOT CLAIMED ANYWHERE** | Deliberate. See the measurement position below. |

---

## C. Measurement position (state this to the client)

The courseware makes **no productivity claim** and asserts **no automation-rate
target**. Both are treated as measurement problems:

1. A target percentage requires a **frozen baseline** measured on the client's own
   payment file, before training begins. Day 1 Lab 5 teaches learners to produce
   exactly this artifact.
2. **Match rate and straight-through rate are different numbers** and conflating
   them is the most common way an O2C automation business case is overstated.
   Day 1 slide 16 and Day 2 Lab 5 both make this explicit.
3. Day 2's value is largely **invisible to a straight-through metric** — it
   converts undifferentiated exception work into coded, routed, SLA-bearing work.
   Measure coded-and-routed volume separately or Day 2 will look like it did nothing.

---

## D. Offline-mode honesty labels

| Surface | Offline behaviour | What you may NOT claim from it |
|---|---|---|
| Chat model | Deterministic keyword stub that quotes verbatim from the input | Any statement about model reasoning, generalisation or accuracy |
| Embeddings | Hashed bag-of-words, 256-dim, L2-normalised | **Semantic** retrieval quality. This is lexical matching: "short paid" and "underpaid" will not retrieve each other |
| Vector store | Real ChromaDB if installed; in-memory cosine fallback otherwise | Performance or scaling characteristics |

Every lab prints its active backend at start-up. If a number appears in a client
deliverable, the backend that produced it must appear next to it.
