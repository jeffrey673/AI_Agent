"""CS Agent 종합 테스트 — 다양한 질문 유형으로 라우팅 + 답변 품질 검증."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8100/v1/chat/completions"

# ── 테스트 질문 30개: 다양한 변수 ──
TEST_QUERIES = [
    # --- 1. 제품별 직접 질문 (라인명 포함) ---
    {"id": "CS-01", "q": "센텔라 앰플 어떻게 사용해?", "expect_route": "cs", "category": "사용법"},
    {"id": "CS-02", "q": "포어마이징 세럼 성분이 뭐야?", "expect_route": "cs", "category": "성분"},
    {"id": "CS-03", "q": "히알루-시카 토너 히알루론산 함량 알려줘", "expect_route": "cs", "category": "성분함량"},
    {"id": "CS-04", "q": "톤브라이트닝 라인 비타민C 함유량", "expect_route": "cs", "category": "성분함량"},
    {"id": "CS-05", "q": "티트리카 B5 크림에 SPF 있어?", "expect_route": "cs", "category": "제품특성"},

    # --- 2. 비건/인증 관련 ---
    {"id": "CS-06", "q": "비건 인증 받은 제품 목록 알려줘", "expect_route": "cs", "category": "비건"},
    {"id": "CS-07", "q": "PETA 인증이 뭐야?", "expect_route": "cs", "category": "비건"},
    {"id": "CS-08", "q": "센텔라 앰플 비건인가요?", "expect_route": "cs", "category": "비건"},

    # --- 3. 사용법/루틴 ---
    {"id": "CS-09", "q": "스킨케어 루틴 순서 알려줘", "expect_route": "cs", "category": "루틴"},
    {"id": "CS-10", "q": "앰플이랑 크림 바르는 순서가 어떻게 돼?", "expect_route": "cs", "category": "루틴"},
    {"id": "CS-11", "q": "센텔라 라인 사용 순서", "expect_route": "cs", "category": "루틴"},

    # --- 4. 피부 타입/민감 ---
    {"id": "CS-12", "q": "민감한 피부에 센텔라 앰플 써도 돼?", "expect_route": "cs", "category": "피부타입"},
    {"id": "CS-13", "q": "아토피 피부에 사용 가능한 제품 있어?", "expect_route": "cs", "category": "피부타입"},
    {"id": "CS-14", "q": "임산부가 사용해도 되나요?", "expect_route": "cs", "category": "안전성"},
    {"id": "CS-15", "q": "어린이도 사용할 수 있나요?", "expect_route": "cs", "category": "안전성"},

    # --- 5. 보관/유통 ---
    {"id": "CS-16", "q": "제품 보관 방법이 어떻게 돼?", "expect_route": "cs", "category": "보관"},
    {"id": "CS-17", "q": "유통기한 지나면 사용해도 돼?", "expect_route": "cs", "category": "유통기한"},
    {"id": "CS-18", "q": "개봉 후 사용 기한이 얼마야?", "expect_route": "cs", "category": "유통기한"},

    # --- 6. 트러블/부작용 ---
    {"id": "CS-19", "q": "센텔라 앰플 쓰고 트러블 났어요", "expect_route": "cs", "category": "트러블"},
    {"id": "CS-20", "q": "알레르기 반응이 있으면 어떻게 해야 하나요?", "expect_route": "cs", "category": "트러블"},
    {"id": "CS-21", "q": "레티놀 사용 후 피부가 붉어졌어요", "expect_route": "cs", "category": "트러블"},

    # --- 7. 브랜드별 질문 ---
    {"id": "CS-22", "q": "커먼랩스 비타민C 선세럼 성분 함량", "expect_route": "cs", "category": "타브랜드"},
    {"id": "CS-23", "q": "좀비뷰티 블러디필 BHA 함량 알려줘", "expect_route": "cs", "category": "타브랜드"},

    # --- 8. 프로바이오시카/랩인네이처 ---
    {"id": "CS-24", "q": "프로바이오시카 앰플이랑 센텔라 앰플 같이 써도 돼?", "expect_route": "cs", "category": "혼합사용"},
    {"id": "CS-25", "q": "랩인네이처 레티놀 부스팅샷 사용 시 주의사항", "expect_route": "cs", "category": "사용법"},

    # --- 9. 라우팅 경계 테스트 (CS가 아닌 것) ---
    {"id": "BQ-01", "q": "2024년 미국 아마존 매출 알려줘", "expect_route": "bigquery", "category": "매출조회"},
    {"id": "GWS-01", "q": "오늘 내 일정 알려줘", "expect_route": "gws", "category": "캘린더"},
    {"id": "DIR-01", "q": "안녕하세요", "expect_route": "direct", "category": "인사"},
    {"id": "NOT-01", "q": "노션에서 반품 정책 찾아줘", "expect_route": "notion", "category": "노션"},
    {"id": "MUL-01", "q": "날씨가 인도네시아 매출에 영향을 줬어?", "expect_route": "multi", "category": "복합"},
]


def test_routing_only():
    """Test keyword classification without API call."""
    from app.agents.orchestrator import OrchestratorAgent
    orch = OrchestratorAgent()

    print("=" * 70)
    print("PHASE 1: 라우팅 정확도 테스트 (30개)")
    print("=" * 70)

    correct = 0
    wrong = []
    for t in TEST_QUERIES:
        route = orch._keyword_classify(t["q"])
        ok = route == t["expect_route"]
        correct += ok
        status = "OK" if ok else "FAIL"
        print(f'  [{status}] {t["id"]:6s} [{route:8s}] (expect:{t["expect_route"]:8s}) {t["q"][:45]}')
        if not ok:
            wrong.append(t)

    print(f"\n라우팅 정확도: {correct}/{len(TEST_QUERIES)} ({100*correct/len(TEST_QUERIES):.0f}%)")
    if wrong:
        print(f"오분류: {[w['id'] for w in wrong]}")
    return correct == len(TEST_QUERIES)


def test_cs_api():
    """Test CS queries through the actual API."""
    cs_queries = [t for t in TEST_QUERIES if t["expect_route"] == "cs"]

    print("\n" + "=" * 70)
    print(f"PHASE 2: CS API E2E 테스트 ({len(cs_queries)}개)")
    print("=" * 70)

    results = []
    for t in cs_queries:
        payload = {
            "model": "gemini",
            "messages": [{"role": "user", "content": t["q"]}],
            "stream": False,
        }
        start = time.time()
        try:
            resp = requests.post(API_URL, json=payload, timeout=120)
            elapsed = time.time() - start
            data = resp.json()

            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            answer_len = len(answer)

            # Quality checks
            is_empty = answer_len < 20
            is_generic = "죄송" in answer and "찾지 못" in answer and answer_len < 100
            has_content = answer_len >= 50

            if elapsed >= 100:
                status = "FAIL"
            elif is_empty:
                status = "EMPTY"
            elif elapsed >= 60:
                status = "WARN"
            else:
                status = "OK"

            results.append({
                "id": t["id"],
                "query": t["q"],
                "category": t["category"],
                "status": status,
                "time": round(elapsed, 1),
                "answer_len": answer_len,
                "answer_preview": answer[:150].replace("\n", " "),
            })

            print(f'  [{status:5s}] {t["id"]:6s} {elapsed:5.1f}s  len={answer_len:4d}  {t["category"]:8s}  {t["q"][:35]}')

        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "id": t["id"],
                "query": t["q"],
                "category": t["category"],
                "status": "ERROR",
                "time": round(elapsed, 1),
                "answer_len": 0,
                "answer_preview": str(e)[:150],
            })
            print(f'  [ERROR] {t["id"]:6s} {elapsed:5.1f}s  {str(e)[:60]}')

    # Summary
    print("\n" + "-" * 70)
    ok_count = sum(1 for r in results if r["status"] == "OK")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    fail_count = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    avg_time = sum(r["time"] for r in results) / len(results) if results else 0

    print(f"OK: {ok_count}  WARN: {warn_count}  FAIL: {fail_count}  평균: {avg_time:.1f}s")

    # Print detailed answers for review
    print("\n" + "=" * 70)
    print("PHASE 3: 답변 상세 (CS 질문)")
    print("=" * 70)
    for r in results:
        print(f'\n--- {r["id"]} [{r["category"]}] {r["query"]} ---')
        print(f'    시간: {r["time"]}s | 길이: {r["answer_len"]}자')
        print(f'    답변: {r["answer_preview"]}...')

    # Save results
    with open("test_results_cs.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: test_results_cs.json")

    return results


if __name__ == "__main__":
    test_routing_only()
    test_cs_api()
