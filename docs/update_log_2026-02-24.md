# Update Log — 2026-02-24 (v7.1.1 Chart Comprehensive Fix)

## 변경 사항

### 1. 차트 종합 수정 — 모든 차트 타입 대응 (`app/core/chart.py`)

#### 1-A. 공통 개선 (v7.1.0 → v7.1.1)
- **공통 시계열 플래그**: `_TIME_HINTS` set으로 중복 제거 (월/분기/Q1~Q4/Jan~Dec/1월~12월)
- **bar → horizontal_bar 자동 전환**: 25자 초과 라벨(제품명 등) + 비시계열 → 자동으로 가로 바 차트 전환
- **가로 차트 라벨 길이 확장**: vertical 25자 → horizontal 40자 (가로 방향에선 더 긴 라벨 표시 가능)
- **가로 차트 이미지 높이 자동 조절**: 카테고리 8개 초과 시 이미지 높이 증가

#### 1-B. 차트별 내림차순 정렬
| 차트 타입 | v7.1.0 | v7.1.1 |
|----------|--------|--------|
| bar | ✅ | ✅ (시계열 플래그 공유) |
| horizontal_bar | ⚠️ 역순 (큰값 하단) | ✅ 오름차순 정렬 → Plotly에서 큰값 상단 |
| grouped_bar | ✅ | ✅ (시계열 플래그 공유) |
| stacked_bar | ❌ 미적용 | ✅ 합계 기준 내림차순 추가 |

#### 1-C. 긴 라벨 가로 방향 자동 전환
| 차트 타입 | v7.1.0 | v7.1.1 |
|----------|--------|--------|
| bar (단일) | ❌ | ✅ → horizontal_bar 자동 전환 |
| grouped_bar | ❌ | ✅ orientation="h" + reversed 정렬 |
| stacked_bar | ❌ | ✅ orientation="h" + reversed 정렬 |

#### 1-D. y_col 축 자동수정 강화
- **v7.1.0**: `_find_numeric_column(exclude=[x_col, y_col])` — x_col이 숫자여도 제외 → 2컬럼 데이터에서 차트 생성 실패
- **v7.1.1**: x_col이 숫자이면 단순 swap (`x_col, y_col = y_col, x_col`) → 2컬럼 데이터에서도 정상 차트 생성
  - Before: "국가별 매출" → chart_no_numeric_column_found → 차트 없음
  - After: "국가별 매출" → 축 swap → 정상 바 차트 ✅

#### 1-E. 차트 설정 프롬프트 강화
- bar: "카테고리 5개 이하 + 이름이 짧을 때만" 명시
- horizontal_bar: "제품명/브랜드명/SKU명 등 긴 텍스트 라벨 시 **반드시 사용**" 강화
- grouped_bar/stacked_bar: 사용 예시 추가

### 2. 후속질문 품질 개선 (`app/agents/orchestrator.py`)
- **시스템 태스크 라우팅 최적화**: Open WebUI의 title/tag/follow-up 생성 요청이 BigQuery로 잘못 라우팅되는 문제 수정
  - `### Task:` 접두사 감지 → `direct` 즉시 라우팅 (LLM 재분류 스킵)
  - 응답시간: ~15s+ → ~9s (-40%)
- **커스텀 후속질문 프롬프트**: 명확하게 답변 가능한 질문만 생성
  - ✅ "2024년 미국 아마존 월별 매출 보여줘" (구체적 데이터 조회)
  - ❌ "~일까요?", "~궁금해요" (모호한 질문)
- **타이틀/태그 생성 시 대화 컨텍스트 전달**: 대화 이력 미포함으로 제목이 일반적이던 문제 수정

### 3. CS Agent 브랜드 별칭 & Flash 전환 (`app/agents/cs_agent.py`)
- **브랜드 별칭 매칭**: 한국어 브랜드명 ↔ 영어 DB 값 매핑
  - "커먼랩스" → COMMONLABS, "좀비뷰티" → ZOMBIE BEAUTY
- **Flash LLM 전환**: CS 답변 생성을 Pro → Flash로 전환 (단순 Q&A 합성은 Flash로 충분)
  - CS-236 "커먼랩스 비건이야?": 131s → 9.8s (-93%)
  - CS-237 "좀비뷰티 비건 인증?": 133s → 8.1s (-94%)

## 수정 파일 목록

| 파일 | 변경 | 설명 |
|------|------|------|
| `app/core/chart.py` | 수정 | 전체 차트 타입 종합 수정 (정렬, 가로 전환, 축 swap, 프롬프트) |
| `app/agents/orchestrator.py` | 수정 | 시스템 태스크 라우팅, 후속질문 프롬프트, 타이틀 컨텍스트 |
| `app/agents/cs_agent.py` | 수정 | 브랜드 별칭, Flash LLM 전환 |

## 테스트 결과

### 차트 종합 수정 검증 (v7.1.1)

| 테스트 | 차트 타입 | 결과 | 시간 |
|--------|----------|------|------|
| 상위 5개 제품 판매+매출 시각화 | grouped_bar → horizontal | ✅ 제품명 y축, 내림차순, 데이터 라벨 | 27.3s |
| 상위 3개 제품 판매량+매출 비교 | grouped_bar → horizontal | ✅ 가로 전환, 최대값 상단 | 25.5s |
| 동남아 국가별 매출 상위 5개국 | bar (세로) | ✅ 내림차순, 짧은 라벨 세로 유지 | 24.6s |
| 2024년 월별 매출 추이 | line | ✅ 시계열 순서 유지, 가로 전환 안 됨 | 21.6s |

### 이전 수정 검증 (v7.1.0)

#### 후속질문 검증
- Follow-up 생성 시간: 9.0s (기존 ~15s+)
- JSON 형식 ✅, 구체적 질문 ✅, `follow_ups` 키 ✅

#### 500건 E2E 재검증 (WARN 수정 후)
- CS-236: 131.0s → 9.8s ✅
- CS-237: 133.2s → 8.1s ✅
- GWS-28: 114.6s → 23.5s ✅
- 최종: **500/500 OK (100%)**
