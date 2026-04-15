"""Wiki search — find stored facts relevant to a user query.

Week 2 v1: SQL-only search over `knowledge_wiki`. No vector embedding, no LLM
rerank. Good enough for the first cut — we can layer embeddings on once we
have enough rows to see what's actually missing.

Two public entry points:

- ``search_facts(query, limit)``: best-effort relevance search used by the
  orchestrator to inject context before routing.
- ``extract_keywords(query)``: exposed for debugging and unit tests.

Ranking is a simple weighted score:
    score = 2 * entity_matches + 1 * summary_matches
          + 0.5 * confidence
          - 0.1 * log10(age_days + 1)

Pending / active rows both participate. Archived rows are excluded.
"""

from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime, timezone

import structlog

from app.db.mariadb import fetch_all

logger = structlog.get_logger(__name__)


# Words that add noise without improving matches.
_STOP_TOKENS: set[str] = {
    "뭐", "무엇", "어떻게", "어때", "얼마", "언제", "어디", "누구", "왜",
    "이", "그", "저", "것", "수", "때", "년", "월", "일",
    "알려", "알려줘", "보여", "보여줘", "말해", "설명",
    "있어", "있나", "있는지", "없어", "없나", "입니다", "입니까",
    "the", "a", "an", "is", "are", "was", "were", "of", "for", "to",
}

_TOKEN_MIN_LEN = 2
_MAX_CANDIDATES = 60  # pull this many from DB before ranking in Python
_DEFAULT_LIMIT = 6


def extract_keywords(query: str) -> list[str]:
    """Pull meaningful tokens out of a query for LIKE matching.

    Handles Korean, alphanumerics and slash/dash-joined terms. Drops short
    tokens and Korean/English stopwords.
    """
    if not query:
        return []
    # Keep Korean syllables, Latin letters, digits, and a few joiners
    parts = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9\-_/.]*", query)
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        t = p.lower()
        if len(t) < _TOKEN_MIN_LEN:
            continue
        if t in _STOP_TOKENS:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(p)
    return out


def _build_candidate_query(tokens: list[str]) -> tuple[str, tuple]:
    """Build a UNION-free OR-search against entity and summary."""
    if not tokens:
        return "", ()
    clauses = []
    params: list[str] = []
    for t in tokens[:8]:  # cap token count so the query stays small
        like = f"%{t}%"
        clauses.append("(entity LIKE %s OR summary LIKE %s OR value LIKE %s)")
        params.extend([like, like, like])
    where = " OR ".join(clauses)
    sql = f"""
        SELECT id, domain, entity, period, metric, value, summary,
               confidence, extracted_at, source_route, status,
               thumbs_up, thumbs_down
        FROM knowledge_wiki
        WHERE status <> 'archived'
          AND ({where})
        LIMIT {int(_MAX_CANDIDATES)}
    """
    return sql, tuple(params)


def _score(row: dict, tokens: list[str]) -> float:
    entity = (row.get("entity") or "").lower()
    summary = (row.get("summary") or "").lower()
    value = str(row.get("value") or "").lower()

    entity_hits = sum(1 for t in tokens if t.lower() in entity)
    summary_hits = sum(1 for t in tokens if t.lower() in summary)
    value_hits = sum(1 for t in tokens if t.lower() in value)

    score = 2.0 * entity_hits + 1.0 * summary_hits + 0.5 * value_hits
    score += 0.5 * float(row.get("confidence") or 0)

    # Freshness: newer is slightly better
    extracted_at = row.get("extracted_at")
    if isinstance(extracted_at, datetime):
        if extracted_at.tzinfo is None:
            extracted_at = extracted_at.replace(tzinfo=timezone.utc)
        age_days = max(0, (datetime.now(timezone.utc) - extracted_at).days)
        score -= 0.1 * math.log10(age_days + 1)

    # Feedback signal
    score += 0.3 * int(row.get("thumbs_up") or 0)
    score -= 0.5 * int(row.get("thumbs_down") or 0)
    return score


