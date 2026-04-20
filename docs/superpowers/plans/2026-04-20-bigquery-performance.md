# BigQuery 응답 속도 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BigQuery 라우트 응답 속도를 개선한다 — 로딩 피드백을 즉시 노출(Plan A)하고, SQL 파티션 필터 강제로 BQ 실행 시간을 단축한다(Plan B).

**Architecture:**  
Plan A는 `orchestrator.py`의 `route_and_stream`에서 wiki 조회보다 먼저 `yield ("source", route)`를 실행해 프론트엔드 로딩 인디케이터를 즉시 표시한다. Plan B는 `prompts/sql_generator.txt`에 파티션 필터 규칙을 추가하고, `sql_agent.py`에 강제 검증 레이어를 추가해 대형 테이블 전체 스캔을 차단한다.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Gemini Flash, BigQuery, pytest

---

## 파일 변경 목록

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/agents/orchestrator.py` | Modify | `route_and_stream`: wiki 조회를 source yield 뒤로 이동 |
| `prompts/sql_generator.txt` | Modify | 파티션 최적화 규칙 섹션 추가 |
| `app/agents/sql_agent.py` | Modify | `_enforce_partition_filter` 함수 추가 + `run_sql_agent_stream` 호출 |
| `tests/test_sql_agent.py` | Modify | 파티션 필터 검증 테스트 추가 |

---

## Task 1: wiki 조회를 source yield 뒤로 이동 (Plan A)

**Files:**
- Modify: `app/agents/orchestrator.py` — `route_and_stream` 메서드

**배경:** 현재 `route_and_stream`은 wiki 조회(`await search_with_pages`)를 맨 앞에서 실행한다. 이 때문에 `yield ("source", route)` 전까지 프론트엔드 로딩 인디케이터가 갱신되지 않는다. wiki 조회는 ~500ms 소요. 이를 yield 뒤로 옮기면 즉시 피드백이 표시된다.

- [ ] **Step 1: 현재 코드 확인**

`app/agents/orchestrator.py`의 `route_and_stream` 메서드 시작 부분 확인:
```
# 현재 구조 (라인 ~483-628):
async def route_and_stream(self, ...):
    wiki_context = ""
    try:
        wiki_context = await search_with_pages(query, limit=4)   # ← 여기서 ~500ms 블록킹
        ...
    except ...:
        ...

    db_entry, clean_query = self.parse_db_prefix(query)
    # ... 많은 코드 ...
    route = self._keyword_classify(query)
    yield ("source", route)  # ← 이게 로딩 인디케이터 트리거, 너무 늦게 옴
```

- [ ] **Step 2: wiki 조회 블록 삭제**

`app/agents/orchestrator.py`에서 `route_and_stream` 메서드 내 다음 블록을 삭제한다 (라인 ~483-494):

```python
        wiki_context = ""
        try:
            from app.knowledge.wiki_search import search_with_pages
            wiki_context = await search_with_pages(query, limit=4)
            if wiki_context:
                logger.info("wiki_context_injected", length=len(wiki_context))
        except Exception as e:
            logger.warning("wiki_lookup_failed", error=str(e)[:200])
```

- [ ] **Step 3: yield ("source", route) 직후에 wiki 조회 추가**

`route_and_stream`에서 `yield ("source", route)` 라인(~628)을 찾아, 그 **바로 아래에** 다음 블록을 삽입한다:

```python
        # Wiki lookup runs AFTER source yield — loading indicator shows first.
        wiki_context = ""
        try:
            from app.knowledge.wiki_search import search_with_pages
            wiki_context = await search_with_pages(query, limit=4)
            if wiki_context:
                logger.info("wiki_context_injected", length=len(wiki_context))
        except Exception as e:
            logger.warning("wiki_lookup_failed", error=str(e)[:200])
```

단, 이 블록의 삽입 위치는 `yield ("source", route)` 바로 다음이어야 하며, 이어지는 LLM re-classify 코드 (`if not _single_route: ... _classify_with_llm`) 보다 **앞**이어야 한다.

정확한 삽입 전후:
```python
        yield ("source", route)

        # ↓ 이 자리에 삽입
        wiki_context = ""
        try:
            from app.knowledge.wiki_search import search_with_pages
            wiki_context = await search_with_pages(query, limit=4)
            if wiki_context:
                logger.info("wiki_context_injected", length=len(wiki_context))
        except Exception as e:
            logger.warning("wiki_lookup_failed", error=str(e)[:200])
        # ↑ 삽입 끝

        if not _single_route:
            # Re-classify short ambiguous queries ...
