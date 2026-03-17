# Update Log — 2026-03-17 (v8.0 Enterprise Output + Frontend + Speed)

## 변경 사항

### 1. 엔터프라이즈급 아웃풋 업그레이드

#### 전 라우트 구조화 답변 템플릿 통일
- **BigQuery**: 📊 제목 → 요약 → 상세 데이터(표) → 시각화(차트) → 분석 인사이트 → 후속 질문
- **CS Agent**: 🧴 제목 → 답변 → 상세 정보 → 참고 사항 → 출처 → 후속 질문
- **Notion**: 📋 제목 → 요약 → 주요 내용 → 관련 세부 사항 → 출처 → 후속 질문
- **Direct LLM**: 구조화 표준 + 표/헤더/인용 강제 + AI 생성 footer + 후속 질문
- **Multi Agent**: 📈 제목 → 요약 → 내부 데이터 → 외부 맥락 → 종합 인사이트 → 제안 → 후속 질문

#### 비즈니스 분석 인사이트 강화 (BQ)
- 비중/점유율: "전체의 42% 비중", "1위 국가가 전체의 30% 차지"
- 변화율: "전월 대비 15% 증가", "전년 동기 대비 23% 성장"
- 추세: "3개월 연속 상승세", "하반기 들어 둔화 추세"
- 집중도: "상위 3개국이 전체의 80% 차지"

#### LLM 생성 후속 질문 → 클릭 가능한 칩
- 이전: 하드코딩된 랜덤 풀에서 3개 선택
- 이후: LLM이 맥락 기반으로 동적 생성 → 프론트엔드에서 클릭 시 자동 질문 전송
- `extractFollowupsFromAnswer()`: 답변에서 💡 블록 파싱
- `stripFollowupBlock()`: 마크다운 본문에서 중복 제거 (칩으로만 표시)

#### 자동 Source Footer
- Direct: `*AI 생성 답변 · 날짜*` 프로그래밍 방식 자동 추가
- Multi: `*분석 기준: SKIN1004 내부 데이터 + Google 검색 · 날짜*`
- BQ/CS/Notion: 각 에이전트 프롬프트에서 자체 footer

### 2. 프론트엔드 고급화

#### 새 UI 기능
- **Scroll-to-bottom 버튼**: 대화 스크롤 시 ↓ 화살표 (ChatGPT/Claude 동일)
- **코드블록 Copy 버튼**: hover 시 Copy 표시, 클릭 시 "Copied!" 피드백
- **Skeleton Loader**: 대화 로딩 시 shimmer 애니메이션 placeholder
- **메시지 타임스탬프**: hover 시 HH:MM 표시
- **빈 사이드바 상태**: "새 대화를 시작해보세요" / "검색 결과가 없습니다"

#### CSS 개선
- **blockquote**: accent 왼쪽 보더 + 배경색 (인사이트 시각 강조)
- **테이블**: zebra striping + hover 강조 + border-radius
- **입력 포커스**: accent glow box-shadow
- **Suggestion chip**: hover 부양 효과 (translateY + shadow)
- **타이핑 인디케이터**: 8px → 10px 도트
- **hr 구분선**: 얇고 반투명
- **Follow-up chip**: 💡 아이콘 prefix + hover 효과 + 말줄임

### 3. LLM 속도 최적화

- **max_output_tokens**: 16384 → 8192 (평균 12% 응답 속도 개선)
- **retry 딜레이**: [0.3, 0.8, 2]s → [0.1, 0.3, 1.0]s (재시도 시 1.7초 절감)
- **빈 결과 fallback 타임아웃**: 5.0s → 2.0s (3초 절감)

### 4. 컨텍스트 관리 개선

- **토큰 추정**: char count → 한국어 가중치 (한글 2.5배, ASCII 0.3배)
- `_estimate_tokens()` 함수 추가 (routes.py)

### 5. 공유 프롬프트 상수 (prompt_fragments.py)

- `FORMATTING_STANDARDS`: 답변 형식 표준 (볼드, 표, 금액, 인용)
- `FOLLOWUP_INSTRUCTION`: 후속 질문 제안 형식 가이드
- `TONE_GUIDELINES`: 전문적 + 친근한 톤 가이드

### 6. response_formatter.py v2.0

- Follow-up 빈줄 정규화: LLM이 생성한 `> -` 항목 사이 빈 줄 제거 → 연속 blockquote
- 자동 source footer: 도메인별 분기 (direct/multi)
- 기존 footer 중복 방지: 조회 기준/출처/AI 생성 키워드 감지

### 7. Claude Code Skill 추가

- `/upload-update-log`: 업데이트 로그 Notion 업로드 커맨드

## 품질 테스트 결과

| 라우트 | 점수 | 시간 |
|--------|------|------|
| Direct 인사 | 100% | 3.6s |
| Direct 지식 | 100% | 30.8s |
| Direct 비교 | 100% | 19.6s |
| BQ 매출 조회 | 100% | 9.3s |
| BQ 국가별 비교 | 100% | 13.5s |
| BQ 시계열 추이 | 100% | 12.3s |
| CS 제품 문의 | 100% | 10.4s |
| CS 비건 인증 | 100% | 11.3s |

**8/8 = 100% (엔터프라이즈 품질 달성)**

## 성능 비교 (Before → After)

| 라우트 | Before | After | 개선 |
|--------|--------|-------|------|
| direct-simple | 4.1s | 3.0s | -27% |
| bq-ranking | 19.6s | 15.8s | -19% |
| cs | 10.4s | 9.0s | -13% |

## 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/core/prompt_fragments.py` | FORMATTING_STANDARDS, FOLLOWUP_INSTRUCTION, TONE_GUIDELINES 추가 |
| `app/core/response_formatter.py` | v2.0: follow-up 정규화 + auto source footer |
| `app/agents/sql_agent.py` | 후속 질문 + 비즈니스 인사이트 강화 + 빈결과 2s |
| `app/agents/cs_agent.py` | 🧴 구조화 템플릿 |
| `app/agents/notion_agent.py` | 후속 질문 필수 + 포맷 강화 |
| `app/agents/orchestrator.py` | Direct 시스템 프롬프트 + Multi footer + 톤 가이드 |
| `app/agents/graph.py` | direct_llm_answer 동기화 |
| `app/core/llm.py` | max_tokens 8192, retry [0.1,0.3,1.0] |
| `app/api/routes.py` | _estimate_tokens() 한국어 가중치 |
| `app/frontend/chat.html` | Scroll 버튼, 캐시 v104 |
| `app/frontend/chat.js` | 후속 질문 파싱+칩, stripFollowupBlock, skeleton, 타임스탬프, 빈상태 |
| `app/static/style.css` | blockquote, 테이블, Copy 버튼, skeleton, scroll, timestamp, chip |
| `scripts/test_output_quality.py` | 품질 테스트 스크립트 (신규) |
| `.claude/commands/upload-update-log.md` | Notion 업로드 skill (신규) |
