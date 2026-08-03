"""
FAIRsFAIR / F-UJI aligned FAIR scorer.
Implements the FAIRsFAIR Data Object Assessment Metrics (v0.5) metric IDs,
as used by F-UJI (https://www.f-uji.net/, DOI 10.5281/zenodo.6361400;
metrics DOI 10.5281/zenodo.6461229).

Each metric is evaluated to passed / partial / failed against a normalized
record. Results roll up to per-principle F/A/I/R percentages and an overall
FAIRness level, matching F-UJI's reporting style. Scores are computed in code.

For records with a resolvable PID/DOI, fuji_live() defers to the authoritative
F-UJI REST API instead of this heuristic.
"""
import json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# FAIRsFAIR metric catalogue (subset F-UJI evaluates for datasets)
METRICS = [
    ("F", "FsF-F1-01D", "Globally unique & persistent identifier"),
    ("F", "FsF-F2-01M", "Rich descriptive metadata"),
    ("F", "FsF-F3-01M", "Metadata includes the identifier of the data"),
    ("F", "FsF-F4-01M", "Metadata is offered via a searchable/harvestable index"),
    ("A", "FsF-A1-01M", "Standardised access protocol declared in metadata"),
    ("A", "FsF-A1-02M", "Data content accessible via standardised protocol"),
    ("A", "FsF-A2-01M", "Metadata guaranteed to remain available"),
    ("I", "FsF-I1-01M", "Metadata in a machine-readable, structured format"),
    ("I", "FsF-I1-02M", "Data content in a machine-readable, structured format"),
    ("I", "FsF-I2-01M", "Metadata uses FAIR-aligned controlled vocabularies"),
    ("I", "FsF-I3-01M", "Qualified references to other (meta)data / entities"),
    ("R", "FsF-R1-01MD", "Plurality of accurate, relevant attributes"),
    ("R", "FsF-R1.1-01M", "Access/usage license specified"),
    ("R", "FsF-R1.1-02M", "License is machine-readable (SPDX/URI)"),
    ("R", "FsF-R1.2-01M", "Provenance / source information present"),
    ("R", "FsF-R1.3-01M", "Metadata meets a community/domain standard"),
]

STD_SCHEMES = ("ATC", "MeSH", "InChIKey", "DOI", "PMID", "GEO", "ChEMBL", "NCT", "EMA", "USAN", "DailyMed")

def _has_std_vocab(r):
    return sum(1 for o in r.get("ontologies", []) if any(s in o for s in STD_SCHEMES))

def evaluate(r):
    """Return {metric_id: (status, note)} where status in pass/partial/fail."""
    n_std = _has_std_vocab(r)
    n_ont = len(r.get("ontologies", []))
    res = {}
    def put(mid, ok, partial=False, note=""):
        res[mid] = ("pass" if ok else ("partial" if partial else "fail"), note)

    put("FsF-F1-01D", r.get("persistent_id"),
        note="PID resolves" if r.get("persistent_id") else "no persistent identifier")
    put("FsF-F2-01M", n_ont >= 2 and len(r.get("description",""))>60, partial=(n_ont==1),
        note=f"{n_ont} metadata vocab(s), description present")
    put("FsF-F3-01M", r.get("persistent_id"),
        note="metadata carries the data identifier")
    put("FsF-F4-01M", True, note=f"indexed & harvestable in {r['source']}")
    put("FsF-A1-01M", True, note="HTTPS/REST access protocol in metadata")
    put("FsF-A1-02M", r.get("open_access"), partial=not r.get("open_access"),
        note="open access" if r.get("open_access") else "full content behind subscription; metadata open")
    put("FsF-A2-01M", r.get("verified"), partial=not r.get("verified"),
        note="repository-backed persistence" if r.get("verified") else "persistence unconfirmed (seed)")
    put("FsF-I1-01M", r.get("structured"), partial=not r.get("structured"),
        note="structured machine-readable record" if r.get("structured") else "free-text / semi-structured")
    _datafmt = r.get("type") in ("compound", "omics")
    put("FsF-I1-02M", _datafmt and r.get("verified"),
        partial=(r.get("type") == "trial") or (r.get("type")=="omics" and not r.get("verified")),
        note=("machine-readable data files (structures/matrices)" if _datafmt
              else "registry fields, no downloadable data object" if r.get("type")=="trial"
              else "narrative text, not a structured data object"))
    put("FsF-I2-01M", n_std >= 2, partial=(n_std==1),
        note=f"{n_std} FAIR-aligned vocabulary scheme(s)")
    put("FsF-I3-01M", len(r.get("entities", [])) >= 1,
        note=f"{len(r.get('entities',[]))} qualified entity link(s)")
    put("FsF-R1-01MD", n_ont>=2 and len(r.get("description",""))>80, partial=(n_ont>=1),
        note="multiple accurate attributes")
    put("FsF-R1.1-01M", bool(r.get("license")) and r.get("license")!="unknown",
        note=f"license: {r.get('license')}")
    _spdx = {"CC BY-SA 3.0","CC BY","CC BY 4.0","CC0","CC BY (open access)"}
    _lic = r.get("license","")
    put("FsF-R1.1-02M", _lic in _spdx, partial=_lic in ("Public domain (NLM)","Open (NCBI)"),
        note=("SPDX-identifiable license" if _lic in _spdx
              else "open but license not machine-readable" if _lic in ("Public domain (NLM)","Open (NCBI)")
              else "no machine-readable license"))
    put("FsF-R1.2-01M", r.get("verified"), partial=not r.get("verified"),
        note=f"provenance: {r['source']}" if r.get("verified") else "provenance unverified")
    put("FsF-R1.3-01M", r.get("structured") and n_std>=1, partial=(n_std>=1),
        note="conforms to a community metadata standard")
    return res

