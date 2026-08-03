"""Pull DMD/dystrophin target data from ChEMBL and Open Targets (both free,
no auth). Run on a machine with internet access; data/raw/biomarker_dmd.json
currently holds a sample pulled via MCP chembl/ot connectors.
"""
import json
import pathlib
import requests

OUT_PATH = pathlib.Path(__file__).parent.parent / "data" / "raw" / "biomarker_dmd.json"
CHEMBL_TARGET = "https://www.ebi.ac.uk/chembl/api/data/target/search.json"
OPEN_TARGETS_GRAPHQL = "https://api.platform.opentargets.org/api/v4/graphql"


def fetch_chembl_target(gene_symbol: str = "DMD") -> dict:
    resp = requests.get(CHEMBL_TARGET, params={"q": gene_symbol}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_open_targets_associations(ensembl_gene_id: str = "ENSG00000198947") -> dict:
    query = """
    query target($ensemblId: String!) {
      target(ensemblId: $ensemblId) {
        approvedSymbol
        biotype
        associatedDiseases(page: {index: 0, size: 500}) {
          count
          rows { score disease { id name } }
        }
      }
    }
    """
    resp = requests.post(OPEN_TARGETS_GRAPHQL, json={
        "query": query, "variables": {"ensemblId": ensembl_gene_id},
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


# Below this score, associations degrade fast into generic/tangential
# neuromuscular phenotype terms rather than genuinely DMD-relevant diseases
# (checked the live score distribution: 11 rows >=0.5, 52 rows >=0.2, then a
# long noisy tail down to ~0.06 by rank 500) -- keep signal, drop the tail.
ASSOCIATION_SCORE_CUTOFF = 0.2


if __name__ == "__main__":
    chembl = fetch_chembl_target()
    ot = fetch_open_targets_associations()
    rows = ot.get("data", {}).get("target", {}).get("associatedDiseases", {}).get("rows", [])
    associated_diseases = [
        {"id": r["disease"]["id"], "name": r["disease"]["name"], "score": r["score"]}
        for r in rows if r["score"] >= ASSOCIATION_SCORE_CUTOFF
    ]
    OUT_PATH.write_text(json.dumps({
        "source": ["ChEMBL", "Open Targets Platform"],
        "chembl_target": chembl,
        "open_targets_associations": ot,
        "associated_diseases": associated_diseases,
    }, indent=2))
    print(f"Wrote biomarker data ({len(associated_diseases)} disease associations >= "
          f"{ASSOCIATION_SCORE_CUTOFF}) to {OUT_PATH}")
