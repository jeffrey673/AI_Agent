"""Entity normalization — map messy entity strings to canonical names.

Three layers, cheapest first:

1. **Trivial normalization**: lowercase / whitespace collapse / drop obvious
   wrapper words like "팀", "라인", "제품군".
2. **Alias table lookup** (``wiki_entity_aliases``): manual or LLM-seeded
   mappings (e.g., "마다가스카 센텔라 앰플" ↔ "Madagascar Centella Ampoule").
3. **Cluster merge pass** (script-driven): Gemini Flash clusters near-duplicate
   entities and writes back to the alias table. Runs offline, not on each call.

The search layer should call :func:`canonicalize` before matching so a single
canonical form absorbs user/language variants.
"""

from __future__ import annotations

import re
from typing import Iterable

import structlog

from app.db.mariadb import execute, fetch_all, fetch_one

logger = structlog.get_logger(__name__)


# Wrapper words — strip from the tail when calculating the normalized form.
_TRAILING_NOISE = [
    "팀", "라인", "제품군", "제품", "브랜드", "그룹", "상품",
    "(주)", "주식회사", "inc", "inc.", "corp", "corp.", "ltd", "ltd.",
]


_MULTISPACE = re.compile(r"\s+")


def _strip_trailing(text: str) -> str:
    lower = text.strip()
    for w in _TRAILING_NOISE:
        if lower.lower().endswith(" " + w) or lower.lower().endswith(w):
            lower = lower[: -len(w)].rstrip()
    return lower


def normalize_raw(entity: str) -> str:
    """Trivial normalization — no DB. Safe to call anywhere."""
    if not entity:
        return ""
    e = entity.strip()
    e = _MULTISPACE.sub(" ", e)
    e = _strip_trailing(e)
    return e.strip()


def canonicalize(entity: str) -> str:
    """Trivial normalize → alias table lookup → canonical form.

    Falls back to the normalized input when no alias is registered.
    """
    norm = normalize_raw(entity)
    if not norm:
        return entity
    try:
        row = fetch_one(
            "SELECT canonical FROM wiki_entity_aliases WHERE alias = %s LIMIT 1",
            (norm.lower(),),
        )
        if row and row.get("canonical"):
            return row["canonical"]
    except Exception as e:
        logger.warning("canonicalize_lookup_failed", error=str(e)[:200])
    return norm


def register_alias(alias: str, canonical: str, source: str = "manual") -> None:
    """Insert (or overwrite) a single alias → canonical mapping."""
    if not alias or not canonical:
        return
    try:
        execute(
            "INSERT INTO wiki_entity_aliases (alias, canonical, source) "
            "VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE canonical = VALUES(canonical), source = VALUES(source)",
            (alias.lower().strip(), canonical.strip(), source),
        )
    except Exception as e:
        logger.warning("register_alias_failed", error=str(e)[:200])


def register_aliases(pairs: Iterable[tuple[str, str]], source: str = "manual") -> int:
    count = 0
    for alias, canonical in pairs:
        register_alias(alias, canonical, source)
        count += 1
    return count


# ------------------------------------------------------------------
# LLM-driven cluster merge — run as an offline script
# ------------------------------------------------------------------

_CLUSTER_PROMPT = """아래는 SKIN1004 지식 위키에 저장된 엔티티 이름 후보입니다.
서로 다른 표기의 동일한 대상을 하나의 canonical 이름으로 묶어주세요.

## 입력 엔티티 목록
{entities}

## 규칙
1. 같은 회사/제품/팀의 다른 표기는 묶는다 (한영 혼용, 약어 등).
2. canonical은 그룹 내에서 **가장 명확하고 공식적인 표기**로 선택.
3. 명백히 같다고 확신할 수 없는 것은 **묶지 마세요**.
4. 각 그룹에 최소 2개 이상 포함된 경우만 출력.

## 출력 형식
JSON 배열만 출력. 다른 텍스트 금지.

[
  {{"canonical": "마다가스카 센텔라 토너 앰플", "aliases": ["Madagascar Centella Toner Ampoule", "마다 센텔라 앰플"]}},
  {{"canonical": "JBT", "aliases": ["JBT 팀", "Japan BT"]}}
]
"""


def cluster_merge_pass(max_entities: int = 200) -> int:
    """Pull the most-mentioned entities and let Flash cluster near-duplicates.

    Returns the number of new alias rows written. Designed to be invoked from
    a dedicated script so we don't add LLM calls to the hot path.
    """
    import json as _json

    rows = fetch_all(
        """
        SELECT entity, COUNT(*) AS cnt
        FROM knowledge_wiki
        WHERE status <> 'archived'
        GROUP BY entity
        ORDER BY cnt DESC
        LIMIT %s
        """,
        (max_entities,),
    )
    if not rows:
        return 0

    entity_list = "\n".join(f"- {r['entity']}" for r in rows if r.get("entity"))
    prompt = _CLUSTER_PROMPT.format(entities=entity_list)

    from app.core.llm import get_flash_client
    client = get_flash_client()
    try:
        raw = client.generate(prompt, temperature=0.0, max_output_tokens=8000)
    except Exception as e:
        logger.warning("cluster_merge_llm_failed", error=str(e)[:200])
        return 0

    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    raw = raw.strip()
    try:
        clusters = _json.loads(raw)
    except _json.JSONDecodeError:
        # Salvage: trim to last complete `}` and close the array.
        last = raw.rfind("},")
        if last == -1:
            last = raw.rfind("}")
        if last != -1:
            candidate = raw[: last + 1] + "]"
            try:
                clusters = _json.loads(candidate)
            except _json.JSONDecodeError:
                logger.warning("cluster_merge_json_failed", preview=raw[:300])
                return 0
        else:
            logger.warning("cluster_merge_json_failed", preview=raw[:300])
            return 0

    if not isinstance(clusters, list):
        return 0

    written = 0
    for group in clusters:
        if not isinstance(group, dict):
            continue
        canonical = (group.get("canonical") or "").strip()
        aliases = group.get("aliases") or []
        if not canonical or not aliases:
            continue
        register_alias(canonical, canonical, source="llm")
        for a in aliases:
            if isinstance(a, str) and a.strip() and a.strip() != canonical:
                register_alias(a, canonical, source="llm")
                written += 1
    logger.info("cluster_merge_done", groups=len(clusters), aliases_written=written)
    return written
