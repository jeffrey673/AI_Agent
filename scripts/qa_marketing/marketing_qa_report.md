# SKIN1004 Marketing QA 3,300 Report

**Date**: 2026-03-07 11:06
**Tables**: 13
**Total Questions**: 3900

## Overall Summary

| Metric | Value |
|--------|-------|
| Pass Rate (OK+WARN) | **100.0%** (3900/3900) |
| OK Rate | 89.4% (3488) |
| WARN | 412 |
| FAIL/ERROR/EMPTY | 0 |
| Avg Latency | 40.8s |
| P50 Latency | 38.3s |
| P95 Latency | 66.6s |

## Per-Table Results

| Table | Total | OK | WARN | FAIL | Pass% | Avg(s) | P50(s) | P95(s) |
|-------|-------|-----|------|------|-------|--------|--------|--------|
| advertising | 300 | 292 | 8 | 0 | 100.0% | 35.1 | 33.6 | 55.6 |
| amazon_search | 300 | 263 | 37 | 0 | 100.0% | 40.9 | 36.4 | 74.7 |
| influencer | 300 | 278 | 22 | 0 | 100.0% | 39.0 | 38.0 | 63.4 |
| marketing_cost | 300 | 270 | 30 | 0 | 100.0% | 42.1 | 41.1 | 66.0 |
| meta_ads | 300 | 254 | 46 | 0 | 100.0% | 43.7 | 41.5 | 69.3 |
| platform | 300 | 242 | 58 | 0 | 100.0% | 46.5 | 46.8 | 71.0 |
| product | 300 | 263 | 37 | 0 | 100.0% | 42.4 | 40.9 | 70.2 |
| review_amazon | 300 | 237 | 63 | 0 | 100.0% | 45.9 | 45.4 | 72.9 |
| review_qoo10 | 300 | 270 | 30 | 0 | 100.0% | 42.9 | 41.7 | 66.0 |
| review_shopee | 300 | 264 | 36 | 0 | 100.0% | 42.5 | 40.6 | 68.4 |
| review_smartstore | 300 | 266 | 34 | 0 | 100.0% | 42.7 | 40.7 | 68.6 |
| sales_all | 300 | 297 | 3 | 0 | 100.0% | 33.6 | 31.3 | 53.9 |
| shopify | 300 | 292 | 8 | 0 | 100.0% | 33.2 | 31.6 | 53.1 |

## Latency Distribution

| Range | Count | Percent |
|-------|-------|---------|
| <10s | 3 | 0.1% |
| 10-20s | 138 | 3.5% |
| 20-30s | 781 | 20.0% |
| 30-45s | 1627 | 41.7% |
| 45-60s | 938 | 24.1% |
| 60-90s | 413 | 10.6% |
| 90s+ | 0 | 0.0% |

## Slow Queries — WARN (412건, top 30)

| ID | Table | Time | Query |
|----|-------|------|-------|
| IF-222 | influencer | 89.8s | 팔로워수와 조회수 상관관계 |
| RQ-149 | review_qoo10 | 89.6s | 큐텐 제품별 리뷰 트렌드 |
| PL-085 | platform | 89.4s | 순위 상위 제품들의 가격 분석 |
| AZ-245 | amazon_search | 89.1s | 아마존 전환율 통계 분석 |
| AZ-226 | amazon_search | 88.9s | 아마존 노출 대비 구매 전환율 분석 |
| MT-029 | meta_ads | 88.6s | 메타 광고 스냅샷 데이터 |
| PL-272 | platform | 88.3s | 채널별 경쟁 강도 분석 |
| AD-265 | advertising | 88.0s | 전환율이 가장 높은 국가와 플랫폼 조합 |
| PL-090 | platform | 86.9s | 순위 상위 제품의 할인율 |
| PL-207 | platform | 86.9s | SKIN1004 채널별 포지셔닝 분석 |
| RT-057 | review_smartstore | 86.3s | 스마트스토어 최근 리뷰 3건만 보여줘 |
| AZ-253 | amazon_search | 85.9s | 아마존 전환율 분포 분석 |
| RA-149 | review_amazon | 85.7s | 아마존 제품별 리뷰 트렌드 |
| RA-176 | review_amazon | 85.4s | Amazon 전체 리뷰 건수 추이 차트 |
| RS-033 | review_shopee | 85.4s | 쇼피 리뷰 수집 날짜 기준 최신순 정렬 |
| RA-152 | review_amazon | 85.3s | Amazon 최근 리뷰 30건 한국어 번역 |
| RA-105 | review_amazon | 85.2s | 아마존 리뷰 수 증가율 |
| MT-025 | meta_ads | 84.9s | 가장 광고 많은 페이지는? |
| AZ-050 | amazon_search | 84.6s | 아마존 전환율 순위 |
| MC-299 | marketing_cost | 84.4s | 2025년 마케팅 비용 종합 분석 리포트 |
| MC-265 | marketing_cost | 84.2s | 매체별 매출 월별 추이 |
| AZ-220 | amazon_search | 84.1s | 아마존 캐나다 전체 데이터 |
| AZ-300 | amazon_search | 84.1s | 아마존 데이터 품질 점검 리포트 |
| RA-077 | review_amazon | 83.7s | 아마존 최근 리뷰 25건 |
| PL-046 | platform | 83.6s | 채널별 SKIN1004 가격 범위 |
| RT-198 | review_smartstore | 83.4s | 스마트스토어 최근 리뷰 8건 |
| RS-256 | review_shopee | 83.1s | Shopee 리뷰 제품별 월별 통계표 |
| MT-294 | meta_ads | 83.0s | 플랫폼별 광고 비율 분석 |
| IF-069 | influencer | 82.1s | 말레이시아 인플루언서 마케팅 성과 |
| RA-245 | review_amazon | 82.0s | 아마존 리뷰 번역문 최근 순 |
