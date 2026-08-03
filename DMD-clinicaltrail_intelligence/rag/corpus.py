"""Load the raw per-source JSON files and normalize them into a single
list of Document objects that the rest of the pipeline (chunking,
embedding, retrieval, agents) can treat uniformly regardless of which
open-access source they came from.

Each Document carries a `citation` field -- this is what lets the
Reporting Agent produce answers with a traceable source ID instead of
paraphrased, unattributed text.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

DATA_DIR = pathlib.Path(__file__).parent.parent / "data" / "raw"


@dataclass
class Document:
    doc_id: str
    source_type: str  # "trial" | "literature" | "biomarker" | "regulatory"
    title: str
    text: str
    citation: str  # human-readable source ID, e.g. "NCT03375255" or "PMID 34120909"
    url: str | None = None
    metadata: dict = field(default_factory=dict)


def _load_json(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_trials() -> list[Document]:
    data = _load_json("trials_dmd.json")
    docs = []
    for item in data.get("items", []):
        nct = item.get("nct_id", "UNKNOWN")
        primary_outcomes = ", ".join(o.get("measure", "") for o in item.get("primary_outcomes") or [])
        text = (
            f"{item.get('title', '')}. Status: {item.get('status')}. "
            f"Phase: {item.get('phase')}. Sponsor: {item.get('sponsor')}. "
            f"Enrollment: {item.get('enrollment')}. "
            f"Interventions: {', '.join(item.get('interventions') or [])}. "
            f"Primary outcomes: {primary_outcomes}. "
            f"Eligibility: {(item.get('eligibility_criteria') or '')[:600]}"
        )
        docs.append(Document(
            doc_id=nct, source_type="trial", title=item.get("title", ""),
            text=text, citation=nct,
            url=f"https://clinicaltrials.gov/study/{nct}" if nct != "UNKNOWN" else None,
            metadata=item,
        ))
    return docs


def load_literature() -> list[Document]:
    data = _load_json("literature_dmd.json")
    docs = []
    for art in data.get("articles", []):
        pmid = art.get("pmid", "UNKNOWN")
        text = f"{art.get('title', '')}. {art.get('abstract', '')}"
        docs.append(Document(
            doc_id=f"PMID{pmid}", source_type="literature", title=art.get("title", ""),
            text=text, citation=f"PMID {pmid}",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid != "UNKNOWN" else None,
            metadata={
                "doi": art.get("doi"), "journal": art.get("journal"), "year": art.get("year"),
                "diseases": art.get("diseases") or [],
            },
        ))
    return docs


def load_biomarker() -> list[Document]:
    """Merges three biomarker-domain sources into one list of Documents:
    the ChEMBL dystrophin target record, its Open Targets disease
    associations (one Document per disease, score >= 0.2 -- see
    ingestion/fetch_biomarker.py for the cutoff rationale), and hand-curated
    standard DMD clinical trial endpoints/biomarkers."""
    docs = []

    data = _load_json("biomarker_dmd.json")
    if data:
        target = data.get("target", {})
        target_text = (
            f"Target: {target.get('pref_name')} (gene {target.get('gene_symbol')}, "
            f"UniProt {target.get('uniprot_accession')}). "
            f"Key biological processes: {', '.join(target.get('go_process_highlights') or [])}. "
            f"Pathways: {', '.join(target.get('reactome_pathways') or [])}. "
            f"{data.get('note', '')}"
        )
        docs.append(Document(
            doc_id=target.get("target_chembl_id", "CHEMBL_UNKNOWN"),
            source_type="biomarker", title=target.get("pref_name", "Dystrophin"),
            text=target_text, citation=target.get("target_chembl_id", "ChEMBL"),
            url=f"https://www.ebi.ac.uk/chembl/target_report_card/{target.get('target_chembl_id')}/" if target.get("target_chembl_id") else None,
            metadata=target,
        ))

        for disease in data.get("associated_diseases", []):
            docs.append(Document(
                doc_id=disease["id"], source_type="biomarker",
                title=f"Dystrophin target association: {disease['name']}",
                text=(
                    f"The dystrophin target (gene DMD) is associated with {disease['name']} "
                    f"(Open Targets association score {disease['score']:.2f})."
                ),
                citation=f"Open Targets: {disease['id']} ({disease['name']})",
                url=f"https://platform.opentargets.org/disease/{disease['id']}",
                metadata=disease,
            ))

    guidance = _load_json("biomarker_endpoints_dmd.json")
    for item in guidance.get("items", []):
        docs.append(Document(
            doc_id=item.get("id", f"ENDPOINT-{item.get('name', '')[:20]}"),
            source_type="biomarker", title=item.get("name", ""),
            text=(
                f"{item.get('name')} ({item.get('type')}, measured via {item.get('measured_via')}). "
                f"{item.get('description', '')} Used in: {item.get('used_in', '')}"
            ),
            citation=f"DMD clinical endpoint (seed, verify): {item.get('name')}",
            url=None, metadata=item,
        ))

    return docs


def load_regulatory() -> list[Document]:
    data = _load_json("regulatory_dmd.json")
    docs = []
    for i, event in enumerate(data.get("approval_events", [])):
        text = (
            f"{event.get('drug')} ({event.get('brand')}, sponsor {event.get('sponsor')}). "
            f"Pathway: {event.get('pathway')}. Mechanism: {event.get('mechanism')}. "
            f"Surrogate endpoint: {event.get('surrogate_endpoint')}. "
            f"{event.get('safety_signal', '')}"
        )
        citation_label = "FDA record (verified via openFDA)" if event.get("status") == "verified_via_openfda" \
            else "FDA/EMA record (seed, verify)"
        docs.append(Document(
            doc_id=f"REG-{i}-{event.get('drug', 'unknown').replace(' ', '_')}",
            source_type="regulatory", title=event.get("brand", event.get("drug", "")),
            text=text, citation=f"{citation_label}: {event.get('drug')}",
            url=None, metadata=event,
        ))
    for i, program in enumerate(data.get("discontinued_programs", [])):
        text = (
            f"{program.get('drug')} (sponsor {program.get('sponsor')}) -- discontinued. "
            f"Mechanism: {program.get('mechanism')}. Reason: {program.get('reason')}."
        )
        docs.append(Document(
            doc_id=f"REG-DISC-{i}-{program.get('drug', 'unknown').replace(' ', '_')}",
            source_type="regulatory", title=f"Discontinued: {program.get('drug', '')}",
            text=text, citation=f"Discontinued program (seed, verify): {program.get('drug')}",
            url=None, metadata=program,
        ))
    return docs


def load_regulatory_guidance() -> list[Document]:
    """General FDA/EMA clinical-trial-design guidance (eligibility,
    diversity, decentralized trials, RWE, rare disease, accelerated
    approval) -- distinct from load_regulatory()'s drug-specific approval
    history. Folding this into the regulatory corpus lets the Regulatory
    Agent ground ordinary Q&A in these documents too, not just the
    Regulatory Insights table."""
    data = _load_json("regulatory_guidance_dmd.json")
    docs = []
    for item in data.get("items", []):
        text = (
            f"{item.get('guidance')} ({item.get('agency')}, {item.get('status')}, {item.get('date')}). "
            f"Impact area: {item.get('impact_area')}. {item.get('description', '')} {item.get('ai_insight', '')}"
        )
        docs.append(Document(
            doc_id=item.get("id", f"GUIDANCE-{item.get('guidance', '')[:20]}"),
            source_type="regulatory", title=item.get("guidance", ""),
            text=text, citation=f"{item.get('agency')} guidance ({item.get('date')}): {item.get('guidance')}",
            url=None, metadata=item,
        ))
    return docs


def counts_by_source() -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc in load_all():
        counts[doc.source_type] = counts.get(doc.source_type, 0) + 1
    return counts


def load_all() -> list[Document]:
    return (
        load_trials() + load_literature() + load_biomarker()
        + load_regulatory() + load_regulatory_guidance()
    )
