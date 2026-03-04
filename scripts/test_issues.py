"""Retest problematic items from QA 300: WARN + ERROR + SHORT."""
import requests
import time
import json

API_URL = "http://localhost:8100/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}

tests = [
    # WARN (Multi 106-113s) — now with Flash search
    ("MULTI-09", "skin1004-Search", "K-뷰티 글로벌 뉴스와 SKIN1004 실적 비교", "multi"),
    ("MULTI-15", "skin1004-Search", "블랙프라이데이 시즌 아마존 매출 영향 분석", "multi"),
    ("EDGE-40", "skin1004-Search", "2024년 3분기 vs 4분기 인도네시아 플랫폼별 매출 변화와 원인 분석", "multi"),
    # ERROR (NT-03 false positive)
    ("NT-03", "skin1004-Search", "노션에서 데이터 분석 파트 정보 알려줘", "notion"),
    # SHORT items
    ("DIRECT-10", "skin1004-Search", "고마워! 오늘도 잘 부탁해", "direct"),
    ("DIRECT-14", "skin1004-Search", "SKIN1004 설립 연도가 언제야?", "direct"),
    ("DIRECT-21", "skin1004-Search", "좋은 아침이야!", "direct"),
    ("DIRECT-25", "skin1004-Search", "다음에 또 물어볼게 잘 있어!", "direct"),
    ("EDGE-28", "skin1004-Search", "얼마", "direct"),
    ("EDGE-30", "skin1004-Search", "ㅎㅇ", "direct"),
]

ERROR_KEYWORDS = ["오류가 발생", "SQL 실행 실패", "ConnectError", "ReadError"]

print(f"{'='*70}")
print(f"Issue Retest — {len(tests)} queries (v6.5 fixes)")
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
            results.append({"tag": tag, "status": "HTTP_ERR", "perf": "OK", "time": elapsed, "len": 0, "answer": ""})
            continue

        answer = resp.json()["choices"][0]["message"]["content"]
        answer_len = len(answer)

        # Fixed error detection: only check first 200 chars
        is_error = any(kw in answer[:200] for kw in ERROR_KEYWORDS)
        is_short = answer_len < 30
        perf = "FAIL" if elapsed >= 90 else ("WARN" if elapsed >= 60 else "OK")
        status = "ERROR" if is_error else ("SHORT" if is_short else "OK")

        preview = answer[:150].replace('\n', ' ')
        print(f"  -> {status} | {perf} | {elapsed:.1f}s | {answer_len}ch", flush=True)
        print(f"     {preview}", flush=True)
        results.append({"tag": tag, "status": status, "perf": perf, "time": elapsed, "len": answer_len, "answer": answer[:300]})
    except requests.exceptions.Timeout:
        elapsed = time.time() - t0
        print(f"  -> TIMEOUT ({elapsed:.1f}s)", flush=True)
        results.append({"tag": tag, "status": "TIMEOUT", "perf": "FAIL", "time": elapsed, "len": 0, "answer": ""})
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  -> EXCEPTION ({elapsed:.1f}s) {e}", flush=True)
        results.append({"tag": tag, "status": "EXCEPTION", "perf": "FAIL", "time": elapsed, "len": 0, "answer": ""})

# Summary
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")

ok = sum(1 for r in results if r["status"] == "OK")
warns = sum(1 for r in results if r["perf"] == "WARN")
fails = sum(1 for r in results if r["perf"] == "FAIL")
shorts = sum(1 for r in results if r["status"] == "SHORT")
errors = sum(1 for r in results if r["status"] == "ERROR")
avg_time = sum(r["time"] for r in results) / len(results) if results else 0

print(f"OK: {ok}/{len(results)} | WARN: {warns} | FAIL: {fails} | SHORT: {shorts} | ERROR: {errors} | Avg: {avg_time:.1f}s")
print()

for r in results:
    icon = r["status"] if r["status"] != "OK" else r["perf"]
    print(f"  [{icon:>7}] [{r['tag']:>10}] {r['time']:6.1f}s  {r['len']:>5}ch")

with open("test_issues_result.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved to test_issues_result.json")
