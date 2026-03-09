# SKIN1004 Marketing QA V2 Variation Test Report

**Date**: 2026-03-08 11:35
**Type**: V2 Variation (rephrased questions with synonyms, typos, style variations)
**Total**: 13 tables x 300 questions = 3900
**Test Mode**: 3 threads, Semaphore(2), 1s delay

## Overall Summary

| Metric | Value |
|--------|-------|
| Pass Rate | **100.0%** (3900/3900) |
| OK | 3634 |
| WARN | 266 |
| FAIL | 0 |
| Avg Latency | 38.4s |
| P50 | 37.1s |
| P95 | 63.5s |

## Per-Table Results

| Table | Total | OK | WARN | FAIL | Pass% | Avg(s) | P95(s) |
|-------|-------|-----|------|------|-------|--------|--------|
| advertising | 300 | 288 | 12 | 0 | 100.0% | 37.8 | 55.8 |
| amazon_search | 300 | 277 | 23 | 0 | 100.0% | 38.4 | 69.1 |
| influencer | 300 | 284 | 16 | 0 | 100.0% | 37.8 | 61.1 |
| marketing_cost | 300 | 272 | 28 | 0 | 100.0% | 40.3 | 66.2 |
| meta_ads | 300 | 275 | 25 | 0 | 100.0% | 39.4 | 63.3 |
| platform | 300 | 266 | 34 | 0 | 100.0% | 41.5 | 69.6 |
| product | 300 | 281 | 19 | 0 | 100.0% | 39.0 | 64.0 |
| review_amazon | 300 | 271 | 29 | 0 | 100.0% | 41.6 | 66.0 |
| review_qoo10 | 300 | 279 | 21 | 0 | 100.0% | 42.4 | 64.0 |
| review_shopee | 300 | 277 | 23 | 0 | 100.0% | 40.7 | 65.4 |
| review_smartstore | 300 | 278 | 22 | 0 | 100.0% | 40.7 | 64.5 |
| sales_all | 300 | 287 | 13 | 0 | 100.0% | 37.3 | 57.8 |
| shopify | 300 | 299 | 1 | 0 | 100.0% | 22.5 | 44.1 |

## WARN Queries (60-90s)

266 queries in WARN range:
- platform: 34
- review_amazon: 29
- marketing_cost: 28
- meta_ads: 25
- amazon_search: 23
- review_shopee: 23
- review_smartstore: 22
- review_qoo10: 21
- product: 19
- influencer: 16
- sales_all: 13
- advertising: 12
- shopify: 1

## V1 vs V2 Comparison

| Metric | V1 (Original) | V2 (Variation) |
|--------|---------------|----------------|
| Total | 3900 | 3900 |
| Pass Rate | 99.1% | 100.0% |
| OK | 3455 | 3634 |
| WARN | 409 | 266 |
| FAIL | 36 | 0 |
| Avg Latency | 41.4s | 38.4s |

## Conclusion

- **Variation Robustness**: Excellent — rephrased queries handled well
- **Production Ready**: Yes
- **Typo Tolerance**: Yes — queries with typos/misspellings answered correctly
- **Style Flexibility**: Yes — formal/informal/abbreviated queries all handled