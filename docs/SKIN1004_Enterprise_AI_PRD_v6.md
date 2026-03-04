# SKIN1004 Enterprise AI System

## Product Requirements Document

**Hybrid AI System: Text-to-SQL + Notion + Google Workspace + CS DB + Multi-Agent**
**Single FastAPI Server + Custom Frontend Architecture**

**Version 8.0**
**2026.02.26**
**DB Team / Data Analytics**

---

# 1. Project Overview

본 프로젝트는 SKIN1004의 글로벌 세일즈 데이터, 사내 Notion 문서, Google Workspace, 고객 CS 상담 데이터를 통합 관리하는 엔터프라이즈 AI 시스템이다. 약 200명의 임직원이 자연어로 매출 데이터를 조회하고, Notion 문서를 검색하며, Google Calendar/Gmail/Drive에 접근하고, 제품 CS 상담 정보를 즉시 확인할 수 있는 환경을 제공한다.

> **핵심 설계 원칙**: Orchestrator-Worker 멀티 에이전트 구조. 매출 데이터에는 Text-to-SQL, 사내 문서에는 Notion Direct API, 개인 업무에는 Google Workspace OAuth2, 제품 상담에는 CS DB 검색을 적용. 키워드 우선 분류 + LLM 라우팅으로 질문 유형을 자동 판별하여 6개 경로로 최적 처리한다.

## 1.1 프로젝트 배경

- Shopee, Lazada, TikTok Shop, Amazon 등 다국적 플랫폼 매출 데이터가 BigQuery에 통합 관리중
- 매출 데이터 조회 시 SQL 작성이 필요하여 비기술 직원의 데이터 접근성이 제한됨
- 사내 문서(정책, 매뉴얼, 제품 정보 등)가 분산 관리되어 정보 검색에 시간 소요
- 고객 CS 상담 데이터(3개 브랜드, 739건)가 Google Spreadsheet에 분산 관리
- 200명 규모의 임직원이 동시에 활용할 수 있는 가성비 높은 AI 솔루션 필요

## 1.2 프로젝트 목표

| 목표 | 설명 | KPI | 현재 달성 |
|------|------|-----|----------|
| 데이터 민주화 | 비기술 직원도 자연어로 매출 데이터 조회 | SQL 작성 없이 데이터 접근율 90%+ | QA 500 BQ 100% |
| 정보 검색 효율화 | 사내 문서 + CS 검색 시간 단축 | 평균 검색 시간 60초 이내 | Notion 36.5s, CS 17.7s |
| 비용 최적화 | 200명 동시 사용 기준 월 운영비 최소화 | 월 $500 이하 (AI API 비용) | 예상 $310-810 |
| 정확도 확보 | 매출 수치 오류 제로 목표 | Text-to-SQL 정확도 95%+ | QA 500: 99.8% |

---

# 2. System Architecture

## 2.1 단일 서버 아키텍처 (v8.0)

> **v7.0 변경**: Open WebUI + 프록시 서버를 완전 제거하고, 커스텀 프론트엔드를 FastAPI 단일 서버로 통합. 3-서버 구조(Proxy + Open WebUI + FastAPI) → 1-서버 구조(FastAPI only)로 간소화.

