"""Append-only query and feedback logs, plus simple aggregate stats -- the
demo's minimal observability layer. Ported from fair-discovery's
monitoring/feedback.py; that version threaded a pydantic Config object
through for the log paths, which this project has no equivalent of, so the
paths are plain module-level constants instead (same pattern as
rag/embed_store.py's INDEX_PATH).
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
QUERY_LOG_PATH = DATA_DIR / "query_log.jsonl"
FEEDBACK_LOG_PATH = DATA_DIR / "feedback_log.jsonl"


def _append_jsonl(path: pathlib.Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _read_jsonl(path: pathlib.Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def log_query(query: str, citations: List[str], used_llm: bool) -> None:
    _append_jsonl(
        QUERY_LOG_PATH,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "citations": citations,
            "used_llm": used_llm,
        },
    )


def log_feedback(query: str, rating: int, comment: Optional[str] = None) -> None:
    _append_jsonl(
        FEEDBACK_LOG_PATH,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "rating": rating,
            "comment": comment,
        },
    )


def compute_stats() -> Dict[str, Any]:
    queries = _read_jsonl(QUERY_LOG_PATH)
    feedback = _read_jsonl(FEEDBACK_LOG_PATH)

    top_queries = Counter(q["query"] for q in queries).most_common(5)
    ratings = [f["rating"] for f in feedback if isinstance(f.get("rating"), (int, float))]

    return {
        "total_queries": len(queries),
        "queries_answered_by_llm": sum(1 for q in queries if q.get("used_llm")),
        "queries_answered_extractively": sum(1 for q in queries if not q.get("used_llm")),
        "total_feedback": len(feedback),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "top_queries": [{"query": q, "count": c} for q, c in top_queries],
    }
