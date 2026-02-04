"""BigQuery table creation script for AI_RAG dataset."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud import bigquery

from app.config import get_settings


def setup_bigquery_tables() -> None:
    """Create the AI_RAG dataset and required tables."""
    settings = get_settings()
    client = bigquery.Client(project=settings.gcp_project_id)

    # 1. Create AI_RAG dataset if not exists
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_dataset_rag}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"

    try:
        client.create_dataset(dataset, exists_ok=True)
        print(f"[OK] Dataset created or already exists: {dataset_id}")
    except Exception as e:
        print(f"[ERROR] Failed to create dataset: {e}")
        return

    # 2. Create rag_embeddings table
    embeddings_table_id = settings.embeddings_table_full_path
    embeddings_schema = [
        bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("content", "STRING"),
        bigquery.SchemaField("metadata", "JSON"),
        bigquery.SchemaField(
            "embedding",
            "FLOAT64",
            mode="REPEATED",
            description="BGE-M3 768-dim embedding vector",
        ),
        bigquery.SchemaField("source_type", "STRING"),
        bigquery.SchemaField(
            "created_at",
            "TIMESTAMP",
            default_value_expression="CURRENT_TIMESTAMP()",
        ),
    ]

    embeddings_table = bigquery.Table(embeddings_table_id, schema=embeddings_schema)
    try:
        client.create_table(embeddings_table, exists_ok=True)
        print(f"[OK] Table created or already exists: {embeddings_table_id}")
    except Exception as e:
        print(f"[ERROR] Failed to create embeddings table: {e}")

    # 3. Create qa_logs table
    qa_logs_table_id = settings.qa_logs_table_full_path
    qa_logs_schema = [
        bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("user_id", "STRING"),
        bigquery.SchemaField("query", "STRING"),
        bigquery.SchemaField("route_type", "STRING"),
        bigquery.SchemaField("generated_sql", "STRING"),
        bigquery.SchemaField("retrieved_docs", "STRING", mode="REPEATED"),
        bigquery.SchemaField("answer", "STRING"),
        bigquery.SchemaField("feedback", "STRING"),
        bigquery.SchemaField("latency_ms", "INT64"),
        bigquery.SchemaField(
            "created_at",
            "TIMESTAMP",
            default_value_expression="CURRENT_TIMESTAMP()",
        ),
    ]

    qa_logs_table = bigquery.Table(qa_logs_table_id, schema=qa_logs_schema)
    try:
        client.create_table(qa_logs_table, exists_ok=True)
        print(f"[OK] Table created or already exists: {qa_logs_table_id}")
    except Exception as e:
        print(f"[ERROR] Failed to create qa_logs table: {e}")

    print("\n[DONE] BigQuery setup completed.")


if __name__ == "__main__":
    setup_bigquery_tables()
