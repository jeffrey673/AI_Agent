# SKIN1004 AI Agent — Knowledge Map
**Generated**: 2026-04-16T10:31:19.457021+09:00 · **Files**: 109 · **Nodes**: 972 · **Edges**: 1966 · **Commit**: 458ce00

## Clusters
- **cluster_00** — 1 nodes
- **cluster_01** — 14 nodes
- **cluster_02** — 30 nodes
- **cluster_03** — 6 nodes
- **cluster_04** — 53 nodes
- **cluster_05** — 41 nodes
- **cluster_06** — 6 nodes
- **cluster_07** — 10 nodes
- **cluster_08** — 49 nodes
- **cluster_09** — 50 nodes
- **cluster_10** — 6 nodes
- **cluster_11** — 63 nodes
- **cluster_12** — 31 nodes
- **cluster_13** — 37 nodes
- **cluster_14** — 94 nodes
- **cluster_15** — 1 nodes
- **cluster_16** — 112 nodes
- **cluster_17** — 55 nodes
- **cluster_18** — 1 nodes
- **cluster_19** — 30 nodes
- **cluster_20** — 21 nodes
- **cluster_21** — 7 nodes
- **cluster_22** — 6 nodes
- **cluster_23** — 5 nodes
- **cluster_24** — 26 nodes
- **cluster_25** — 18 nodes
- **cluster_26** — 137 nodes
- **cluster_27** — 15 nodes
- **cluster_28** — 6 nodes
- **cluster_29** — 8 nodes
- **cluster_30** — 33 nodes

## God Nodes
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/auth_api.py` (file) — Authentication endpoints: signup, signin, me, logout.

Uses MariaDB for user sto
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/agents/sql_agent.py` (file) — Text-to-SQL Agent using LangGraph.

Workflow: generate_sql → validate_sql → exec
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/routes.py` (file) — OpenAI-compatible API endpoints for Open WebUI integration.
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/knowledge_map/builder.py` (file) — Knowledge Map build orchestrator — discover → cache → parse → flash → graph → ex
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/conversation_api.py` (file) — Conversation CRUD API for chat history (MariaDB).
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/admin_group_api.py` (file) — Admin endpoints: AD user & group management (MariaDB).
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/main.py` (file) — SKIN1004 Enterprise AI - FastAPI application entry point.

Single server on port
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/models/schemas.py` (file) — Pydantic request/response models for OpenAI-compatible API.

## How to navigate
Read this file first, then open graph.json and follow wiki_page fields. Never Grep without consulting this map.
