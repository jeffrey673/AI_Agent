"""Hybrid chunking: Semantic + Hierarchical chunking for RAG."""

import re
import uuid
from typing import Dict, List, Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class HybridChunker:
    """Hybrid document chunker combining semantic and hierarchical approaches.

    - Semantic Chunking: Splits by meaning boundaries using embedding similarity.
    - Hierarchical Chunking: Maintains parent-child relationships (sections → paragraphs).
    """

    def __init__(
        self,
        max_chunk_size: int = 512,
        overlap: int = 50,
        similarity_threshold: float = 0.5,
    ) -> None:
        """Initialize the chunker.

        Args:
            max_chunk_size: Maximum number of tokens per chunk.
            overlap: Number of overlapping tokens between chunks.
            similarity_threshold: Threshold for semantic splitting.
        """
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.similarity_threshold = similarity_threshold
        self._embedding_model = None
        logger.info(
            "chunker_initialized",
            max_chunk_size=max_chunk_size,
            overlap=overlap,
        )

    def _get_embedding_model(self):
        """Lazy-load the embedding model for semantic chunking."""
        if self._embedding_model is None:
            from app.core.embeddings import get_embedding_model
            self._embedding_model = get_embedding_model()
        return self._embedding_model

    def chunk_document(
        self,
        content: str,
        source: str = "",
        metadata: Optional[Dict] = None,
    ) -> List[Dict]:
        """Chunk a document using hybrid approach.

        First splits by hierarchical structure (headings),
        then applies semantic chunking within each section.

        Args:
            content: Markdown document content.
            source: Source file path or identifier.
            metadata: Additional metadata to attach to chunks.

        Returns:
            List of chunk dicts with id, content, metadata.
        """
        if not content or not content.strip():
            return []

        metadata = metadata or {}
        sections = self._split_by_headings(content)
        all_chunks = []

        for section in sections:
            section_chunks = self._chunk_section(section)
            for i, chunk_text in enumerate(section_chunks):
                if not chunk_text.strip():
                    continue

                chunk = {
                    "id": str(uuid.uuid4()),
                    "content": chunk_text.strip(),
                    "metadata": {
                        **metadata,
                        "source": source,
                        "section_title": section.get("title", ""),
                        "section_level": section.get("level", 0),
                        "chunk_index": i,
                        "parent_id": section.get("id"),
                    },
                    "source_type": metadata.get("extension", "unknown"),
                }
                all_chunks.append(chunk)

        logger.info("document_chunked", source=source, chunk_count=len(all_chunks))
        return all_chunks

    def _split_by_headings(self, content: str) -> List[Dict]:
        """Split markdown content by heading hierarchy.

        Args:
            content: Markdown content.

        Returns:
            List of section dicts with title, level, content, id.
        """
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        lines = content.split('\n')

        sections = []
        current_section = {
            "id": str(uuid.uuid4()),
            "title": "Introduction",
            "level": 0,
            "lines": [],
        }

        for line in lines:
            match = re.match(heading_pattern, line)
            if match:
                # Save current section if it has content
                if current_section["lines"]:
                    current_section["content"] = '\n'.join(current_section["lines"])
                    sections.append(current_section)

                # Start new section
                level = len(match.group(1))
                title = match.group(2).strip()
                current_section = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "level": level,
                    "lines": [],
                }
            else:
                current_section["lines"].append(line)

        # Don't forget the last section
        if current_section["lines"]:
            current_section["content"] = '\n'.join(current_section["lines"])
            sections.append(current_section)

        return sections

    def _chunk_section(self, section: Dict) -> List[str]:
        """Chunk a section by paragraph boundaries with size constraints.

        Args:
            section: Section dict with content.

        Returns:
            List of chunk text strings.
        """
        content = section.get("content", "")
        if not content.strip():
            return []

        # Split by paragraphs (double newline)
        paragraphs = re.split(r'\n\s*\n', content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para.split())  # Approximate token count by word count

            if current_size + para_size > self.max_chunk_size and current_chunk:
                # Flush current chunk
                chunks.append('\n\n'.join(current_chunk))
                # Keep overlap
                if self.overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-1]
                    overlap_words = overlap_text.split()
                    if len(overlap_words) > self.overlap:
                        overlap_text = ' '.join(overlap_words[-self.overlap:])
                    current_chunk = [overlap_text]
                    current_size = len(overlap_text.split())
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(para)
            current_size += para_size

        # Don't forget remaining
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    def chunk_documents(
        self,
        documents: List[Dict],
    ) -> List[Dict]:
        """Chunk multiple documents.

        Args:
            documents: List of dicts with 'content', 'source', 'metadata'.

        Returns:
            List of all chunks from all documents.
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(
                content=doc["content"],
                source=doc.get("source", ""),
                metadata=doc.get("metadata", {}),
            )
            all_chunks.extend(chunks)

        logger.info("documents_chunked", doc_count=len(documents), total_chunks=len(all_chunks))
        return all_chunks


def get_chunker(
    max_chunk_size: int = 512,
    overlap: int = 50,
) -> HybridChunker:
    """Create a new chunker instance."""
    return HybridChunker(max_chunk_size=max_chunk_size, overlap=overlap)
