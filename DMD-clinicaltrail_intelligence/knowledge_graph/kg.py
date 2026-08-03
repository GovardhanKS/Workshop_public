"""Builds a lightweight 'related records' graph from shared source, type,
and entities -- ported from fair-discovery's knowledge_graph/kg.py, which
built the same kind of graph from shared organism/platform/keywords over
GEO dataset records.

Scoped deliberately to the fair/ catalog's 15 records (fair/dmd_datasets.json):
those already carry curated `source`/`type`/`entities` fields, the same shape
fair-discovery's DatasetRecord provided. The main RAG corpus (trials/
literature/biomarker/regulatory, loaded via rag.corpus.load_all()) has no
equivalent curated fields and only sparse ID overlap with the fair/ catalog,
so building a graph over it would mean inventing keywords rather than reusing
real ones -- out of scope here. See fair/service.py for the catalog this
graph is built from, and ui/app.py's FAIR Catalog tab for where it's shown.
"""
from __future__ import annotations

import json
import pathlib
from typing import Dict, List

import networkx as nx
from networkx.readwrite import json_graph

KG_PATH = pathlib.Path(__file__).parent.parent / "data" / "kg.json"


def build_kg(records: List[dict]) -> nx.Graph:
    graph = nx.Graph()
    for r in records:
        graph.add_node(r["id"], title=r["title"], source=r["source"], type=r["type"],
                        entities=r.get("entities", []))

    for i, a in enumerate(records):
        for b in records[i + 1:]:
            weight = _shared_weight(a, b)
            if weight > 0:
                graph.add_edge(a["id"], b["id"], weight=weight)

    return graph


def _shared_weight(a: dict, b: dict) -> float:
    weight = 0.0
    if a.get("source") and a["source"] == b.get("source"):
        weight += 1.0
    if a.get("type") and a["type"] == b.get("type"):
        weight += 1.0
    shared_entities = {e.lower() for e in a.get("entities", [])} & {e.lower() for e in b.get("entities", [])}
    weight += 0.5 * len(shared_entities)
    return weight


def related_datasets(graph: nx.Graph, node_id: str, k: int = 5) -> List[Dict]:
    if node_id not in graph:
        return []
    neighbors = sorted(graph[node_id].items(), key=lambda item: item[1].get("weight", 0), reverse=True)
    return [
        {
            "id": neighbor,
            "weight": data.get("weight", 0),
            **{attr: val for attr, val in graph.nodes[neighbor].items()},
        }
        for neighbor, data in neighbors[:k]
    ]


def save_kg(graph: nx.Graph, path: pathlib.Path = KG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(json_graph.node_link_data(graph), fh)


def load_kg(path: pathlib.Path = KG_PATH) -> nx.Graph:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return json_graph.node_link_graph(data)


def _normalize(node_id: str) -> str:
    return node_id.replace(" ", "").replace(":", "").upper()


def related_for_citations(citations: List[str], k: int = 3) -> Dict[str, List[Dict]]:
    """Best-effort match of RAG-corpus citations (e.g. 'NCT06817382', 'PMID
    32717791') against the fair/ catalog graph's node IDs, which use a
    slightly different format ('PMID32717791', no space). Returns only the
    citations that actually hit a catalog node -- the two datasets barely
    overlap by ID, so an empty result for most queries is expected, not a bug."""
    graph = get_graph()
    by_normalized = {_normalize(n): n for n in graph.nodes}
    out: Dict[str, List[Dict]] = {}
    for citation in citations:
        node = by_normalized.get(_normalize(citation))
        if node:
            neighbors = related_datasets(graph, node, k=k)
            if neighbors:
                out[citation] = neighbors
    return out


_GRAPH_CACHE: nx.Graph | None = None


def get_graph() -> nx.Graph:
    """Build (and cache) the graph over the fair/ catalog once per process,
    mirroring rag.embed_store.get_store()'s load-once-and-reuse pattern."""
    global _GRAPH_CACHE
    if _GRAPH_CACHE is None:
        from fair import service as fair_service

        _GRAPH_CACHE = build_kg(fair_service.scored_catalog())
    return _GRAPH_CACHE
