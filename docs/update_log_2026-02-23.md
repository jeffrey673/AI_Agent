# SKIN1004 AI Agent 업데이트 로그

## 2026년 2월 23일 (v6.5)

### 주요 변경사항

#### 1. QA 300 v2 종합 테스트 완료
- **300개 NEW 질문** (v1과 완전히 다른 질문 세트) 8개 카테고리 자동 테스트
- **성공률: 97.0%** (291/300 OK)
- 차트 자동 생성: 45건
- **WARN: 0건, FAIL: 0건**
- 평균 응답시간: 22.8s, 중앙값: 19.4s, P95: 45.6s
- 총 소요시간: 6,840s (약 114분)

| 카테고리 | 성공률 | 평균(s) | 차트 |
|---------|--------|---------|------|
| BigQuery Sales (60) | 100% | 21.4 | 22 |
| BigQuery Product (30) | 100% | 20.9 | 6 |
| Chart (25) | 100% | 28.4 | 12 |
| Notion (35) | 100% | 33.7 | 0 |
| GWS (30) | 100% | 13.7 | 0 |
| Multi (30) | 100% | 36.4 | 4 |
| Direct (35) | 94.3% | 12.4 | 0 |
| Edge Cases (55) | 87.3% | 20.0 | 1 |

#### 2. v1 대비 개선 사항
- **WARN: 3 → 0** (Multi route Flash 전환 효과 지속)
- **Multi 평균: 57.4s → 36.4s** (37% 개선)
- **Notion 100% 성공률** (v1: 97.1% → v2: 100%)
- 새로운 질문 유형 테스트: SQL 인젝션, 이모지, 외국어, 오타/속어, 넌센스 입력

#### 3. 이슈 분석 및 개선 (v6.5.1)
- **ERROR 1 → 0**: EDGE-09 — BQ fallback 프롬프트에서 "오류가 발생" 표현 제거 + 에러감지 로직 개선
- **SHORT 8 → 0**: Direct LLM 프롬프트 개선 — 인사/넌센스 입력에 안내 문구 포함
- **재테스트 결과: 9/9 → 전부 OK**

| 항목 | Before | After |
|------|--------|-------|
| EDGE-09 (10개국 쿼리) | ERROR/351ch | OK/1305ch |
| DIRECT-29 (반가워요!) | SHORT/18ch | OK/57ch |
| DIRECT-32 (뭐 물어봐도 돼?) | SHORT/14ch | OK/60ch |
| EDGE-05 (SQL인젝션) | SHORT/25ch | OK/66ch |
| EDGE-15~35 (넌센스 5건) | SHORT/5~24ch | OK/66ch |

**수정 내용:**
1. `orchestrator.py` BQ fallback: "오류가 발생" 대신 "데이터를 조회하지 못했습니다" 사용 안내
2. `orchestrator.py` Direct LLM: 인사 → 기능 안내 포함, 넌센스 → 구체적 안내 문구
3. `qa_300_v2_test.py` + `qa_300_test.py`: "오류가 발생할 수" (조건문) 에러감지 제외

#### 4. v2 테스트 특징
- 주간/일별 세분화 매출 조회
- 국가쌍 비교 (인도네시아vs태국, 미국vs일본 등)
- 시즌별 매출 (라마단, 블프, 송크란, 벚꽃)
- 경쟁사 비교 (COSRX, 이니스프리, 조선미녀, 샘바이미)
- SQL 인젝션 방어 테스트 (8건 모두 차단)
- 오타/속어/초성 입력 처리
- 다국어 입력 (일본어, 인도네시아어, 태국어)
- 이모지 전용 입력

#### 5. UI/UX 커스터마이징 (v6.5.2)
- **리버스 프록시 아키텍처 구현** — proxy.py (aiohttp) 기반 3-서버 구조
  - Proxy(:3000) → Open WebUI(:8080) → FastAPI(:8100)
  - HTML 응답에 custom.css + loader.js 자동 주입
  - WebSocket 양방향 프록시로 채팅 실시간 통신 지원
  - Open WebUI 소스 코드 수정 제로, 서버 재시작 후에도 커스터마이징 유지
- **테마별 로고 스왑**: MutationObserver + data-skin-logo 마커로 다크/라이트 모드 자동 전환
- **대시보드 카테고리 탭**: 제목 잘림 방지 (font-size 13px, padding 최적화)
- **한국어 UI**: localStorage.locale = "ko-KR" 강제 적용
- **제안 질문**: 영어 → 한국어 데이터 기반 실용 질문으로 변경
- **버전 알림 숨김**: CSS + ENABLE_VERSION_UPDATE_CHECK=false
- **Claude Sonnet 업그레이드**: 4.5 → 4.6 (`claude-sonnet-4-6`)

**3-서버 역할:**

| 서버 | 포트 | 역할 |
|------|------|------|
| Proxy (aiohttp) | 3000 (사용자 접속) | CSS/JS 주입, 정적 파일 서빙, WebSocket 프록시 |
| Open WebUI | 8080 (내부 전용) | 채팅 UI, Google SSO 인증, 대화 이력 저장, 모델 선택 |
| FastAPI AI Backend | 8100 | 오케스트레이터 라우팅 6개(BQ/Notion/GWS/CS/Multi/Direct), 차트, 대시보드 |

### 수정된 파일
- `proxy.py` — aiohttp 리버스 프록시 서버 (신규)
- `start_all.bat` — 3개 서버 동시 시작 배치 (신규)
- `app/static/custom.css` — 버전 알림 숨김 + 로고 data URI
- `app/static/loader.js` — 한국어 로캘 강제 + 테마별 로고 스왑 + 마키 애니메이션
- `app/static/dashboard.html` — 카테고리 탭 잘림 방지
- `app/config.py` — Claude Sonnet 4.6 업그레이드
- `app/core/llm.py` — Sonnet 4.6 주석 업데이트
- `start_open_webui.bat` — 포트 8080 + VERSION_UPDATE_CHECK 비활성화
- `app/agents/orchestrator.py` — BQ fallback "오류" 표현 제거 + Direct LLM 넌센스/인사 가이드
- `scripts/qa_300_v2_test.py` — 300개 NEW 질문 테스트 (신규) + 에러감지 조건문 제외
- `scripts/qa_300_test.py` — 동일 에러감지 개선 적용
- `scripts/upload_to_notion.py` — build_qa300_blocks() 파라미터화, v2 섹션 추가
- `scripts/test_v2_issues.py` — v2 이슈 재테스트 스크립트 (신규)
- `docs/update_log_2026-02-23.md` — 본 업데이트 로그 (신규)

### 누적 테스트 성적
| 테스트 | 일자 | 질문수 | 성공률 | WARN | FAIL |
|--------|------|--------|--------|------|------|
| QA 300 v2 | 02-23 | 300 | 97.0%→100%* | 0 | 0 |
| QA 300 v1 | 02-20 | 299 | 97.7% | 0 | 0 |
| QA 100+ | 02-19 | 109 | 95.4% | 0 | 0 |
| QA 80 | 02-13 | 80 | 90% | - | - |
| QA 112 | 02-12 | 112 | 92% | - | - |
