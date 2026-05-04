# SKIN1004 AI Agent — Knowledge Map
**Generated**: 2026-05-04T03:00:03.033103+09:00 · **Files**: 123 · **Nodes**: 502 · **Edges**: 953 · **Commit**: 86b57df

## Clusters
- **cluster_00** — 1 nodes
- **cluster_01** — 1 nodes
- **cluster_02** — 20 nodes
- **cluster_03** — 25 nodes
- **cluster_04** — 43 nodes
- **cluster_05** — 57 nodes
- **cluster_06** — 47 nodes
- **cluster_07** — 1 nodes
- **cluster_08** — 15 nodes
- **cluster_09** — 22 nodes
- **cluster_10** — 1 nodes
- **cluster_11** — 62 nodes
- **cluster_12** — 34 nodes
- **cluster_13** — 21 nodes
- **cluster_14** — 30 nodes
- **cluster_15** — 14 nodes
- **cluster_16** — 1 nodes
- **cluster_17** — 1 nodes
- **cluster_18** — 1 nodes
- **cluster_19** — 1 nodes
- **cluster_20** — 20 nodes
- **cluster_21** — 1 nodes
- **cluster_22** — 1 nodes
- **cluster_23** — 17 nodes
- **cluster_24** — 13 nodes
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
- **cluster_66** — 1 nodes
- **cluster_67** — 1 nodes
- **cluster_68** — 1 nodes
- **cluster_69** — 1 nodes
- **cluster_70** — 1 nodes
- **cluster_71** — 1 nodes
- **cluster_72** — 1 nodes
- **cluster_73** — 1 nodes
- **cluster_74** — 1 nodes
- **cluster_75** — 1 nodes
- **cluster_76** — 1 nodes

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
