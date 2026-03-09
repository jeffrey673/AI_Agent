"""Upload SKIN1004 AI System Architecture Report to Notion.

Generates a comprehensive technical architecture report covering:
- System classification (Compound AI System / LangGraph Multi-Agent)
- Architecture diagram (Orchestrator-Worker pattern)
- Agent details (SQL, Notion, GWS, CS, Direct, Multi)
- Tech stack & LLM strategy
- Safety system & performance metrics
- Data flow & routing logic

Usage:
  python scripts/upload_architecture_report.py
"""
import os
import sys
import time
import httpx
import re
from datetime import datetime

# ── Configuration ──
PAGE_ID = "3032b428-3b00-80ae-8241-cedef71fc3be"
NOTION_VERSION = "2022-06-28"
MAX_TEXT_LEN = 1900
MAX_BLOCKS_PER_CALL = 100
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_token():
    sys.path.insert(0, BASE_DIR)
    from app.config import get_settings
    return get_settings().notion_mcp_token


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def rich_text(text: str, bold=False, code=False, color="default") -> list:
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


def paragraph(text: str, bold=False, color="default") -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text(text, bold=bold, color=color)},
    }


def heading1(text: str) -> dict:
    return {"object": "block", "type": "heading_1", "heading_1": {"rich_text": rich_text(text)}}


def heading2(text: str) -> dict:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": rich_text(text)}}


def heading3(text: str) -> dict:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": rich_text(text)}}


def bulleted(text: str, bold=False) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text(text, bold=bold)},
    }


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def callout(text: str, emoji: str = "📌") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": rich_text(text),
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


def toggle(text: str, children: list = None) -> dict:
    block = {
        "object": "block",
        "type": "toggle",
        "toggle": {"rich_text": rich_text(text, bold=True)},
    }
    if children:
        block["toggle"]["children"] = children[:MAX_BLOCKS_PER_CALL]
    return block


def table_block(rows: list) -> dict:
    width = len(rows[0]) if rows else 1
    table_rows = []
    for row in rows:
        cells = []
        for cell in row:
            cells.append(rich_text(str(cell)[:MAX_TEXT_LEN]))
        while len(cells) < width:
            cells.append(rich_text(""))
        table_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": cells},
        })
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def append_blocks(token: str, parent_id: str, blocks: list):
    hdrs = headers(token)
    for start in range(0, len(blocks), MAX_BLOCKS_PER_CALL):
        batch = blocks[start:start + MAX_BLOCKS_PER_CALL]
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{parent_id}/children",
            headers=hdrs,
            json={"children": batch},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"  ERROR: {r.status_code} {r.text[:300]}")
            return False
        time.sleep(0.3)
    return True


def append_blocks_get_ids(token: str, parent_id: str, blocks: list) -> list:
    hdrs = headers(token)
    ids = []
    for start in range(0, len(blocks), MAX_BLOCKS_PER_CALL):
        batch = blocks[start:start + MAX_BLOCKS_PER_CALL]
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{parent_id}/children",
            headers=hdrs,
            json={"children": batch},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"  ERROR: {r.status_code} {r.text[:300]}")
            continue
        for result in r.json().get("results", []):
            ids.append(result["id"])
        time.sleep(0.3)
    return ids


# ── Report Content ──

