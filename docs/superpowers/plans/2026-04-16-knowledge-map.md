# SKIN1004 Knowledge Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static code/docs knowledge map (Karpathy LLM wiki + Graphify concepts) that Claude Code reads first in every session to minimize grep/file exploration tokens. Rebuilds daily at 03:00.

**Architecture:** Single Python build pipeline (`app/knowledge_map/builder.py`) runs AST + Markdown parsing (confidence 1.0), then Gemini Flash semantic extraction (confidence 0.5-0.9) in parallel batches, merges into a NetworkX graph, runs Louvain community detection, and exports `knowledge_map/graph.json` + `knowledge_map/GRAPH_REPORT.md` + `knowledge_map/wiki/**/*.md`. SHA256+mtime cache ensures incremental rebuilds. A one-line `CLAUDE.md` trigger tells Claude to read `GRAPH_REPORT.md` first, then related nodes, never Grep directly.

**Tech Stack:** Python 3.11+, `ast` (stdlib), `hashlib` (stdlib), `networkx`, `python-louvain`, Gemini Flash (via existing `app.core.llm.get_flash_client`), pytest for tests, Windows Task Scheduler (PowerShell) for daily cron.

**Spec:** `docs/superpowers/specs/2026-04-16-knowledge-map-design.md`

**Naming collision note:** This plan uses `app/knowledge_map/` (not `app/knowledge/`) because `app/knowledge/` is an existing runtime package (conversation fact mining → MariaDB). Two systems stay independent.

**v1.0 scope (what's in, what's deferred):**
- **In v1.0**: `graph.json` (full), `GRAPH_REPORT.md` (structural — clusters + god nodes + navigation rules, no Flash-synthesized narrative), `wiki/index.md`, `wiki/log.md`, incremental cache, Task Scheduler, CLAUDE.md trigger.
- **Deferred to v1.1**: per-cluster narrative wiki pages via `synthesize_wiki.txt` prompt (`knowledge_map/wiki/<cluster>/*.md`), Flash-synthesized "What this project is" section of GRAPH_REPORT.md, `wiki_page` field population on nodes.
- **Why**: v1.0 already delivers the core win — Claude reads GRAPH_REPORT.md (one page) instead of grep-ing. Per-cluster narrative pages are polish, not foundation. Ship v1.0, measure, then decide if narrative pages are worth the Flash cost.

---

## File Structure

**Create**:
- `app/knowledge_map/__init__.py` — module marker
- `app/knowledge_map/cache.py` — SHA256+mtime cache (~50 lines)
- `app/knowledge_map/ast_parser.py` — Python AST extraction (~120 lines)
- `app/knowledge_map/md_parser.py` — Markdown structure extraction (~80 lines)
- `app/knowledge_map/semantic.py` — Gemini Flash semantic pass (~150 lines)
- `app/knowledge_map/graph.py` — NetworkX graph + Louvain clustering (~100 lines)
- `app/knowledge_map/exporters.py` — graph.json + wiki/**/*.md + GRAPH_REPORT.md writers (~200 lines)
- `app/knowledge_map/builder.py` — main orchestrator (~180 lines)
- `app/knowledge_map/config.py` — paths, exclude patterns, constants (~50 lines)
- `prompts/knowledge_map/extract_concepts.txt` — Flash prompt for per-file concepts/relations
- `prompts/knowledge_map/synthesize_wiki.txt` — Flash prompt for wiki page generation
- `prompts/knowledge_map/synthesize_report.txt` — Flash prompt for GRAPH_REPORT.md
- `scripts/build_knowledge_graph.py` — CLI entrypoint (~60 lines)
- `scripts/validate_graph.py` — post-build validator (~80 lines)
- `scripts/register_knowledge_task.ps1` — Task Scheduler registration
- `tests/test_knowledge_map_cache.py` — cache unit tests
- `tests/test_knowledge_map_ast.py` — AST parser unit tests
- `tests/test_knowledge_map_md.py` — Markdown parser unit tests
- `tests/test_knowledge_map_graph.py` — graph builder unit tests
- `tests/test_knowledge_map_exporters.py` — exporter unit tests
- `tests/fixtures/knowledge_map/sample_module.py` — AST test fixture
- `tests/fixtures/knowledge_map/sample_doc.md` — Markdown test fixture

**Modify**:
- `requirements.txt` — add `networkx>=3.0`, `python-louvain>=0.16`
- `.gitignore` — add `knowledge_map/.cache/`
- `CLAUDE.md` — add "Knowledge Map (먼저 읽기 — 필수)" section at top

**Output (generated, git-tracked)**:
- `knowledge_map/graph.json`
- `knowledge_map/GRAPH_REPORT.md`
- `knowledge_map/wiki/index.md`
- `knowledge_map/wiki/log.md`
- `knowledge_map/wiki/**/*.md` (per-cluster pages)
- `knowledge_map/.cache/file_hashes.json` (gitignored)

---

## Task 1: Dependencies, directory skeleton, gitignore

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `app/knowledge_map/__init__.py`
- Create: `prompts/knowledge_map/` (empty dir placeholder)
- Create: `knowledge_map/.cache/.gitkeep`

- [ ] **Step 1.1: Add deps to requirements.txt**

Append to `requirements.txt`:
```
networkx>=3.0
python-louvain>=0.16
```

- [ ] **Step 1.2: Install deps**

Run: `python -m pip install networkx>=3.0 python-louvain>=0.16`
Expected: both packages install successfully on Windows (pure Python, no C deps).

- [ ] **Step 1.3: Verify import**

Run: `python -c "import networkx, community; print(networkx.__version__, community.__version__)"`
Expected: prints two version strings, no ImportError.

- [ ] **Step 1.4: Create module skeleton**

Create `app/knowledge_map/__init__.py`:
```python
"""Knowledge Map — static code/docs knowledge graph for Claude Code sessions.

Separate from app.knowledge (runtime conversation fact mining). See
docs/superpowers/specs/2026-04-16-knowledge-map-design.md.
"""
```

- [ ] **Step 1.5: Create prompt & output dirs**

Run:
```bash
mkdir -p prompts/knowledge_map knowledge_map/.cache knowledge_map/wiki
```
Create empty `knowledge_map/.cache/.gitkeep` (so directory exists in git even though contents are ignored).

- [ ] **Step 1.6: Update .gitignore**

Append to `.gitignore`:
```
# Knowledge Map build cache (regenerable)
knowledge_map/.cache/
!knowledge_map/.cache/.gitkeep
```

- [ ] **Step 1.7: Commit**

```bash
git add requirements.txt .gitignore app/knowledge_map/__init__.py prompts/knowledge_map knowledge_map/.cache/.gitkeep
git commit -m "feat(knowledge_map): bootstrap module skeleton and deps"
```

