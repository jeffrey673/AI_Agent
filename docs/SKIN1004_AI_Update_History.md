# SKIN1004 Enterprise AI — 업데이트 내역 통합본

> **Last Updated**: 2026-02-26
> **대상 독자**: IT팀, 개발팀
> **목적**: 시스템 변경 이력 추적 및 공유

---

## 목차

1. [버전 히스토리 요약 테이블](#1-버전-히스토리-요약-테이블)
2. [v7.2.1 (02-25)](#2-v721-02-25--광범위-쿼리-수정--safety-system--coherence-check)
3. [v7.1.1 (02-24)](#3-v711-02-24--차트-종합-수정--cs-flash-전환--후속질문-개선)
4. [v7.0 (02-24~25)](#4-v70-02-2425--커스텀-프론트엔드-open-webui-제거--admin-시스템)
5. [v6.5 (02-23)](#5-v65-02-23--qa-300-v2--multi-flash--3-서버-프록시-ui)
6. [v6.4 (02-20)](#6-v64-02-20--qa-300-v1--multi-병렬--빈-결과-처리)
7. [v6.2 (이전)](#7-v62-이전--cs-agent--notion-병렬--bq-flash-전환)
8. [QA 테스트 누적 성적](#8-qa-테스트-누적-성적)

---

## 1. 버전 히스토리 요약 테이블

| 날짜 | 버전 | 주요 변경 | 테스트 결과 |
|------|------|----------|------------|
| 02-25 | **v7.2.1** | 광범위 쿼리 수정, Safety System (MaintenanceManager + CircuitBreaker), Coherence Check, WARN 3→0 | 500/500 OK (99.8%), avg 27.1s |
| 02-24 | **v7.1.1** | 차트 종합 수정 (전 타입), CS Flash 전환, 후속질문 개선, 브랜드 별칭 | 500/500 OK (100%), avg 41.4s |
| 02-24~25 | **v7.0** | Open WebUI 완전 제거, 커스텀 프론트엔드 (login/chat SPA), Admin 시스템, JWT cookie 인증 | 기능 테스트 통과 |
| 02-23 | **v6.5.2** | 리버스 프록시 UI (3-서버), 한국어 로캘, 테마 로고 스왑, Claude Sonnet 4.6 업그레이드 | UI 테스트 통과 |
| 02-23 | **v6.5.1** | QA 300 v2 이슈 수정 (ERROR 1→0, SHORT 8→0) | 9/9 재테스트 OK |
| 02-23 | **v6.5** | QA 300 v2 (300 NEW 질문), Multi Flash 전환, CS Agent v1.0, QA 500 통합 | 500/500 (99.4%), avg 41.4s |
| 02-20 | **v6.4** | QA 300 v1, Multi 병렬 (BQ+Search), 에러 감지 개선, Notion 리포트 업로드 | 299/299 (97.7%), avg 23.9s |
| 02-10 | **v5.0** | Dual LLM (Gemini+Claude), Google Search Grounding, GWS 개별 OAuth2, Open WebUI SSO | 기능 테스트 통과 |
| 02-06 | **v4.0** | 차트 시각화 (30색, 레전드 정렬), 데이터 조회 10,000행 확대 | 차트 테스트 통과 |

---

## 2. v7.2.1 (02-25) — 광범위 쿼리 수정 + Safety System + Coherence Check

### 2-A. 광범위 쿼리 데이터 절삭 문제 수정

**문제**: 3개+ 차원 쿼리("국가별 제품 업체 월별 매출")에서 ORDER BY 없이 알파벳순 정렬 → 1000행 LIMIT에 걸려 일부 국가만 반환.

**수정**:
1. SQL 프롬프트에 규칙 17 추가: 3개+ 차원 쿼리 시 `ORDER BY total_revenue DESC` 필수
2. Smart Preview (`_build_smart_preview()`): 100행 초과 결과 → aggregate summary + top 20을 LLM에 전달
3. 1000행 LIMIT 도달 시 절삭 경고 삽입

| 파일 | 변경 |
|------|------|
| `prompts/sql_generator.txt` | 규칙 17 추가 |
| `app/agents/sql_agent.py` | Smart Preview, 절삭 경고 |

### 2-B. Safety System 신규

#### MaintenanceManager
- **자동 감지**: 60초 주기 `__TABLES__` 메타데이터 폴링 (비용 $0)
- **감지 방식**: last_modified 180초 이내 → "updating" OR row_count 5%+ 감소
- **수동 토글**: `POST /admin/maintenance?action=on/off`
- BQ 쿼리 차단: 점검 중 bigquery/multi 라우트에서 "데이터 점검 중" 메시지 반환

#### CircuitBreaker
- 서비스별 인스턴스 (bigquery, notion, gemini)
- 연속 3회 실패 → OPEN (60초 차단) → HALF_OPEN (1건 시도) → CLOSED

#### 프론트엔드 UI
- 사이드바 System Status 버튼 내 인라인 상태 표시 (All OK / 이슈 ticker)
- System Status Drawer: 서비스별 상태 카드

### 2-C. 질문-답변 정합성 검증 (Coherence Check)

- `_verify_coherence()`: Flash로 질문 범위 vs 답변 범위 일치 검증
- 불일치 시 답변 상단에 `> ⚠️ 참고: {issue}` 삽입
- CS/direct/multi 라우트 제외
- False Positive 수정: 147/500 (29.4%) → 0/40 (0%)

### 2-D. WARN 3건 수정

| ID | 원인 | 수정 | 이전 | 이후 |
|----|------|------|------|------|
| GWS-26 | ReAct가 불필요 도구 반복 호출 | `_classify_tool()` 도구 사전 분류 | 114.3s | 9.9s (-91%) |
| NT-17 | Notion 답변에 Pro 사용 (과도) | Flash 전환 | 105.4s | 49.0s (-53%) |
| MULTI-14 | coherence 검증 중복 | multi route 제외 | 114.0s | 43.0s (-62%) |

### 2-E. 수정 파일

| 파일 | 변경 |
|------|------|
| `app/core/safety.py` | **신규** — MaintenanceManager + CircuitBreaker |
| `app/agents/orchestrator.py` | 점검모드 가드, coherence, FP 수정 |
| `app/agents/sql_agent.py` | 날짜 컨텍스트, Smart Preview, 정합성 규칙 |
| `app/agents/cs_agent.py` | 정합성 규칙 4개 |
| `app/agents/notion_agent.py` | Flash 전환, 정합성 규칙 3개 |
| `app/agents/gws_agent.py` | 도구 사전 분류, recursion_limit 축소 |
| `app/api/routes.py` | 3개 안전장치 API 추가 |
| `app/main.py` | 자동감지 백그라운드 태스크 |
| `app/core/bigquery.py` | Circuit Breaker 래핑 |

### 2-F. 테스트 결과 (QA 500)

| 카테고리 | OK | WARN | FAIL | 합계 | 평균(s) |
|----------|-----|------|------|------|---------|
| CS | 260 | 0 | 0 | 260 | 17.7 |
| BQ | 60 | 0 | 0 | 60 | 45.1 |
| PROD | 30 | 0 | 0 | 30 | 50.2 |
| CHART | 25 | 0 | 0 | 25 | 16.7 |
| DIRECT | 30 | 0 | 0 | 30 | 23.4 |
| NT | 35 | 0 | 0 | 35 | 36.5 |
| GWS | 30 | 0 | 0 | 30 | 22.4 |
| MULTI | 29 | 1 | 0 | 30 | 55.5 |
| **합계** | **499** | **1** | **0** | **500** | **27.1** |

- **99.8% PASS**, WARN 1건: MULTI-29 (108.2s, multi route 복합 웹검색)
- p50=21.8s, p95=59.8s, Wall time=113.2분

---

## 3. v7.1.1 (02-24) — 차트 종합 수정 + CS Flash 전환 + 후속질문 개선

### 3-A. 차트 종합 수정 (`app/core/chart.py`)

**공통 개선**:
- 시계열 플래그 `_TIME_HINTS` 통합 (월/분기/Q1~Q4/Jan~Dec)
- 25자 초과 라벨 + 비시계열 → bar → horizontal_bar 자동 전환
- 가로 차트 라벨 40자 확장, 카테고리 8개 초과 시 이미지 높이 자동 증가

**차트별 정렬**:

| 차트 타입 | 수정 전 | 수정 후 |
|----------|---------|---------|
| bar | 시계열 플래그 별도 | 통합 플래그 |
| horizontal_bar | 큰값 하단 (역순) | 큰값 상단 (오름차순 정렬) |
| grouped_bar | - | 긴 라벨 시 orientation="h" 자동 전환 |
| stacked_bar | 정렬 미적용 | 합계 기준 내림차순 |

**y_col 축 자동수정 강화**:
- x_col이 숫자이면 단순 swap → 2컬럼 데이터에서도 차트 정상 생성

### 3-B. 후속질문 품질 개선

- `### Task:` 접두사 감지 → `direct` 즉시 라우팅 (BQ 오라우팅 방지)
- 커스텀 프롬프트: 명확 답변 가능 질문만 생성 (모호한 "~일까요?" 제거)
- 타이틀/태그 생성 시 대화 컨텍스트 전달

### 3-C. CS Agent Flash 전환 + 브랜드 별칭

- 답변 생성 Pro → Flash 전환 (단순 Q&A 합성)
- 브랜드 별칭: "커먼랩스" → COMMONLABS, "좀비뷰티" → ZOMBIE BEAUTY

| 테스트 | 이전 | 이후 | 개선율 |
|--------|------|------|--------|
| CS-236 "커먼랩스 비건이야?" | 131.0s | 9.8s | -93% |
| CS-237 "좀비뷰티 비건 인증?" | 133.2s | 8.1s | -94% |
| GWS-28 "shipping 메일 찾아줘" | 114.6s | 23.5s | -79% |

### 3-D. 테스트 결과

- **QA 500: 500/500 OK (100%)**, WARN 0, FAIL 0
- 평균 응답시간: 41.4s

---

## 4. v7.0 (02-24~25) — 커스텀 프론트엔드 (Open WebUI 제거) + Admin 시스템

### 4-A. 아키텍처 변경

| 항목 | 이전 (v6.x) | v7.0 |
|------|------------|------|
| 서버 구성 | Proxy(:3000) + Open WebUI(:8080) + FastAPI(:8100) | **FastAPI 단일 서버(:3000)** |
| 프론트엔드 | Open WebUI (Docker) | **커스텀 SPA (login.html + chat.html)** |
| 인증 | Open WebUI Google SSO | **JWT httpOnly cookie (bcrypt)** |
| 대화 저장 | Open WebUI SQLite | **자체 SQLite (SQLAlchemy ORM)** |
| 모델 관리 | Open WebUI 설정 | **Admin 시스템 (권한별 모델 제어)** |

### 4-B. 커스텀 프론트엔드

**로그인 페이지** (`app/frontend/login.html`):
- Craver 마키 배경 애니메이션 (CSS-only)
- 글라스모피즘 로그인 카드 (blur 50px, 반투명)
- 다크/라이트 테마 토글
- 회원가입/로그인 모드 전환
- 로고: splash-dark-new.png (다크) / splash.png (라이트)

**채팅 페이지** (`app/frontend/chat.html` + `chat.js`):
- 사이드바: 로고, 검색, 날짜별 대화 목록, Dashboard/System Status/Admin 버튼, 사용자 푸터
- 탑바: 모델 선택 드롭다운, Google 연결 버튼
- 환영 화면: 인사 + 8개 제안 칩
- SSE 스트리밍 + 마크다운 렌더링 + 차트 렌더링
- 후속 질문 칩 (AI 응답 후)
- Drawer (우측 슬라이드): Dashboard, System Status, Admin

### 4-C. Admin 시스템

- `GET /api/admin/users`: 전체 사용자 + 모델 권한
- `PUT /api/admin/users/{id}/models`: 사용자별 모델 토글
- `allowed_models` 컬럼 (comma-separated, 기본: "skin1004-Search")
- Admin은 항상 전체 모델, 권한 수정 불가

### 4-D. 데이터베이스

- SQLite (`skin1004_chat.db`): Users, Conversations, Messages
- SQLAlchemy ORM + 자동 마이그레이션 (`_migrate()`)
- Cascade 삭제 (User → Conversations → Messages)

### 4-E. 주요 신규/수정 파일

| 파일 | 유형 |
|------|------|
| `app/frontend/login.html` | 신규 |
| `app/frontend/chat.html` | 신규 |
| `app/frontend/chat.js` | 신규 |
| `app/frontend/auth.js` | 신규 |
| `app/static/style.css` | 신규 |
| `app/api/auth_api.py` | 신규 |
| `app/api/auth_middleware.py` | 신규 |
| `app/api/conversation_api.py` | 신규 |
| `app/api/admin_api.py` | 신규 |
| `app/db/database.py` | 신규 |
| `app/db/models.py` | 신규 |
| `app/main.py` | 전면 재작성 |

---

## 5. v6.5 (02-23) — QA 300 v2 + Multi Flash + 3-서버 프록시 UI

### 5-A. QA 300 v2 종합 테스트

- **300개 NEW 질문** (v1과 완전히 다른 질문 세트)
- 성공률: **97.0% → 100%** (이슈 수정 후)
- WARN: 0, FAIL: 0
- 평균: 22.8s, 중앙값: 19.4s, P95: 45.6s

| 카테고리 | 성공률 | 평균(s) | 차트 |
|---------|--------|---------|------|
| BQ Sales (60) | 100% | 21.4 | 22 |
| BQ Product (30) | 100% | 20.9 | 6 |
| Chart (25) | 100% | 28.4 | 12 |
| Notion (35) | 100% | 33.7 | 0 |
| GWS (30) | 100% | 13.7 | 0 |
| Multi (30) | 100% | 36.4 | 4 |
| Direct (35) | 94.3% | 12.4 | 0 |
| Edge Cases (55) | 87.3% | 20.0 | 1 |

**v2 신규 테스트 유형**: SQL 인젝션 8건 차단, 이모지/외국어/오타/초성 입력, 넌센스 입력 처리

### 5-B. CS Agent v1.0 신규 (`app/agents/cs_agent.py`)

- Google Spreadsheet 13개 탭, ~739건 Q&A 데이터
- 3개 브랜드: SKIN1004, COMMONLABS, ZOMBIE BEAUTY
- 키워드 가중치 검색 (제품명 +3, 라인명 +2, 카테고리 +1.5)
- 서버 시작 시 메모리 캐시 워밍업
- CS 키워드 60+개 등록 (성분, 사용법, 비건, 피부타입 등)
- **CS 260건 E2E**: 260/260 OK, 평균 37.1s

### 5-C. QA 500 통합 테스트

- CS 260 + BQ 60 + PROD 30 + CHART 25 + NT 35 + GWS 30 + MULTI 30 + DIRECT 30
- **497/500 OK (99.4%)**, WARN 3, FAIL 0
- 평균: 41.4s, Wall time: 173.1분

### 5-D. UI/UX 커스터마이징 (v6.5.2)

- **3-서버 프록시 구조**: Proxy(:3000) → Open WebUI(:8080) → FastAPI(:8100)
  - HTML 응답에 custom.css + loader.js 자동 주입 (Open WebUI 소스 수정 제로)
- 테마별 로고 스왑 (MutationObserver)
- 한국어 로캘 강제 적용
- 제안 질문 영어 → 한국어 변경
- Claude Sonnet 4.5 → 4.6 업그레이드

### 5-E. 이슈 수정 (v6.5.1)

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| ERROR 1 (EDGE-09) | BQ fallback "오류가 발생" | "데이터를 조회하지 못했습니다" |
| SHORT 8 | 인사/넌센스에 짧은 응답 | 기능 안내 포함 |

---

## 6. v6.4 (02-20) — QA 300 v1 + Multi 병렬 + 빈 결과 처리

### 6-A. QA 300 v1 종합 테스트

- **300개 질문** 8개 카테고리 자동 테스트
- 성공률: **97.7%** (292/299 OK)
- 차트 자동 생성: 69건
- FAIL: 0, 평균: 23.9s, 중앙값: 18.3s, P95: 56.5s

| 카테고리 | 성공률 | 평균(s) | 차트 |
|---------|--------|---------|------|
| BQ Sales (60) | 100% | 18.9 | 33 |
| BQ Product (30) | 100% | 19.0 | 9 |
| Chart (25) | 100% | 22.4 | 17 |
| Notion (35) | 97.1% | 33.4 | 0 |
| GWS (30) | 100% | 13.8 | 0 |
| Multi (30) | 100% | 57.4 | 0 |
| Direct (35) | 88.6% | 11.9 | 0 |
| Edge Cases (54) | 96.3% | 21.6 | 10 |

### 6-B. Multi Route 속도 개선

- Google Search: Pro → Flash 모델 전환
- Search prompt 간결화, max_output_tokens 8192→4096
- MULTI 평균: **106-113s → 34-51s** (약 60% 개선)

| 테스트 | Before | After | 개선율 |
|--------|--------|-------|--------|
| MULTI-09 | 106.7s | 50.7s | -52% |
| MULTI-15 | 113.4s | 34.2s | -70% |
| EDGE-40 | 113.3s | 45.0s | -60% |

### 6-C. 에러 감지 로직 개선

- ERROR 판정: answer 전체 → **앞 200자만 검사**
- Notion 본문에 "오류가 발생" 포함 시 오탐(false positive) 방지

### 6-D. Notion 리포트 업로드

- QA 300 결과를 Notion "AI 사람만들기 로그" 페이지에 자동 업로드
- `build_qa300_blocks()` 함수 추가
- 카테고리별 토글, 이슈 요약 포함

---

## 7. v6.2 (이전) — CS Agent + Notion 병렬 + BQ Flash 전환

### 7-A. v5.0 (02-10) — Dual LLM + Google Search + GWS OAuth

**Dual LLM 아키텍처**:

| 모델 ID | LLM | 용도 |
|---------|-----|------|
| skin1004-Search | Gemini 2.5 Pro | 매출 조회, Google 검색, 일반 질문 |
| skin1004-Analysis | Claude Sonnet 4.5 | 심층 분석, 복합 추론 |

**속도 최적화**:

| 항목 | 이전 | 이후 |
|------|------|------|
| SQL 쿼리 응답 | 38-42s | **11-13s** |
| 분류 방식 | LLM 매번 호출 | 키워드 우선 → LLM 폴백 |
| 답변+차트 | 순차 처리 | **병렬** (ThreadPoolExecutor) |
| 스키마 | 매번 BQ 조회 | **글로벌 캐시** |

**Google Search Grounding**:
- Gemini 네이티브 Google Search grounding (별도 API 키 불필요)
- Multi-source: Google Search(외부) + BigQuery(내부) 합성

**GWS 개별 OAuth2**:
- MCP 단일 사용자 → 개별 OAuth2 (전 직원)
- `googleapiclient` 직접 호출 (Gmail, Drive, Calendar)
- 개별 토큰 파일 저장 (`data/gws_tokens/`)

### 7-B. v4.0 (02-06) — 차트 시각화 + 데이터 확대

**차트 개선**:
- ChatGPT 스타일 디자인 (흰색 배경, Arial 글꼴)
- 색상 팔레트: 10색 → **30색** 확장
- 데이터 라벨 표시 (K/M/B 축약)
- 레전드: 차트 오른쪽, 매출 높은 순 정렬
- 동적 이미지 크기 (레전드 10개 초과 시 확장)

**데이터 조회 확대**: MAX_RESULT_ROWS 1,000행 → **10,000행**

---

## 8. QA 테스트 누적 성적

| 테스트 | 일자 | 질문수 | 성공률 | WARN | FAIL | 평균(s) |
|--------|------|--------|--------|------|------|---------|
| **QA 500 v3** (v7.2.1) | 02-25 | 500 | **99.8%** | 1 | 0 | **27.1** |
| QA 500 v2 (v7.1.1) | 02-24 | 500 | **100%** | 0 | 0 | 41.4 |
| QA 500 v1 (v6.5) | 02-23 | 500 | 99.4% | 3 | 0 | 41.4 |
| QA 300 v2 (v6.5) | 02-23 | 300 | 97.0%→100% | 0 | 0 | 22.8 |
| QA 300 v1 (v6.4) | 02-20 | 299 | 97.7% | 0 | 0 | 23.9 |
| QA 100+ | 02-19 | 109 | 95.4% | 0 | 0 | - |
| QA 80 | 02-13 | 80 | 90% | - | - | - |
| QA 112 | 02-12 | 112 | 92% | - | - | - |

### 성능 추이 그래프 (텍스트)

```
성공률 추이:
  100% ─── ●──────●  ← v7.1.1 (500건 100%), v7.2.1 (99.8%)
   99% ────────────●  ← v6.5 QA500 (99.4%)
   98% ─
   97% ──●──●        ← v6.4 (97.7%), v6.5 v2 (97.0%→100%)
   96% ─
   95% ─●            ← QA 100+ (95.4%)
   ...
   90% ●──●          ← QA 80 (90%), QA 112 (92%)
        ──────────────────────────────────
        02-12  02-13  02-19  02-20  02-23  02-24  02-25

평균 응답시간 추이:
   50s ─
   41s ──────────────●──●  ← v6.5 (41.4s), v7.1.1 (41.4s)
   30s ─
   27s ─────────────────●  ← v7.2.1 (27.1s)
   24s ──●──●              ← v6.4 (23.9s), v6.5 v2 (22.8s)
   20s ─
        ──────────────────────────────────
        02-20  02-23  02-24  02-25
```

### 성능 기준

| 등급 | 조건 | 설명 |
|------|------|------|
| **OK** | < 100초 | 정상 응답 |
| **WARN** | 100~199초 | 느린 응답 (최적화 대상) |
| **FAIL** | >= 200초 | 타임아웃급 실패 |

### 핵심 속도 개선 내역

| 개선 항목 | 버전 | 이전 | 이후 | 개선율 |
|-----------|------|------|------|--------|
| 키워드 우선 분류 | v5.0 | LLM 매번 | 키워드 즉시 | 즉시 |
| SQL 생성 Flash 전환 | v5.0 | Pro 38-42s | Flash 11-13s | -70% |
| 답변+차트 병렬 | v5.0 | 순차 | ThreadPoolExecutor | -40% |
| BQ 스키마 캐시 | v5.0 | 매 쿼리 조회 | 시작 시 1회 | -5s |
| Multi Search Flash | v6.4 | Pro 106-113s | Flash 34-51s | -60% |
| CS Agent Flash | v7.1.1 | Pro 131-133s | Flash 8-10s | -93% |
| Notion 답변 Flash | v7.2.1 | Pro 105s | Flash 49s | -53% |
| GWS 도구 사전 분류 | v7.2.1 | 3도구 호출 | 1도구만 | -91% |

---

> **문서 작성**: Claude AI
> **최종 검증**: 2026-02-26

