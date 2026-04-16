"""Unit tests for app.knowledge_map.graph."""
from __future__ import annotations

import pytest

from app.knowledge_map.graph import KnowledgeGraph, Node, Edge


def test_add_nodes_and_edges() -> None:
    g = KnowledgeGraph()
    g.add_node(Node(id="a", type="file", summary="Module a"))
    g.add_node(Node(id="b", type="file", summary="Module b"))
    g.add_edge(Edge(src="a", dst="b", type="imports", confidence=1.0))
    assert len(g.nodes()) == 2
    assert len(g.edges()) == 1


def test_louvain_clustering_assigns_clusters() -> None:
    g = KnowledgeGraph()
    for n in ["a1", "a2", "a3"]:
        g.add_node(Node(id=n, type="file"))
    for n in ["b1", "b2", "b3"]:
        g.add_node(Node(id=n, type="file"))
    g.add_edge(Edge(src="a1", dst="a2", type="calls", confidence=1.0))
    g.add_edge(Edge(src="a2", dst="a3", type="calls", confidence=1.0))
    g.add_edge(Edge(src="a1", dst="a3", type="calls", confidence=1.0))
    g.add_edge(Edge(src="b1", dst="b2", type="calls", confidence=1.0))
    g.add_edge(Edge(src="b2", dst="b3", type="calls", confidence=1.0))
    g.add_edge(Edge(src="b1", dst="b3", type="calls", confidence=1.0))
    g.add_edge(Edge(src="a1", dst="b1", type="references", confidence=0.5))

    g.compute_clusters()

    cluster_a = {g.get_node("a1").cluster, g.get_node("a2").cluster, g.get_node("a3").cluster}
    cluster_b = {g.get_node("b1").cluster, g.get_node("b2").cluster, g.get_node("b3").cluster}
    assert len(cluster_a) == 1
    assert len(cluster_b) == 1
    assert cluster_a != cluster_b


def test_god_nodes_ranked_by_edge_count() -> None:
    g = KnowledgeGraph()
    g.add_node(Node(id="hub", type="file"))
    g.add_node(Node(id="a", type="file"))
    g.add_node(Node(id="b", type="file"))
    g.add_node(Node(id="c", type="file"))
    g.add_edge(Edge(src="hub", dst="a", type="calls", confidence=1.0))
    g.add_edge(Edge(src="hub", dst="b", type="calls", confidence=1.0))
    g.add_edge(Edge(src="hub", dst="c", type="calls", confidence=1.0))

    gods = g.god_nodes(top_n=1)
    assert len(gods) == 1
    assert gods[0].id == "hub"
