# DMD Clinical Trial Intelligence

Working scaffold for the capstone plan in
`Capstone4_MultiAgent_Clinical_Trial_Intelligence_Workflow.md`. A single
retrieve-and-answer RAG pipeline plus a Comparison Agent run live against a
real, open-access DMD corpus, surfaced through a Streamlit UI, a FastAPI
service, and an MCP stdio server, with structured comparison tables and an
executive dashboard. Also bundles a separate FAIR-ness scoring catalog
(`fair/`) and a knowledge graph (`knowledge_graph/`) merged in from two
companion projects -- see the dedicated section below. Defaults to
extractive (non-LLM) generation and a TF-IDF vector store, both fully
offline -- swap in the "production" backends below once running somewhere
with normal internet access. See [ARCHITECTURE.md](ARCHITECTURE.md) for how
the pieces fit together (including the 2026-07-23 architecture change from
four domain agents to one pipeline), [FILE_GUIDE.md](FILE_GUIDE.md) for a
plain-language file-by-file index, and [DEPLOYMENT.md](DEPLOYMENT.md) for
running this beyond a laptop demo.

## What's real vs. seed data

Per-source counts from `rag.corpus.counts_by_source()` (what the UI tiles
and `/stats` show): **trial 353, literature 7,620, biomarker 61,
regulatory 19.**

- `data/raw/trials_dmd.json` -- 353 real ClinicalTrials.gov records (pulled
  live), restricted to interventional DMD trials, including eligibility
  criteria, primary outcomes, and posted results where available.
- `data/raw/literature_dmd.json` -- 7,620 real PubMed abstracts, the
  complete live result set for the query in `ingestion/fetch_literature.py`
  (`Duchenne muscular dystrophy AND (exon skipping OR gene therapy OR
  dystrophin)`) at the time it was last run, not a sample. Any answer citing
  these **must** attribute PubMed and include the DOI link, per PubMed's
  terms of use.
- `data/raw/biomarker_dmd.json` -- the real ChEMBL dystrophin target record
  plus 52 Open Targets target-disease associations (live, score >= 0.2 --
  see `ingestion/fetch_biomarker.py` for why that cutoff), for 53 of the 61
  biomarker documents. ChEMBL's molecule/compound API is currently down
  (EBI-side outage) -- not wired in yet, follow-up once it's back.
- `data/raw/biomarker_endpoints_dmd.json` -- **seed data, hand-curated,** 8
  standard DMD clinical trial endpoints/biomarkers (dystrophin expression,
  CK, NSAA, 6MWT, FVC, muscle MRI fat fraction, PUL, timed function tests --
  the same endpoints referenced throughout the trials corpus). No live API
  publishes endpoint-definition metadata, so this is general knowledge,
  flagged `needs_verification`. Makes up the remaining 8 of the 61
  biomarker documents.
- `data/raw/regulatory_dmd.json` -- 9 drug approval events (7 verified live
  against openFDA drug labels -- golodirsen, viltolarsen, casimersen,
  givinostat, deflazacort, vamorolone; ataluren is EU-only so has no openFDA
  record, confirmed live, flagged `needs_verification` instead) + 2
  discontinued/failed programs (general knowledge, flagged
  `needs_verification`). Each entry's own `status` field says which.
- `data/raw/regulatory_guidance_dmd.json` -- **seed data, hand-curated.**
  Real FDA/EMA clinical-trial-design guidance documents (eligibility,
  diversity, decentralized trials, RWE, rare disease, accelerated
  approval), verified against FDA.gov/Federal Register at the time of
  writing. Powers the Regulatory Insights table. A couple of entries are
  explicitly flagged draft/status-unresolved -- re-verify before relying
  on those two.

