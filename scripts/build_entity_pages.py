"""CLI — compile wiki_entity_pages from current knowledge_wiki state.

Usage:
    python scripts/build_entity_pages.py                     # only stale
    python scripts/build_entity_pages.py --all               # full rebuild
    python scripts/build_entity_pages.py --entity "센텔라 앰플"  # single
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.db.mariadb import ensure_wiki_entity_pages_table  # noqa: E402
from app.knowledge.entity_pages import compile_entity_page, ensure_entity_pages  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile entity pages")
    parser.add_argument("--entity", type=str, default=None)
    parser.add_argument("--all", action="store_true", help="Rebuild even if fresh")
    parser.add_argument("--batch", type=int, default=500)
    args = parser.parse_args()

    ensure_wiki_entity_pages_table()

    if args.entity:
        result = compile_entity_page(args.entity)
        print(result)
        return 0

    total_compiled = 0
    total_pruned = 0
    iteration = 0
    while True:
        iteration += 1
        result = ensure_entity_pages(limit=args.batch, only_stale=not args.all)
        total_compiled += result["compiled"]
        total_pruned += result["pruned"]
        print(
            f"iter {iteration}: compiled={result['compiled']} "
            f"pruned={result['pruned']} seen={result['seen']}"
        )
        if result["seen"] < args.batch or (not result["compiled"] and not result["pruned"]):
            break
        if iteration >= 50:
            print("hit safety cap")
            break

    print(f"\ndone: compiled={total_compiled} pruned={total_pruned}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
