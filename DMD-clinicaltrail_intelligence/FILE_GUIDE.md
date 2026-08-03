# Plain-English Guide to Every File

This project answers questions about Duchenne Muscular
Dystrophy (DMD) by pulling together evidence from clinical trials,
scientific papers, drug-safety records, and biology databases, then
writing a single, source-cited answer. This guide explains what each
file does, in plain language, without assuming a programming background.

## The big picture

> **Updated 2026-07-23**: this used to be "four reporters + an editor" (four
> domain agents, each answering independently, then synthesized). That's
> been replaced by one librarian who searches the whole filing cabinet at
> once — simpler, and the four topics still exist as labels on the
> evidence, not as separate people. If you see old docs/notes describing
> "the Literature Agent" etc., they're describing the previous design.

Think of it like a small newsroom:

1. A **librarian** (`rag/pipeline.py`) searches the whole filing cabinet
   (the data files + search index) for whatever's most relevant to the
   question, across trials, research papers, biology, and regulatory
   history at once, then writes one clean, cited answer.
2. A **fact-checker** (the Comparison Agent) pulls up two specific
   records side by side — two trials, or two papers — and builds a
   structured comparison table instead of a paragraph.
3. Three **front desks** let a person actually ask a question: a web page
   (Streamlit UI), a programmatic API (for other software to call), and
   an MCP server (for AI agents/tools to call).
4. A separate, smaller **card catalog** (`fair/` + `knowledge_graph/`) rates
   how trustworthy/reusable 15 specific records are, and shows how they
   relate to each other — independent of the main filing cabinet above.
5. A **logbook** (`monitoring/`) quietly notes down every question asked
   and every thumbs-up/down given, so there's a record of what people
   actually asked and whether the answers helped.

## Top-level files

| File | What it's for |
|---|---|
| `README.md` | The project's front page — what it does, what's real data vs. placeholder data, and how to run it. |
| `ARCHITECTURE.md` | A more technical diagram/explanation of how all the pieces connect (for developers). |
| `FILE_GUIDE.md` | This file — a plain-language index of every file in the project. |
| `DEPLOYMENT.md` | How to actually run this somewhere persistent — locally, in a container (Podman), or on a small always-on server — plus how much hardware it needs. |
| `requirements.txt` | The shopping list of software packages needed to run the project (used by the setup command `pip install`). |
| `requirements-hf.txt` | An optional, second shopping list — only needed if you switch on the heavier "production" search backend (see `rag/embed_store.py` below). Kept separate so the default setup stays small and fast to install. |
| `requirements-mcp.txt` | An optional, third shopping list — only needed to run `mcp_server/server.py`. |
| `reports/pdf.py` | Turns any of the tables/answers into a branded, downloadable PDF — this is what powers every "Download as PDF" button in the web page. |
| `Dockerfile`, `docker-compose.yml` | Recipes for packaging this project into a self-contained container image, so it runs the same way on any machine without a manual setup. See `DEPLOYMENT.md`. |
| `logo/` | Gitignored. Drop an optional `brand_logo.png` here to brand the web page header and PDF exports -- falls back to a generic text badge if absent. |

## `ui/` — the web page people use to ask questions

| File | What it's for |
|---|---|
| `ui/app.py` | The Streamlit web page: branded header (generic badge by default, see `logo/`), source-type tiles showing corpus counts, and six tabs — Ask a Question (grounded answer + evidence + related records + 👍/👎 feedback), Compare Trials, Compare Literature, Regulatory Insights, an Executive Dashboard with at-a-glance counts, and FAIR Catalog (see `fair/` below). Every table has a "Download as PDF" button. |

## `api/` — the programmatic front desk (for other software)

| File | What it's for |
|---|---|
| `api/main.py` | A web service (API) that lets other programs send a question — or a pair of trial/paper IDs to compare — and get back structured JSON, without needing the visual web page. Includes `/health` (is it running?), `/stats` (how much data is loaded, how many questions asked), `/fair/catalog` + `/fair/resolve` (see `fair/` below), `/related/{accession}` (see `knowledge_graph/` below), and `/feedback` + `/monitoring/stats` (see `monitoring/` below). |

