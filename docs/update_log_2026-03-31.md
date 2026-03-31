# Update Log — 2026-03-31 (v8.1 — Design System + QA Fix)

## 변경 사항

### 1. [UI] 디자인 시스템 전면 개선 (12 commits)

#### 접근성 강화
- `prefers-reduced-motion` 지원 추가 — 모션 감도가 높은 사용자를 위해 모든 애니메이션 비활성화
- `color-scheme: dark light` 선언 — OS 레벨 다크모드 인식
- `:focus-visible` 키보드 포커스 스타일 추가 — 키보드 네비게이션 시 오렌지 아웃라인 표시
- ARIA 접근성 강화 — sidebar, 검색, drawer에 role/aria-label 추가 (6개 → 14개)

#### 타이포그래피
- Pretendard 한글 웹폰트 CDN 로드 추가 — 한글 렌더링 품질 향상
- DESIGN.md 기반 type scale CSS 변수 정의 (--text-2xs ~ --text-3xl + --text-ui, --text-caption)
- font-size 하드코딩 72곳 → CSS 변수 교체 (10px, 11px, 12px, 13px, 14px, 18px)
- AI 메시지 본문 font-size 15px → 16px (var(--text-md))
- body line-height: 1.5 명시

#### 성능 최적화
- `transition: all` 21곳 전부 제거 → 각 요소별 구체적 속성 명시 (background-color, color, opacity 등)
- --duration-short/normal/long CSS 변수 도입 (0.15s/0.2s/0.3s)
- font preconnect 링크 추가 (fonts.googleapis.com, gstatic, jsdelivr)
- theme-color 메타 #171717 → #111111 (DESIGN.md 일치)

#### CSS 변수 일관성
- `#ef4444` → `var(--error)`, `#22c55e` → `var(--success)` 전역 교체
- `#dc2626`, `#e53e3e`, `#c53030` → `var(--error)` 교체
- `border-radius: 999px` → `var(--radius-full)` 전역 교체
- `var(--danger)` → `var(--error)` 통일
- spacing 하드코딩 47곳 → `var(--space-*)` 교체 (gap, padding, margin)

#### 콘텐츠/UX
- Drawer 제목 ALL CAPS 제거 — "USER MANAGEMENT" → "User Management" (Title Case + Figtree)
- chart-container 인라인 스타일 → CSS 클래스로 이전
- 코드 복사 체크마크 SVG 색상 → CSS 변수 사용

### 2. [버그] QA 발견 이슈 수정

#### 제품명 언더스코어 노출 수정 (ISSUE-001)
- 이전: `SK_Centella_Light_Cleansing_Oil_200ml` (DB 원본 형식)
- 이후: `SK Centella Light Cleansing Oil 200ml` (읽기 쉬운 형식)
- `_humanize_row()` 함수 도입 — product/set/제품 등 패턴으로 제품명 컬럼 자동 감지
- SQL 프롬프트에 언더스코어 사용 금지 규칙 추가

#### 후속 질문 칩 미표시 수정 (ISSUE-002)
- `showFollowups()` 함수가 정의만 되고 호출되지 않던 버그 수정
- 스트리밍 완료 시점에 `showFollowups(text, cleanContent)` 호출 추가
- LLM 생성 후속 질문이 클릭 가능한 칩으로 하단에 표시됨

## QA 테스트 결과

| 테스트 | 결과 | 비고 |
|--------|------|------|
| 제안 칩 클릭 (쇼피 매출) | PASS | BQ 라우트, 구조화된 응답 |
| 회사 소개 질문 | PASS | Direct LLM, 정확한 정보 |
| 아마존 Top 5 제품 | PASS | 차트 시각화 포함 |
| 무의미한 입력 | PASS | Graceful 에러 처리 |
| 후속 질문 칩 | PASS | 3개 칩 정상 표시 |
| Health Score | 88/100 | Console 70, Functional 90, UX 85 |

## 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| app/static/style.css | 디자인 시스템 전면 개선 (462줄 변경) |
| app/frontend/chat.html | preconnect, ARIA, drawer 제목 |
| app/frontend/login.html | preconnect, theme-color |
| app/frontend/chat.js | 후속 질문 칩 호출, chart CSS 변수 |
| app/agents/sql_agent.py | 제품명 휴머나이징, 프롬프트 개선 |

## CSS 변수 사용률 (Before → After)

| 카테고리 | Before | After |
|---------|:------:|:-----:|
| Spacing (--space-*) | 0 | 58 |
| Font (--text-*) | 0 | 164 |
| Color (semantic) | ~40 | 100 |
| transition: all | 21 | 0 |

## Design Score: B+ → A-
