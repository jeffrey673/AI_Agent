"""NetworkX graph wrapper + Louvain community detection for Knowledge Map."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx


@dataclass
class Node:
    id: str
    type: str
    file: Optional[str] = None
    lines: Optional[list[int]] = None
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    cluster: Optional[str] = None
    confidence: float = 1.0
    wiki_page: Optional[str] = None
    mentioned_in: list[str] = field(default_factory=list)


@dataclass
class Edge:
    src: str
    dst: str
    type: str
    confidence: float


class KnowledgeGraph:
    """Thin wrapper over networkx.MultiDiGraph with Louvain clustering."""

    def __init__(self) -> None:
        self._g = nx.MultiDiGraph()
        self._node_data: dict[str, Node] = {}
        self._edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        self._node_data[node.id] = node
        self._g.add_node(node.id)

    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)
        self._g.add_edge(edge.src, edge.dst, key=f"{edge.type}:{len(self._edges)}", type=edge.type, confidence=edge.confidence)

    def get_node(self, node_id: str) -> Node:
        return self._node_data[node_id]

    def nodes(self) -> list[Node]:
        return list(self._node_data.values())

    def edges(self) -> list[Edge]:
        return list(self._edges)

    def compute_clusters(self) -> None:
        """Run Louvain (community detection) on undirected projection."""
        import community as community_louvain

        if not self._node_data:
            return

        simple = nx.Graph()
        simple.add_nodes_from(self._g.nodes())
        weight: dict[tuple[str, str], float] = {}
        for u, v, data in self._g.edges(data=True):
            if u == v:
                continue
            key = tuple(sorted((u, v)))
            weight[key] = weight.get(key, 0.0) + float(data.get("confidence", 1.0))
        for (u, v), w in weight.items():
            simple.add_edge(u, v, weight=w)

        partition = community_louvain.best_partition(simple, random_state=42)
        for node_id, cid in partition.items():
            if node_id in self._node_data:
                self._node_data[node_id].cluster = f"cluster_{cid:02d}"

    def god_nodes(self, top_n: int = 8) -> list[Node]:
        """Return nodes sorted by total edge count (in + out), descending."""
        degrees = dict(self._g.degree())
        ranked = sorted(self._node_data.values(), key=lambda n: degrees.get(n.id, 0), reverse=True)
        return ranked[:top_n]

    def cluster_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for n in self._node_data.values():
            if n.cluster:
                counts[n.cluster] = counts.get(n.cluster, 0) + 1
        return counts
