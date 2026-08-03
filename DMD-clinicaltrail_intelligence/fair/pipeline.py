"""
DMD Data Discovery Pipeline
===========================
Duchenne Muscular Dystrophy demo: ingest -> normalize -> FAIR score -> index.

Sources: GEO (NCBI E-utilities), ClinicalTrials.gov v2, ChEMBL, PubMed.
KG backbone: Open Targets (gene-disease-drug).

Run where outbound HTTPS is allowed:
    python pipeline.py --live      # fetch fresh records from all 4 APIs
    python pipeline.py             # score the bundled dmd_datasets.json (offline)

The FAIR score is computed here, in code. The LLM/RAG layer only NARRATES it.
"""
import json, re, sys, urllib.request, urllib.parse, os

DISEASE = "Duchenne muscular dystrophy"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ingest (live)
def _get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode()

def fetch_geo(n=10):
    """NCBI E-utilities: GEO DataSets. No MCP exists for GEO, so we hit eutils directly."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    ids = json.loads(_get(base + "esearch.fcgi?db=gds&term=" +
          urllib.parse.quote(DISEASE) + f"&retmax={n}&retmode=json"))["esearchresult"]["idlist"]
    out = []
    if ids:
        summ = json.loads(_get(base + "esummary.fcgi?db=gds&id=" + ",".join(ids) + "&retmode=json"))["result"]
        for i in ids:
            s = summ.get(i, {})
            out.append(_norm(id="GSE"+str(s.get("accession","")).replace("GSE",""), source="GEO", type="omics",
                title=s.get("title",""), description=s.get("summary",""),
                url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={s.get('accession','')}",
                ontologies=["GEO accession"], license="Open (NCBI)", persistent_id=True,
                open_access=True, structured=False, verified=True, entities=[], year=None))
    return out

def fetch_clinicaltrials(n=10):
    url = ("https://clinicaltrials.gov/api/v2/studies?query.cond=" +
           urllib.parse.quote(DISEASE) + f"&pageSize={n}")
    data = json.loads(_get(url))
    out = []
    for st in data.get("studies", []):
        p = st["protocolSection"]; idm = p["identificationModule"]
        out.append(_norm(id=idm["nctId"], source="ClinicalTrials.gov", type="trial",
            title=idm.get("officialTitle") or idm.get("briefTitle",""),
            description=p.get("descriptionModule",{}).get("briefSummary",""),
            url=f"https://clinicaltrials.gov/study/{idm['nctId']}",
            ontologies=["NCT ID","MeSH:Muscular Dystrophy, Duchenne"], license="Public domain (NLM)",
            persistent_id=True, open_access=True, structured=True, verified=True, entities=[], year=None))
    return out

# ChEMBL and PubMed: use the bio-research MCP tools in the agent, or the public REST APIs below.
def fetch_chembl_drug(name):
    url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/search?q={urllib.parse.quote(name)}&format=json"
    m = json.loads(_get(url))["molecules"][0]
    return _norm(id=m["molecule_chembl_id"], source="ChEMBL", type="compound",
        title=m.get("pref_name",name), description=f"ChEMBL molecule, max_phase {m.get('max_phase')}.",
        url=f"https://www.ebi.ac.uk/chembl/compound_report_card/{m['molecule_chembl_id']}/",
        ontologies=["ChEMBL ID","ATC"], license="CC BY-SA 3.0",
        persistent_id=True, open_access=True, structured=True, verified=True, entities=[], year=None)

# ------------------------------------------------------------------- normalize
def _norm(**k):
    k.setdefault("ontologies", []); k.setdefault("entities", [])
    return k

# ----------------------------------------------------------- FAIR score (rubric)
def fair_score(r):
    """Deterministic FAIR sub-scores (0-25 each) with per-criterion evidence."""
    ev = {}
    n_ont = len(r.get("ontologies", []))
    # Findable
    F = 0; fe = []
    if r.get("persistent_id"): F += 8; fe.append("+8 persistent identifier")
    else: fe.append("+0 no persistent ID")
    F += 5; fe.append("+5 indexed in a searchable registry")
    if n_ont >= 2: F += 7; fe.append("+7 rich metadata (>=2 controlled vocabularies)")
    elif n_ont == 1: F += 4; fe.append("+4 minimal metadata")
    else: fe.append("+0 metadata sparse")
    if r.get("verified"): F += 5; fe.append("+5 provenance verified")
    else: fe.append("+0 unverified seed record")
    F = min(F, 25); ev["Findable"] = (F, fe)
    # Accessible
    A = 10; ae = ["+10 retrievable via standard protocol (HTTPS/API)"]
    if r.get("open_access"): A += 8; ae.append("+8 open access")
    else: ae.append("+0 full record behind subscription")
    A += 7; ae.append("+7 metadata openly accessible")
    A = min(A, 25); ev["Accessible"] = (A, ae)
    # Interoperable
    I = min(n_ont * 5, 15); ie = [f"+{min(n_ont*5,15)} uses {n_ont} standard vocab/ID scheme(s)"]
    if r.get("structured"): I += 10; ie.append("+10 machine-readable structured record")
    else: I += 3; ie.append("+3 free-text / semi-structured")
    I = min(I, 25); ev["Interoperable"] = (I, ie)
    # Reusable
    R = 0; re_ = []
    if r.get("license") and r["license"] != "unknown": R += 8; re_.append(f"+8 explicit license ({r['license']})")
    else: re_.append("+0 no clear license")
    R += 7; re_.append(f"+7 clear source provenance ({r['source']})")
    if r.get("structured"): R += 5; re_.append("+5 structured, reusable fields")
    else: re_.append("+0 unstructured")
    if r.get("verified"): R += 5; re_.append("+5 verified record")
    R = min(R, 25); ev["Reusable"] = (R, re_)
    total = F + A + I + R
    return {"total": total, "F": F, "A": A, "I": I, "R": R, "evidence": ev}

# ------------------------------------------------------------------------- main
def load_offline():
    return json.load(open(os.path.join(HERE, "dmd_datasets.json")))["records"]

def run(live=False):
    if live:
        recs = fetch_geo() + fetch_clinicaltrials()
        for d in ["ataluren", "eteplirsen", "givinostat"]:
            try: recs.append(fetch_chembl_drug(d))
            except Exception as e: print("chembl", d, "failed:", e)
    else:
        recs = load_offline()
    for r in recs:
        r["fair"] = fair_score(r)
    return recs

if __name__ == "__main__":
    live = "--live" in sys.argv
    recs = run(live=live)
    recs.sort(key=lambda r: r["fair"]["total"], reverse=True)
    print(f"{'RECORD':<16}{'SOURCE':<20}{'FAIR':>5}  F  A  I  R")
    print("-"*60)
    for r in recs:
        f = r["fair"]
        print(f"{r['id']:<16}{r['source']:<20}{f['total']:>5} {f['F']:>2} {f['A']:>2} {f['I']:>2} {f['R']:>2}")
    json.dump(recs, open(os.path.join(HERE, "dmd_scored.json"), "w"), indent=1)
    print("\nWrote dmd_scored.json")
