# Update Log — 2026-02-25 (v7.2.1 광범위 쿼리 수정 + Safety System + Coherence)

## 변경 사항

### 0. 광범위 쿼리 데이터 절삭 문제 수정 (v7.2.1)

#### 0-A. 문제
- "국가별 제품 업체 2024년~2026년 1월까지 월별 매출 및 판매수량" 같은 3개+ 차원 쿼리에서:
  - SQL이 `GROUP BY Country, Company_Name, SET, month` → 수만~십만 행
  - `ORDER BY` 없이 알파벳순 → 1000행 LIMIT에 걸려 "가나" 데이터만 반환
  - `results[:20]`만 LLM에 전달 → 가나 2건만 보고 답변 생성
  - **결과**: 사용자는 전체 국가 데이터를 원했으나 가나만 받음

#### 0-B. 수정
1. **SQL 프롬프트 규칙 17 추가** (`prompts/sql_generator.txt`):
   - 3개+ 차원 쿼리 시 `ORDER BY total_revenue DESC` 필수
   - LIMIT 1000은 유지하되 매출 높은 순서로 정렬 → 핵심 데이터 우선
2. **Smart Preview** (`app/agents/sql_agent.py` — `_build_smart_preview()`):
   - 100행 초과 결과 → aggregate summary + top 20 by revenue를 LLM에 전달
   - 매출/수량 컬럼 자동 감지 + `_is_numeric_col()` 검증 (Country→count 오탐 방지)
3. **절삭 경고**: 1000행 LIMIT 도달 시 프롬프트에 경고 삽입

#### 0-C. 수정 파일
| 파일 | 변경 |
|------|------|
| `prompts/sql_generator.txt` | 규칙 17 (광범위 쿼리 ORDER BY DESC 필수) |
| `app/agents/sql_agent.py` | `_build_smart_preview()`, 스마트 프리뷰 라우팅, 절삭 경고 |

#### 0-D. 검증
- "국가별 제품 업체 월별 매출" → 미국, 글로벌_플랫폼, 베트남 등 다양한 국가 포함 (38.9s OK)
- 기존 BQ 쿼리 10건 regression: 10/10 OK (19-39s)

### 1. 안전장치 시스템 신규 (`app/core/safety.py`)

#### 1-A. MaintenanceManager (BigQuery 점검 모드)
- **수동 토글**: `POST /admin/maintenance?action=on&reason=...` / `action=off`
- **자동 감지**: 60초 주기로 `__TABLES__` 메타데이터 쿼리 (비용 0원)
  - baseline 대비 50% 이상 행 수 감소 → 자동 점검모드 ON
  - 90% 이상 복구 → 자동 점검모드 OFF
- **BQ 쿼리 차단**: 점검 중 bigquery/multi 라우트에서 SQL 실행 안 함 → "데이터 점검 중" 메시지 반환

#### 1-B. CircuitBreaker (서비스별 차단기)
- 서비스별 인스턴스: `bigquery`, `gemini`, `notion`
- 연속 3회 실패 → OPEN (호출 차단) → 60초 쿨다운 → HALF_OPEN (1건 시도) → 성공 시 CLOSED
- `execute_query()` 래핑: BigQuery 쿼리 전 circuit breaker 확인

#### 1-C. 프론트엔드 UI
- **상단 점검 배너**: 주황색 슬라이드인 배너 ("데이터 점검 중 — 매출 조회 일시 중단")
- **사이드바 DB 상태 패널**: 5개 서비스 초록/빨강 dot 실시간 표시 (30초 폴링)
  - BigQuery 매출, BigQuery 제품, Notion 문서, CS Q&A, Google Workspace

### 2. 질문-답변 정합성 검증 (`_verify_coherence`)

