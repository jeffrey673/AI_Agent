import requests, json, time

BASE = "http://localhost:8100/v1/chat/completions"
results = []
queries = [
    "노션에서 업무 매뉴얼 찾아줘",
    "마케팅 일정 확인해줘",
    "틱톡샵 운영 방법 알려줘",
    "쇼피 셀러 가이드 내용",
    "라자다 입점 절차",
    "브랜드 가이드라인 내용",
    "제품 등록 프로세스",
    "CS 응대 매뉴얼",
    "물류 배송 정책",
    "프로모션 기획 가이드",
    "SNS 마케팅 전략 문서",
    "인플루언서 협업 가이드",
    "KBT 운영 방법",
    "네이버 스토어 업무 공유",
    "아마존 FBA 가이드",
    "동남아 시장 분석 리포트",
    "신제품 런칭 체크리스트",
    "가격 정책 문서",
    "경쟁사 분석 자료",
    "회의록 확인해줘"
]

for i, q in enumerate(queries, 1):
    start = time.time()
    try:
        r = requests.post(BASE, json={
            "model": "skin1004-Analysis",
            "messages": [{"role": "user", "content": q}],
            "stream": False
        }, headers={"Authorization": "Bearer sk-skin1004"}, timeout=120)
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
    
    # Classify by performance threshold
    if elapsed >= 200:
        perf = "FAIL"
    elif elapsed >= 100:
        perf = "WARN"
    else:
        perf = "OK"
    
    results.append({
        "no": i,
        "query": q,
        "status": status,
        "perf": perf,
        "time_s": round(elapsed, 1),
        "answer": answer
    })
    print(f"[Notion {i:2d}/20] {status:5s} {perf:4s} {elapsed:6.1f}s - {q}")

with open("C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/test_results_notion.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

ok = [r for r in results if r["status"] == "OK"]
err = [r for r in results if r["status"] != "OK"]
times = [r["time_s"] for r in results]
perf_ok = [r for r in results if r["perf"] == "OK"]
perf_warn = [r for r in results if r["perf"] == "WARN"]
perf_fail = [r for r in results if r["perf"] == "FAIL"]

print(f"\n{'='*50}")
print(f"  Notion Test Summary (20 queries)")
print(f"{'='*50}")
print(f"  Status:  OK={len(ok)}, ERROR/FAIL={len(err)}")
print(f"  Perf:    OK={len(perf_ok)} (<100s), WARN={len(perf_warn)} (100-200s), FAIL={len(perf_fail)} (>=200s)")
print(f"  Timing:  Avg={sum(times)/len(times):.1f}s, Min={min(times):.1f}s, Max={max(times):.1f}s")
print(f"{'='*50}")

if perf_warn or perf_fail:
    print(f"\n  Slow queries:")
    for r in perf_warn + perf_fail:
        print(f"    [{r['perf']}] #{r['no']} {r['time_s']}s - {r['query']}")

if err:
    print(f"\n  Failed queries:")
    for r in err:
        print(f"    [{r['status']}] #{r['no']} - {r['query']}: {r['answer'][:80]}")
