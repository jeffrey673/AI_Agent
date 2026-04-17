"""Eval run review endpoints (admin only).

Serves the review UI (`/frontend/eval_review.html`):
- list runs
- page through a run's Q/A, filter by verdict/team
- mark a row as good/bad/skip
- show summary counts for a run
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth_middleware import get_current_user
from app.core.anonymization import anon_id_for
from app.db.mariadb import execute, fetch_all, fetch_one
from app.db.models import User

eval_router = APIRouter(prefix="/api/admin/eval", tags=["eval"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user


@eval_router.get("/runs")
async def list_runs(_: User = Depends(_require_admin)) -> dict:
    rows = await asyncio.to_thread(
        fetch_all,
        "SELECT id, started_at, finished_at, total, done, notes "
        "FROM eval_runs ORDER BY id DESC LIMIT 100",
    )
    # Normalize datetimes for JSON
    for r in rows:
        for k in ("started_at", "finished_at"):
            if r.get(k) is not None:
                r[k] = r[k].isoformat()
    return {"runs": rows}


@eval_router.get("/runs/{run_id}/qa")
async def list_qa(
    run_id: int,
    verdict: Optional[str] = None,
    team: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
    _: User = Depends(_require_admin),
) -> dict:
    where = ["run_id = %s"]
    params: list = [run_id]
    if verdict:
        where.append("verdict = %s")
        params.append(verdict)
    if team:
        where.append("team = %s")
        params.append(team)

    where_clause = " AND ".join(where)
    count_row = await asyncio.to_thread(
        fetch_one,
        f"SELECT COUNT(*) AS c FROM eval_qa WHERE {where_clause}",
        tuple(params),
    )
    total = int(count_row["c"]) if count_row else 0

    params_with_paging = params + [limit, offset]
    rows = await asyncio.to_thread(
        fetch_all,
        f"SELECT id, team, question, answer, route, response_time_ms, "
        f"conversation_id, source, verdict, reviewed_at "
        f"FROM eval_qa WHERE {where_clause} ORDER BY id LIMIT %s OFFSET %s",
        tuple(params_with_paging),
    )
    for r in rows:
        if r.get("reviewed_at") is not None:
            r["reviewed_at"] = r["reviewed_at"].isoformat()
    return {"rows": rows, "total": total}


class VerdictBody(BaseModel):
    verdict: str  # good | bad | skip | pending


@eval_router.post("/qa/{qa_id}/verdict")
async def set_verdict(
    qa_id: int, body: VerdictBody, user: User = Depends(_require_admin)
) -> dict:
    if body.verdict not in ("good", "bad", "skip", "pending"):
        raise HTTPException(status_code=400, detail="invalid verdict")
    anon = anon_id_for(user.id)
    await asyncio.to_thread(
        execute,
        "UPDATE eval_qa SET verdict = %s, reviewed_at = %s, reviewed_by_anon = %s "
        "WHERE id = %s",
        (body.verdict, datetime.utcnow(), anon, qa_id),
    )
    return {"ok": True, "verdict": body.verdict}


@eval_router.get("/runs/{run_id}/summary")
async def run_summary(run_id: int, _: User = Depends(_require_admin)) -> dict:
    counts = await asyncio.to_thread(
        fetch_all,
        "SELECT verdict, COUNT(*) AS c FROM eval_qa WHERE run_id = %s GROUP BY verdict",
        (run_id,),
    )
    by_team = await asyncio.to_thread(
        fetch_all,
        "SELECT team, COUNT(*) AS total, "
        "SUM(CASE WHEN verdict='good' THEN 1 ELSE 0 END) AS good, "
        "SUM(CASE WHEN verdict='bad' THEN 1 ELSE 0 END) AS bad, "
        "SUM(CASE WHEN verdict='skip' THEN 1 ELSE 0 END) AS skip_, "
        "AVG(response_time_ms) AS avg_ms "
        "FROM eval_qa WHERE run_id = %s GROUP BY team ORDER BY team",
        (run_id,),
    )
    return {
        "run_id": run_id,
        "counts": {r["verdict"]: int(r["c"]) for r in counts},
        "by_team": [
            {
                "team": r["team"],
                "total": int(r["total"]),
                "good": int(r["good"] or 0),
                "bad": int(r["bad"] or 0),
                "skip": int(r["skip_"] or 0),
                "avg_ms": float(r["avg_ms"] or 0),
            }
            for r in by_team
        ],
    }
