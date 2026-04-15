"""Community detection for the wiki knowledge graph.

Builds a NetworkX graph from ``wiki_graph_edges`` and runs Louvain community
detection (the stable algorithm NetworkX ships with — no extra deps). Each
entity lands in exactly one community; the community row captures size and
top entities. ``wiki_graph_edges.community_id`` is updated in place so the
frontend can colour nodes by community.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import structlog

from app.db.mariadb import execute, fetch_all

logger = structlog.get_logger(__name__)


def _build_nx_graph():
    import networkx as nx
    rows = fetch_all(
        "SELECT src_entity, dst_entity, relation, weight FROM wiki_graph_edges"
    )
    g = nx.Graph()
    for r in rows:
        src = (r["src_entity"] or "").strip()
        dst = (r["dst_entity"] or "").strip()
        if not src or not dst or src == dst:
            continue
        w = float(r["weight"] or 1.0)
        if g.has_edge(src, dst):
            g[src][dst]["weight"] += w
        else:
            g.add_edge(src, dst, weight=w, relation=r["relation"])
    return g


def detect_communities(resolution: float = 1.0) -> dict[str, int]:
    """Run Louvain on the wiki graph and write community assignments.

    Returns a dict of {entity: community_id}.
    """
    import networkx as nx
    from networkx.algorithms.community import louvain_communities

    g = _build_nx_graph()
    if g.number_of_nodes() == 0:
        logger.info("communities_graph_empty")
        return {}

    partitions = louvain_communities(g, weight="weight", resolution=resolution, seed=42)
    partitions_sorted = sorted(partitions, key=len, reverse=True)

    entity_to_community: dict[str, int] = {}
    # Reset community rows
    execute("DELETE FROM wiki_communities")
    execute("UPDATE wiki_graph_edges SET community_id = NULL")

    for idx, community in enumerate(partitions_sorted):
        members = list(community)
        if len(members) < 2:
            continue
        # Pick a label — highest-degree entity in the community
        top_members = sorted(
            members, key=lambda n: g.degree(n, weight="weight"), reverse=True
        )
        top_entities = top_members[:5]
        label = top_entities[0] if top_entities else f"community_{idx}"

        # Measure density for ranking
        subgraph = g.subgraph(members)
        density = nx.density(subgraph)

        execute(
            """
            INSERT INTO wiki_communities (id, label, size, density, top_entities)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (idx + 1, label[:128], len(members), float(density), json.dumps(top_entities, ensure_ascii=False)),
        )
        for m in members:
            entity_to_community[m] = idx + 1

    # Write community_id onto every edge where both endpoints share a community.
    if entity_to_community:
        for src, cid in entity_to_community.items():
            execute(
                "UPDATE wiki_graph_edges SET community_id = %s "
                "WHERE (src_entity = %s AND dst_entity IN "
                "  (SELECT dst_entity FROM (SELECT DISTINCT dst_entity FROM wiki_graph_edges WHERE src_entity = %s) x)) "
                "AND community_id IS NULL",
                (cid, src, src),
            )
    logger.info(
        "communities_detected",
        communities=len(partitions_sorted),
        non_trivial=sum(1 for c in partitions_sorted if len(c) >= 2),
        assigned_entities=len(entity_to_community),
    )

    # Propagate community_id into wiki_entity_pages too
    for entity, cid in entity_to_community.items():
        execute(
            "UPDATE wiki_entity_pages SET community_id = %s WHERE canonical_entity = %s",
            (cid, entity),
        )
        execute(
            "UPDATE wiki_entity_pages SET community_label = "
            "(SELECT label FROM wiki_communities WHERE id = %s) "
            "WHERE canonical_entity = %s",
            (cid, entity),
        )

    return entity_to_community


def get_communities() -> list[dict]:
    return fetch_all(
        "SELECT id, label, size, density, top_entities, detected_at "
        "FROM wiki_communities ORDER BY size DESC"
    )
