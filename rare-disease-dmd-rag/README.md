# DMD Clinical Trial Intelligence

A retrieval-augmented (RAG) pipeline for Duchenne muscular dystrophy (DMD)
research. Ask a question and get a cited answer, compare two trials or two
papers side by side, or browse regulatory history -- all grounded in real
sources, not model guesswork.

## What it does

- **Ask a question** and get a grounded, cited answer pulled from clinical
  trial, literature, biomarker, and regulatory data.
- **Compare two trials or two papers** side by side, with an AI-written
  summary alongside the structured facts.
- **Browse regulatory history** -- FDA/EMA drug approvals and
  clinical-trial-design guidance.
- **Track corpus size and query volume** from a simple dashboard.

By default everything runs fully offline -- no API key, no internet needed
after setup -- using extractive summarization and a TF-IDF search index.
Swap in a real LLM or embedding model any time; see Configuration below.

## Quickstart

```bash
pip install -r requirements.txt

python -m rag.embed_store          # build the search index once

uvicorn api.main:app --reload --port 8000     # terminal 1
streamlit run ui/app.py                        # terminal 2
```

Or with Docker/Podman, no local Python setup at all:

```bash
docker compose up --build
docker compose down
```

- UI: http://localhost:8501
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8000/dashboard

## Data

| Source | What it is |
|---|---|
| Clinical trials | ClinicalTrials.gov, pulled live |
| Literature | PubMed abstracts, pulled live, tagged with disease entities |
| Biomarker | ChEMBL + Open Targets (live) plus a handful of curated clinical endpoint definitions |
| Regulatory | Drug approvals verified against openFDA, plus hand-curated FDA/EMA trial-design guidance |

Re-run the scripts in `ingestion/` any time you want fresher data:

```bash
python -m ingestion.fetch_trials
python -m ingestion.fetch_literature
python -m ingestion.fetch_biomarker
python -m ingestion.fetch_regulatory
python -m rag.embed_store           # rebuild the index afterward
```

The FDA/EMA guidance file has no API to pull from -- it's hand-curated and
needs periodic manual re-verification.

## Configuration

Everything below is optional -- copy `.env.example` to `.env` and fill in
only what you need:

- **Use a real LLM** instead of the offline extractive default: set
  `LLM_MODE=llm` plus `OPENAI_API_BASE`, `MODEL_NAME`, and `OPENAI_API_KEY`
  (any OpenAI-compatible endpoint works -- Groq, Ollama, llama.cpp, HF
  Inference). Falls back to the extractive summary automatically if the
  call fails.
- **Use a production embedding backend**: set `EMBEDDING_BACKEND=hf` for
  sentence-transformers + Chroma instead of TF-IDF (`pip install -r
  requirements-hf.txt` first).

See [DEPLOYMENT.md](DEPLOYMENT.md) for running this beyond a laptop, and
[ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together.

## Branding

No real logo ships with this project -- the UI and PDF exports fall back to
a generic text badge. Drop your own `brand_logo.png` into `logo/`
(gitignored) to brand your own deployment.

## Notes

This pipeline evolves as we learn more about what works well for RAG over
biomedical data -- expect changes to retrieval, chunking, and data sources
over time, the same way any actively developed pipeline does.