```
                      ┌─────────────────────────────────────────────┐
                      │            사용자 브라우저                     │
                      │                                             │
                      │   login.html  ──  chat.html  ──  dashboard  │
                      │   (Craver BG)    (SPA 채팅)     (Looker등)   │
                      └──────────────────┬──────────────────────────┘
                                         │ HTTP / SSE (port 3000)
                                         │ JWT httpOnly cookie 인증
                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Server (:3000)                          │
│                                                                        │
│  ┌──────────────────────── API Layer ─────────────────────────────┐   │
│  │                                                                 │   │
│  │  Auth API         Chat API          Conv API       Admin API    │   │
│  │  /api/auth/*      /v1/chat/         /api/convs/*   /api/admin/* │   │
│  │  signup/signin    completions       CRUD+messages  users/models │   │
│  │                                                                 │   │
│  │  Google OAuth     Safety API        Health API     Dashboard    │   │
│  │  /auth/google/*   /safety/status    /health        /dashboard   │   │
│  │                   /admin/maint.*    /health/ready               │   │
│  └─────────────────────────┬───────────────────────────────────────┘   │
│                            │                                           │
│  ┌─────────────────────────▼───────────────────────────────────────┐   │
│  │                    Orchestrator Engine                           │   │
│  │           키워드 우선 분류 → LLM 폴백 → 6경로 실행               │   │
│  │                                                                 │   │
│  │  ┌──────┐ ┌──────┐ ┌─────┐ ┌────┐ ┌──────┐ ┌────────┐         │   │
│  │  │ BQ   │ │Notion│ │ GWS │ │ CS │ │Multi │ │Direct  │         │   │
│  │  │Agent │ │Agent │ │Agent│ │Agt │ │Agent │ │LLM     │         │   │
│  │  └──┬───┘ └──┬───┘ └──┬──┘ └─┬──┘ └──┬───┘ └───┬────┘         │   │
│  └─────┼────────┼────────┼──────┼───────┼─────────┼───────────────┘   │
│        │        │        │      │       │         │                    │
│  ┌─────▼──┐ ┌───▼──┐ ┌──▼───┐ ┌▼────┐ ┌▼──────┐ ┌▼──────────────┐   │
│  │BigQuery│ │Notion│ │Google│ │GShee│ │Google │ │Gemini 3 Pro   │   │
│  │  GCP   │ │ API  │ │ API  │ │ts   │ │Search │ │Claude Opus4.6 │   │
│  │        │ │      │ │OAuth2│ │API  │ │Ground.│ │+ Flash        │   │
│  └────────┘ └──────┘ └──────┘ └─────┘ └───────┘ └───────────────┘   │
│                                                                        │
│  ┌──────────────────── Safety Layer ──────────────────────────────┐   │
│  │  MaintenanceManager (BQ 테이블 업데이트 감지, 60s 폴링)         │   │
│  │  CircuitBreaker (서비스별 3회 실패 → 60s 차단)                  │   │
│  │  Coherence Check (질문-답변 정합성 검증)                        │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌──────────────────── Data Layer ────────────────────────────────┐   │
│  │  SQLite: Users, Conversations, Messages (skin1004_chat.db)     │   │
│  │  BQ Schema Cache (startup preload)                             │   │
│  │  CS Q&A Cache (739건 메모리 캐시)                               │   │
│  │  Notion Title Cache (10 pages warmup)                          │   │
│  └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

| 구성 요소 | 역할 |
|----------|------|
| **FastAPI (:3000)** | AI 백엔드 + 프론트엔드 + 인증 + 데이터 저장 (단일 서버) |
| **SQLite** | 사용자/대화/메시지 저장 (파일 DB) |
| **BigQuery** | 매출 데이터 (READ-ONLY) |

## 2.2 이전 아키텍처 대비 변경

| 항목 | v6.x (이전) | v8.0 (현재) |
|------|------------|------------|
| 서버 구성 | Proxy(:3000) + Open WebUI(:8080) + FastAPI(:8100) | **FastAPI 단일(:3000)** |
| 프론트엔드 | Open WebUI (Docker, SvelteKit) | **커스텀 SPA (Vanilla JS)** |
| 인증 | Open WebUI Google SSO | **JWT httpOnly cookie (bcrypt)** |
| 대화 저장 | Open WebUI SQLite | **자체 SQLite (SQLAlchemy ORM)** |
| 모델 관리 | Open WebUI 설정 | **Admin 시스템 (권한별 모델 제어)** |
| UI 커스터마이징 | 프록시 CSS/JS 주입 (불안정) | **네이티브 HTML/CSS (완전 제어)** |

## 2.3 Text-to-SQL이 핵심인 이유

SKIN1004의 매출 데이터는 BigQuery에 구조화된 테이블로 관리된다. 구조화된 데이터에 RAG를 적용할 경우:

| 항목 | Text-to-SQL | RAG |
|------|-------------|-----|
| 정확도 | 정확한 숫자 반환 (SQL 직접 실행) | 요약/근사치 (환각 위험) |
| 속도 | 빠름 (SQL 1회 실행) | 느림 (임베딩 → 검색 → 생성) |
| 실시간성 | 항상 최신 데이터 | 인덱싱 주기에 의존 |
| 집계 연산 | SUM, AVG, GROUP BY 정확 | 숫자 계산에 구조적 한계 |

---

# 3. Tech Stack

## 3.1 AI 모델 선정: Dual LLM + Flash 3계층 구조

200명 규모의 동시 사용을 고려하여 3계층 LLM 구조를 채택. 프론트엔드 모델 피커에서 사용자가 모델을 선택하면 해당 LLM이 메인 응답을 생성하고, 경량 작업은 항상 Flash가 전담.

```
┌──────────────────────────────────────────────────────────┐
│                    LLM 3계층 구조                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [Tier 1] 메인 응답 LLM (사용자 선택)                      │
│  ┌────────────────────┐  ┌────────────────────┐          │
│  │ Gemini 3 Pro       │  │ Claude Opus 4.6    │          │
│  │ (skin1004-Search)  │  │ (skin1004-Analysis)│          │
│  │                    │  │                    │          │
│  │ - Google Search    │  │ - 심층 분석         │          │
│  │   grounding        │  │ - 복잡한 추론       │          │
│  │ - 범용 대화        │  │ - 구조화된 답변     │          │
│  └────────────────────┘  └────────────────────┘          │
│                                                          │
│  [Tier 2] 경량 작업 전용 — Gemini 2.5 Flash               │
│  ┌────────────────────────────────────────────┐          │
│  │ - SQL 생성/검증      - 차트 설정 JSON      │          │
│  │ - 라우팅 분류         - 답변 포맷팅         │          │
│  │ - Notion 페이지 선택  - CS 답변 합성        │          │
│  │ - 쿼리 리라이팅       - Coherence 검증      │          │
│  └────────────────────────────────────────────┘          │
│                                                          │
│  [Tier 3] 키워드 분류 (LLM 미사용, 0ms)                   │
│  ┌────────────────────────────────────────────┐          │
│  │ - Notion: 노션, notion, 정책, 매뉴얼       │          │
│  │ - GWS: 일정, 메일, 드라이브, 캘린더         │          │
│  │ - CS: 성분, 비건, 사용법, 센텔라, 민감       │          │
│  │ - Data: 매출, 판매, 순위, 차트, 그래프       │          │
│  │ - Multi: 데이터 + 날씨/영향/원인/트렌드     │          │
│  └────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