```

- [ ] **Step 4: 서버 재시작 후 수동 확인**

```bash
pm2 restart skin1004-dev
```

브라우저에서 BigQuery 질문 (예: "지난달 미국 매출 알려줘") 전송 후:
- 전송 즉시 "📊 데이터 조회 중..." 텍스트가 응답 버블에 표시되는지 확인
- DevTools Network 탭에서 SSE 첫 번째 `<!-- source:bigquery -->` 이벤트 수신 시점 확인

- [ ] **Step 5: Commit**

```bash
git add app/agents/orchestrator.py
git commit -m "perf(orchestrator): yield source before wiki lookup for instant loading feedback"
```

---

## Task 2: SQL 파티션 필터 규칙 추가 (Plan B - 프롬프트)

**Files:**
- Modify: `prompts/sql_generator.txt`

**배경:** SALES_ALL_Backup, integrated_ad 같은 대형 테이블에 날짜 필터 없이 SQL이 생성되면 BQ가 전체 데이터를 스캔한다 (~15-20s). 날짜 파티션 필터 추가 시 5-8s로 단축 가능.

- [ ] **Step 1: sql_generator.txt 상단 규칙 섹션 찾기**

`prompts/sql_generator.txt` 파일에서 `⛔ 날짜 최우선 규칙:` 섹션 위치 확인.

- [ ] **Step 2: 파티션 최적화 섹션 추가**

`⛔ 날짜 최우선 규칙:` 섹션 바로 **아래에** 다음 내용을 삽입한다:

```
⚠️ BigQuery 파티션 최적화 필수 (BQ 실행 속도에 직결):
1. SALES_ALL_Backup, integrated_ad, Integrated_marketing_cost 테이블 사용 시:
   → 반드시 WHERE Date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD' 조건 포함
   → 기간이 명시되지 않은 질문: 최근 90일 기본값 (DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY))
