# Update Log — 2026-03-04 (v7.3.0 마케팅 11개 테이블 통합 + 보안 강화)

## 변경 사항

### 1. 마케팅/리뷰/광고 11개 BigQuery 테이블 통합

#### 1-A. 문제
- 기존 시스템은 SALES_ALL_Backup, Product 2개 테이블만 지원
- 마케팅팀 데이터(광고비, 인플루언서, Shopify, 리뷰, 메타 광고 등) 조회 불가

#### 1-B. 수정
1. **SQL 프롬프트 확장** (`prompts/sql_generator.txt`):
   - 13개 테이블 선택 규칙표 추가 (질문 유형별 → 사용 테이블 매핑)
   - 11개 마케팅 테이블 스키마 자동 로딩 (startup warmup)
2. **Config 허용 테이블** (`app/config.py`):
   - `allowed_tables`에 11개 마케팅 테이블 추가 (SQL 안전장치 통과)
3. **키워드 분류 확장** (`app/agents/orchestrator.py`):
   - `_DATA_KEYWORDS`에 광고/마케팅/인플루언서/리뷰/Shopify 키워드 60+ 추가
   - `_STRONG_DATA`에 마케팅 키워드 추가 (CS와 충돌 방지)
4. **System Status 11개 DB** (`app/core/safety.py`):
   - `get_safety_status()`에 11개 마케팅 테이블 서비스 카드 추가
5. **프론트엔드 System Status** (`app/frontend/chat.js`):
   - `SERVICE_ICONS`에 11개 마케팅 DB 아이콘 추가

#### 1-C. 추가된 테이블
| 테이블 | 설명 |
|--------|------|
| `marketing_analysis.integrated_advertising_data` | 통합 광고 데이터 (틱톡/페이스북/구글/네이버/카카오/아마존/쇼피) |
| `marketing_analysis.Integrated_marketing_cost` | 통합 마케팅 비용 (매체별/팀별/국가별) |
| `marketing_analysis.shopify_analysis_sales` | Shopify 자사몰 판매 데이터 |
| `Platform_Data.raw_data` | 플랫폼별 제품 순위/가격 메트릭스 |
| `marketing_analysis.influencer_input_ALL_TEAMS` | 인플루언서 마케팅 데이터 |
| `marketing_analysis.amazon_search_analytics_catalog_performance` | 아마존 검색 분석 |
| `Review_Data.Amazon_Review` | 아마존 리뷰 |
| `Review_Data.Qoo10_Review` | 큐텐 리뷰 |
| `Review_Data.Shopee_Review` | 쇼피 리뷰 |
| `Review_Data.Smartstore_Review` | 스마트스토어 리뷰 |
| `ad_data.meta data_test` | 메타 광고 라이브러리 |

#### 1-D. 수정 파일
| 파일 | 변경 |
|------|------|
| `prompts/sql_generator.txt` | 13개 테이블 선택 규칙, 마케팅 스키마 |
| `app/config.py` | `allowed_tables`에 11개 추가 |
| `app/agents/orchestrator.py` | 마케팅 키워드 60+ 추가 |
| `app/agents/sql_agent.py` | `MARKETING_TABLES` 리스트, 스키마 로딩 |
| `app/core/safety.py` | 11개 마케팅 서비스 카드 |
| `app/frontend/chat.js` | 11개 `SERVICE_ICONS` 추가 |
| `app/main.py` | startup warmup에 마케팅 스키마 포함 |

### 2. SQL 집계 수준 드리프트 버그 수정

#### 2-A. 문제
- "쇼피 인도네시아 이번 달 매출" 질문 → 제품별 GROUP BY가 추가되어 총합 대신 제품별 분해 결과 반환
- 원인: Rule 14(제품 필터 시 GROUP BY SET)를 LLM이 과도하게 적용, 제품 질문이 아닌데도 제품별 분해

