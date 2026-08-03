"""Pull DMD literature from PubMed via NCBI E-utilities (free, no key needed
for light use; get an API key from NCBI for higher rate limits).

Same caveat as fetch_trials.py: run on a machine with internet access.
data/raw/literature_dmd.json currently holds a sample pulled via an MCP
PubMed connector. Attribution requirement: any answer generated from this
data must cite PubMed and include the DOI link for the article referenced.
"""
import json
import pathlib
import time
import requests
import xml.etree.ElementTree as ET

OUT_PATH = pathlib.Path(__file__).parent.parent / "data" / "raw" / "literature_dmd.json"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBTATOR = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"
QUERY = "Duchenne muscular dystrophy AND (exon skipping OR gene therapy OR dystrophin)"


def search_pmids(query: str, max_results: int = 10000) -> list[str]:
    resp = requests.get(ESEARCH, params={
        "db": "pubmed", "term": query, "retmax": max_results, "retmode": "json",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["esearchresult"]["idlist"]


def _fetch_batch_xml(batch: list[str], attempts: int = 4) -> bytes:
    """A 200-ID batch is a multi-MB response -- occasionally drops mid-stream
    on a flaky connection. Retry with backoff rather than losing the whole
    run to one bad batch."""
    for attempt in range(attempts):
        try:
            resp = requests.get(EFETCH, params={
                "db": "pubmed", "id": ",".join(batch), "retmode": "xml",
            }, timeout=60)
            resp.raise_for_status()
            return resp.content
        except (requests.exceptions.RequestException,) as exc:
            if attempt == attempts - 1:
                raise
            wait = 2 ** attempt
            print(f"  batch fetch failed ({exc}), retrying in {wait}s...")
            time.sleep(wait)


def _parse_batch(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    articles = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID")
        title = art.findtext(".//ArticleTitle") or ""
        abstract = " ".join(t.text or "" for t in art.findall(".//AbstractText"))
        doi = None
        for eid in art.findall(".//ArticleId"):
            if eid.get("IdType") == "doi":
                doi = eid.text
        journal = art.findtext(".//Journal/Title") or ""
        year = art.findtext(".//PubDate/Year") or ""
        articles.append({
            "pmid": pmid, "doi": doi, "title": title,
            "journal": journal, "year": year, "abstract": abstract,
        })
    return articles


def _write_out(articles: list[dict]) -> None:
    OUT_PATH.write_text(json.dumps({
        "source": "PubMed",
        "attribution": "According to PubMed (https://pubmed.ncbi.nlm.nih.gov/). Cite the DOI for any article referenced in generated answers.",
        "query": QUERY,
        "articles": articles,
    }, indent=2))


def fetch_metadata(pmids: list[str], batch_size: int = 100, checkpoint: bool = True) -> list[dict]:
    """Fetches in batches and writes to OUT_PATH after every batch (not just
    at the end) -- a multi-thousand-article pull takes several minutes over
    dozens of requests, and a late failure shouldn't throw away everything
    fetched so far."""
    articles = []
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        content = _fetch_batch_xml(batch)
        articles.extend(_parse_batch(content))
        print(f"  fetched {len(articles)}/{len(pmids)}")
        if checkpoint:
            _write_out(articles)
        time.sleep(0.4)  # be polite to NCBI's rate limits
    return articles


def fetch_disease_entities(pmids: list[str], batch_size: int = 100) -> dict[str, list[str]]:
    """NCBI PubTator3 -- a free, no-auth, pre-trained biomedical NER +
    normalization service (MeSH-linked Disease/Chemical/Gene/Species
    entities), run once here at ingestion time rather than live at
    comparison-click time. Offline-safe by construction: the result gets
    cached into literature_dmd.json just like everything else, so a demo
    running with no network never notices this dependency existed."""
    diseases_by_pmid: dict[str, list[str]] = {}
    for i in range(0, len(pmids), batch_size):
        batch = [p for p in pmids[i:i + batch_size] if p]
        for attempt in range(4):
            try:
                resp = requests.get(PUBTATOR, params={"pmids": ",".join(batch)}, timeout=30)
                resp.raise_for_status()
                docs = resp.json().get("PubTator3", [])
                break
            except requests.exceptions.RequestException as exc:
                if attempt == 3:
                    print(f"  PubTator batch failed permanently ({exc}), skipping {len(batch)} PMIDs")
                    docs = []
                    break
                wait = 2 ** attempt
                print(f"  PubTator batch failed ({exc}), retrying in {wait}s...")
                time.sleep(wait)
        for doc in docs:
            pmid = doc.get("id", "").split("|")[0]
            names = []
            seen = set()
            for passage in doc.get("passages", []):
                for ann in passage.get("annotations", []):
                    if ann.get("infons", {}).get("type") == "Disease":
                        name = ann["infons"].get("name")
                        if name and name.lower() not in seen:
                            seen.add(name.lower())
                            names.append(name)
            if pmid:
                diseases_by_pmid[pmid] = names
        print(f"  disease-tagged {min(i + batch_size, len(pmids))}/{len(pmids)}")
        time.sleep(0.3)
    return diseases_by_pmid


def enrich_existing_with_diseases() -> None:
    """Run PubTator entity extraction against an already-fetched
    literature_dmd.json in place, without re-pulling PubMed metadata --
    for backfilling disease tags onto a corpus fetched before this
    enrichment step existed."""
    data = json.loads(OUT_PATH.read_text())
    articles = data["articles"]
    pmids = [a["pmid"] for a in articles]
    diseases_by_pmid = fetch_disease_entities(pmids)
    for article in articles:
        article["diseases"] = diseases_by_pmid.get(article["pmid"], [])
    OUT_PATH.write_text(json.dumps(data, indent=2))
    tagged = sum(1 for a in articles if a["diseases"])
    print(f"Tagged {tagged}/{len(articles)} articles with disease entities")


if __name__ == "__main__":
    pmids = search_pmids(QUERY)
    print(f"Found {len(pmids)} matching PMIDs, fetching in batches...")
    articles = fetch_metadata(pmids)
    print("Fetching disease entities via PubTator3...")
    diseases_by_pmid = fetch_disease_entities([a["pmid"] for a in articles])
    for article in articles:
        article["diseases"] = diseases_by_pmid.get(article["pmid"], [])
    _write_out(articles)
    print(f"Wrote {len(articles)} articles to {OUT_PATH}")
