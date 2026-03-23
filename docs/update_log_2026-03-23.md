# Update Log — 2026-03-23 (v8.5~v9.0 속도 대폭 개선 + 실시간 스트리밍 + QA 강화)

## 주요 변경 사항

### 1. 실시간 스트리밍 구현 (v8.7~v9.0)
- **Direct 라우트**: Claude Sonnet 실시간 스트리밍 — TTFB 9.5초 → **2초** (ChatGPT급)
- **BQ 라우트**: SQL 실행 후 답변 포맷을 Flash 스트리밍으로 — TTFB **9.4초부터 타이핑 시작**
- **스트리밍 아키텍처**: `route_and_stream` async generator + thread→asyncio.Queue 패턴
- **렌더링 부드럽게**: 150ms throttle markdown + CSS fadeInContent 애니메이션
- **중복 전송 제거**: 스트리밍 후 done 이벤트에서 중복 답변 전송 방지
- **AbortController**: 스트리밍 중 대화 전환 시 안전 abort

### 2. Direct 라우트 Claude Sonnet 전환 (v8.8)
- 일반 대화 LLM: Gemini Pro → **Claude Sonnet 4** (TTFB 7초 → 1.7초)
- BQ SQL 생성/차트: Gemini Flash 유지 (SQL 특화)
- Claude `generate_stream()`, `generate_with_history_stream()` 메서드 추가

### 3. MariaDB SQL 캐시 복구 (v8.6)
- `.env` MARIADB_HOST: `localhost` → `127.0.0.1` (소켓 vs TCP 이슈 해결)
- 동일 질문 반복 시 SQL 생성 **5초 → 0초** 스킵 (BQ는 매번 최신 데이터로 실행)
- 캐시 범위: DB 전체 공유 (같은 brand_filter 그룹 내)

### 4. SQL 프롬프트 경량화 + 속도 개선 (v8.5)
- SQL 프롬프트: 65K → **57K** (제품 카탈로그 축약, 중복 예시 제거)
- SQL 생성: 7.5초 → **4.5초**, 전체: 18초 → **9.5초** (간단 쿼리 -47%)

### 5. SQL 복잡 쿼리 강화 (v8.3~v8.4)
- **CTE(WITH절) 허용**: 이동평균, 누적합, 전년대비, 서브쿼리 지원
- **SQL 생성 강제**: "조회하지 못했습니다" / 되묻기 응답 절대 금지
- **SQL 생성 실패 시 자동 재시도** (강화 프롬프트)
- **SQL max_output_tokens 8192** (CTE 잘림 방지)
- **모호한 질문 기본값**: "요즘"=3개월, "잘 팔리는"=TOP 10, "실적 어때"=월별 추이
- **Product YoY/MoM/Category 비교 예시 SQL 6개** 추가
- **Timeout 방지**: 전국가 YoY → TOP 10 제한, 누적 → 최근 12개월

### 6. 회사 정보 시스템 프롬프트 상세화
- 크레이버코퍼레이션 공식 정보: 공동대표 전항일/천주혁, 설립 2014년 8월
- 소재지, 브랜드 3개, 글로벌 리테일(Costco, ULTA, H&M), 슬로건 "WHAT DO YOU CRAVE?"
- "회사 소개" 질문 → 웹검색 스킵, 시스템 프롬프트로 즉시 답변

### 7. 라우팅 개선
- **_DIRECT_LOCK**: "회사", "소개", "재밌" 등 direct 확정 키워드 → LLM 재분류 건너뛰기
- **웹검색 키워드 확대**: 넷플릭스, 영화, 드라마, 유튜브, 스포츠, 주식 등 추가
- **연도 참조(2024~2029년) 질문 자동 웹검색**
- **Claude thinking 노출 방지**: 내부 사고 과정 출력 금지 규칙

### 8. 프론트엔드 개선
- **후속질문 칩 컴포넌트 제거** (LLM 인라인 💡 블록으로 대체)
- **차트 x축 자동 매칭**: 컬럼명 불일치 시 case-insensitive + fallback
- **admin brand_filter 버그 수정**: 그룹 미지정 시 SK,CL 하드코딩 제거

### 9. QA 테스트 (Playwright E2E + API)
- **QA 100 (API)**: 9개 테이블 × 100문항 = 900건, **99.6% PASS**, avg 41.8s
- **Playwright E2E**: 100문항 실제 브라우저 테스트, **93% PASS**, avg 31.5s
- **jp2 시트 리테스트**: 26건 이슈 중 **20건 해결 (77%)**, Timeout **4→0건**

## 속도 개선 요약

| 항목 | 이전 | 이후 | 개선 |
|------|------|------|------|
| Direct 일반 대화 (TTFB) | 9.5s | **2.0s** | -79% |
| BQ 간단 쿼리 | 18.1s | **9.5s** | -47% |
| BQ 캐시 히트 | 18.1s | **7.5s** | -59% |
| BQ 복잡 쿼리 | 27s | **22s** | -19% |
| Direct 간단 인사 | 4.7s | **2.6s** | -45% |
| 웹검색 질문 | 17.7s | **7.2s** | -59% |

## 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/core/llm.py` | Claude generate_stream, generate_with_history_stream, Gemini generate_stream |
| `app/agents/orchestrator.py` | route_and_stream, Claude 전환, DIRECT_LOCK, 회사정보, thinking 방지 |
| `app/agents/sql_agent.py` | run_sql_agent_stream, SQL 재시도, brand_filter 기본값 수정 |
| `app/api/routes.py` | route_and_stream 기반 SSE, no-cache 헤더 |
| `app/core/chart.py` | x/y 컬럼 자동 매칭 |
| `app/core/prompt_fragments.py` | 서론 간결화 |
| `app/frontend/chat.js` | 150ms throttle, AbortController, 후속칩 제거 |
| `app/static/style.css` | fadeInContent 애니메이션 |
| `prompts/sql_generator.txt` | CTE 허용, 복잡쿼리 강제, Product YoY/MoM, 프롬프트 경량화 |
