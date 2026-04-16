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