#### 2-A. Orchestrator 레벨 (`app/agents/orchestrator.py`)
- `_verify_coherence()` 메서드 추가: Flash로 질문 범위 vs 답변 범위 일치 여부 검증
- 불일치 시 답변 상단에 경고 배너 삽입: `> ⚠️ **참고**: {issue}`
- direct/multi 라우트는 제외 (multi는 합성 프롬프트가 이미 검증)

#### 2-B. 각 에이전트 프롬프트 강화
- **sql_agent.py**: 오늘 날짜 컨텍스트 + 데이터 범위 감지 + 3개 정합성 규칙 (8/9/10)
- **cs_agent.py**: 4개 정합성 규칙 (7/8/9/10) — 다른 제품 정보 대체 금지
- **notion_agent.py**: 3개 정합성 규칙 (6/7/8) — 찾을 수 없으면 솔직히 답변

### 3. WARN 3건 원인 분석 및 수정

#### 3-A. GWS-26: 114.3s → 9.9s (-91%)
- **원인**: ReAct 에이전트가 캘린더만 필요한 쿼리에 Gmail/Drive 도구까지 반복 호출
- **수정** (`gws_agent.py`):
  - `_classify_tool()` 메서드 추가: 쿼리 키워드로 calendar/gmail/drive 사전 분류
  - 단일 도구만 필요한 경우 해당 도구만 에이전트에 전달
  - 시스템 프롬프트에 "도구 1번만 호출" 강제 + `recursion_limit` 10→6

#### 3-B. NT-17: 105.4s → 49.0s (-53%)
- **원인**: Notion 답변 생성에 Pro/Claude 사용 (80-100s) — 포맷팅 작업인데 과도한 모델
- **수정** (`notion_agent.py`):
  - `_generate_answer()`에서 `get_llm_client(model_type)` → `get_flash_client()` 전환
  - Notion 답변 포맷팅은 경량 작업 → Flash로 충분

#### 3-C. MULTI-14: 114.0s → 43.0s (-62%)
- **원인**: 합성 후 coherence 검증이 중복 실행 (~10s 추가)
- **수정** (`orchestrator.py`):
  - `_verify_coherence()`에서 multi 라우트 제외 (합성 프롬프트가 이미 scope 검증)

### 4. API 엔드포인트 추가 (`app/api/routes.py`)

| Method | Path | 용도 |
|--------|------|------|
| POST | `/admin/maintenance?action=on/off` | 수동 점검모드 토글 |
| GET | `/admin/maintenance/status` | 점검 상태 폴링 |
| GET | `/safety/status` | 전체 안전장치 대시보드 |

### 5. 백그라운드 태스크 (`app/main.py`)
- `_start_maintenance_monitor()`: lifespan에서 자동감지 루프 시작 (60초 주기)

## 수정 파일 목록

| 파일 | 변경 | 설명 |
|------|------|------|
| `app/core/safety.py` | **신규** | MaintenanceManager + CircuitBreaker 코어 모듈 |
| `app/agents/orchestrator.py` | 수정 | 점검모드 가드, coherence 검증, multi 제외 |
| `app/agents/sql_agent.py` | 수정 | 날짜 컨텍스트, 정합성 규칙 추가 |
| `app/agents/cs_agent.py` | 수정 | 정합성 규칙 4개 추가 |
| `app/agents/notion_agent.py` | 수정 | Flash 전환, 정합성 규칙 3개 추가 |
| `app/agents/gws_agent.py` | 수정 | 도구 사전 분류, recursion_limit 축소 |
| `app/api/routes.py` | 수정 | 3개 관리 엔드포인트 추가 |
| `app/main.py` | 수정 | 자동감지 백그라운드 태스크 |
| `app/core/bigquery.py` | 수정 | circuit breaker 래핑 |
| `app/static/loader.js` | 수정 | 점검 배너 + DB 상태 패널 |
| `app/static/custom.css` | 수정 | 배너 + 패널 스타일 |

## 테스트 결과

