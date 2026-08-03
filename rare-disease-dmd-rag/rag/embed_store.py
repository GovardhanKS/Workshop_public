"""Vector store for the DMD demo corpus.

Two backends:
  - "tfidf" (default): scikit-learn TF-IDF + cosine similarity. Fully
    offline, no model download, no API key. Good enough for a demo-sized
    corpus (tens of documents) and for environments without internet
    access to Hugging Face.
  - "hf": sentence-transformers open embedding model (BAAI/bge-base-en-v1.5
    by default) + Chroma. This is the production path per the workflow
    doc (section 3) -- switch to it once running somewhere with normal
    internet access, by setting EMBEDDING_BACKEND=hf.

Both backends expose the same .query(text, top_k) -> list[(Document, score)]
interface so the rest of the pipeline doesn't care which one is active.
"""
from __future__ import annotations

import os
import pickle
import pathlib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .corpus import Document, load_all
from .chunk import chunk_documents

INDEX_PATH = pathlib.Path(__file__).parent.parent / "data" / "index_tfidf.pkl"
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "tfidf")


class TfidfStore:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
        self.docs: list[Document] = []
        self.matrix = None

    def build(self, docs: list[Document]):
        self.docs = docs
        texts = [d.text for d in docs]
        self.matrix = self.vectorizer.fit_transform(texts)
        return self

    def query(self, text: str, top_k: int = 5, source_type: str | None = None):
        query_vec = self.vectorizer.transform([text])
        sims = cosine_similarity(query_vec, self.matrix)[0]
        ranked = sorted(range(len(self.docs)), key=lambda i: sims[i], reverse=True)
        results = []
        for i in ranked:
            doc = self.docs[i]
            if source_type and doc.source_type != source_type:
                continue
            if sims[i] <= 0:
                continue
            results.append((doc, float(sims[i])))
            if len(results) >= top_k:
                break
        return results

    def save(self, path: pathlib.Path = INDEX_PATH):
        # Pickle the fitted vectorizer/matrix/docs as a plain dict rather
        # than `self` -- building via `python -m rag.embed_store` gives
        # TfidfStore a __module__ of "__main__" in that process, so
        # pickling the instance directly fails to unpickle in any other
        # process (the API, the UI) that imports this module normally.
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "docs": self.docs, "matrix": self.matrix}, f)

    @classmethod
    def load(cls, path: pathlib.Path = INDEX_PATH) -> "TfidfStore":
        with open(path, "rb") as f:
            data = pickle.load(f)
        store = cls()
        store.vectorizer = data["vectorizer"]
        store.docs = data["docs"]
        store.matrix = data["matrix"]
        return store


class HFChromaStore:
    """Production embedding backend -- open-weight sentence-transformers
    model + Chroma, matching the workflow doc's tool-stack recommendation.
    Not exercised in the offline demo sandbox; use once deployed with
    internet access."""

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        import chromadb
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=str(INDEX_PATH.parent / "chroma"))
        self.collection = self.client.get_or_create_collection("dmd_corpus")

    def build(self, docs: list[Document]):
        embeddings = self.model.encode([d.text for d in docs]).tolist()
        self.collection.add(
            ids=[d.doc_id for d in docs],
            embeddings=embeddings,
            documents=[d.text for d in docs],
            metadatas=[{"citation": d.citation, "source_type": d.source_type,
                        "title": d.title, "url": d.url or ""} for d in docs],
        )
        return self

    def query(self, text: str, top_k: int = 5, source_type: str | None = None):
        embedding = self.model.encode([text]).tolist()
        where = {"source_type": source_type} if source_type else None
        res = self.collection.query(query_embeddings=embedding, n_results=top_k, where=where)
        results = []
        for doc_text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            doc = Document(doc_id=meta["citation"], source_type=meta["source_type"],
                            title=meta["title"], text=doc_text, citation=meta["citation"],
                            url=meta["url"] or None)
            results.append((doc, 1 - dist))
        return results


def build_index(backend: str = EMBEDDING_BACKEND):
    docs = chunk_documents(load_all())
    if backend == "hf":
        store = HFChromaStore().build(docs)
    else:
        store = TfidfStore().build(docs)
        store.save()
    return store


_STORE_CACHE: dict[str, TfidfStore | HFChromaStore] = {}


def get_store(backend: str = EMBEDDING_BACKEND):
    """Load once per process and reuse -- the API/UI serve many queries
    against the same index, so re-reading the pickle from disk (or
    reloading the HF model) on every request would waste time and memory
    for no benefit."""
    if backend in _STORE_CACHE:
        return _STORE_CACHE[backend]
    if backend == "hf":
        store = HFChromaStore()
    elif INDEX_PATH.exists():
        store = TfidfStore.load()
    else:
        store = build_index(backend)
    _STORE_CACHE[backend] = store
    return store


if __name__ == "__main__":
    store = build_index()
    print(f"Indexed {len(store.docs)} chunks using backend={EMBEDDING_BACKEND}")
