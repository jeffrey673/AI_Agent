"""Knowledge graph — entity relationships mined from wiki facts.

Reads accumulated wiki rows, asks Gemini Flash to extract (src, relation, dst)
triples per domain, and upserts them into ``wiki_graph_edges``. Separate from
live request handling — this runs from a script or a low-frequency cron.

Relation vocabulary is intentionally small so the graph stays navigable:

- ``owns``         team/company owns a product, channel, or customer
- ``belongs_to``   fact/entity belongs to a larger scope (product to line, etc.)
- ``compares_to``  two entities share a comparison metric (rankings)
- ``sells_in``     product is sold through a market/channel/region
- ``linked``       generic co-occurrence when nothing stronger fits
"""

from __future__ import annotations

import json as _json
import re
from typing import Any

import structlog

from app.db.mariadb import execute, fetch_all

logger = structlog.get_logger(__name__)


_ALLOWED_RELATIONS = {"owns", "belongs_to", "compares_to", "sells_in", "linked"}


_EXTRACT_PROMPT = """다음은 SKIN1004 지식 위키에 저장된 팩트 요약들입니다.
각 팩트에서 **두 엔티티 간의 관계**를 추출해 JSON 배열로 출력하세요.

## 팩트
{facts}

## 관계 어휘 (반드시 이 중 하나)
- owns: 팀/회사가 제품/채널/고객사를 보유함
- belongs_to: 엔티티가 더 큰 범위에 속함 (제품 → 라인)
- compares_to: 두 엔티티가 같은 지표로 비교됨 (순위 비교)
- sells_in: 제품이 특정 지역/채널에서 판매됨
- linked: 위 중 어느 것도 명확하지 않지만 같은 팩트에 함께 등장

## 규칙
1. 한 팩트에서 최소 0개, 최대 3개 관계까지만.
2. src/dst는 팩트 요약에 **실제 등장한 엔티티**여야 함.
3. 자기 자신과의 관계는 만들지 말 것.

## 출력 형식 (JSON 배열만)
[
  {{"src": "...", "dst": "...", "relation": "owns", "wiki_id": 123}},
  ...
]
"""


def _clean_json(raw: str) -> str:
    """Peel markdown code fences, tolerant of truncated output missing the
    closing ```. Also handles plain ```json...``` and bare ```...```.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


def _extract_relations_sync(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not facts:
        return []
    bullet = "\n".join(
        f"- (id={f['id']}) {f['summary']}" for f in facts if f.get("summary")
    )
    prompt = _EXTRACT_PROMPT.format(facts=bullet)

    from app.core.llm import get_flash_client
    client = get_flash_client()
    try:
        raw = client.generate(prompt, temperature=0.0, max_output_tokens=8000)
    except Exception as e:
        logger.warning("graph_llm_failed", error=str(e)[:200])
        return []

    cleaned = _clean_json(raw)
    try:
        data = _json.loads(cleaned)
    except _json.JSONDecodeError:
        # Salvage truncated array — keep the complete elements.
        last = cleaned.rfind("},")
        if last == -1:
            last = cleaned.rfind("}")
        if last != -1:
            try:
                data = _json.loads(cleaned[: last + 1] + "]")
            except _json.JSONDecodeError:
                logger.warning("graph_json_failed", preview=cleaned[:300])
                return []
        else:
            logger.warning("graph_json_failed", preview=cleaned[:300])
            return []
    if not isinstance(data, list):
        return []

    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rel = (item.get("relation") or "").strip()
        if rel not in _ALLOWED_RELATIONS:
            continue
        src = (item.get("src") or "").strip()
        dst = (item.get("dst") or "").strip()
        if not src or not dst or src == dst:
            continue
        out.append({
            "src": src[:255],
            "dst": dst[:255],
            "relation": rel,
            "wiki_id": item.get("wiki_id"),
        })
    return out


def _upsert_edge_sync(edge: dict[str, Any]) -> None:
    try:
        execute(
            """
            INSERT INTO wiki_graph_edges (src_entity, dst_entity, relation, weight, source_wiki_ids)
            VALUES (%s, %s, %s, 1.0, JSON_ARRAY(%s))
            ON DUPLICATE KEY UPDATE
                weight = weight + 1.0,
                source_wiki_ids = JSON_ARRAY_APPEND(
                    COALESCE(source_wiki_ids, JSON_ARRAY()), '$', %s
                )
            """,
            (edge["src"], edge["dst"], edge["relation"], edge["wiki_id"], edge["wiki_id"]),
        )
    except Exception as e:
        logger.warning("upsert_edge_failed", error=str(e)[:200])


def build_graph_from_wiki(limit_facts: int = 500, chunk: int = 30) -> dict[str, int]:
    """Walk recent wiki facts and upsert edges. Returns counts."""
    facts = fetch_all(
        """
        SELECT id, entity, summary
        FROM knowledge_wiki
        WHERE status <> 'archived' AND summary IS NOT NULL
        ORDER BY id DESC
        LIMIT %s
        """,
        (limit_facts,),
    )
    stats = {"facts_seen": len(facts), "chunks": 0, "edges_written": 0}
    if not facts:
        return stats

    for i in range(0, len(facts), chunk):
        batch = facts[i : i + chunk]
        stats["chunks"] += 1
        edges = _extract_relations_sync(batch)
        for e in edges:
            _upsert_edge_sync(e)
            stats["edges_written"] += 1
    logger.info("graph_build_done", **stats)
    return stats