---

## Task 2: Config module (paths & exclude patterns)

**Files:**
- Create: `app/knowledge_map/config.py`

- [ ] **Step 2.1: Write config module**

Create `app/knowledge_map/config.py`:
```python
"""Paths, exclude patterns, and build constants for Knowledge Map."""
from __future__ import annotations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Output
OUTPUT_ROOT = PROJECT_ROOT / "knowledge_map"
GRAPH_JSON = OUTPUT_ROOT / "graph.json"
REPORT_MD = OUTPUT_ROOT / "GRAPH_REPORT.md"
WIKI_DIR = OUTPUT_ROOT / "wiki"
WIKI_INDEX = WIKI_DIR / "index.md"
WIKI_LOG = WIKI_DIR / "log.md"
CACHE_DIR = OUTPUT_ROOT / ".cache"
CACHE_FILE = CACHE_DIR / "file_hashes.json"

# Source roots to scan
SOURCE_ROOTS = [
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "app",
]

# Paths to exclude (relative fragments; matched via 'in str(path)')
EXCLUDE_FRAGMENTS = [
    # backup/deprecated
    "backup_before_custom_frontend",
    "open-webui-backup",
    "_docker_recovery_temp",
    "craver_design_clone",
    # temp / logs
    "/logs/",
    "/temp_",
    "__pycache__",
    # frontend out of scope
    "/app/frontend/",
    "/app/static/",
    # tests and scripts not indexed (they're run, not read)
    "/tests/",
    "/scripts/",
    # qa noise
    "/docs/QA_",
]

# File extensions to index
INCLUDE_EXTENSIONS = {".py", ".md"}

# Flash semantic pass
FLASH_PARALLEL = 10  # asyncio.gather fanout
FLASH_MAX_RETRIES = 3
FLASH_BACKOFF_BASE = 2.0  # seconds

# Louvain resolution (higher = more communities, default 1.0)
LOUVAIN_RESOLUTION = 1.0
```

- [ ] **Step 2.2: Verify config loads**

Run:
```bash
python -c "from app.knowledge_map.config import PROJECT_ROOT, SOURCE_ROOTS; print(PROJECT_ROOT); print([str(p) for p in SOURCE_ROOTS])"
```
Expected: prints absolute project root and the two source root paths.

- [ ] **Step 2.3: Commit**

```bash
git add app/knowledge_map/config.py
git commit -m "feat(knowledge_map): config (paths, exclude patterns, constants)"
```

---

## Task 3: Cache module (TDD)

**Files:**
- Create: `tests/test_knowledge_map_cache.py`
- Create: `app/knowledge_map/cache.py`

- [ ] **Step 3.1: Write failing test**

Create `tests/test_knowledge_map_cache.py`:
```python
"""Unit tests for app.knowledge_map.cache."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from app.knowledge_map.cache import FileCache, file_fingerprint


def test_file_fingerprint_stable(tmp_path: Path) -> None:
    f = tmp_path / "a.py"
    f.write_text("print('hi')\n", encoding="utf-8")
    fp1 = file_fingerprint(f)
    fp2 = file_fingerprint(f)
    assert fp1 == fp2
    assert "sha256" in fp1
    assert "mtime" in fp1


def test_file_fingerprint_changes_on_edit(tmp_path: Path) -> None:
    f = tmp_path / "a.py"
    f.write_text("print('hi')\n", encoding="utf-8")
    fp1 = file_fingerprint(f)
    f.write_text("print('bye')\n", encoding="utf-8")
    fp2 = file_fingerprint(f)
    assert fp1["sha256"] != fp2["sha256"]


def test_cache_load_missing_returns_empty(tmp_path: Path) -> None:
    cache = FileCache(tmp_path / "cache.json")
    assert cache.load() == {}


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache = FileCache(cache_file)
    data = {"a.py": {"sha256": "abc", "mtime": 1.0}}
    cache.save(data)
    assert cache_file.exists()
    assert cache.load() == data


def test_is_changed_detects_new_file(tmp_path: Path) -> None:
    f = tmp_path / "new.py"
    f.write_text("x = 1\n", encoding="utf-8")
    cache = FileCache(tmp_path / "c.json")
    assert cache.is_changed(f, previous={}) is True


def test_is_changed_skips_unchanged(tmp_path: Path) -> None:
    f = tmp_path / "same.py"
    f.write_text("x = 1\n", encoding="utf-8")
    cache = FileCache(tmp_path / "c.json")
    previous = {str(f): file_fingerprint(f)}
    assert cache.is_changed(f, previous=previous) is False
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_map_cache.py -v`
Expected: FAIL — `ImportError: cannot import name 'FileCache'` or `ModuleNotFoundError`.

- [ ] **Step 3.3: Implement cache module**

Create `app/knowledge_map/cache.py`:
```python
"""SHA256 + mtime file fingerprint cache for incremental builds."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def file_fingerprint(path: Path) -> dict[str, Any]:
    """Return {sha256, mtime, size} for a file. Reads the whole file once."""
    data = path.read_bytes()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "mtime": path.stat().st_mtime,
        "size": len(data),
    }


class FileCache:
    """Persistent cache of file fingerprints for incremental rebuilds."""

    def __init__(self, cache_file: Path) -> None:
        self.cache_file = cache_file

    def load(self) -> dict[str, dict[str, Any]]:
        if not self.cache_file.exists():
            return {}
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self, data: dict[str, dict[str, Any]]) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def is_changed(self, path: Path, previous: dict[str, dict[str, Any]]) -> bool:
        key = str(path)
        if key not in previous:
            return True
        prev = previous[key]
        try:
            st = path.stat()
        except FileNotFoundError:
            return True
        # Fast path: mtime + size match → assume unchanged
        if prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size:
            return False
        # Slow path: hash compare
        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        return prev.get("sha256") != current_hash
```

- [ ] **Step 3.4: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_map_cache.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add app/knowledge_map/cache.py tests/test_knowledge_map_cache.py
git commit -m "feat(knowledge_map): file fingerprint cache with TDD"
```

---

## Task 4: AST parser (TDD)

**Files:**
- Create: `tests/fixtures/knowledge_map/sample_module.py`
- Create: `tests/test_knowledge_map_ast.py`
- Create: `app/knowledge_map/ast_parser.py`

- [ ] **Step 4.1: Create AST test fixture**

Create `tests/fixtures/knowledge_map/sample_module.py`:
```python
"""Sample module for AST parser tests."""
from __future__ import annotations
import json
from pathlib import Path

from app.core.llm import get_flash_client


def top_level_func(x: int) -> int:
    """Double x."""
    return x * 2


class SampleAgent:
    """Sample agent class."""

    def __init__(self) -> None:
        self.client = get_flash_client()

    def run(self, query: str) -> str:
        return f"processed: {query}"


