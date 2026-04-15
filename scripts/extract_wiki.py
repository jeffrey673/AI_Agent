"""CLI — extract facts from recent conversations into knowledge_wiki.

Usage (from project root):
    python scripts/extract_wiki.py                    # last 60 min, up to 100 pairs
    python scripts/extract_wiki.py --minutes 1440     # last 24 h
    python scripts/extract_wiki.py --minutes 60 --limit 50 --concurrent 6

This is the same code path the hourly cron uses — handy for debugging
extraction quality interactively without waiting for the scheduler.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.db.mariadb import ensure_knowledge_wiki_table  # noqa: E402
from app.knowledge.wiki_extractor import extract_batch  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Extract wiki facts from recent conversations.")
    parser.add_argument("--minutes", type=int, default=60, help="Time window in minutes (default 60)")
    parser.add_argument("--limit", type=int, default=100, help="Max Q/A pairs to process (default 100)")
    parser.add_argument("--concurrent", type=int, default=4, help="Parallel Flash calls (default 4)")
    args = parser.parse_args()

    ensure_knowledge_wiki_table()

    result = await extract_batch(
        since_minutes=args.minutes,
        limit=args.limit,
        max_concurrent=args.concurrent,
    )
    print(
        f"pairs_seen={result['pairs_seen']} "
        f"skipped={result['pairs_skipped']} "
        f"facts_written={result['facts_written']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
