"""Insights layer — Graphify-style "GRAPH_REPORT" for the wiki graph.

Computes:
- God nodes: entities with the most connections (degree centrality).
- Orphan entities: entities with very few facts, suggesting unused or
  one-off mentions that may need cleanup.
- Surprising connections: high-weight edges whose endpoints live in
  different domains — often the most actionable cross-cutting insights.
- Stale facts: time-sensitive rows (route=bigquery with a recent period)
  that haven't been refreshed in a while.
- Contradictions: facts currently flagged as conflicting.
- Top communities: largest clusters detected by Louvain.

All numbers come from plain SQL — no LLM calls — so this runs fast and
cheap on every drawer open.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.db.mariadb import fetch_all

logger = structlog.get_logger(__name__)


def god_nodes(top: int = 10) -> list[dict]:
    """Top N entities by total incident edge weight."""
    return fetch_all(
        """
        SELECT e.entity, e.degree, e.weight_sum
        FROM (
            SELECT src_entity AS entity,
                   COUNT(*) AS degree,
                   SUM(weight) AS weight_sum
            FROM wiki_graph_edges GROUP BY src_entity
            UNION ALL
            SELECT dst_entity AS entity,
                   COUNT(*) AS degree,
                   SUM(weight) AS weight_sum
            FROM wiki_graph_edges GROUP BY dst_entity
        ) e
        GROUP BY e.entity
        ORDER BY SUM(e.weight_sum) DESC
        LIMIT %s
        """,
        (int(top),),
    )


def orphan_entities(max_facts: int = 1, limit: int = 30) -> list[dict]:
    """Entities that appear in only a handful of facts and no edges."""
    return fetch_all(
        """
        SELECT k.entity,
               k.domain,
               COUNT(*) AS fact_count,
               MAX(k.summary) AS sample_summary
        FROM knowledge_wiki k
        LEFT JOIN wiki_graph_edges e
          ON e.src_entity = k.entity OR e.dst_entity = k.entity
        WHERE k.status <> 'archived'
        GROUP BY k.entity, k.domain
        HAVING COUNT(*) <= %s AND COUNT(e.id) = 0
        ORDER BY fact_count ASC
        LIMIT %s
        """,
        (int(max_facts), int(limit)),
    )


def surprising_connections(top: int = 15) -> list[dict]:
    """Edges where src and dst live in different primary domains."""
    return fetch_all(
        """
        SELECT
            e.src_entity, e.dst_entity, e.relation, e.weight,
            (SELECT domain FROM knowledge_wiki WHERE entity = e.src_entity
             ORDER BY extracted_at DESC LIMIT 1) AS src_domain,
            (SELECT domain FROM knowledge_wiki WHERE entity = e.dst_entity
             ORDER BY extracted_at DESC LIMIT 1) AS dst_domain
        FROM wiki_graph_edges e
        HAVING src_domain IS NOT NULL
           AND dst_domain IS NOT NULL
           AND src_domain <> dst_domain
        ORDER BY e.weight DESC
        LIMIT %s
        """,
        (int(top),),
    )


def stale_facts(max_age_days: int = 14, limit: int = 20) -> list[dict]:
    """Time-sensitive BQ facts whose extraction is older than the threshold."""
    return fetch_all(
        """
        SELECT id, domain, entity, period, metric, value, summary,
               extracted_at, source_route
        FROM knowledge_wiki
        WHERE source_route = 'bigquery'
          AND status <> 'archived'
          AND review_status <> 'needs_review'
          AND period LIKE '2026-%%'
          AND extracted_at < NOW() - INTERVAL %s DAY
        ORDER BY extracted_at ASC
        LIMIT %s
        """,
        (int(max_age_days), int(limit)),
    )


def active_contradictions(limit: int = 50) -> list[dict]:
    """Currently flagged conflicting facts, paired with their sibling."""
    return fetch_all(
        """
        SELECT a.id, a.entity, a.period, a.metric, a.value AS value_a,
               a.summary AS summary_a, a.conflict_with_id,
               b.value AS value_b, b.summary AS summary_b
        FROM knowledge_wiki a
        LEFT JOIN knowledge_wiki b ON b.id = a.conflict_with_id
        WHERE a.conflict_with_id IS NOT NULL
          AND a.review_status = 'needs_review'
          AND a.status <> 'archived'
        ORDER BY a.validated_at DESC
        LIMIT %s
        """,
        (int(limit),),
    )


def top_communities(top: int = 10) -> list[dict]:
    return fetch_all(
        "SELECT id, label, size, density, top_entities "
        "FROM wiki_communities ORDER BY size DESC LIMIT %s",
        (int(top),),
    )


def suggested_queries(limit: int = 5) -> list[str]:
    """Synthesize a few exploratory questions from the god nodes.

    Deterministic — no LLM. Uses high-degree entities as seed targets.
    """
    gods = god_nodes(top=limit * 2)
    out: list[str] = []
    templates = [
        "{entity} 관련 지난 분기 추이는?",
        "{entity} 매출 YoY 비교",
        "{entity}에서 가장 변화가 큰 지표는?",
        "{entity} 관련 제품/채널 리스트",
        "{entity} 최근 마케팅 비용 대비 ROAS",
    ]
    for i, row in enumerate(gods[:limit]):
        entity = row.get("entity") or ""
        if not entity:
            continue
        out.append(templates[i % len(templates)].format(entity=entity))
    return out


def full_report() -> dict:
    """Everything the insights tab needs in one payload."""
    return {
        "god_nodes": god_nodes(top=10),
        "orphans": orphan_entities(max_facts=1, limit=30),
        "surprising": surprising_connections(top=15),
        "stale": stale_facts(max_age_days=14, limit=20),
        "contradictions": active_contradictions(limit=50),
        "communities": top_communities(top=10),
        "suggested_queries": suggested_queries(limit=6),
    }
