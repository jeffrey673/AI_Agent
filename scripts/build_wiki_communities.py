"""CLI — run Louvain community detection on wiki_graph_edges."""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.db.mariadb import ensure_wiki_communities_table  # noqa: E402
from app.knowledge.wiki_communities import detect_communities, get_communities  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect graph communities")
    parser.add_argument("--resolution", type=float, default=1.0,
                        help="Louvain resolution — higher = smaller communities")
    args = parser.parse_args()

    ensure_wiki_communities_table()
    mapping = detect_communities(resolution=args.resolution)
    print(f"assigned {len(mapping)} entities to communities")

    print("\n=== top communities ===")
    for c in get_communities()[:15]:
        print(f"  #{c['id']} {c['label'][:40]:<40} size={c['size']:>4} density={c['density']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
