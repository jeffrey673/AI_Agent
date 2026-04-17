"""Generate a diverse ~500-question eval set (10 teams x 50) as JSONL.

Source mix:
- Real queries: user messages from ``messages`` that contain team keywords.
  These reflect actual work questions users have asked.
- Synthetic queries: Gemini Flash fills the remainder by proposing work-style
  questions for each team's topic.

Diversity:
- Dedupe near-identical questions with cosine similarity > 0.85 using the
  project's local BGE-M3 embedder.
- K-means cluster the survivors, then round-robin across clusters so the
  final 50 covers varied subtopics instead of piling onto one theme.

Output: ``tests/eval/questions_YYYYMMDD.jsonl``, one record per line:
  {"team", "source": "real"|"synthetic", "question", "cluster_id"}

Usage:
    python scripts/generate_eval_questions.py
    python scripts/generate_eval_questions.py --per-team 20  # smaller smoke run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from app.core.embeddings import get_embedding_model  # noqa: E402
from app.core.llm import get_flash_client  # noqa: E402
from app.db.mariadb import fetch_all  # noqa: E402


# (display_name, notion_page_id, keyword list for real-query filtering, topic description)
TEAMS: list[tuple[str, str, list[str], str]] = [
    ("법인 태블릿", "2532b4283b0080eba96ce35ae8ba8743",
     ["태블릿", "법인", "ipad"],
     "사내 법인 태블릿(iPad 등) 관리·배포·반납·초기화 관련 업무"),
    ("데이터 분석 파트", "1602b4283b0080f186cfc6425d9a53dd",
     ["데이터 분석", "DA", "분석", "da파트"],
     "SKIN1004 데이터 분석 파트의 업무 체계·프로젝트·도구·프로세스"),
    ("EAST 2팀 가이드", "2e62b4283b00803a8007df0d3003705c",
     ["east 2팀", "이스트", "east2"],
     "EAST 2팀(동부 이커머스) 운영 가이드 및 업무 지침"),
    ("EAST 2026 업무파악", "2e12b4283b0080b48a1dd7bbbd6e0e53",
     ["east", "업무파악", "2026"],
     "EAST팀 2026년도 업무파악 자료 (조직, 역할, 프로세스)"),
    ("EAST 틱톡샵 접속", "19d2b4283b0080dc89d9e6d9c11ec1e5",
     ["틱톡샵", "tiktok shop", "접속"],
     "EAST 팀에서 사용하는 TikTok Shop 접속/로그인 방법 및 계정 관리"),
    ("EAST 해외 출장", "1982b4283b008039ad79ec0c1c1e38fb",
     ["해외 출장", "출장비", "비자"],
     "EAST 팀 해외 출장 절차, 경비, 비자, 법인카드, 일정 작성법"),
    ("WEST 틱톡샵 US", "22e2b4283b008060bac6cef042c3787b",
     ["west", "틱톡샵 us", "tiktokshop us"],
     "WEST 팀의 미국 TikTok Shop 대시보드와 KPI, 광고 성과 분석"),
    ("KBT 스스 운영", "c058d9e89e8a4780b32e866b8248b5b1",
     ["kbt", "스스", "스마트스토어"],
     "KBT 팀의 스마트스토어(스스) 운영 방법 및 일일 업무"),
    ("네이버 스스", "1fb2b4283b00802883faef2df97c6f73",
     ["네이버", "스마트스토어", "스스"],
     "네이버 스마트스토어 업무 공유: 상품등록·프로모션·정산"),
    ("DB daily 광고", "1dc2b4283b0080cb8790cf5218896ebd",
     ["광고", "daily", "광고 입력"],
     "DB팀 daily 광고 입력 업무: 데일리 광고비/성과 시트 작성과 검수"),
]

# A single team's 50 must come from this many clusters so topics don't collapse.
CLUSTERS_PER_TEAM = 18
# Candidates to fetch before dedupe+cluster pick.
SYNTH_PER_TEAM = 100
# Real-query soft cap — we still want a healthy synthetic layer on top.
REAL_CAP_PER_TEAM = 25
# Cosine threshold above which two questions are considered duplicates.
DEDUPE_COSINE = 0.85


def load_real_queries(keyword_sets: list[list[str]], per_team_cap: int) -> list[list[str]]:
    """Return a list (aligned with TEAMS) of deduped real user questions."""
    rows = fetch_all(
        "SELECT m.content FROM messages m "
        "WHERE m.role = 'user' AND m.content IS NOT NULL "
        "ORDER BY m.created_at DESC LIMIT 50000"
    )
    texts_lower: list[tuple[str, str]] = [
        (r["content"], (r["content"] or "").lower()) for r in rows
    ]

    out: list[list[str]] = []
    for keywords in keyword_sets:
        kws = [k.lower() for k in keywords]
        matches: list[str] = []
        seen: set[str] = set()
        for orig, low in texts_lower:
            if not orig:
                continue
            if any(k in low for k in kws):
                clean = orig.strip()
                if clean and clean not in seen and 5 <= len(clean) <= 500:
                    matches.append(clean)
                    seen.add(clean)
            if len(matches) >= per_team_cap:
                break
        out.append(matches)
    return out


SYNTH_PROMPT = """다음은 사내 업무 주제입니다. 이 주제에 대해 실무자(팀원)가
AI 비서에게 실제로 물어볼 법한 업무 질문을 {n}개 생성하세요.

주제: {topic}

