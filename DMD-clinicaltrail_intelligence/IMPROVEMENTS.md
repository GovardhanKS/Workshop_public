# Corpus expansion notes -- 2026-08-03

Moving the RAG corpus from demo-scale to production-realistic scale. Trials
were already solid (353, live from ClinicalTrials.gov); literature,
biomarker, and regulatory were thin or structurally capped. This pass fixed
the root causes and pulled real data from every working live source.

## Numbers

| Source | Before | After | Change |
|---|---|---|---|
| Trial | 353 | 353 | unchanged -- already live/healthy |
| Literature | 10 | 7,620 | full live PubMed result set for the existing query, not a sample |
| Biomarker | 1 | 61 | structural bug fix + live Open Targets data + curated endpoints |
| Regulatory | 10 | 19 | 7 new drugs verified live via openFDA + 1 previously-unloaded discontinued program surfaced |

Counts are from `rag.corpus.counts_by_source()` -- the same numbers the UI's
source tiles and `/stats` show.

## What actually changed, per source

**Literature** -- `ingestion/fetch_literature.py` had only ever been run to
pull a 10-article sample; the query itself matches 7,632 PubMed articles.
Raised `search_pmids()`'s cap to 10,000 and re-ran it live. Along the way,
the original 10-ID `efetch` batch size made a full run ~760 requests
(~5+ min) and the first live attempt died mid-run to a dropped connection
on one batch. Fixed by raising the batch size to 100-200 IDs/request (with
retry-with-backoff) and writing to disk after every batch instead of only
at the end -- a dropped connection now costs one retry, not the whole run.

**Biomarker** -- `rag/corpus.py:load_biomarker()` had a structural bug: it
read a single `target` field and ignored everything else in the file, so it
could never produce more than 1 document no matter how much data existed.
Rewrote it to emit one document per real signal: the ChEMBL dystrophin
target (1), Open Targets disease associations scored >= 0.2 (52 -- a
data-driven cutoff chosen by checking the live score distribution rather
than an arbitrary top-N), and 8 new hand-curated standard DMD clinical
endpoints (NSAA, 6MWT, FVC, muscle MRI fat fraction, PUL, timed function
tests, dystrophin expression, serum CK) in a new
`data/raw/biomarker_endpoints_dmd.json`. ChEMBL's compound/bioactivity API
is currently down (EBI-side 500s, confirmed live) -- not wired in, flagged
as a follow-up.

**Regulatory** -- `load_regulatory()` never read the `discontinued_programs`
list already sitting in the seed file; now it does. Added 7 new
`approval_events` for DMD drugs missing from the seed data (golodirsen,
viltolarsen, casimersen, givinostat, deflazacort, vamorolone, ataluren),
verifying each US-approved one live against openFDA's actual label text
(quoted in `openfda_indications_snippet`) and flipping its `status` to
`verified_via_openfda`. Ataluren is EU-only -- confirmed live that openFDA
has no record of it, kept flagged `needs_verification` with a note
explaining why instead of treating that as a data gap to fix. Added 1 new
discontinued program (Wave Life Sciences' suvodirsen) alongside the
existing one.

## Explicitly not done

- `fair/` catalog and `knowledge_graph/` -- a separate, disjoint demo
  dataset, out of scope for this pass.
- ChEMBL molecule/compound data -- API is down right now.
- `regulatory_guidance_dmd.json` expansion -- hand-curated with no live
  source to verify new entries against; risk of fabricating citations
  outweighed the benefit of a bigger number here.

See [README.md](README.md#whats-real-vs-seed-data) for the living version of
these per-source notes.