async def async_func() -> None:
    """Async function."""
    pass
```

- [ ] **Step 4.2: Write failing test**

Create `tests/test_knowledge_map_ast.py`:
```python
"""Unit tests for app.knowledge_map.ast_parser."""
from __future__ import annotations
from pathlib import Path

import pytest

from app.knowledge_map.ast_parser import parse_python_file, PythonNode

FIXTURE = Path(__file__).parent / "fixtures" / "knowledge_map" / "sample_module.py"


def test_parse_python_file_returns_nodes() -> None:
    result = parse_python_file(FIXTURE)
    assert result.module_doc == "Sample module for AST parser tests."
    assert len(result.imports) >= 3
    assert "app.core.llm.get_flash_client" in result.imports or "app.core.llm" in str(result.imports)
    assert len(result.classes) == 1
    assert len(result.functions) == 2  # top_level_func + async_func


def test_parse_python_file_class_details() -> None:
    result = parse_python_file(FIXTURE)
    cls = result.classes[0]
    assert cls.name == "SampleAgent"
    assert cls.docstring == "Sample agent class."
    method_names = {m.name for m in cls.methods}
    assert method_names == {"__init__", "run"}
    assert cls.line_start > 0
    assert cls.line_end > cls.line_start


def test_parse_python_file_function_details() -> None:
    result = parse_python_file(FIXTURE)
    func_by_name = {f.name: f for f in result.functions}
    assert func_by_name["top_level_func"].docstring == "Double x."
    assert func_by_name["async_func"].is_async is True
    assert func_by_name["top_level_func"].is_async is False


def test_parse_python_file_handles_syntax_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n    pass\n", encoding="utf-8")
    result = parse_python_file(bad)
    assert result is None or result.parse_error is not None
```

- [ ] **Step 4.3: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_map_ast.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_python_file'`.

- [ ] **Step 4.4: Implement AST parser**

Create `app/knowledge_map/ast_parser.py`:
```python
"""Python AST parser — extracts classes, functions, imports (confidence 1.0)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FunctionNode:
    name: str
    line_start: int
    line_end: int
    docstring: Optional[str]
    is_async: bool
    args: list[str] = field(default_factory=list)


@dataclass
class ClassNode:
    name: str
    line_start: int
    line_end: int
    docstring: Optional[str]
    methods: list[FunctionNode] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)


@dataclass
class PythonNode:
    """All AST-extracted facts for a single .py file."""
    path: Path
    module_doc: Optional[str]
    imports: list[str] = field(default_factory=list)
    classes: list[ClassNode] = field(default_factory=list)
    functions: list[FunctionNode] = field(default_factory=list)
    parse_error: Optional[str] = None


def _func_from_node(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionNode:
    return FunctionNode(
        name=node.name,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        docstring=ast.get_docstring(node),
        is_async=isinstance(node, ast.AsyncFunctionDef),
        args=[a.arg for a in node.args.args],
    )


def _import_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    # ImportFrom
    mod = node.module or ""
    return [f"{mod}.{alias.name}" if mod else alias.name for alias in node.names]


def parse_python_file(path: Path) -> Optional[PythonNode]:
    """Parse a .py file and return structured AST facts. None on fatal error."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return PythonNode(path=path, module_doc=None, parse_error=f"read: {e}")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return PythonNode(path=path, module_doc=None, parse_error=f"syntax: {e}")

    result = PythonNode(path=path, module_doc=ast.get_docstring(tree))

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            result.imports.extend(_import_names(node))
        elif isinstance(node, ast.ClassDef):
            cls = ClassNode(
                name=node.name,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                docstring=ast.get_docstring(node),
                bases=[ast.unparse(b) for b in node.bases],
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cls.methods.append(_func_from_node(child))
            result.classes.append(cls)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.functions.append(_func_from_node(node))

    return result
```

- [ ] **Step 4.5: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_map_ast.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 4.6: Commit**

```bash
git add tests/fixtures/knowledge_map/sample_module.py tests/test_knowledge_map_ast.py app/knowledge_map/ast_parser.py
git commit -m "feat(knowledge_map): Python AST parser with TDD"
```

---

## Task 5: Markdown parser (TDD)

**Files:**
- Create: `tests/fixtures/knowledge_map/sample_doc.md`
- Create: `tests/test_knowledge_map_md.py`
- Create: `app/knowledge_map/md_parser.py`

- [ ] **Step 5.1: Create Markdown test fixture**

Create `tests/fixtures/knowledge_map/sample_doc.md`:
```markdown
# Main Title

Intro paragraph with [link to spec](../specs/design.md).

## Section One

Some text.

### Subsection A

More text with [another link](https://example.com).

## Section Two

- bullet one
- bullet two
```

- [ ] **Step 5.2: Write failing test**

Create `tests/test_knowledge_map_md.py`:
```python
"""Unit tests for app.knowledge_map.md_parser."""
from __future__ import annotations
from pathlib import Path

import pytest

from app.knowledge_map.md_parser import parse_markdown_file, MarkdownNode

FIXTURE = Path(__file__).parent / "fixtures" / "knowledge_map" / "sample_doc.md"


def test_parse_markdown_title() -> None:
    result = parse_markdown_file(FIXTURE)
    assert result.title == "Main Title"


def test_parse_markdown_headings() -> None:
    result = parse_markdown_file(FIXTURE)
    heading_texts = [h.text for h in result.headings]
    assert "Main Title" in heading_texts
    assert "Section One" in heading_texts
    assert "Subsection A" in heading_texts
    assert "Section Two" in heading_texts

    by_level = {h.text: h.level for h in result.headings}
    assert by_level["Main Title"] == 1
    assert by_level["Section One"] == 2
    assert by_level["Subsection A"] == 3


def test_parse_markdown_links() -> None:
    result = parse_markdown_file(FIXTURE)
    targets = [l.target for l in result.links]
    assert "../specs/design.md" in targets
    assert "https://example.com" in targets


def test_parse_markdown_date_from_filename(tmp_path: Path) -> None:
    f = tmp_path / "update_log_2026-03-25.md"
    f.write_text("# Daily\n", encoding="utf-8")
    result = parse_markdown_file(f)
    assert result.filename_date == "2026-03-25"


def test_parse_markdown_no_date() -> None:
    result = parse_markdown_file(FIXTURE)
    assert result.filename_date is None
```

- [ ] **Step 5.3: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_map_md.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 5.4: Implement Markdown parser**