| 모델 | 역할 | 선정 이유 |
|------|------|----------|
| Gemini 3 Pro Preview | 메인 응답 (Search) | Google Search grounding, 1M 토큰, 추론 향상 |
| Claude Opus 4.6 | 메인 응답 (Analysis) | 심층 분석, 복잡한 추론, 구조화된 답변 |
| Gemini 2.5 Flash | 경량 작업 전용 | SQL/라우팅/포맷팅 (속도+안정성 최우선) |
| Claude Sonnet 4.6 | Claude 경량 태스크 | GWS ReAct agent 등 |

> **속도 최적화**: 키워드 우선 분류(Tier 3) → 매칭 실패 시에만 Flash 라우팅(Tier 2) → 최종 답변은 메인 LLM(Tier 1). BQ 응답 38-42초 → 18-45초로 개선.

## 3.2 전체 기술 스택

| 레이어 | 기술 | 선정 이유 |
|--------|------|----------|
| **Frontend** | Custom SPA (HTML/CSS/JS) | 완전한 UI 제어, Open WebUI 의존 제거 |
| | marked.js + highlight.js + Chart.js | 마크다운/코드/차트 렌더링 |
| **API Server** | FastAPI (:3000) | 비동기 처리, SSE 스트리밍, OpenAI-compatible |
| **Auth** | JWT httpOnly cookie (bcrypt) | 보안 쿠키, 7일 만료, 비밀번호 해싱 |
| **ORM** | SQLAlchemy 2.0 | SQLite 접근, 자동 마이그레이션 |
| **Orchestration** | Orchestrator-Worker | 키워드 우선 분류 + LLM 라우팅, 6경로 |
| **SQL Pipeline** | LangGraph | generate → validate → execute → format + chart |
| **Main LLM** | Gemini 3 Pro / Claude Opus 4.6 | Dual 모델 선택 (모델 피커) |
| **Fast LLM** | Gemini 2.5 Flash | SQL/라우팅/포맷팅 경량 작업 |
| **Database** | BigQuery (GCP) | 매출 데이터 READ-ONLY (SALES_ALL_Backup, Product) |
| **Local DB** | SQLite | Users, Conversations, Messages |
| **Document** | Notion API (Direct) | 허용 목록 10페이지, 실시간 접근 |
| **Workspace** | Google Workspace API | Gmail, Calendar, Drive (개별 OAuth2) |
| **CS Data** | Google Sheets API v4 | 13탭, 739건 Q&A, 메모리 캐시 |
| **Search** | Google Search (grounding) | Gemini 네이티브, API 키 불필요 |
| **Chart** | Chart.js (Frontend) | 6종 차트, 30색 팔레트, 자동 타입 선택 |
| **Safety** | MaintenanceManager + CircuitBreaker | 테이블 업데이트 감지, 서비스 차단기 |
| **Logging** | structlog (JSON) | 구조화 로깅, 요청 추적 |

