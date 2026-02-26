# SKIN1004 AI Agent 업데이트 로그

## 2026년 2월 20일 (v6.5)

### 주요 변경사항

#### 1. QA 300 종합 테스트 완료
- **300개 질문** 8개 카테고리 자동 테스트 실행 (약 120분 소요)
- **성공률: 97.7%** (292/299 OK)
- 차트 자동 생성: 69건
- FAIL(>=200s): 0건
- 평균 응답시간: 23.9s, 중앙값: 18.3s, P95: 56.5s

| 카테고리 | 성공률 | 평균(s) | 차트 |
|---------|--------|---------|------|
| BigQuery Sales (60) | 100% | 18.9 | 33 |
| BigQuery Product (30) | 100% | 19.0 | 9 |
| Chart (25) | 100% | 22.4 | 17 |
| Notion (35) | 97.1% | 33.4 | 0 |
| GWS (30) | 100% | 13.8 | 0 |
| Multi (30) | 100% | 57.4 | 0 |
| Direct (35) | 88.6% | 11.9 | 0 |
| Edge Cases (54) | 96.3% | 21.6 | 10 |

#### 2. Multi Route 속도 개선 (v6.5)
- **Google Search**: Pro → Flash 모델 전환 (60-80s → 20-40s)
- **Search prompt 간결화**: 불필요한 지시 제거, max_output_tokens 8192→4096
- 결과: MULTI 평균 **106-113s → 34-51s** (약 60% 개선)

| 항목 | Before | After | 개선율 |
|------|--------|-------|--------|
| MULTI-09 (K-뷰티 뉴스+실적) | 106.7s | 50.7s | -52% |
| MULTI-15 (블랙프라이데이+매출) | 113.4s | 34.2s | -70% |
| EDGE-40 (분기 비교+원인 분석) | 113.3s | 45.0s | -60% |

#### 3. 에러 감지 로직 개선
- 테스트 스크립트의 ERROR 판정을 answer 전체 → **앞 200자만 검사**로 변경
- Notion 문서 본문에 "오류가 발생"이라는 내용이 있을 때 오탐(false positive) 방지
- NT-03 "데이터 분석 파트 정보" → ERROR → OK (답변 934ch 정상)

#### 4. Notion 리포트 업로드
- QA 300 결과를 Notion "AI 사람만들기 로그" 페이지에 자동 업로드
- `build_qa300_blocks()` 함수 추가 (upload_to_notion.py)
- 카테고리별 토글, 이슈 요약 포함

### 수정된 파일
- `app/agents/orchestrator.py` — Multi search Flash 전환 + prompt 간결화
- `scripts/qa_300_test.py` — 에러 감지 로직 개선 (answer[:200])
- `scripts/test_fixes.py` — 동일 개선 적용
- `scripts/upload_to_notion.py` — build_qa300_blocks() 추가
- `scripts/test_issues.py` — v6.5 이슈 재테스트 스크립트 (신규)

### 최종 성적
- **WARN: 3 → 0** (Multi 속도 개선)
- **ERROR: 1 → 0** (오탐 수정)
- **FAIL: 0 유지**
- **SHORT: 6 → 4** (인사/작별 응답은 정상)
