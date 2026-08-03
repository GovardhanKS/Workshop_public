"""Comparison Agent -- builds the three structured tables the capstone
brief calls for (literature comparison, trial comparison, regulatory
insights) instead of free-text answers. Unlike the domain agents, this
reads the corpus directly by ID (NCT/PMID) rather than through the
retriever: a comparison needs one specific record's full text, not the
single best-matching chunk of it.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

from rag.corpus import Document, load_all
from rag.retrieve import retrieve
from agents.llm import LLM_MODE, generate, extract_fields
from rag.retrieve import EvidencePacket

TOP_K_DEFAULT = 10
REGULATORY_GUIDANCE_PATH = pathlib.Path(__file__).parent.parent / "data" / "raw" / "regulatory_guidance_dmd.json"

_CORPUS_CACHE: list[Document] | None = None


def _corpus() -> list[Document]:
    global _CORPUS_CACHE
    if _CORPUS_CACHE is None:
        _CORPUS_CACHE = load_all()
    return _CORPUS_CACHE


def find_trial(nct_id: str) -> Document | None:
    nct_id = nct_id.strip().upper()
    return next((d for d in _corpus() if d.source_type == "trial" and d.doc_id.upper() == nct_id), None)


def find_article(pmid: str) -> Document | None:
    pmid = pmid.strip().upper()
    if not pmid.startswith("PMID"):
        pmid = f"PMID{pmid}"
    return next((d for d in _corpus() if d.source_type == "literature" and d.doc_id.upper() == pmid), None)


@dataclass
class Shortlist:
    items: list[Document]
    total_matches: int
    note: str | None


def shortlist(source_type: str, query: str | None = None, top_k: int = TOP_K_DEFAULT) -> Shortlist:
    """Top-k candidates for a comparison picker -- ranked by relevance to
    `query` if given, else the corpus's natural order. Always capped so a
    353-trial corpus doesn't get dumped into one dropdown."""
    all_docs = [d for d in _corpus() if d.source_type == source_type]
    if query:
        hits = retrieve(query, source_type=source_type, top_k=top_k)
        by_citation = {d.citation: d for d in all_docs}
        items = [by_citation[h.citation] for h in hits if h.citation in by_citation]
    else:
        items = all_docs[:top_k]
    note = None
    if len(all_docs) > len(items):
        note = f"Showing top {len(items)} of {len(all_docs)} {source_type} records. Search to narrow further."
    return Shortlist(items=items, total_matches=len(all_docs), note=note)


@dataclass
class ComparisonRow:
    parameter: str
    value_a: str
    value_b: str
    ai_observation: str


@dataclass
class ComparisonResult:
    label_a: str
    label_b: str
    rows: list[ComparisonRow]
    summary: str
    caveat: str | None = None


