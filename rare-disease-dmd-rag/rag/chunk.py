"""Chunk Documents before embedding.

The DMD demo corpus is small enough (titles + abstracts + structured trial
fields) that most documents are already under the target chunk size, so this
mostly acts as a safety net for any longer regulatory or full-text documents
added later. Recursive character splitting with overlap, per the workflow
plan (workflow doc, section 2).
"""
from __future__ import annotations

from .corpus import Document

CHUNK_SIZE = 800  # characters, ~ a few hundred tokens
CHUNK_OVERLAP = 120


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Split any oversized Document into multiple chunk-Documents, each
    keeping the parent's citation/url so retrieval results still resolve
    back to a single source ID."""
    chunked = []
    for doc in docs:
        pieces = split_text(doc.text)
        if len(pieces) == 1:
            chunked.append(doc)
            continue
        for i, piece in enumerate(pieces):
            chunked.append(Document(
                doc_id=f"{doc.doc_id}::chunk{i}", source_type=doc.source_type,
                title=doc.title, text=piece, citation=doc.citation,
                url=doc.url, metadata=doc.metadata,
            ))
    return chunked
