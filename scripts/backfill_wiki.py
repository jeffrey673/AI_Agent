"""CLI — backfill knowledge_wiki from ALL historical conversations.

Walks the entire `messages` table, pairs every assistant response with its
preceding user question, and extracts facts via Gemini Flash. Skips pairs
that already have wiki rows, so re-running is safe.

The extractor filters out routes that shouldn't be indexed (direct/cs), so
we don't leak chit-chat or customer-service content into the wiki.

Usage:
    python scripts/backfill_wiki.py                       # all history, batches of 50
    python scripts/backfill_wiki.py --batch 100           # bigger batches
    python scripts/backfill_wiki.py --concurrent 6        # parallelism
    python scripts/backfill_wiki.py --dry-run             # count only, no LLM calls

Run this once. After it finishes, the hourly cron handles incremental updates.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.db.mariadb import ensure_knowledge_wiki_table, fetch_all  # noqa: E402
from app.knowledge.wiki_extractor import extract_batch  # noqa: E402


def _count_pending() -> int:
    row = fetch_all(
        """
        SELECT COUNT(*) AS cnt FROM messages m
        LEFT JOIN knowledge_wiki k ON k.source_message_id = m.id
        WHERE m.role = 'assistant' AND k.id IS NULL
        """
    )
    return int(row[0]["cnt"]) if row else 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill knowledge_wiki from all past conversations.")
    parser.add_argument("--batch", type=int, default=50, help="Pairs per batch (default 50)")
    parser.add_argument("--concurrent", type=int, default=4, help="Parallel Flash calls (default 4)")
    parser.add_argument("--dry-run", action="store_true", help="Count pending pairs and exit")
    parser.add_argument("--max-batches", type=int, default=None, help="Safety cap on batch iterations")
    args = parser.parse_args()

    ensure_knowledge_wiki_table()

    pending = _count_pending()
    print(f"pending assistant messages without wiki rows: {pending}")
    if args.dry_run or pending == 0:
        return 0

    total_seen = 0
    total_written = 0
    iteration = 0
    start = time.time()

    while True:
        iteration += 1
        if args.max_batches and iteration > args.max_batches:
            print(f"hit max-batches cap ({args.max_batches}), stopping")
            break

        result = await extract_batch(
            since_minutes=None,  # no time filter — walk all history
            limit=args.batch,
            max_concurrent=args.concurrent,
        )
        total_seen += result["pairs_seen"]
        total_written += result["facts_written"]
        elapsed = time.time() - start
        print(
            f"batch {iteration}: seen={result['pairs_seen']} "
            f"skipped={result['pairs_skipped']} "
            f"facts={result['facts_written']} "
            f"totals(seen={total_seen}, facts={total_written}) "
            f"elapsed={elapsed:.1f}s"
        )
        if result["pairs_seen"] == 0:
            print("no more pairs pending — done")
            break

    print(
        f"\nbackfill complete: {total_seen} pairs processed, "
        f"{total_written} facts written, {time.time() - start:.1f}s total"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
