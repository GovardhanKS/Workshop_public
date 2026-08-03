"""Pull DMD drug label / adverse-event data from openFDA (free, no auth).

This is the one MCP server the team needs to build (see the workflow doc,
section 4) -- there was no existing connector for it. This script is the
plain-REST version; wrap it as an MCP tool server once the demo needs the
Regulatory Agent to call it live rather than from a pre-fetched JSON file.
"""
import json
import pathlib
import requests

OUT_PATH = pathlib.Path(__file__).parent.parent / "data" / "raw" / "regulatory_dmd.json"
LABEL_URL = "https://api.fda.gov/drug/label.json"
EVENT_URL = "https://api.fda.gov/drug/event.json"

DMD_DRUGS = [
    "eteplirsen", "golodirsen", "viltolarsen", "casimersen",
    "delandistrogene moxeparvovec", "ataluren",
]


def fetch_label(drug_name: str) -> dict | None:
    resp = requests.get(LABEL_URL, params={
        "search": f'openfda.generic_name:"{drug_name}"', "limit": 1,
    }, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_adverse_events(drug_name: str, limit: int = 5) -> dict | None:
    resp = requests.get(EVENT_URL, params={
        "search": f'patient.drug.medicinalproduct:"{drug_name}"', "limit": limit,
    }, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    records = []
    for drug in DMD_DRUGS:
        label = fetch_label(drug)
        events = fetch_adverse_events(drug)
        records.append({"drug": drug, "label": label, "adverse_events": events})
    OUT_PATH.write_text(json.dumps({
        "source": "openFDA",
        "drugs": records,
    }, indent=2))
    print(f"Wrote regulatory data for {len(records)} drugs to {OUT_PATH}")
