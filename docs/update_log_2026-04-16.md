# Update Log — 2026-04-16 (Knowledge Map v1.0)

## 개요

카파시(Karpathy) LLM Wiki + Graphify 개념을 결합한 **정적 지식 지도 시스템** 구축. Claude Code 세션이 매번 grep/파일 탐색하는 비효율을 해결. 매일 새벽 3시 자동 리빌드로 항상 최신 상태 유지.

**핵심 효과**: 에이전트가 질문에 답할 때 원본 파일 전체를 읽는 대신, 1페이지 요약(GRAPH_REPORT.md) + 관련 노드 2-3개만 읽음 → **쿼리당 토큰 최대 71.5배 절감** (Graphify 벤치 기준)

## 변경 사항

### 1. 기능: Knowledge Map 빌드 파이프라인 (7개 모듈)

- `app/knowledge_map/` 패키지 신규 생성 (~700줄)
  - `config.py` — 경로, 제외 패턴, Flash 병렬 설정
  - `cache.py` — SHA256 + mtime 파일 지문 캐시 (증분 빌드용)
  - `ast_parser.py` — Python AST 추출 (클래스/함수/임포트/독스트링)
  - `md_parser.py` — Markdown 구조 추출 (H1-H6/링크/날짜)
  - `semantic.py` — Gemini Flash 의미 추출 (개념·관계·요약, asyncio.Semaphore N=10)
  - `graph.py` — NetworkX 그래프 + Louvain 커뮤니티 탐지
  - `exporters.py` — graph.json + wiki/index.md + GRAPH_REPORT.md + log.md 내보내기
  - `builder.py` — 전체 파이프라인 오케스트레이터

### 2. 기능: CLI 도구 + 검증기

- `scripts/build_knowledge_graph.py` — `--force` / `--dry-run` / `--bootstrap`
- `scripts/validate_graph.py` — graph.json 스키마·무결성·엣지 타입 검증
- `scripts/register_knowledge_task.ps1` — Windows Task Scheduler 등록

### 3. 기능: Flash 프롬프트 3종

- `prompts/knowledge_map/extract_concepts.txt` — 파일별 개념·관계 추출
- `prompts/knowledge_map/synthesize_wiki.txt` — 클러스터별 위키 페이지 합성
- `prompts/knowledge_map/synthesize_report.txt` — GRAPH_REPORT.md 합성

### 4. 기능: CLAUDE.md 트리거 (최상단 삽입)

- "모든 작업 전에 `knowledge_map/GRAPH_REPORT.md`를 먼저 읽어라" — Claude Code가 자동으로 지식 지도부터 탐색
- Grep/Glob 직행 금지 규칙 명시
- 다음 세션부터 즉시 적용

### 5. 인프라: Task Scheduler 자동화

- `SKIN1004-Graphify-Daily` — 매일 03:00 증분 리빌드
- 기존 `SKIN1004-AD-Sync-Daily` (22:00) 패턴 동일

### 6. 설계 문서

- `docs/superpowers/specs/2026-04-16-knowledge-map-design.md` — 설계 스펙
- `docs/superpowers/plans/2026-04-16-knowledge-map.md` — 16개 task 구현 플랜

## 초기 빌드 결과 (Bootstrap)

| 항목 | 값 |
|------|------|
| 인덱싱 파일 | 109개 (.py + .md) |
| 노드 | 972개 |
| 엣지 | 1,966개 |
| 클러스터 | 31개 (Louvain) |
| 빌드 시간 | 92초 |
| Flash 호출 | 109회 (Gemini 2.5 Flash) |
| Validator | Errors: 0 / Warnings: 47 (비표준 엣지 타입) |

## 테스트 결과

| 테스트 | 결과 | 시간 |
|--------|------|------|
| test_knowledge_map_cache (6) | PASS | 0.09s |
| test_knowledge_map_ast (4) | PASS | 0.07s |
| test_knowledge_map_md (5) | PASS | 0.08s |
| test_knowledge_map_semantic (2) | PASS | 0.13s |
| test_knowledge_map_graph (3) | PASS | 0.27s |
| test_knowledge_map_exporters (4) | PASS | 0.25s |
| **전체 (24 tests)** | **ALL PASS** | **0.41s** |

## 산출물

| 파일 | 설명 |
|------|------|
| `knowledge_map/graph.json` | 972 nodes, 1966 edges (JSON, 정렬된 diff-friendly) |
| `knowledge_map/GRAPH_REPORT.md` | 1페이지 요약 — 에이전트 첫 진입점 |
| `knowledge_map/wiki/index.md` | 31 클러스터 목차 |
| `knowledge_map/wiki/log.md` | 빌드 기록 (append-only) |

## 주요 설계 결정

| 결정 | 이유 |
|------|------|
| graphify 도구 대신 커스텀 구현 | Flash가 Claude subagent보다 10배 저렴, 03:00 무인 실행 가능, Windows 설치 무통증 |
| `app/knowledge_map/` 네이밍 | 기존 `app/knowledge/` (런타임 대화 지식 시스템)과 충돌 회피 |
| Louvain (python-louvain) | Leiden보다 설치 간단 (순수 Python), 품질 충분 |
| graph.json git 추적 | 변경 이력 추적 가능, PR에서 지식 지도 변화 리뷰 가능 |
| v1.0 구조적 REPORT | Flash 내러티브 합성은 v1.1로 연기 — 핵심 가치는 이미 전달 |

## 수정 파일 (35개 신규)

| 파일 | 변경 내용 |
|------|-----------|
| `app/knowledge_map/__init__.py` | 모듈 마커 (docstring only) |
| `app/knowledge_map/config.py` | 경로, 제외 패턴, Flash 설정 |
| `app/knowledge_map/cache.py` | SHA256 + mtime 캐시 |
| `app/knowledge_map/ast_parser.py` | Python AST 파서 |
| `app/knowledge_map/md_parser.py` | Markdown 구조 파서 |
| `app/knowledge_map/semantic.py` | Gemini Flash 의미 추출 |
| `app/knowledge_map/graph.py` | NetworkX + Louvain |
| `app/knowledge_map/exporters.py` | JSON/MD 내보내기 |
| `app/knowledge_map/builder.py` | 빌드 오케스트레이터 |
| `scripts/build_knowledge_graph.py` | CLI 엔트리포인트 |
| `scripts/validate_graph.py` | 그래프 검증기 |
| `scripts/register_knowledge_task.ps1` | Task Scheduler 등록 |
| `prompts/knowledge_map/*.txt` | Flash 프롬프트 3종 |
| `tests/test_knowledge_map_*.py` | 유닛 테스트 6개 파일 (24 tests) |
| `knowledge_map/*` | 빌드 산출물 |
| `CLAUDE.md` | Knowledge Map 트리거 섹션 추가 |
| `requirements.txt` | networkx, python-louvain 추가 |
| `.gitignore` | knowledge_map/.cache/ 제외 |

## v1.1 예정 (후속)

- per-cluster 내러티브 위키 페이지 (Flash 합성)
- GRAPH_REPORT.md "What this project is" Flash 내러티브
- 비표준 엣지 타입 → `related_to` 정규화
- wiki_page 필드 노드에 연결
