#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Upload 2026-03-12 update log to Notion."""

import sys
import time
import httpx
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.upload_to_notion import (
    get_token, heading3, paragraph, bulleted, callout, divider,
    toggle, table_block, append_blocks, append_blocks_get_ids,
    PAGE_ID, rich_text,
)


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def get_all_blocks(token):
    blocks = []
    url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100"
    while url:
        resp = httpx.get(url, headers=headers(token), timeout=30)
        data = resp.json()
        blocks.extend(data.get("results", []))
        if data.get("has_more"):
            url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100&start_cursor={data['next_cursor']}"
        else:
            url = None
    return blocks


def insert_after(token, after_id, children):
    """Insert children blocks after a specific block."""
    resp = httpx.patch(
        f"https://api.notion.com/v1/blocks/{PAGE_ID}/children",
        headers=headers(token),
        json={"children": children, "after": after_id},
        timeout=60,
    )
    return resp.status_code == 200, resp.text[:200]


def build_0312_toggle():
    """Build 2026-03-12 toggle with children."""
    children = [
        callout(
            "Meta Ads SQL 프롬프트 개선 (35건 검증)\n"
            "Frontend 정리 (모델 선택기 제거, Claude 브랜딩 제거)\n"
            "Code Review /simplify — 6건 수정",
            "🔧"
        ),
        heading3("1. Meta Ads SQL 프롬프트 개선"),
        paragraph("Google Sheet '시트1의 사본' 검증/정답쿼리 35건 분석 → 6개 공통 패턴 도출"),
        bulleted("집계 질문(국가별/유형별/전체)에 WHERE brand 조건 넣지 않도록 룰 추가"),
        bulleted("국가명 영어 필수: country_name = 'South Korea' (한국 X)"),
        bulleted("publisher_platform은 리스트 형태 → LIKE '%facebook%' 사용"),
        bulleted("ad_type은 공식계정/파트너십 정보만, 이미지/비디오는 snapshot 컬럼"),
        bulleted("날짜 정렬: start_date_formatted 컬럼 사용"),
        bulleted("활성/비활성 비교: GROUP BY is_active (brand별 X)"),
        bulleted("스키마 확장: 13 → 20 컬럼 (start_date_formatted, end_date_formatted 등)"),
        bulleted("예시 확장: 3 → 8개 (MT1-MT8), 검증된 정답 SQL 사용"),
        heading3("2. Frontend 정리"),
        bulleted("모델 선택기(select) → hidden input 변환 (단일 모델: skin1004-Analysis)"),
        bulleted("Claude 브랜딩 완전 제거 (SERVICE_ICONS, MODEL_LABELS)"),
        bulleted("Admin drawer: 그룹 CRUD, AD 사용자 관리, 비밀번호 변경 모달"),
        bulleted("Cache busting: v24 → v25"),
        heading3("3. CS Q&A Warmup 안정화"),
        bulleted("3회 재시도 로직 추가 (5초 간격)"),
        bulleted("import를 retry loop 밖으로 이동 (중복 import 방지)"),
        bulleted("동시 서버 시작 시 Google Sheets API 경합 문제 해결"),
        heading3("4. Notion 페이지 정리"),
        bulleted("raw 블록 정리: 109개 → 32개 블록"),
        bulleted("3/10, 3/11 업데이트를 접이식 toggle로 변환"),
        bulleted("삭제 + 삽입 스크립트 (notion_cleanup.py)"),
        heading3("5. Code Review (/simplify) — 6건 수정"),
        table_block([
            ["#", "항목", "변경"],
            ["1", "filterModelSelector 제거", "hidden input이므로 dead code"],
            ["2", "renderAdminGroups 블록 스코프", "불필요한 { } 래핑 제거"],
            ["3", "renderAdminDepts innerHTML", "+= 루프 → 문자열 빌드 후 1회 DOM 쓰기"],
            ["4", "renderAdminGroups gf innerHTML", "동일 패턴 최적화"],
            ["5", "escapeHtml 단일 패스", "5회 replace → 1회 regex + map"],
            ["6", "CS warmup import 호이스팅", "retry loop 밖으로 이동"],
        ]),
        paragraph("15 files changed, +1,538 / -469 lines. All API tests passed."),
    ]
    return toggle("2026-03-12 | Meta Ads SQL 개선 + Frontend 정리 + Code Review", children)


def main():
    token = get_token()
    print(f"Target page: {PAGE_ID}")

    # Find insertion point (after "새로운 업데이트" paragraph)
    blocks = get_all_blocks(token)
    print(f"Current blocks: {len(blocks)}")

    insert_after_id = None
    for i, b in enumerate(blocks):
        btype = b["type"]
        if btype == "paragraph":
            rt = b.get(btype, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in rt])
            if "새로운 업데이트" in text:
                insert_after_id = b["id"]
                print(f"Insert after block {i}: '{text[:50]}'")
                break

    if not insert_after_id:
        print("ERROR: Could not find insertion point ('새로운 업데이트')")
        print("Falling back to append at end of page...")
        toggle_block = build_0312_toggle()
        ok = append_blocks(token, PAGE_ID, [toggle_block])
        print(f"Append toggle: {'OK' if ok else 'FAILED'}")
    else:
        toggle_block = build_0312_toggle()
        ok, msg = insert_after(token, insert_after_id, [toggle_block])
        print(f"Insert 3/12 toggle: {'OK' if ok else 'FAILED'} {msg[:100] if not ok else ''}")

    # Verify
    time.sleep(1)
    blocks = get_all_blocks(token)
    print(f"\nFinal blocks: {len(blocks)}")
    for i, b in enumerate(blocks[:20]):
        btype = b["type"]
        text = ""
        if btype in ("heading_1", "heading_2", "heading_3", "paragraph", "callout", "toggle"):
            rt = b.get(btype, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in rt])[:60]
        elif btype == "divider":
            text = "---"
        print(f"  [{i:3d}] {btype:20s} | {text}")

    print("\nDone!")


if __name__ == "__main__":
    main()
