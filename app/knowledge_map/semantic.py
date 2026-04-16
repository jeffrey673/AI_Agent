"""Gemini Flash semantic pass — pulls concepts/relations/summary per file."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.knowledge_map.config import (
    FLASH_BACKOFF_BASE,
    FLASH_MAX_RETRIES,
    FLASH_PARALLEL,
    PROJECT_ROOT,
)


_PROMPT_TEMPLATE_PATH = PROJECT_ROOT / "prompts" / "knowledge_map" / "extract_concepts.txt"
_MAX_CONTENT_CHARS = 8000


@dataclass
class SemanticFacts:
    summary: str
    concepts: list[str] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    parse_error: Optional[str] = None


def _load_prompt_template() -> str:
    return _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_prompt(file_path: Path, file_type: str, structural_facts: dict[str, Any], content: str) -> str:
    template = _load_prompt_template()
    truncated = content[:_MAX_CONTENT_CHARS]
    return (
        template
        .replace("{file_path}", str(file_path))
        .replace("{file_type}", file_type)
        .replace("{structural_facts}", json.dumps(structural_facts, ensure_ascii=False, indent=2))
        .replace("{content}", truncated)
    )


async def _flash_json_call(prompt: str) -> str:
    """Call Gemini Flash and return raw text. Isolated for test mocking."""
    from app.core.llm import get_flash_client
    client = get_flash_client()
    return await asyncio.to_thread(client.generate, prompt)


def _parse_response(raw: str) -> SemanticFacts:
    """Tolerant JSON parse — strips code fences, returns error node on failure."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        return SemanticFacts(summary="", parse_error=f"json: {e}")
    return SemanticFacts(
        summary=str(payload.get("summary", "")),
        concepts=list(payload.get("concepts", [])),
        relations=list(payload.get("relations", [])),
        tags=list(payload.get("tags", [])),
    )


async def extract_semantic_facts(
    file_path: Path,
    file_type: str,
    structural_facts: dict[str, Any],
) -> SemanticFacts:
    """Run the Flash semantic pass for a single file with retries."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return SemanticFacts(summary="", parse_error=f"read: {e}")

    prompt = _build_prompt(file_path, file_type, structural_facts, content)

    last_err: Optional[str] = None
    for attempt in range(FLASH_MAX_RETRIES):
        try:
            raw = await _flash_json_call(prompt)
            return _parse_response(raw)
        except Exception as e:
            last_err = f"attempt_{attempt}: {e}"
            await asyncio.sleep(FLASH_BACKOFF_BASE ** attempt)
    return SemanticFacts(summary="", parse_error=last_err)


async def extract_semantic_facts_batch(
    items: list[tuple[Path, str, dict[str, Any]]],
) -> list[SemanticFacts]:
    """Parallel batch with FLASH_PARALLEL fanout via asyncio.Semaphore."""
    sem = asyncio.Semaphore(FLASH_PARALLEL)

    async def _bounded(path: Path, ftype: str, facts: dict[str, Any]) -> SemanticFacts:
        async with sem:
            return await extract_semantic_facts(path, ftype, facts)

    return await asyncio.gather(*(_bounded(p, t, f) for p, t, f in items))
