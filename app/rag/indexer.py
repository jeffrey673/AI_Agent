"""BigQuery vector indexing for RAG embeddings."""

import json
import uuid
from typing import Any, Dict, List, Optional

import structlog

from app.config import get_settings
from app.core.bigquery import get_bigquery_client
from app.core.embeddings import get_embedding_model

logger = structlog.get_logger(__name__)


class VectorIndexer:
    """Index document chunks into BigQuery as vector embeddings."""

    def __init__(self, batch_size: int = 50) -> None:
        """Initialize the indexer.

        Args:
            batch_size: Number of chunks to process per batch.
        """
        self.batch_size = batch_size
        self.settings = get_settings()
        logger.info("vector_indexer_initialized", batch_size=batch_size)

    def index_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Generate embeddings and insert chunks into BigQuery.

        Args:
            chunks: List of chunk dicts with id, content, metadata, source_type.

        Returns:
            Number of chunks successfully indexed.
        """
        if not chunks:
            return 0

        embedding_model = get_embedding_model()
        bq = get_bigquery_client()
        indexed_count = 0

        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            texts = [chunk["content"] for chunk in batch]

            try:
                # Generate embeddings
                embeddings = embedding_model.embed(texts)

                # Prepare rows for BigQuery
                rows = []
                for chunk, embedding in zip(batch, embeddings):
                    row = {
                        "id": chunk.get("id", str(uuid.uuid4())),
                        "content": chunk["content"],
                        "metadata": json.dumps(
                            chunk.get("metadata", {}), ensure_ascii=False
                        ),
                        "embedding": embedding,
                        "source_type": chunk.get("source_type", "unknown"),
                    }
                    rows.append(row)

                # Insert into BigQuery
                bq.insert_embeddings(rows)
                indexed_count += len(rows)

                logger.info(
                    "batch_indexed",
                    batch_start=i,
                    batch_size=len(batch),
                    total_indexed=indexed_count,
                )

            except Exception as e:
                logger.error(
                    "batch_indexing_failed",
                    batch_start=i,
                    error=str(e),
                )

        logger.info("indexing_completed", total_indexed=indexed_count, total_chunks=len(chunks))
        return indexed_count

    def delete_by_source(self, source: str) -> None:
        """Delete all embeddings from a specific source.

        Args:
            source: Source identifier to delete.
        """
        bq = get_bigquery_client()
        table = self.settings.embeddings_table_full_path

        sql = f"""
        DELETE FROM `{table}`
        WHERE JSON_VALUE(metadata, '$.source') = '{source}'
        """

        try:
            bq.client.query(sql).result()
            logger.info("embeddings_deleted", source=source)
        except Exception as e:
            logger.error("embedding_deletion_failed", source=source, error=str(e))
            raise

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector index.

        Returns:
            Dict with total_documents, source_types, etc.
        """
        bq = get_bigquery_client()
        table = self.settings.embeddings_table_full_path

        sql = f"""
        SELECT
            COUNT(*) AS total_documents,
            COUNT(DISTINCT source_type) AS source_type_count,
            COUNT(DISTINCT JSON_VALUE(metadata, '$.source')) AS unique_sources,
            MIN(created_at) AS oldest_entry,
            MAX(created_at) AS newest_entry
        FROM `{table}`
        """

        try:
            results = bq.execute_query(sql, timeout=15.0, max_rows=1)
            return results[0] if results else {}
        except Exception as e:
            logger.error("stats_retrieval_failed", error=str(e))
            return {"error": str(e)}


def get_vector_indexer(batch_size: int = 50) -> VectorIndexer:
    """Create a new vector indexer instance."""
    return VectorIndexer(batch_size=batch_size)