요구사항:
- 한국어로, 각 질문은 한 줄, 번호/불릿 없이 출력
- 업무 프로세스, 도구 사용법, 일정, 규정, 트러블슈팅, 담당자, 파일 위치 등
  다양한 각도로 분산 (같은 유형을 반복하지 말 것)
- 매우 구체적인 것 ~ 매우 일반적인 것을 골고루
- 한 줄에 하나씩, 질문만 출력 (답변 금지, 설명 금지)
"""


async def synthesize_for_team(topic: str, n: int) -> list[str]:
    """Ask Flash for ``n`` candidate questions about ``topic``."""
    client = get_flash_client()
    prompt = SYNTH_PROMPT.format(topic=topic, n=n)
    # Flash client exposes a sync .generate(prompt); wrap for the event loop.
    resp = await asyncio.to_thread(client.generate, prompt)
    text = resp if isinstance(resp, str) else str(resp)
    # Parse: strip leading bullets/numbers, keep only real-looking questions.
    def _clean(ln: str) -> str:
        return ln.strip().lstrip("-*·0123456789.) \t")
    lines = [_clean(ln) for ln in text.splitlines()]
    out, seen = [], set()
    for ln in lines:
        if not ln or len(ln) < 5 or len(ln) > 300:
            continue
        looks_question = "?" in ln or ln.endswith(("까", "죠", "요", "야", "나", "?"))
        if not looks_question:
            continue
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return out[:n]


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _dedupe(candidates: list[str], vecs: np.ndarray, threshold: float) -> tuple[list[str], np.ndarray]:
    """Greedy: for each candidate, drop if too close to any already-kept one."""
    keep_idx: list[int] = []
    for i, _ in enumerate(candidates):
        dup = False
        for j in keep_idx:
            if _cosine_sim(vecs[i], vecs[j]) > threshold:
                dup = True
                break
        if not dup:
            keep_idx.append(i)
    return [candidates[i] for i in keep_idx], vecs[keep_idx]


def _pick_diverse(
    candidates: list[str],
    vecs: np.ndarray,
    target: int,
    k_clusters: int,
    sources_aligned: list[str],
) -> list[dict]:
    """Pick ``target`` questions spread across clusters."""
    if len(candidates) <= target:
        return [
            {"question": q, "cluster_id": i % k_clusters, "source": sources_aligned[i]}
            for i, q in enumerate(candidates)
        ]
    from sklearn.cluster import KMeans

    k = min(k_clusters, len(candidates))
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(vecs)
    labels = km.labels_
    by_cluster: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        by_cluster.setdefault(int(lab), []).append(idx)

    picks: list[dict] = []
    # Round-robin across clusters, preferring real queries first inside a cluster
    cluster_keys = list(by_cluster.keys())
    # Sort each cluster's indices so that 'real' comes before 'synthetic'
    for lab in cluster_keys:
        by_cluster[lab].sort(key=lambda i: 0 if sources_aligned[i] == "real" else 1)

    while len(picks) < target and any(by_cluster[lab] for lab in cluster_keys):
        for lab in cluster_keys:
            if by_cluster[lab]:
                idx = by_cluster[lab].pop(0)
                picks.append({
                    "question": candidates[idx],
                    "cluster_id": lab,
                    "source": sources_aligned[idx],
                })
                if len(picks) >= target:
                    break
    return picks


async def build_for_team(
    team: str, topic: str, real: list[str],
    per_team: int, synth_per_team: int, clusters: int,
) -> list[dict]:
    # Synthesize on top of real queries so every team reaches ``per_team + margin``
    needed = max(synth_per_team, per_team * 3 - len(real))
    synth = await synthesize_for_team(topic, needed)
    candidates = real + synth
    sources_aligned = (["real"] * len(real)) + (["synthetic"] * len(synth))
    if not candidates:
        return []

    embedder = get_embedding_model()
    vecs = np.array(embedder.embed(candidates), dtype=np.float32)
    kept, kept_vecs = _dedupe(candidates, vecs, DEDUPE_COSINE)
    # Re-align sources to kept set
    kept_sources = []
    j = 0
    for i, q in enumerate(candidates):
        if j < len(kept) and candidates[i] == kept[j]:
            kept_sources.append(sources_aligned[i])
            j += 1
    # Fallback if alignment drifted (rare)
    if len(kept_sources) != len(kept):
        kept_sources = ["synthetic"] * len(kept)

    picks = _pick_diverse(kept, kept_vecs, per_team, clusters, kept_sources)
    return [
        {"team": team, "source": p["source"], "question": p["question"], "cluster_id": p["cluster_id"]}
        for p in picks
    ]


async def main_async(per_team: int, out_path: Path) -> int:
    reals = load_real_queries(
        [kws for (_t, _p, kws, _d) in TEAMS], REAL_CAP_PER_TEAM
    )
    rows: list[dict] = []
    for (team, _page_id, _kws, topic), real in zip(TEAMS, reals):
        print(f"[{team}] real={len(real)}  synthesizing...", flush=True)
        out = await build_for_team(
            team, topic, real,
            per_team=per_team,
            synth_per_team=SYNTH_PER_TEAM,
            clusters=CLUSTERS_PER_TEAM,
        )
        print(f"[{team}] picked {len(out)}")
        rows.extend(out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(rows)} rows → {out_path}")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-team", type=int, default=50)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    date = datetime.now().strftime("%Y%m%d")
    out_path = Path(args.out) if args.out else Path("tests/eval") / f"questions_{date}.jsonl"
    return 0 if asyncio.run(main_async(args.per_team, out_path)) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
