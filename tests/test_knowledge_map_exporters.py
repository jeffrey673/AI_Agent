"""Unit tests for app.knowledge_map.exporters."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from app.knowledge_map.graph import KnowledgeGraph, Node, Edge
from app.knowledge_map.exporters import write_graph_json, write_wiki_index, sort_key_for_diff


def _build_sample_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add_node(Node(id="app.agents.bq", type="class", file="app/agents/bq.py", summary="BQ agent", cluster="cluster_01"))
    g.add_node(Node(id="app.main", type="module", file="app/main.py", summary="Main app", cluster="cluster_02"))
    g.add_edge(Edge(src="app.main", dst="app.agents.bq", type="calls", confidence=1.0))
    return g


def test_write_graph_json_creates_file(tmp_path: Path) -> None:
    g = _build_sample_graph()
    out = tmp_path / "graph.json"
    write_graph_json(g, out, commit="abc123", file_count=2)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == "1.0"
    assert data["stats"]["files"] == 2
    assert data["stats"]["nodes"] == 2
    assert data["stats"]["edges"] == 1
    assert data["source_commit"] == "abc123"


def test_graph_json_nodes_are_sorted_for_stable_diffs(tmp_path: Path) -> None:
    g = _build_sample_graph()
    out = tmp_path / "graph.json"
    write_graph_json(g, out, commit="abc", file_count=2)
    data = json.loads(out.read_text(encoding="utf-8"))
    ids = [n["id"] for n in data["nodes"]]
    assert ids == sorted(ids)


def test_write_wiki_index_creates_toc(tmp_path: Path) -> None:
    g = _build_sample_graph()
    out = tmp_path / "index.md"
    write_wiki_index(g, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# Knowledge Map Wiki Index" in content
    assert "cluster_01" in content
    assert "cluster_02" in content


def test_sort_key_for_diff_is_stable() -> None:
    assert sort_key_for_diff({"id": "z"}) == "z"
    assert sort_key_for_diff({"src": "a", "dst": "b", "type": "calls"}) == "a->b:calls"
    assert sort_key_for_diff({"from": "x", "to": "y", "type": "imports"}) == "x->y:imports"
