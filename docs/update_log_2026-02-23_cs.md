# Update Log — 2026-02-23 (CS Agent v1.0)

## 변경 사항

### 1. CS Agent 신규 구현 (`app/agents/cs_agent.py`)
- Google Spreadsheet 13개 탭에서 737건 Q&A 데이터 로드
- 3개 브랜드 통합: SKIN1004, COMMONLABS, ZOMBIE BEAUTY
- 키워드 가중치 검색 (제품명 +3, 라인명 +2, 카테고리 +1.5)
- 서버 시작 시 메모리 캐시 워밍업 (Google Sheets API batchGet)
- CS 전문 프롬프트로 상담원 톤 답변 생성

### 2. 오케스트레이터 라우팅 업데이트 (`app/agents/orchestrator.py`)
- `cs` 라우트 추가 (6번째 라우트)
- CS 키워드 60+개 등록 (제품 라인, 브랜드, 성분, 사용법, 피부 타입 등)
- 라우팅 우선순위: Notion > GWS > CS > BigQuery > Multi > Direct
- CS + 매출 키워드 동시 존재 시 BigQuery 우선 (강한 데이터 키워드만 체크)

### 3. 설정 및 인프라
- `.env`에 `CS_SPREADSHEET_ID` 추가
- `app/config.py`에 `cs_spreadsheet_id` 필드 추가
- `app/main.py`에 CS DB 워밍업 추가 (서버 시작 시 자동 로드)

## 테스트 결과

### Phase 1: 라우팅 정확도
- **300개 질문** (CS 260 + BQ 25 + Notion 10 + GWS 5)
- 결과: **300/300 (100%)**

### Phase 2: CS 검색 품질
- **260개 CS 질문**에 대한 Q&A 검색 적중률
- 결과: **259/260 (99.6%)**

### Phase 3: API E2E
- **260개 CS 질문** 실제 API 호출 테스트 (2개 병렬 그룹)
- 결과: **260/260 OK** (WARN: 0, FAIL: 0, ERROR: 0)
- 평균 응답 시간: **37.1초**
- 총 Wall time: 80.6분

### 응답 시간 분포
| 구간 | 건수 | 비율 |
|------|------|------|
| 0-20s | 8 | 3.1% |
| 20-30s | 52 | 20.0% |
| 30-40s | 118 | 45.4% |
| 40-50s | 62 | 23.8% |
| 50-60s | 20 | 7.7% |
| 60s+ (WARN) | 0 | 0% |

## 수정 파일 목록
| 파일 | 변경 | 설명 |
|------|------|------|
| `app/agents/cs_agent.py` | 신규 | CS Agent 전체 구현 (313줄) |
| `app/agents/orchestrator.py` | 수정 | CS 라우팅 + 핸들러 + 키워드 60+개 |
| `app/config.py` | 수정 | cs_spreadsheet_id 필드 추가 |
| `.env` | 수정 | CS_SPREADSHEET_ID 추가 |
| `app/main.py` | 수정 | CS DB 워밍업 함수 추가 |
| `docs/SKIN1004_Enterprise_AI_PRD_v5.md` | 수정 | v7.0.0 CS Agent 섹션 추가 |

### Phase 4: 전체파트 통합 E2E (500건)
- **500개 질문**: CS 260 + BQ 60 + PROD 30 + CHART 25 + NT 35 + GWS 30 + MULTI 30 + DIRECT 30
- 2개 병렬 그룹으로 실행
- 결과: **497/500 OK (99.4%)**, WARN 3, FAIL 0
- 평균 응답 시간: **41.4초**
- 총 Wall time: 173.1분

### 카테고리별 결과
| Category | OK | WARN | Total | Avg(s) |
|----------|-----|------|-------|--------|
| BQ | 60 | 0 | 60 | 42.3 |
| CHART | 25 | 0 | 25 | 54.6 |
| CS | 258 | 2 | 260 | 40.6 |
| DIRECT | 30 | 0 | 30 | 28.9 |
| GWS | 29 | 1 | 30 | 20.6 |
| MULTI | 30 | 0 | 30 | 49.0 |
| NT | 35 | 0 | 35 | 53.1 |
| PROD | 30 | 0 | 30 | 47.3 |

### WARN 상세
| ID | Time | Query |
|----|------|-------|
| CS-236 | 131.0s | 커먼랩스 비건이야? |
| CS-237 | 133.2s | 좀비뷰티 비건 인증? |
| GWS-28 | 114.6s | 메일함에서 shipping 관련 메일 찾아줘 |

## 이슈 해결 내역
1. **403 Permission Error**: 시스템 환경변수의 서비스 계정과 .env 서비스 계정이 다른 문제 → gspread 계정으로 스프레드시트 공유
2. **헤더 자동 감지**: 탭마다 제목/설명 행이 있어 row 0이 헤더가 아닌 문제 → rows 0-9 스캔하여 Q&A 키워드 포함 행 탐색
3. **라우팅 오분류**: "라인"이 DATA 키워드에 포함되어 CS 질문이 BQ로 빠지는 문제 → 강한 데이터 키워드(매출, 수량, 주문 등)만 CS 우선 해제
