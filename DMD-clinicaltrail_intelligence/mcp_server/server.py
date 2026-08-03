"""MCP stdio server exposing DMD data discovery as agent tools. Ported from
fair-discovery's mcp_server/server.py, which wrapped its own `Platform`
object (catalog+retriever+KG+RAG bundled together); this project has no
single such object, so each tool wraps the equivalent piece directly:
rag.pipeline for ask(), rag.retrieve/rag.corpus for search/get, the
knowledge_graph package for related_datasets(), and fair.service for
fair_score()/part of catalog_stats().

Run with: python -m mcp_server.server
Requires: pip install -r requirements-mcp.txt
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised only without `mcp` installed
    raise SystemExit(
        "The `mcp` package is required to run the MCP server: pip install -r requirements-mcp.txt"
    ) from exc

from fair import service as fair_service
from knowledge_graph.kg import get_graph, related_datasets as _related_datasets
from monitoring.feedback import compute_stats
from rag import corpus as rag_corpus
from rag.pipeline import ask as _ask
from rag.retrieve import retrieve as _retrieve

mcp = FastMCP("dmd-clinical-trial-intelligence")

_corpus_cache: list[rag_corpus.Document] | None = None


def _all_docs() -> list[rag_corpus.Document]:
    global _corpus_cache
    if _corpus_cache is None:
        _corpus_cache = rag_corpus.load_all()
    return _corpus_cache


def _title_for_citation(citation: str) -> Optional[str]:
    return next((d.title for d in _all_docs() if d.citation == citation), None)


@mcp.tool()
def search_datasets(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search over the DMD corpus (trials, literature, biomarker, regulatory).
    Returns ranked records with their citation, source type, and score."""
    return [
        {
            "citation": ev.citation, "title": _title_for_citation(ev.citation),
            "source_type": ev.source_type, "url": ev.url, "score": ev.score,
        }
        for ev in _retrieve(query, top_k=top_k)
    ]


@mcp.tool()
def get_dataset(citation: str) -> Optional[Dict[str, Any]]:
    """Fetch full text/metadata for one record by its citation (e.g. an NCT
    ID, 'PMID 12345', or a fair/ catalog accession like CHEMBL256997)."""
    doc = next((d for d in _all_docs() if d.citation == citation or d.doc_id == citation), None)
    if doc:
        return {
            "doc_id": doc.doc_id, "source_type": doc.source_type, "title": doc.title,
            "text": doc.text, "citation": doc.citation, "url": doc.url, "metadata": doc.metadata,
        }
    resolved = fair_service.resolve_accession(citation)
    return resolved if resolved.get("source") else None


@mcp.tool()
def ask(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Ask a natural-language question about DMD; returns a grounded answer
    with citations across the whole corpus (no per-domain filtering)."""
    return asdict(_ask(query, top_k=top_k))


@mcp.tool()
def related_datasets(accession: str, k: int = 5) -> List[Dict[str, Any]]:
    """Find records related to the given accession via the knowledge graph
    (shared source, type, or entities). Scoped to the fair/ catalog's 15
    records (GEO/ChEMBL/ClinicalTrials/PubMed) -- not the full 353-trial
    corpus, which has no curated entity data to link on."""
    return _related_datasets(get_graph(), accession, k=k)


@mcp.tool()
def fair_score(accession: str) -> Optional[Dict[str, Any]]:
    """Return the Findable/Accessible/Interoperable/Reusable score breakdown
    for a fair/ catalog accession (FAIRsFAIR/F-UJI-aligned metrics)."""
    resolved = fair_service.resolve_accession(accession)
    return resolved.get("fair")


@mcp.tool()
def catalog_stats() -> Dict[str, Any]:
    """Return corpus size by source, fair/ catalog size, and query/feedback
    volume for this running instance."""
    stats = compute_stats()
    stats["corpus_by_source"] = rag_corpus.counts_by_source()
    stats["fair_catalog_size"] = len(fair_service.scored_catalog())
    return stats


if __name__ == "__main__":
    mcp.run()