Create `app/knowledge_map/md_parser.py`:
```python
"""Markdown structural parser — H1-H6 headings, links, date from filename."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass
class Heading:
    level: int
    text: str
    line: int


@dataclass
class Link:
    text: str
    target: str


@dataclass
class MarkdownNode:
    path: Path
    title: Optional[str]
    headings: list[Heading] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    filename_date: Optional[str] = None
    word_count: int = 0


def parse_markdown_file(path: Path) -> MarkdownNode:
    """Parse a .md file. Never raises — returns an empty node on error."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return MarkdownNode(path=path, title=None)

    node = MarkdownNode(path=path, title=None)

    # Headings (with line numbers)
    for idx, line in enumerate(content.splitlines(), start=1):
        m = _HEADING_RE.match(line)
        if m:
            node.headings.append(Heading(level=len(m.group(1)), text=m.group(2).strip(), line=idx))

    if node.headings and node.headings[0].level == 1:
        node.title = node.headings[0].text

    # Links
    for m in _LINK_RE.finditer(content):
        node.links.append(Link(text=m.group(1), target=m.group(2)))

    # Date from filename (for update_log_YYYY-MM-DD.md)
    dm = _DATE_RE.search(path.name)
    if dm:
        node.filename_date = dm.group(1)

    node.word_count = len(content.split())
    return node
```

- [ ] **Step 5.5: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_map_md.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5.6: Commit**

```bash
git add tests/fixtures/knowledge_map/sample_doc.md tests/test_knowledge_map_md.py app/knowledge_map/md_parser.py
git commit -m "feat(knowledge_map): Markdown parser with TDD"
```

---

## Task 6: Flash prompts

**Files:**
- Create: `prompts/knowledge_map/extract_concepts.txt`
- Create: `prompts/knowledge_map/synthesize_wiki.txt`
- Create: `prompts/knowledge_map/synthesize_report.txt`

- [ ] **Step 6.1: Write extract_concepts prompt**

Create `prompts/knowledge_map/extract_concepts.txt`:
```
You are analyzing source files from the SKIN1004 AI Agent project to build a knowledge map.

For the file below, extract:
1. A 1-2 sentence summary of what this file does (role in the project).
2. Up to 5 domain concepts this file implements or references (e.g., "megawari_filter", "langgraph_sql_agent", "mariadb_connection_pool").
3. Up to 5 relationships to OTHER parts of the project, formatted as (target_hint, relation_type, confidence).
   - target_hint: name of a module/file/concept this relates to
   - relation_type: one of [calls, imports, references, supersedes, implements, documented_in, related_to]
   - confidence: 0.5-0.9 (for inferences; AST-derived imports get 1.0 separately)

Return STRICT JSON (no markdown fences):
{
  "summary": "...",
  "concepts": ["concept_a", "concept_b"],
  "relations": [
    {"target": "app.agents.orchestrator", "type": "calls", "confidence": 0.8},
    {"target": "concept:megawari_filter", "type": "implements", "confidence": 0.9}
  ],
  "tags": ["bigquery", "sql_agent"]
}

If the file is too trivial or uninformative, return empty arrays but always include a summary.

FILE PATH: {file_path}
FILE TYPE: {file_type}
STRUCTURAL FACTS (pre-extracted):
{structural_facts}

FILE CONTENT (may be truncated to 8000 chars):
---
{content}
---
```

- [ ] **Step 6.2: Write synthesize_wiki prompt**

Create `prompts/knowledge_map/synthesize_wiki.txt`:
```
You are writing a single wiki page for a cluster of related files in the SKIN1004 AI Agent project.

Given the cluster name and the list of file summaries below, produce a concise Markdown wiki page (300-600 words) with this structure:

# {cluster_title}

> Auto-generated {date} · Files: {file_count}

## Purpose
(2-3 sentences)

## Key Files
- `path/to/file.py` — short role
- ...

## Key Concepts
- concept_a — what it is in this project
- ...

## How It Fits In
(How this cluster connects to other clusters — use the relation hints provided.)

## Common Questions This Page Answers
- ...
- ...

Rules:
- Write in Korean when referring to domain concepts from CLAUDE.md (megawari, skin1004, etc.), English for code identifiers.
- Cite exact file paths so Claude Code can Read them if needed.
- Never invent facts not present in the inputs.
- Keep under 600 words.

CLUSTER NAME: {cluster_name}
FILE SUMMARIES:
{file_summaries}
RELATIONS TO OTHER CLUSTERS:
{cross_cluster_relations}
```

- [ ] **Step 6.3: Write synthesize_report prompt**

Create `prompts/knowledge_map/synthesize_report.txt`:
```
You are writing GRAPH_REPORT.md — the ONE page Claude Code reads first in every session.

Given the statistics and top nodes below, produce a Markdown report with this exact structure:

# SKIN1004 AI Agent — Knowledge Map
**Generated**: {generated_at} · **Files**: {file_count} · **Nodes**: {node_count} · **Commit**: {commit}

## 🎯 What this project is
(2-3 sentence synthesis from top_level_summary input)

## 🏛️ Top-level Clusters
(Numbered list from clusters input — one line each: name, file count, one-sentence role)

## 🌟 God Nodes (highest edge count — most central)
(Top 8 from god_nodes input — format: `- \`node_id\` ({edge_count} edges) — one-line role`)

## ❓ Suggested Questions This Map Can Answer Instantly
(Generate 8-10 realistic questions that a developer on this project would ask, based on clusters and concepts. Include file paths in parentheses.)

## 📅 Recent Changes
(Bullet list from recent_changes input — one line per entry: `- YYYY-MM-DD · topic`)

## 🔗 How to navigate
Read this file first. Then open graph.json and find the 2-3 nodes most relevant to your question. Read only those nodes' wiki_page values (`knowledge_map/wiki/**/*.md`). Only read original source files if the wiki page doesn't answer. Never Grep without consulting this map first.

Rules:
- Be concrete. Use real file paths, real cluster names, real node ids.
- Korean for domain context, English for code identifiers.
- Total length 400-800 words.

INPUTS:
{inputs_json}
```

- [ ] **Step 6.4: Commit**

```bash
git add prompts/knowledge_map/
git commit -m "feat(knowledge_map): Flash prompts for concepts, wiki, report"
```

---

## Task 7: Semantic module (Gemini Flash integration)

**Files:**
- Create: `tests/test_knowledge_map_semantic.py`
- Create: `app/knowledge_map/semantic.py`

- [ ] **Step 7.1: Write failing test**

Create `tests/test_knowledge_map_semantic.py`:
```python
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
```

- [ ] **Step 7.2: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_map_semantic.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 7.3: Implement semantic module**

Create `app/knowledge_map/semantic.py`:
```python
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
    from app.core.llm import get_flash_client  # local import to avoid cycles
    client = get_flash_client()
    # Adapt to existing client API. Most get_flash_client implementations
    # expose an async `generate` or `chat` method. We assume `generate_async`.
    return await asyncio.to_thread(client.generate, prompt)


