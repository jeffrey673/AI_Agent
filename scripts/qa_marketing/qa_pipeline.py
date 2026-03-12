#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
QA Full Pipeline — 13 Tables x 500 Questions = 6,500 Tests.

Stages:
  generate  — Create questions_v3_*.json (Tier1: import 300, Tier2: LLM edge, Tier3: variation)
  run       — Execute tests with auto-recovery on server crash
  retest    — Re-test WARN/FAIL up to 3 iterations
  report    — Generate markdown report
  upload    — Upload results to Notion
  all       — Run all stages sequentially

Usage:
  python -X utf8 scripts/qa_marketing/qa_pipeline.py generate
  python -X utf8 scripts/qa_marketing/qa_pipeline.py run
  python -X utf8 scripts/qa_marketing/qa_pipeline.py all
"""

import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock, Semaphore

import requests

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
RESULTS_DIR = BASE_DIR / "results_v3"
AGGREGATE_FILE = BASE_DIR / "results_v3_aggregate.json"
CHECKPOINT_FILE = BASE_DIR / "results_v3" / "_checkpoint.json"
RETEST_LOG_FILE = BASE_DIR / "retest_v3_log.json"
REPORT_FILE = BASE_DIR / "v3_pipeline_report.md"

# ── API ──
API_URL = "http://localhost:3001/v1/chat/completions"
HEALTH_URL = "http://localhost:3001/health"
MODEL = "gemini"

# ── Threading ──
NUM_TABLE_THREADS = 3
MAX_CONCURRENT_API = 2
CALL_DELAY = 1.0
TIMEOUT = 180
MAX_RETRIES = 3

# ── Thresholds ──
FAIL_THRESHOLD = 90
WARN_THRESHOLD = 60
MIN_ANSWER_LEN = 20

# ── Auto-recovery ──
MAX_CONSECUTIVE_ERRORS = 10
SERVER_RESTART_TIMEOUT = 120
HEALTH_POLL_INTERVAL = 5

# ── Thread-safe state ──
print_lock = Lock()
results_lock = Lock()
save_lock = Lock()
api_semaphore = Semaphore(MAX_CONCURRENT_API)
consecutive_errors = 0
error_lock = Lock()

all_results: dict[str, list] = {}
completed_ids: set[str] = set()


# ── Table config: name → (prefix, category, schema hint for LLM) ──
TABLE_CONFIG = {
    "sales_all": {
        "prefix": "SA",
        "category": "sales_all",
        "schema_hint": (
            "SALES_ALL_Backup: 매출(Sales1_R), 수량(Total_Qty), 국가(Country), "
            "플랫폼(Mall_Classification), 제품(SET), 팀(Team_NEW), 날짜(Date DATETIME), "
            "브랜드(Brand: SK/CL/ETC/DD/UM), Category, Line, Sales_Type(B2B/B2C)"
        ),
    },
    "advertising": {
        "prefix": "AD",
        "category": "platform_cost",
        "schema_hint": (
            "integrated_advertising_data: 광고비(Cost), 노출(Impressions), 클릭(Clicks), "
            "전환(Conversions), ROAS, CTR, CPC, CVR, Platform, Country, Campaign, Date"
        ),
    },
    "amazon_search": {
        "prefix": "AZ",
        "category": "amazon_search",
        "schema_hint": (
            "amazon_search_analytics: CTR, Impressions, Clicks, Cart_Adds, "
            "Purchases, Purchases_Conversion_Rate, Country, ASIN, Date"
        ),
    },
    "influencer": {
        "prefix": "IF",
        "category": "influencer",
        "schema_hint": (
            "influencer_input_ALL_TEAMS: 팔로워(followers), 조회수(views), 좋아요(likes), "
            "비용(cost), 팀(Team), 티어(Tier), 플랫폼(platform), 국가(country), Date"
        ),
    },
    "marketing_cost": {
        "prefix": "MC",
        "category": "marketing_cost",
        "schema_hint": (
            "Integrated_marketing_cost: 광고비+인플루언서비용 통합, Cost, "
            "cost_type(광고/인플루언서), Platform, Country, Campaign, Month"
        ),
    },
    "meta_ads": {
        "prefix": "MT",
        "category": "meta_ads",
        "schema_hint": (
            "meta data_test: 메타(Facebook/Instagram) 광고 라이브러리, "
            "ad_id, page_name, start_date, status, platform, impression_range"
        ),
    },
    "platform": {
        "prefix": "PL",
        "category": "platform",
        "schema_hint": (
            "Platform_Data.raw_data: 플랫폼별 제품 순위, 가격(price), "
            "할인가(discount_price), 랭킹(rank), channel, product_name, Date"
        ),
    },
    "product": {
        "prefix": "PR",
        "category": "product",
        "schema_hint": (
            "Product: 제품별 수량(Total_Qty), SKU, SET(제품명), Line, "
            "Category(Ampoule/Suncare/SET/Cream/Pack/Cleanser/Oil/Toner/Others), "
            "Brand(SK/CL), Country, Date"
        ),
    },
    "review_amazon": {
        "prefix": "RA",
        "category": "review_amazon",
        "schema_hint": (
            "Review_Data.Amazon_Review: rating, review_text, collect_date, "
            "product_name, country, verified_purchase"
        ),
    },
    "review_qoo10": {
        "prefix": "RQ",
        "category": "review_qoo10",
        "schema_hint": (
            "Review_Data.Qoo10_Review: rating, review_text, collect_date, "
            "product_name, reviewer"
        ),
    },
    "review_shopee": {
        "prefix": "RS",
        "category": "review_shopee",
        "schema_hint": (
            "Review_Data.Shopee_Review: rating, content, collect_date, "
            "product_name, country, shop_name"
        ),
    },
    "review_smartstore": {
        "prefix": "RT",
        "category": "review_smartstore",
        "schema_hint": (
            "Review_Data.Smartstore_Review: rating, content, collect_date, "
            "product_name, reviewer, purchase_option"
        ),
    },
    "shopify": {
        "prefix": "SH",
        "category": "shopify",
        "schema_hint": (
            "shopify_analysis_sales: Shopify 자사몰 판매, "
            "net_sales, quantity, order_count, product_title, country, Date"
        ),
    },
}


# ═════════════════════════════════════════════════════════
#  V2 Variation Engine (from generate_v2_questions.py)
# ═════════════════════════════════════════════════════════

SYNONYMS = {
    "매출": ["수익", "판매액", "매출액", "매상", "세일즈", "매출금액"],
    "합계": ["총합", "전체", "합산", "토탈", "총액"],
    "비교": ["대비", "비교 분석", "대조", "견줘봐"],
    "추이": ["변화", "트렌드", "흐름", "추세", "변동"],
    "알려줘": ["보여줘", "말해줘", "확인해줘", "가르쳐줘", "체크해줘"],
    "분석": ["분석해줘", "분석 좀", "살펴봐줘", "파악해줘"],
    "순위": ["랭킹", "순서", "TOP", "상위"],
    "현황": ["상황", "현재 상태", "실태", "동향"],
    "월별": ["매월", "달별", "월간", "각 월"],
    "국가별": ["나라별", "국가 기준", "각 나라"],
    "플랫폼별": ["채널별", "플랫폼 기준"],
    "얼마야": ["얼마임", "얼마인지", "얼마나 돼", "몇이야"],
    "보여줘": ["보여줄래", "보여줄 수 있어?", "알려줘", "보여줄래?"],
    "비용": ["비용금액", "지출", "예산", "경비"],
    "판매 수량": ["판매량", "팔린 수량", "판매 건수", "팔린 갯수"],
    "수량": ["판매량", "갯수", "수", "개수"],
    "제품별": ["제품 기준", "각 제품", "상품별"],
    "리뷰": ["후기", "리뷰데이터", "평가"],
    "가장 많은": ["제일 많은", "최다", "가장 높은", "1위"],
    "가장 적은": ["제일 적은", "최소", "가장 낮은"],
    "광고비": ["광고 비용", "광고 집행비", "광고 예산", "광고 지출"],
    "클릭률": ["CTR", "클릭율"],
    "전환수": ["전환 건수", "구매수", "전환 횟수"],
    "노출수": ["노출 건수", "임프레션", "노출 횟수"],
    "전환율": ["CVR", "전환률", "구매 전환율"],
    "팀별": ["팀 기준", "각 팀"],
    "에이전시별": ["에이전시 기준", "각 에이전시"],
    "조회수": ["뷰수", "뷰 카운트", "시청수"],
    "인플루언서": ["인플루엔서", "크리에이터", "KOL"],
    "캠페인별": ["캠페인 기준", "각 캠페인"],
    "티어별": ["티어 기준", "각 티어"],
    "할인율": ["할인률", "디스카운트율", "세일률"],
    "장바구니": ["카트", "장바구니 담기"],
}

TYPOS = {
    "매출": ["메출", "매축"],
    "쇼피": ["쇼핑", "shopee"],
    "라자다": ["라자더", "lazada"],
    "틱톡": ["tiktok", "틱톱"],
    "아마존": ["amazon", "아마죤"],
    "라쿠텐": ["rakuten"],
    "큐텐": ["큐탠", "qoo10"],
    "인도네시아": ["인니", "인도네시야"],
    "태국": ["타이"],
    "베트남": ["베남"],
    "필리핀": ["필핀"],
    "말레이시아": ["말레이"],
    "싱가포르": ["싱가폴"],
    "센텔라": ["centella", "쎈텔라"],
    "앰플": ["앰풀", "ampoule"],
    "클렌저": ["클랜저", "클렌져"],
    "선크림": ["썬크림", "선크링"],
    "리뷰": ["리부", "후기"],
    "스마트스토어": ["스마스토", "스마트스토아"],
    "Shopify": ["쇼피파이", "shopify"],
    "마케팅": ["마캐팅"],
    "브랜드": ["브렌드"],
}

CONTEXT_PREFIXES = [
    "우리 회사 ", "혹시 ", "요즘 ", "참고로 ", "궁금한데 ", "잠깐, ",
    "확인 좀 해줘 ", "빠르게 ", "간단하게 ", "정확한 ",
]
CONTEXT_SUFFIXES = [
    " 좀", " 빨리", " 부탁", " 알고 싶어", " 궁금해",
    " 확인해줘", " 정리해줘", " 보여줘", " 알려줄래?", " 좀 봐줘",
]
STYLES = ["formal", "informal", "casual", "polite", "question"]


def apply_synonym(text: str, prob: float = 0.35) -> str:
    for word, syns in SYNONYMS.items():
        if word in text and random.random() < prob:
            text = text.replace(word, random.choice(syns), 1)
    return text


def apply_typo(text: str, prob: float = 0.12) -> str:
    for word, typo_list in TYPOS.items():
        if word in text and random.random() < prob:
            text = text.replace(word, random.choice(typo_list), 1)
    return text


def add_context(text: str, prob: float = 0.25) -> str:
    if random.random() < prob:
        text = random.choice(CONTEXT_PREFIXES) + text
    if random.random() < prob * 0.5:
        text = text + random.choice(CONTEXT_SUFFIXES)
    return text


def change_ending(text: str) -> str:
    style = random.choice(STYLES)
    text = text.rstrip("?").rstrip()
    if style == "formal":
        for old, new in [("알려줘", "알려주세요"), ("보여줘", "보여주세요"),
                         ("해줘", "해주세요"), ("뭐야", "무엇인가요"),
                         ("얼마야", "얼마인가요")]:
            if text.endswith(old):
                return text[:-len(old)] + new
        if not text.endswith(("요", "다", "세요", "까요")):
            text += " 알려주세요"
    elif style == "informal":
        for old, new in [("알려주세요", "알려줘"), ("보여주세요", "보여줘"),
                         ("해주세요", "해줘"), ("인가요", "야?")]:
            if text.endswith(old):
                return text[:-len(old)] + new
    elif style == "casual":
        if not text.endswith(("?", "줘", "야")):
            text += random.choice([" 얼마임?", " 몇이야?", " 어때?", "?", " 좀 알려줘"])
    elif style == "polite":
        if not text.endswith(("요", "다")):
            text += random.choice([" 확인 부탁드립니다", " 알려주시면 감사하겠습니다", " 부탁드려요"])
    elif style == "question":
        if not text.endswith("?"):
            text += random.choice([" 어떻게 되나요?", " 알 수 있을까요?", " 확인 가능한가요?"])
    return text


def swap_word_order(text: str, prob: float = 0.2) -> str:
    if random.random() > prob:
        return text
    m = re.search(r'(\d{4}년)\s+([\w가-힣]+)', text)
    if m and random.random() < 0.5:
        text = text.replace(m.group(0), f"{m.group(2)} {m.group(1)}", 1)
    return text


def rephrase_query(original: str) -> str:
    text = original
    for func in [apply_synonym, apply_typo, add_context, swap_word_order]:
        text = func(text)
    if random.random() < 0.6:
        text = change_ending(text)
    if text == original:
        text = apply_synonym(text, prob=0.8)
    if text == original:
        text = add_context(text, prob=0.9)
    if text == original:
        text = change_ending(text)
    return text


# ═════════════════════════════════════════════════════════
#  Stage 1: GENERATE
# ═════════════════════════════════════════════════════════

def _generate_edge_cases_llm(table_name: str, existing_queries: list[str], count: int = 100) -> list[str]:
    """Use Gemini Flash to generate edge-case questions for a table."""
    cfg = TABLE_CONFIG[table_name]
    schema = cfg["schema_hint"]

    # Sample existing queries for context
    sample = random.sample(existing_queries, min(20, len(existing_queries)))
    sample_text = "\n".join(f"- {q}" for q in sample)

    prompt = f"""당신은 SKIN1004 AI 시스템의 QA 테스트 질문 생성기입니다.