---

# 4. Core Features

## 4.1 Text-to-SQL Agent

**메인 테이블**: `skin1004-319714.Sales_Integration.SALES_ALL_Backup`
**제품 테이블**: `skin1004-319714.Sales_Integration.Product`

**LangGraph 파이프라인**:
```
generate_sql (Flash) → validate_sql (규칙) → execute_sql (BQ) → format_answer (Flash)
                                                                        ↓
                                                              chart_generation (병렬, Flash)
```

**안전장치**:
- READ-ONLY: SELECT 문만 허용, INSERT/UPDATE/DELETE/DROP 차단
- 테이블 화이트리스트: SALES_ALL_Backup, Product만 접근 가능
- 쿼리 타임아웃: 최대 30초
- 결과 행 제한: 최대 10,000행
- 광범위 쿼리 보호: 3개+ 차원 시 ORDER BY DESC 필수, Smart Preview

**차트 시각화**:
- 6종 차트: bar, horizontal_bar, line, pie, grouped_bar, stacked_bar
- 30색 고유 팔레트, 데이터 레이블 (K/M/B 축약)
- 긴 라벨(25자+) → horizontal_bar 자동 전환
- 시계열 데이터 순서 보존
- 비시계열 내림차순 정렬

## 4.2 Notion Agent (v6.2)

**검색 대상**: 허용 목록 10개 Notion 페이지/DB (관리자 설정)

**동작 흐름**:
```
사용자 질문 → 키워드 매칭 (허용 목록 타이틀 대조)
                ├─ 매칭 성공 → 병렬 페이지 읽기 (최대 3페이지)
                └─ 매칭 실패 → Flash LLM 페이지 선택
             → 블록 텍스트 추출 (15,000자 예산)
             → Google Sheets 자동 감지/조회 (최대 2개, 병렬)
             → 답변 생성 (Flash)
```

**핵심 기능**: 허용 목록 기반 검색 (워밍업 ~3초), LLM 폴백, Sheets 자동 읽기, UUID 자동 변환, 타입 폴백 (page/database), 병렬 페이지/시트 읽기

## 4.3 CS Agent (v1.1)

**데이터 소스**: Google Spreadsheet 13개 탭 (739건 Q&A)
- 3개 브랜드: SKIN1004, COMMONLABS, ZOMBIE BEAUTY
- 제품별 질문/답변, 비건 인증, 사용 루틴, 성분 정보

**동작 흐름**:
```
사용자 질문 → 키워드 추출 (제품명/라인/브랜드/카테고리)
           → Q&A 검색 (키워드 가중치 + 단어 유사도)
           → 상위 10개 Q&A 선별
           → 답변 합성 (Flash, CS 전문 프롬프트)
```

**핵심 기능**: 서버 시작 시 전체 Q&A 메모리 캐시, 키워드 가중치 검색 (제품명+3, 라인+2, 카테고리+1.5), 브랜드 별칭 매칭 ("커먼랩스"→COMMONLABS), Flash LLM 답변 합성

**라우팅 키워드**: 60+개 (제품 라인, 브랜드, 성분, 사용법, 피부타입, 알레르기 등)

## 4.4 Google Workspace Agent (v4.2)

**접근 서비스**: Gmail (읽기), Calendar (읽기), Drive (읽기)

**인증 방식**: 개별 OAuth2 (사용자별 토큰, `data/gws_tokens/` 저장)
```
사용자 → Google 연결 버튼 클릭 → OAuth 동의 → 토큰 저장
      → "이번주 일정?" → GWS Agent가 해당 사용자 토큰으로 Calendar API 호출
```

