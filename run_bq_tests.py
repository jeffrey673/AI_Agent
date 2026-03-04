import requests, json, time, sys

BASE = "http://localhost:8100/v1/chat/completions"
results = []

queries = [
    "이번 달 전체 매출 합계 알려줘",
    "국가별 매출 순위 Top 5",
    "쇼피 플랫폼 이번 달 매출",
    "태국 쇼피 최근 3개월 매출 추이",
    "라자다 전체 매출 합계",
    "틱톡샵 월별 매출 비교",
    "아마존 매출 현황",
    "인도네시아 전체 플랫폼 매출",
    "베트남 쇼피 매출",
    "말레이시아 라자다 매출",
    "이번 달 가장 많이 팔린 제품 Top 10",
    "지난달 대비 매출 증감률",
    "플랫폼별 매출 비중",
    "일별 매출 추이 최근 7일",
    "필리핀 매출 현황",
    "태국 틱톡샵 매출",
    "싱가포르 쇼피 매출",
    "전월 동기 대비 매출 비교",
    "SKU별 판매 수량 Top 10",
    "국가별 플랫폼별 매출 크로스탭",
]

print(f"Starting 20 BigQuery/매출 tests against {BASE}")
print(f"{'='*80}")

for i, q in enumerate(queries, 1):
    start = time.time()
    try:
        r = requests.post(BASE, json={
            "model": "skin1004-Analysis",
            "messages": [{"role": "user", "content": q}],
            "stream": False
        }, headers={"Authorization": "Bearer sk-skin1004"}, timeout=180)
        elapsed = time.time() - start
        data = r.json()
        if "choices" in data:
            answer = data["choices"][0]["message"]["content"][:150]
            status = "OK"
        else:
            answer = str(data)[:150]
            status = "ERROR"
    except Exception as e:
        elapsed = time.time() - start
        answer = str(e)[:150]
        status = "FAIL"

    results.append({"no": i, "query": q, "status": status, "time_s": round(elapsed, 1), "answer": answer})
    print(f"[BQ {i:2d}/20] {status:5s} {elapsed:6.1f}s - {q}")
    sys.stdout.flush()

# Save results to JSON
output_path = "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/test_results_bq.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nResults saved to {output_path}")

# Summary
print(f"\n{'='*80}")
print(f"{'SUMMARY':^80}")
print(f"{'='*80}")

ok_count = sum(1 for r in results if r["status"] == "OK")
err_count = sum(1 for r in results if r["status"] == "ERROR")
fail_count = sum(1 for r in results if r["status"] == "FAIL")
times = [r["time_s"] for r in results]
avg_time = sum(times) / len(times) if times else 0
min_time = min(times) if times else 0
max_time = max(times) if times else 0

print(f"  Total tests:  20")
print(f"  OK:           {ok_count}")
print(f"  ERROR:        {err_count}")
print(f"  FAIL:         {fail_count}")
print(f"  Avg time:     {avg_time:.1f}s")
print(f"  Min time:     {min_time:.1f}s")
print(f"  Max time:     {max_time:.1f}s")
print(f"  Total time:   {sum(times):.1f}s")

# Performance classification
print(f"\n{'='*80}")
print(f"{'PERFORMANCE CLASSIFICATION':^80}")
print(f"{'='*80}")
warn_list = [r for r in results if r["time_s"] >= 100]
fail_perf = [r for r in results if r["time_s"] >= 200]
ok_perf = [r for r in results if r["time_s"] < 100]

if fail_perf:
    print(f"\n  FAIL (>=200s) - {len(fail_perf)} queries:")
    for r in fail_perf:
        print(f"    #{r['no']:2d} {r['time_s']:6.1f}s  {r['query']}")
if warn_list:
    warn_only = [r for r in warn_list if r["time_s"] < 200]
    if warn_only:
        print(f"\n  WARN (>=100s) - {len(warn_only)} queries:")
        for r in warn_only:
            print(f"    #{r['no']:2d} {r['time_s']:6.1f}s  {r['query']}")
print(f"\n  OK (<100s) - {len(ok_perf)} queries")

# Detailed results table
print(f"\n{'='*80}")
print(f"{'DETAILED RESULTS':^80}")
print(f"{'='*80}")
print(f"{'No':>3} | {'Status':>6} | {'Time':>7} | {'Query':<35} | {'Answer (excerpt)'}")
print(f"{'-'*3}-+-{'-'*6}-+-{'-'*7}-+-{'-'*35}-+-{'-'*50}")
for r in results:
    ans_short = r["answer"].replace("\n", " ")[:50]
    print(f"{r['no']:3d} | {r['status']:>6} | {r['time_s']:6.1f}s | {r['query']:<35} | {ans_short}")

print(f"\nDone.")
