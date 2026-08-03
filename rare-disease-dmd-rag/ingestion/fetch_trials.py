"""Pull DMD trials from ClinicalTrials.gov API v2 (free, no auth).

Run this on a machine with normal internet access -- the demo sandbox used to
scaffold this repo could not reach clinicaltrials.gov directly, so
data/raw/trials_dmd.json currently holds a manually-saved sample pulled via
an MCP connector instead. Re-run this script before the workshop to refresh
with the latest trial statuses.
"""
import json
import pathlib
import requests

OUT_PATH = pathlib.Path(__file__).parent.parent / "data" / "raw" / "trials_dmd.json"
API_URL = "https://clinicaltrials.gov/api/v2/studies"


def _summarize_results(study: dict, max_len: int = 400) -> str | None:
    """Best-effort plain-text summary of the primary posted outcome measure's
    group-level values -- ClinicalTrials.gov's results schema is deeply
    nested and varies a lot between trials, so this deliberately only
    surfaces the first measure/class rather than trying to model every shape."""
    results = study.get("resultsSection", {})
    measures = results.get("outcomeMeasuresModule", {}).get("outcomeMeasures", [])
    primary = next((m for m in measures if m.get("type") == "PRIMARY"), measures[0] if measures else None)
    if not primary:
        return None
    groups = {g["id"]: g.get("title", g["id"]) for g in primary.get("groups", [])}
    classes = primary.get("classes", [])
    if not classes:
        return None
    measurements = classes[0].get("categories", [{}])[0].get("measurements", [])
    unit = primary.get("unitOfMeasure", "")
    parts = [f"{groups.get(m.get('groupId'), m.get('groupId'))}: {m.get('value')} {unit}".strip()
             for m in measurements if m.get("value") is not None]
    if not parts:
        return None
    summary = f"{primary.get('title', 'Primary outcome')} -- " + "; ".join(parts)
    if len(summary) > max_len:
        summary = summary[:max_len].rsplit(" ", 1)[0] + "..."
    return summary


def fetch_dmd_trials(page_size: int = 100, max_pages: int = 5) -> list[dict]:
    items, token = [], None
    for _ in range(max_pages):
        params = {
            "query.cond": "Duchenne muscular dystrophy",
            # Interventional only -- excludes observational/natural-history
            # studies, which have no phase/arms/endpoints to compare anyway.
            "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
            "pageSize": page_size,
        }
        if token:
            params["pageToken"] = token
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for study in data.get("studies", []):
            protocol = study.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            design = protocol.get("designModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
            arms = protocol.get("armsInterventionsModule", {}).get("interventions", [])
            conditions = protocol.get("conditionsModule", {}).get("conditions", [])
            eligibility = protocol.get("eligibilityModule", {})
            outcomes = protocol.get("outcomesModule", {})
            has_results = study.get("hasResults", False)
            items.append({
                "nct_id": ident.get("nctId"),
                "title": ident.get("briefTitle"),
                "status": status.get("overallStatus"),
                "phase": design.get("phases"),
                "conditions": conditions,
                "sponsor": sponsor.get("name"),
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "start_date": status.get("startDateStruct", {}).get("date"),
                "interventions": [a.get("name") for a in arms],
                "eligibility_criteria": eligibility.get("eligibilityCriteria"),
                "min_age": eligibility.get("minimumAge"),
                "max_age": eligibility.get("maximumAge"),
                "sex": eligibility.get("sex"),
                "primary_outcomes": [
                    {"measure": o.get("measure"), "time_frame": o.get("timeFrame")}
                    for o in outcomes.get("primaryOutcomes", [])
                ],
                "has_results": has_results,
                "results_summary": _summarize_results(study) if has_results else None,
            })
        token = data.get("nextPageToken")
        if not token:
            break
    return items


if __name__ == "__main__":
    trials = fetch_dmd_trials()
    OUT_PATH.write_text(json.dumps({
        "source": "ClinicalTrials.gov API v2",
        "query": "condition=Duchenne muscular dystrophy",
        "items": trials,
    }, indent=2))
    print(f"Wrote {len(trials)} trials to {OUT_PATH}")
