"""BGE-M3 embedding model for vector search."""

from typing import List, Optional, Union

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class EmbeddingModel:
    """BGE-M3 embedding model wrapper.

    Uses FlagEmbedding for high-quality multilingual embeddings.
    Falls back to sentence-transformers if FlagEmbedding is unavailable.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_name = self.settings.embedding_model
        self.dim = self.settings.embedding_dim
        self._model = None
        self._use_flag_embedding = True
        logger.info("embedding_model_config", model=self.model_name, dim=self.dim)

    def _load_model(self) -> None:
        """Lazy-load the embedding model."""
        if self._model is not None:
            return

        try:
            from FlagEmbedding import BGEM3FlagModel

            self._model = BGEM3FlagModel(self.model_name, use_fp16=True)
            self._use_flag_embedding = True
            logger.info("loaded_flag_embedding_model", model=self.model_name)
        except ImportError:
            logger.warning("FlagEmbedding not available, falling back to sentence-transformers")
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._use_flag_embedding = False
            logger.info("loaded_sentence_transformer_model", model=self.model_name)

    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """Generate embeddings for one or more texts.

        Args:
            texts: A single text string or list of text strings.

        Returns:
            List of embedding vectors (each is a list of floats).
        """
        self._load_model()

        if isinstance(texts, str):
            texts = [texts]

        logger.info("generating_embeddings", count=len(texts))

        try:
            if self._use_flag_embedding:
                output = self._model.encode(
                    texts,
                    batch_size=32,
                    max_length=512,
                )
                # BGE-M3 returns dict with 'dense_vecs'
                embeddings = output["dense_vecs"].tolist()
            else:
                embeddings = self._model.encode(
                    texts,
                    batch_size=32,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                ).tolist()

            logger.info("embeddings_generated", count=len(embeddings), dim=len(embeddings[0]))
            return embeddings

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single query text.

        Args:
            text: Query text string.

        Returns:
            Embedding vector as list of floats.
        """
        result = self.embed(text)
        return result[0]

    def test_connection(self) -> bool:
        """Test embedding model loading and inference.

        Returns:
            True if model works correctly.
        """
        try:
            embedding = self.embed_query("테스트 문장입니다.")
            expected_dim = self.dim
            actual_dim = len(embedding)
            logger.info(
                "embedding_test_passed",
                expected_dim=expected_dim,
                actual_dim=actual_dim,
            )
            return actual_dim == expected_dim
        except Exception as e:
            logger.error("embedding_test_failed", error=str(e))
            return False


# Singleton instance
_model: Optional[EmbeddingModel] = None


def get_embedding_model() -> EmbeddingModel:
    """Get or create the embedding model singleton."""
    global _model
    if _model is None:
        _model = EmbeddingModel()
    return _model