### 점검모드 E2E 테스트
1. `POST /admin/maintenance?action=on` → 활성화 ✅
2. 매출 질문 → "데이터 점검 중" 메시지 ✅ (SQL 미실행)
3. 상단 주황색 배너 표시 ✅
4. 사이드바 BigQuery 빨강 dot ✅
5. `POST /admin/maintenance?action=off` → 해제 ✅
6. 동일 질문 → 정상 데이터 응답 ✅
7. 배너 사라짐 + 사이드바 초록 복구 ✅

### 정합성 검증 테스트
| 질문 | 기대 | 결과 |
|------|------|------|
| 2026년 매출 알려달라 | 부분 데이터 경고 | ✅ "1~2월 데이터만 제공됨" |
| 2026년 전체 국가 매출 | 부분 데이터 경고 | ✅ "2월 24일까지의 데이터" |
| 2030년 매출 | 미래 데이터 없음 경고 | ✅ "2030년 데이터 없음" |
| 올해 연간 매출 | 부분 데이터 경고 | ✅ "2026년 데이터는 1-2월만" |

### WARN 수정 검증
| ID | 이전 | 이후 | 개선율 |
|----|------|------|--------|
| GWS-26 | 114.3s (WARN) | 9.9s (OK) | -91% |
| NT-17 | 105.4s (WARN) | 49.0s (OK) | -53% |
| MULTI-14 | 114.0s (WARN) | 43.0s (OK) | -62% |

### QA 500 전체파트 종합 E2E 테스트 (v7.2.1 — 광범위 쿼리 수정 포함)

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

- **99.8% PASS** (499 OK, 1 WARN, 0 FAIL)
- WARN 1건: MULTI-29 "TikTok Shop 글로벌 확장 전략과 우리 틱톡 매출 전망" (108.2s) — multi route 웹검색+BQ 복합
- p50=21.8s, p95=59.8s, min=5.8s, max=108.2s
- Wall time: 113.2분 (2그룹 병렬)

### 6. Coherence 검증 False Positive 수정

#### 6-A. 문제 분석
- QA 500 결과에서 147/500 (29.4%) 답변에 불필요한 `⚠️ 참고` 경고가 삽입됨
- 원인: coherence 프롬프트에 SKIN1004 컨텍스트 부재, 판단 기준 과도하게 엄격

#### 6-B. False Positive 카테고리별 분포 (수정 전)
| 카테고리 | FP 수 | 주 원인 |
|----------|--------|---------|
| CS | 61 | DB 한계("찾을 수 없음")를 불일치로 판단 |
| MULTI | 20 | 합성 답변의 부분성을 오류로 판단 |
| NT | 17 | 문서 미발견을 불일치로 판단 |
| GWS | 14 | API 응답 범위를 불일치로 판단 |
| BQ | 14 | 부분 데이터 경고를 이중 경고 |
| CHART | 10 | 차트 데이터 제한을 오류로 판단 |
| DIRECT | 6 | 일반 답변을 불완전으로 판단 |
| PROD | 5 | 제품 데이터 한계를 오류로 판단 |

#### 6-C. 수정 내용 (`app/agents/orchestrator.py` — `_verify_coherence()`)
1. **CS route 완전 skip**: CS DB 한계는 정상 동작
2. **Limitation phrase 사전 감지**: 답변에 "찾을 수 없", "확인되지 않", "⚠️" 등이 이미 포함되면 skip
3. **SKIN1004 컨텍스트 추가**: 프롬프트에 "SKIN1004 화장품 회사 내부 AI 시스템" 명시
4. **판단 기준 축소**: 제품/국가/채널 **완전 불일치**만 flag (부분 데이터, 미발견은 정상)
5. **direct/multi route skip**: 이미 적용됨

#### 6-D. 수정 후 검증 (40건 샘플 테스트)
| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| False Positive | 29.4% (147/500) | **0% (0/40)** |
| WARN | 0 | 0 |
| ERROR | 0 | 0 |
| 평균 응답시간 | 34.8s | **18.3s** |
