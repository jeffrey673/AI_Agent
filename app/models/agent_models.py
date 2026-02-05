"""v3.0 Multi-Model configuration.

Orchestrator / BigQuery Agent: Opus 4.5 (Tool calling)
Notion / GWS Agent: Sonnet 4 (cost-efficient)
Existing Gemini config in app/config.py is preserved as-is.
"""

from enum import Enum


class AgentModel(Enum):
    ORCHESTRATOR = "claude-opus-4-5-20251101"
    BIGQUERY_AGENT = "claude-opus-4-5-20251101"
    QUERY_VERIFIER = "claude-opus-4-5-20251101"
    NOTION_AGENT = "claude-sonnet-4-20250514"
    GWS_AGENT = "claude-sonnet-4-20250514"
    DIRECT_LLM = "claude-sonnet-4-20250514"


# Gemini fallback (kept during transition)
FALLBACK_MODEL = "gemini-2.0-flash"