2. SELECT * 금지 — 답변에 필요한 컬럼만 명시 (Revenue, Total_Qty, Country 등)
3. 서브쿼리에서 먼저 WHERE로 범위 좁힌 후 집계 (풀스캔 방지)
```

- [ ] **Step 3: 서버 재시작 (프롬프트 캐시 갱신)**

```bash
pm2 restart skin1004-dev
```

`sql_agent.py`의 `_prompt_cache`가 프로세스 재시작 시 초기화되므로 다음 요청부터 새 프롬프트 적용.

- [ ] **Step 4: Commit**

```bash
git add prompts/sql_generator.txt
git commit -m "perf(sql): add partition filter optimization rules to sql_generator prompt"
```

---

## Task 3: 파티션 필터 강제 검증 레이어 추가 (Plan B - 코드)

**Files:**
- Modify: `app/agents/sql_agent.py`
- Modify: `tests/test_sql_agent.py`

**배경:** 프롬프트 규칙만으로는 LLM이 항상 준수하지 않을 수 있다. `validate_sql_node` 통과 직후에 코드 레벨 검증을 추가해, 대형 테이블 + 날짜 필터 없는 SQL을 감지하면 Flash에 재생성을 요청한다.

- [ ] **Step 1: 테스트 먼저 작성**

`tests/test_sql_agent.py`에 다음 테스트 추가:

```python
class TestPartitionFilter:
    """Tests for _enforce_partition_filter."""

    def test_no_change_when_date_filter_present(self):
        from app.agents.sql_agent import _enforce_partition_filter
        sql = (
            "SELECT Country, SUM(Revenue) AS total "
            "FROM `skin1004-319714.Sales_Integration.SALES_ALL_Backup` "
            "WHERE Date BETWEEN '2025-01-01' AND '2025-03-31' "
            "GROUP BY Country"
        )
        result = _enforce_partition_filter(sql, "국가별 매출")
        assert result == sql  # unchanged

    def test_no_change_for_small_table(self):
        from app.agents.sql_agent import _enforce_partition_filter
        sql = (
            "SELECT Name FROM `skin1004-319714.Sales_Integration.Product` LIMIT 10"
        )
        result = _enforce_partition_filter(sql, "제품 목록")
        assert result == sql  # Product is not a large table

    def test_no_change_when_date_filter_lowercase(self):
        from app.agents.sql_agent import _enforce_partition_filter
        sql = (
            "SELECT Country, SUM(Revenue) "
            "FROM `skin1004-319714.Sales_Integration.SALES_ALL_Backup` "
            "WHERE date >= '2025-01-01' GROUP BY Country"
        )
        result = _enforce_partition_filter(sql, "매출")
        assert result == sql  # has date filter (case-insensitive)

    def test_detects_missing_filter_on_sales_table(self):
        from app.agents.sql_agent import _enforce_partition_filter
        sql = (
            "SELECT Country, SUM(Revenue) AS total "
            "FROM `skin1004-319714.Sales_Integration.SALES_ALL_Backup` "
            "GROUP BY Country ORDER BY total DESC LIMIT 10"
        )
        # Cannot call Flash in unit test — just verify detection logic returns
        # a non-None string (real LLM call only in integration tests)
        # Patch the Flash call to return a safe sentinel
        import unittest.mock as mock
        sentinel_sql = (
            "SELECT Country, SUM(Revenue) AS total "
            "FROM `skin1004-319714.Sales_Integration.SALES_ALL_Backup` "
            "WHERE Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) "
            "GROUP BY Country ORDER BY total DESC LIMIT 10"
        )
        with mock.patch("app.agents.sql_agent.get_flash_client") as mock_flash:
            mock_client = mock.MagicMock()
            mock_client.generate.return_value = sentinel_sql
            mock_flash.return_value = mock_client
            result = _enforce_partition_filter(sql, "국가별 매출")
        assert "DATE_SUB" in result or "INTERVAL" in result or "Date" in result
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
cd C:\Users\DB_PC\Desktop\python_bcj\AI_Agent
python -m pytest tests/test_sql_agent.py::TestPartitionFilter -v
```

Expected: `ImportError` 또는 `AttributeError: module has no attribute '_enforce_partition_filter'`

- [ ] **Step 3: `_enforce_partition_filter` 함수 구현**

`app/agents/sql_agent.py`에서 `_extract_tables_from_sql` 함수(~라인 45) 바로 아래에 추가:

```python
# Large tables that MUST have a date filter for acceptable scan performance.
_LARGE_TABLES_REQUIRING_DATE_FILTER = [
    "SALES_ALL_Backup",
    "integrated_ad",
    "Integrated_marketing_cost",
]


def _enforce_partition_filter(sql: str, query: str) -> str:
    """If SQL targets a large table without any date filter, request Flash re-gen.

    Returns the original sql unchanged when:
    - No large table is targeted
    - A date/Date filter is already present (case-insensitive)

    Returns a re-generated sql when:
    - A large table is targeted AND no date filter found
    """
    if not sql:
        return sql

    targets_large = any(t in sql for t in _LARGE_TABLES_REQUIRING_DATE_FILTER)
    if not targets_large:
        return sql

    has_date_filter = bool(re.search(r'\bdate\b', sql, re.IGNORECASE) and
                           re.search(r'\bwhere\b', sql, re.IGNORECASE))
    if has_date_filter:
        return sql

    logger.info("partition_filter_missing_rewrite", sql=sql[:200])
    llm = get_flash_client()
    retry_prompt = (
        _load_prompt("sql_generator.txt")
        + f"\n\n## 사용자 질문\n{query}"
        + "\n\n⚠️⚠️ 이전 SQL이 대형 테이블 전체를 스캔합니다 (매우 느림)!"
        + "\n반드시 WHERE Date BETWEEN ... AND ... 날짜 조건을 추가하세요."
        + "\n기간 미지정 시 기본값: DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) ~ CURRENT_DATE()"
        + "\nSELECT * 금지 — 필요한 컬럼만 선택하세요."
    )
    try:
        new_sql = llm.generate(retry_prompt, temperature=0.0, max_output_tokens=10000)
        new_sql = sanitize_sql(new_sql)
        if new_sql and len(new_sql) > 10:
            logger.info("partition_filter_rewritten", new_sql=new_sql[:200])
            return new_sql
    except Exception as e:
        logger.warning("partition_filter_rewrite_failed", error=str(e))
    return sql
