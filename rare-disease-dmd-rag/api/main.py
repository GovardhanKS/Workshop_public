"""FastAPI service exposing the DMD RAG pipeline.

Run: uvicorn api.main:app --reload --port 8000

Endpoints:
  GET  /health              -- liveness check
  GET  /stats                -- corpus size + query counters for the exec dashboard
  GET  /dashboard             -- static HTML snapshot of corpus counts
  POST /query                -- {"question": "...", "top_k": 10}  (top_k optional)
  POST /generate-summary      -- alias of /query
  POST /compare-trials        -- {"trialA": "NCT...", "trialB": "NCT..."}
  POST /compare-literature    -- {"pmidA": "...", "pmidB": "..."}
  POST /regulatory-insights   -- {} (no body needed) -> guidance table
  POST /feedback              -- {"question": "...", "rating": 1-5, "comment": "..."}
  GET  /monitoring/stats      -- query/feedback log stats

None of these rebuild the RAG index per request -- the index is built once
by `python -m rag.embed_store` and loaded once per process (see
rag/embed_store.py's get_store() cache). A request only ever searches the
already-built index.
"""
from __future__ import annotations

import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agents import comparison
from monitoring.feedback import compute_stats, log_feedback
from rag.corpus import counts_by_source
from rag.pipeline import TOP_K_DEFAULT, ask

app = FastAPI(title="DMD Clinical Trial Intelligence API", version="0.3.0")

_QUERY_COUNT = 0  # in-memory counter, resets on restart -- fine here, not a durable metric
_DASHBOARD_PATH = pathlib.Path(__file__).parent.parent / "static" / "corpus_dashboard.html"


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None


class Citation(BaseModel):
    citation: str
    source_type: str
    url: str | None


class QueryResponse(BaseModel):
    question: str
    summary: str
    citations: list[Citation]
    note: str | None = None


class CompareTrialsRequest(BaseModel):
    trialA: str
    trialB: str


class CompareLiteratureRequest(BaseModel):
    pmidA: str
    pmidB: str


class ComparisonRowOut(BaseModel):
    parameter: str
    value_a: str
    value_b: str
    ai_observation: str


class ComparisonResponse(BaseModel):
    label_a: str
    label_b: str
    summary: str
    comparison: list[ComparisonRowOut]
    caveat: str | None = None


class FeedbackRequest(BaseModel):
    question: str
    rating: int
    comment: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "corpus_sources": list(counts_by_source().keys())}


@app.get("/stats")
def stats():
    counts = counts_by_source()
    return {
        "trials_indexed": counts.get("trial", 0),
        "publications_indexed": counts.get("literature", 0),
        "regulatory_documents_indexed": counts.get("regulatory", 0),
        "biomarker_records_indexed": counts.get("biomarker", 0),
        "queries_performed": _QUERY_COUNT,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """A self-hosted, shareable snapshot of the corpus numbers -- static HTML
    served from this app itself, not a third-party link."""
    if not _DASHBOARD_PATH.exists():
        raise HTTPException(404, "Dashboard not built -- see static/corpus_dashboard.html")
    return _DASHBOARD_PATH.read_text()


def _run_query(req: QueryRequest) -> QueryResponse:
    global _QUERY_COUNT
    _QUERY_COUNT += 1
    report = ask(req.question, top_k=req.top_k or TOP_K_DEFAULT)
    return QueryResponse(
        question=report.question, summary=report.summary,
        citations=[Citation(**c) for c in report.citations], note=report.note,
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    return _run_query(req)


@app.post("/generate-summary", response_model=QueryResponse)
def generate_summary(req: QueryRequest):
    return _run_query(req)


@app.post("/compare-trials", response_model=ComparisonResponse)
def compare_trials(req: CompareTrialsRequest):
    global _QUERY_COUNT
    _QUERY_COUNT += 1
    try:
        result = comparison.compare_trials(req.trialA, req.trialB)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ComparisonResponse(
        label_a=result.label_a, label_b=result.label_b, summary=result.summary,
        comparison=[ComparisonRowOut(**vars(r)) for r in result.rows], caveat=result.caveat,
    )


@app.post("/compare-literature", response_model=ComparisonResponse)
def compare_literature(req: CompareLiteratureRequest):
    global _QUERY_COUNT
    _QUERY_COUNT += 1
    try:
        result = comparison.compare_literature(req.pmidA, req.pmidB)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ComparisonResponse(
        label_a=result.label_a, label_b=result.label_b, summary=result.summary,
        comparison=[ComparisonRowOut(**vars(r)) for r in result.rows], caveat=result.caveat,
    )


@app.post("/regulatory-insights")
def regulatory_insights():
    return comparison.load_regulatory_guidance()


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    log_feedback(req.question, req.rating, req.comment)
    return {"status": "recorded"}


@app.get("/monitoring/stats")
def monitoring_stats():
    return compute_stats()
