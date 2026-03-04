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

GWS_QUERIES = [
    "내 이메일 확인해줘",
    "오늘 캘린더 일정",
    "이번 주 미팅 일정",
    "내일 일정 알려줘",
    "최근 받은 메일 요약",
    "안 읽은 메일 몇 개야",
    "이번 주 회의 일정",
    "다음 주 스케줄",
    "캘린더에 회의 있어?",
    "최근 보낸 메일 확인",
    "이메일에서 인보이스 찾아줘",
    "구글 드라이브 파일 찾아줘",
    "최근 공유된 문서",
    "캘린더 이번 달 일정",
    "메일에서 배송 관련 내용",
    "지난주 받은 메일 중 중요한 것",
    "내 메일함 정리해줘",
    "캘린더에 휴가 등록되어있어?",
    "이메일 검색해줘 skin1004",
    "다음 미팅 언제야",
]

results = []

for i, q in enumerate(GWS_QUERIES, 1):
    print(f"[GWS {i:02d}/20] {q} ...", end=" ", flush=True)
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
        # Determine pass/fail by performance threshold
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
out_path = "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/test_results_gws.json"
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
print(f"GWS TEST SUMMARY ({len(results)} queries)")
print(f"{'='*60}")
print(f"  OK:   {ok_count}")
print(f"  WARN: {warn_count}")
print(f"  FAIL: {fail_count}")
print(f"  Avg time: {avg_time}s")
print(f"  Routes: {routes}")
print(f"  Saved to: {out_path}")
