"""Output writers — graph.json, wiki/*.md, GRAPH_REPORT.md, wiki/index.md, wiki/log.md."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.knowledge_map.graph import KnowledgeGraph, Node, Edge

_VERSION = "1.0"


def sort_key_for_diff(obj: dict[str, Any]) -> str:
    """Stable sort key for nodes/edges so git diffs stay readable."""
    if "id" in obj:
        return str(obj["id"])
    return f"{obj.get('src', '')}->{obj.get('dst', '')}:{obj.get('type', '')}"


def _node_to_dict(n: Node) -> dict[str, Any]:
    d = asdict(n)
    return {k: v for k, v in d.items() if v not in (None, [], "")}


def _edge_to_dict(e: Edge) -> dict[str, Any]:
    return {"from": e.src, "to": e.dst, "type": e.type, "confidence": e.confidence}


def write_graph_json(
    graph: KnowledgeGraph,
    out_path: Path,
    commit: str,
    file_count: int,
    extra_stats: dict[str, Any] | None = None,
) -> None:
    nodes = sorted((_node_to_dict(n) for n in graph.nodes()), key=sort_key_for_diff)
    edges = sorted((_edge_to_dict(e) for e in graph.edges()), key=sort_key_for_diff)
    payload: dict[str, Any] = {
        "version": _VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_commit": commit,
        "stats": {
            "files": file_count,
            "nodes": len(nodes),
            "edges": len(edges),
            "clusters": len({n.get("cluster") for n in nodes if n.get("cluster")}),
            **(extra_stats or {}),
        },
        "nodes": nodes,
        "edges": edges,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_wiki_index(graph: KnowledgeGraph, out_path: Path) -> None:
    counts = graph.cluster_counts()
    lines = [
        "# Knowledge Map Wiki Index",
        "",
        f"_Generated {datetime.now().astimezone().isoformat()}_",
        "",
        "## Clusters",
        "",
    ]
    for cluster, count in sorted(counts.items()):
        lines.append(f"- **{cluster}** ({count} nodes) — `wiki/{cluster}.md`")
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def append_wiki_log(log_path: Path, entry: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().isoformat()
    line = f"- {stamp} · {entry}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def write_cluster_wiki_page(cluster_name: str, body: str, out_path: Path) -> None:
    """Body is the Flash-synthesized Markdown for a single cluster."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")


def write_graph_report(body: str, out_path: Path) -> None:
    """Body is the Flash-synthesized GRAPH_REPORT.md content."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
