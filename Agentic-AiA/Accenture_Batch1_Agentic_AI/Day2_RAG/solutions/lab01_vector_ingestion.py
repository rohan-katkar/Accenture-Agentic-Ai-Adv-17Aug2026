# LAB TITLE: Day 2 Lab 1 - Vector Database Initialisation and Document Ingestion
# %% [markdown]
# ## Day 2 · Lab 1 — Vector Database Initialisation & Document Ingestion
#
# **Duration:** 45 minutes  **Difficulty:** Core
#
# ### Why this lab exists
#
# Day 1 ended with two unfinished transactions, and both are unfinished for the
# same reason: the fact needed to resolve them exists only in a document.
#
# | Txn | Day 1 outcome | What is missing | Where the answer lives |
# |---|---|---|---|
# | BNK-1008 | `UAC`, $15,000 unapplied | which invoices it covers | remittance advice |
# | BNK-1002 | `PARTIAL_MATCH`, no reason code | why $500 was withheld | remittance advice |
#
# Today we make those documents queryable. Not because vector search is
# fashionable — because a $15,000 payment is sitting in an exception queue and the
# answer is in a text file nobody has parsed.
#
# ### The four things that actually determine retrieval quality
#
# 1. **Chunking** — what unit of text becomes one searchable record
# 2. **Metadata** — what you can filter on *before* similarity is even considered
# 3. **IDs** — stable, deterministic, so re-ingestion updates rather than duplicates
# 4. **Embeddings** — which vector space you put everything in
#
# Most retrieval failures are chunking or metadata failures. Very few are
# embedding-model failures. Spend your time accordingly.
#
# ### Prerequisites
# Day 1 complete. `chromadb` installed (a fallback runs if not — see Step 1).

# %%
"""Day 2 Lab 1 - Vector Database Initialisation and Document Ingestion."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

_here = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
for _p in [_here, *_here.parents]:
    if (_p / "00_Program").is_dir():
        sys.path.insert(0, str(_p))
        break

from shared.config import SEED_DIR, settings                       # noqa: E402
from shared.foundry_client import get_embedder                     # noqa: E402
from shared.telemetry import configure, get_logger, log_event      # noqa: E402
from shared.vectorstore import backend_summary, get_collection     # noqa: E402

configure(level=settings.log_level, logfile="d2lab01_audit.log")
log = get_logger("day2.lab1")

COLLECTION = "remittance_advice"

# %% [markdown]
# ### Step 1 — Which backends are actually live?
#
# Two independent seams, and you need to know the state of both before you make
# any claim about retrieval quality in front of a client.
#
# > **The honesty rule for today.** If the embedder reports `offline-hashed-bow`,
# > you are doing **lexical** matching, not semantic matching. "Short paid" and
# > "underpaid" share no tokens and will not retrieve each other, though a real
# > embedding model places them close together. The pipeline is identical and the
# > lab is still worth doing — but do not present retrieval *quality* from this
# > backend. Say which backend produced any number you show.

# %%
print(backend_summary())
embed = get_embedder()
backend = getattr(embed, "backend_name", "?")
print(f"embedder            : {backend}")
print(f"vector dimension    : {len(embed(['dimension probe'])[0])}")

if backend.startswith("offline"):
    print("\n*** LEXICAL MODE. Pipeline valid, retrieval-quality claims are not. ***")

# %% [markdown]
# ### Step 2 — Read the source documents
#
# Five remittance advices, each tied to a bank transaction by filename convention
# (`BNK-1002_acme.txt`). In production these arrive as PDF attachments on an AP
# mailbox; `pypdf` extracts the text and everything downstream is identical.

# %%
REMIT_DIR = SEED_DIR / "remittance"
documents = {p.name.split("_")[0]: p.read_text(encoding="utf-8")
             for p in sorted(REMIT_DIR.glob("*.txt"))}

for txn_id, text in documents.items():
    first_line = next((l for l in text.splitlines() if l.strip()), "")
    print(f"  {txn_id}  {len(text):>5} chars  |  {first_line[:48]}")

# %% [markdown]
# ### Step 3 — Chunking: the decision that matters most
#
# A remittance advice has structure a naive splitter destroys. Compare:
#
# | Strategy | What breaks |
# |---|---|
# | Fixed 500-character windows | splits an invoice line from its amount |
# | One chunk per document | a 3-page advice retrieves as one blob; the model sees mostly noise |
# | **Paragraph-aware, with overlap** | preserves whole invoice lines and whole reason sentences |
#
# We split on blank lines and merge fragments below a floor, so a two-line
# heading never becomes its own record. The overlap carries one trailing line
# forward so a sentence spanning a boundary is still retrievable from both sides.
#
# > **Say this out loud:** there is no universally correct chunk size. There is
# > only a chunk size that matches how *your* documents carry meaning. Test it
# > against real retrieval, do not copy a number from a blog post.

# %%
MIN_CHUNK_CHARS = 120
OVERLAP_LINES = 1


def chunk_document(text: str) -> list[str]:
    """Paragraph-aware chunking with single-line overlap."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]

    merged: list[str] = []
    for block in blocks:
        if merged and len(merged[-1]) < MIN_CHUNK_CHARS:
            merged[-1] = merged[-1] + "\n" + block
        else:
            merged.append(block)

    # <<<BLANK hint="Build `overlapped`: for each chunk after the first, prepend the last OVERLAP_LINES line(s) of the previous chunk">
    overlapped: list[str] = []
    for i, chunk in enumerate(merged):
        if i == 0:
            overlapped.append(chunk)
            continue
        tail = "\n".join(merged[i - 1].splitlines()[-OVERLAP_LINES:])
        overlapped.append(f"{tail}\n{chunk}")
    return overlapped
    # >>>


