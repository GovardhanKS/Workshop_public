"""
Search accuracy harness: recall@k and MRR on a hand-labeled gold set.
Compares semantic (TF-IDF cosine) vs keyword retrieval on the catalog.
Emits search_eval.md. Numbers are real (computed here), not asserted.
"""
import json, os, math, re
HERE = os.path.dirname(os.path.abspath(__file__))
recs = json.load(open(os.path.join(HERE, "dmd_datasets.json")))["records"]
ids = [r["id"] for r in recs]

tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())
docs = [tok(" ".join([r["title"], r["description"], " ".join(r.get("entities",[])),
                      " ".join(r.get("ontologies",[]))])) for r in recs]
df = {}
for d in docs:
    for t in set(d): df[t] = df.get(t,0)+1
N = len(docs)
idf = lambda t: math.log((N+1)/(df.get(t,0)+1))+1
def vec(ts):
    tf={}
    for t in ts: tf[t]=tf.get(t,0)+1
    return {t: tf[t]*idf(t) for t in tf}
dvecs = [vec(d) for d in docs]
def cos(a,b):
    d=sum(a[t]*b.get(t,0) for t in a)
    na=math.sqrt(sum(v*v for v in a.values())); nb=math.sqrt(sum(v*v for v in b.values()))
    return d/(na*nb) if na and nb else 0

def rank(q, mode):
    qt=tok(q)
    if mode=="keyword":
        scored=[(ids[i], sum(1 for t in qt if t in set(docs[i]))/max(len(qt),1)) for i in range(N)]
    else:
        qv=vec(qt)
        scored=[(ids[i], cos(qv,dvecs[i])) for i in range(N)]
    return [x for x,_ in sorted(scored, key=lambda z:-z[1]) if _>0]

# Gold set: query -> set of relevant record ids (hand-labeled against the 15 records)
GOLD = {
 "exon skipping":                 {"CHEMBL2108278","PMID37673849","PMID38291016"},
 "nonsense mutation readthrough": {"CHEMBL256997","NCT00264888"},
 "gene therapy":                  {"NCT06817382","PMID32717791","PMID37673849","PMID35165856"},
 "CRISPR gene editing":           {"PMID35165856","PMID37673849"},
 "cardiac cardiomyopathy":        {"PMID32985912","NCT04740554"},
 "corticosteroid":                {"NCT06564974","NCT04740554"},
 "HDAC inhibitor":                {"CHEMBL1213492"},
 "transcriptomics muscle":        {"GSE1004","GSE-SEED-2"},
 "antisense oligonucleotide":     {"CHEMBL2108278","PMID38291016"},
 "vamorolone":                    {"NCT06564974"},
 "dystrophin restoration":        {"PMID32717791","CHEMBL256997","CHEMBL2108278"},
 "rimeporide NHE-1":              {"NCT02710591"},
}

def metrics(mode, ks=(1,3,5)):
    rec={k:[] for k in ks}; rr=[]
    for q,rel in GOLD.items():
        ranked=rank(q,mode)
        for k in ks:
            hits=len(set(ranked[:k]) & rel)
            rec[k].append(hits/len(rel))
        pos=[i+1 for i,x in enumerate(ranked) if x in rel]
        rr.append(1/pos[0] if pos else 0)
    return {("recall@%d"%k): round(sum(rec[k])/len(rec[k]),3) for k in ks} | {"MRR": round(sum(rr)/len(rr),3)}

sem=metrics("semantic"); kw=metrics("keyword")
print("Gold set:", len(GOLD), "queries over", N, "records")
print(f"{'metric':<12}{'semantic':>10}{'keyword':>10}")
for m in ["recall@1","recall@3","recall@5","MRR"]:
    print(f"{m:<12}{sem[m]:>10}{kw[m]:>10}")

md=["# Search accuracy — recall@k & MRR\n",
f"Hand-labeled gold set of **{len(GOLD)} queries** over **{N} records**. Metrics computed in `evaluate_search.py` (not asserted).\n",
"| Metric | Semantic (TF-IDF) | Keyword |","|---|--:|--:|"]
for m in ["recall@1","recall@3","recall@5","MRR"]:
    md.append(f"| {m} | {sem[m]} | {kw[m]} |")
md+= ["","## Notes",
"- **Recall@k**: fraction of relevant records retrieved in the top k, averaged over queries.",
"- **MRR**: mean reciprocal rank of the first relevant hit.",
"- Semantic uses the same TF-IDF cosine as the catalog UI; production would swap in a",
"  biomedical embedding (e.g. PubMedBERT) + hybrid exact-ID match to lift recall further.",
"- Gold set is small (demo scale); widen it before quoting these as production numbers."]
open(os.path.join(HERE,"search_eval.md"),"w").write("\n".join(md))
open(os.path.join(HERE,"search_eval.json"),"w").write(json.dumps({"semantic":sem,"keyword":kw,"queries":len(GOLD),"records":N}))
print("\nWrote search_eval.md / .json")
