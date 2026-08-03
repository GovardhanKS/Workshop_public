"""Shared retrieval function the RAG pipeline (rag/pipeline.py) and the
Comparison Agent call. Returns EvidencePackets -- structured, citation-tagged
objects -- rather than free text, per the workflow doc's design principle:
callers should never have to trust prose, only resolve source IDs.

Dedup + optional rerank ported from fair-discovery's retriever/retriever.py
(there: dedup per-accession across matched chunks; here: per-citation across
this project's chunked Documents, see rag/chunk.py).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from .embed_store import get_store

logger = logging.getLogger(__name__)
RERANK = os.environ.get("RERANK", "0") == "1"
_RERANK_WARNED = False
_FETCH_FACTOR = 4  # over-fetch before dedup so top_k *unique* documents still surface


@dataclass
class EvidencePacket:
    claim_text: str
    citation: str
    url: str | None
    source_type: str
    score: float


def retrieve(query: str, source_type: str | None = None, top_k: int = 10) -> list[EvidencePacket]:
    store = get_store()
    raw_hits = store.query(query, top_k=top_k * _FETCH_FACTOR, source_type=source_type)

    # A document chunked into multiple pieces can surface more than once in
    # raw_hits -- keep only the highest-scoring chunk per citation so one
    # verbose trial/article doesn't crowd out other relevant sources.
    best_by_citation: dict[str, tuple] = {}
    for doc, score in raw_hits:
        prev = best_by_citation.get(doc.citation)
        if prev is None or score > prev[1]:
            best_by_citation[doc.citation] = (doc, score)

    results = sorted(best_by_citation.values(), key=lambda ds: ds[1], reverse=True)[:top_k]
    if RERANK:
        results = _rerank(query, results)

    return [
        EvidencePacket(
            claim_text=doc.text, citation=doc.citation, url=doc.url,
            source_type=doc.source_type, score=round(score, 3),
        )
        for doc, score in results
    ]


def _rerank(query: str, results: list[tuple]) -> list[tuple]:
    """Optional cross-encoder rerank, gated behind RERANK=1. Uses the same
    optional sentence-transformers dependency as EMBEDDING_BACKEND=hf
    (requirements-hf.txt) -- no new dependency for this feature specifically."""
    global _RERANK_WARNED
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        if not _RERANK_WARNED:
            logger.warning(
                "RERANK=1 but sentence-transformers is not installed; skipping rerank "
                "(pip install -r requirements-hf.txt)."
            )
            _RERANK_WARNED = True
        return results
    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    pairs = [(query, doc.text) for doc, _ in results]
    scores = cross_encoder.predict(pairs)
    reranked = [(doc, float(s)) for (doc, _), s in zip(results, scores)]
    return sorted(reranked, key=lambda ds: ds[1], reverse=True)