def build_report() -> list:
    """Build the full architecture report as Notion blocks."""
    today = datetime.now().strftime("%Y-%m-%d")
    blocks = []

    # ── Title & Meta ──
    blocks.append(heading1(f"SKIN1004 Enterprise AI - System Architecture Report"))
    blocks.append(callout(
        f"작성일: {today} | Version: v7.2 Production | "
        f"분류: LangGraph Multi-Agent Compound AI System",
        "🏗️"
    ))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 1: System Classification
    # ══════════════════════════════════════════════
    blocks.append(heading2("1. 시스템 분류 (System Classification)"))
    blocks.append(paragraph(
        "본 시스템은 단순 RAG나 LangChain 체인이 아닌, "
        "LangGraph 기반 Multi-Agent Compound AI System입니다. "
        "Stanford/Berkeley에서 제안한 Compound AI System 범주에 해당하며, "
        "여러 컴포넌트(LLM + 검색 + 도구 + 에이전트)를 조합한 복합 시스템입니다."
    ))
    blocks.append(paragraph(""))

    blocks.append(table_block([
        ["기술 요소", "시스템 내 적용", "설명"],
        ["LangGraph", "Orchestrator, SQL Agent",
         "상태 기반 그래프 워크플로우 — 조건부 분기, 루프, 상태 관리가 가능한 DAG 구조"],
        ["Agentic RAG", "RAG Agent (설계됨)",
         "Adaptive + Corrective + Self-Reflective RAG — 관련성 평가 및 재검색"],
        ["Text-to-SQL (NL2SQL)", "SQL Agent",
         "자연어 → BigQuery SQL 변환 → 실행 → 자연어 답변 생성"],
        ["Tool-Augmented LLM", "Notion / GWS / CS Agent",
         "LLM이 외부 도구(API)를 호출하여 작업을 수행하는 에이전트"],
        ["ReAct Agent", "GWS Agent",
         "Reasoning + Acting 패턴 — LLM이 도구 호출을 자율적으로 결정"],
        ["LangChain", "하위 의존성",
         "langchain-core, langchain-anthropic을 라이브러리로 사용 (체인 방식 아님)"],
    ]))
    blocks.append(paragraph(""))

    blocks.append(heading3("명칭 정의"))
    blocks.append(bulleted("공식 명칭: LangGraph Multi-Agent Compound AI System"))
    blocks.append(bulleted("기술 발표용: LangGraph 기반 Multi-Agent Orchestration System"))
    blocks.append(bulleted("간략 표현: 멀티 에이전트 AI 시스템 (LangGraph)"))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 2: Architecture Overview
    # ══════════════════════════════════════════════
    blocks.append(heading2("2. 아키텍처 개요 (Architecture Overview)"))
    blocks.append(heading3("2.1 Orchestrator-Worker 패턴"))
    blocks.append(paragraph(
        "중앙 Orchestrator가 사용자 질문의 의도를 분석(키워드 우선 + LLM 폴백)하고, "
        "적절한 Sub Agent(Worker)에게 작업을 위임하는 패턴입니다. "
        "각 에이전트는 독립적으로 동작하며, 실패 시 fallback 경로가 있습니다."
    ))
    blocks.append(paragraph(""))

    blocks.append(heading3("2.2 시스템 흐름도"))
    blocks.append(callout(
        "User Query → FastAPI (port 3000) → Orchestrator → "
        "Keyword Classify → [LLM Classify if ambiguous] → "
        "Route to Sub Agent → Response + Chart (parallel) → SSE Stream → Frontend",
        "🔄"
    ))
    blocks.append(paragraph(""))

    blocks.append(heading3("2.3 라우팅 경로 (6 Routes)"))
    blocks.append(table_block([
        ["Route", "트리거 키워드 예시", "처리 에이전트", "사용 LLM"],
        ["bigquery", "매출, 수량, 주문, 광고, 인플루언서, 리뷰",
         "SQL Agent → BigQuery", "Flash (SQL생성) + Pro/Claude (답변)"],
        ["notion", "노션, 정책, 매뉴얼, 가이드",
         "Notion Agent → Notion API", "Flash (검색) + Pro/Claude (답변)"],
        ["gws", "메일, 드라이브, 캘린더, 일정",
         "GWS Agent → Google Workspace", "Claude ReAct Agent"],
        ["cs", "성분, 사용법, 비건, 제품문의, 피부",
         "CS Agent → Google Sheets", "Flash (검색) + Pro/Claude (합성)"],
        ["multi", "매출 + 원인/트렌드/영향 (복합)",
         "BQ + Web Search 병렬", "Flash (BQ) + Pro/Claude (종합)"],
        ["direct", "일반 질문, 인사, 실시간 정보",
         "Direct LLM", "Pro / Claude"],
    ]))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 3: Agent Details
    # ══════════════════════════════════════════════
    blocks.append(heading2("3. 에이전트 상세 (Agent Details)"))

    # SQL Agent
    blocks.append(heading3("3.1 SQL Agent (Text-to-SQL)"))
    blocks.append(paragraph(
        "LangGraph StateGraph 기반. 자연어 질문을 BigQuery SQL로 변환하여 실행합니다."
    ))
    blocks.append(table_block([
        ["노드", "기능", "비고"],
        ["generate_sql", "자연어 → BigQuery SQL 변환", "Gemini Flash, lazy schema loading"],
        ["validate_sql", "SQL 보안 검증", "SELECT ONLY, 테이블 화이트리스트, 금지 키워드 차단"],
        ["execute_sql", "BigQuery 실행", "timeout 45s, max 1000 rows"],
        ["format_answer", "결과 → 자연어 답변 + 차트", "Pro/Claude, 병렬 차트 생성"],
    ]))
    blocks.append(bulleted("SQL 안전장치: INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE 차단"))
    blocks.append(bulleted("Lazy Schema: 쿼리 키워드 기반으로 관련 테이블 스키마만 포함 (50KB→15-25KB)"))
    blocks.append(bulleted("지원 테이블: SALES_ALL_Backup, Product, 마케팅 7개, 리뷰 4개, 인플루언서, Shopify"))
    blocks.append(bulleted("실패 시 Direct LLM 자동 폴백 (에러 대신 안내 메시지)"))
    blocks.append(paragraph(""))

    # Notion Agent
    blocks.append(heading3("3.2 Notion Agent (Document Search)"))
    blocks.append(paragraph(
        "Allowlist 기반 직접 API 호출. MCP 의존성 제거, 10개 사전 정의 페이지/DB만 검색합니다."
    ))
    blocks.append(bulleted("v6.2: 병렬 페이지 읽기 (asyncio.gather), 병렬 시트 읽기"))
    blocks.append(bulleted("Flash LLM으로 검색 키워드 추출 및 페이지 선택"))
    blocks.append(bulleted("Content 제한: 페이지당 15,000자, 최대 200블록"))
    blocks.append(paragraph(""))

    # GWS Agent
    blocks.append(heading3("3.3 GWS Agent (Google Workspace)"))
    blocks.append(paragraph(
        "per-user OAuth2 인증 기반 ReAct Agent. "
        "Claude Sonnet이 Gmail/Drive/Calendar API 도구를 자율적으로 호출합니다."
    ))
    blocks.append(bulleted("langchain_anthropic ChatAnthropic + langgraph create_react_agent"))
    blocks.append(bulleted("도구: search_gmail, search_drive, list_calendar_events"))
    blocks.append(bulleted("timeout 120s, recursion_limit=10 (4-5회 도구 호출)"))
    blocks.append(paragraph(""))

    # CS Agent
    blocks.append(heading3("3.4 CS Agent (Customer Service)"))
    blocks.append(paragraph(
        "Google Spreadsheet 13탭 ~1,100개 CS Q&A를 메모리에 캐싱. "
        "키워드 매칭 + word overlap 스코어링 + LLM 합성으로 CS 답변을 생성합니다."
    ))
    blocks.append(bulleted("브랜드: SKIN1004, COMMONLABS, ZOMBIE BEAUTY"))
    blocks.append(bulleted("카테고리: 제품문의, 비건인증, 공통FAQ, 제품별CS, 사용루틴"))
    blocks.append(bulleted("Flash LLM으로 빠른 답변 합성 (40s→~10s)"))
    blocks.append(paragraph(""))

    # Multi Agent
    blocks.append(heading3("3.5 Multi Agent (복합 분석)"))
    blocks.append(paragraph(
        "내부 데이터(BigQuery) + 외부 정보(Web Search)를 병렬로 수집하여 "
        "종합 분석 답변을 생성합니다."
    ))
    blocks.append(bulleted("ThreadPoolExecutor로 BQ + Tavily Web Search 동시 실행"))
    blocks.append(bulleted("Flash로 쿼리 재작성 (data-only BQ 쿼리 분리)"))
    blocks.append(bulleted("Google Search Grounding (Gemini generate_with_search)"))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 4: LLM Strategy
    # ══════════════════════════════════════════════
    blocks.append(heading2("4. LLM 전략 (Dual LLM + Tiered)"))
    blocks.append(paragraph(
        "사용자 선택 모델(Pro/Claude)로 최종 답변을 생성하고, "
        "내부 작업(SQL 생성, 라우팅, 차트, CS, Notion)은 Gemini Flash로 처리하여 "
        "비용과 속도를 최적화합니다."
    ))
    blocks.append(table_block([
        ["모델", "용도", "특징"],
        ["Gemini 3 Pro Preview", "사용자 대화 (기본)", "범용 답변, 한국어 우수"],
        ["Claude Opus 4.6 / Sonnet 4.6", "사용자 대화 (선택)", "복잡 추론, GWS ReAct"],
        ["Gemini 2.5 Flash", "내부 작업 전용",
         "SQL 생성, 라우팅 분류, 차트 설정, CS 검색, Notion 페이지 선택"],
    ]))
    blocks.append(bulleted("모델 전환: 프론트엔드 모델 피커로 실시간 전환"))
    blocks.append(bulleted("Admin: 사용자별 모델 접근 권한 제어 (allowed_models)"))
    blocks.append(bulleted("Retry: 3회 재시도 (exponential backoff: 1s/2s/4s)"))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 5: Tech Stack
    # ══════════════════════════════════════════════
    blocks.append(heading2("5. 기술 스택 (Tech Stack)"))
    blocks.append(table_block([
        ["Layer", "Technology", "비고"],
        ["Backend", "FastAPI + Uvicorn", "Single server, port 3000"],
        ["Frontend", "Custom SPA (HTML/JS/CSS)", "login.html, chat.html, SSE streaming"],
        ["LLM Orchestration", "LangGraph + LangChain Core", "StateGraph, ReAct Agent"],
        ["Primary LLM", "Gemini 3 Pro + Claude Opus/Sonnet", "Dual LLM, user selectable"],
        ["Fast LLM", "Gemini 2.5 Flash", "Internal tasks only"],
        ["Database", "Google BigQuery", "Sales, Marketing, Review, Influencer data"],
        ["Vector Search", "BigQuery Vector Search", "BGE-M3 768-dim embeddings"],
        ["Document", "Notion API (Direct)", "Allowlist 10 pages, no MCP"],
        ["Workspace", "Google Workspace API", "Gmail, Drive, Calendar (OAuth2)"],
        ["CS Data", "Google Sheets API", "13 tabs, ~1,100 Q&A entries"],
        ["Auth", "JWT httpOnly Cookie", "PyJWT + bcrypt, 7일 만료"],
        ["Chart", "Chart.js", "ChatGPT-style, SSE inline"],
        ["Logging", "structlog (JSON)", "BigQuery qa_logs 테이블"],
        ["Safety", "MaintenanceManager + CircuitBreaker", "Auto-detect + manual toggle"],
    ]))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 6: Frontend Architecture
    # ══════════════════════════════════════════════
    blocks.append(heading2("6. 프론트엔드 아키텍처"))
    blocks.append(paragraph(
        "Custom SPA 기반. Open WebUI 의존성을 완전히 제거하고 자체 프론트엔드를 구축했습니다."
    ))
    blocks.append(table_block([
        ["페이지", "파일", "주요 기능"],
        ["로그인", "app/frontend/login.html", "Craver marquee 배경, glassmorphism, 다크/라이트 토글"],
        ["채팅", "app/frontend/chat.html", "사이드바, 대화 관리, SSE 스트리밍, 마크다운 렌더링"],
        ["대시보드", "app/static/dashboard.html", "5 카테고리 탭, Looker Studio/Sheets/Tableau 임베딩"],
    ]))
    blocks.append(bulleted("8개 제안 칩 (Welcome Screen) + 후속 질문 제안"))
    blocks.append(bulleted("Multimodal: 이미지 첨부/붙여넣기/드래그앤드롭 → vision LLM"))
    blocks.append(bulleted("Drawer UI: Dashboard, System Status, Admin (슬라이드 패널)"))
    blocks.append(bulleted("테마: CSS Variables, orange accent (#e89200), Montserrat font"))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 7: Safety & Reliability
    # ══════════════════════════════════════════════
    blocks.append(heading2("7. 안전 시스템 (Safety & Reliability)"))
    blocks.append(table_block([
        ["컴포넌트", "방식", "설명"],
        ["SQL 보안", "화이트리스트 + 키워드 차단",
         "SELECT ONLY, 허용 테이블만, INSERT/DROP/ALTER 등 차단"],
        ["MaintenanceManager", "자동감지 + 수동토글",
         "60초 __TABLES__ 폴링, row_count 50% 하락 감지 → soft warning"],
        ["CircuitBreaker", "서비스별 독립",
         "3회 연속 실패 → OPEN (60s 차단) → HALF_OPEN → CLOSED"],
        ["Coherence Check", "비동기 백그라운드",
         "질문-답변 정합성 검증 (fire-and-forget, 응답 지연 없음)"],
        ["QueryVerifier", "비동기 백그라운드",
         "SQL 결과 재검증 (fire-and-forget, 5-15s 차단 제거)"],
        ["BQ Fallback", "자동 대체",
         "SQL 실패 시 Direct LLM 폴백 (에러 대신 안내 메시지)"],
        ["Rate Limit", "LLM 재시도",
         "429/500/503 에러 시 3회 재시도 (exponential backoff)"],
    ]))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 8: Performance
    # ══════════════════════════════════════════════
    blocks.append(heading2("8. 성능 최적화 (Performance)"))
    blocks.append(heading3("8.1 최적화 기법"))
    blocks.append(bulleted("Keyword-first 라우팅: LLM 호출 없이 키워드로 즉시 분류 (0ms vs ~1s)"))
    blocks.append(bulleted("Lazy Schema Loading: 쿼리 관련 테이블만 프롬프트에 포함 (50KB→15-25KB)"))
    blocks.append(bulleted("병렬 처리: 답변 + 차트 동시 생성 (ThreadPoolExecutor)"))
    blocks.append(bulleted("Fire-and-forget: QueryVerifier, Coherence Check → 백그라운드 스레드"))
    blocks.append(bulleted("SQL LIMIT: 1000행 기본 (LLM 처리 최적화)"))
    blocks.append(bulleted("API 메시지 제한: max 30 messages (컨텍스트 블로트 방지)"))
    blocks.append(bulleted("대화 메모리: 15턴, 1500자 (ChatGPT 수준 문맥 유지)"))
    blocks.append(paragraph(""))

    blocks.append(heading3("8.2 성능 기준"))
    blocks.append(table_block([
        ["등급", "응답 시간", "판정"],
        ["OK", "< 60초", "정상"],
        ["WARN", "60초 ~ 89초", "주의 (통과)"],
        ["FAIL", ">= 90초", "실패"],
    ]))
    blocks.append(paragraph(""))

    blocks.append(heading3("8.3 QA 테스트 결과"))
    blocks.append(table_block([
        ["테스트", "질문 수", "통과율", "평균 응답시간"],
        ["Marketing QA Phase 1", "3,900", "100%", "42.5s"],
        ["Context Coherence (Phase 2)", "260 (13x20)", "100%", "-"],
        ["V2 Variation (Phase 3)", "3,900", "100%", "-"],
        ["통합", "8,060", "100%", "-"],
    ]))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 9: Data Sources
    # ══════════════════════════════════════════════
    blocks.append(heading2("9. 데이터 소스 (Data Sources)"))
    blocks.append(table_block([
        ["소스", "테이블/위치", "데이터 유형"],
        ["BigQuery", "Sales_Integration.SALES_ALL_Backup", "다국적 플랫폼 매출 (Shopee, Lazada, TikTok, Amazon)"],
        ["BigQuery", "Sales_Integration.Product", "제품 마스터 (SKU, Category, Qty)"],
        ["BigQuery", "marketing_analysis.*", "광고 데이터, 마케팅 비용, Shopify, 인플루언서"],
        ["BigQuery", "Review_Data.*", "아마존/큐텐/쇼피/스마트스토어 리뷰"],
        ["BigQuery", "Platform_Data.raw_data", "플랫폼 메트릭스 (순위, 가격, 할인)"],
        ["BigQuery", "ad_data.meta data_test", "메타 광고 라이브러리"],
        ["Notion", "10 allowlisted pages", "사내 문서, 정책, 매뉴얼"],
        ["Google Sheets", "CS Q&A (13 tabs)", "제품 CS 상담 데이터 (~1,100건)"],
        ["Google Workspace", "Gmail/Drive/Calendar", "per-user OAuth2 인증"],
        ["Tavily", "Web Search API", "CRAG 폴백 (외부 정보)"],
    ]))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 10: Comparison
    # ══════════════════════════════════════════════
    blocks.append(heading2("10. 기술 비교 (왜 LangGraph인가)"))
    blocks.append(table_block([
        ["방식", "구조", "장단점", "본 시스템 해당"],
        ["LangChain (Chain)", "선형 파이프라인 A→B→C",
         "단순하지만 분기/루프 불가", "X"],
        ["RAG (기본)", "검색→생성 단일 경로",
         "문서 QA에 적합하지만 복합 작업 불가", "부분 (RAG Agent)"],
        ["LangGraph (Graph)", "조건부 분기, 루프, 상태 관리 DAG",
         "복잡한 워크플로우 가능, 학습곡선 있음", "O (핵심)"],
        ["Compound AI System", "LLM + 검색 + 도구 + 에이전트 조합",
         "여러 컴포넌트 통합, 설계 복잡", "O (전체)"],
    ]))
    blocks.append(paragraph(""))

    # ══════════════════════════════════════════════
    # Section 11: Infrastructure
    # ══════════════════════════════════════════════
    blocks.append(heading2("11. 인프라 (Infrastructure)"))
    blocks.append(bulleted("GCP Project: skin1004-319714"))
    blocks.append(bulleted("Server: Single FastAPI (port 3000 production, port 3001 development)"))
    blocks.append(bulleted("Auth: JWT httpOnly cookie (PyJWT + bcrypt, 7일 만료)"))
    blocks.append(bulleted("Admin: jeffrey@skin1004korea.com (자동 승격)"))
    blocks.append(bulleted("DB: SQLite (users, conversations, messages)"))
    blocks.append(bulleted("비용 목표: 월 $500 이하 (Gemini API + BigQuery + Cloud Run)"))
    blocks.append(paragraph(""))

    # ── Footer ──
    blocks.append(divider())
    blocks.append(callout(
        f"Generated: {today} | "
        "SKIN1004 Enterprise AI v7.2 | "
        "LangGraph Multi-Agent Compound AI System | "
        "DB Team / Data Analytics",
        "📋"
    ))

    return blocks


