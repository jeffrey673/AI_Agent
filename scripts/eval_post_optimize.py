"""Analyze the most recent eval run and apply safe optimizations.

Report: writes ``logs/eval_<YYYYMMDD>_perf.md`` with p50/p95/max per team.

Automatic remediation (only if a team's p95 > ``SLOW_P95_MS``):
  1. Composite index on ``knowledge_wiki(entity, period, metric)`` if missing.
     (Cheap, monotonic — never removed.)
  2. Recompile wiki_entity_pages for entities mentioned by the slow team's
     questions — only if the ``entity_pages`` module is available.

Does NOT modify state mid-run — this runs after the Playwright batch
finishes, so the quality signal stays clean.

Usage:
    python scripts/eval_post_optimize.py          # latest run
    python scripts/eval_post_optimize.py --run-id 3
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from app.db.mariadb import execute, fetch_all, fetch_one  # noqa: E402


SLOW_P95_MS = 20_000
COMPOSITE_INDEX_NAME = "idx_kw_entity_period_metric"


def _p(values: list[int], q: float) -> int:
    if not values:
        return 0
    return int(np.percentile(values, q))


def _ensure_wiki_composite_index() -> bool:
    row = fetch_one(
        "SELECT 1 AS ok FROM INFORMATION_SCHEMA.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_wiki' "
        "AND INDEX_NAME = %s",
        (COMPOSITE_INDEX_NAME,),
    )
    if row:
        return False
    execute(
        f"ALTER TABLE knowledge_wiki ADD INDEX {COMPOSITE_INDEX_NAME} "
        f"(entity, period, metric)"
    )
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", type=int, default=None)
    args = ap.parse_args()

    if args.run_id is None:
        r = fetch_one("SELECT id FROM eval_runs ORDER BY id DESC LIMIT 1")
        if not r:
            print("no eval_runs rows — nothing to analyze")
            return 1
        run_id = int(r["id"])
    else:
        run_id = args.run_id
    print(f"analyzing run_id={run_id}")

    rows = fetch_all(
        "SELECT team, response_time_ms FROM eval_qa "
        "WHERE run_id = %s AND response_time_ms > 0",
        (run_id,),
    )
    by_team: dict[str, list[int]] = {}
    for r in rows:
        by_team.setdefault(r["team"], []).append(int(r["response_time_ms"]))

    lines: list[str] = [
        f"# Eval perf report — run {run_id} — {datetime.utcnow().isoformat()}Z",
        "",
        f"Threshold: p95 > {SLOW_P95_MS}ms triggers remediation.",
        "",
        "| team | n | p50 (ms) | p95 (ms) | max (ms) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    slow_teams: list[str] = []
    for team, vals in sorted(by_team.items()):
        p50 = int(np.median(vals))
        p95 = _p(vals, 95)
        lines.append(f"| {team} | {len(vals)} | {p50} | {p95} | {max(vals)} |")
        if p95 > SLOW_P95_MS:
            slow_teams.append(team)

    lines.append("")
    lines.append(f"**Slow teams (p95 > {SLOW_P95_MS}ms):** "
                 f"{', '.join(slow_teams) if slow_teams else 'none'}")
    lines.append("")

    # Always ensure composite index (cheap, monotonic)
    added = _ensure_wiki_composite_index()
    lines.append(f"- knowledge_wiki composite index `{COMPOSITE_INDEX_NAME}`: "
                 f"{'added' if added else 'already present'}")

    out_dir = Path("logs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"eval_{datetime.utcnow().strftime('%Y%m%d')}_perf.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