sample = documents["BNK-1002"]
chunks = chunk_document(sample)
print(f"BNK-1002 -> {len(chunks)} chunks\n")
for i, c in enumerate(chunks):
    preview = c.replace("\n", " ⏎ ")[:88]
    print(f"  [{i}] {len(c):>4} chars | {preview}")

print("\nCheck that the damage sentence survived intact in one chunk:")
damage = [i for i, c in enumerate(chunks) if "crushed" in c.lower()]
print(f"  found in chunk(s): {damage}  <- if this is empty, chunking broke the evidence")

# %% [markdown]
# ### Step 4 — Metadata: the filter that runs before similarity
#
# This is the most under-used control in RAG. Similarity search over *every*
# remittance in the corpus is both slower and wronger than similarity search over
# the three chunks belonging to the transaction you are actually reconciling.
#
# In cash application this is not an optimisation, it is a correctness
# requirement: retrieving Stark Industries' damage claim while processing Acme's
# payment would post a deduction against the wrong customer.
#
# We attach `txn_id`, `customer`, `chunk_index` and `source_file`. `txn_id` is the
# one that prevents cross-contamination.

# %%
CUSTOMER_BY_TXN = {
    "BNK-1002": "Acme Corp", "BNK-1004": "Wayne Enterprises",
    "BNK-1008": "Umbrella Health", "BNK-1009": "Stark Industries",
    "BNK-1010": "Hooli Inc",
}


