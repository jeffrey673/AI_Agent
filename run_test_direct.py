import requests
import json
import time
import sys

URL = "http://localhost:8100/v1/chat/completions"
HEADERS = {
    "Authorization": "Bearer sk-skin1004",
    "Content-Type": "application/json"
}
MODEL = "skin1004-Analysis"
TIMEOUT = 120

DIRECT_QUERIES = [
    "안녕하세요",
    "SKIN1004는 어떤 브랜드야?",
    "마다가스카르 센텔라란?",
    "동남아 이커머스 시장 트렌드",
    "쇼피란 무엇인가?",
    "라자다와 쇼피의 차이점",
    "틱톡샵 마케팅 전략",
    "K-뷰티 글로벌 트렌드",
    "태국 화장품 시장 규모",
    "인도네시아 뷰티 시장 분석 및 매출 데이터",
    "비건 화장품 트렌드와 우리 매출 영향",
    "오늘 날씨 어때?",
    "환율 정보 알려줘",
    "고마워",
    "도움말",
    "시스템 상태 확인",
    "SKIN1004 베스트셀러 제품은?",
    "센텔라 앰플 성분 알려줘",
    "동남아 매출과 시장 트렌드 종합 분석해줘",
    "태국과 베트남 시장 비교 분석",
]

results = []

for i, q in enumerate(DIRECT_QUERIES, 1):
    print(f"[DIRECT {i:02d}/20] {q} ...", end=" ", flush=True)
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": q}],
        "stream": False
    }
    start = time.time()
    try:
        r = requests.post(URL, headers=HEADERS, json=payload, timeout=TIMEOUT)
        elapsed = round(time.time() - start, 1)
        data = r.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "NO_CONTENT")
        route = data.get("route_type", "unknown")
        status = "OK" if r.status_code == 200 else f"HTTP_{r.status_code}"
        if elapsed >= 200:
            grade = "FAIL"
        elif elapsed >= 100:
            grade = "WARN"
        else:
            grade = "OK"
        print(f"{grade} ({elapsed}s) route={route}")
    except requests.exceptions.Timeout:
        elapsed = round(time.time() - start, 1)
        answer = "TIMEOUT"
        route = "unknown"
        status = "TIMEOUT"
        grade = "FAIL"
        print(f"TIMEOUT ({elapsed}s)")
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        answer = str(e)
        route = "unknown"
        status = "ERROR"
        grade = "FAIL"
        print(f"ERROR ({elapsed}s): {e}")

    results.append({
        "index": i,
        "query": q,
        "route_type": route,
        "status": status,
        "grade": grade,
        "elapsed_s": elapsed,
        "answer_preview": answer[:300] if answer else ""
    })

# Save results
out_path = "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/test_results_direct.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Summary
ok_count = sum(1 for r in results if r["grade"] == "OK")
warn_count = sum(1 for r in results if r["grade"] == "WARN")
fail_count = sum(1 for r in results if r["grade"] == "FAIL")
avg_time = round(sum(r["elapsed_s"] for r in results) / len(results), 1)
routes = {}
for r in results:
    rt = r["route_type"]
    routes[rt] = routes.get(rt, 0) + 1

print(f"\n{'='*60}")
print(f"DIRECT/MULTI TEST SUMMARY ({len(results)} queries)")
print(f"{'='*60}")
print(f"  OK:   {ok_count}")
print(f"  WARN: {warn_count}")
print(f"  FAIL: {fail_count}")
print(f"  Avg time: {avg_time}s")
print(f"  Routes: {routes}")
print(f"  Saved to: {out_path}")
