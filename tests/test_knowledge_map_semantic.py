"""Unit tests for app.knowledge_map.semantic (Flash mocked)."""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.knowledge_map.semantic import SemanticFacts, extract_semantic_facts


@pytest.mark.asyncio
async def test_extract_semantic_facts_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "agent.py"
    f.write_text("class Foo:\n    pass\n", encoding="utf-8")

    fake_response = json.dumps({
        "summary": "A foo agent.",
        "concepts": ["foo_concept"],
        "relations": [{"target": "app.bar", "type": "calls", "confidence": 0.8}],
        "tags": ["agent"],
    })

    with patch("app.knowledge_map.semantic._flash_json_call", new=AsyncMock(return_value=fake_response)):
        result = await extract_semantic_facts(
            file_path=f,
            file_type="python",
            structural_facts={"classes": ["Foo"]},
        )

    assert isinstance(result, SemanticFacts)
    assert result.summary == "A foo agent."
    assert "foo_concept" in result.concepts
    assert result.relations[0]["type"] == "calls"


@pytest.mark.asyncio
async def test_extract_semantic_facts_malformed_json_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "agent.py"
    f.write_text("x = 1\n", encoding="utf-8")

    with patch("app.knowledge_map.semantic._flash_json_call", new=AsyncMock(return_value="not json at all")):
        result = await extract_semantic_facts(
            file_path=f,
            file_type="python",
            structural_facts={},
        )

    assert result.summary == ""
    assert result.parse_error is not None
