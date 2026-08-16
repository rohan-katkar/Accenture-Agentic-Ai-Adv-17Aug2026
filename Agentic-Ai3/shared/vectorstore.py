"""
shared/vectorstore.py
=====================
The same seam idea as foundry_client.py, applied to the vector database.

Day 2 teaches the real Chroma API - `PersistentClient`, `get_or_create_collection`,
`add`, `query`. Learners must see the actual calls, because that is the syllabus
item and because they will use them at their desks.

What this module adds is a *fallback*: a minimal in-memory collection exposing
the same four methods, used only when `chromadb` cannot be imported. An
air-gapped room, a failed native wheel or a corporate proxy blocking a download
should not cost you an afternoon of Day 2.

DESIGN CHOICE WORTH EXPLAINING IN CLASS
---------------------------------------
We pass embeddings to Chroma EXPLICITLY rather than letting it embed for us.
Chroma's default embedding function downloads a local ONNX model on first use.
That is a surprise network call, an unpinned model, and a different vector space
from the one your production Azure deployment uses. Passing embeddings yourself
means the vectors in the store are the same vectors your application will query
with - which is the only way retrieval quality is reproducible.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from shared.telemetry import get_logger, log_event

log = get_logger(__name__)

try:
    import chromadb  # type: ignore

    CHROMA_AVAILABLE = True
    CHROMA_VERSION = getattr(chromadb, "__version__", "unknown")
except Exception as exc:  # noqa: BLE001
    CHROMA_AVAILABLE = False
    CHROMA_VERSION = f"unavailable ({type(exc).__name__})"


# ---------------------------------------------------------------------------
# Fallback collection - same surface as the Chroma methods the labs use
# ---------------------------------------------------------------------------
class MiniCollection:
    """In-memory cosine-similarity store. Not a database. A safety net.

    Implements exactly the four calls Day 2 makes on a Chroma collection:
    add(), query(), count(), get(). Nothing else. If a lab needs a fifth method,
    that is a signal the lab has drifted past what the fallback can honestly
    stand in for.
    """

    backend_name = "mini-fallback"

    def __init__(self, name: str) -> None:
        self.name = name
        self._ids: list[str] = []
        self._docs: list[str] = []
        self._meta: list[dict] = []
        self._vecs: list[list[float]] = []

    def add(self, *, ids: Sequence[str], documents: Sequence[str],
            embeddings: Sequence[Sequence[float]],
            metadatas: Sequence[dict] | None = None) -> None:
        metadatas = metadatas or [{} for _ in ids]
        for i, doc, vec, meta in zip(ids, documents, embeddings, metadatas):
            if i in self._ids:                     # upsert semantics
                k = self._ids.index(i)
                self._docs[k], self._vecs[k], self._meta[k] = doc, list(vec), dict(meta)
            else:
                self._ids.append(i)
                self._docs.append(doc)
                self._vecs.append(list(vec))
                self._meta.append(dict(meta))

    def count(self) -> int:
        return len(self._ids)

    def get(self, *, where: dict | None = None) -> dict:
        keep = [k for k in range(len(self._ids)) if _matches(self._meta[k], where)]
        return {
            "ids": [self._ids[k] for k in keep],
            "documents": [self._docs[k] for k in keep],
            "metadatas": [self._meta[k] for k in keep],
        }

    def query(self, *, query_embeddings: Sequence[Sequence[float]],
              n_results: int = 3, where: dict | None = None) -> dict:
        out_ids, out_docs, out_meta, out_dist = [], [], [], []
        for q in query_embeddings:
            scored = [
                (_cosine(q, self._vecs[k]), k)
                for k in range(len(self._ids)) if _matches(self._meta[k], where)
            ]
            scored.sort(key=lambda t: -t[0])
            top = scored[:n_results]
            out_ids.append([self._ids[k] for _, k in top])
            out_docs.append([self._docs[k] for _, k in top])
            out_meta.append([self._meta[k] for _, k in top])
            # Chroma returns a DISTANCE (lower = closer). Cosine distance = 1 - sim.
            out_dist.append([round(1.0 - s, 6) for s, _ in top])
        return {"ids": out_ids, "documents": out_docs,
                "metadatas": out_meta, "distances": out_dist}


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _matches(meta: dict, where: dict | None) -> bool:
    """Supports the flat equality filters the labs use: {"txn_id": "BNK-1002"}."""
    if not where:
        return True
    return all(meta.get(k) == v for k, v in where.items())


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_clients: dict[str, Any] = {}


def get_collection(name: str, persist_dir: str | None = None, *, reset: bool = False) -> Any:
    """Return a Chroma collection, or a MiniCollection if Chroma is unavailable."""
    if not CHROMA_AVAILABLE:
        log_event(log, "vectorstore_fallback", reason="chromadb import failed",
                  detail=CHROMA_VERSION)
        key = f"mini::{name}"
        if reset or key not in _clients:
            _clients[key] = MiniCollection(name)
        return _clients[key]

    from shared.config import settings

    path = persist_dir or settings.chroma_dir
    if path not in _clients:
        _clients[path] = chromadb.PersistentClient(path=path)
    client = _clients[path]

    if reset:
        try:
            client.delete_collection(name)
        except Exception:  # noqa: BLE001 - absent collection is fine
            pass

    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},   # cosine, to match our normalised vectors
    )
    log_event(log, "vectorstore_ready", backend="chromadb",
              version=CHROMA_VERSION, collection=name, count=collection.count())
    return collection


def backend_summary() -> str:
    return (f"chromadb available : {CHROMA_AVAILABLE}\n"
            f"chromadb version   : {CHROMA_VERSION}")
