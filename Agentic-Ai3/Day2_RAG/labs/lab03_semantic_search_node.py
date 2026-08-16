# ==========================================================================
# STARTER FILE - Day 2 Lab 3 - Implementing a Semantic Vector Search Node
# ==========================================================================
# There are 2 blank(s) to complete, each marked with a TODO.
# Work top to bottom. Run the file after each blank - it fails loudly at the
# next unfinished blank it REACHES, which tells you where you are.
#
# Blanks are numbered by position in the file, not by execution order. A blank
# inside a function defined early but called late is reached after a later one,
# so the file may halt at blank 2 before blank 1. That is expected.
#
# Stuck? The completed file is in ../solutions/ - but try for ten minutes
# first. The debugging is the lesson.
# ==========================================================================

# LAB TITLE: Day 2 Lab 3 - Implementing a Semantic Vector Search Node
# %% [markdown]
# ## Day 2 · Lab 3 — Implementing a Semantic Vector Search Node
#
# **Duration:** 40 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# Lab 1 built a searchable corpus. This lab turns search into a **graph node** —
# and adds the control that most RAG implementations skip.
#
# ### The control most implementations skip
#
# Vector search **always returns results**. Ask a store containing five remittance
# advices "what is the capital of France" and it will hand back three remittance
# chunks, ranked. It has no concept of *"nothing here is relevant."*
#
# That is fine for a chatbot and dangerous for cash application. If you retrieve
# three irrelevant chunks and pass them to a model asking "what is the deduction
# reason?", the model will find one. It will be confident. It will be wrong.
#
# So the node must gate on distance and return an explicit **no-evidence** signal.
# `QUERY` — needing a human — is a legitimate, valuable outcome. Manufacturing a
# reason code is not.
#
# ### Prerequisites
# Day 2 Labs 1–2 complete. Run Lab 1 first — this lab reads the collection it built.

# %%
"""Day 2 Lab 3 - Implementing a Semantic Vector Search Node."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import settings                             # noqa: E402
from shared.foundry_client import get_embedder                 # noqa: E402
from shared.telemetry import configure, get_logger, log_event, trace_node  # noqa: E402
from shared.vectorstore import get_collection                  # noqa: E402

configure(level=settings.log_level, logfile="d2lab03_audit.log")
log = get_logger("day2.lab3")

COLLECTION = "remittance_advice"
embed = get_embedder()
collection = get_collection(COLLECTION)

if collection.count() == 0:
    raise SystemExit("Collection is empty. Run Day 2 Lab 1 first — it builds the corpus.")
print(f"Collection '{COLLECTION}' holds {collection.count()} chunks "
      f"(embedder: {getattr(embed, 'backend_name', '?')})")

# %% [markdown]
# ### Step 1 — Calibrate the distance threshold before you trust it
#
# A relevance threshold copied from a tutorial is a guess. Calibrate it against
# your own corpus and your own embedder, because the number depends on both.
#
# We run three probes:
#
# | Probe | Expectation |
# |---|---|
# | a query the corpus genuinely answers | low distance |
# | a query about a different customer's issue | mid distance |
# | a query with nothing to do with the corpus | high distance |
#
# The threshold sits between the second and third. **Re-run this whenever the
# embedding model changes** — a threshold tuned on one vector space is meaningless
# in another.

# %%
PROBES = [
    ("damaged goods withheld from payment", "should hit — Acme's damage claim"),
    ("early payment discount taken outside terms", "no document says this"),
    ("what is the capital of France", "nothing to do with this corpus"),
]

print(f"{'DIST':>8}  {'TXN':<10}  PROBE")
print("-" * 78)
observed: list[float] = []
for probe, expectation in PROBES:
    res = collection.query(query_embeddings=embed([probe]), n_results=1)
    dist = res["distances"][0][0]
    observed.append(dist)
    print(f"{dist:>8.4f}  {res['metadatas'][0][0]['txn_id']:<10}  {probe}")
    print(f"{'':>8}  {'':<10}  ({expectation})")

print(f"""
Every probe returned something. The nonsense query returned a remittance chunk
at distance {observed[-1]:.4f}. Vector search does not know how to say "nothing
here". YOU have to decide where the cut-off sits.""")

