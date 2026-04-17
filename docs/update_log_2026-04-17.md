# Update Log — 2026-04-17 (Anonymization v1.0 + Eval Pipeline v1.0)

## 변경 사항

### 1. [프라이버시/아키텍처] 대화 데이터 익명화 (Phase 1)

DB 덤프가 유출돼도 "누가 무엇을 물었는지" 역추적 불가능한 구조로 전환.

- 신규 환경 변수 **`ANON_SALT`** (32바이트 hex) 추가. `.env` 주입, 로그에 절대 노출되지 않음.
- 신규 모듈 `app/core/anonymization.py`:
  - `compute_anon_id(user_id) = hmac_sha256(salt, user_id)[:16]` — 결정론적, 솔트 없이 역추적 불가
  - `anon_id_for(user_id)` — lru_cache 1024개로 핫 패스 비용 제거
  - Salt가 32자 미만이면 호출 시점에 ValueError (prod에서 충돌 예방)
- `conversations` + `message_feedback` 에 `anon_id VARCHAR(32) + INDEX` 컬럼 추가 (idempotent ALTER, 스타트업 훅)
- `conversation_api.py` 전면 개편:
  - 사이드바 "내 대화", 대화 상세, 피드백 조회/저장 — 모두 `WHERE anon_id = %s` 로 전환
  - INSERT 시 anon_id 같이 기록 (user_id는 2주 soak 기간 병행)
  - `feedback_submitted` 로그에서 `user.display_name` 제거, `anon_id` 로 교체
- 신규 `app/core/log_scrub.py` — structlog 프로세서로 모든 로그에서 `user_id` → `anon_id`, `email`/`name`/`display_name` 드롭. `audit`/`security` 네임스페이스는 예외 (보안 인시던트 추적용)
- `scripts/migrate_anonymize_conversations.py` — 기존 **607 conversations + 18 message_feedback** 백필 완료 (unique user 32명)
- **Prod reload 완료** (3000) — 동일 salt 공유, 스키마 자동 마이그레이션

### 2. [품질 평가] 500문항 Eval 파이프라인 (Phase 2)

10개 팀 × 최대 50문항을 Playwright로 실 서버에 질의, 답변을 저장하고 관리자가 👍/👎 판정하는 시스템 구축.

- 신규 테이블 `eval_runs` + `eval_qa` (FK cascade, verdict ENUM: pending/good/bad/skip)
- `scripts/generate_eval_questions.py`:
  - 실사용 쿼리(`messages` 필터링) + Gemini Flash 합성(팀당 ~150 후보) 하이브리드
  - BGE-M3 로컬 임베딩으로 cosine 0.85+ 중복 제거 → K-means 클러스터링 → 라운드 로빈 픽으로 주제 다양성 확보
  - 산출물: `tests/eval/questions_20260417.jsonl` (총 **450문항**, 8개 팀 만점 50 + 2개 팀은 중복 제거로 50 미만)
- `tests/eval/playwright_runner.py`:
  - `/api/auth/signin` 으로 쿠키 민팅 후 `chat.html` 직접 진입 (로그인 폼 스킵)
  - 질의 간 3s throttle, SSE 스트리밍 완료 감지 로직 정확히: `#btn-send.stop-mode` 클래스 해제 대기
  - 답변/응답시간/route/conversation_id 캡처 → `eval_qa` 저장
- 신규 API `/api/admin/eval/*` (admin only): runs, qa 페이징+필터, verdict 업데이트, per-team summary
- 신규 UI `/frontend/eval_review.html`:
  - 스티키 헤더 + 필터(run/team/verdict) + 진행 바 (good/bad/skip/pending)
  - 각 행에 👍 Good / 👎 Bad / ⏭ Skip 버튼, 판정에 따라 행 색상 변경
  - 마크다운 렌더링으로 답변 미리보기
- `scripts/eval_post_optimize.py`:
  - 팀별 p50/p95/max 계산 → `logs/eval_YYYYMMDD_perf.md` 리포트
  - p95 > 20초 팀 자동 플래그 + `knowledge_wiki(entity, period, metric)` 복합 인덱스 ensure (monotonic)
