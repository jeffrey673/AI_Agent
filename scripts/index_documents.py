"""Batch script to parse and index documents into BigQuery vector store."""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.parser import get_document_parser
from app.rag.chunker import get_chunker
from app.rag.indexer import get_vector_indexer


def main(
    input_dir: str,
    batch_size: int = 50,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> None:
    """Parse documents, chunk them, and index to BigQuery.

    Args:
        input_dir: Path to directory containing documents.
        batch_size: Number of chunks per BigQuery insert batch.
        chunk_size: Maximum tokens per chunk.
        chunk_overlap: Overlap tokens between chunks.
    """
    input_path = Path(input_dir)
    if not input_path.is_dir():
        print(f"[ERROR] 디렉토리가 존재하지 않습니다: {input_dir}")
        sys.exit(1)

    print(f"[1/3] 문서 파싱 중... ({input_dir})")
    parser = get_document_parser()
    documents = parser.parse_directory(input_dir)
    print(f"  → {len(documents)}개 문서 파싱 완료")

    if not documents:
        print("[DONE] 파싱할 문서가 없습니다.")
        return

    print(f"[2/3] 문서 청킹 중... (chunk_size={chunk_size}, overlap={chunk_overlap})")
    chunker = get_chunker(max_chunk_size=chunk_size, overlap=chunk_overlap)
    chunks = chunker.chunk_documents(documents)
    print(f"  → {len(chunks)}개 청크 생성")

    if not chunks:
        print("[DONE] 생성된 청크가 없습니다.")
        return

    print(f"[3/3] 벡터 인덱싱 중... (batch_size={batch_size})")
    indexer = get_vector_indexer(batch_size=batch_size)
    indexed = indexer.index_chunks(chunks)
    print(f"  → {indexed}개 청크 인덱싱 완료")

    print(f"\n[DONE] 총 {len(documents)}개 문서 → {len(chunks)}개 청크 → {indexed}개 인덱싱")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="문서 인덱싱 배치 스크립트")
    parser.add_argument("input_dir", help="문서 디렉토리 경로")
    parser.add_argument("--batch-size", type=int, default=50, help="배치 크기 (default: 50)")
    parser.add_argument("--chunk-size", type=int, default=512, help="청크 크기 (default: 512)")
    parser.add_argument("--chunk-overlap", type=int, default=50, help="청크 오버랩 (default: 50)")

    args = parser.parse_args()
    main(
        input_dir=args.input_dir,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
