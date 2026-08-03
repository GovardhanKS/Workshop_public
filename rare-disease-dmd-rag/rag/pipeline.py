"""Single retrieve -> answer pipeline. Replaces the old agents/orchestrator.py
+ agents/reporting_agent.py + agents/base.py's per-domain-agent fan-out
(literature/trials/biomarker/regulatory each answering independently, then
synthesized) with a single retrieval call across the whole corpus, matching
fair-discovery's rag/pipeline.py architecture (one retriever -> one answerer,
with citations and query logging).

The domain split still exists as a *filter* (source_type on rag.retrieve.retrieve
and in agents/comparison.py's per-tab lookups), it's just no longer 4 separate
agents each generating their own answer.
"""
from __future__ import annotations

from dataclasses import dataclass

from agents.llm import LLM_MODE, generate
from monitoring.feedback import log_query
from rag.retrieve import EvidencePacket, retrieve

TOP_K_DEFAULT = 10


@dataclass
class Report:
    question: str
    summary: str
    citations: list[dict]
    note: str | None = None


def ask(question: str, top_k: int = TOP_K_DEFAULT) -> Report:
    evidence: list[EvidencePacket] = retrieve(question, top_k=top_k)
    summary = generate(question, evidence)
    citations = [
        {"citation": ev.citation, "source_type": ev.source_type, "url": ev.url}
        for ev in evidence
    ]
    note = None
    if len(evidence) == top_k:
        note = (
            f"Showing the top {top_k} most relevant sources across the whole corpus. "
            "Ask a more specific question to surface others."
        )
    log_query(question, citations=[c["citation"] for c in citations], used_llm=LLM_MODE == "llm")
    return Report(question=question, summary=summary, citations=citations, note=note)
