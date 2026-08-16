"""
Day 2 Web Application - Remittance Intelligence Explorer
========================================================
Run:  streamlit run Day2_RAG/webapp/app_remittance_explorer.py

PREREQUISITE: run Day 2 Lab 1 at least once. It builds the collection this app reads.

WHAT IT IS FOR
--------------
Day 2's controls are invisible in a terminal. This console makes three of them
visible to a non-engineer in about ninety seconds:

  1. RETRIEVAL   - move the distance threshold and watch chunks fall out of scope
  2. GROUNDING   - see a fabricated citation rejected in real time
  3. ROUTING     - move the confidence floor and watch a dispute become a QUERY

TEACHING USE (12 minutes, end of Day 2)
---------------------------------------
Open the Grounding tab. Paste a plausible-sounding quote that is NOT in the
document and submit it. It gets rejected. Then paste a real sentence from the
document. It passes. That single demonstration does more to explain hallucination
control than twenty minutes of slides.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "00_Program").is_dir():
        REPO = _p
        sys.path.insert(0, str(_p))
        break
else:  # pragma: no cover
    st.error("Could not locate the repository root (the folder containing 00_Program).")
    st.stop()

sys.path.insert(0, str(REPO / "Day2_RAG" / "solutions"))

from shared.config import SEED_DIR, settings  # noqa: E402
from shared.foundry_client import get_chat_client, get_embedder  # noqa: E402
from shared.telemetry import configure  # noqa: E402
from shared.vectorstore import CHROMA_AVAILABLE, get_collection  # noqa: E402

configure(level="WARNING")

st.set_page_config(page_title="Remittance Intelligence", page_icon="◈", layout="wide")

NAVY, DEEP, TEAL, MINT, GOLD = "#21295C", "#065A82", "#1C7293", "#16A0A0", "#E0A800"

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2rem; }}
  h1, h2, h3 {{ font-family: Cambria, Georgia, serif; color: {NAVY}; }}
  code, pre {{ font-family: Consolas, monospace; }}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_backends():
    embed = get_embedder()
    collection = get_collection("remittance_advice")
    return embed, collection


embed, collection = load_backends()
embed_backend = getattr(embed, "backend_name", "?")
chat_backend = get_chat_client().backend_name

st.title("Remittance Intelligence Explorer")
st.caption("Day 2 · retrieval, grounding and confidence routing, made visible")

if collection.count() == 0:
    st.error(
        "The vector collection is empty. Run **Day 2 Lab 1** first — it ingests the "
        "remittance corpus this application reads.\n\n"
        "`python Day2_RAG/solutions/lab01_vector_ingestion.py`"
    )
    st.stop()

# --- backend honesty banner -------------------------------------------------
if embed_backend.startswith("offline"):
    st.warning(
        f"**Lexical mode.** The embedder is `{embed_backend}` — hashed bag-of-words, "
        "not a semantic model. The pipeline is real; the *retrieval quality* is not "
        "representative. \"Short paid\" and \"underpaid\" share no tokens and will not "
        "retrieve each other here. Do not quote retrieval quality from this backend.",
        icon="⚠",
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("Chunks indexed", collection.count())
c2.metric("Vector store", "ChromaDB" if CHROMA_AVAILABLE else "in-memory fallback")
c3.metric("Embedder", embed_backend)
c4.metric("Chat backend", chat_backend)

# --- sidebar ----------------------------------------------------------------
st.sidebar.title("Controls")
threshold = st.sidebar.slider(
    "Relevance threshold (cosine distance)", 0.50, 1.00, 0.92, 0.01,
    help="Chunks with distance ABOVE this are treated as no evidence. Lower is stricter.")
top_k = st.sidebar.slider("Top K", 1, 5, 3)
confidence_floor = st.sidebar.slider(
    "Confidence floor for auto-dispute", 0.0, 1.0, 0.60, 0.05,
    help="Findings below this floor route to QUERY for human review.")

st.sidebar.divider()
st.sidebar.caption(
    "Both numbers are **assumptions**, not measurements. Day 2 Labs 3 and 5 "
    "specify the experiments that would replace them. See the evidence register."
)

tab_search, tab_ground, tab_route, tab_corpus = st.tabs(
    ["1 · Retrieval", "2 · Grounding", "3 · Confidence routing", "4 · Corpus"])

# ---------------------------------------------------------------- Retrieval --
with tab_search:
    st.subheader("Filtered, distance-gated retrieval")

    left, right = st.columns([3, 2])
    query = left.text_input(
        "Query", "reason the customer withheld part of the payment")
    txn_options = ["— all customers (unfiltered) —", "BNK-1002", "BNK-1004",
                   "BNK-1008", "BNK-1009", "BNK-1010"]
    txn = right.selectbox("Filter by transaction", txn_options, index=1)

    where = None if txn.startswith("—") else {"txn_id": txn}
    result = collection.query(
        query_embeddings=embed([query]), n_results=top_k, where=where)

    rows = []
    for chunk_id, doc, dist, meta in zip(
        result["ids"][0], result["documents"][0],
        result["distances"][0], result["metadatas"][0],
    ):
        rows.append({
            "Distance": round(dist, 4),
            "Passes gate": "yes" if dist <= threshold else "NO",
            "Txn": meta.get("txn_id"),
            "Customer": meta.get("customer"),
            "Chunk": doc.replace("\n", " ")[:110],
        })

    frame = pd.DataFrame(rows)
    st.dataframe(frame, use_container_width=True, hide_index=True)

    passed = sum(1 for r in rows if r["Passes gate"] == "yes")
    if passed == 0:
        st.success(
            f"**No evidence.** Nothing scored within {threshold}. This is a valid, "
            "valuable outcome — the transaction routes to `QUERY` and a human decides. "
            "An automation that can never say *I don't know* does not have a higher "
            "automation rate; it has an undetected error rate."
        )
    else:
        st.info(f"{passed} of {len(rows)} chunk(s) passed the gate at threshold {threshold}.")

    if where is None:
        others = {r["Txn"] for r in rows}
        if len(others) > 1:
            st.warning(
                f"**Unfiltered search pulled in {len(others)} different transactions:** "
                f"{', '.join(sorted(others))}. In cash application the metadata filter is a "
                "**correctness** control, not a performance tweak — retrieving Stark's "
                "dispute while processing Acme's payment posts a deduction against the "
                "wrong account.", icon="⚠")

# ---------------------------------------------------------------- Grounding --
with tab_ground:
    st.subheader("Verbatim citation check")
    st.markdown(
        "A model's citation must be a **literal substring** of the retrieved document. "
        "This one check catches fabricated evidence that no amount of prompt "
        "engineering reliably prevents — and it costs one line of code."
    )

    doc_choice = st.selectbox(
        "Source document", ["BNK-1002", "BNK-1008", "BNK-1009", "BNK-1010", "BNK-1004"])
    source_path = next(iter((SEED_DIR / "remittance").glob(f"{doc_choice}_*.txt")), None)
    source_text = source_path.read_text(encoding="utf-8") if source_path else ""

    a, b = st.columns([3, 2])
    with b:
        st.markdown("**Source document**")
        st.code(source_text, language="text")

    with a:
        citation = st.text_area(
            "Claimed citation (paste a real sentence, then try inventing one)",
            "Five units arrived crushed and unusable at our Newark dock",
            height=110)

        needle = " ".join(citation.split()).lower()
        haystack = " ".join(source_text.split()).lower()
        grounded = bool(needle) and needle in haystack

        if grounded:
            st.success("**GROUNDED.** This text appears verbatim in the source document.")
        else:
            st.error(
                "**REJECTED — not a verbatim quote.** In Day 2 Lab 4 this raises a "
                "`ValueError`, the finding is discarded, and the transaction fails safe "
                "to `UNKNOWN` → `QUERY`."
            )
            st.caption(
                "Try: *\"the agreed contract price was 95.00 per unit\"* — fluent, "
                "specific, plausible, and entirely invented. That is what a "
                "hallucinated citation looks like from the outside."
            )

# --------------------------------------------------------- Confidence route --
with tab_route:
    st.subheader("How a finding becomes a dispute — or a question")

    r1, r2 = st.columns(2)
    code = r1.selectbox("Reason code", ["D01", "D02", "D03", "D04", "D05", "UNKNOWN"], index=2)
    confidence = r2.slider("Model confidence", 0.0, 1.0, 0.85, 0.05)

    codes = pd.read_csv(SEED_DIR / "deduction_codes.csv")
    route = "query" if (code == "UNKNOWN" or confidence < confidence_floor) else "dispute"

    if route == "dispute":
        row = codes[codes["reason_code"] == code].iloc[0]
        st.success(
            f"**→ open_dispute** · code `{code}` ({row['category']}) · "
            f"owner **{row['owning_team']}** · SLA **{row['sla_days']} days**"
        )
        st.caption("Cash is applied, a coded dispute is raised, and it lands in the "
                   "owning team's queue with its evidence attached.")
    else:
        why = ("the document stated no reason" if code == "UNKNOWN"
               else f"confidence {confidence:.2f} is below the floor of {confidence_floor:.2f}")
        st.warning(f"**→ QUERY** · human review required · {why}")
        st.caption("Lower automation rate. Higher correctness rate. Those two numbers "
                   "move in opposite directions and only one of them reaches a "
                   "steering-committee slide.")

    st.divider()
    st.markdown("#### Deduction reason codes")
    st.dataframe(codes, use_container_width=True, hide_index=True)
    st.caption(
        "**Note:** `owning_team` and `sla_days` are courseware additions, not client "
        "specification. They exist so learners see that a code alone is not "
        "actionable — routing is. Replace with the client's real ownership matrix "
        "before any client-facing use."
    )

# ------------------------------------------------------------------- Corpus --
with tab_corpus:
    st.subheader("Indexed corpus")
    everything = collection.get()
    st.dataframe(pd.DataFrame({
        "Chunk ID": everything["ids"],
        "Txn": [m.get("txn_id") for m in everything["metadatas"]],
        "Customer": [m.get("customer") for m in everything["metadatas"]],
        "Chars": [len(d) for d in everything["documents"]],
        "Text": [d.replace("\n", " ")[:100] for d in everything["documents"]],
    }), use_container_width=True, hide_index=True)

    st.markdown("""
#### What determines retrieval quality, in order of impact

1. **Chunking** — what unit of text becomes one searchable record
2. **Metadata** — what you filter on *before* similarity is considered
3. **IDs** — content-derived, so re-ingestion updates rather than duplicates
4. **Embeddings** — which vector space everything lives in

Most retrieval failures are chunking or metadata failures. Very few are embedding-model
failures. Spend your time accordingly.
""")

st.divider()
st.caption(f"Accenture Batch 1 · Agentic AI Foundation · Day 2 · "
           f"offline_mode={settings.offline_mode}")