def _search_sync(query: str, limit: int) -> list[dict]:
    tokens = extract_keywords(query)
    if not tokens:
        return []
    sql, params = _build_candidate_query(tokens)
    try:
        candidates = fetch_all(sql, params)
    except Exception as e:
        logger.warning("wiki_search_query_failed", error=str(e)[:200])
        return []
    if not candidates:
        return []

    scored = [(row, _score(row, tokens)) for row in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [r for r, s in scored[:limit] if s > 0]
    return top


# Queries that are never worth a wiki lookup — chit-chat, greetings, tiny
# fragments. Matched by the full stripped query or by startswith.
_SKIP_EXACT: set[str] = {
    "안녕", "안녕하세요", "하이", "반가워", "반가워요",
    "고마워", "고맙습니다", "감사", "감사합니다",
    "ㅎㅎ", "ㅋㅋ", "ㅇㅇ", "응", "네", "예", "yes", "ok", "okay",
    "테스트", "test", "hi", "hello", "hey",
}
_SKIP_PREFIX = ("안녕",)
_MIN_QUERY_LEN_FOR_WIKI = 4  # shorter than this = no wiki enrichment


def should_skip_wiki(query: str) -> bool:
    q = (query or "").strip().lower()
    if len(q) < _MIN_QUERY_LEN_FOR_WIKI:
        return True
    if q in _SKIP_EXACT:
        return True
    for prefix in _SKIP_PREFIX:
        if q.startswith(prefix) and len(q) <= len(prefix) + 4:
            return True
    return False


async def search_facts(query: str, limit: int = _DEFAULT_LIMIT) -> list[dict]:
    """Return the most relevant wiki facts for ``query`` (async wrapper).

    Hybrid keyword + embedding score. Keyword SQL and the Gemini query
    embedding run in parallel so total wait ≈ max(sql, embed) instead of
    sum. Embedding is best-effort and its timeout is enforced by
    ``embed_query_async`` itself.
    """
    if should_skip_wiki(query):
        return []

    from app.knowledge.wiki_embed import embed_query_async, load_wiki_embeddings, cosine

    # Fire keyword SQL and Gemini embedding at the same time.
    keyword_task = asyncio.to_thread(_search_sync, query, limit * 3)
    embed_task = embed_query_async(query)
    cache_task = asyncio.to_thread(load_wiki_embeddings)

    keyword_hits, query_vec, cache = await asyncio.gather(
        keyword_task, embed_task, cache_task, return_exceptions=False
    )

    if not keyword_hits:
        return []
    if not query_vec or not cache:
        return keyword_hits[:limit]

    tokens = extract_keywords(query)
    reranked = []
    for row in keyword_hits:
        emb = cache.get(int(row["id"]))
        semantic = cosine(query_vec, emb) if emb is not None else 0.0
        kw_score = _score(row, tokens)
        combined = (kw_score * 0.5) + (semantic * 10.0)
        reranked.append((row, combined))
    reranked.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in reranked[:limit]]


def format_facts_for_prompt(facts: list[dict]) -> str:
    """Render fact rows as a Markdown bullet list suitable for injection."""
    if not facts:
        return ""
    lines = []
    for f in facts:
        summary = (f.get("summary") or "").strip()
        period = f.get("period") or ""
        metric = f.get("metric") or ""
        source = f.get("source_route") or "wiki"
        tag_bits = [b for b in [period, metric] if b]
        tag = f" ({', '.join(tag_bits)})" if tag_bits else ""
        lines.append(f"- {summary}{tag}  _[source: {source}]_")
    return "\n".join(lines)


async def search_with_pages(query: str, limit: int = 4) -> str:
    """Richer context builder: prefer compiled entity pages, fall back to
    individual facts. Returns ready-to-inject markdown or ``""``.

    Short-circuits on trivial queries (greetings, one-word chit-chat) so
    the orchestrator doesn't pay wiki overhead on every tiny message.
    Entity-page search and fact search run in parallel.
    """
    if should_skip_wiki(query):
        return ""

    try:
        from app.knowledge.entity_pages import search_entity_pages
        page_task = asyncio.to_thread(search_entity_pages, query, limit)
    except Exception as e:
        logger.warning("entity_page_search_failed", error=str(e)[:200])
        page_task = asyncio.sleep(0, result=[])

    fact_task = search_facts(query, limit=limit)

    pages, fact_hits = await asyncio.gather(page_task, fact_task, return_exceptions=False)

    blocks: list[str] = []
    covered_entities: set[str] = set()
    for p in pages or []:
        markdown = (p.get("markdown") or "").strip()
        if not markdown:
            continue
        covered_entities.add(p.get("canonical_entity") or "")
        blocks.append(markdown)

    stray_facts = [
        f for f in (fact_hits or [])
        if (f.get("entity") or "") not in covered_entities
    ]
    if stray_facts:
        blocks.append("## 추가 관련 팩트\n" + format_facts_for_prompt(stray_facts))

    return "\n\n".join(blocks)
