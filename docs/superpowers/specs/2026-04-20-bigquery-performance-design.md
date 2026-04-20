# BigQuery 응답 속도 개선 설계

**Date**: 2026-04-20  
**Status**: Approved  
**Scope**: 실사용자 BigQuery 라우트 응답 속도 개선 (A+B 조합)

---

## 문제 정의

Eval run 6 기준 BigQuery 라우트 성능:
- 177개 질문 / 평균 **27s** / p95 **43s**
- 전체 450 질문 중 39%가 BigQuery 라우트
- 병목: BQ 실행 15-20s (전체 응답의 ~70%)
- SQL 캐시 히트율: 1.7% (eval 질문이 모두 다름 — 프로덕션에서는 더 높을 것)

---

## 목표

| 지표 | 현재 | 목표 |
|------|------|------|
| 첫 응답 피드백 (TTFB) | ~27s 침묵 | **≤ 1s** |
| BigQuery 평균 응답 | 27s | **10-15s** |
| BQ p95 | 43s | **25s 이하** |

---

## 방안 A — 조기 SSE 피드백

### 목적
BQ 실행이 시작되는 시점에 즉시 사용자에게 피드백 전송. 실제 속도는 같지만 체감 응답성을 개선.

### 변경 위치
- `app/api/routes.py` — 스트리밍 핸들러
- `app/agents/orchestrator.py` — 라우트 결정 콜백

### 동작 흐름
```
1. /v1/chat/completions 요청 수신
2. 오케스트레이터 라우트 결정 → "bigquery" 확인
3. SSE chunk 즉시 전송: "📊 데이터를 조회하고 있습니다..."
4. BQ 실행 (15-20s)
5. 실제 답변 SSE 스트리밍
```

### 구현 방식
오케스트레이터에 `status_callback: Callable[[str], None]` 파라미터 추가.  
라우트 결정 직후 콜백 호출 → routes.py SSE generator가 즉시 chunk 전송.

### 제약
- 기존 스트리밍 구조 유지 (StreamingResponse 변경 없음)
- 로딩 메시지는 최종 답변에서 제거 (중복 방지)

---

## 방안 B — SQL 파티션 필터 강제

### 목적
BQ는 스캔 바이트 기준으로 실행 시간이 결정됨. 날짜 파티션 필터 없이 SALES_ALL_Backup 전체를 스캔하면 15-20s. 필터 적용 시 5-8s로 단축 가능.

### 변경 위치
1. `prompts/sql_generator.txt` — 파티션 최적화 규칙 추가
2. `app/agents/sql_agent.py` — `validate_sql_node` 후처리 레이어 추가

### 프롬프트 추가 규칙
```
⚠️ BigQuery 파티션 최적화 필수:
1. Date 컬럼이 있는 모든 테이블: WHERE Date BETWEEN ... AND ... 반드시 포함
2. SELECT * 금지 — 답변에 필요한 컬럼만 명시
3. 집계 전 서브쿼리에서 WHERE로 범위 먼저 제한
4. 사용하지 않는 컬럼 JOIN 금지
5. 기간 명시 없는 질문: 기본값 최근 90일 적용
```

### SQL 후처리 검증 레이어 (`sql_agent.py`)
`validate_sql_node` 통과 후, `execute_sql` 직전에 추가 검증:

```python
def _enforce_partition_filter(sql: str, query: str) -> str:
    """대형 테이블에 날짜 필터 없으면 자동 주입."""
    LARGE_TABLES = ["SALES_ALL_Backup", "integrated_ad", "Integrated_marketing_cost"]
    has_date_filter = re.search(r'WHERE.*Date', sql, re.IGNORECASE)
    targets_large = any(t in sql for t in LARGE_TABLES)
    
    if targets_large and not has_date_filter:
        # 기간 명시 없는 질문 → 최근 90일 자동 주입
        # Flash에 재생성 요청 (직접 SQL 수정보다 안전)
        return _request_sql_with_filter(sql, query)
    return sql
```

Flash 재생성 방식 채택 이유: SQL 직접 수정은 서브쿼리/CTE 구조 깨질 위험 있음.

### SELECT * 감지
생성된 SQL에 `SELECT *` 포함 시 → Flash에 컬럼 명시 재생성 요청 (1회 한정).

---

## 파일 변경 목록

| 파일 | 변경 내용 |
|------|----------|
| `app/api/routes.py` | status_callback 연결, 조기 SSE chunk 전송 |
| `app/agents/orchestrator.py` | status_callback 파라미터 추가, 라우트 결정 시 호출 |
| `prompts/sql_generator.txt` | 파티션 최적화 규칙 섹션 추가 |
| `app/agents/sql_agent.py` | `_enforce_partition_filter` 함수 추가, validate_sql_node 후 호출 |

---

## 테스트 기준

- [ ] BigQuery 질문 후 1초 이내 SSE 청크 수신 확인
- [ ] SALES_ALL_Backup 쿼리에 날짜 필터 없을 시 자동 주입 동작
- [ ] SELECT * 포함 SQL 재생성 트리거 동작
- [ ] 기존 정상 쿼리에 불필요한 필터 추가되지 않음
- [ ] Eval run 재실행 후 BigQuery 평균 응답 ≤ 15s

---

## 범위 밖

- BQ 결과 캐시 (결과값이 매일 변하므로 제외)
- MariaDB 야간 집계 스냅샷 (C안, 별도 작업으로 분리)
- Eval 파이프라인 병렬화 (병목 확인됨, 별도 이슈로 분리)
- BQ BI Engine / 슬롯 예약 (인프라 비용 결정 필요)
