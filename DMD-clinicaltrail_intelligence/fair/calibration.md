# FAIR scoring calibration — heuristic vs authoritative F-UJI

Provisional heuristic (this catalog) benchmarked against the FAIRsFAIR / F-UJI service.

| Record | Source | Type | Heuristic | F-UJI | Δ | F-UJI applies? | Note |
|---|---|---|--:|--:|--:|:--:|---|
| CHEMBL256997 | ChEMBL | compound | 100 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| CHEMBL2108278 | ChEMBL | compound | 100 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| CHEMBL1213492 | ChEMBL | compound | 100 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| NCT06817382 | ClinicalTrials.gov | trial | 94 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| NCT00264888 | ClinicalTrials.gov | trial | 94 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| NCT02710591 | ClinicalTrials.gov | trial | 94 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| NCT06564974 | ClinicalTrials.gov | trial | 94 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| NCT04740554 | ClinicalTrials.gov | trial | 94 | — | — | N/A | not a F-UJI dataset object (compound/trial) |
| PMID32717791 | PubMed | literature | 88 | — | — | yes | resolvable dataset object |
| PMID35165856 | PubMed | literature | 79 | — | — | yes | resolvable dataset object |
| PMID37673849 | PubMed | literature | 79 | — | — | yes | resolvable dataset object |
| PMID38291016 | PubMed | literature | 79 | — | — | yes | resolvable dataset object |
| PMID32985912 | PubMed | literature | 79 | — | — | yes | resolvable dataset object |
| GSE1004 | GEO | omics | 73 | — | — | pending verify | seed accession not yet resolvable |
| GSE-SEED-2 | GEO | omics | 42 | — | — | pending verify | seed accession not yet resolvable |

## How to read this
- **Heuristic**: computed in-catalog from record metadata (16 FAIRsFAIR metric IDs). Labeled *provisional*.
- **F-UJI**: authoritative score from the live service (run `python calibrate.py --fuji` with creds).
- **Δ = heuristic − F-UJI**: our calibration error. Target: |Δ| ≤ 10 on applicable records.

## What to expect (before you run --fuji)
F-UJI requires *machine-actionable* evidence (schema.org / DataCite metadata, PID signposting,
content negotiation). It therefore usually scores **lower** than an optimistic heuristic — so
positive Δ on GEO/DOI records is expected, and closing it means either the source genuinely lacks
machine-readable metadata (true finding) or our heuristic is too generous (tighten the rule).

F-UJI can authoritatively score **5 of 15** catalog records today
(dataset objects with resolvable PIDs: GEO accessions and DOIs). ChEMBL compounds and trial
registrations are shown as catalogue-level heuristic only — they are not FAIR *data objects* in
F-UJI's sense, which is stated openly in the catalog UI.

## Calibration loop
1. Run `--fuji` on the applicable records.  2. Fill the F-UJI column, inspect Δ.
3. Where Δ is large, read the F-UJI metric log to see which metric disagrees.
4. Adjust that heuristic rule (or accept the source is genuinely weaker).  5. Re-run until |Δ| ≤ 10.

_Metric set: FAIRsFAIR Data Object Assessment Metrics. Tool: F-UJI (Devaraju & Huber 2023,
doi:10.5281/zenodo.6361400; metrics doi:10.5281/zenodo.6461229)._