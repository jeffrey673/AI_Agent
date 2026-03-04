# SKIN1004 Enterprise AI — 기술 아키텍처 문서

> **Version**: 4.0 (Custom Frontend)
> **Last Updated**: 2026-02-26
> **대상 독자**: IT팀, 개발팀, 시스템 관리자

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [기술 스택](#3-기술-스택)
4. [정보 구조도 (IA)](#4-정보-구조도-ia)
5. [AI 에이전트 라우팅](#5-ai-에이전트-라우팅)
6. [기능 정의서](#6-기능-정의서)
7. [데이터베이스 스키마](#7-데이터베이스-스키마)
8. [API 엔드포인트 목록](#8-api-엔드포인트-목록)
9. [보안](#9-보안)
10. [성능 지표](#10-성능-지표)

---

## 1. 시스템 개요

**SKIN1004 Enterprise AI**는 사내 매출 데이터 조회, 문서 검색, Google Workspace 연동, 고객 상담 지원을 하나의 채팅 인터페이스로 통합한 AI 어시스턴트입니다.

### 목적

- 사내 매출/판매 데이터를 자연어로 조회하고 시각화
- Notion 사내 문서를 AI 기반으로 검색·요약
- Gmail, Google Drive, Calendar를 대화형으로 활용
- 제품 CS 상담 데이터를 즉시 검색·답변

### 핵심 가치

| 가치 | 설명 |
|------|------|
| **즉시성** | 자연어 질문 → 평균 27초 내 답변 (QA 500 기준) |
| **정확성** | LangGraph 기반 SQL 생성/검증/실행 파이프라인 |
| **안전성** | SELECT-only SQL, Circuit Breaker, 점검모드 자동감지 |
| **접근성** | 웹 브라우저만으로 전 직원 사용 가능 |

---

## 2. 시스템 아키텍처

### 전체 구조도

```
                          ┌─────────────────────────────────────────────────┐
                          │              사용자 브라우저                       │
                          │   login.html  /  chat.html  /  dashboard.html   │
                          └──────────────────┬──────────────────────────────┘
                                             │ HTTP / SSE
                                             ▼
                    ┌────────────────────────────────────────────────────────┐
                    │                  FastAPI Server (:3000)                │
                    │                                                        │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
                    │  │ Auth API │  │ Chat API │  │Admin API │  │Conv API│ │
                    │  │/api/auth │  │/v1/chat  │  │/api/admin│  │/api/   │ │
                    │  │          │  │/completns│  │          │  │convs   │ │
                    │  └──────────┘  └─────┬────┘  └──────────┘  └────────┘ │
                    │                      │                                 │
                    │               ┌──────▼──────┐                         │
                    │               │ Orchestrator │                         │
                    │               │ (라우팅 엔진)  │                         │
                    │               └──────┬──────┘                         │
                    │    ┌─────┬─────┬─────┼─────┬─────┐                    │
                    │    ▼     ▼     ▼     ▼     ▼     ▼                    │
                    │  ┌───┐┌───┐┌───┐┌───┐┌─────┐┌──────┐                 │
                    │  │BQ ││Not││GWS││CS ││Multi││Direct│                 │
                    │  │SQL││ion││   ││   ││     ││ LLM  │                 │
                    │  └─┬─┘└─┬─┘└─┬─┘└─┬─┘└──┬──┘└──┬───┘                 │
                    └────┼────┼────┼────┼─────┼─────┼───────────────────────┘
                         │    │    │    │     │     │
              ┌──────────▼┐ ┌▼──┐┌▼──┐┌▼──┐ ┌▼──┐ ┌▼──────────────┐
              │ BigQuery  │ │Not││Goo││Goo│ │Goo│ │Gemini 3 Pro   │
              │ (GCP)     │ │ion││gle││gle│ │gle│ │Claude Opus 4.6│
              │           │ │API││API││She│ │Sea│ │               │
              │ SALES_ALL │ │   ││   ││ets│ │rch│ │Google Search  │
              │ Product   │ │   ││   ││   │ │   │ │  Grounding    │
              └───────────┘ └───┘└───┘└───┘ └───┘ └───────────────┘
```

### 서버 구성

| 구성 요소 | 포트 | 역할 |
|----------|------|------|
| **FastAPI** | 3000 | AI 백엔드 + 프론트엔드 (단일 서버) |
| **SQLite** | (파일) | 사용자/대화/메시지 저장 |

> **v4.0 변경**: Open WebUI + 프록시 서버를 완전히 제거하고, 커스텀 프론트엔드를 FastAPI 단일 서버로 통합.

---

## 3. 기술 스택

### 레이어별 기술

| 레이어 | 기술 | 버전/모델 | 용도 |
|--------|------|-----------|------|
| **Frontend** | HTML/CSS/JS (SPA) | Vanilla JS | 커스텀 채팅 UI, 로그인 |
| | marked.js | - | 마크다운 렌더링 |
| | highlight.js | - | 코드 구문 강조 |
| | Chart.js | - | 차트 렌더링 |
| **Backend** | FastAPI | 0.115+ | REST API + SSE 스트리밍 |
| | Uvicorn | 0.34+ | ASGI 서버 |
| | SQLAlchemy | 2.0+ | ORM (SQLite) |
| | pydantic-settings | 2.0+ | 환경변수 관리 |
| | structlog | 24.0+ | JSON 구조화 로깅 |
| **LLM (대화용)** | Gemini 3 Pro | gemini-3-pro-preview | 기본 대화 모델 (Search) |
| | Claude Opus 4.6 | claude-opus-4-6 | 심층 분석 모델 (Analysis) |
| **LLM (내부 경량)** | Gemini 2.5 Flash | gemini-2.5-flash | SQL 생성, 라우팅, 차트, CS |
| | Claude Sonnet 4.6 | claude-sonnet-4-6 | Claude 경량 태스크 |
| **Orchestration** | LangGraph | 0.2+ | SQL 에이전트 상태 그래프 |
| **Database** | BigQuery | (GCP) | 매출 데이터 + 벡터 서치 |
| | SQLite | 3.x | 사용자 인증, 대화 이력 |
| **External API** | Notion API | v1 | 사내 문서 검색 |
| | Google Workspace API | v1 | Gmail, Drive, Calendar |
| | Google Sheets API | v4 | CS Q&A 데이터 |
| | Google Search | (Grounding) | 실시간 웹 검색 |
| **Auth** | PyJWT | - | JWT 토큰 생성/검증 |
| | bcrypt | - | 비밀번호 해싱 |
| | Google OAuth2 | - | GWS 개별 사용자 인증 |
| **Infra** | GCP | skin1004-319714 | 프로젝트 |
| | Windows 11 | 로컬 서버 | 개발/운영 서버 |

### 모델 선택 체계

```
사용자 모델 선택 (Frontend)
    │
    ├── skin1004-Search  ──→  Gemini 3 Pro (대화) + Flash (내부)
    │
    └── skin1004-Analysis ──→  Claude Opus 4.6 (대화) + Sonnet 4.6 (내부)

※ 라우팅, SQL 생성, 차트 설정, CS 답변 등 내부 경량 작업은
   모델 선택과 무관하게 항상 Gemini Flash 사용 (속도 최적화)
```

---

## 4. 정보 구조도 (IA)

### URL 라우팅 맵

```
/                          → chat.html (인증 필요, 미인증 시 /login 리다이렉트)
/login                     → login.html (로그인/회원가입)
/dashboard                 → dashboard.html (Looker/Sheets/Tableau 임베드)
/docs                      → FastAPI Swagger UI
/redoc                     → FastAPI ReDoc

/v1/chat/completions       → AI 채팅 (OpenAI-compatible)
/v1/models                 → 모델 목록

/api/auth/signup           → 회원가입
/api/auth/signin           → 로그인
/api/auth/me               → 현재 사용자 정보
/api/auth/logout           → 로그아웃

/api/conversations         → 대화 목록/생성
/api/conversations/{id}    → 대화 상세/수정/삭제
/api/conversations/{id}/messages → 메시지 추가

/api/admin/users           → 사용자 목록 (admin)
/api/admin/users/{id}/models → 모델 권한 수정 (admin)

/auth/google/login         → Google OAuth 시작
/auth/google/callback      → Google OAuth 콜백
/auth/google/status        → Google 연결 상태 확인
/auth/google/revoke        → Google 토큰 해제

/admin/maintenance         → 점검모드 토글
/admin/maintenance/status  → 점검 상태 조회
/safety/status             → 전체 안전장치 현황

/health                    → 서버 헬스체크
/health/ready              → 서비스 준비 상태

/frontend/*                → 프론트엔드 정적 파일
/static/*                  → CSS, 이미지, 대시보드 정적 파일
```

### 페이지별 컴포넌트 트리

```
login.html
├── 배경 (Craver 마키 애니메이션)
├── 테마 토글 버튼 (다크/라이트)
└── 로그인 카드 (글라스모피즘)
    ├── 로고 (splash-dark-new.png / splash.png)
    ├── 이메일 / 비밀번호 / 이름 입력
    ├── 로그인 / 회원가입 토글
    └── 에러 메시지

chat.html
├── 사이드바
│   ├── 로고
│   ├── 새 대화 버튼
│   ├── 대화 검색
│   ├── 대화 목록 (날짜별 그룹)
│   │   ├── 오늘
│   │   ├── 어제
│   │   ├── 지난 7일
│   │   └── 이전
│   ├── Dashboard 버튼 (→ Drawer)
│   ├── System Status 버튼 (→ Drawer)
│   │   └── 인라인 상태 표시 (All OK / 이슈 ticker)
│   ├── Admin 버튼 (admin만, → Drawer)
│   └── 사용자 푸터 (이름, 로그아웃)
│
├── 메인 영역
│   ├── 탑바
│   │   ├── 모델 선택 드롭다운
│   │   └── Google 연결 버튼
│   │
│   ├── 환영 화면 (대화 없을 때)
│   │   ├── 인사 메시지
│   │   └── 8개 제안 질문 칩
│   │
│   ├── 메시지 영역
│   │   ├── 사용자 메시지
│   │   └── AI 메시지 (마크다운 + 차트 + 코드 하이라이트)
│   │       └── 후속 질문 칩 (응답 후 표시)
│   │
│   └── 입력 영역
│       ├── 텍스트 입력 (textarea)
│       └── 전송 버튼
│
└── Drawer (우측 슬라이드)
    ├── Dashboard Drawer → iframe (dashboard.html)
    ├── System Status Drawer → 서비스 카드 (ticker)
    └── Admin Drawer → 사용자 카드 (모델 토글)

dashboard.html (iframe 내)
├── 5개 카테고리 탭
│   ├── 인플루엔서
│   ├── 매출&제품
│   ├── 퍼포먼스마케팅
│   ├── 기타
│   └── 솔루션
└── 아이템 카드
    ├── Looker Studio (iframe embed)
    ├── Google Sheets (iframe embed)
    ├── Tableau (iframe embed)
    ├── Tool (링크)
    └── Web (링크)
```

---

## 5. AI 에이전트 라우팅

### 라우팅 플로우차트

```
사용자 질문 입력
       │
       ▼
  ┌──────────────────┐
  │ _keyword_classify │  ← 키워드 기반 1차 분류 (LLM 미호출, 즉시)
  └────────┬─────────┘
           │
     ┌─────┼─────┬─────┬─────┬──────┐
     │     │     │     │     │      │
     ▼     ▼     ▼     ▼     ▼      ▼
 "notion" "gws" "cs" "bq" "multi" "direct"
     │     │     │     │     │      │
     │     │     │     │     │      ├── 대화 컨텍스트 있음?
     │     │     │     │     │      │   ├── YES → Flash LLM 재분류
     │     │     │     │     │      │   └── NO  → direct 확정
     │     │     │     │     │      │
     ▼     ▼     ▼     ▼     ▼      ▼
  ┌─────────────────────────────────────────┐
  │            Orchestrator                  │
  │  route_and_execute(query, model_type)    │
  └────────┬────────────────────────────────┘
           │
     ┌─────┼─────┬─────┬─────┬──────┐
     ▼     ▼     ▼     ▼     ▼      ▼
  ┌─────┐┌────┐┌───┐┌───┐┌─────┐┌──────┐
  │ BQ  ││ NT ││GWS││ CS││Multi││Direct│
  │Agent││Agent│Agent│Agent│Agent ││ LLM  │
  └──┬──┘└──┬─┘└─┬─┘└─┬─┘└──┬──┘└──┬───┘
     │      │    │    │     │      │
     ▼      ▼    ▼    ▼     ▼      ▼
  ┌─────────────────────────────────────┐
  │  _verify_coherence (정합성 검증)      │ ← cs/direct/multi 제외
  └────────────────┬────────────────────┘
                   ▼
  ┌─────────────────────────────────────┐
  │  ensure_formatting (마크다운 포맷)    │
  └────────────────┬────────────────────┘
                   ▼
              SSE 스트리밍 응답
```

### 6개 라우팅 경로 상세

| 경로 | 트리거 키워드 (예시) | 처리 흐름 | 외부 의존 |
|------|---------------------|-----------|-----------|
| **bigquery** | 매출, 수량, 주문, 차트, 그래프, 국가별, 월별, top, 순위 | 질문 → SQL 생성 (Flash) → SQL 검증 → BQ 실행 → 답변 포맷 (Flash) + 차트 (병렬) | BigQuery |
| **notion** | 노션, 정책, 매뉴얼, 프로세스, 가이드, 반품 | 질문 → 페이지 선택 (Flash) → 병렬 페이지 읽기 → 답변 생성 (Flash) | Notion API |
| **gws** | 드라이브, 메일, 캘린더, 회의록, 일정, 파일 찾아 | 질문 → 도구 사전 분류 → ReAct 에이전트 (Claude Sonnet) → API 호출 | Google API (OAuth) |
| **cs** | 성분, 비건, 사용법, 센텔라, 민감, 알레르기, 영유아 | 질문 → 키워드 가중치 검색 (캐시) → 상위 5건 매칭 → 답변 생성 (Flash) | Google Sheets |
| **multi** | 데이터 키워드 + 날씨/영향/원인/트렌드/경쟁 | 질문 → BQ 데이터 쿼리 + Google Search (병렬) → 종합 분석 (Flash) | BigQuery + Google Search |
| **direct** | 키워드 매칭 없음 / 일반 질문 | 질문 → LLM 직접 응답 (Google Search grounding 포함) | Gemini/Claude |

### 키워드 분류 우선순위

```
System Task (### Task:)  →  direct (즉시)
         ↓
Notion 키워드            →  notion
         ↓
GWS 키워드               →  gws
         ↓
CS 키워드 (강한 데이터 키워드 없을 때)  →  cs
         ↓
데이터 + 외부 키워드      →  multi
         ↓
데이터 키워드             →  bigquery
         ↓
기본값                   →  direct
```

### BigQuery SQL Agent (LangGraph 워크플로우)

```
generate_sql  →  validate_sql  →  execute_sql  →  format_answer
   (Flash)       (규칙 기반)       (BigQuery)       (Flash)
                                                      ↓
                                              chart_generation (병렬)
                                                   (Flash)
```

| 노드 | 역할 | 소요시간 |
|------|------|---------|
| generate_sql | 자연어 → BigQuery SQL 변환 | ~3-5s |
| validate_sql | SELECT-only, 테이블 화이트리스트, 위험 키워드 차단 | <0.1s |
| execute_sql | BigQuery 쿼리 실행 (30s 타임아웃, 10,000행 제한) | ~5-15s |
| format_answer | 결과 → 자연어 답변 + 표 정리 | ~3-5s |
| chart_generation | 차트 설정 JSON 생성 + Chart.js 렌더링 | ~3-5s (병렬) |

---

## 6. 기능 정의서

### 6.1 인증 시스템

| 기능 | 설명 |
|------|------|
| **회원가입** | 이메일 + 이름 + 비밀번호 (4자 이상), bcrypt 해싱 |
| **로그인** | 이메일 + 비밀번호 → JWT 토큰 (httpOnly cookie, 7일 만료) |
| **자동 리다이렉트** | 미인증 → /login, 인증 → / (chat.html) |
| **첫 사용자 Admin** | 첫 번째 가입 사용자 자동 admin 부여 |
| **Admin 보장** | jeffrey@skin1004korea.com → 서버 시작 시 자동 admin 승격 |
| **Google OAuth** | GWS 연동용 OAuth2 (사용자별 토큰, Drive/Gmail/Calendar 스코프) |

### 6.2 채팅

| 기능 | 설명 |
|------|------|
| **모델 선택** | skin1004-Search (Gemini) / skin1004-Analysis (Claude) |
| **SSE 스트리밍** | 답변을 20자 단위로 실시간 전송 |
| **마크다운 렌더링** | marked.js 기반 (표, 목록, 강조, 인용) |
| **코드 하이라이트** | highlight.js 기반 코드 블록 구문 강조 |
| **차트 렌더링** | Chart.js 기반 (bar, line, pie, grouped, stacked, horizontal) |
| **후속 질문** | AI 응답 후 3개 후속 질문 칩 표시 |
| **대화 컨텍스트** | 최근 5턴 대화 이력 전달 (참조 해결: "그거", "아까", "다시") |
| **소스 라벨** | SSE에 `<!-- source:bigquery -->` 등 소스 정보 포함 |

### 6.3 대화 기록

| 기능 | 설명 |
|------|------|
| **자동 제목** | 첫 사용자 메시지 앞 60자를 대화 제목으로 설정 |
| **날짜 그룹** | 오늘 / 어제 / 지난 7일 / 이전으로 그룹 표시 |
| **검색** | 대화 제목 검색 (프론트엔드 필터링) |
| **삭제** | 대화 + 모든 메시지 cascade 삭제 |
| **모델 표시** | 각 대화에 사용된 모델 저장 |

### 6.4 대시보드

| 기능 | 설명 |
|------|------|
| **5개 탭** | 인플루엔서, 매출&제품, 퍼포먼스마케팅, 기타, 솔루션 |
| **아이템 타입** | Looker Studio, Google Sheets, Tableau, Tool, Web |
| **Looker 임베드** | URL 자동 `/embed/` 변환, iframe 렌더링 |
| **새 탭 열기** | 원본 URL을 새 탭에서 열기 버튼 |
| **Drawer 방식** | 우측 슬라이드 패널로 표시 (chat.html에서 iframe) |

### 6.5 Admin 시스템

| 기능 | 설명 |
|------|------|
| **사용자 목록** | 전체 사용자 이메일, 이름, 역할, 모델 권한 표시 |
| **모델 권한 관리** | 사용자별 skin1004-Search / skin1004-Analysis 토글 |
| **Admin 접근 제한** | role=admin만 Admin 패널 접근 가능 |
| **Admin 모델 잠금** | Admin은 항상 전체 모델 접근, 권한 수정 불가 |

### 6.6 Safety 시스템

| 기능 | 설명 |
|------|------|
| **MaintenanceManager** | BigQuery 테이블 업데이트 감지 및 쿼리 차단 |
| **자동 감지** | 60초 주기 `__TABLES__` 메타데이터 폴링 (비용 0원) |
| **감지 방식 (하이브리드)** | last_modified 180초 이내 → "updating" OR row_count 5%+ 감소 |
| **수동 토글** | POST /admin/maintenance?action=on/off |
| **CircuitBreaker** | 서비스별 (bigquery, notion 등) 연속 3회 실패 → 60초 차단 |
| **System Status** | 사이드바 인라인 표시 (All OK / 이슈 ticker 애니메이션) |
| **정합성 검증** | Flash로 질문-답변 스코프 일치 여부 검증 |

---

## 7. 데이터베이스 스키마

### 7.1 SQLite (사용자/대화/메시지)

**파일 경로**: `C:/Users/DB_PC/.open-webui/data/skin1004_chat.db`

#### Users 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | STRING(32) PK | UUID (hex) |
| email | STRING(255) UNIQUE | 이메일 주소 |
| name | STRING(255) | 사용자 이름 |
| password | STRING(255) | bcrypt 해시 |
| role | STRING(20) | "user" 또는 "admin" |
| allowed_models | STRING(500) | 허용 모델 (쉼표 구분, 기본: "skin1004-Search") |
| created_at | DATETIME | 생성 시각 (UTC) |

#### Conversations 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | STRING(32) PK | UUID (hex) |
| user_id | STRING(32) FK → users.id | 소유 사용자 |
| title | STRING(500) | 대화 제목 (기본: "New Chat") |
| model | STRING(100) | 사용 모델 (기본: "skin1004-ai") |
| created_at | DATETIME | 생성 시각 |
| updated_at | DATETIME | 최종 수정 시각 |

#### Messages 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | STRING(32) PK | UUID (hex) |
| conversation_id | STRING(32) FK → conversations.id | 소속 대화 |
| role | STRING(20) | "user" 또는 "assistant" |
| content | TEXT | 메시지 내용 |
| created_at | DATETIME | 생성 시각 |

#### 관계

```
Users  1 ──── N  Conversations  1 ──── N  Messages
      (cascade)                (cascade)
```

### 7.2 BigQuery (매출 데이터)

**프로젝트**: `skin1004-319714`

#### SALES_ALL_Backup

| 항목 | 값 |
|------|-----|
| Full Path | `skin1004-319714.Sales_Integration.SALES_ALL_Backup` |
| 접근 권한 | **READ-ONLY** (SELECT만 허용) |
| 주요 데이터 | 다국적 플랫폼 매출 (Shopee, Lazada, TikTok Shop, Amazon 등) |
| 행 수 | ~수십만 행 |

#### Product

| 항목 | 값 |
|------|-----|
| Full Path | `skin1004-319714.Sales_Integration.Product` |
| 접근 권한 | **READ-ONLY** |
| 주요 데이터 | 제품 마스터 (제품명, SKU, 라인, 카테고리) |

### 7.3 외부 데이터 소스

| 소스 | 접근 방식 | 데이터 |
|------|-----------|--------|
| Google Spreadsheet | Sheets API v4 (서비스 계정) | CS Q&A 13탭, ~739건 |
| Notion | Notion API (토큰) | 사내 문서 ~10 페이지 |
| Google Workspace | OAuth2 (사용자별) | Gmail, Drive, Calendar |

---

## 8. API 엔드포인트 목록

### 인증 API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/auth/signup` | - | 회원가입 (email, name, password) |
| POST | `/api/auth/signin` | - | 로그인 (email, password) → JWT cookie |
| GET | `/api/auth/me` | JWT | 현재 사용자 정보 |
| POST | `/api/auth/logout` | - | JWT cookie 삭제 |

### AI 채팅 API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| POST | `/v1/chat/completions` | JWT | AI 채팅 (OpenAI-compatible, SSE 스트리밍 지원) |
| GET | `/v1/models` | - | 사용 가능 모델 목록 |

### 대화 관리 API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/conversations` | JWT | 내 대화 목록 (최신순) |
| POST | `/api/conversations` | JWT | 새 대화 생성 |
| GET | `/api/conversations/{id}` | JWT | 대화 상세 (메시지 포함) |
| PUT | `/api/conversations/{id}` | JWT | 대화 제목 수정 |
| DELETE | `/api/conversations/{id}` | JWT | 대화 삭제 (cascade) |
| POST | `/api/conversations/{id}/messages` | JWT | 메시지 추가 |

### Admin API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/admin/users` | Admin | 전체 사용자 목록 + 모델 권한 |
| PUT | `/api/admin/users/{id}/models` | Admin | 사용자 모델 권한 수정 |

### Google OAuth API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/auth/google/login` | - | Google OAuth 시작 (user_email 파라미터) |
| GET | `/auth/google/callback` | - | OAuth 콜백 (code + state) |
| GET | `/auth/google/status` | - | Google 연결 상태 확인 |
| POST | `/auth/google/revoke` | - | Google 토큰 해제 |

### 안전장치 API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| POST | `/admin/maintenance` | - | 점검모드 토글 (action=on/off, reason) |
| GET | `/admin/maintenance/status` | - | 점검 상태 조회 |
| GET | `/safety/status` | - | 전체 안전장치 현황 (서비스 + CB) |

### 시스템 API

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/health` | - | 서버 헬스체크 (liveness) |
| GET | `/health/ready` | - | 서비스 준비 상태 (readiness) |
| GET | `/dashboard` | - | 대시보드 HTML 서빙 |

### 프론트엔드 라우트

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/` | Cookie | 채팅 페이지 (미인증 → /login) |
| GET | `/login` | - | 로그인 페이지 |

---

## 9. 보안

### 9.1 인증 보안

| 항목 | 구현 |
|------|------|
| **비밀번호 저장** | bcrypt 단방향 해싱 (salt 포함) |
| **JWT 토큰** | HS256 서명, httpOnly cookie, 7일 만료 |
| **Cookie 설정** | httpOnly=True, samesite=lax, path=/ |
| **Admin 격리** | role 기반 접근 제어 (Depends 미들웨어) |
| **CORS** | 전체 origin 허용 (내부 네트워크 운영 기준) |

### 9.2 SQL 안전장치

| 항목 | 구현 |
|------|------|
| **허용 구문** | SELECT 만 허용 |
| **차단 키워드** | INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE |
| **테이블 화이트리스트** | `SALES_ALL_Backup`, `Product` 만 허용 |
| **쿼리 타임아웃** | 30초 |
| **결과 행 제한** | 최대 10,000행 |
| **SQL 인젝션** | LLM 생성 SQL → 규칙 기반 검증 → 파라미터 바인딩 |

### 9.3 Circuit Breaker

```
CLOSED (정상)
   │
   │ 연속 3회 실패
   ▼
OPEN (차단, 60초)
   │
   │ 60초 경과
   ▼
HALF_OPEN (1건 시도)
   │
   ├── 성공 → CLOSED
   └── 실패 → OPEN
```

| 대상 서비스 | 실패 임계 | 쿨다운 |
|-------------|-----------|--------|
| bigquery | 3회 | 60초 |
| notion | 3회 | 60초 |
| gemini | 3회 | 60초 |

### 9.4 점검모드 (MaintenanceManager)

- BigQuery 테이블 업데이트 중 → SQL 쿼리 자동 차단
- `__TABLES__` 메타데이터 60초 주기 폴링 (비용: $0)
- 하이브리드 감지: last_modified 180초 이내 OR row_count 5%+ 감소
- 수동 토글 가능 (수동 모드는 자동 해제 안 됨)

### 9.5 요청 로깅

- 모든 요청에 X-Request-ID 헤더 부여
- 요청/응답 JSON 구조화 로깅 (structlog)
- 노이즈 경로 로깅 제외 (/health, /safety/status 등)
- JWT cookie에서 사용자 이메일 자동 추출

---

## 10. 성능 지표

### QA 500 종합 테스트 결과 (v7.2.1, 2026-02-25)

| 항목 | 수치 |
|------|------|
| **총 질문 수** | 500개 |
| **성공률** | 99.8% (499 OK, 1 WARN, 0 FAIL) |
| **평균 응답시간** | 27.1초 |
| **중앙값 (P50)** | 21.8초 |
| **P95** | 59.8초 |
| **최소** | 5.8초 |
| **최대** | 108.2초 |
| **총 소요시간** | 113.2분 (2그룹 병렬) |

### 카테고리별 성능

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

### 성능 기준

| 기준 | 조건 | 의미 |
|------|------|------|
| **OK** | < 100초 | 정상 |
| **WARN** | 100~199초 | 경고 (느림) |
| **FAIL** | >= 200초 | 실패 (타임아웃급) |

### 속도 최적화 히스토리

| 최적화 항목 | 이전 | 이후 | 개선율 |
|-------------|------|------|--------|
| 키워드 우선 분류 | LLM 매번 호출 | 키워드 매칭 | -100% 지연 |
| SQL 생성 (Flash) | Pro 38-42s | Flash 11-13s | -70% |
| 답변+차트 병렬 | 순차 처리 | ThreadPoolExecutor | -40% |
| BQ 스키마 캐시 | 매번 조회 | 시작 시 1회 | -5s/쿼리 |
| Multi route (Flash) | Pro 106-113s | Flash 34-51s | -60% |
| CS Agent (Flash) | Pro 131-133s | Flash 8-10s | -93% |
| Notion 답변 (Flash) | Pro 105s | Flash 49s | -53% |
| GWS 도구 사전 분류 | 3도구 모두 호출 | 1도구만 호출 | -91% |

---

## 부록: 프로젝트 파일 구조

```
AI_Agent/
├── app/
│   ├── main.py                    # FastAPI 앱 + lifespan (워밍업, 안전장치)
│   ├── config.py                  # pydantic-settings 환경변수
│   │
│   ├── api/
│   │   ├── routes.py              # /v1/chat/completions, 안전장치 API
│   │   ├── auth_api.py            # 회원가입/로그인/로그아웃
│   │   ├── auth_middleware.py     # JWT cookie 검증
│   │   ├── auth_routes.py         # Google OAuth2 엔드포인트
│   │   ├── conversation_api.py    # 대화 CRUD
│   │   ├── admin_api.py           # Admin 사용자/모델 관리
│   │   └── middleware.py          # CORS, 요청 로깅
│   │
│   ├── agents/
│   │   ├── orchestrator.py        # 6경로 라우팅 엔진
│   │   ├── sql_agent.py           # LangGraph Text-to-SQL
│   │   ├── notion_agent.py        # Notion 문서 검색/요약
│   │   ├── gws_agent.py           # Google Workspace ReAct
│   │   ├── cs_agent.py            # CS Q&A 검색
│   │   └── query_verifier.py      # 쿼리 검증
│   │
│   ├── core/
│   │   ├── llm.py                 # Dual LLM (Gemini + Claude)
│   │   ├── bigquery.py            # BigQuery 클라이언트
│   │   ├── safety.py              # MaintenanceManager + CircuitBreaker
│   │   ├── google_auth.py         # OAuth2 토큰 관리
│   │   ├── google_workspace.py    # Gmail/Drive/Calendar API
│   │   ├── chart.py               # Chart.js 설정 생성
│   │   └── response_formatter.py  # 마크다운 포맷 정리
│   │
│   ├── db/
│   │   ├── database.py            # SQLAlchemy 엔진, 세션, 마이그레이션
│   │   └── models.py              # User, Conversation, Message ORM
│   │
│   ├── models/
│   │   └── schemas.py             # Pydantic 요청/응답 스키마
│   │
│   ├── frontend/
│   │   ├── login.html             # 로그인 페이지
│   │   ├── chat.html              # 채팅 페이지
│   │   ├── chat.js                # 채팅 프론트엔드 로직
│   │   └── auth.js                # 인증 프론트엔드 로직
│   │
│   └── static/
│       ├── style.css              # 전체 스타일 (다크/라이트 테마)
│       ├── dashboard.html         # 대시보드 Hub
│       └── images/                # 로고, 파비콘
│
├── prompts/                       # LLM 프롬프트 텍스트 파일
├── scripts/                       # 테스트, 배치, Notion 업로드
├── docs/                          # 기술 문서, 업데이트 로그
├── .env                           # 환경변수 (API 키)
└── requirements.txt               # Python 의존성
```

---

> **문서 작성**: Claude AI
> **최종 검증**: 2026-02-26 (소스 코드 기반 전수 검증)
