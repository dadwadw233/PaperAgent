import argparse
import hashlib
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from pypdf import PdfReader
from sqlmodel import Session, select

from backend.app.db import create_db_engine, init_db
from backend.app.models import Chunk, FileAttachment, Paper


def chunk_streaming(text: str, chunk_size: int, overlap: int, carry: str = "") -> Tuple[List[str], str]:
    """Split text into chunks with overlap, returning new chunks and carry remainder."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    # normalize to utf-8 friendly form, replace surrogates
    safe_text = (carry + text).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    buffer = safe_text
    chunks: List[str] = []
    while len(buffer) >= chunk_size:
        chunk = buffer[:chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        buffer = buffer[chunk_size - overlap :]
    return chunks, buffer


def extract_pdf_pages(pdf_path: Path):
    """Yield text per page to avoid loading entire PDF in memory."""
    try:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            txt = page.extract_text() or ""
            # sanitize to avoid surrogate errors downstream
            safe = txt.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            yield safe
    except Exception as exc:  # pypdf can raise various errors; we keep it broad but logged.
        print(f"[WARN] Failed to parse PDF {pdf_path}: {exc}")
        return


def hash_chunk(paper_id: int, source_path: str, seq: int, content: str) -> str:
    h = hashlib.md5()
    h.update(f"{paper_id}:{source_path}:{seq}".encode("utf-8"))
    h.update(content.encode("utf-8"))
    return h.hexdigest()


def process_pdf_for_paper(
    session: Session,
    paper: Paper,
    pdf_path: Path,
    chunk_size: int,
    overlap: int,
    start_seq: int = 0,
) -> Tuple[int, int]:
    inserted = 0
    skipped = 0
    carry = ""
    seq = start_seq
    for page_text in extract_pdf_pages(pdf_path):
        new_chunks, carry = chunk_streaming(page_text, chunk_size=chunk_size, overlap=overlap, carry=carry)
        for chunk in new_chunks:
            chunk_hash = hash_chunk(paper.id, str(pdf_path), seq, chunk)
            exists = session.exec(select(Chunk).where(Chunk.hash == chunk_hash)).first()
            if exists:
                skipped += 1
            else:
                rec = Chunk(
                    paper_id=paper.id,
                    source_path=str(pdf_path),
                    seq=seq,
                    hash=chunk_hash,
                    content=chunk,
                    text_length=len(chunk),
                )
                session.add(rec)
                inserted += 1
            seq += 1
    # flush remaining carry
    if carry.strip():
        chunk = carry.strip()
        chunk_hash = hash_chunk(paper.id, str(pdf_path), seq, chunk)
        exists = session.exec(select(Chunk).where(Chunk.hash == chunk_hash)).first()
        if exists:
            skipped += 1
        else:
            rec = Chunk(
                paper_id=paper.id,
                source_path=str(pdf_path),
                seq=seq,
                hash=chunk_hash,
                content=chunk,
                text_length=len(chunk),
            )
            session.add(rec)
            inserted += 1
    return inserted, skipped


def ingest_pdfs(
    limit_papers: Optional[int],
    chunk_size: int,
    overlap: int,
    progress_cb: Optional[Callable[[Dict], None]] = None,
):
    engine = create_db_engine()
    init_db(engine)
    with Session(engine) as session:
        papers_query = select(Paper).where(Paper.is_paper == True).order_by(Paper.id)
        if limit_papers:
            papers_query = papers_query.limit(limit_papers)
        papers = session.exec(papers_query).all()

        # 预扫描，先确定总数，避免进度条不断变化
        paper_pdf_list = []
        total_pdfs = 0
        total_papers_with_pdf = 0
        for paper in papers:
            attachments = session.exec(
                select(FileAttachment).where(FileAttachment.paper_id == paper.id)
            ).all()
            pdf_paths = [
                Path(att.path)
                for att in attachments
                if att.path and att.path.lower().endswith(".pdf")
            ]
            if not pdf_paths:
                continue
            paper_pdf_list.append((paper, pdf_paths))
            total_pdfs += len(pdf_paths)
            total_papers_with_pdf += 1

        total_inserted = 0
        total_skipped = 0
        processed_pdfs = 0

        for paper, pdf_paths in paper_pdf_list:
            if progress_cb:
                progress_cb(
                    {
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "stage": "start_paper",
                        "total_papers": total_papers_with_pdf,
                        "total_pdfs": total_pdfs,
                        "chunks_inserted": total_inserted,
                        "chunks_skipped": total_skipped,
                        "processed_pdfs": processed_pdfs,
                    }
                )
            for pdf_path in pdf_paths:
                if not pdf_path.exists():
                    print(f"[WARN] File not found: {pdf_path}")
                    if progress_cb:
                        progress_cb(
                            {
                                "stage": "file_missing",
                                "path": str(pdf_path),
                                "processed_pdfs": processed_pdfs,
                                "total_pdfs": total_pdfs,
                            }
                        )
                    continue
                if progress_cb:
                    progress_cb(
                        {
                            "stage": "start_pdf",
                            "path": str(pdf_path),
                            "processed_pdfs": processed_pdfs,
                            "total_pdfs": total_pdfs,
                        }
                    )
                inserted, skipped = process_pdf_for_paper(
                    session, paper, pdf_path, chunk_size, overlap
                )
                total_inserted += inserted
                total_skipped += skipped
                processed_pdfs += 1
                if progress_cb:
                    progress_cb(
                        {
                            "stage": "done_pdf",
                            "path": str(pdf_path),
                            "processed_pdfs": processed_pdfs,
                            "total_pdfs": total_pdfs,
                            "chunks_inserted": total_inserted,
                            "chunks_skipped": total_skipped,
                        }
                    )
            session.commit()
            if progress_cb:
                progress_cb(
                    {
                        "stage": "done_paper",
                        "paper_id": paper.id,
                        "chunks_inserted": total_inserted,
                        "chunks_skipped": total_skipped,
                        "processed_pdfs": processed_pdfs,
                        "total_pdfs": total_pdfs,
                    }
                )

    print(
        f"PDF processing done. papers_with_pdf={total_papers_with_pdf}, chunks_inserted={total_inserted}, skipped_existing={total_skipped}"
    )
    if progress_cb:
        progress_cb(
            {
                "stage": "finished",
                "papers_with_pdf": total_papers_with_pdf,
                "chunks_inserted": total_inserted,
                "chunks_skipped": total_skipped,
                "total_pdfs": total_pdfs,
                "processed_pdfs": processed_pdfs,
            }
        )


def main():
    parser = argparse.ArgumentParser(description="Process PDF attachments into text chunks.")
    parser.add_argument("--limit-papers", type=int, default=None, help="Limit number of papers to process.")
    parser.add_argument("--chunk-size", type=int, default=1200, help="Chunk size (characters).")
    parser.add_argument("--overlap", type=int, default=200, help="Overlap between chunks (characters).")
    args = parser.parse_args()
    ingest_pdfs(
        limit_papers=args.limit_papers,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )


if __name__ == "__main__":
    main()