- **run_id=6 실행 중** (2026-04-17 16:12 기동, ETA ~2시간, 450/450 완료 시 자동 종료)

### 3. [버그픽스] 채팅 편집 재전송 시 질문 중복 표시

- `_resendEditedMessage`가 msgEl을 DOM에 남기고 텍스트만 새 것으로 갱신한 뒤 `sendMessage()` 호출 → `appendUserMessage`가 또 추가 → **같은 B 버블이 2개** 렌더링되고 `currentMessages` 배열에도 2번 push
- 수정: msgEl 자체를 제거하고 `currentMessages.splice(cmIdx)` 로 편집 행부터 잘라냄 → `sendMessage()` 가 깨끗하게 재구성
- 회귀 테스트 `tests/frontend/test_edit_resend_no_duplicate.py` 추가 — 버기 구현과 수정 구현 양쪽 invariant 검증 (Playwright 하네스)
- Cache v210 → v211

## 테스트 결과

| 테스트 | 결과 | 비고 |
|--------|------|------|
| `tests/test_anonymization.py` | 7/7 pass | compute_anon_id 결정성·충돌·솔트 가드 |
| `tests/test_config_anon_salt.py` | 2/2 pass | Settings 필드 로드 |
| `tests/test_log_scrub.py` | 4/4 pass | user_id→anon_id 치환, audit 네임스페이스 보존 |
| `tests/frontend/test_edit_resend_no_duplicate.py` | 2/2 pass | 편집 중복 회귀 (Playwright) |
| 전체 회귀 (frontend 제외) | 60/60 pass | 기존 `test_list_models` 제외 (anon 무관) |
| Eval smoke (run_id=5) | 5/5 pass | 답변 1.5~1.7KB, route=notion 정상 |
| Backfill (dev+prod) | 607 convo + 18 fb | distinct anon = distinct uid (32) — 충돌 0 |

## 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/config.py` | `anon_salt` 필드 추가 (env `ANON_SALT`) |
| `app/core/anonymization.py` | **신규** — compute_anon_id / anon_id_for + 솔트 가드 |
| `app/core/log_scrub.py` | **신규** — structlog 프로세서 (user_id→anon_id, email/name drop) |
| `app/db/mariadb.py` | `ensure_anon_columns()` + `ensure_eval_tables()` + DDL |
| `app/api/conversation_api.py` | 모든 SQL 쿼리를 anon_id 기반으로 전환 |
| `app/api/eval_api.py` | **신규** — 관리자 eval review 엔드포인트 (runs/qa/verdict/summary) |
| `app/frontend/eval_review.html` | **신규** — 관리자 리뷰 UI, 👍/👎/⏭ 판정 |
| `app/frontend/chat.html` / `chat.js` | 편집 중복 픽스, 캐시 v210→v211 |
| `app/main.py` | 로그 스크럽 프로세서 체인 연결 + eval_router 마운트 |
| `scripts/migrate_anonymize_conversations.py` | **신규** — 기존 행 백필 (idempotent) |
| `scripts/generate_eval_questions.py` | **신규** — 질문 생성기 (real+synth+clustering) |
| `scripts/eval_post_optimize.py` | **신규** — 팀별 p50/p95 + auto index |
| `tests/eval/playwright_runner.py` | **신규** — 500 Q 배치 러너 |
| `tests/eval/questions_20260417.jsonl` | **신규** — 생성된 450문항 |
| `docs/superpowers/specs/2026-04-17-anonymization-and-eval-design.md` | **신규** — 설계 문서 |
| `docs/superpowers/plans/2026-04-17-anonymization-and-eval.md` | **신규** — 구현 계획 (18 tasks) |
| `.gitignore` | `.env.eval` 추가 |

## 배포

- **Dev (3001)**: 모든 변경 배포 완료, 검증 통과
- **Prod (3000)**: `pm2 reload skin1004-prod` 완료, 익명화 구조 라이브
- 다음 단계: eval run 완료 후 주인님이 `/frontend/eval_review.html` 에서 450문항 판정 → `scripts/eval_post_optimize.py` 로 성능 리포트 생성