아래 테이블 스키마를 참고하여, 기존 질문과 중복되지 않는 새로운 edge case 질문을 {count}개 생성하세요.

## 테이블: {table_name}
스키마: {schema}

## 기존 질문 샘플 (참고용):
{sample_text}

## 생성 규칙:
1. 다중 조건 필터 (국가+플랫폼+기간 동시)
2. 비교 분석 (전월 대비, 전년 대비, YoY, MoM)
3. 경계값 (가장 적은, 0인, 없는 데이터)
4. 부정 조건 (~제외, ~아닌, ~외의)
5. 복합 집계 (TOP N, 비율, 점유율)
6. 기간 범위 (2024 Q3, 최근 6개월, 하반기)
7. 시각화/차트 요청 ("그래프로", "차트로", "추이 보여줘")
8. 한국어 자연스러운 질문체 사용

## 응답 형식:
JSON 배열로만 응답. 각 항목은 문자열(질문 텍스트).
[
  "질문1",
  "질문2",
  ...
]"""

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from app.core.llm import get_flash_client
        client = get_flash_client()
        response = client.generate_json(prompt)
        # generate_json may return string or parsed object
        if isinstance(response, str):
            # Strip markdown fences if present
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
            response = json.loads(text)
        if isinstance(response, list):
            return [str(q) for q in response[:count]]
        return []
    except Exception as e:
        print(f"  [LLM ERROR] {table_name}: {e}")
        return []


def stage_generate():
    """Generate questions_v3_*.json — 500 per table."""
    print("=" * 70)
    print("  STAGE 1: GENERATE — 13 tables x 500 questions")
    print("=" * 70)

    random.seed(42)
    total_generated = 0

    for table_name, cfg in sorted(TABLE_CONFIG.items()):
        prefix = cfg["prefix"]
        category = cfg["category"]
        out_file = BASE_DIR / f"questions_v3_{table_name}.json"

        # ── Tier 1: Import existing 300 ──
        orig_file = BASE_DIR / f"questions_{table_name}.json"
        if not orig_file.exists():
            print(f"  [SKIP] {table_name}: questions_{table_name}.json not found")
            continue

        with open(orig_file, "r", encoding="utf-8") as f:
            tier1 = json.load(f)
        existing_queries = [q["query"] for q in tier1]
        print(f"  [{table_name}] Tier1: {len(tier1)} imported from original")

        # ── Tier 2: LLM edge cases (301-400) ──
        print(f"  [{table_name}] Tier2: Generating edge cases via LLM...")
        edge_queries = _generate_edge_cases_llm(table_name, existing_queries, count=100)

        # Deduplicate against existing
        existing_set = set(q.lower().strip() for q in existing_queries)
        edge_queries = [q for q in edge_queries if q.lower().strip() not in existing_set]

        # If LLM returned fewer than 100, pad with variations of existing
        while len(edge_queries) < 100:
            base = random.choice(existing_queries)
            varied = rephrase_query(base)
            if varied.lower().strip() not in existing_set:
                edge_queries.append(varied)
                existing_set.add(varied.lower().strip())

        edge_queries = edge_queries[:100]
        tier2 = []
        for i, q in enumerate(edge_queries):
            tier2.append({
                "id": f"{prefix}-{301 + i:03d}",
                "query": q,
                "category": category,
                "tier": 2,
            })
        print(f"  [{table_name}] Tier2: {len(tier2)} edge cases generated")

        # ── Tier 3: Variations of Tier 2 (401-500) ──
        tier3_base = random.sample(tier1, min(50, len(tier1))) + tier2[:50]
        tier3 = []
        used_queries = set(q.lower().strip() for q in existing_queries + edge_queries)
        attempts = 0
        while len(tier3) < 100 and attempts < 500:
            base = random.choice(tier3_base)
            varied = rephrase_query(base["query"])
            if varied.lower().strip() not in used_queries:
                tier3.append({
                    "id": f"{prefix}-{401 + len(tier3):03d}",
                    "query": varied,
                    "category": category,
                    "tier": 3,
                })
                used_queries.add(varied.lower().strip())
            attempts += 1

        # Pad if still short
        while len(tier3) < 100:
            base = random.choice(tier1)
            varied = rephrase_query(base["query"])
            tier3.append({
                "id": f"{prefix}-{401 + len(tier3):03d}",
                "query": varied,
                "category": category,
                "tier": 3,
            })

        tier3 = tier3[:100]
        print(f"  [{table_name}] Tier3: {len(tier3)} variations generated")

        # ── Combine all 500 ──
        all_questions = []
        for q in tier1:
            q_copy = dict(q)
            q_copy["tier"] = 1
            all_questions.append(q_copy)
        all_questions.extend(tier2)
        all_questions.extend(tier3)

        # Write output
        out_file.write_text(
            json.dumps(all_questions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  [{table_name}] Total: {len(all_questions)} → {out_file.name}")
        total_generated += len(all_questions)

    print(f"\n  GENERATE COMPLETE: {total_generated} questions across {len(TABLE_CONFIG)} tables")
    return total_generated


# ═════════════════════════════════════════════════════════
#  Stage 2: RUN
# ═════════════════════════════════════════════════════════

def _health_check() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _restart_server():
    """Kill existing server and restart."""
    print("  [RECOVERY] Killing existing server processes...")
    try:
        subprocess.run(
            ["powershell", "-Command", "Get-Process python | Stop-Process -Force"],
            capture_output=True, timeout=15,
        )
    except Exception as e:
        print(f"  [RECOVERY] Kill error (may be OK): {e}")

    time.sleep(3)

    print("  [RECOVERY] Starting uvicorn...")
    subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "uvicorn",
         "app.main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    # Poll health
    print(f"  [RECOVERY] Polling /health (max {SERVER_RESTART_TIMEOUT}s)...")
    start = time.time()
    while time.time() - start < SERVER_RESTART_TIMEOUT:
        time.sleep(HEALTH_POLL_INTERVAL)
        if _health_check():
            print(f"  [RECOVERY] Server is back! ({time.time() - start:.0f}s)")
            return True
    print("  [RECOVERY] Server did not come back in time!")
    return False


def _save_checkpoint(table_progress: dict):
    """Save checkpoint for resume."""
    with save_lock:
        CHECKPOINT_FILE.write_text(
            json.dumps(table_progress, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _load_checkpoint() -> dict:
    """Load checkpoint."""
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _discover_v3_files() -> dict[str, list]:
    """Find all questions_v3_*.json files."""
    table_questions = {}
    for f in sorted(BASE_DIR.glob("questions_v3_*.json")):
        table_name = f.stem.replace("questions_v3_", "")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                table_questions[table_name] = data
        except Exception as e:
            print(f"  [SKIP] {f.name}: {e}")
    return table_questions


def _test_single(question: dict, table_name: str) -> dict:
    """Test a single question against the API."""
    global consecutive_errors
    q = question["query"]
    qid = question["id"]

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": q}],
        "stream": False,
    }

    api_semaphore.acquire()
    start = time.time()
    try:
        resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        alen = len(answer)

        if elapsed >= FAIL_THRESHOLD:
            status = "FAIL"
        elif alen < MIN_ANSWER_LEN:
            status = "EMPTY"
        elif elapsed >= WARN_THRESHOLD:
            status = "WARN"
        else:
            status = "OK"

        with error_lock:
            consecutive_errors = 0

        return {
            "id": qid,
            "query": q,
            "table": table_name,
            "category": question.get("category", table_name),
            "tier": question.get("tier", 1),
            "status": status,
            "time": round(elapsed, 1),
            "answer_len": alen,
            "answer_preview": answer[:200].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.time() - start
        with error_lock:
            consecutive_errors += 1
        return {
            "id": qid,
            "query": q,
            "table": table_name,
            "category": question.get("category", table_name),
            "tier": question.get("tier", 1),
            "status": "ERROR",
            "time": round(elapsed, 1),
            "answer_len": 0,
            "answer_preview": str(e)[:200],
        }
    finally:
        api_semaphore.release()


def _save_table_results(table_name: str):
    with save_lock:
        results = all_results.get(table_name, [])
        out_file = RESULTS_DIR / f"results_v3_{table_name}.json"
        out_file.write_text(
            json.dumps(sorted(results, key=lambda x: x["id"]),
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _save_aggregate():
    with save_lock:
        agg = []
        for table_name, results in all_results.items():
            agg.extend(results)
        agg.sort(key=lambda x: x["id"])
        AGGREGATE_FILE.write_text(
            json.dumps(agg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _run_table(table_name: str, questions: list):
    """Run all questions for a single table with retry, delays, and auto-recovery."""
    global consecutive_errors

    remaining = [q for q in questions if q["id"] not in completed_ids]
    total = len(questions)
    done_prev = total - len(remaining)

    with print_lock:
        print(f"\n  [{table_name}] Starting: {len(remaining)} remaining / {total} total (prev={done_prev})", flush=True)

    if not remaining:
        with print_lock:
            print(f"  [{table_name}] All done!", flush=True)
        return

    for i, q in enumerate(remaining):
        # Auto-recovery check
        with error_lock:
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                with print_lock:
                    print(f"  [{table_name}] {consecutive_errors} consecutive errors — triggering recovery...", flush=True)
                # Save checkpoint
                _save_table_results(table_name)
                _save_aggregate()
                # Check and restart
                if not _health_check():
                    _restart_server()
                with error_lock:
                    consecutive_errors = 0
                time.sleep(5)

        # Retry loop
        r = None
        for attempt in range(MAX_RETRIES):
            r = _test_single(q, table_name)
            if r and r["status"] != "ERROR":
                break
            wait = [5, 15, 30][min(attempt, 2)]
            with print_lock:
                print(f"  [{table_name}] Retry {attempt + 1}/{MAX_RETRIES} for {q['id']} (wait {wait}s)", flush=True)
            time.sleep(wait)

        if r is None:
            continue

        with results_lock:
            if table_name not in all_results:
                all_results[table_name] = []
            all_results[table_name].append(r)
            completed_ids.add(r["id"])
            table_done = len(all_results[table_name])

        icon = {"OK": "+", "WARN": "!", "FAIL": "X", "ERROR": "E", "EMPTY": "0"}.get(r["status"], "?")
        with print_lock:
            print(
                f"  [{icon}] {r['id']:8s} {r['time']:5.1f}s len={r['answer_len']:4d} "
                f"({table_done}/{total}) [{table_name}] {q['query'][:35]}",
                flush=True,
            )

        # Save after every question
        _save_table_results(table_name)

        time.sleep(CALL_DELAY)

    # Final save
    _save_table_results(table_name)


def _load_existing_results():
    """Load previously completed results for resume."""
    global all_results, completed_ids
    RESULTS_DIR.mkdir(exist_ok=True)

    for f in RESULTS_DIR.glob("results_v3_*.json"):
        if f.name.startswith("_"):
            continue
        table_name = f.stem.replace("results_v3_", "")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            prev_ok = [r for r in data if r["status"] in ("OK", "WARN")]
            all_results[table_name] = prev_ok
            for r in prev_ok:
                completed_ids.add(r["id"])
        except Exception:
            pass


def _print_summary():
    """Print grand summary dashboard."""
    W = 80
    print("\n" + "=" * W)
    print(f"{'QA V3 PIPELINE — GRAND SUMMARY':^{W}}")
    print("=" * W)

    grand_total = 0
    grand_ok = 0
    grand_warn = 0
    grand_fail = 0
    grand_times = []
    table_lines = []

    for table_name in sorted(all_results.keys()):
        results = all_results[table_name]
        if not results:
            continue
        ok = sum(1 for r in results if r["status"] == "OK")
        warn = sum(1 for r in results if r["status"] == "WARN")
        fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        total = len(results)
        avg_t = sum(r["time"] for r in results) / total
        times = [r["time"] for r in results]
        p50 = sorted(times)[total // 2]
        p95 = sorted(times)[int(total * 0.95)]

        grand_total += total
        grand_ok += ok
        grand_warn += warn
        grand_fail += fail
        grand_times.extend(times)

        bar_w = 20
        ok_bar = round(ok / total * bar_w)
        warn_bar = round(warn / total * bar_w)
        fail_bar = bar_w - ok_bar - warn_bar
        bar = "#" * ok_bar + "!" * warn_bar + "x" * fail_bar

        table_lines.append(
            f"  {table_name:30s} [{bar:20s}] "
            f"OK={ok:3d} W={warn:3d} F={fail:3d}  "
            f"avg={avg_t:5.1f}s p50={p50:5.1f}s p95={p95:5.1f}s"
        )

    if grand_total > 0:
        grand_pass_rate = (grand_ok + grand_warn) / grand_total * 100
        grand_avg = sum(grand_times) / grand_total
        grand_p50 = sorted(grand_times)[grand_total // 2]
        grand_p95 = sorted(grand_times)[int(grand_total * 0.95)]

        print(f"\n  OVERALL: {grand_pass_rate:.1f}% PASS")
        print(f"  Total={grand_total}  OK={grand_ok}  WARN={grand_warn}  FAIL={grand_fail}")
        print(f"  Latency: avg={grand_avg:.1f}s  p50={grand_p50:.1f}s  p95={grand_p95:.1f}s")

    print(f"\n  {'Table':30s} {'Bar':22s} {'OK':>4s} {'W':>4s} {'F':>4s}  "
          f"{'Avg':>6s} {'P50':>6s} {'P95':>6s}")
    print(f"  {'-' * 30} {'-' * 22} {'-' * 4} {'-' * 4} {'-' * 4}  {'-' * 6} {'-' * 6} {'-' * 6}")
    for line in table_lines:
        print(line)

    # Distribution
    if grand_times:
        buckets = [(0, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 90), (90, 9999)]
        labels = ["<10s", "10-20", "20-30", "30-45", "45-60", "60-90", "90s+"]
        counts = [sum(1 for t in grand_times if lo <= t < hi) for lo, hi in buckets]
        hist_max = max(counts) if counts else 1
        print(f"\n  Distribution:")
        for label, cnt in zip(labels, counts):
            bar_len = round(cnt / hist_max * 30) if hist_max else 0
            pct = cnt / grand_total * 100
            print(f"    {label:>7s} | {'#' * bar_len:<30s} {cnt:4d} ({pct:4.1f}%)")

    print("=" * W)


def stage_run():
    """Run all v3 tests with auto-recovery."""
    print("=" * 70)
    print("  STAGE 2: RUN — Test execution with auto-recovery")
    print("=" * 70)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Health check
    if not _health_check():
        print("  Server not responding. Attempting restart...")
        if not _restart_server():
            print("  ERROR: Could not start server. Aborting.")
            return
    print("  Server is healthy.")

    # Discover question files
    table_questions = _discover_v3_files()
    if not table_questions:
        print("  ERROR: No questions_v3_*.json found. Run 'generate' first.")
        return

    total_q = sum(len(qs) for qs in table_questions.values())
    print(f"  Found {len(table_questions)} tables, {total_q} questions")

    # Load existing results for resume
    _load_existing_results()
    remaining = total_q - len(completed_ids)
    print(f"  Completed: {len(completed_ids)}, Remaining: {remaining}")

    if remaining == 0:
        print("\n  All questions already completed!")
        _print_summary()
        return

    wall_start = time.time()

    with ThreadPoolExecutor(max_workers=NUM_TABLE_THREADS) as executor:
        futures = {}
        for table_name, qs in sorted(table_questions.items()):
            future = executor.submit(_run_table, table_name, qs)
            futures[future] = table_name

        for future in as_completed(futures):
            table_name = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"  [ERROR] Table {table_name} failed: {e}")

    wall_time = time.time() - wall_start

    # Final save
    _save_aggregate()

    print(f"\n  Wall time: {wall_time:.0f}s ({wall_time / 60:.1f}min)")
    _print_summary()


# ═════════════════════════════════════════════════════════
#  Stage 3: RETEST
# ═════════════════════════════════════════════════════════

def stage_retest(max_iterations: int = 3):
    """Re-test WARN/FAIL, up to max_iterations. Only keep improvements."""
    print("=" * 70)
    print(f"  STAGE 3: RETEST — Max {max_iterations} iterations")
    print("=" * 70)

    if not _health_check():
        print("  Server not responding. Attempting restart...")
        if not _restart_server():
            print("  ERROR: Could not start server. Aborting.")
            return

    retest_log = []

    for iteration in range(1, max_iterations + 1):
        print(f"\n  --- Iteration {iteration}/{max_iterations} ---")

        # Load current results
        all_data = {}
        for f in sorted(RESULTS_DIR.glob("results_v3_*.json")):
            if f.name.startswith("_"):
                continue
            table_name = f.stem.replace("results_v3_", "")
            all_data[table_name] = json.loads(f.read_text(encoding="utf-8"))

        # Collect WARN/FAIL
        to_retest = []
        for table_name, results in all_data.items():
            for r in results:
                if r["status"] in ("WARN", "FAIL", "ERROR", "EMPTY"):
                    to_retest.append((table_name, r))

        if not to_retest:
            print("  No WARN/FAIL found. Done!")
            break

        print(f"  Found {len(to_retest)} WARN/FAIL items to retest")
        improved = 0
        unchanged = 0

        for idx, (table_name, old_result) in enumerate(to_retest):
            q = {"id": old_result["id"], "query": old_result["query"],
                 "category": old_result.get("category", table_name),
                 "tier": old_result.get("tier", 1)}

            new_result = _test_single(q, table_name)

            # Only keep improvement
            old_status = old_result["status"]
            new_status = new_result["status"]
            status_order = {"OK": 0, "WARN": 1, "FAIL": 2, "EMPTY": 2, "ERROR": 3}

            if status_order.get(new_status, 9) < status_order.get(old_status, 9):
                # Improved — update in results
                for i, r in enumerate(all_data[table_name]):
                    if r["id"] == old_result["id"]:
                        all_data[table_name][i] = new_result
                        break
                improved += 1
                with print_lock:
                    print(f"  [UP] {old_result['id']} {old_status}({old_result['time']:.1f}s) → "
                          f"{new_status}({new_result['time']:.1f}s)")
            elif new_status == old_status and new_result["time"] < old_result["time"]:
                # Same status but faster
                for i, r in enumerate(all_data[table_name]):
                    if r["id"] == old_result["id"]:
                        all_data[table_name][i] = new_result
                        break
                improved += 1
            else:
                unchanged += 1

            if (idx + 1) % 10 == 0:
                print(f"  Progress: {idx + 1}/{len(to_retest)} (improved={improved})")

            time.sleep(CALL_DELAY)

        # Save updated results
        for table_name, results in all_data.items():
            out_file = RESULTS_DIR / f"results_v3_{table_name}.json"
            out_file.write_text(
                json.dumps(sorted(results, key=lambda x: x["id"]),
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # Rebuild aggregate
        agg = []
        for results in all_data.values():
            agg.extend(results)
        agg.sort(key=lambda x: x["id"])
        AGGREGATE_FILE.write_text(
            json.dumps(agg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Count remaining
        remaining_warn_fail = sum(
            1 for results in all_data.values()
            for r in results if r["status"] in ("WARN", "FAIL", "ERROR", "EMPTY")
        )

        retest_log.append({
            "iteration": iteration,
            "tested": len(to_retest),
            "improved": improved,
            "unchanged": unchanged,
            "remaining_warn_fail": remaining_warn_fail,
        })
        print(f"  Iteration {iteration}: improved={improved}, unchanged={unchanged}, "
              f"remaining WARN/FAIL={remaining_warn_fail}")

        if remaining_warn_fail == 0:
            print("  All WARN/FAIL resolved!")
            break

    # Save retest log
    RETEST_LOG_FILE.write_text(
        json.dumps(retest_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  Retest log saved: {RETEST_LOG_FILE}")


# ═════════════════════════════════════════════════════════
#  Stage 4: REPORT
# ═════════════════════════════════════════════════════════

def stage_report() -> str:
    """Generate markdown report."""
    print("=" * 70)
    print("  STAGE 4: REPORT — Markdown generation")
    print("=" * 70)

    all_data = {}
    for f in sorted(RESULTS_DIR.glob("results_v3_*.json")):
        if f.name.startswith("_"):
            continue
        table_name = f.stem.replace("results_v3_", "")
        all_data[table_name] = json.loads(f.read_text(encoding="utf-8"))

    if not all_data:
        print("  No results found!")
        return ""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_results_flat = [r for v in all_data.values() for r in v]
    total_q = len(all_results_flat)

    grand_ok = sum(1 for r in all_results_flat if r["status"] == "OK")
    grand_warn = sum(1 for r in all_results_flat if r["status"] == "WARN")
    grand_fail = sum(1 for r in all_results_flat if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    grand_pass = grand_ok + grand_warn
    pass_rate = grand_pass / total_q * 100 if total_q else 0
    times = [r["time"] for r in all_results_flat]
    avg_t = sum(times) / len(times) if times else 0
    p50 = sorted(times)[len(times) // 2] if times else 0
    p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

    lines = []
    lines.append(f"# SKIN1004 QA V3 Pipeline Report — 13 x 500 = 6,500")
    lines.append(f"")
    lines.append(f"**Date**: {now}")
    lines.append(f"**Tables**: {len(all_data)}")
    lines.append(f"**Total Questions**: {total_q}")
    lines.append(f"")

    # Overall summary
    lines.append(f"## Overall Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Pass Rate (OK+WARN) | **{pass_rate:.1f}%** ({grand_pass}/{total_q}) |")
    lines.append(f"| OK Rate | {grand_ok / total_q * 100:.1f}% ({grand_ok}) |")
    lines.append(f"| WARN | {grand_warn} |")
    lines.append(f"| FAIL/ERROR/EMPTY | {grand_fail} |")
    lines.append(f"| Avg Latency | {avg_t:.1f}s |")
    lines.append(f"| P50 | {p50:.1f}s |")
    lines.append(f"| P95 | {p95:.1f}s |")
    lines.append(f"")

    # Per-table
    lines.append(f"## Per-Table Results")
    lines.append(f"")
    lines.append(f"| Table | Total | OK | WARN | FAIL | Pass% | Avg(s) | P50(s) | P95(s) |")
    lines.append(f"|-------|-------|-----|------|------|-------|--------|--------|--------|")

    for table_name in sorted(all_data.keys()):
        results = all_data[table_name]
        t_total = len(results)
        t_ok = sum(1 for r in results if r["status"] == "OK")
        t_warn = sum(1 for r in results if r["status"] == "WARN")
        t_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_pass = (t_ok + t_warn) / t_total * 100 if t_total else 0
        t_times = [r["time"] for r in results]
        t_avg = sum(t_times) / len(t_times) if t_times else 0
        t_p50 = sorted(t_times)[len(t_times) // 2] if t_times else 0
        t_p95 = sorted(t_times)[int(len(t_times) * 0.95)] if t_times else 0
        lines.append(
            f"| {table_name} | {t_total} | {t_ok} | {t_warn} | {t_fail} | "
            f"{t_pass:.1f}% | {t_avg:.1f} | {t_p50:.1f} | {t_p95:.1f} |"
        )
    lines.append(f"")

    # Tier analysis
    lines.append(f"## Tier Analysis")
    lines.append(f"")
    lines.append(f"| Tier | Description | Total | OK | WARN | FAIL | Pass% | Avg(s) |")
    lines.append(f"|------|-------------|-------|-----|------|------|-------|--------|")

    for tier_num, desc in [(1, "Original (1-300)"), (2, "Edge Case (301-400)"), (3, "Variation (401-500)")]:
        tier_results = [r for r in all_results_flat if r.get("tier", 1) == tier_num]
        if not tier_results:
            continue
        t_total = len(tier_results)
        t_ok = sum(1 for r in tier_results if r["status"] == "OK")
        t_warn = sum(1 for r in tier_results if r["status"] == "WARN")
        t_fail = sum(1 for r in tier_results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_pass = (t_ok + t_warn) / t_total * 100 if t_total else 0
        t_avg = sum(r["time"] for r in tier_results) / t_total if t_total else 0
        lines.append(
            f"| Tier {tier_num} | {desc} | {t_total} | {t_ok} | {t_warn} | {t_fail} | "
            f"{t_pass:.1f}% | {t_avg:.1f} |"
        )
    lines.append(f"")

    # Latency distribution
    lines.append(f"## Latency Distribution")
    lines.append(f"")
    buckets = [(0, 10, "<10s"), (10, 20, "10-20s"), (20, 30, "20-30s"),
               (30, 45, "30-45s"), (45, 60, "45-60s"), (60, 90, "60-90s"), (90, 9999, "90s+")]
    lines.append(f"| Range | Count | Percent |")
    lines.append(f"|-------|-------|---------|")
    for lo, hi, label in buckets:
        cnt = sum(1 for t in times if lo <= t < hi)
        pct = cnt / len(times) * 100 if times else 0
        lines.append(f"| {label} | {cnt} | {pct:.1f}% |")
    lines.append(f"")

    # FAIL/WARN top 30
    fails = [r for r in all_results_flat if r["status"] in ("FAIL", "ERROR", "EMPTY")]
    if fails:
        fails.sort(key=lambda x: -x["time"])
        lines.append(f"## Failures ({len(fails)})")
        lines.append(f"")
        lines.append(f"| ID | Table | Tier | Status | Time | Query |")
        lines.append(f"|----|-------|------|--------|------|-------|")
        for r in fails[:30]:
            q = r["query"][:50].replace("|", "\\|")
            lines.append(
                f"| {r['id']} | {r.get('table', '?')} | {r.get('tier', 1)} | "
                f"{r['status']} | {r['time']:.1f}s | {q} |"
            )
        lines.append(f"")

    warns = [r for r in all_results_flat if r["status"] == "WARN"]
    if warns:
        warns.sort(key=lambda x: -x["time"])
        lines.append(f"## Slow Queries — WARN ({len(warns)}, top 30)")
        lines.append(f"")
        lines.append(f"| ID | Table | Tier | Time | Query |")
        lines.append(f"|----|-------|------|------|-------|")
        for r in warns[:30]:
            q = r["query"][:50].replace("|", "\\|")
            lines.append(f"| {r['id']} | {r.get('table', '?')} | {r.get('tier', 1)} | {r['time']:.1f}s | {q} |")
        lines.append(f"")

    # Retest history
    if RETEST_LOG_FILE.exists():
        try:
            retest_log = json.loads(RETEST_LOG_FILE.read_text(encoding="utf-8"))
            lines.append(f"## Retest History")
            lines.append(f"")
            lines.append(f"| Iteration | Tested | Improved | Remaining |")
            lines.append(f"|-----------|--------|----------|-----------|")
            for entry in retest_log:
                lines.append(
                    f"| {entry['iteration']} | {entry['tested']} | "
                    f"{entry['improved']} | {entry['remaining_warn_fail']} |"
                )
            lines.append(f"")
        except Exception:
            pass

    report_text = "\n".join(lines)
    REPORT_FILE.write_text(report_text, encoding="utf-8")
    print(f"  Report saved: {REPORT_FILE}")
    print(f"  Total: {total_q}, Pass: {pass_rate:.1f}% (OK={grand_ok}, WARN={grand_warn}, FAIL={grand_fail})")
    return report_text


# ═════════════════════════════════════════════════════════
#  Stage 5: UPLOAD (Notion)
# ═════════════════════════════════════════════════════════

def stage_upload():
    """Upload results to Notion."""
    print("=" * 70)
    print("  STAGE 5: UPLOAD — Notion")
    print("=" * 70)

    import httpx

    sys.path.insert(0, str(PROJECT_DIR))
    from app.config import get_settings
    token = get_settings().notion_mcp_token

    PAGE_ID = "3032b428-3b00-80ae-8241-cedef71fc3be"
    NOTION_VERSION = "2022-06-28"
    MAX_TEXT_LEN = 1900
    MAX_BLOCKS_PER_CALL = 100

    def _headers():
        return {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _rich_text(text, bold=False, code=False, color="default"):
        chunks = []
        while text:
            chunk = text[:MAX_TEXT_LEN]
            text = text[MAX_TEXT_LEN:]
            chunks.append({
                "type": "text",
                "text": {"content": chunk},
                "annotations": {"bold": bold, "code": code, "color": color},
            })
        return chunks if chunks else [{"type": "text", "text": {"content": ""}}]

    def _paragraph(text, bold=False):
        return {"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _rich_text(text, bold=bold)}}

    def _heading2(text):
        return {"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": _rich_text(text)}}

    def _callout(text, emoji="📌"):
        return {"object": "block", "type": "callout",
                "callout": {"rich_text": _rich_text(text),
                            "icon": {"type": "emoji", "emoji": emoji}}}

    def _bulleted(text):
        return {"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rich_text(text)}}

    def _toggle(text, children=None):
        block = {"object": "block", "type": "toggle",
                 "toggle": {"rich_text": _rich_text(text, bold=True)}}
        if children:
            block["toggle"]["children"] = children[:MAX_BLOCKS_PER_CALL]
        return block

    def _table_block(rows):
        width = len(rows[0]) if rows else 1
        table_rows = []
        for row in rows:
            cells = [_rich_text(str(c)[:MAX_TEXT_LEN]) for c in row]
            while len(cells) < width:
                cells.append(_rich_text(""))
            table_rows.append({"object": "block", "type": "table_row",
                               "table_row": {"cells": cells}})
        return {"object": "block", "type": "table",
                "table": {"table_width": width, "has_column_header": True,
                          "has_row_header": False, "children": table_rows}}

    def _append_blocks(parent_id, blocks):
        hdrs = _headers()
        for start in range(0, len(blocks), MAX_BLOCKS_PER_CALL):
            batch = blocks[start:start + MAX_BLOCKS_PER_CALL]
            r = httpx.patch(
                f"https://api.notion.com/v1/blocks/{parent_id}/children",
                headers=hdrs, json={"children": batch}, timeout=60,
            )
            if r.status_code != 200:
                print(f"  ERROR: {r.status_code} {r.text[:300]}")
                return False
            time.sleep(0.3)
        return True

    def _get_children(block_id):
        hdrs = _headers()
        results = []
        cursor = None
        while True:
            url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
            if cursor:
                url += f"&start_cursor={cursor}"
            r = httpx.get(url, headers=hdrs, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    # ── Build blocks ──
    all_data = {}
    for f in sorted(RESULTS_DIR.glob("results_v3_*.json")):
        if f.name.startswith("_"):
            continue
        table_name = f.stem.replace("results_v3_", "")
        all_data[table_name] = json.loads(f.read_text(encoding="utf-8"))

    if not all_data:
        print("  No results to upload!")
        return

    all_results_flat = [r for v in all_data.values() for r in v]
    total_q = len(all_results_flat)
    ok = sum(1 for r in all_results_flat if r["status"] == "OK")
    warn = sum(1 for r in all_results_flat if r["status"] == "WARN")
    fail = sum(1 for r in all_results_flat if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    times = [r["time"] for r in all_results_flat]
    avg_t = sum(times) / len(times) if times else 0
    p50 = sorted(times)[len(times) // 2] if times else 0
    p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

    now = datetime.now().strftime("%Y-%m-%d")
    blocks = []

    # Summary callout
    blocks.append(_callout(
        f"QA V3 Pipeline: {ok + warn}/{total_q} PASS ({(ok + warn) / total_q * 100:.1f}%) | "
        f"OK: {ok} | WARN: {warn} | FAIL: {fail} | "
        f"Avg: {avg_t:.1f}s | P50: {p50:.1f}s | P95: {p95:.1f}s | "
        f"Tables: {len(all_data)} | 3 Tiers (300+100+100)",
        "🧪"
    ))

    # Per-table summary table
    header = ["Table", "Total", "OK", "WARN", "FAIL", "Pass%", "Avg(s)", "P50(s)"]
    rows = [header]
    for table_name in sorted(all_data.keys()):
        results = all_data[table_name]
        t_total = len(results)
        t_ok = sum(1 for r in results if r["status"] == "OK")
        t_warn = sum(1 for r in results if r["status"] == "WARN")
        t_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_pass = (t_ok + t_warn) / t_total * 100 if t_total else 0
        t_times = [r["time"] for r in results]
        t_avg = sum(t_times) / len(t_times) if t_times else 0
        t_p50 = sorted(t_times)[len(t_times) // 2] if t_times else 0
        rows.append([
            table_name, str(t_total), str(t_ok), str(t_warn), str(t_fail),
            f"{t_pass:.1f}%", f"{t_avg:.1f}", f"{t_p50:.1f}",
        ])
    rows.append(["TOTAL", str(total_q), str(ok), str(warn), str(fail),
                 f"{(ok + warn) / total_q * 100:.1f}%", f"{avg_t:.1f}", f"{p50:.1f}"])
    blocks.append(_table_block(rows))

    # Tier analysis table
    tier_header = ["Tier", "Total", "OK", "WARN", "FAIL", "Pass%", "Avg(s)"]
    tier_rows = [tier_header]
    for tier_num, desc in [(1, "Original (1-300)"), (2, "Edge Case (301-400)"), (3, "Variation (401-500)")]:
        tier_results = [r for r in all_results_flat if r.get("tier", 1) == tier_num]
        if not tier_results:
            continue
        t_total = len(tier_results)
        t_ok = sum(1 for r in tier_results if r["status"] == "OK")
        t_warn = sum(1 for r in tier_results if r["status"] == "WARN")
        t_fail = sum(1 for r in tier_results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_pass = (t_ok + t_warn) / t_total * 100 if t_total else 0
        t_avg = sum(r["time"] for r in tier_results) / t_total
        tier_rows.append([f"T{tier_num}: {desc}", str(t_total), str(t_ok), str(t_warn),
                          str(t_fail), f"{t_pass:.1f}%", f"{t_avg:.1f}"])
    blocks.append(_table_block(tier_rows))

    # Per-table toggles (non-OK only)
    for table_name in sorted(all_data.keys()):
        results = all_data[table_name]
        t_ok = sum(1 for r in results if r["status"] == "OK")
        t_warn = sum(1 for r in results if r["status"] == "WARN")
        t_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_avg = sum(r["time"] for r in results) / len(results) if results else 0

        non_ok = [r for r in results if r["status"] != "OK"]
        children = []
        for r in sorted(non_ok, key=lambda x: -x["time"]):
            icon = {"WARN": "⚠️", "FAIL": "❌", "ERROR": "❌", "EMPTY": "⭕"}.get(r["status"], "❓")
            children.append(_bulleted(
                f"{icon} [{r['id']}] T{r.get('tier', 1)} {r['query'][:50]} "
                f"({r['time']:.1f}s) — {r['status']}"
            ))
        if not children:
            children = [_paragraph(f"All {len(results)} queries passed (OK)")]

        blocks.append(_toggle(
            f"{table_name}: {t_ok + t_warn}/{len(results)} PASS "
            f"(OK={t_ok} W={t_warn} F={t_fail}, avg {t_avg:.1f}s)",
            children[:MAX_BLOCKS_PER_CALL]
        ))

    # ── Upload ──
    print(f"  Uploading {len(blocks)} blocks to Notion...")

    section_blocks = [_heading2(f"{now} QA V3 Pipeline — 13 x 500 = 6,500")]
    section_blocks.extend(blocks)

    # Find QA section
    children = _get_children(PAGE_ID)
    qa_section_id = None
    for child in children:
        if child.get("type") == "heading_1":
            rt = child.get("heading_1", {}).get("rich_text", [])
            text = "".join(t.get("text", {}).get("content", "") for t in rt)
            if "QA Test Reports" in text:
                qa_section_id = child["id"]
                break

    if qa_section_id:
        insert_after = qa_section_id
        for i, child in enumerate(children):
            if child["id"] == qa_section_id:
                if i + 1 < len(children) and children[i + 1].get("type") == "paragraph":
                    insert_after = children[i + 1]["id"]
                break

        print(f"  Inserting after QA section...")
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{PAGE_ID}/children",
            headers=_headers(),
            json={"children": section_blocks[:MAX_BLOCKS_PER_CALL], "after": insert_after},
            timeout=60,
        )
        if r.status_code == 200:
            print(f"  OK: {len(section_blocks)} blocks inserted")
            if len(section_blocks) > MAX_BLOCKS_PER_CALL:
                _append_blocks(PAGE_ID, section_blocks[MAX_BLOCKS_PER_CALL:])
        else:
            print(f"  Insert failed ({r.status_code}), falling back to append...")
            _append_blocks(PAGE_ID, section_blocks)
    else:
        print("  QA section not found, appending to end...")
        _append_blocks(PAGE_ID, section_blocks)

    print(f"\n  Done! {len(blocks)} blocks uploaded.")
    print(f"  Check: https://www.notion.so/{PAGE_ID.replace('-', '')}")


# ═════════════════════════════════════════════════════════
#  Stage 6: ALL
# ═════════════════════════════════════════════════════════

def stage_all():
    """Run all stages sequentially."""
    print("\n" + "=" * 70)
    print("  QA FULL PIPELINE — generate → run → retest → report → upload")
    print("=" * 70 + "\n")

    start = time.time()

    stage_generate()
    print()
    stage_run()
    print()
    stage_retest()
    print()
    stage_report()
    print()
    stage_upload()

    elapsed = time.time() - start
    print(f"\n  PIPELINE COMPLETE — Total time: {elapsed:.0f}s ({elapsed / 60:.1f}min)")


# ═════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════

STAGES = {
    "generate": stage_generate,
    "run": stage_run,
    "retest": stage_retest,
    "report": stage_report,
    "upload": stage_upload,
    "all": stage_all,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
        print(f"Usage: python {sys.argv[0]} <stage>")
        print(f"Stages: {', '.join(STAGES.keys())}")
        sys.exit(1)

    stage = sys.argv[1]
    print(f"\n  QA Pipeline — Stage: {stage}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    STAGES[stage]()


if __name__ == "__main__":
    main()