def _parse_response(raw: str) -> SemanticFacts:
    """Tolerant JSON parse — strips code fences, returns error node on failure."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip ``` fences
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
```

- [ ] **Step 7.4: Install pytest-asyncio if missing**

Run: `python -c "import pytest_asyncio" 2>&1 || python -m pip install pytest-asyncio`
Expected: either already installed, or installs.

Add to `tests/test_knowledge_map_semantic.py` top if not already configured globally:
```python
pytestmark = pytest.mark.asyncio
```

If the project has `pyproject.toml`/`pytest.ini` with `asyncio_mode = "auto"`, skip this.

- [ ] **Step 7.5: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_map_semantic.py -v`
Expected: 2 tests PASS.

- [ ] **Step 7.6: Commit**

```bash
git add tests/test_knowledge_map_semantic.py app/knowledge_map/semantic.py
git commit -m "feat(knowledge_map): Gemini Flash semantic extraction with retries"
```

---

## Task 8: Graph module (NetworkX + Louvain)

**Files:**
- Create: `tests/test_knowledge_map_graph.py`
- Create: `app/knowledge_map/graph.py`

- [ ] **Step 8.1: Write failing test**

Create `tests/test_knowledge_map_graph.py`:
```python
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
    # Two dense communities
    for n in ["a1", "a2", "a3"]:
        g.add_node(Node(id=n, type="file"))
    for n in ["b1", "b2", "b3"]:
        g.add_node(Node(id=n, type="file"))
    # Dense inside a-group
    g.add_edge(Edge(src="a1", dst="a2", type="calls", confidence=1.0))
    g.add_edge(Edge(src="a2", dst="a3", type="calls", confidence=1.0))
    g.add_edge(Edge(src="a1", dst="a3", type="calls", confidence=1.0))
    # Dense inside b-group
    g.add_edge(Edge(src="b1", dst="b2", type="calls", confidence=1.0))
    g.add_edge(Edge(src="b2", dst="b3", type="calls", confidence=1.0))
    g.add_edge(Edge(src="b1", dst="b3", type="calls", confidence=1.0))
    # One weak bridge
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
```

- [ ] **Step 8.2: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_map_graph.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 8.3: Implement graph module**

Create `app/knowledge_map/graph.py`:
```python
"""NetworkX graph wrapper + Louvain community detection for Knowledge Map."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx


@dataclass
class Node:
    id: str
    type: str  # file / module / class / function / concept / doc
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
    type: str  # calls / imports / references / supersedes / implements / documented_in / related_to
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
        import community as community_louvain  # python-louvain

        if not self._node_data:
            return

        # Project MultiDiGraph → undirected simple graph, summing confidence as weight
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
        # Map integer cluster id → stable string label
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
```

- [ ] **Step 8.4: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_map_graph.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 8.5: Commit**

```bash
git add tests/test_knowledge_map_graph.py app/knowledge_map/graph.py
git commit -m "feat(knowledge_map): NetworkX graph + Louvain clustering with TDD"
```

---

## Task 9: Exporters (graph.json + wiki + GRAPH_REPORT)

**Files:**
- Create: `tests/test_knowledge_map_exporters.py`
- Create: `app/knowledge_map/exporters.py`

- [ ] **Step 9.1: Write failing test**

Create `tests/test_knowledge_map_exporters.py`:
```python
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
```

- [ ] **Step 9.2: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge_map_exporters.py -v`
Expected: FAIL.

- [ ] **Step 9.3: Implement exporters**

Create `app/knowledge_map/exporters.py`:
```python
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
    # Drop None/empty for compactness
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
```

- [ ] **Step 9.4: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge_map_exporters.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 9.5: Commit**

```bash
git add tests/test_knowledge_map_exporters.py app/knowledge_map/exporters.py
git commit -m "feat(knowledge_map): exporters for graph.json, wiki index, log"
```

---

## Task 10: Builder (main orchestrator)

**Files:**
- Create: `app/knowledge_map/builder.py`

- [ ] **Step 10.1: Implement builder**