## `mcp_server/` — the AI-agent front desk

| File | What it's for |
|---|---|
| `mcp_server/server.py` | An MCP (Model Context Protocol) server: the same capabilities as the API above (search, ask, get a record, find related records, get a FAIR score, get catalog stats), but exposed as tools an AI agent can call directly rather than as HTTP endpoints a person browses to. Run with `python -m mcp_server.server`; needs `pip install -r requirements-mcp.txt` first. |

## `agents/` — the librarian's writer, and the fact-checker

| File | What it's for |
|---|---|
| `agents/comparison.py` | The "fact-checker" — looks up two specific trials or two specific papers by their ID and builds the side-by-side comparison tables (Phase, Sample Size, Primary Endpoint, etc., plus an AI Observation column), and loads the Regulatory Insights guidance table. |
| `agents/llm.py` | The "writer": turns a pile of evidence snippets into readable prose, or pulls specific facts (like sample size) out of an abstract's free text. Can run in a simple no-AI mode (just lists the evidence) or a full AI mode (calls a language model) — configurable, and safely falls back to the simple mode if the AI call fails. |

## `rag/` — the shared filing cabinet and search system

*(RAG = "Retrieval-Augmented Generation" — a fancy term for "look up real
facts first, then write the answer from those facts" rather than letting
an AI make things up.)*