# %% [markdown]
# ### Step 2 — Set the threshold, and be honest about how you chose it
#
# > **Documented assumption — carry this into the assumptions register.**
# > The value below was chosen against *this* corpus with *this* embedder. It is a
# > starting point, not a validated production setting. Tuning it properly means
# > building a labelled set of query/document pairs and measuring precision and
# > recall — which is a work package, not a constant.

# %%
RELEVANCE_THRESHOLD = 0.92   # cosine distance; ABOVE this is treated as no evidence
TOP_K = 3

print(f"RELEVANCE_THRESHOLD = {RELEVANCE_THRESHOLD}  (cosine distance, lower is closer)")
print(f"TOP_K               = {TOP_K}")
print("\nGiven the probe distances above, sanity-check that this threshold would")
print("admit the damage query and reject the nonsense query. If it does not,")
print("change the number here rather than pretending the default was principled.")

# %% [markdown]
# ### Step 3 — The retrieval function
#
# Three responsibilities, in order:
#
# 1. **Filter by `txn_id`** — correctness, not performance (Lab 1, Step 7)
# 2. **Gate on distance** — drop chunks beyond the threshold
# 3. **Return provenance** — every chunk carries its ID and distance, because
#    Lab 4 has to cite evidence and "the model said so" is not a citation

# %%
@dataclass
class Evidence:
    chunk_id: str
    text: str
    distance: float
    txn_id: str
    customer: str

    @property
    def confidence(self) -> float:
        """Map distance to a rough 0-1 score for display only.

        HONESTY LABEL: this is a monotone rescaling of distance, not a
        calibrated probability. Do not put it in front of a business user as
        'the model is 87% confident'. It is not that.
        """
        return round(max(0.0, min(1.0, 1.0 - self.distance)), 3)


def retrieve(query: str, txn_id: str | None = None,
             top_k: int = TOP_K, threshold: float = RELEVANCE_THRESHOLD) -> list[Evidence]:
    """Filtered, distance-gated retrieval with provenance."""
    where = {"txn_id": txn_id} if txn_id else None
    result = collection.query(
        query_embeddings=embed([query]), n_results=top_k, where=where)

    # ------------------------------------------------------------------
    # TODO (Blank 1): Build a list of Evidence from the parallel result lists (ids, documents, distances, metadatas), keeping only rows whose distance <= threshold
    # ------------------------------------------------------------------
    raise NotImplementedError("Lab blank 1 - see the TODO above")


for query, txn in [("why was the payment short", "BNK-1002"),
                   ("what is the capital of France", "BNK-1002")]:
    found = retrieve(query, txn_id=txn)
    print(f"\nquery={query!r}  txn={txn}  ->  {len(found)} chunk(s) passed the gate")
    for ev in found:
        print(f"    dist={ev.distance:.4f}  {ev.chunk_id}")
        print(f"    {ev.text.replace(chr(10), ' ')[:78]}")

# %% [markdown]
# ### Step 4 — The graph node
#
# Same contract as every Day 1 node: state in, partial dict out. Two things it
# must get right:
#
# - Build the query from **state**, not from a hard-coded string. The question
#   asked of the corpus depends on what the rule engine already found.
# - When nothing passes the gate, set `remittance_found = False` and say so in the
#   trace. Silence is not the same as absence, and downstream nodes must be able
#   to tell the difference.

# %%
def node_remittance_search(state: dict) -> dict:
    """Retrieve remittance evidence for this transaction."""
    txn_id = state.get("txn_id", "")
    run_id = state.get("run_id", "-")

    with trace_node(log, "remittance_search", run_id, txn_id=txn_id) as out:
        variance = state.get("variance_usd", 0.0)
        # ------------------------------------------------------------------
        # TODO (Blank 2): Build the retrieval query FROM STATE: a negative variance asks why money was withheld, a positive variance asks about the excess, and zero asks which invoices the payment covers
        # ------------------------------------------------------------------
        raise NotImplementedError("Lab blank 2 - see the TODO above")

        found = retrieve(query, txn_id=txn_id)
        out["chunks_retrieved"] = len(found)
        out["best_distance"] = found[0].distance if found else None

        if not found:
            return {
                "remittance_found": False,
                "remittance_evidence": [],
                "trace": [f"remittance_search: no chunk within {RELEVANCE_THRESHOLD} "
                          f"for {txn_id} — no evidence available"],
            }

        return {
            "remittance_found": True,
            "remittance_evidence": [
                {"chunk_id": e.chunk_id, "text": e.text, "distance": e.distance}
                for e in found
            ],
            "remittance_text": "\n\n---\n\n".join(e.text for e in found),
            "trace": [f"remittance_search: {len(found)} chunk(s) retrieved for {txn_id}, "
                      f"best distance {found[0].distance:.4f}"],
        }

