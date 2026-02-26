# -*- coding: utf-8 -*-
import requests, json, time, os, sys

API = "http://localhost:8100/v1/chat/completions"
HEADERS = {"Authorization": "Bearer sk-skin1004", "Content-Type": "application/json"}

queries = [
    "노션에서 제품 성분 정보 찾아줘",
    "신제품 런칭 프로세스 알려줘",
    "마케팅 캠페인 가이드라인",
    "입사자 온보딩 절차",
    "재고 관리 정책",
    "반품 처리 매뉴얼",
    "해외 배송 가이드",
    "브랜드 가이드라인",
    "인사 평가 기준",
    "노션 문서 목록 보여줘",
    "제품 카탈로그 정보",
    "CS 응대 매뉴얼",
    "틱톡샵 운영 방법",
    "쇼피 셀러 가이드",
    "회사 조직도",
    "마케팅 예산 계획",
    "제품 성분표 확인",
    "업무 프로세스 문서",
    "사내 규정 안내",
    "노션에 있는 매뉴얼 검색해줘",
]

results = []
for i, q in enumerate(queries):
    print(f"[Notion {i+1}/20] {q}", flush=True)
    start = time.time()
    try:
        resp = requests.post(API, headers=HEADERS, json={
            "model": "skin1004-Analysis",
            "messages": [{"role": "user", "content": q}],
            "stream": False
        }, timeout=300)
        elapsed = round(time.time() - start, 1)
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:200]
        status = "OK" if elapsed < 100 else ("WARN" if elapsed < 200 else "FAIL")
        if "오류" in answer or "error" in answer.lower():
            status = "ERROR"
        results.append({"id": i+1, "query": q, "time_s": elapsed, "status": status, "answer_preview": answer})
        print(f"  -> {status} ({elapsed}s)", flush=True)
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        results.append({"id": i+1, "query": q, "time_s": elapsed, "status": "ERROR", "answer_preview": str(e)[:200]})
        print(f"  -> ERROR ({elapsed}s): {e}", flush=True)

OUTPUT = os.path.join("C:" + os.sep, "Users", "DB_PC", "Desktop", "python_bcj", "AI_Agent", "test_results_notion.json")
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
ok = len([r for r in results if r["status"]=="OK"])
warn = len([r for r in results if r["status"]=="WARN"])
fail = len([r for r in results if r["status"]=="FAIL"])
error = len([r for r in results if r["status"]=="ERROR"])
print(f"Done. OK={ok} WARN={warn} FAIL={fail} ERROR={error} / Total={len(results)}", flush=True)