**핵심 기능**: 도구 사전 분류 (`_classify_tool()` — calendar/gmail/drive), ReAct 에이전트 (Claude Sonnet), recursion_limit=10, 120s 타임아웃

## 4.5 Multi-Source Agent

**동작 흐름**:
1. 사용자 질문 → Flash로 데이터 전용 BigQuery 쿼리 리라이팅
2. Google Search (외부 정보) + BigQuery (내부 데이터) **병렬** 실행
3. Flash로 두 결과 종합 분석 보고서 합성

## 4.6 Direct LLM

- Google Search grounding 포함 (Gemini 네이티브 / Claude는 Gemini Search 결과 주입)
- 대화 히스토리 전달 (최근 5턴)
- 모델별 자기소개 포함

## 4.7 프론트엔드 (Custom SPA)

**로그인 페이지** (`app/frontend/login.html`):
- Craver 마키 배경 애니메이션 (CSS-only)
- 글라스모피즘 카드 (blur 50px, 반투명)
- 다크/라이트 테마 토글
- 회원가입/로그인 모드 전환

**채팅 페이지** (`app/frontend/chat.html` + `chat.js`):
- 사이드바: 로고, 검색, 날짜별 대화 목록, Dashboard/System Status/Admin 버튼
- 탑바: 모델 선택 드롭다운, Google 연결 버튼
- 환영 화면: 인사 + 8개 제안 칩
- SSE 스트리밍 + 마크다운/코드/차트 렌더링
- 후속 질문 칩 (AI 응답 후 3개)
- Drawer (우측 슬라이드): Dashboard, System Status, Admin

**대시보드** (`app/static/dashboard.html`):
- 5개 탭: 인플루엔서, 매출&제품, 퍼포먼스마케팅, 기타, 솔루션
- Looker Studio, Google Sheets, Tableau iframe 임베드

