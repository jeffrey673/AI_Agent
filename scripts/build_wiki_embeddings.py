"""CLI — embed all wiki rows that don't yet have an embedding.

Batches of 100, resumable, idempotent. Skips archived rows. Safe to run
alongside the hourly extractor cron.

Usage:
    python scripts/build_wiki_embeddings.py               # loop until drained
    python scripts/build_wiki_embeddings.py --max-batches 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.knowledge.wiki_embed import ensure_wiki_embeddings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate knowledge_wiki.embedding")
    parser.add_argument("--batch", type=int, default=100, help="Rows per batch")
    parser.add_argument("--max-batches", type=int, default=None, help="Safety cap")
    args = parser.parse_args()

    total = 0
    iteration = 0
    start = time.time()

    while True:
        iteration += 1
        if args.max_batches and iteration > args.max_batches:
            print(f"hit max-batches cap ({args.max_batches}), stopping")
            break
        result = ensure_wiki_embeddings(limit=args.batch)
        total += result["indexed"]
        elapsed = time.time() - start
        print(
            f"batch {iteration}: indexed={result['indexed']} "
            f"remaining={result['remaining']} "
            f"total={total} elapsed={elapsed:.1f}s"
        )
        if result["indexed"] == 0:
            print("nothing left to embed — done")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
