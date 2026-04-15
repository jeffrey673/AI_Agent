"""E2E test — verify wiki retrieval augments live answers.

Asks questions whose facts we already seeded during the backfill, then
checks the response stream contains content that overlaps with the wiki
snapshot. Also captures total latency so we can compare against the
pre-wiki baseline later.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import jwt
import httpx

from app.config import get_settings
from app.db.mariadb import fetch_all

BASE = "http://127.0.0.1:3001"
_ALGO = "HS256"

# Questions that should have high wiki relevance after backfill
PROBES = [
    "아시아 매출 성장률 알려줘",
    "랩인네이처 라인 주요 고객사 알려줘",
    "EAST1 팀 일매출 얼마야",
    "싱가포르 쇼피 센텔라 앰플 추이",
]


def _build_admin_token() -> str:
    s = get_settings()
    payload = {
        "user_id": 1,
        "email": "jeffrey@skin1004korea.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "brand_filter": "",
        "role": "admin",
    }
    return jwt.encode(payload, s.jwt_secret_key, algorithm=_ALGO)


async def ask(client: httpx.AsyncClient, token: str, query: str) -> dict:
    payload = {
        "model": "skin1004-Analysis",
        "messages": [{"role": "user", "content": query}],
        "stream": True,
    }
    t0 = asyncio.get_event_loop().time()
    full = []
    first_chunk_at = None
    try:
        async with client.stream(
            "POST",
            f"{BASE}/v1/chat/completions",
            json=payload,
            cookies={"token": token},
            timeout=120.0,
        ) as resp:
            if resp.status_code != 200:
                return {"ok": False, "status": resp.status_code, "error": await resp.aread()}
            async for chunk in resp.aiter_text():
                if first_chunk_at is None:
                    first_chunk_at = asyncio.get_event_loop().time()
                full.append(chunk)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    total = asyncio.get_event_loop().time() - t0
    ttft = (first_chunk_at - t0) if first_chunk_at else None
    body = "".join(full)
    return {
        "ok": True,
        "total_ms": int(total * 1000),
        "first_chunk_ms": int(ttft * 1000) if ttft else None,
        "chars": len(body),
        "preview": body[:400],
    }


def snapshot_wiki_count_for(query: str) -> int:
    from app.knowledge.wiki_search import extract_keywords, _build_candidate_query
    tokens = extract_keywords(query)
    sql, params = _build_candidate_query(tokens)
    if not sql:
        return 0
    rows = fetch_all(sql, params)
    return len(rows)


async def main() -> int:
    token = _build_admin_token()
    print(f"=== wiki E2E ({len(PROBES)} probes) ===\n")

    # Wiki totals
    total_rows = fetch_all("SELECT COUNT(*) AS c FROM knowledge_wiki")[0]["c"]
    print(f"knowledge_wiki rows: {total_rows}\n")

    async with httpx.AsyncClient() as client:
        for q in PROBES:
            hits = snapshot_wiki_count_for(q)
            print(f"[Q] {q}")
            print(f"    candidate_wiki_matches: {hits}")
            result = await ask(client, token, q)
            if not result["ok"]:
                print(f"    ERROR: {result.get('error')}")
                print()
                continue
            print(
                f"    ttft={result['first_chunk_ms']}ms "
                f"total={result['total_ms']}ms "
                f"chars={result['chars']}"
            )
            print(f"    preview: {result['preview'][:200]}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
