# DMD FAIR Data Catalog
### One searchable catalog of the scattered DMD data landscape — every record FAIR-scored, provenance-traced, and graph-linked.

---

## The problem
Research data for a single disease is smeared across incompatible silos — expression
studies in **GEO**, trials in **ClinicalTrials.gov**, compounds in **ChEMBL**, findings in
**PubMed** — each with its own identifiers, metadata, and access rules. A scientist asking
"what data exists for Duchenne muscular dystrophy, and can I trust it?" has no single place
to look, no consistent quality signal, and no map of how the pieces connect.

## What it is
A FAIR data **catalog** for one disease, done properly. It ingests records from four public
sources into one schema, scores every record for **FAIR-ness** using a recognized standard,
links them into a **knowledge graph**, and lets you find them by meaning — with an optional
cited AI answer on top.

## How it works (5 stages)
**Ingest → Normalize → FAIR-score → Index → Serve.**
Records are pulled live from ChEMBL, ClinicalTrials.gov and PubMed (verified), plus GEO via
NCBI E-utilities. Everything is normalized to one schema, scored, embedded for semantic
search, and linked into an Open Targets–style graph.

## Why it's credible (this is the part scientists care about)
- **Real records, not mock-ups** — e.g. Ataluren (CHEMBL256997), Eteplirsen, Givinostat;
  live DMD trials; real papers with DOIs.
- **Standards-based scoring** — the **FAIRsFAIR Data Object Assessment Metrics** (16 metric
  IDs, `FsF-F1-01D`…`FsF-R1.3`) implemented by **F-UJI**, not a home-grown rubric.
- **Scores are computed in code and labeled provisional** — the AI layer only *narrates*
  them, it cannot invent a number.
- **Calibrated against the authoritative tool** — a heuristic-vs-F-UJI table quantifies the
  gap and a documented loop tightens it (target |Δ| ≤ 10).
- **Honest about limits** — F-UJI scores *datasets*; compounds/trials/papers are marked as
  catalogue-level, stated openly in the UI.

## The FAIR ladder (provisional heuristic, current seed data)
ChEMBL 100 · Trials 94 · PubMed 88 (open) / 79 (subscription) · GEO 73 (Moderate) ·
unverified seed 42 (Basic). The unverified record scoring *lowest* is the integrity signal:
the catalog penalizes what it can't trust.

## 90-second demo script
1. Search **"exon skipping gene therapy"** → ranked, FAIR-scored results across 4 sources.
2. Expand any card → the **F-UJI metric drill-down** (pass/partial/fail with evidence).
3. Point at the **unverified GEO seed at 42%** → "the catalog flags what it can't trust."
4. Toggle **RAG** → a cited answer that reuses the scores but can't alter them.
5. Click a **knowledge-graph** node → re-center on dystrophin / a mechanism / a drug.
6. Scroll to **Calibration** → "and here's how we validate the scores against the standard."

## Roadmap
- Live F-UJI scoring wired for all GEO/DOI records; calibrate & tighten the heuristic.
- **Accession resolver**: paste `GSE…`/`NCT…`/`CHEMBL…`/`PMID…` → auto-route & score.
- Recall@k accuracy harness on a curated gold set.
- User data infusion: upload a file, scored by the *same* pipeline, in a private sandbox.
- Generalize the pattern to the next disease.

_Metric set: FAIRsFAIR Data Object Assessment Metrics. Tool: F-UJI (Devaraju & Huber 2023,
doi:10.5281/zenodo.6361400)._
