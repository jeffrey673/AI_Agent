"""Knowledge layer — persistent fact extraction and retrieval.

Components:
- wiki_extractor: Gemini Flash-based fact extraction from past conversations
- wiki_store: MariaDB read/write for knowledge_wiki
- wiki_map: hierarchical index (domain → entity → metric/period)
"""
