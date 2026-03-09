#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate V2 variation questions for Marketing QA testing.
Reads original question files and creates rephrased versions with:
- Different Korean phrasing styles (formal/informal)
- Typos/abbreviations
- Word order swaps
- Synonyms
- Additional context words
"""

import json
import random
import os
import re

random.seed(42)  # reproducible

# ─── Rephrasing helpers ───

STYLES = [
    "formal",      # ~해주세요, ~알려주세요, ~인가요?
    "informal",    # ~해줘, ~알려줘, ~뭐야?
    "casual",      # ~임?, ~얼마임?, ~좀
    "polite",      # ~부탁드립니다, ~확인 부탁드려요
    "question",    # ~인지 알 수 있을까요?, ~어떻게 되나요?
]

CONTEXT_PREFIXES = [
    "우리 회사 ", "혹시 ", "요즘 ", "참고로 ", "궁금한데 ", "잠깐, ",
    "확인 좀 해줘 ", "빠르게 ", "간단하게 ", "정확한 ",
]

CONTEXT_SUFFIXES = [
    " 좀", " 빨리", " 부탁", " 알고 싶어", " 궁금해",
    " 확인해줘", " 정리해줘", " 보여줘", " 알려줄래?", " 좀 봐줘",
]

# Synonym maps
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

# Typo map (common Korean typos)
TYPOS = {
    "매출": ["메출", "매축", "매출"],
    "쇼피": ["쇼핑", "쇼피", "shopee"],
    "라자다": ["라자더", "라자다", "lazada"],
    "틱톡": ["틱톡", "tiktok", "틱톱"],
    "아마존": ["아마존", "amazon", "아마죤"],
    "라쿠텐": ["라쿠텐", "rakuten"],
    "큐텐": ["큐탠", "큐텐", "qoo10"],
    "인도네시아": ["인니", "인도네시아", "인도네시야"],
    "태국": ["태국", "타이"],
    "베트남": ["베트남", "베남"],
    "필리핀": ["필핀", "필리핀"],
    "말레이시아": ["말레이", "말레이시아"],
    "싱가포르": ["싱가폴", "싱가포르"],
    "센텔라": ["센텔라", "centella", "쎈텔라"],
    "앰플": ["앰풀", "앰플", "ampoule"],
    "히알루시카": ["히알루시카", "히알루"],
    "프로바이오시카": ["프로바이오", "프로바이오시카"],
    "클렌저": ["클렌저", "클랜저", "클렌져"],
    "토너": ["토너", "토나"],
    "크림": ["크림", "크링"],
    "선크림": ["선크림", "썬크림", "선크링"],
    "광고": ["광고", "광고"],
    "리뷰": ["리뷰", "리부", "후기"],
    "스마트스토어": ["스마트스토어", "스마스토", "스마트스토아"],
    "Shopify": ["쇼피파이", "Shopify", "shopify"],
    "마케팅": ["마케팅", "마캐팅"],
    "브랜드": ["브랜드", "브렌드"],
}


def apply_typo(text, prob=0.15):
    """Randomly apply typos to known words."""
    for word, typo_list in TYPOS.items():
        if word in text and random.random() < prob:
            replacement = random.choice(typo_list)
            text = text.replace(word, replacement, 1)
    return text


def apply_synonym(text, prob=0.3):
    """Randomly apply synonyms."""
    for word, syns in SYNONYMS.items():
        if word in text and random.random() < prob:
            replacement = random.choice(syns)
            text = text.replace(word, replacement, 1)
    return text


def add_context(text, prob=0.25):
    """Add context words like '우리 회사', '요즘'."""
    if random.random() < prob:
        prefix = random.choice(CONTEXT_PREFIXES)
        text = prefix + text
    if random.random() < prob * 0.5:
        suffix = random.choice(CONTEXT_SUFFIXES)
        text = text + suffix
    return text


def change_ending(text):
    """Change sentence ending style."""
    style = random.choice(STYLES)

    # Remove existing endings to re-apply
    text = text.rstrip("?").rstrip()

    if style == "formal":
        endings = [
            ("알려줘", "알려주세요"),
            ("보여줘", "보여주세요"),
            ("해줘", "해주세요"),
            ("몇 개야", "몇 개인가요"),
            ("뭐야", "무엇인가요"),
            ("있어", "있나요"),
            ("얼마야", "얼마인가요"),
            ("어디야", "어디인가요"),
        ]
        for old, new in endings:
            if text.endswith(old):
                text = text[:-len(old)] + new
                return text
        if not text.endswith(("요", "다", "세요", "까요")):
            text += " 알려주세요"
    elif style == "informal":
        endings = [
            ("알려주세요", "알려줘"),
            ("보여주세요", "보여줘"),
            ("해주세요", "해줘"),
            ("인가요", "야?"),
        ]
        for old, new in endings:
            if text.endswith(old):
                text = text[:-len(old)] + new
                return text
    elif style == "casual":
        if not text.endswith(("?", "줘", "야")):
            casual_endings = [" 얼마임?", " 몇이야?", " 어때?", "?", " 좀 알려줘"]
            text += random.choice(casual_endings)
    elif style == "polite":
        if not text.endswith(("요", "다")):
            polite_endings = [" 확인 부탁드립니다", " 알려주시면 감사하겠습니다", " 부탁드려요"]
            text += random.choice(polite_endings)
    elif style == "question":
        if not text.endswith("?"):
            q_endings = [" 어떻게 되나요?", " 알 수 있을까요?", " 확인 가능한가요?", "은 어떤가요?"]
            text += random.choice(q_endings)

    return text


def swap_word_order(text, prob=0.2):
    """Swap word order for some phrases."""
    if random.random() > prob:
        return text

    # Pattern: "2025년 인도네시아" <-> "인도네시아 2025년"
    year_country = re.search(r'(\d{4}년)\s+([\w가-힣]+)', text)
    if year_country and random.random() < 0.5:
        old = year_country.group(0)
        new = f"{year_country.group(2)} {year_country.group(1)}"
        text = text.replace(old, new, 1)

    # Pattern: "매출 인도네시아" <-> "인도네시아 매출"
    return text


def rephrase_query(original_query, idx):
    """Apply multiple rephrasing strategies."""
    text = original_query

    # Apply transformations in random order with probabilities
    transforms = [
        (apply_synonym, 0.35),
        (apply_typo, 0.12),
        (add_context, 0.2),
        (swap_word_order, 0.2),
    ]

    random.shuffle(transforms)

    for func, _ in transforms:
        text = func(text)

    # Always try to change the ending style for variety
    if random.random() < 0.6:
        text = change_ending(text)

    # If unchanged, force at least one modification
    if text == original_query:
        # Force synonym or context
        text = apply_synonym(text, prob=0.8)
        if text == original_query:
            text = add_context(text, prob=0.9)
        if text == original_query:
            text = change_ending(text)

    return text


def generate_v2_file(input_path, output_path):
    """Generate v2 variation file from original."""
    with open(input_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    v2_questions = []
    for i, q in enumerate(questions):
        new_q = {
            "id": f"V2_{q['id']}",
            "query": rephrase_query(q["query"], i),
            "category": q["category"]
        }
        v2_questions.append(new_q)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(v2_questions, f, ensure_ascii=False, indent=2)

    print(f"  Generated {len(v2_questions)} questions -> {os.path.basename(output_path)}")
    return len(v2_questions)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Find all original question files (exclude v2 files)
    files = sorted([
        f for f in os.listdir(base_dir)
        if f.startswith("questions_") and f.endswith(".json") and "_v2_" not in f
    ])

    print(f"Found {len(files)} original question files:\n")

    total = 0
    for fname in files:
        # Extract table name: questions_sales_all.json -> sales_all
        table_name = fname.replace("questions_", "").replace(".json", "")
        input_path = os.path.join(base_dir, fname)
        output_path = os.path.join(base_dir, f"questions_v2_{table_name}.json")

        print(f"Processing: {fname}")
        count = generate_v2_file(input_path, output_path)
        total += count

    print(f"\nTotal: {total} variation questions generated across {len(files)} files.")


if __name__ == "__main__":
    main()