def stable_id(txn_id: str, index: int, text: str) -> str:
    """Deterministic ID: same content re-ingested updates rather than duplicates.

    A random UUID here is the single most common cause of a corpus that silently
    doubles in size every time the ingestion job runs.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
    return f"{txn_id}::{index:02d}::{digest}"


records: list[dict] = []
for txn_id, text in documents.items():
    for index, chunk in enumerate(chunk_document(text)):
        records.append({
            "id": stable_id(txn_id, index, chunk),
            "document": chunk,
            "metadata": {
                "txn_id": txn_id,
                "customer": CUSTOMER_BY_TXN.get(txn_id, "UNKNOWN"),
                "chunk_index": index,
                "source_file": f"{txn_id}_*.txt",
            },
        })

print(f"{len(records)} chunks across {len(documents)} documents\n")
print(f"{'TXN':<10}{'IDX':>4}  {'CHARS':>6}  ID")
print("-" * 74)
for r in records:
    print(f"{r['metadata']['txn_id']:<10}{r['metadata']['chunk_index']:>4}  "
          f"{len(r['document']):>6}  {r['id']}")

# %% [markdown]
# ### Step 5 — Embed and ingest
#
# Note what we do **not** do: we do not let Chroma embed for us. Chroma's default
# embedding function downloads a local ONNX model on first use — a surprise
# network call, an unpinned model, and a different vector space from the one your
# production Azure deployment queries with.
#
# Passing embeddings explicitly means the vectors in the store are the same
# vectors your application will search with. That is the only way retrieval
# quality is reproducible between a laptop and a pipeline.

# %%
collection = get_collection(COLLECTION, reset=True)

texts = [r["document"] for r in records]
vectors = embed(texts)
print(f"Embedded {len(vectors)} chunks -> dimension {len(vectors[0])}")

# <<<BLANK hint="Call collection.add() with ids, documents, embeddings and metadatas built from `records` and `vectors`">
collection.add(
    ids=[r["id"] for r in records],
    documents=texts,
    embeddings=vectors,
    metadatas=[r["metadata"] for r in records],
)
# >>>

print(f"Collection '{COLLECTION}' now holds {collection.count()} chunks.")
log_event(log, "ingestion_complete", collection=COLLECTION,
          chunks=collection.count(), embedder=backend)

# %% [markdown]
# ### Step 6 — Prove idempotency
#
# Run the same ingestion again. Because the IDs are content-derived, the count
# must not change. If it doubles, your job has been quietly corrupting the corpus
# on every scheduled run — and the symptom is retrieval that gets worse over time
# for no visible reason.

# %%
before = collection.count()
collection.add(ids=[r["id"] for r in records], documents=texts,
               embeddings=vectors, metadatas=[r["metadata"] for r in records])
after = collection.count()

print(f"before re-ingest : {before}")
print(f"after re-ingest  : {after}")
assert before == after, "Re-ingestion duplicated records - IDs are not stable"
print("Idempotent. Content-derived IDs did their job.")

# %% [markdown]
# ### Step 7 — First query, and the metadata filter in action
#
# Two searches with the identical query string. The only difference is the
# metadata filter. Watch what the unfiltered search pulls in.

# %%
QUERY = "goods arrived damaged and we withheld payment"
q_vec = embed([QUERY])

print(f"QUERY: {QUERY!r}\n")

print("A. UNFILTERED - searches every customer's remittance")
print("-" * 74)
unfiltered = collection.query(query_embeddings=q_vec, n_results=3)
for rank, (doc, meta, dist) in enumerate(zip(
        unfiltered["documents"][0], unfiltered["metadatas"][0], unfiltered["distances"][0]), 1):
    print(f"  {rank}. dist={dist:.4f}  {meta['txn_id']} ({meta['customer']})")
    print(f"     {doc.replace(chr(10), ' ')[:82]}")

print("\nB. FILTERED to txn_id = BNK-1002")
print("-" * 74)
filtered = collection.query(query_embeddings=q_vec, n_results=3, where={"txn_id": "BNK-1002"})
for rank, (doc, meta, dist) in enumerate(zip(
        filtered["documents"][0], filtered["metadatas"][0], filtered["distances"][0]), 1):
    print(f"  {rank}. dist={dist:.4f}  {meta['txn_id']} ({meta['customer']})")
    print(f"     {doc.replace(chr(10), ' ')[:82]}")

print("""
Distances are COSINE DISTANCE: lower is closer, 0.0 is identical.

Read search A carefully. Acme's damage chunk should rank first - but look at
ranks 2 and 3. Other customers' remittances are in the result set, competing for
the model's attention, on a query that has nothing to do with them. Now imagine
the top result is only marginally ahead, or the query is vaguer, or the corpus
has ten thousand documents instead of ten. Ranking is a gradient, not a
guarantee.

Search B cannot make that mistake. It is not searching harder - it is searching a
smaller, correct universe. In cash application the metadata filter is a
CORRECTNESS control, not a performance tweak: retrieving Stark's dispute while
processing Acme's payment posts a deduction against the wrong account.""")

# %% [markdown]
# ### Checkpoint — you are done when
#
# - [ ] You can state which embedding backend you are on and what that licenses you to claim.
# - [ ] `chunk_document` keeps the "crushed and unusable" sentence in one chunk.
# - [ ] The collection holds every chunk, and re-ingestion does not change the count.
# - [ ] The filtered query returns only BNK-1002 chunks.
#
# ### Discussion — 8 minutes
#
# 1. A customer sends a 40-page remittance covering 300 invoices. Does
#    paragraph-aware chunking still hold? What would you change?
# 2. Which metadata field would you add for a multi-entity group where a parent
#    company pays its subsidiaries' invoices? (Hint: `paying_entity` and
#    `billed_entity` are not the same field.)
# 3. Retention: how long may these chunks persist under your data policy, and
#    what deletes them? A vector store with no deletion story is a compliance
#    finding waiting to happen.
#
# ### Business impact
#
# Every deduction reason your organisation cannot classify automatically becomes
# an analyst reading a PDF. Making that corpus queryable is the prerequisite for
# everything on Day 2 — but note what has *not* happened yet: nothing has been
# extracted, validated or posted. Retrieval is a search problem. Trusting what you
# retrieved is a separate problem, and it is Lab 4.