Create `app/knowledge_map/builder.py`:
```python
"""Knowledge Map build orchestrator — discover → cache → parse → flash → graph → export."""
from __future__ import annotations

import asyncio
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from app.knowledge_map.ast_parser import parse_python_file, PythonNode
from app.knowledge_map.cache import FileCache, file_fingerprint
from app.knowledge_map.config import (
    CACHE_FILE,
    EXCLUDE_FRAGMENTS,
    GRAPH_JSON,
    INCLUDE_EXTENSIONS,
    REPORT_MD,
    SOURCE_ROOTS,
    WIKI_DIR,
    WIKI_INDEX,
    WIKI_LOG,
)
from app.knowledge_map.exporters import (
    append_wiki_log,
    write_graph_json,
    write_graph_report,
    write_wiki_index,
)
from app.knowledge_map.graph import Edge, KnowledgeGraph, Node
from app.knowledge_map.md_parser import parse_markdown_file, MarkdownNode
from app.knowledge_map.semantic import SemanticFacts, extract_semantic_facts_batch

logger = structlog.get_logger(__name__)


def _is_excluded(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(frag in s for frag in EXCLUDE_FRAGMENTS)


def discover_source_files() -> list[Path]:
    """Walk SOURCE_ROOTS, filter by extension and exclude patterns."""
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in INCLUDE_EXTENSIONS:
                continue
            if _is_excluded(p):
                continue
            files.append(p)
    return sorted(files)


def _current_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _python_facts_to_nodes(py: PythonNode) -> tuple[list[Node], list[Edge]]:
    """Convert AST result → confidence-1.0 nodes and edges."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    file_id = str(py.path).replace("\\", "/")
    nodes.append(Node(
        id=file_id,
        type="file",
        file=file_id,
        summary=py.module_doc or "",
        confidence=1.0,
    ))
    for cls in py.classes:
        cid = f"{file_id}::{cls.name}"
        nodes.append(Node(
            id=cid,
            type="class",
            file=file_id,
            lines=[cls.line_start, cls.line_end],
            summary=cls.docstring or "",
            confidence=1.0,
        ))
        edges.append(Edge(src=file_id, dst=cid, type="documented_in", confidence=1.0))
    for fn in py.functions:
        fid = f"{file_id}::{fn.name}"
        nodes.append(Node(
            id=fid,
            type="function",
            file=file_id,
            lines=[fn.line_start, fn.line_end],
            summary=fn.docstring or "",
            confidence=1.0,
        ))
        edges.append(Edge(src=file_id, dst=fid, type="documented_in", confidence=1.0))
    for imp in py.imports:
        edges.append(Edge(src=file_id, dst=imp, type="imports", confidence=1.0))
    return nodes, edges


def _md_facts_to_nodes(md: MarkdownNode) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    file_id = str(md.path).replace("\\", "/")
    nodes.append(Node(
        id=file_id,
        type="doc",
        file=file_id,
        summary=md.title or "",
        tags=[md.filename_date] if md.filename_date else [],
        confidence=1.0,
    ))
    for link in md.links:
        # Only internal links become edges
        if not link.target.startswith("http"):
            edges.append(Edge(src=file_id, dst=link.target, type="references", confidence=0.7))
    return nodes, edges


def _merge_semantic_into_graph(
    graph: KnowledgeGraph,
    file_id: str,
    facts: SemanticFacts,
) -> None:
    if facts.parse_error:
        return
    # Update file node summary if empty
    node = graph.get_node(file_id)
    if not node.summary and facts.summary:
        node.summary = facts.summary
    if facts.tags:
        node.tags = list(set(node.tags + facts.tags))
    # Add concept nodes + implements edges
    for concept in facts.concepts:
        cid = f"concept:{concept}"
        if cid not in {n.id for n in graph.nodes()}:
            graph.add_node(Node(id=cid, type="concept", summary=concept, confidence=0.8))
        graph.add_edge(Edge(src=file_id, dst=cid, type="implements", confidence=0.8))
    # Add inferred relations
    for rel in facts.relations:
        target = rel.get("target")
        rtype = rel.get("type", "related_to")
        conf = float(rel.get("confidence", 0.6))
        if target:
            graph.add_edge(Edge(src=file_id, dst=str(target), type=str(rtype), confidence=conf))


async def build(
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the full build pipeline. Returns a stats dict."""
    started = datetime.now()
    logger.info("knowledge_map.build.start", force=force, dry_run=dry_run)

    files = discover_source_files()
    logger.info("knowledge_map.discovered", count=len(files))

    cache = FileCache(CACHE_FILE)
    previous = {} if force else cache.load()
    changed = [f for f in files if cache.is_changed(f, previous)]
    logger.info("knowledge_map.changed", count=len(changed), total=len(files))

    if dry_run:
        return {
            "files": len(files),
            "changed": len(changed),
            "estimated_flash_calls": len(changed),
            "duration_sec": (datetime.now() - started).total_seconds(),
        }

    graph = KnowledgeGraph()
    semantic_items: list[tuple[Path, str, dict[str, Any]]] = []

    # 1. Structural pass (all files, not just changed — graph must be complete)
    for f in files:
        if f.suffix == ".py":
            py = parse_python_file(f)
            if py is None:
                continue
            nodes, edges = _python_facts_to_nodes(py)
            for n in nodes:
                graph.add_node(n)
            for e in edges:
                graph.add_edge(e)
            if f in changed:
                semantic_items.append((f, "python", {"classes": [c.name for c in py.classes], "functions": [fn.name for fn in py.functions]}))
        elif f.suffix == ".md":
            md = parse_markdown_file(f)
            nodes, edges = _md_facts_to_nodes(md)
            for n in nodes:
                graph.add_node(n)
            for e in edges:
                graph.add_edge(e)
            if f in changed:
                semantic_items.append((f, "markdown", {"title": md.title, "headings": [h.text for h in md.headings[:10]]}))

    # 2. Semantic pass (only changed files)
    flash_calls = 0
    if semantic_items:
        logger.info("knowledge_map.flash.start", count=len(semantic_items))
        results = await extract_semantic_facts_batch(semantic_items)
        for (path, _, _), facts in zip(semantic_items, results):
            file_id = str(path).replace("\\", "/")
            _merge_semantic_into_graph(graph, file_id, facts)
        flash_calls = len(semantic_items)

    # 3. Clustering
    graph.compute_clusters()

    # 4. Export
    commit = _current_commit()
    write_graph_json(
        graph,
        GRAPH_JSON,
        commit=commit,
        file_count=len(files),
        extra_stats={
            "flash_calls": flash_calls,
            "cache_hits": len(files) - len(changed),
            "build_duration_sec": round((datetime.now() - started).total_seconds(), 2),
        },
    )
    write_wiki_index(graph, WIKI_INDEX)

    # Minimal placeholder GRAPH_REPORT.md until Flash synthesis is wired in Task 11
    report_body = (
        f"# SKIN1004 AI Agent — Knowledge Map\n"
        f"**Generated**: {datetime.now().astimezone().isoformat()} · "
        f"**Files**: {len(files)} · **Nodes**: {len(graph.nodes())} · "
        f"**Edges**: {len(graph.edges())} · **Commit**: {commit}\n\n"
        f"## Clusters\n"
    )
    for cluster, cnt in sorted(graph.cluster_counts().items()):
        report_body += f"- **{cluster}** — {cnt} nodes\n"
    report_body += "\n## God Nodes\n"
    for n in graph.god_nodes(top_n=8):
        report_body += f"- `{n.id}` ({n.type}) — {n.summary[:80] or 'no summary'}\n"
    report_body += "\n## How to navigate\nRead this file first, then open graph.json and follow wiki_page fields. Never Grep without consulting this map.\n"
    write_graph_report(report_body, REPORT_MD)

    # Update cache with new fingerprints
    new_cache = {str(f): file_fingerprint(f) for f in files}
    cache.save(new_cache)

    # Append log
    append_wiki_log(WIKI_LOG, f"build complete · files={len(files)} changed={len(changed)} flash={flash_calls}")

    stats = {
        "files": len(files),
        "changed": len(changed),
        "nodes": len(graph.nodes()),
        "edges": len(graph.edges()),
        "clusters": len(graph.cluster_counts()),
        "flash_calls": flash_calls,
        "duration_sec": round((datetime.now() - started).total_seconds(), 2),
    }
    logger.info("knowledge_map.build.done", **stats)
    return stats
```

- [ ] **Step 10.2: Smoke test import**

Run:
```bash
python -c "from app.knowledge_map.builder import discover_source_files; files = discover_source_files(); print(f'discovered {len(files)} files'); print(files[:5])"
```
Expected: prints a non-zero count and 5 sample paths. No import errors.

- [ ] **Step 10.3: Commit**

```bash
git add app/knowledge_map/builder.py
git commit -m "feat(knowledge_map): build orchestrator (discover→parse→flash→graph→export)"
```

---

## Task 11: CLI entrypoint

**Files:**
- Create: `scripts/build_knowledge_graph.py`

- [ ] **Step 11.1: Implement CLI**

