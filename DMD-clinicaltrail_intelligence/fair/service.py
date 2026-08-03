"""Thin wiring layer between the fair/ scoring + resolver scripts and the
rest of the app (api/main.py, ui/app.py) -- keeps pipeline.py/fair_fairsfair.py/
resolver.py as faithful, standalone-runnable copies of the original
dmd_platform demo (see fair/README.md for how to run them directly).
"""
from __future__ import annotations

import json
import pathlib

from . import fair_fairsfair as scorer
from . import resolver as accession_resolver

HERE = pathlib.Path(__file__).parent


def scored_catalog() -> list[dict]:
    """The 15-record demo catalog (GEO/ChEMBL/ClinicalTrials/PubMed), each
    scored against the FAIRsFAIR/F-UJI-aligned metrics in fair_fairsfair.py."""
    records = json.loads((HERE / "dmd_datasets.json").read_text())["records"]
    for r in records:
        r["fair"] = scorer.score(r)
    return sorted(records, key=lambda r: r["fair"]["overall"], reverse=True)


def resolve_accession(raw: str) -> dict:
    """Detect an accession's type (GSE/NCT/CHEMBL/PMID/DOI/Ensembl/EFO/...),
    route it to its source, and FAIR-score it if it's already in the catalog."""
    return accession_resolver.resolve(raw)
