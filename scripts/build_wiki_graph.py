"""CLI — build the knowledge graph from wiki facts.

Pulls recent wiki rows, asks Gemini Flash to extract entity relationships,
and upserts edges into wiki_graph_edges.

Usage:
    python scripts/build_wiki_graph.py              # 500 most recent facts
    python scripts/build_wiki_graph.py --limit 2000
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.db.mariadb import ensure_wiki_graph_edges_table  # noqa: E402
from app.knowledge.wiki_graph import build_graph_from_wiki  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wiki graph from recent facts")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--chunk", type=int, default=30)
    args = parser.parse_args()

    ensure_wiki_graph_edges_table()
    stats = build_graph_from_wiki(limit_facts=args.limit, chunk=args.chunk)
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
