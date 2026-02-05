"""SKIN1004 Enterprise AI - Configuration Management."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # GCP
    gcp_project_id: str = "skin1004-319714"
    google_application_credentials: str = "C:/json_key/skin1004-319714-60527c477460.json"

    # Gemini
    gemini_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""

    # BigQuery - Sales
    bq_dataset_sales: str = "Sales_Integration"
    bq_table_sales: str = "SALES_ALL_Backup"

    # BigQuery - RAG
    bq_dataset_rag: str = "AI_RAG"
    bq_table_embeddings: str = "rag_embeddings"
    bq_table_qa_logs: str = "qa_logs"

    # Embedding
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 768

    # Anthropic (v3.0)
    anthropic_api_key: str = ""

    # Notion MCP (v3.0)
    notion_mcp_token: str = ""

    # Tavily
    tavily_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Chart
    chart_base_url: str = "http://localhost:8100"

    @property
    def sales_table_full_path(self) -> str:
        """Full BigQuery path for the sales table."""
        return f"{self.gcp_project_id}.{self.bq_dataset_sales}.{self.bq_table_sales}"

    @property
    def embeddings_table_full_path(self) -> str:
        """Full BigQuery path for the embeddings table."""
        return f"{self.gcp_project_id}.{self.bq_dataset_rag}.{self.bq_table_embeddings}"

    @property
    def qa_logs_table_full_path(self) -> str:
        """Full BigQuery path for the QA logs table."""
        return f"{self.gcp_project_id}.{self.bq_dataset_rag}.{self.bq_table_qa_logs}"

    @property
    def allowed_tables(self) -> List[str]:
        """Tables allowed for Text-to-SQL queries."""
        return [
            self.sales_table_full_path,
        ]


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