# %% [markdown]
# ### Step 5 — Run it across the Day 1 exception queue
#
# These are the four transactions Day 1 could not finish. Watch which ones now
# have evidence and — importantly — which still do not.

# %%
CASES = [
    {"txn_id": "BNK-1002", "variance_usd": -500.0, "note": "short payment, damage claim"},
    {"txn_id": "BNK-1008", "variance_usd": 0.0, "note": "UAC, needs invoice breakdown"},
    {"txn_id": "BNK-1009", "variance_usd": -300.0, "note": "short payment, vague remittance"},
    {"txn_id": "BNK-1010", "variance_usd": 1000.0, "note": "overpayment"},
    {"txn_id": "BNK-1005", "variance_usd": 0.0, "note": "UIC — no remittance exists at all"},
]

for case in CASES:
    state = {"run_id": "d2l3", **case}
    result = node_remittance_search(state)
    flag = "EVIDENCE" if result["remittance_found"] else "NO EVIDENCE"
    print(f"\n{case['txn_id']}  [{flag}]  ({case['note']})")
    print(f"  {result['trace'][0]}")
    for chunk in result.get("remittance_evidence", [])[:1]:
        print(f"  top chunk: {chunk['text'].replace(chr(10), ' ')[:76]}")

# %% [markdown]
# ### Step 6 — Read the results honestly
#
# BNK-1005 has no remittance document at all. The node correctly reports no
# evidence — that transaction stays `UIC` and Treasury owns it. **That is the
# system working, not failing.**
#
# BNK-1009's remittance exists but says only *"Amount adjusted per internal
# review. Balance under evaluation."* It contains no deduction reason. The chunk
# will retrieve — it is the only Stark document — but it does not answer the
# question.
#
# > **This is the distinction Lab 4 exists to enforce.** Retrieval found *a*
# > document. It did not find *an answer*. A node that conflates the two will
# > assign BNK-1009 a confident reason code invented from a sentence that says
# > nothing. Retrieval is a search problem; grounding is a separate problem.

# %%
stark = retrieve("reason the customer withheld part of the payment", txn_id="BNK-1009")
print("BNK-1009 retrieved evidence, verbatim:\n")
for ev in stark:
    print(f"  [dist {ev.distance:.4f}]  {ev.text}\n")
print("Ask the room: which of D01-D05 does this text support?")
print("Correct answer: none. The right output is QUERY, not a guess.")

log_event(log, "lab03_complete", threshold=RELEVANCE_THRESHOLD, top_k=TOP_K)

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] You calibrated the threshold against your own probes rather than accepting the default.
# - [ ] `retrieve()` drops chunks beyond the threshold and returns provenance for those it keeps.
# - [ ] BNK-1005 returns no evidence and the trace says so explicitly.
# - [ ] You can explain why BNK-1009 retrieving a chunk is not the same as BNK-1009 having an answer.
#
# ### Discussion — 8 minutes
#
# 1. If you raise the threshold to 0.99, everything passes the gate. What breaks?
#    If you lower it to 0.5, what breaks? Which failure is more expensive here?
# 2. `Evidence.confidence` is a rescaled distance, not a probability. What harm
#    does it do to show it to a business user as "87% confident"?
# 3. Your corpus grows from 10 chunks to 2 million. Which part of this node
#    changes? (The filter becomes essential rather than merely correct; the
#    threshold needs re-calibration; `top_k` alone stops being sufficient.)
#
# ### Business impact
#
# The distance gate is what lets the workflow say "I do not know." An automation
# that never says that does not have a higher automation rate — it has an
# undetected error rate. In cash application those errors surface weeks later as
# customer disputes about credits that were never agreed, and every one of them
# costs more to unwind than the analyst time the automation saved.