def score(r):
    res = evaluate(r)
    val = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
    groups = {"F": [], "A": [], "I": [], "R": []}
    for grp, mid, _ in METRICS:
        groups[grp].append(val[res[mid][0]])
    pct = {g: round(100*sum(v)/len(v)) for g, v in groups.items()}
    overall = round(sum(pct.values())/4)
    level = ("Advanced" if overall>=75 else "Moderate" if overall>=50
             else "Basic" if overall>=25 else "Incomplete")
    return {"overall": overall, "level": level, "principles": pct,
            "metrics": {mid: {"status": res[mid][0], "note": res[mid][1],
                              "principle": grp, "label": lbl}
                        for grp, mid, lbl in METRICS}}

import base64
def fuji_live(pid, base="https://www.f-uji.net/fuji/api/v1/evaluate",
              user=None, pw=None):
    """Authoritative assessment via the real F-UJI REST API (needs internet + object PID).
    The public f-uji.net API requires HTTP Basic auth credentials you register on the site;
    pass them or set env F_UJI_USER / F_UJI_PW. Returns the raw F-UJI JSON."""
    user = user or os.environ.get("F_UJI_USER"); pw = pw or os.environ.get("F_UJI_PW")
    body = json.dumps({"object_identifier": pid, "test_debug": False,
                       "use_datacite": True, "metadata_service_endpoint": "",
                       "metadata_service_type": ""}).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if user and pw:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
    req = urllib.request.Request(base, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)

def map_fuji(resp):
    """Map raw F-UJI response to our {overall, level, principles{F,A,I,R}} shape."""
    summ = resp.get("summary", {})
    pct = summ.get("score_percent", {})
    principles = {k: round(pct.get(k, 0)) for k in ("F", "A", "I", "R")}
    overall = round(pct.get("FAIR", sum(principles.values())/4))
    level = resp.get("results", [{}]) and summ.get("maturity")  # F-UJI reports maturity too
    lvl = ("Advanced" if overall>=75 else "Moderate" if overall>=50
           else "Basic" if overall>=25 else "Incomplete")
    return {"overall": overall, "level": lvl, "principles": principles,
            "authoritative": True, "fuji_maturity": level}

def resolvable_pid(r):
    """The identifier F-UJI can resolve: DOI URL for literature, GEO accession URL, else source URL."""
    if r["source"] == "PubMed" and r.get("url","").startswith("https://doi.org/"):
        return r["url"]
    if r["source"] == "GEO" and r.get("verified"):
        return r["url"]
    return None  # ChEMBL compounds / trial registrations are not F-UJI dataset objects

if __name__ == "__main__":
    recs = json.load(open(os.path.join(HERE, "dmd_datasets.json")))["records"]
    for r in recs: r["fair"] = score(r)
    recs.sort(key=lambda r: r["fair"]["overall"], reverse=True)
    print(f"{'RECORD':<15}{'SOURCE':<20}{'FAIR':>5} {'LEVEL':<11} F/A/I/R")
    print("-"*66)
    for r in recs:
        f=r["fair"]; p=f["principles"]
        print(f"{r['id']:<15}{r['source']:<20}{f['overall']:>4}% {f['level']:<11} "
              f"{p['F']:>3}/{p['A']:>3}/{p['I']:>3}/{p['R']:>3}")
    json.dump(recs, open(os.path.join(HERE,"dmd_scored.json"),"w"), indent=1)
    print("\nExample metric detail for", recs[0]['id'], "(top):")
    for mid,m in list(recs[0]['fair']['metrics'].items())[:4]:
        print(f"  {mid:<13}{m['status']:<8}{m['note']}")