Create `scripts/build_knowledge_graph.py`:
```python
"""CLI entrypoint for Knowledge Map build.

Usage:
    python scripts/build_knowledge_graph.py              # incremental
    python scripts/build_knowledge_graph.py --force      # rebuild all
    python scripts/build_knowledge_graph.py --dry-run    # show plan only
    python scripts/build_knowledge_graph.py --bootstrap  # alias for --force
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path so `from app...` works when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.knowledge_map.builder import build  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SKIN1004 Knowledge Map")
    parser.add_argument("--force", action="store_true", help="Rebuild everything, ignore cache")
    parser.add_argument("--bootstrap", action="store_true", help="Alias for --force (first run)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be built, no Flash calls")
    args = parser.parse_args()

    force = args.force or args.bootstrap
    stats = asyncio.run(build(force=force, dry_run=args.dry_run))

    print("=" * 60)
    print("Knowledge Map build complete")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:20s}: {v}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 11.2: Dry-run verification**

Run: `python scripts/build_knowledge_graph.py --dry-run`
Expected:
- Prints `files`, `changed`, `estimated_flash_calls`, `duration_sec`
- `files` should be roughly 150-250 (all .py under app/ and .md under docs/ minus exclusions)
- `changed` should equal `files` on first run (cache empty)
- No Flash calls made

- [ ] **Step 11.3: Commit**

```bash
git add scripts/build_knowledge_graph.py
git commit -m "feat(knowledge_map): CLI entrypoint with dry-run / force / bootstrap"
```

---

## Task 12: Validator

**Files:**
- Create: `scripts/validate_graph.py`

- [ ] **Step 12.1: Implement validator**

Create `scripts/validate_graph.py`:
```python
"""Validate knowledge_map/graph.json — schema, integrity, dangling references.

Exit code 0 = healthy, 1 = issues found.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
GRAPH_JSON = _ROOT / "knowledge_map" / "graph.json"

_REQUIRED_TOP = {"version", "generated_at", "source_commit", "stats", "nodes", "edges"}
_REQUIRED_NODE = {"id", "type"}
_REQUIRED_EDGE = {"from", "to", "type", "confidence"}
_VALID_EDGE_TYPES = {"calls", "imports", "references", "supersedes", "implements", "documented_in", "related_to"}


def validate() -> int:
    if not GRAPH_JSON.exists():
        print(f"❌ {GRAPH_JSON} does not exist. Run build first.")
        return 1
    try:
        data = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ graph.json is not valid JSON: {e}")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    missing = _REQUIRED_TOP - set(data.keys())
    if missing:
        errors.append(f"missing top-level keys: {missing}")

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    node_ids = {n.get("id") for n in nodes}

    for n in nodes:
        missing = _REQUIRED_NODE - set(n.keys())
        if missing:
            errors.append(f"node {n.get('id', '?')} missing {missing}")

    for e in edges:
        missing = _REQUIRED_EDGE - set(e.keys())
        if missing:
            errors.append(f"edge {e} missing {missing}")
            continue
        if e["type"] not in _VALID_EDGE_TYPES:
            errors.append(f"edge {e['from']}→{e['to']} has unknown type: {e['type']}")
        if e["from"] not in node_ids:
            warnings.append(f"dangling src: {e['from']} (edge {e['from']}→{e['to']})")

    # Cluster sanity
    clusters = {n.get("cluster") for n in nodes if n.get("cluster")}
    if not clusters:
        warnings.append("no clusters assigned — did compute_clusters() run?")

    print(f"Nodes:    {len(nodes)}")
    print(f"Edges:    {len(edges)}")
    print(f"Clusters: {len(clusters)}")
    print(f"Errors:   {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    for err in errors[:20]:
        print(f"  ❌ {err}")
    for w in warnings[:20]:
        print(f"  ⚠️  {w}")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(validate())
```

- [ ] **Step 12.2: Commit**

```bash
git add scripts/validate_graph.py
git commit -m "feat(knowledge_map): graph.json validator script"
```

---

## Task 13: First real bootstrap build

**Files:** (outputs, committed at the end)
- `knowledge_map/graph.json`
- `knowledge_map/GRAPH_REPORT.md`
- `knowledge_map/wiki/index.md`
- `knowledge_map/wiki/log.md`
- `knowledge_map/.cache/file_hashes.json` (gitignored)

- [ ] **Step 13.1: Dry-run — verify scope & cost**

Run: `python scripts/build_knowledge_graph.py --dry-run`
Expected: `files` count is reasonable (150-250). If over 300, review `EXCLUDE_FRAGMENTS` for misses.

- [ ] **Step 13.2: Real bootstrap**

Run: `python scripts/build_knowledge_graph.py --bootstrap`
Expected:
- 5-10 minutes runtime
- Flash calls ≈ file count
- Final summary prints `nodes > files`, `edges > nodes`, `clusters` 5-30
- No ImportErrors or tracebacks

If Flash rate-limits: errors will show in structlog. Partial builds are acceptable — re-run to fill gaps.

- [ ] **Step 13.3: Validate**

Run: `python scripts/validate_graph.py`
Expected: `Errors: 0`. Warnings OK in moderation (dangling refs from inferred relations are expected).

- [ ] **Step 13.4: Inspect outputs manually**

Open `knowledge_map/GRAPH_REPORT.md` and skim. It should list clusters and god nodes. If god nodes include obvious project hubs (`app.main`, orchestrator, get_flash_client etc.), the graph is probably healthy.

Open `knowledge_map/graph.json` and check:
- `stats.nodes` is 300-1000 range
- `stats.edges` is 500-3000 range
- Node ids sorted alphabetically
- First few nodes have non-empty `summary`

- [ ] **Step 13.5: Commit outputs**

```bash
git add knowledge_map/graph.json knowledge_map/GRAPH_REPORT.md knowledge_map/wiki/
git commit -m "chore(knowledge_map): initial bootstrap build"
```

---

## Task 14: Task Scheduler registration

**Files:**
- Create: `scripts/register_knowledge_task.ps1`

- [ ] **Step 14.1: Create PowerShell registration script**

Create `scripts/register_knowledge_task.ps1`:
```powershell
# Register SKIN1004-Graphify-Daily Task Scheduler entry.
# Mirrors SKIN1004-AD-Sync-Daily pattern.

param(
    [string]$TaskName = "SKIN1004-Graphify-Daily",
    [string]$TriggerTime = "03:00"
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = (Get-Command python).Source
$ScriptPath = Join-Path $ProjectRoot "scripts\build_knowledge_graph.py"
$LogPath = Join-Path $ProjectRoot "logs\knowledge_build.log"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

# Ensure log directory exists
New-Item -ItemType Directory -Force -Path (Split-Path $LogPath) | Out-Null

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "SKIN1004 Knowledge Map daily rebuild (Karpathy wiki + Graphify). Output: $ProjectRoot\knowledge_map\"

Write-Host "Registered $TaskName — daily at $TriggerTime" -ForegroundColor Green
Write-Host "Verify: schtasks /query /tn $TaskName"
```

- [ ] **Step 14.2: Run registration (requires admin or current user)**

Run: `powershell -ExecutionPolicy Bypass -File scripts/register_knowledge_task.ps1`
Expected: "Registered SKIN1004-Graphify-Daily — daily at 03:00" in green.

- [ ] **Step 14.3: Verify task exists**

Run: `schtasks /query /tn SKIN1004-Graphify-Daily`
Expected: entry listed, status "Ready", next run at 03:00 tomorrow.

- [ ] **Step 14.4: Test-run the task (optional)**

Run: `schtasks /run /tn SKIN1004-Graphify-Daily`
Let it complete, then check `logs/knowledge_build.log` (if stdout redirection added) or `pm2 logs` equivalent.

Expected: the build runs to completion. Incremental (very fast since nothing changed).

- [ ] **Step 14.5: Commit**

```bash
git add scripts/register_knowledge_task.ps1
git commit -m "feat(knowledge_map): Task Scheduler registration script"
```

---

## Task 15: CLAUDE.md trigger (the critical one-line)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 15.1: Read current CLAUDE.md**

Run: `cat CLAUDE.md` (or use Read tool)
Note the current structure — the deployment rules should stay first. The Knowledge Map section goes AFTER the top header and BEFORE the deployment rules if appropriate, or RIGHT AFTER deployment rules if Claude needs to read deployment first. Per our design: **it goes right after the `# SKIN1004 AI Agent — 개발 규칙` header**, making it the first thing Claude sees before reading rules.

- [ ] **Step 15.2: Insert Knowledge Map section**

Edit `CLAUDE.md` — insert the following block IMMEDIATELY AFTER the first line `# SKIN1004 AI Agent — 개발 규칙` and BEFORE the existing `## 배포 규칙 (최우선)` section:

```markdown

## 🧠 Knowledge Map (먼저 읽기 — 필수)

**모든 작업 전에 다음 순서를 지켜라**:

1. **먼저** `knowledge_map/GRAPH_REPORT.md`를 읽는다. 한 페이지에 프로젝트 전체 구조·중심 노드·최근 변경이 요약돼 있다.
2. 필요하면 `knowledge_map/graph.json`을 읽어 관련 노드 2~3개만 골라낸다 (id, cluster, wiki_page 필드).
3. 골라낸 노드의 `wiki_page` 경로(`knowledge_map/wiki/**.md`)만 Read한다.
4. **그래도 부족할 때만** 원본 파일(`app/**`, `docs/**`)을 Read하거나 Grep한다.

**금지 행동**:
- GRAPH_REPORT.md를 건너뛰고 바로 Grep/Glob하지 마라. 토큰 낭비다.
- `knowledge_map/` 디렉토리를 무시하지 마라. 매일 03:00 자동 업데이트되는 신뢰 가능한 소스다.
- 지도가 낡았다고 판단되면 `python scripts/build_knowledge_graph.py --force` 실행을 제안하라.

**지도가 커버하지 못하는 영역**:
- `tests/`, `scripts/` 일회성 파일, `backup_*`, `logs/`, `temp_*`, `app/frontend/`, `app/static/` — 이들은 지도에 없다. 필요시 직접 탐색.

```

- [ ] **Step 15.3: Verify the edit**

Run: `head -40 CLAUDE.md`
Expected: the Knowledge Map section appears immediately after the top header and before 배포 규칙.

- [ ] **Step 15.4: Commit**

```bash
git add CLAUDE.md
git commit -m "feat(knowledge_map): CLAUDE.md trigger — AI auto-reads map first"
```

---

## Task 16: End-to-end verification

- [ ] **Step 16.1: Final validate**

Run: `python scripts/validate_graph.py`
Expected: `Errors: 0`.

- [ ] **Step 16.2: Confirm Task Scheduler**

Run: `schtasks /query /tn SKIN1004-Graphify-Daily /fo LIST | findstr /I "TaskName Status Next"`
Expected: Task exists, Status Ready, Next Run Time tomorrow 03:00.

- [ ] **Step 16.3: Smoke test — wiki/log.md**

Run: `cat knowledge_map/wiki/log.md`
Expected: at least one timestamped line from the bootstrap build.

- [ ] **Step 16.4: Smoke test — CLAUDE.md readability**

Open `CLAUDE.md` in an editor and verify the Knowledge Map block appears as the very first content after the title. The one-line rule "먼저 GRAPH_REPORT.md를 읽는다" should be visible in the first screen.

- [ ] **Step 16.5: Run all knowledge_map tests once**

Run: `python -m pytest tests/test_knowledge_map_*.py -v`
Expected: all green.

- [ ] **Step 16.6: Tag the milestone**

```bash
git tag -a knowledge-map-v1.0 -m "Knowledge Map v1.0 — Karpathy wiki + Graphify bootstrap"
```
(Don't push the tag automatically — user can push when ready.)

---

## Notes for the implementing engineer

- **Flash client API**: `app.core.llm.get_flash_client()` returns a Gemini Flash client. If its method is not a sync `generate(prompt) -> str`, adapt `_flash_json_call` in `app/knowledge_map/semantic.py` accordingly. Check with `python -c "from app.core.llm import get_flash_client; c = get_flash_client(); print(dir(c))"`.
- **pytest asyncio mode**: if `pyproject.toml` doesn't set `asyncio_mode = "auto"`, each async test needs `@pytest.mark.asyncio` decorator. The plan assumes auto mode; fall back to explicit decorators if pytest complains.
- **Windows paths**: use `Path` objects throughout. Never hardcode backslashes. When serializing node ids, always normalize to forward slashes.
- **Git auto-commit by scheduled task**: the PowerShell script does NOT auto-commit. Daily commits of `knowledge_map/` will need a follow-up wrapper that runs `git add knowledge_map/ && git commit ...` after build. For v1.0 we leave this manual — the user reviews the diff next morning. (Out of scope for v1.0 per spec.)
- **Flash cost**: first bootstrap ~$1-2. Monitor `flash_calls` in the build summary. Kill the process if the count gets wildly out of proportion.
- **If validator fails with "no clusters"**: python-louvain requires the undirected projection to have edges. Very small graphs may produce 0 clusters — acceptable for first run if the project grows.

## Success criteria (mirrored from spec)

- [ ] First build completed, `knowledge_map/GRAPH_REPORT.md` + `graph.json` + `wiki/` exist
- [ ] `scripts/validate_graph.py` exits 0
- [ ] Task Scheduler `SKIN1004-Graphify-Daily` registered and visible in `schtasks /query`
- [ ] CLAUDE.md trigger section added at top
- [ ] All knowledge_map pytest tests passing
- [ ] Sample query token savings measured (optional — defer to v1.1)
