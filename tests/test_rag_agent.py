"""Tests for RAG pipeline components."""

import pytest

from app.rag.chunker import HybridChunker


class TestHybridChunker:
    """Tests for the hybrid document chunker."""

    def setup_method(self):
        self.chunker = HybridChunker(max_chunk_size=50, overlap=10)

    def test_empty_content(self):
        chunks = self.chunker.chunk_document("")
        assert chunks == []

    def test_single_paragraph(self):
        content = "This is a simple paragraph with some text."
        chunks = self.chunker.chunk_document(content, source="test.md")
        assert len(chunks) >= 1
        assert chunks[0]["content"] == content
        assert chunks[0]["metadata"]["source"] == "test.md"

    def test_heading_splitting(self):
        content = """# Section 1

Content of section 1.

# Section 2

Content of section 2.
"""
        chunks = self.chunker.chunk_document(content)
        # Should produce at least 2 chunks (one per section)
        assert len(chunks) >= 2

    def test_hierarchical_sections(self):
        content = """# Main Title

Introduction paragraph.

## Sub Section

Sub section content here.

### Deep Section

Deep nested content.
"""
        chunks = self.chunker.chunk_document(content)
        assert len(chunks) >= 2

        # Check that section titles are captured in metadata
        titles = [c["metadata"]["section_title"] for c in chunks]
        assert any("Main Title" in t for t in titles) or any("Introduction" in t for t in titles)

    def test_chunk_has_required_fields(self):
        content = "Some content for testing."
        chunks = self.chunker.chunk_document(
            content, source="test.pdf", metadata={"extension": ".pdf"}
        )
        assert len(chunks) >= 1

        chunk = chunks[0]
        assert "id" in chunk
        assert "content" in chunk
        assert "metadata" in chunk
        assert "source_type" in chunk

    def test_large_content_splitting(self):
        # Create content larger than max_chunk_size
        paragraphs = [f"Paragraph {i} with enough words to make it count." for i in range(20)]
        content = "\n\n".join(paragraphs)

        chunks = self.chunker.chunk_document(content)
        assert len(chunks) > 1

    def test_chunk_documents_multiple(self):
        docs = [
            {"content": "Document one content.", "source": "doc1.md", "metadata": {}},
            {"content": "Document two content.", "source": "doc2.md", "metadata": {}},
        ]
        chunks = self.chunker.chunk_documents(docs)
        assert len(chunks) >= 2
