# Search accuracy — recall@k & MRR

Hand-labeled gold set of **12 queries** over **15 records**. Metrics computed in `evaluate_search.py` (not asserted).

| Metric | Semantic (TF-IDF) | Keyword |
|---|--:|--:|
| recall@1 | 0.576 | 0.576 |
| recall@3 | 0.951 | 0.979 |
| recall@5 | 0.972 | 1.0 |
| MRR | 1.0 | 1.0 |

## Notes
- **Recall@k**: fraction of relevant records retrieved in the top k, averaged over queries.
- **MRR**: mean reciprocal rank of the first relevant hit.
- Semantic uses the same TF-IDF cosine as the catalog UI; production would swap in a
  biomedical embedding (e.g. PubMedBERT) + hybrid exact-ID match to lift recall further.
- Gold set is small (demo scale); widen it before quoting these as production numbers.