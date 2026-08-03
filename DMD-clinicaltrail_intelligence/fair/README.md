# DMD FAIR Data Discovery — demo pipeline

> Merged into the main `dmd-clinical-trial-intelligence` project as the `fair/` subpackage. It runs
> independently of that project's agents/RAG pipeline (own data, own scripts, no
> shared code, stdlib-only deps) and is additionally surfaced there via the
> **FAIR Catalog** UI tab and the `/fair/catalog` / `/fair/resolve` API endpoints
> (see `fair/service.py`). Everything below still applies when running the files
> in this folder standalone, as originally designed.

A scoped, disease-specific demo (Duchenne muscular dystrophy) of a multi-source
omics data-discovery platform: **ingest → normalize → FAIR score → index → serve**.

## What's here
| File | Purpose |
|---|---|
| `demo.html` | Interactive demo (also a live Cowork artifact): search + RAG + FAIR drill-down + knowledge graph |
| `pipeline.py` | Ingest (live API fetch) + normalize to one schema |
| `fair_fairsfair.py` | FAIRsFAIR / F-UJI aligned scorer + optional live F-UJI REST call |
| `dmd_datasets.json` | 15 normalized records (real ChEMBL/Trials/PubMed; seed GEO) |
| `dmd_scored.json` | Records with computed FAIR results (generated) |
| `resolver.py` | Accession resolver: ID → source routing (+ catalog/live resolve) |
| `evaluate_search.py` | recall@k / MRR search-accuracy harness (gold set) |
| `calibrate.py` | Heuristic vs authoritative F-UJI calibration table |
| `PITCH.md` | One-page pitch for a mixed (exec + scientist) audience |

## Sources (4) + KG backbone
- **GEO** (NCBI) — omics/transcriptomics. *No MCP; fetched via E-utilities.*
- **ClinicalTrials.gov** — trials (494 DMD trials live).
- **ChEMBL** — approved DMD drugs (Ataluren, Eteplirsen, Givinostat — all verified).
- **PubMed** — literature (7 real articles w/ DOIs).
- **Open Targets** — gene–disease–drug **knowledge-graph backbone** (not a dataset source).

## FAIR scoring — the standards-based part
Scoring is re-based on the **FAIRsFAIR Data Object Assessment Metrics** implemented by
**F-UJI** (per fair-impact.eu). 14 metric IDs (`FsF-F1-01D` … `FsF-R1.3-01M`) are
evaluated to pass / partial / fail, rolled up to per-principle F/A/I/R percentages and a
FAIRness level (Advanced ≥75 / Moderate ≥50 / Basic ≥25 / Incomplete).

- Scores are computed **in code** and merely displayed; the RAG/LLM layer only *narrates* them.
- Records with a resolvable PID/DOI can defer to the **authoritative F-UJI REST API**
  (`fair_fairsfair.fuji_live(pid)` → https://www.f-uji.net/).
- Cite: Devaraju & Huber (2023), F-UJI, doi:10.5281/zenodo.6361400; metrics doi:10.5281/zenodo.6461229.

### Current spread (offline seed data)
ChEMBL 100% · Trials 94% · PubMed 88% (open access) vs 79% (subscription) ·
GEO 73% (Moderate, free-text metadata) · unverified seed 42% (Basic) — the integrity signal.
Adding machine-readable-license (FsF-R1.1-02M) and data-format (FsF-I1-02M) metrics
separates sources the way authoritative F-UJI would.

**Honest caveat:** F-UJI is designed for *datasets* assessed via a PID landing page.
GEO records fit perfectly; a compound / trial / paper are scored by the same metric
*logic* but only GEO/DOI objects fully resolve in the live F-UJI service.

## Run
```
python3 fair_fairsfair.py         # score bundled records, print table
python3 pipeline.py --live        # fetch fresh records from all 4 APIs (needs internet)
python3 fair_fairsfair.py --fuji  # authoritative F-UJI scores for DOI/GEO records
python3 resolver.py               # demo: route sample accessions to their source
python3 evaluate_search.py        # recall@k / MRR on the gold set -> search_eval.md
python3 calibrate.py [--fuji]     # heuristic vs F-UJI calibration -> calibration.md
                                  #   (needs internet + F_UJI_USER / F_UJI_PW env creds)
```

On-screen scores are a **provisional heuristic** clearly labeled as such; the `--fuji`
path calls the real F-UJI service and only applies to true dataset objects (GEO / DOIs).
This sandbox has no outbound internet, so the bundled JSON is used for the demo; the
`--live` path runs on any machine with network access.

## Maps to the 6 original deliverable questions
1. **Visible FAIR scoring** → per-metric F-UJI drill-down, not a black-box badge.
2. **Knowledge graph** → re-centerable ego-graph (not a hairball); Open Targets backbone.
3. **Semantic discovery accuracy** → hybrid TF-IDF semantic + keyword modes; next: recall@k on a gold set.
4. **MCP integration** → records pulled live via ChEMBL/Trials/PubMed MCPs; ID-resolver pattern documented.
5. **Operations guide** → this file (split later into runbook / data-onboarding SOP / architecture).
6. **User data infusion** → planned: user file scored by the *same* F-UJI pipeline, session-sandboxed.

## Next
- Wire the live F-UJI API for GEO/DOI records (button currently links to f-uji.net).
- Add the accession → MCP **resolver** (regex-route GSE/NCT/CHEMBL/PMID) end-to-end.
- Build the gold set + recall@k harness for search accuracy.
