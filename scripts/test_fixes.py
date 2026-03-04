"""Quick test for v6.4 fixes: multi parallel, routing fix, empty result improvement."""
import requests
import time
import json

API_URL = "http://localhost:8100/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}

tests = [
    # BQ-08: was 108s (false multi-routing due to "매출 트렌드")
    ("BQ-08", "skin1004-Search", "아마존 미국 2025년 월별 매출 트렌드", "bigquery"),
    # BQ-11/12/14: empty results (SHORT) → now should give helpful suggestions
    ("BQ-11", "skin1004-Search", "2024년 하반기 동남아시아 국가별 매출 순위", "bigquery"),
    ("BQ-12", "skin1004-Search", "일본 아마존 2025년 매출 알려줘", "bigquery"),
    ("BQ-14", "skin1004-Search", "필리핀 쇼피 vs 라자다 매출 비교", "bigquery"),
    # MULTI: was 103-165s → now parallel + Flash synthesis
    ("MULTI-01", "skin1004-Search", "인도네시아 뷰티 시장 트렌드와 우리 매출 분석해줘", "multi"),
    ("MULTI-03", "skin1004-Search", "미국 K-뷰티 트렌드와 아마존 매출 연관성 분석", "multi"),
    ("MULTI-05", "skin1004-Search", "일본 화장품 시장 전망과 우리 일본 매출 분석", "multi"),
    ("MULTI-09", "skin1004-Search", "K-뷰티 글로벌 뉴스와 SKIN1004 실적 비교", "multi"),
    # EDGE empty results
    ("EDGE-01", "skin1004-Search", "2030년 매출 알려줘", "bigquery"),
    ("EDGE-20", "skin1004-Search", "대만 쇼피 2025년 매출 알려줘", "bigquery"),
]

print(f"{'='*70}")
print(f"v6.4 Fix Verification Test — {len(tests)} queries")
print(f"{'='*70}")

results = []
for i, (tag, model, q, expected) in enumerate(tests, 1):
    print(f"\n[{i}/{len(tests)}] [{tag}] {q}", flush=True)
    t0 = time.time()
    try:
        resp = requests.post(API_URL, json={
            "model": model,
            "messages": [{"role": "user", "content": q}]
        }, headers=HEADERS, timeout=180)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"  -> HTTP_ERR {resp.status_code} ({elapsed:.1f}s)", flush=True)
            results.append({"tag": tag, "status": "HTTP_ERR", "time": elapsed, "answer": ""})
            continue

        answer = resp.json()["choices"][0]["message"]["content"]
        answer_len = len(answer)
        has_chart = "![chart]" in answer or "![Chart]" in answer
        is_short = answer_len < 30
        is_error = any(kw in answer[:200] for kw in ["오류가 발생", "SQL 실행 실패", "ConnectError"])

        perf = "FAIL" if elapsed >= 90 else ("WARN" if elapsed >= 60 else "OK")
        status = "ERROR" if is_error else ("SHORT" if is_short else "OK")

        chart_tag = " [CHART]" if has_chart else ""
        preview = answer[:150].replace('\n', ' ')
        print(f"  -> {status} | {perf} | {elapsed:.1f}s | {answer_len}ch{chart_tag}", flush=True)
        print(f"     {preview}", flush=True)
        results.append({"tag": tag, "status": status, "perf": perf, "time": elapsed, "len": answer_len, "answer": answer[:300]})
    except requests.exceptions.Timeout:
        elapsed = time.time() - t0
        print(f"  -> TIMEOUT ({elapsed:.1f}s)", flush=True)
        results.append({"tag": tag, "status": "TIMEOUT", "time": elapsed, "answer": ""})
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  -> EXCEPTION ({elapsed:.1f}s) {e}", flush=True)
        results.append({"tag": tag, "status": "EXCEPTION", "time": elapsed, "answer": ""})

# Summary
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")

ok = sum(1 for r in results if r["status"] == "OK")
warns = sum(1 for r in results if r["perf"] == "WARN")
fails = sum(1 for r in results if r["perf"] == "FAIL")
shorts = sum(1 for r in results if r["status"] == "SHORT")
avg_time = sum(r["time"] for r in results) / len(results) if results else 0

print(f"OK: {ok}/{len(results)} | WARN: {warns} | FAIL: {fails} | SHORT: {shorts} | Avg: {avg_time:.1f}s")
print()

for r in results:
    icon = "OK" if r["status"] == "OK" and r["perf"] == "OK" else r["perf"] if r["perf"] != "OK" else r["status"]
    print(f"  [{icon:>5}] [{r['tag']:>8}] {r['time']:6.1f}s  {r['len'] if 'len' in r else 0:>5}ch")

# Save
with open("test_fixes_result.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved to test_fixes_result.json")