```

- [ ] **Step 4: `run_sql_agent_stream` 내 호출 추가**

`run_sql_agent_stream` 함수(라인 ~1208) 내, `validate_sql_node` 호출 바로 다음:

```python
    state.update(generate_sql(state))
    state.update(validate_sql_node(state))
    if state.get("sql_valid"):
        # ↓ 추가
        state["generated_sql"] = _enforce_partition_filter(
            state.get("generated_sql", ""), query
        )
        # ↑ 추가
        state.update(execute_sql(state))
```

- [ ] **Step 5: `run_sql_agent` 비스트리밍 버전에도 동일 추가**

`run_sql_agent` 함수(라인 ~1162) 내에서도 `validate_sql_node` 다음:

```python
    state.update(generate_sql(state))
    state.update(validate_sql_node(state))
    if state.get("sql_valid"):
        state["generated_sql"] = _enforce_partition_filter(
            state.get("generated_sql", ""), state["query"]
        )
        state.update(execute_sql(state))
```

- [ ] **Step 6: 테스트 재실행 — PASS 확인**

```bash
python -m pytest tests/test_sql_agent.py::TestPartitionFilter -v
```

Expected output:
```
PASSED tests/test_sql_agent.py::TestPartitionFilter::test_no_change_when_date_filter_present
PASSED tests/test_sql_agent.py::TestPartitionFilter::test_no_change_for_small_table
PASSED tests/test_sql_agent.py::TestPartitionFilter::test_no_change_when_date_filter_lowercase
PASSED tests/test_sql_agent.py::TestPartitionFilter::test_detects_missing_filter_on_sales_table
```

- [ ] **Step 7: 기존 SQL 테스트 전체 통과 확인**

```bash
python -m pytest tests/test_sql_agent.py -v
```

Expected: All PASSED

- [ ] **Step 8: Commit**

```bash
git add app/agents/sql_agent.py tests/test_sql_agent.py
git commit -m "perf(sql): add _enforce_partition_filter — auto-rewrite large-table queries without date filter"
```

---

## Task 4: 개발서버 검증 및 dev 배포

**Files:** 없음 (검증 단계)

- [ ] **Step 1: dev 서버 재시작**

```bash
pm2 restart skin1004-dev
```

- [ ] **Step 2: BigQuery 날짜 필터 없는 질문 테스트**

브라우저에서 http://127.0.0.1:3001 접속 후:

질문 1: `"국가별 전체 매출 랭킹 알려줘"` (날짜 미지정 → 필터 주입 여부 확인)
- 로그에서 `partition_filter_missing_rewrite` 또는 `partition_filter_rewritten` 확인:
  ```bash
  pm2 logs skin1004-dev --lines 30 --nostream | grep partition
  ```
- 응답 시간 체크 (이전 ~27s → 목표 ≤15s)

질문 2: `"2025년 1분기 미국 아마존 매출"` (날짜 있음 → 필터 주입 안 해야 함)
- 로그에 `partition_filter_missing_rewrite` 없어야 함

- [ ] **Step 3: 로딩 인디케이터 즉시 표시 확인**

브라우저 DevTools → Network → EventStream 탭 열고:
1. 질문 전송
2. 첫 번째 SSE 이벤트 수신 시간 확인 (목표: 전송 후 ≤200ms)
3. `<!-- source:bigquery -->` 이벤트로 "📊 데이터 조회 중..." 텍스트 표시 확인

- [ ] **Step 4: Commit (없으면 Skip)**

변경사항 없으면 Skip. 검증 중 발견한 버그는 별도 수정 후 커밋.

---

## 완료 기준

- [ ] 모든 `TestPartitionFilter` 테스트 PASS
- [ ] `test_sql_agent.py` 전체 PASS
- [ ] BigQuery 질문 전송 후 200ms 이내 "📊 데이터 조회 중..." 표시
- [ ] 날짜 미지정 + 대형 테이블 쿼리: `partition_filter_rewritten` 로그 확인
- [ ] 날짜 있는 쿼리: 파티션 필터 재생성 미발생 확인
- [ ] dev 서버에서 응답 시간 주관적으로 빨라진 것 확인