**스타일**: CSS variables, 다크/라이트 테마, Montserrat 폰트, orange accent (#e89200)

## 4.8 Admin 시스템

- 사용자 목록 + 모델 권한 관리 (Admin 전용)
- 사용자별 skin1004-Search / skin1004-Analysis 토글
- `allowed_models` 컬럼 (comma-separated, 기본: "skin1004-Search")
- Admin은 항상 전체 모델, 권한 수정 불가
- jeffrey@skin1004korea.com → 서버 시작 시 자동 admin 승격

---

# 5. Data Schema

## 5.1 SQLite (사용자 인증 + 대화 기록)

**파일 경로**: `C:/Users/DB_PC/.open-webui/data/skin1004_chat.db`

```
Users (id PK, email UNIQUE, name, password[bcrypt], role, allowed_models, created_at)
  │
  └─ 1:N ─ Conversations (id PK, user_id FK, title, model, created_at, updated_at)
              │
              └─ 1:N ─ Messages (id PK, conversation_id FK, role, content, created_at)
```

## 5.2 BigQuery (매출 데이터)

| 테이블 | Full Path | 접근 | 용도 |
|--------|-----------|------|------|
| SALES_ALL_Backup | `skin1004-319714.Sales_Integration.SALES_ALL_Backup` | READ-ONLY | 다국적 플랫폼 매출 |
| Product | `skin1004-319714.Sales_Integration.Product` | READ-ONLY | 제품 마스터 |

## 5.3 외부 데이터 소스

| 소스 | 접근 방식 | 데이터 |
|------|-----------|--------|
| Google Spreadsheet | Sheets API v4 (서비스 계정) | CS Q&A 13탭, 739건 |
| Notion | Notion API (Internal Integration) | 사내 문서 10페이지 |
| Google Workspace | OAuth2 (사용자별) | Gmail, Drive, Calendar |

---

# 6. Agent & Module Design

## 6.1 Orchestrator 라우팅 흐름

```
사용자 질문 → _keyword_classify()
                 │
    ┌────────────┼─────────────┐
    │ 키워드     │ 컨텍스트+   │ 키워드
    │ 매칭 성공  │ 매칭 실패   │ 매칭 실패
    │            │             │ (컨텍스트 없음)
    ▼            ▼             ▼
  route       Flash LLM     "direct"
  확정       _classify()      확정
                 │
                 ▼
              route 확정
                 │
    ┌──────┬─────┼──────┬──────┬──────┐
    ▼      ▼     ▼      ▼      ▼      ▼
 bigquery notion  gws    cs   multi  direct
    │      │     │      │      │      │
    ▼      ▼     ▼      ▼      ▼      ▼
[에이전트 실행] → _verify_coherence() → ensure_formatting() → SSE 응답
```

**키워드 우선순위**: System Task → Notion → GWS → CS (강한 데이터 키워드 없을 때) → Multi (데이터+외부) → BigQuery (데이터만) → Direct (기본)

## 6.2 에이전트별 처리 흐름

| 에이전트 | 모듈 | 처리 흐름 | 사용 LLM |
|---------|------|----------|---------|
| SQL Agent | sql_agent.py | generate_sql → validate → execute → format (+chart 병렬) | Flash 전용 |
| Notion Agent (v6.2) | notion_agent.py | search_pages → read_blocks∥sheets (병렬) → generate | Flash (전체) |
| CS Agent (v1.1) | cs_agent.py | search_qa (키워드+유사도) → generate (CS 프롬프트) | Flash (답변) |
| GWS Agent (v4.2) | gws_agent.py | classify_tool → ReAct agent (recursion_limit=10) | Sonnet (ReAct) |
| Multi Agent | orchestrator.py | rewrite → [Google Search ∥ BigQuery] → synthesize | Flash (전체) |
| Direct | orchestrator.py | LLM 직접 호출 (Google Search grounding 포함) | Main (선택) |

## 6.3 핵심 모듈

| 모듈 | 파일 | 설명 |
|------|------|------|
| Orchestrator | `app/agents/orchestrator.py` | 6경로 라우팅 + 에이전트 실행 + Coherence 검증 |
| SQL Agent | `app/agents/sql_agent.py` | LangGraph Text-to-SQL + Smart Preview + 차트 |
| Notion Agent | `app/agents/notion_agent.py` | 허용 목록 검색 + 병렬 읽기 + Sheets 자동 |
| CS Agent | `app/agents/cs_agent.py` | Sheets Q&A 검색 + Flash 답변 + 브랜드 별칭 |
| GWS Agent | `app/agents/gws_agent.py` | Gmail/Calendar/Drive ReAct + 도구 사전 분류 |
| LLM Client | `app/core/llm.py` | Dual LLM (Gemini/Claude) + Flash + Sonnet |
| Safety | `app/core/safety.py` | MaintenanceManager + CircuitBreaker |
| BigQuery | `app/core/bigquery.py` | SQL 실행 + 스키마 캐싱 + CB 래핑 |
| Auth API | `app/api/auth_api.py` | 회원가입/로그인/로그아웃 (JWT+bcrypt) |
| Auth Middleware | `app/api/auth_middleware.py` | JWT cookie 검증 |
| Conversation API | `app/api/conversation_api.py` | 대화 CRUD + 메시지 |
| Admin API | `app/api/admin_api.py` | 사용자 목록 + 모델 권한 |
| Google Auth | `app/core/google_auth.py` | OAuth2 토큰 관리 (파일 기반) |
| Response Formatter | `app/core/response_formatter.py` | 마크다운 포맷 정리 |

---

# 7. Security & Safety

## 7.1 인증 보안

| 항목 | 구현 |
|------|------|
| 비밀번호 | bcrypt 단방향 해싱 (salt 포함) |
| JWT 토큰 | HS256, httpOnly cookie, 7일 만료, samesite=lax |
| Admin | role 기반 접근 제어 (FastAPI Depends) |
| CORS | 전체 origin 허용 (내부 네트워크 운영) |
| 요청 추적 | X-Request-ID + X-Latency-Ms 헤더 자동 부여 |

## 7.2 SQL 안전장치

| 항목 | 구현 |
|------|------|
| 허용 구문 | SELECT 만 |
| 차단 키워드 | INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE |
| 테이블 화이트리스트 | SALES_ALL_Backup, Product |
| 쿼리 타임아웃 | 30초 |
| 결과 행 제한 | 10,000행 |

## 7.3 Safety System (v7.2)

**MaintenanceManager**: BQ 테이블 업데이트 중 쿼리 자동 차단
- 자동 감지: 60초 주기 `__TABLES__` 폴링 (비용 $0)
- 감지 방식: last_modified 180초 이내 → "updating" OR row_count 5%+ 감소
- 수동 토글: `POST /admin/maintenance?action=on/off`
- BQ/Multi 라우트 차단 → "데이터 점검 중" 안내

**CircuitBreaker**: 서비스별 차단기
- 대상: bigquery, notion, gemini
- 3회 연속 실패 → OPEN (60초 차단) → HALF_OPEN (1건 시도) → CLOSED

**Coherence Check**: 질문-답변 정합성 검증
- Flash로 경량 검증 (질문 범위 vs 답변 범위)
- CS/direct/multi 제외
- 불일치 시 경고 배너 삽입

---

# 8. Environment Configuration

| 항목 | 값 |
|------|-----|
| GCP Project ID | skin1004-319714 |
| 메인 테이블 | `skin1004-319714.Sales_Integration.SALES_ALL_Backup` |
| 제품 테이블 | `skin1004-319714.Sales_Integration.Product` |
| JSON Key (개발용) | `C:/json_key/skin1004-319714-60527c477460.json` |
| Main LLM (Search) | Gemini 3 Pro Preview (`gemini-3-pro-preview`) |
| Main LLM (Analysis) | Claude Opus 4.6 (`claude-opus-4-6`) |
| Fast LLM | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| Light Claude | Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| FastAPI Server | port 3000 (단일 서버) |
| SQLite DB | `C:/Users/DB_PC/.open-webui/data/skin1004_chat.db` |
| Notion | Internal Integration (허용 목록 10페이지) |
| Google OAuth | 개별 사용자 OAuth2 (gmail, calendar, drive readonly) |
| CS Data | Google Spreadsheet (13탭, 739건) |
| 사용자 수 | 약 200명 |

---

# 9. Cost Estimation

200명 기준, 1인당 하루 평균 20회 질문 가정 (월 약 12만 건)

| 항목 | 월 예상 비용 | 비고 |
|------|-------------|------|
| Gemini 3 Pro Preview API | $100-250 | 메인 응답 (skin1004-Search) |
| Gemini 2.5 Flash API | $30-80 | SQL/라우팅/포맷팅 경량 작업 |
| Claude Opus 4.6 API | $50-200 | 메인 응답 (skin1004-Analysis) |
| BigQuery 스토리지 | $50-100 | 기존 인프라 활용 |
| BigQuery 쿼리 비용 | $50-150 | 온디맨드 과금 |
| Notion API | $0 | 무료 (Internal Integration) |
| Google Workspace API | $0 | 기존 라이선스 포함 |
| Google Sheets API | $0 | 무료 (서비스 계정) |
| **합계** | **$280-780/월** | GPT-4o 단일 모델 대비 1/3~1/5 수준 |

---

# 10. QA Test Results

## 10.1 최신 종합 테스트 (v7.2.1, QA 500, 2026-02-25)

| 카테고리 | 질문수 | OK | WARN | FAIL | 평균(s) |
|----------|--------|-----|------|------|---------|
| CS | 260 | 260 | 0 | 0 | 17.7 |
| BQ (Sales) | 60 | 60 | 0 | 0 | 45.1 |
| BQ (Product) | 30 | 30 | 0 | 0 | 50.2 |
| Chart | 25 | 25 | 0 | 0 | 16.7 |
| Direct | 30 | 30 | 0 | 0 | 23.4 |
| Notion | 35 | 35 | 0 | 0 | 36.5 |
| GWS | 30 | 30 | 0 | 0 | 22.4 |
| Multi | 30 | 29 | 1 | 0 | 55.5 |
| **합계** | **500** | **499** | **1** | **0** | **27.1** |

- **99.8% PASS**, WARN 1건: MULTI-29 (108.2s)
- p50=21.8s, p95=59.8s, min=5.8s, max=108.2s
- Wall time: 113.2분 (2그룹 병렬)

## 10.2 성능 기준

| 등급 | 조건 | 설명 |
|------|------|------|
| **OK** | < 100초 | 정상 |
| **WARN** | 100~199초 | 경고 (최적화 대상) |
| **FAIL** | >= 200초 | 실패 |

## 10.3 누적 테스트 이력

| 테스트 | 일자 | 질문수 | 성공률 | WARN | FAIL | 평균(s) |
|--------|------|--------|--------|------|------|---------|
| QA 500 v3 (v7.2.1) | 02-25 | 500 | **99.8%** | 1 | 0 | **27.1** |
| QA 500 v2 (v7.1.1) | 02-24 | 500 | **100%** | 0 | 0 | 41.4 |
| QA 500 v1 (v6.5) | 02-23 | 500 | 99.4% | 3 | 0 | 41.4 |
| QA 300 v2 | 02-23 | 300 | 97→100% | 0 | 0 | 22.8 |
| QA 300 v1 | 02-20 | 299 | 97.7% | 0 | 0 | 23.9 |
| QA 100+ | 02-19 | 109 | 95.4% | 0 | 0 | - |
| QA 112 | 02-12 | 112 | 92% | - | - | - |

## 10.4 속도 최적화 이력

| 최적화 | 버전 | 이전 | 이후 | 개선율 |
|--------|------|------|------|--------|
| 키워드 우선 분류 | v5.0 | LLM 매번 | 즉시 | 즉시 |
| SQL Flash 전환 | v5.0 | 38-42s | 11-13s | -70% |
| 답변+차트 병렬 | v5.0 | 순차 | ThreadPoolExecutor | -40% |
| BQ 스키마 캐시 | v5.0 | 매번 조회 | 시작 시 1회 | -5s |
| Multi Search Flash | v6.4 | 106-113s | 34-51s | -60% |
| CS Agent Flash | v7.1.1 | 131-133s | 8-10s | -93% |
| Notion 답변 Flash | v7.2.1 | 105s | 49s | -53% |
| GWS 도구 사전분류 | v7.2.1 | 114s | 10s | -91% |

---

# 11. Implementation Status

| 항목 | 상태 | 비고 |
|------|------|------|
| Phase 1: 인프라 및 환경 구성 | **DONE** | BigQuery, Gemini, FastAPI |
| Phase 2: Text-to-SQL Agent | **DONE** | LangGraph, SQL 생성/검증/실행/포맷, Smart Preview |
| Phase 2+: 차트 시각화 | **DONE** | Chart.js 6종, 30색, 레전드, 가로 자동전환 |
| Phase 2+: 스키마 관리 | **DONE** | Excel 기반 26개 컬럼 화이트리스트 |
| Phase 2+: 속도 최적화 | **DONE** | Flash 분리, 병렬 처리, 캐싱 |
| Phase 3: RAG 파이프라인 | TODO | Docling 파서, BGE-M3 임베딩, BigQuery 벡터 인덱스 |
| Phase 4: 프론트엔드 | **DONE** | 커스텀 SPA (Open WebUI 완전 제거) |
| Phase 4+: Dual LLM | **DONE** | Gemini 3 Pro + Claude Opus 4.6 |
| Phase 4+: Google Search | **DONE** | Gemini 네이티브 grounding |
| Phase 4+: GWS OAuth | **DONE** | 개별 OAuth2, ReAct agent |
| Phase 4+: Notion v6.2 | **DONE** | 허용 목록, 병렬 읽기, Sheets 자동 |
| Phase 4+: CS Agent v1.1 | **DONE** | 739건 Q&A, Flash, 브랜드 별칭 |
| Phase 4+: Admin 시스템 | **DONE** | 사용자/모델 권한 관리 |
| Phase 4+: Dashboard | **DONE** | 5탭, Looker/Sheets/Tableau 임베드 |
| Phase 4+: Safety System | **DONE** | Maintenance + CircuitBreaker + Coherence |
| Phase 5: 테스트 | **DONE** | QA 500: 99.8% (500건 E2E) |

---

# 12. Version History

> 상세 업데이트 내역은 `docs/SKIN1004_AI_Update_History.md` 참조.

| 날짜 | 버전 | 주요 변경 |
|------|------|----------|
| 02-26 | **v8.0** | PRD 전면 재작성 (현행 아키텍처 반영) |
| 02-25 | v7.2.1 | 광범위 쿼리 수정, Safety System, Coherence Check |
| 02-24 | v7.1.1 | 차트 종합 수정, CS Flash, 후속질문 |
| 02-24 | v7.0 | 커스텀 프론트엔드, Admin, JWT 인증 (Open WebUI 제거) |
| 02-23 | v6.5 | QA 300 v2, CS Agent, 3-서버 프록시 UI |
| 02-20 | v6.4 | QA 300 v1, Multi 병렬 |
| 02-10 | v5.0 | Dual LLM, Google Search, GWS OAuth |
| 02-06 | v4.0 | 차트 시각화, 10,000행 확대 |

---

**End of Document**