| File | What it's for |
|---|---|
| `rag/corpus.py` | Reads the raw data files (see `data/raw/` below) and converts each trial, article, biology record, or regulatory event into a standard format every other file can work with. |
| `rag/chunk.py` | Splits any very long document into smaller pieces, so the search system can find and quote the exact relevant passage rather than an entire long document. |
| `rag/embed_store.py` | Builds and manages the searchable index — like the card catalog of the filing cabinet. Supports a simple offline mode (default) and a more advanced production mode that needs the extra packages in `requirements-hf.txt`. Loads the index once and reuses it for every question asked afterward, rather than rebuilding it each time. |
| `rag/retrieve.py` | The actual "look this up" function that fetches the most relevant facts for a given question — keeps only the best-scoring passage per source (so one long trial doesn't crowd out everything else), and can optionally double-check its top results with a slower, more careful re-ranking pass (`RERANK=1`). |
| `rag/pipeline.py` | The librarian: takes a question, calls `retrieve.py` once across the whole corpus, hands the results to `agents/llm.py` to write the answer, and jots the question down in the logbook (`monitoring/`). This is what `ui/app.py`, `api/main.py`, and `mcp_server/server.py` all call. |

## `knowledge_graph/` — how the FAIR catalog's 15 records relate to each other

| File | What it's for |
|---|---|
| `knowledge_graph/kg.py` | Draws a map connecting the FAIR catalog's 15 records to each other — two records are linked more strongly if they're from the same source, the same type (compound/trial/paper), or mention the same things (e.g. both mention "dystrophin"). Powers the "Related records" section of the FAIR Catalog tab, the `/related/{accession}` endpoint, and a best-effort attempt to spot when something in a regular answer also happens to be in this smaller 15-record catalog. |

## `monitoring/` — the logbook

| File | What it's for |
|---|---|
| `monitoring/feedback.py` | Writes down every question asked and every 👍/👎 given to a plain text logbook (`data/query_log.jsonl`, `data/feedback_log.jsonl` — one line per entry, human-readable), and can tally them up into simple stats (how many questions, how many got a thumbs-up, etc.) for `GET /monitoring/stats`. |

## `fair/` — a separate FAIR-ness scoring catalog, merged in from a companion demo

*(FAIR = Findable, Accessible, Interoperable, Reusable — a recognized standard for
"is this dataset actually trustworthy and usable," not a home-grown rubric.)*

This is a standalone 15-record catalog (GEO, ChEMBL, ClinicalTrials.gov, PubMed)
scored against the FAIRsFAIR/F-UJI standard, plus an accession resolver. It runs
independently of the main agents/RAG pipeline above and is surfaced through its own
UI tab ("FAIR Catalog") and API endpoints (`/fair/catalog`, `/fair/resolve`).

| File | What it's for |
|---|---|
| `fair/pipeline.py` | Ingest (live API fetch of GEO/ClinicalTrials/ChEMBL) + normalize to one flat schema. Run standalone: `python fair/pipeline.py [--live]`. |
| `fair/fair_fairsfair.py` | The actual FAIR scorer — 16 FAIRsFAIR/F-UJI metric IDs evaluated to pass/partial/fail, rolled up to F/A/I/R percentages. Can also call the real, authoritative F-UJI web service for records with a resolvable DOI/PID. |
| `fair/resolver.py` | Paste any biomedical ID (GSE/NCT/CHEMBL/PMID/DOI/ENSG/EFO/...) → detects its type → routes it to the right source, and FAIR-scores it if it's already in the catalog. |
| `fair/evaluate_search.py` | A search-accuracy report card (recall@k / MRR) on a hand-labeled gold set — run standalone: `python fair/evaluate_search.py` → `search_eval.md`. |
| `fair/calibrate.py` | Compares this catalog's heuristic FAIR score against the authoritative F-UJI service, to quantify and tighten the gap — run standalone: `python fair/calibrate.py [--fuji]` → `calibration.md`. |
| `fair/dmd_datasets.json` | The 15 normalized records this catalog scores (real ChEMBL/Trials/PubMed; seed GEO). |
| `fair/service.py` | The thin glue code the main API/UI import to reach `fair_fairsfair.py`/`resolver.py` without duplicating logic. |
| `fair/README.md`, `fair/PITCH.md`, `fair/COVERAGE.md` | The original companion demo's own docs — audience-facing pitch, run instructions, and deliverable-coverage ledger. |

## `ingestion/` — the scripts that stock the filing cabinet

These are run occasionally (not during a live demo) to fetch fresh data
from public, free data sources on the internet.

| File | What it's for |
|---|---|
| `ingestion/fetch_trials.py` | Downloads DMD clinical trial records from ClinicalTrials.gov — restricted to actual drug/device trials (not purely observational studies), including eligibility criteria and results where posted, so the Compare Trials table has real data to show. |
| `ingestion/fetch_literature.py` | Downloads DMD-related scientific article abstracts from PubMed. |
| `ingestion/fetch_biomarker.py` | Downloads dystrophin gene/protein biology data from ChEMBL and Open Targets. |
| `ingestion/fetch_regulatory.py` | Downloads FDA drug label and safety-event data from openFDA. This one still needs to be run/wired up — see the data status table below. |

## `data/` — where the facts actually live

| File | What it's for |
|---|---|
| `data/raw/trials_dmd.json` | Real, live-pulled clinical trial records. |
| `data/raw/literature_dmd.json` | Real, live-pulled PubMed article abstracts. |
| `data/raw/biomarker_dmd.json` | Real, live-pulled biology/target data. |
| `data/raw/regulatory_dmd.json` | **Placeholder data, not yet verified** — built from general knowledge rather than pulled live from the FDA. Needs `ingestion/fetch_regulatory.py` run before it should be trusted as fact. |
| `data/raw/regulatory_guidance_dmd.json` | Hand-researched list of real FDA/EMA guidance documents relevant to DMD trial design (eligibility, diversity, decentralized trials, real-world evidence, rare disease, accelerated approval). This is what fills the Regulatory Insights table. A few entries are explicitly marked "draft" or "status unresolved" where the underlying guidance itself hasn't been finalized — that's the guidance's real-world status, not an error in this file. |
| `data/index_tfidf.pkl` | The pre-built search index (the "card catalog") generated from all the files above, so the system doesn't have to rebuild it every time someone asks a question. |
| `data/query_log.jsonl`, `data/feedback_log.jsonl` | The logbook `monitoring/feedback.py` writes to — created the first time a question is asked / feedback is given, not checked into the repo. |

## Not covered above

- `.venv/` — a self-contained folder of installed software packages
  needed to run the project. Not something to open or edit; it's managed
  automatically by the setup tools.
- `__pycache__/` folders and `.pyc` files — automatically generated
  temporary files that speed up re-running the code. Safe to ignore.
