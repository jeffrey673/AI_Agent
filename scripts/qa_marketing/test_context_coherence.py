"""Context Coherence Test — 20-message conversation chains.

Tests if the AI maintains context across multi-turn conversations,
similar to ChatGPT-level conversational ability.

Creates 13 conversation chains (one per table), each with 20 related
messages that progressively build on previous answers.
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

API_URL = "http://localhost:3001/v1/chat/completions"
MODEL = "gemini"
TIMEOUT = 180
CHAIN_LENGTH = 20  # Messages per conversation chain

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results_context"
CHAINS_FILE = BASE_DIR / "context_chains.json"
RESULTS_FILE = BASE_DIR / "context_results.json"

# Thresholds
FAIL_THRESHOLD = 90
WARN_THRESHOLD = 60
MIN_ANSWER_LEN = 20


# ============================================================
# Conversation chains — 13 tables × 20 messages each
# Each chain simulates a realistic multi-turn conversation
# ============================================================

CONVERSATION_CHAINS = {
    "sales_all": [
        "올해 전체 매출이 얼마야?",
        "그중에서 가장 매출이 높은 국가는?",
        "그 국가의 월별 추이 보여줘",
        "전년 동기 대비 얼마나 성장했어?",
        "두 번째로 매출 높은 국가는?",
        "1위와 2위 국가를 비교해줘",
        "B2B와 B2C 비율은 어떻게 돼?",
        "B2C 중 가장 큰 채널은?",
        "그 채널의 최근 3개월 매출은?",
        "전체 채널 중 성장률이 가장 높은 곳은?",
        "쇼피 전체 매출 합산은?",
        "쇼피 국가별로 분해해줘",
        "인도네시아 쇼피가 전체 쇼피에서 차지하는 비중은?",
        "인도네시아 쇼피의 월별 추이도 보여줘",
        "아마존 전체 매출도 알려줘",
        "아마존과 쇼피 매출 비교하면?",
        "틱톡 매출은 어때?",
        "쇼피, 아마존, 틱톡 3개 채널 비교표 만들어줘",
        "가장 성장률이 높은 채널은 어디야?",
        "종합적으로 올해 매출 현황을 정리해줘",
    ],
    "product": [
        "전체 제품 수량은 얼마야?",
        "가장 많이 팔린 제품은?",
        "그 제품의 월별 판매량 추이 보여줘",
        "앰플 카테고리 수량은?",
        "앰플 중에서 가장 인기 있는 제품은?",
        "선케어 카테고리도 보여줘",
        "앰플과 선케어 비교하면?",
        "크림 카테고리 수량은?",
        "카테고리별 TOP 3 제품 뽑아줘",
        "센텔라 라인 제품들 리스트 보여줘",
        "센텔라 라인 총 수량은?",
        "히알루시카 라인도 보여줘",
        "센텔라와 히알루시카 비교하면?",
        "국가별로 가장 인기 있는 제품은?",
        "인도네시아에서 인기 제품은?",
        "베트남에서는?",
        "인도네시아와 베트남 인기 제품 비교해줘",
        "올해 신제품은 뭐가 있어?",
        "SET 상품 중 가장 많이 팔린 건?",
        "전체 제품 현황 요약해줘",
    ],
    "advertising": [
        "전체 광고비는 얼마야?",
        "ROAS가 가장 높은 캠페인은?",
        "그 캠페인의 상세 지표 보여줘",
        "월별 광고비 추이는?",
        "CTR이 가장 높은 광고는?",
        "전환율 TOP 5는?",
        "플랫폼별 광고 성과 비교해줘",
        "쇼피 광고 성과는?",
        "아마존 광고 성과는?",
        "쇼피와 아마존 광고 비교하면?",
        "이번 달 광고비 얼마 썼어?",
        "지난달과 비교하면?",
        "노출수 추이 보여줘",
        "클릭수 추이도",
        "CPC 평균은?",
        "국가별 광고 성과는?",
        "가장 효율 좋은 국가는?",
        "인도네시아 광고 상세 보여줘",
        "태국은?",
        "전체 광고 현황 종합 리포트 만들어줘",
    ],
    "marketing_cost": [
        "전체 마케팅 비용은 얼마야?",
        "매체별로 분해해줘",
        "가장 비용이 많은 매체는?",
        "그 매체의 월별 추이 보여줘",
        "팀별 마케팅 비용은?",
        "가장 많이 쓴 팀은?",
        "그 팀이 주로 쓰는 매체는?",
        "광고비와 인플루언서 비용 비중은?",
        "인플루언서 비용이 가장 높은 팀은?",
        "분기별 마케팅 비용 추이는?",
        "전년 대비 증감은?",
        "매체별 비용 효율은 어때?",
        "국가별 마케팅 비용은?",
        "인도네시아 마케팅 비용은?",
        "태국은?",
        "인도네시아와 태국 비교해줘",
        "구매수 대비 마케팅 비용은?",
        "가장 효율적인 국가는?",
        "올해 마케팅 비용 전망은?",
        "마케팅 비용 종합 분석해줘",
    ],
    "influencer": [
        "전체 인플루언서 수는?",
        "팔로워 가장 많은 인플루언서는?",
        "조회수 TOP 10 보여줘",
        "좋아요 TOP 10은?",
        "팀별 인플루언서 수는?",
        "가장 많은 팀은?",
        "그 팀 인플루언서 리스트 보여줘",
        "티어별 인플루언서 수는?",
        "마이크로 인플루언서는 몇 명?",
        "매크로 vs 마이크로 비교하면?",
        "국가별 인플루언서 수는?",
        "한국 인플루언서 리스트",
        "베트남은?",
        "캠페인별 인플루언서 수는?",
        "인플루언서 비용 총합은?",
        "비용 대비 조회수 효율은?",
        "에이전시별 인플루언서 비용은?",
        "가장 효율적인 에이전시는?",
        "콘텐츠 유형별 성과 비교해줘",
        "인플루언서 마케팅 종합 요약해줘",
    ],
    "shopify": [
        "Shopify 전체 매출은?",
        "국가별로 분해해줘",
        "가장 매출 높은 국가는?",
        "그 국가의 월별 추이는?",
        "제품별 매출 TOP 10은?",
        "가장 많이 팔린 제품은?",
        "그 제품의 월별 추이 보여줘",
        "평균 주문 금액은?",
        "주문 건수 추이는?",
        "할인율 평균은?",
        "미국 Shopify 매출은?",
        "일본은?",
        "미국과 일본 비교하면?",
        "카테고리별 매출은?",
        "선케어 매출은?",
        "앰플 매출은?",
        "선케어와 앰플 비교하면?",
        "전년 대비 성장률은?",
        "재구매율 관련 데이터 있어?",
        "Shopify 종합 현황 정리해줘",
    ],
    "platform": [
        "플랫폼별 SKIN1004 가격은?",
        "가장 비싼 채널은?",
        "가장 저렴한 채널은?",
        "채널 간 가격 차이는?",
        "쇼피에서 SKIN1004 가격은?",
        "아마존에서는?",
        "쇼피와 아마존 가격 비교하면?",
        "제품별 순위는?",
        "1위 제품은 뭐야?",
        "그 제품의 채널별 가격은?",
        "할인율 가장 높은 채널은?",
        "원가 대비 할인율은?",
        "센텔라 앰플 채널별 가격은?",
        "선크림 채널별 가격은?",
        "가격 경쟁력이 높은 채널은?",
        "가격이 변동된 제품은?",
        "경쟁사 제품과 가격 비교 가능해?",
        "라자다에서 SKIN1004 가격은?",
        "틱톡샵에서는?",
        "채널별 가격 전략 요약해줘",
    ],
    "amazon_search": [
        "아마존 검색 전환율 평균은?",
        "전환율 가장 높은 국가는?",
        "그 국가의 월별 추이 보여줘",
        "CTR 평균은?",
        "CTR 가장 높은 제품은?",
        "클릭수 TOP 10은?",
        "노출수 추이 보여줘",
        "장바구니 추가율은?",
        "장바구니율 가장 높은 국가는?",
        "미국 아마존 검색 성과 보여줘",
        "일본은?",
        "미국과 일본 비교하면?",
        "제품별 검색 성과 TOP 5는?",
        "센텔라 앰플의 검색 성과는?",
        "선크림 검색 성과는?",
        "앰플과 선크림 비교하면?",
        "검색 키워드별 성과 있어?",
        "전환율이 개선된 제품은?",
        "매출과 검색 성과 상관관계는?",
        "아마존 검색 성과 종합 리포트 만들어줘",
    ],
    "review_amazon": [
        "아마존 리뷰 총 몇 건이야?",
        "평균 평점은?",
        "별점 분포 보여줘",
        "5점 리뷰가 가장 많은 제품은?",
        "1점 리뷰가 가장 많은 제품은?",
        "최근 리뷰 10건 보여줘",
        "긍정적인 리뷰 키워드는?",
        "부정적인 리뷰 키워드는?",
        "제품별 리뷰 수는?",
        "센텔라 앰플 리뷰 보여줘",
        "그 제품의 평균 평점은?",
        "선크림 리뷰는?",
        "앰플과 선크림 리뷰 비교하면?",
        "월별 리뷰 추이는?",
        "최근 3개월 리뷰 트렌드는?",
        "리뷰 수가 급증한 시기는?",
        "리뷰 수 대비 평점 관계는?",
        "국가별 리뷰 분포는?",
        "미국 리뷰가 가장 많지?",
        "아마존 리뷰 종합 분석해줘",
    ],
    "review_qoo10": [
        "큐텐 리뷰 총 몇 건이야?",
        "평균 평점은?",
        "별점 분포 보여줘",
        "가장 리뷰 많은 제품은?",
        "그 제품 리뷰 요약해줘",
        "최근 리뷰 10건 보여줘",
        "제품별 리뷰 수는?",
        "센텔라 앰플 리뷰는?",
        "선크림 리뷰는?",
        "비교하면?",
        "월별 리뷰 추이는?",
        "최근 리뷰 트렌드는?",
        "피부타입별 리뷰는?",
        "연령대별 리뷰는?",
        "재구매 의향 리뷰는?",
        "부정 리뷰 내용은?",
        "별점 1~2점 리뷰 보여줘",
        "리뷰 수가 가장 많은 달은?",
        "리뷰 길이 평균은?",
        "큐텐 리뷰 종합 분석해줘",
    ],
    "review_shopee": [
        "쇼피 리뷰 총 몇 건이야?",
        "국가별 리뷰 수는?",
        "인도네시아 리뷰는 몇 건?",
        "인도네시아 평균 평점은?",
        "가장 리뷰 많은 제품은?",
        "최근 리뷰 10건 보여줘",
        "별점 분포 보여줘",
        "5점 비율은?",
        "제품별 리뷰 수 TOP 5는?",
        "센텔라 앰플 리뷰 보여줘",
        "선크림 리뷰는?",
        "크림 리뷰는?",
        "가장 평점 높은 제품은?",
        "가장 평점 낮은 제품은?",
        "월별 리뷰 추이는?",
        "태국 리뷰는?",
        "인도네시아와 태국 비교하면?",
        "부정 리뷰 패턴은?",
        "리뷰에 가장 많이 언급된 키워드는?",
        "쇼피 리뷰 종합 분석해줘",
    ],
    "review_smartstore": [
        "스마트스토어 리뷰 총 몇 건이야?",
        "평균 평점은?",
        "별점 분포 보여줘",
        "가장 리뷰 많은 제품은?",
        "그 제품의 평균 평점은?",
        "최근 리뷰 10건 보여줘",
        "피부타입별 리뷰 수는?",
        "민감성 피부 리뷰는?",
        "피부고민별 리뷰는?",
        "잡티 관련 리뷰는?",
        "제품별 리뷰 수 TOP 5는?",
        "센텔라 앰플 리뷰는?",
        "선크림 리뷰는?",
        "월별 리뷰 추이는?",
        "재구매 관련 리뷰는?",
        "부정 리뷰 키워드는?",
        "연령대별 리뷰는?",
        "사진 리뷰 비율은?",
        "리뷰 반응(좋아요) 많은 리뷰는?",
        "스마트스토어 리뷰 종합 분석해줘",
    ],
    "meta_ads": [
        "메타 광고 총 몇 건이야?",
        "현재 활성 광고 수는?",
        "가장 최근 광고 보여줘",
        "페이지별 광고 수는?",
        "가장 광고 많은 페이지는?",
        "그 페이지 광고 리스트 보여줘",
        "광고 시작일 기준 최신 5건은?",
        "가장 오래된 광고는?",
        "월별 광고 게재 추이는?",
        "플랫폼별 광고 수는?",
        "페이스북 vs 인스타 비교하면?",
        "언어별 광고 분포는?",
        "한국어 광고는 몇 건?",
        "영어 광고는?",
        "광고 형식별 분포는?",
        "동영상 광고 비율은?",
        "이미지 광고 비율은?",
        "최근 종료된 광고는?",
        "광고 지역 타겟팅 분포는?",
        "메타 광고 종합 현황 보여줘",
    ],
}


def run_conversation(table_name, messages, chain_id):
    """Run a 20-message conversation chain."""
    results = []
    history = []  # Maintain conversation context

    for i, user_msg in enumerate(messages):
        msg_id = f"{chain_id}-{i+1:02d}"

        # Build message history (user messages + assistant responses)
        api_messages = []
        for h in history:
            api_messages.append({"role": "user", "content": h["user"]})
            api_messages.append({"role": "assistant", "content": h["assistant"]})
        api_messages.append({"role": "user", "content": user_msg})

        start = time.time()
        try:
            resp = requests.post(
                API_URL,
                json={"model": MODEL, "messages": api_messages, "stream": False},
                timeout=TIMEOUT,
            )
            elapsed = time.time() - start
            answer = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            alen = len(answer)

            if elapsed >= FAIL_THRESHOLD:
                status = "FAIL"
            elif alen < MIN_ANSWER_LEN:
                status = "EMPTY"
            elif elapsed >= WARN_THRESHOLD:
                status = "WARN"
            else:
                status = "OK"

            # Add to history for context
            history.append({"user": user_msg, "assistant": answer[:500]})

        except Exception as e:
            elapsed = time.time() - start
            status = "ERROR"
            answer = str(e)
            alen = 0
            history.append({"user": user_msg, "assistant": ""})

        result = {
            "id": msg_id,
            "turn": i + 1,
            "table": table_name,
            "query": user_msg,
            "status": status,
            "time": round(elapsed, 1),
            "answer_len": alen,
            "answer_preview": answer[:300].replace("\n", " "),
            "context_depth": len(history),
        }
        results.append(result)

        icon = {"OK": "+", "WARN": "!", "FAIL": "X", "ERROR": "E", "EMPTY": "0"}.get(status, "?")
        print(
            f"  [{icon}] {msg_id:12s} turn={i+1:2d} {elapsed:5.1f}s len={alen:5d} "
            f"[{table_name}] {user_msg[:40]}",
            flush=True,
        )

        time.sleep(1)  # Delay between calls

    return results


def analyze_context(results):
    """Analyze context coherence."""
    # Check for signs of lost context
    issues = []
    for r in results:
        preview = r.get("answer_preview", "").lower()
        # Signs of lost context
        if r["turn"] > 1:
            lost_phrases = [
                "무엇을 의미하시나요", "어떤 것을 말씀하시나요",
                "구체적으로 어떤", "어떤 데이터를 원하시나요",
                "질문이 명확하지", "이전 대화", "맥락을 파악",
            ]
            for phrase in lost_phrases:
                if phrase in preview:
                    issues.append(f"  [CONTEXT LOST] {r['id']}: turn={r['turn']} '{r['query'][:30]}' → lost context")
                    break

    return issues


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"Context Coherence Test — {len(CONVERSATION_CHAINS)} chains × {CHAIN_LENGTH} messages")
    print(f"  API: {API_URL}")
    print(f"  Start: {now}")

    all_results = []

    for table_name, messages in sorted(CONVERSATION_CHAINS.items()):
        chain_id = table_name[:2].upper()
        print(f"\n{'='*60}")
        print(f"Chain: {table_name} ({len(messages)} messages)")
        print(f"{'='*60}")

        chain_results = run_conversation(table_name, messages, chain_id)
        all_results.extend(chain_results)

        # Save per-chain
        chain_file = RESULTS_DIR / f"context_{table_name}.json"
        chain_file.write_text(
            json.dumps(chain_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Save all results
    RESULTS_FILE.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Summary
    from collections import Counter
    stats = Counter(r["status"] for r in all_results)
    total = len(all_results)
    ok = stats.get("OK", 0)
    warn = stats.get("WARN", 0)
    fail = stats.get("FAIL", 0) + stats.get("ERROR", 0) + stats.get("EMPTY", 0)
    avg_t = sum(r["time"] for r in all_results) / total
    pass_rate = (ok + warn) / total * 100

    # Turn-by-turn analysis
    turn_stats = {}
    for r in all_results:
        t = r["turn"]
        if t not in turn_stats:
            turn_stats[t] = {"ok": 0, "warn": 0, "fail": 0, "times": []}
        if r["status"] == "OK":
            turn_stats[t]["ok"] += 1
        elif r["status"] == "WARN":
            turn_stats[t]["warn"] += 1
        else:
            turn_stats[t]["fail"] += 1
        turn_stats[t]["times"].append(r["time"])

    # Context loss analysis
    context_issues = analyze_context(all_results)

    print(f"\n{'='*60}")
    print(f"CONTEXT COHERENCE TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Total: {total} messages ({len(CONVERSATION_CHAINS)} chains × {CHAIN_LENGTH})")
    print(f"  Pass: {pass_rate:.1f}% (OK={ok} WARN={warn} FAIL={fail})")
    print(f"  Avg latency: {avg_t:.1f}s")

    print(f"\n  Turn-by-turn performance:")
    print(f"  {'Turn':>4s}  {'OK':>4s}  {'WARN':>4s}  {'FAIL':>4s}  {'Avg(s)':>7s}")
    for t in sorted(turn_stats.keys()):
        s = turn_stats[t]
        avg = sum(s["times"]) / len(s["times"])
        print(f"  {t:4d}  {s['ok']:4d}  {s['warn']:4d}  {s['fail']:4d}  {avg:7.1f}")

    if context_issues:
        print(f"\n  Context Issues ({len(context_issues)}):")
        for issue in context_issues:
            print(issue)
    else:
        print(f"\n  No context loss detected!")

    print(f"\n  Results: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
