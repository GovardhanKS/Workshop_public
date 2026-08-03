"""
Calibration harness: heuristic FAIR score vs authoritative F-UJI.
Emits calibration.md and calibration.csv.

Usage:
    python calibrate.py            # heuristic only; F-UJI column left pending
    python calibrate.py --fuji     # also call live F-UJI (needs internet + creds)

The point: show a scientific audience that our provisional heuristic is validated
against the authoritative FAIRsFAIR/F-UJI tool, quantify the gap, and tighten.
"""
import json, os, sys, csv
try:
    from . import fair_fairsfair as ff  # imported as fair.calibrate
except ImportError:
    import fair_fairsfair as ff  # run directly as a script

HERE = os.path.dirname(os.path.abspath(__file__))
recs = json.load(open(os.path.join(HERE, "dmd_datasets.json")))["records"]
for r in recs:
    r["fair"] = ff.score(r)

use_fuji = "--fuji" in sys.argv
rows = []
for r in recs:
    pid = ff.resolvable_pid(r)
    heur = r["fair"]["overall"]
    if pid is None:
        applic = "N/A" if r.get("verified") else "pending verify"
        fuji = None
        note = ("not a F-UJI dataset object (compound/trial)"
                if r["source"] in ("ChEMBL", "ClinicalTrials.gov")
                else "seed accession not yet resolvable")
    else:
        applic = "yes"
        note = "resolvable dataset object"
        fuji = None
        if use_fuji:
            try:
                fuji = ff.map_fuji(ff.fuji_live(pid))["overall"]
            except Exception as e:
                note = f"F-UJI call failed: {e}"
    delta = (heur - fuji) if isinstance(fuji, int) else None
    rows.append([r["id"], r["source"], r["type"], heur,
                 fuji if fuji is not None else "—",
                 delta if delta is not None else "—", applic, note])

# CSV
with open(os.path.join(HERE, "calibration.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["record","source","type","heuristic_pct","fuji_pct","delta","fuji_applicable","note"])
    w.writerows(rows)

# Markdown
md = ["# FAIR scoring calibration — heuristic vs authoritative F-UJI\n",
"Provisional heuristic (this catalog) benchmarked against the FAIRsFAIR / F-UJI service.\n",
"| Record | Source | Type | Heuristic | F-UJI | Δ | F-UJI applies? | Note |",
"|---|---|---|--:|--:|--:|:--:|---|"]
for row in rows:
    md.append("| " + " | ".join(str(x) for x in row) + " |")
applicable = [r for r in rows if r[6] == "yes"]
md += ["",
"## How to read this",
"- **Heuristic**: computed in-catalog from record metadata (16 FAIRsFAIR metric IDs). Labeled *provisional*.",
"- **F-UJI**: authoritative score from the live service (run `python calibrate.py --fuji` with creds).",
"- **Δ = heuristic − F-UJI**: our calibration error. Target: |Δ| ≤ 10 on applicable records.",
"",
"## What to expect (before you run --fuji)",
"F-UJI requires *machine-actionable* evidence (schema.org / DataCite metadata, PID signposting,",
"content negotiation). It therefore usually scores **lower** than an optimistic heuristic — so",
"positive Δ on GEO/DOI records is expected, and closing it means either the source genuinely lacks",
"machine-readable metadata (true finding) or our heuristic is too generous (tighten the rule).",
"",
f"F-UJI can authoritatively score **{len(applicable)} of {len(rows)}** catalog records today",
"(dataset objects with resolvable PIDs: GEO accessions and DOIs). ChEMBL compounds and trial",
"registrations are shown as catalogue-level heuristic only — they are not FAIR *data objects* in",
"F-UJI's sense, which is stated openly in the catalog UI.",
"",
"## Calibration loop",
"1. Run `--fuji` on the applicable records.  2. Fill the F-UJI column, inspect Δ.",
"3. Where Δ is large, read the F-UJI metric log to see which metric disagrees.",
"4. Adjust that heuristic rule (or accept the source is genuinely weaker).  5. Re-run until |Δ| ≤ 10.",
"",
"_Metric set: FAIRsFAIR Data Object Assessment Metrics. Tool: F-UJI (Devaraju & Huber 2023,",
"doi:10.5281/zenodo.6361400; metrics doi:10.5281/zenodo.6461229)._"]
open(os.path.join(HERE, "calibration.md"), "w").write("\n".join(md))

# console
print(f"{'RECORD':<15}{'SRC':<20}{'HEUR':>5}{'F-UJI':>7}{'Δ':>5}  applies")
print("-"*60)
for row in rows:
    print(f"{row[0]:<15}{row[1]:<20}{row[3]:>5}{str(row[4]):>7}{str(row[5]):>5}  {row[6]}")
print("\nWrote calibration.md and calibration.csv")
