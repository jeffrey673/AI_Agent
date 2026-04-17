# SKIN1004 AI Agent — Knowledge Map
**Generated**: 2026-04-17T03:00:15.402852+09:00 · **Files**: 110 · **Nodes**: 480 · **Edges**: 927 · **Commit**: 9822afd

## Clusters
- **cluster_00** — 1 nodes
- **cluster_01** — 1 nodes
- **cluster_02** — 24 nodes
- **cluster_03** — 71 nodes
- **cluster_04** — 6 nodes
- **cluster_05** — 41 nodes
- **cluster_06** — 23 nodes
- **cluster_07** — 39 nodes
- **cluster_08** — 38 nodes
- **cluster_09** — 26 nodes
- **cluster_10** — 54 nodes
- **cluster_11** — 1 nodes
- **cluster_12** — 12 nodes
- **cluster_13** — 30 nodes
- **cluster_14** — 16 nodes
- **cluster_15** — 14 nodes
- **cluster_16** — 1 nodes
- **cluster_17** — 1 nodes
- **cluster_18** — 1 nodes
- **cluster_19** — 18 nodes
- **cluster_20** — 1 nodes
- **cluster_21** — 1 nodes
- **cluster_22** — 17 nodes
- **cluster_23** — 1 nodes
- **cluster_24** — 1 nodes
- **cluster_25** — 1 nodes
- **cluster_26** — 1 nodes
- **cluster_27** — 1 nodes
- **cluster_28** — 1 nodes
- **cluster_29** — 1 nodes
- **cluster_30** — 1 nodes
- **cluster_31** — 1 nodes
- **cluster_32** — 1 nodes
- **cluster_33** — 1 nodes
- **cluster_34** — 1 nodes
- **cluster_35** — 1 nodes
- **cluster_36** — 1 nodes
- **cluster_37** — 1 nodes
- **cluster_38** — 1 nodes
- **cluster_39** — 1 nodes
- **cluster_40** — 1 nodes
- **cluster_41** — 1 nodes
- **cluster_42** — 1 nodes
- **cluster_43** — 1 nodes
- **cluster_44** — 1 nodes
- **cluster_45** — 1 nodes
- **cluster_46** — 1 nodes
- **cluster_47** — 1 nodes
- **cluster_48** — 1 nodes
- **cluster_49** — 1 nodes
- **cluster_50** — 1 nodes
- **cluster_51** — 1 nodes
- **cluster_52** — 1 nodes
- **cluster_53** — 1 nodes
- **cluster_54** — 1 nodes
- **cluster_55** — 1 nodes
- **cluster_56** — 1 nodes
- **cluster_57** — 1 nodes
- **cluster_58** — 1 nodes
- **cluster_59** — 1 nodes
- **cluster_60** — 1 nodes
- **cluster_61** — 1 nodes
- **cluster_62** — 1 nodes
- **cluster_63** — 1 nodes
- **cluster_64** — 1 nodes
- **cluster_65** — 1 nodes

## God Nodes
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/auth_api.py` (file) — Authentication endpoints: signup, signin, me, logout.

Uses MariaDB for user sto
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/agents/sql_agent.py` (file) — Text-to-SQL Agent using LangGraph.

Workflow: generate_sql → validate_sql → exec
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/routes.py` (file) — OpenAI-compatible API endpoints for Open WebUI integration.
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/knowledge_map/builder.py` (file) — Knowledge Map build orchestrator — discover → cache → parse → flash → graph → ex
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/admin_group_api.py` (file) — Admin endpoints: AD user & group management (MariaDB).
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/api/conversation_api.py` (file) — Conversation CRUD API for chat history (MariaDB).
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/main.py` (file) — SKIN1004 Enterprise AI - FastAPI application entry point.

Single server on port
- `C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/app/models/schemas.py` (file) — Pydantic request/response models for OpenAI-compatible API.

## How to navigate
Read this file first, then open graph.json and follow wiki_page fields. Never Grep without consulting this map.
