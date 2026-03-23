# Update Log — 2026-03-19 (v8.3 SQL 복잡쿼리 강화 + Playwright E2E QA + jp2 이슈 해결)

## 변경 사항

### 1. 코드 리뷰 & 정리 (/simplify)
- 중복 context 호출 제거, ROUTE:BQ 태그 제거, /debug/route 제거, HTML 잔여물 정리

### 2. Notion 미해결 이슈 해결
- 크레이버코퍼레이션 매출 → Brand 필터 없이 전체 조회 (AD 그룹 자동 필터링)
- LIN 약어 → LabinNature 매핑 추가 + 랩인네이처 정확 표기 추가

### 3. SQL 프롬프트 대규모 강화 (jp2 시트 26건 이슈 해결)
- **CTE(WITH절) 허용**: 이동평균, 누적합, 전년대비, 서브쿼리 등 복잡 쿼리 지원
- **SQL 생성 강제**: "조회하지 못했습니다" / 되묻기 응답 절대 금지 → 모호해도 기본값으로 SQL 생성
- **모호한 질문 기본값**: "요즘 매출" → 최근 3개월, "잘 팔리는" → TOP 10, "실적 어때" → 월별 추이
- **SKU + Product_Name 필수**: SKU 조회 시 제품명(SET) 반드시 함께 SELECT
- **"최근/요즘" = 최근 3개월**: 현재 날짜 기준 DATE_SUB 3개월
- **서론 간결화**: 조건(브랜드, 날짜범위, 제외항목)은 답변 끝에 짧게 괄호로
- **5개 실패 패턴 예시 SQL 추가**: MoM 성장률, Country별 최다 Line, 단일거래 최고매출, 교차분석, 평균단가 이상 매출
- **Timeout 방지**: 전국가 YoY → TOP 10 국가 제한, 전체기간 누적 → 최근 12개월
- **사업부 구조 매핑**: B2B(B2B1,B2B2), GM(CBT,GM_EAST1,GM_EAST2,GM_Ecomm,GM_MKT,JBT,KBT), PR(BCM), DD(DD_DT1,DD_DT2)
- **ETC 브랜드 기본 제외**: 매출 조회 시 Brand != 'ETC' 기본 적용

### 4. 스트리밍 중 대화 전환 UI 오류 수정
- AbortController 도입 — AI 응답 생성 중 다른 대화 클릭 시 안전 abort

### 5. QA 테스트 실행
- **QA 100 (API)**: 9개 테이블 × 100문항 = 900건, 99.6% PASS, avg 41.8s
- **Playwright E2E**: 100문항 실제 브라우저 테스트, 93% PASS, avg 31.5s
- **jp2 리테스트**: 26건 이슈 중 20건 해결 (77%), Timeout 4건→0건

### 6. jp2 시트 이슈 해결 현황

| 이전 상태 | 건수 | 이후 |
|-----------|------|------|
| SQL 생성 실패 (복잡쿼리) | 20건 | 14건 해결 |
| 서론 너무 길음 | 1건 | 해결 |
| SKU에 ProductName 누락 | 1건 | 해결 |
| "최근" 기간 잘못 해석 | 1건 | 해결 |
| 속도 느림 (64s+) | 1건 | 해결 (24s) |
| Timeout (185s) | 4건 | 전부 해결 (0건) |

## 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `prompts/sql_generator.txt` | CTE허용, 복잡쿼리강제, 모호한질문기본값, SKU+ProductName, 사업부매핑, ETC제외, 5개 예시SQL |
| `app/core/prompt_fragments.py` | 서론간결화 (조건→맨끝 괄호) |
| `app/frontend/chat.js` | AbortController 스트리밍 안정화 |
| `app/frontend/chat.html` | cache bust v105 |
| `app/agents/orchestrator.py` | 중복context제거, ROUTE태그제거, 크레이버키워드 |
| `app/api/routes.py` | /debug/route 제거 |
| `scripts/playwright_qa_100.py` | Playwright E2E QA 100 스크립트 |
| `scripts/playwright_retest.py` | Playwright 리테스트 스크립트 |