def _phase_rank(phases: list[str] | None) -> int:
    order = {"EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}
    if not phases:
        return -1
    return max((order.get(p, -1) for p in phases), default=-1)


_BIOMARKER_KEYWORDS = ["exon", "dystrophin", "mutation", "genotyp", "deletion", "duplication", "biomarker"]


def _extract_biomarker_mention(eligibility_text: str | None) -> str:
    if not eligibility_text:
        return "Not specified"
    for line in eligibility_text.splitlines():
        low = line.lower()
        if any(kw in low for kw in _BIOMARKER_KEYWORDS):
            return line.strip()[:200]
    return "Not specified"


def _rows_to_evidence(rows: list[ComparisonRow], id_a: str, id_b: str, source_type: str) -> list[EvidencePacket]:
    return [
        EvidencePacket(
            claim_text=f"{r.parameter}: {id_a}={r.value_a} | {id_b}={r.value_b}. {r.ai_observation}",
            citation=f"{id_a} vs {id_b}", url=None, source_type=source_type, score=1.0,
        )
        for r in rows
    ]


def compare_trials(nct_a: str, nct_b: str) -> ComparisonResult:
    doc_a, doc_b = find_trial(nct_a), find_trial(nct_b)
    if not doc_a or not doc_b:
        missing = nct_a if not doc_a else nct_b
        raise ValueError(f"Trial {missing} not found in the indexed corpus.")

    m_a, m_b = doc_a.metadata, doc_b.metadata
    rows = []

    phase_a, phase_b = m_a.get("phase") or ["Not specified"], m_b.get("phase") or ["Not specified"]
    rank_a, rank_b = _phase_rank(m_a.get("phase")), _phase_rank(m_b.get("phase"))
    phase_obs = "Same phase" if rank_a == rank_b else (
        f"{'Trial A' if rank_a > rank_b else 'Trial B'} is later-stage, closer to approval"
        if -1 not in (rank_a, rank_b) else "Phase not comparable"
    )
    rows.append(ComparisonRow("Phase", ", ".join(phase_a), ", ".join(phase_b), phase_obs))

    pop_a = ", ".join(m_a.get("conditions") or []) or "Not specified"
    pop_b = ", ".join(m_b.get("conditions") or []) or "Not specified"
    rows.append(ComparisonRow("Population / Condition", pop_a, pop_b,
                               "Same condition focus" if pop_a == pop_b else "Different condition scope"))

    enroll_a, enroll_b = m_a.get("enrollment"), m_b.get("enrollment")
    if isinstance(enroll_a, int) and isinstance(enroll_b, int) and enroll_a != enroll_b:
        enroll_obs = f"{'Trial A' if enroll_a > enroll_b else 'Trial B'} has higher statistical power (larger cohort)"
    else:
        enroll_obs = "Comparable cohort size" if enroll_a == enroll_b else "Enrollment not comparable"
    rows.append(ComparisonRow("Sample Size (Enrollment)", str(enroll_a or "Not specified"), str(enroll_b or "Not specified"), enroll_obs))

    elig_a = (m_a.get("eligibility_criteria") or "Not specified")[:300]
    elig_b = (m_b.get("eligibility_criteria") or "Not specified")[:300]
    rows.append(ComparisonRow("Inclusion/Exclusion Criteria", elig_a, elig_b, "Review full criteria text for eligibility differences"))

    endpoint_a = "; ".join(o.get("measure", "") for o in m_a.get("primary_outcomes") or []) or "Not specified"
    endpoint_b = "; ".join(o.get("measure", "") for o in m_b.get("primary_outcomes") or []) or "Not specified"
    rows.append(ComparisonRow("Primary Endpoint", endpoint_a, endpoint_b,
                               "Same primary endpoint" if endpoint_a == endpoint_b else "Different efficacy objectives"))

    arms_a = m_a.get("interventions") or []
    arms_b = m_b.get("interventions") or []
    arm_obs = (
        f"Trial {'A' if len(arms_a) > len(arms_b) else 'B'} evaluates combination therapy" if len(arms_a) != len(arms_b)
        else "Same number of treatment arms"
    )
    rows.append(ComparisonRow("Treatment Arms", ", ".join(arms_a) or "Not specified", ", ".join(arms_b) or "Not specified", arm_obs))

    bio_a = _extract_biomarker_mention(m_a.get("eligibility_criteria"))
    bio_b = _extract_biomarker_mention(m_b.get("eligibility_criteria"))
    rows.append(ComparisonRow("Biomarker / Genotype Criteria", bio_a, bio_b,
                               "Similar biomarker strategy" if bio_a == bio_b else "Different biomarker/genotype requirements"))

    res_a = m_a.get("results_summary") or ("Not yet posted" if not m_a.get("has_results") else "Posted -- see ClinicalTrials.gov")
    res_b = m_b.get("results_summary") or ("Not yet posted" if not m_b.get("has_results") else "Posted -- see ClinicalTrials.gov")
    rows.append(ComparisonRow("Results", res_a, res_b,
                               "Both have posted results" if m_a.get("has_results") and m_b.get("has_results")
                               else "Results not yet available for one or both trials"))

    summary = generate(
        f"Compare clinical trial design and outcomes between {nct_a} and {nct_b}",
        _rows_to_evidence(rows, nct_a, nct_b, "trial"),
    )
    return ComparisonResult(label_a=nct_a, label_b=nct_b, rows=rows, summary=summary)


def _disease_area(metadata: dict) -> str:
    diseases = metadata.get("diseases") or []
    if not diseases:
        return "Not tagged"
    return ", ".join(diseases[:4])


def compare_literature(pmid_a: str, pmid_b: str) -> ComparisonResult:
    doc_a, doc_b = find_article(pmid_a), find_article(pmid_b)
    if not doc_a or not doc_b:
        missing = pmid_a if not doc_a else pmid_b
        raise ValueError(f"Article {missing} not found in the indexed corpus.")

    m_a, m_b = doc_a.metadata, doc_b.metadata

    # Disease Area and Biomarker are extracted offline (no LLM needed):
    # disease names come from NCBI PubTator3 NER, cached onto each article
    # at ingestion time (see ingestion/fetch_literature.py); biomarker/
    # genotype mentions reuse the same keyword scan already used for trial
    # eligibility criteria, applied to the abstract text instead.
    disease_a, disease_b = _disease_area(m_a), _disease_area(m_b)
    bio_a, bio_b = _extract_biomarker_mention(doc_a.text), _extract_biomarker_mention(doc_b.text)

    llm_field_names = ["sample_size", "study_type", "primary_endpoint", "key_finding"]
    fields_a = extract_fields(doc_a.text, llm_field_names)
    fields_b = extract_fields(doc_b.text, llm_field_names)

    rows = [
        ComparisonRow("PMID", doc_a.citation, doc_b.citation, "-"),
        ComparisonRow("Journal", m_a.get("journal") or "Not specified", m_b.get("journal") or "Not specified",
                       "Same journal" if m_a.get("journal") == m_b.get("journal") else "Different journals"),
        ComparisonRow("Publication Year", str(m_a.get("year") or "Unknown"), str(m_b.get("year") or "Unknown"),
                       _year_observation(m_a.get("year"), m_b.get("year"))),
        ComparisonRow("Disease Area", disease_a, disease_b,
                       "Same" if disease_a == disease_b else "See values -- NER-tagged via PubTator3"),
        ComparisonRow("Biomarker / Genotype Mention", bio_a, bio_b,
                       "Same" if bio_a == bio_b else "See values -- keyword-matched from abstract text"),
    ]
    llm_labels = {
        "sample_size": "Sample Size", "study_type": "Study Type",
        "primary_endpoint": "Primary Endpoint", "key_finding": "Key Finding",
    }
    for key, label in llm_labels.items():
        val_a, val_b = fields_a[key], fields_b[key]
        obs = "Same" if val_a == val_b and "Not" not in val_a else "See values -- AI-extracted from abstract text"
        rows.append(ComparisonRow(label, val_a, val_b, obs))

    summary = generate(
        f"Compare the literature findings of {doc_a.citation} and {doc_b.citation}",
        _rows_to_evidence(rows, doc_a.citation, doc_b.citation, "literature"),
    )
    caveat = (
        "Sample Size, Study Type, Primary Endpoint, and Key Finding require LLM_MODE=llm (AI extraction from "
        "the abstract) -- showing 'Not available' in offline mode. Disease Area (PubTator3 NER) and "
        "Biomarker/Genotype Mention (keyword match) are available either way."
        if LLM_MODE != "llm" else
        "Sample Size, Study Type, Primary Endpoint, and Key Finding are AI-extracted from the abstract text, not "
        "structured PubMed fields -- verify against the source before citing externally. Disease Area is "
        "NER-tagged via PubTator3, not manually curated."
    )
    return ComparisonResult(label_a=doc_a.citation, label_b=doc_b.citation, rows=rows, summary=summary, caveat=caveat)


def _year_observation(year_a, year_b) -> str:
    try:
        ya, yb = int(year_a), int(year_b)
        if ya == yb:
            return "Same year"
        return f"{'Paper A' if ya > yb else 'Paper B'} is more recent"
    except (TypeError, ValueError):
        return "Not comparable"


def load_regulatory_guidance() -> dict:
    if not REGULATORY_GUIDANCE_PATH.exists():
        return {"items": [], "note": "Regulatory guidance seed file not found."}
    return json.loads(REGULATORY_GUIDANCE_PATH.read_text())
