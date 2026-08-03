"""
Accession resolver: paste any biomedical identifier -> detect type -> route to the
right source -> return the normalized, FAIR-scored record (from catalog or live fetch).

This is the "MCP integration" story: the resolver decides WHICH source/tool handles an
ID; in the agent those routes are the ChEMBL/ClinicalTrials/PubMed MCPs, and GEO/SRA via
NCBI E-utilities.
"""
import re, json, os
try:
    from . import fair_fairsfair as ff  # imported as fair.resolver
except ImportError:
    import fair_fairsfair as ff  # run directly as a script

HERE = os.path.dirname(os.path.abspath(__file__))

# identifier grammar -> (source, resolver route / MCP tool)
PATTERNS = [
    (r"^GSE\d+$",              "GEO",                "NCBI E-utilities (db=gds)"),
    (r"^GDS\d+$",              "GEO",                "NCBI E-utilities (db=gds)"),
    (r"^GSM\d+$",              "GEO",                "NCBI E-utilities (sample)"),
    (r"^(SRR|SRX|SRP|SRS)\d+$","SRA",                "NCBI E-utilities (db=sra)"),
    (r"^PRJNA\d+$",            "BioProject",         "NCBI E-utilities (db=bioproject)"),
    (r"^NCT\d{8}$",            "ClinicalTrials.gov", "mcp c-trials.get_trial_details"),
    (r"^CHEMBL\d+$",           "ChEMBL",             "mcp chembl.compound_search"),
    (r"^ENSG\d{11}$",          "Open Targets",       "mcp ot.query (target)"),
    (r"^EFO_\d+$",             "Open Targets",       "mcp ot.query (disease)"),
    (r"^(MONDO|ORPHA)[:_]\d+$","Open Targets",       "mcp ot.query (disease)"),
    (r"^10\.\d{4,9}/\S+$",     "PubMed/CrossRef",    "mcp pubmed.lookup_by_id (DOI)"),
    (r"^PMID:?\s?\d+$",        "PubMed",             "mcp pubmed.get_article_metadata"),
    (r"^\d{6,9}$",             "PubMed",             "mcp pubmed.get_article_metadata (PMID)"),
]

def detect(raw):
    s = raw.strip()
    for pat, source, route in PATTERNS:
        if re.match(pat, s, re.I):
            return {"id": s.upper() if not s.startswith("10.") else s,
                    "source": source, "route": route}
    return {"id": s, "source": None, "route": None, "error": "unrecognized identifier"}

def resolve(raw, catalog=None):
    d = detect(raw)
    if not d.get("source"):
        return d
    # 1) already in the catalog?
    if catalog is None:
        catalog = json.load(open(os.path.join(HERE, "dmd_datasets.json")))["records"]
    key = d["id"].replace("PMID:", "PMID").replace("PMID ", "PMID")
    for r in catalog:
        if r["id"].upper() == key.upper() or r["id"].upper() == ("PMID"+key).upper():
            rr = dict(r); rr["fair"] = ff.score(r); rr["_resolution"] = "catalog hit"; rr.update(d)
            return rr
    # 2) not cached -> would fetch live via the routed source
    d["_resolution"] = "not in catalog; fetch live via " + d["route"]
    return d

if __name__ == "__main__":
    tests = ["CHEMBL256997", "NCT00264888", "PMID32717791", "GSE1004", "SRR123456",
             "10.3390/genes11080837", "ENSG00000198947", "EFO_0000512", "banana42"]
    for t in tests:
        r = resolve(t)
        hit = r.get("_resolution", r.get("error", ""))
        extra = f' -> "{r["title"]}" FAIR {r["fair"]["overall"]}%' if "fair" in r else ""
        print(f'{t:<26} route: {r.get("source") or "—":<20} {hit}{extra}')
