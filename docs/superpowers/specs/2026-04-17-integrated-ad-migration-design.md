# 통합 광고 데이터 테이블 마이그레이션 (Wide → Long)

**Date**: 2026-04-17
**Owner**: 임재필 (Jeffrey Lim)
**Trigger**: `데이터 학습.xlsb.xlsx` Marketing 시트에서 통합광고 테이블 스키마 완전 교체

## 배경

BigQuery의 통합 광고 데이터가 **기존 wide 포맷에서 long 포맷으로 재설계**되었다.
기존 테이블(`integrated_advertising_data`)은 플랫폼별 컬럼(`TikTok_Cost`, `Facebook_Cost`, ...)을 가지는 와이드 형태였고,
신규 테이블(`integrated_ad`)은 `media` 컬럼에 플랫폼 값을 저장하는 롱 형태다.

완전 교체이므로 기존 테이블 참조는 전면 제거한다.

## 신규 스키마

**테이블**: `skin1004-319714.marketing_analysis.integrated_ad` (60,121행, 2019-06-01 ~ 2027-02-28)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | DATE | 광고 집행일 |
| country | STRING | 국가 (한국어: 대만/말레이시아/미국/베트남/싱가포르/인도네시아/일본/필리핀/한국/호주) |
| team | STRING | 담당팀 (EAST1, EAST2, JBT, KBT, WEST, 기타) |
| media | STRING | 매체 (Amazon, AmazonDSP, Google, KakaoMoments, Meta, NaverGFA, NaverSearch, Qoo10, Rakuten, Shopee, SingleONE, Snapchat, TikTok, Tokopedia, X(Twitter)) |
| account_name | STRING | 광고 계정명 |
| cost_krw | FLOAT | 광고비 (원화) |
| impressions | INTEGER | 노출 수 |
| clicks | INTEGER | 클릭 수 |
| conversions | INTEGER | 전환 수 |
| conversion_value_krw | FLOAT | 전환 가치 (원화) |

## 주요 쿼리 패턴

| 사용자 질문 | SQL 패턴 |
|----------|---------|
| 전체 광고비 | `SUM(cost_krw)` |
| 매체별 광고비 | `GROUP BY media` + `SUM(cost_krw)` |
| 메타/페이스북/인스타 | `WHERE media = 'Meta'` |
| TikTok/구글/아마존 광고 | `WHERE media = 'TikTok'` (등) |
| ROAS | `SAFE_DIVIDE(SUM(conversion_value_krw), SUM(cost_krw))` |
| CTR | `SAFE_DIVIDE(SUM(clicks), SUM(impressions))` |
| CVR | `SAFE_DIVIDE(SUM(conversions), SUM(clicks))` |
| CPC | `SAFE_DIVIDE(SUM(cost_krw), SUM(clicks))` |
| CPM | `SAFE_DIVIDE(SUM(cost_krw)*1000, SUM(impressions))` |
| 팀별 | `GROUP BY team` |
| 국가별 | `GROUP BY country` |
| 계정별 | `GROUP BY account_name` |

## 변경 파일

### 1. `app/config.py` (line 129)
`allowed_tables` 리스트에서 경로 교체:
- `skin1004-319714.marketing_analysis.integrated_advertising_data`
- → `skin1004-319714.marketing_analysis.integrated_ad`

### 2. `app/agents/sql_agent.py`
- **line 119** — `MARKETING_TABLES[0]`: 경로 교체 + 키워드 확장
  - 추가 키워드: `meta`, `메타`, `amazon광고`, `amazonads`, `snapchat`, `tokopedia`, `rakuten`, `x광고`, `twitter광고`, `dsp`, `qoo10광고`, `계정별`, `팀별광고`
- **line 189** — `_SOURCE_TABLE_MAP["광고"]`: 경로 교체
- **line 491** — `_TABLE_DISPLAY_NAMES`: 키 `integrated_advertising_data` → `integrated_ad`

### 3. `prompts/sql_generator.txt`
- **line 26** — 테이블 선택 규칙에서 테이블명 교체
- **line 446-483** — 통합 광고 섹션 전면 재작성
  - Wide 포맷 컬럼 표 제거
  - Long 포맷 10컬럼 스키마 표 추가
  - media 값 목록 (15개)
  - country/team 값 목록
  - 예시 쿼리 8개: 전체/매체별/ROAS/Meta 추이/팀별/국가별/계정 TOP/CVR
  - ⚠️ 메타/페이스북/인스타 → `media='Meta'` (Facebook 아님)

### 4. `app/core/safety.py` — 변경 불필요 (단순 라벨)

## 제외 (이력 보존)

- `scripts/qa_marketing/**/*.json` — 과거 QA 결과
- `docs/update_log_2026-03-04.md` — 과거 업데이트 로그
- `scripts/qa_marketing_test.py`, `scripts/qa_marketing/qa_pipeline.py`, `scripts/qa_marketing/run_qa_100.py` — QA 스크립트 (별도 재정비 필요시 추후)

## 검증 계획

1. 수정 완료 → `pm2 restart skin1004-dev`
2. dev (3001)에서 6개 테스트 쿼리:
   - 이번 달 전체 광고비
   - 매체별 ROAS TOP 5
   - Meta 광고 CTR 월별 추이
   - EAST1 팀 2025년 광고비
   - 계정별 광고비 TOP 10
   - 국가별 전환수 2026 Q1
3. 주인님 확인 후 `pm2 reload skin1004-prod`로 프로덕션 반영
4. `chat.html`의 `?v=` 번호 증가 **불필요** (CSS/JS 변경 없음)

## 리스크 및 완화

- **리스크**: LLM이 캐시된 옛 SQL을 사용하여 옛 테이블에 쿼리 → 실패
  - **완화**: `app/db/mariadb.py`의 `sql_cache` 테이블 비우기 필요 (dev/prod 각각)
- **리스크**: 메타 광고 질문 시 `media='Facebook'`로 잘못된 WHERE 생성
  - **완화**: 프롬프트에 명시적 "메타 = Meta (not Facebook)" 규칙 추가
- **리스크**: 통합 광고 데이터 질문이 `meta data_test` 테이블(ad_data 데이터셋)로 잘못 라우팅
  - **완화**: 키워드 분리 명확화 — `meta data_test`는 "광고 라이브러리" 키워드 유지