Re-run the ingestion scripts in `ingestion/` on a machine with normal
internet access to refresh the live-pulled files with the latest data
before the workshop -- `fetch_literature.py` takes a couple of minutes
(thousands of articles, batched with checkpointing so a dropped connection
mid-run doesn't lose progress), the others are quick. The two hand-curated
files (`biomarker_endpoints_dmd.json`, `regulatory_guidance_dmd.json`) have
no API to re-fetch from -- re-verify those by hand periodically instead.

## Minimum system requirements

| | Default setup (TF-IDF + extractive) | With `EMBEDDING_BACKEND=hf` | With `LLM_MODE=llm` (local llama.cpp/Ollama) |
|---|---|---|---|
| **Python** | 3.10 or newer (built and tested on 3.12) | same | same |
| **RAM** | 1-2 GB | 2 GB+ (loads `BAAI/bge-base-en-v1.5`, ~400 MB, into memory) | add 6-8 GB **for the LLM server process**, separate from the API/UI |
| **Disk** | ~800 MB for dependencies (see `requirements.txt`) + a few MB for the corpus/index | add ~400 MB for the model download (`requirements-hf.txt`) | add ~5 GB for an 8B Q4_K_M GGUF model, if running one locally |
| **CPU** | 1 vCPU is enough for demo/workshop traffic | 1-2 vCPU (embedding is more compute-heavy than TF-IDF) | local LLM inference is CPU/GPU-bound -- size that process independently |
| **Internet** | Needed once, for `pip install`; needed again only when re-running `ingestion/*.py` to refresh data. Serving queries against an already-built index needs no internet. | | Needed to reach whatever endpoint `OPENAI_API_BASE` points at, unless it's local |
| **OS** | Linux, macOS, or Windows via WSL2 (developed/tested on WSL2) | | |
| **Containers (optional)** | Podman (or Docker) if deploying via `docker-compose.yml` -- see [DEPLOYMENT.md](DEPLOYMENT.md) | | |

None of this needs a GPU -- the default backend is scikit-learn TF-IDF,
not an embedding model. See [DEPLOYMENT.md](DEPLOYMENT.md#resource-sizing)
for the same numbers in the context of an actual deployment (VM sizing,
container limits, etc).

## Quickstart

```bash
pip install -r requirements.txt

# 1. Build the vector index (TF-IDF by default, fully offline)
python -m rag.embed_store

# 2. Try a query from the command line
python -c "from rag.pipeline import ask; r = ask('Compare exon-skipping trial endpoints and biomarker evidence for DMD'); print(r.summary)"

# 3. Run the API
uvicorn api.main:app --reload --port 8000

# 4. Run the Streamlit UI (separate terminal)
streamlit run ui/app.py

# 5. Optional: run the MCP server (separate terminal, needs requirements-mcp.txt)
python -m mcp_server.server
```

**Or, with Docker/Podman -- no local Python setup at all:**

```bash
docker compose up --build   # starts API (:8000) + UI (:8501)
docker compose down         # stops and removes both containers
```

Optional: put `LLM_MODE`, `OPENAI_API_BASE`, `MODEL_NAME`, `OPENAI_API_KEY`
in a `.env` file next to `docker-compose.yml` to use a hosted LLM (e.g.
Groq) instead of the extractive default -- see
[DEPLOYMENT.md](DEPLOYMENT.md#2-docker--podman-compose----one-command-up-one-command-down).

The API and UI both talk to the same already-built index -- no rebuild
happens per request/query. See [ARCHITECTURE.md](ARCHITECTURE.md#api-endpoints-apimainpy)
for the full endpoint list (`/query`, `/compare-trials`,
`/compare-literature`, `/regulatory-insights`, `/stats`, `/health`,
`/fair/catalog`, `/fair/resolve`, `/related/{accession}`, `/feedback`,
`/monitoring/stats`), and
[DEPLOYMENT.md](DEPLOYMENT.md) to run this in Podman or on a persistent
server instead of a laptop.

## FAIR-ness catalog, knowledge graph, monitoring, and MCP server

Four pieces were merged in from two companion projects (`dmd_platform`,
then `fair-discovery`):

- **`fair/`** -- a separate, standards-based FAIR-ness scoring catalog. It
  scores 15 DMD records (GEO/ChEMBL/ClinicalTrials/PubMed) against the
  FAIRsFAIR Data Object Assessment Metrics (as implemented by F-UJI), and
  includes an accession resolver that detects and routes any biomedical ID
  (GSE/NCT/CHEMBL/PMID/DOI/ENSG/EFO/...). Runs on its own 15-record
  dataset, disjoint from the main corpus above. Surfaced via the **FAIR
  Catalog** UI tab and the `/fair/catalog` / `/fair/resolve` API endpoints.
  See [fair/README.md](fair/README.md).
- **`knowledge_graph/`** -- a `networkx` graph of "related records" over
  that same 15-record `fair/` catalog (weighted by shared source/type/
  entities). Surfaced in the FAIR Catalog tab, `GET /related/{accession}`,
  and opportunistically cross-referenced into every `ask()` answer's
  citations (most won't match -- the two datasets barely overlap by ID,
  see `knowledge_graph/kg.py`).
- **`monitoring/`** -- append-only query/feedback JSONL logs + aggregate
  stats, wired into `ask()`, the Ask-a-Question tab's 👍/👎 buttons, and
  `POST /feedback` / `GET /monitoring/stats`.
- **`mcp_server/`** -- an MCP stdio server exposing `search_datasets`,
  `get_dataset`, `ask`, `related_datasets`, `fair_score`, and
  `catalog_stats` as agent tools. Optional dependency, see
  `requirements-mcp.txt`.

None of these introduce dependency conflicts with the main pipeline
(`networkx` is now a required dependency; `mcp` is optional). See
[FILE_GUIDE.md](FILE_GUIDE.md#fair--a-separate-fair-ness-scoring-catalog-merged-in-from-a-companion-demo)
for a file-by-file guide to all four.

## Swapping in the production backends

- **Embeddings/vector store**: set `EMBEDDING_BACKEND=hf` to use
  `sentence-transformers` (`BAAI/bge-base-en-v1.5`) + Chroma instead of
  TF-IDF. Install the extra dependencies first: `pip install -r requirements-hf.txt`
  (kept separate from `requirements.txt` since it pulls in torch, which
  the default TF-IDF backend never needs).
- **LLM generation** (also enables AI-extracted fields in the literature
  comparison table -- see ARCHITECTURE.md): set `LLM_MODE=llm` plus
  `OPENAI_API_BASE`, `MODEL_NAME` (and `OPENAI_API_KEY` if needed) to
  route through any OpenAI-compatible endpoint -- a local Ollama server, a
  local llama.cpp server, Groq's free tier, or Hugging Face Inference API
  all work. Falls back to the extractive (no-LLM) summary automatically
  if the call fails, so a flaky network during the live demo won't break
  it.
  - Ollama: `OPENAI_API_BASE=http://localhost:11434/v1`, `MODEL_NAME=llama3.1`
  - llama.cpp: run `./build/bin/llama-server -m
    models/Llama-3.1-8B-Instruct-Q4_K_M.gguf` (defaults to port 8080), then
    `OPENAI_API_BASE=http://localhost:8080/v1`, `MODEL_NAME=llama3.1` --
    llama-server serves the same `/v1/chat/completions` route, so no code
    changes are needed to switch between the two. See
    [DEPLOYMENT.md](DEPLOYMENT.md#using-a-local-llamacpp-model-instead-of-the-extractive-default)
    if you're running this inside a Podman container.
- **Regulatory data**: build/wire an openFDA MCP server (see workflow doc
  section 4) so regulatory queries retrieve live data instead of the seed
  JSON (`data/raw/regulatory_dmd.json`, the drug-approval history --
  distinct from `data/raw/regulatory_guidance_dmd.json`, the hand-curated
  trial-design guidance table, which has no equivalent API to wire up).

## Branding

`ui/app.py` and `reports/pdf.py` ship with a generic navy (`#0C447C`,
`BRAND_NAVY`/`BRAND_NAME` in `ui/app.py`) and a text-badge fallback logo --
no real logo image is bundled. To brand your own deployment, drop a
`brand_logo.png` into `logo/` (gitignored by default, see `.gitignore`)
and update `BRAND_NAME`/`BRAND_NAVY` in `ui/app.py` and `reports/pdf.py`.