def main():
    print("=" * 60)
    print("SKIN1004 AI - System Architecture Report Upload")
    print("=" * 60)

    token = get_token()
    blocks = build_report()
    print(f"\nTotal blocks: {len(blocks)}")

    # Upload as a toggle section (collapsible)
    today = datetime.now().strftime("%Y-%m-%d")
    section_title = f"{today} | System Architecture Report (v7.2)"

    # Create toggle with first block as summary, rest as children
    summary_block = blocks[1] if len(blocks) > 1 else blocks[0]  # callout as summary
    detail_blocks = [blocks[0]] + blocks[2:]  # heading + rest

    # Split into chunks if too many blocks for toggle children
    # Notion toggle children limit is 100
    if len(detail_blocks) <= MAX_BLOCKS_PER_CALL:
        main_toggle = toggle(section_title, [summary_block])
        ids = append_blocks_get_ids(token, PAGE_ID, [main_toggle])
        if ids:
            toggle_id = ids[0]
            append_blocks(token, toggle_id, detail_blocks)
            print(f"\n  Uploaded toggle: {section_title}")
            print(f"  Detail blocks: {len(detail_blocks)}")
    else:
        # Upload in chunks
        main_toggle = toggle(section_title, [summary_block])
        ids = append_blocks_get_ids(token, PAGE_ID, [main_toggle])
        if ids:
            toggle_id = ids[0]
            total = 0
            for start in range(0, len(detail_blocks), MAX_BLOCKS_PER_CALL):
                batch = detail_blocks[start:start + MAX_BLOCKS_PER_CALL]
                append_blocks(token, toggle_id, batch)
                total += len(batch)
                time.sleep(0.3)
            print(f"\n  Uploaded toggle: {section_title}")
            print(f"  Detail blocks: {total} (in {(total // MAX_BLOCKS_PER_CALL) + 1} batches)")

    print("\n" + "=" * 60)
    print("Upload complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
