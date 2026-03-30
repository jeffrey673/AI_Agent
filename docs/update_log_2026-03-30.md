# 업데이트 로그 — 2026-03-30

## 대규모 UX 업그레이드 (Wave 1~4 + 스트리밍 개선)

### 배경
- 사용자 피드백: "속도가 약함, 응답도 시원찮음"
- ChatGPT/Gemini급 상용 품질 목표
- /office-hours 디자인 문서 기반 3+1 Wave 계획 실행

### Wave 1: 체감 속도 개선 (`8770caa`)
- **스트리밍 파이프라인**: 300ms throttle 제거 → incremental append + 문장 경계 마크다운 렌더링
- **Skeleton UI**: 서버 keyword 분류 직후 source 이벤트 즉시 발송 (LLM 재분류 전)
- **Client-side pre-routing**: chat.js에 keyword 즉시 분류기 → fetch 전 route별 로딩 메시지
- **Brand filter JWT 캐싱**: 매 요청 DB 조회 제거, JWT claims에 포함 (하위 호환 fallback)

### Wave 2: 응답 품질 + 안정성 (`2f9fca8`)
- **라우팅 오버라이드**: 짧은 인사말(<5자), 외부 주제(부동산/주식/코인) → 무조건 direct
- **프롬프트 강화**: 짧은 질문엔 짧게, 서론 없이 핵심부터, 후속질문 형식 통일
- **CircuitBreaker 활성화**: Notion/GWS/CS/Multi에 연결 (3회 실패 → 60초 차단)
- **Timeout**: 비스트리밍 15초, Multi 30초, BQ 30초 — 초과 시 부분 결과 반환

### Wave 3: UI 폴리시 (`dc4163e`)
- 메시지 등장 slide-up + fade-in 애니메이션
- 사이드바 open/close smooth transition
- 테이블 가로 스크롤 래퍼 (반응형)
- 코드블록 border + line-height 개선
- Toast 알림 시스템 (error/success/info)

### Wave 4: 관측성 (`b9e9425`)
- 성능 타이밍: first_token_ms, total_ms, route → SSE 메타데이터 + structlog
- 감사 로깅: audit_logs 테이블 (MariaDB/SQLite), fire-and-forget 기록

### 스트리밍 자연스러움 (`b57c932`, `6a542b8`)
- **토큰 버퍼 큐**: 서버 청크를 큐에 저장 → rAF로 3-20자씩 드레인 (적응형 속도)
- **단락 분리 렌더링**: 완료 단락만 마크다운 파싱, 타이핑 꼬리는 raw text
- **연속 질문 버그 수정**: 스트리밍 상태를 _S 객체로 통합, 이전 상태 완전 리셋

### 복사 버튼 수정 (`e260ea7`)
- clipboard API + execCommand fallback (HTTP 환경 지원)
- 복사 성공 시 체크 아이콘 + toast 표시

### 성능 측정 (Wave 완료 후)
| 쿼리 타입 | First Token | Total |
|-----------|------------|-------|
| Direct (hello) | 2,234ms | 4,391ms |
| Direct (회사 소개) | 1,655ms | 11,141ms |
| BigQuery (이번달 매출) | 11,889ms | 13,000ms |

### 변경 규모
- **8커밋**, 11개 파일, +500줄 이상
- 핵심 파일: chat.js, style.css, orchestrator.py, routes.py, auth_api.py, auth_middleware.py, mariadb.py, main.py
