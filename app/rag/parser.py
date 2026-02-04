"""Document parser using Docling for PDF, HWP, PPT → markdown conversion."""

from pathlib import Path
from typing import List, Optional

import structlog

logger = structlog.get_logger(__name__)


class DocumentParser:
    """Parse documents into markdown using Docling.

    Supports: PDF, DOCX, PPTX, HWP, HTML, Markdown, and more.
    """

    def __init__(self) -> None:
        self._converter = None
        logger.info("document_parser_initialized")

    def _load_converter(self) -> None:
        """Lazy-load the Docling converter."""
        if self._converter is not None:
            return

        from docling.document_converter import DocumentConverter

        self._converter = DocumentConverter()
        logger.info("docling_converter_loaded")

    def parse_file(self, file_path: str) -> str:
        """Parse a single document file to markdown.

        Args:
            file_path: Path to the document file.

        Returns:
            Markdown string of the document content.

        Raises:
            FileNotFoundError: If the file does not exist.
            Exception: If parsing fails.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        logger.info("parsing_file", path=str(path), suffix=path.suffix)
        self._load_converter()

        try:
            result = self._converter.convert(str(path))
            markdown = result.document.export_to_markdown()
            logger.info("file_parsed", path=str(path), content_length=len(markdown))
            return markdown
        except Exception as e:
            logger.error("file_parsing_failed", path=str(path), error=str(e))
            raise

    def parse_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
    ) -> List[dict]:
        """Parse all documents in a directory.

        Args:
            directory: Path to the directory.
            extensions: File extensions to include (e.g., [".pdf", ".pptx"]).
                       Defaults to common document types.

        Returns:
            List of dicts with 'source', 'content', and 'metadata'.
        """
        if extensions is None:
            extensions = [".pdf", ".docx", ".pptx", ".hwp", ".html", ".md", ".txt"]

        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"디렉토리가 아닙니다: {directory}")

        documents = []
        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                try:
                    content = self.parse_file(str(file_path))
                    documents.append({
                        "source": str(file_path),
                        "content": content,
                        "metadata": {
                            "filename": file_path.name,
                            "extension": file_path.suffix,
                            "size_bytes": file_path.stat().st_size,
                        },
                    })
                except Exception as e:
                    logger.warning(
                        "skipping_file",
                        path=str(file_path),
                        error=str(e),
                    )

        logger.info("directory_parsed", directory=directory, doc_count=len(documents))
        return documents


# Singleton
_parser: Optional[DocumentParser] = None


def get_document_parser() -> DocumentParser:
    """Get or create the document parser singleton."""
    global _parser
    if _parser is None:
        _parser = DocumentParser()
    return _parser