#### 2-B. 수정 (`prompts/sql_generator.txt`)
1. **Rule 14 범위 명확화**: "예외 없이 항상 적용" → "사용자가 제품명/라인/SKU를 직접 언급했을 때만 적용"
2. **Rule 18 신규**: "집계 수준은 사용자 질문에 맞추기 (최우선 규칙)"
   - 제품을 안 물어봤으면 총합(SUM)만 반환, 제품별 GROUP BY 금지
   - 사용자가 언급한 차원(국가, 채널, 기간)으로만 GROUP BY
3. **예시 추가**: "국가+플랫폼 단순 매출 (제품 분해 X!)" 예시

#### 2-C. 수정 파일
| 파일 | 변경 |
|------|------|
| `prompts/sql_generator.txt` | Rule 14 범위 제한, Rule 18 신규, 예시 추가 |

### 3. P0 보안 수정 (Security Architecture 반영)

#### 3-A. 수정 사항
1. **API key 환경변수 이전**: 코드 내 하드코딩된 API key를 `.env` 환경변수로 이전
2. **JWT 보안 강화**: 쿠키 설정 개선 (httpOnly, SameSite)
3. **SQL Injection 방어**: 파라미터 바인딩 검증
4. **보안 아키텍처 문서**: `docs/SKIN1004_Security_Architecture.md` 작성

#### 3-B. 수정 파일
| 파일 | 변경 |
|------|------|
| `app/core/llm.py` | API key 환경변수 참조 |
| `app/api/routes.py` | 입력 검증 강화 |
| `docs/SKIN1004_Security_Architecture.md` | 전체 보안 아키텍처 문서 |

## 수정 파일 목록

| 파일 | 수정 유형 |
|------|----------|
| `prompts/sql_generator.txt` | 13개 테이블 규칙 + Rule 14/18 수정 |
| `app/config.py` | 11개 마케팅 테이블 허용 |
| `app/agents/orchestrator.py` | 마케팅 키워드 확장 |
| `app/agents/sql_agent.py` | MARKETING_TABLES + 스키마 로딩 |
| `app/core/safety.py` | 11개 마케팅 서비스 카드 |
| `app/frontend/chat.js` | SERVICE_ICONS 11개 추가 |
| `app/main.py` | warmup 마케팅 스키마 |
| `app/core/llm.py` | API key 보안 |
| `app/api/routes.py` | 입력 검증 |
| `docs/SKIN1004_Security_Architecture.md` | 보안 아키텍처 문서 |

## 테스트 결과

### Marketing QA 500 (11개 테이블)
| 지표 | 결과 |
|------|------|
| 총 질문 | 500 |
| OK | 481 (96.2%) |
| WARN (60-90s) | 18 |
| FAIL | 1 |
| 평균 응답시간 | 34.3s |
| p50 | 32.2s |
| p95 | 58.2s |

### 카테고리별 결과
| 카테고리 | OK | WARN | FAIL | Total | Avg | Pass% |
|----------|-----|------|------|-------|------|-------|
| 광고데이터 | 59 | 1 | 0 | 60 | 35.2s | 100% |
| 마케팅비용 | 41 | 4 | 0 | 45 | 41.7s | 100% |
| Shopify | 41 | 4 | 0 | 45 | 32.2s | 100% |
| 인플루언서 | 55 | 5 | 0 | 60 | 42.6s | 100% |
| 플랫폼 | 34 | 1 | 0 | 35 | 36.9s | 100% |
| 아마존검색 | 34 | 1 | 0 | 35 | 32.3s | 100% |
| 아마존리뷰 | 45 | 0 | 0 | 45 | 30.4s | 100% |
| 큐텐리뷰 | 45 | 0 | 0 | 45 | 40.9s | 100% |
| 쇼피리뷰 | 45 | 0 | 0 | 45 | 29.4s | 100% |
| 스마트스토어리뷰 | 44 | 1 | 0 | 45 | 24.9s | 100% |
| 메타광고 | 38 | 1 | 1 | 40 | 27.4s | 97.5% |

### FAIL 분석
- **MT-019** (104.6s): "메타 광고 전체 국가 목록" — DB에 국가 목록 컬럼 없음, direct route로 흘러감 (일반 지식 질문)

### 기존 QA 500 (매출/CS/Notion/GWS)
- 500/500 OK (100%), Avg 41.4s, 0 WARN, 0 FAIL
