import os
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from sqlmodel import Session, select

from backend.app.db import create_db_engine, get_session
from backend.app.models import FileAttachment, Chunk, Summary, Tag
from backend.app.services.pipeline import (
    start_process_pdfs,
    get_job_status,
    start_summarize_job,
    get_summarize_status,
    stop_summarize_job,
    start_embed_job,
    get_embed_status,
    stop_process_pdfs_job,
)
from backend.scripts.dedupe_attachments import dedupe as dedupe_attachments
from backend.scripts.summarize_papers import process_papers as summarize_papers
from backend.app.routers.config import read_config

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class ProcessPdfsRequest(BaseModel):
    chunk_size: int = 1200
    overlap: int = 200
    limit: Optional[int] = None
    skip_existing: bool = True


@router.post("/process_pdfs/start")
def process_pdfs_start(req: ProcessPdfsRequest):
    try:
        job_id = start_process_pdfs(req.chunk_size, req.overlap, req.limit, skip_existing=req.skip_existing)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start process_pdfs: {exc}")
    return {"job_id": job_id}


@router.get("/process_pdfs/status")
def process_pdfs_status(job_id: str = Query(..., description="Job ID from /start")):
    status = get_job_status(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post("/process_pdfs/stop")
def process_pdfs_stop(job_id: str):
    status = stop_process_pdfs_job(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post("/dedupe_attachments")
def dedupe_attachments_endpoint():
    result = dedupe_attachments()
    return {"status": "ok", "result": result}


class SummarizeRequest(BaseModel):
    limit: Optional[int] = None
    chunk_chars: int = 4000
    skip_existing: bool = True
    dry_run: bool = False


class EmbedRequest(BaseModel):
    limit_chunks: Optional[int] = None
    collection: str = "paper_chunks"
    persist_dir: str = "./chroma_store"
    batch_size: int = 16
    embed_base_url: Optional[str] = None
    embed_model: Optional[str] = None
    embed_api_key: Optional[str] = None


@router.post("/embed_chunks/start")
def embed_chunks_start(req: EmbedRequest):
    engine = create_db_engine()
    with get_session(engine) as session:
        cfg = read_config(session)
    for key, override in [
        ("EMBED_BASE_URL", req.embed_base_url),
        ("EMBED_MODEL", req.embed_model),
        ("EMBED_API_KEY", req.embed_api_key),
    ]:
        if override:
            os.environ[key] = override
        elif cfg.get(key):
            os.environ[key] = cfg[key]
    job_id = start_embed_job(
        limit_chunks=req.limit_chunks,
        collection=req.collection,
        persist_dir=req.persist_dir,
        batch_size=req.batch_size,
    )
    return {"job_id": job_id}


@router.get("/embed_chunks/status")
def embed_chunks_status(job_id: str = Query(...)):
    status = get_embed_status(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post("/summarize/start")
def summarize_start(req: SummarizeRequest):
    # Populate env from config entries so scripts can read them.
    engine = create_db_engine()
    with get_session(engine) as session:
        cfg = read_config(session)
    for key in ["LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"]:
        if cfg.get(key):
            os.environ[key] = cfg[key]
    job_id = start_summarize_job(
        limit=req.limit,
        chunk_chars=req.chunk_chars,
        skip_existing=req.skip_existing,
        dry_run=req.dry_run,
    )
    return {"job_id": job_id}


@router.get("/summarize/status")
def summarize_status(job_id: str = Query(...)):
    status = get_summarize_status(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post("/summarize/stop")
def summarize_stop(job_id: str):
    status = stop_summarize_job(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


def get_db_session():
    engine = create_db_engine()
    with get_session(engine) as session:
        yield session


@router.get("/stats")
def pipeline_stats(session: Session = Depends(get_db_session), sample_missing: int = Query(default=20, ge=0, le=200)):
    pdf_attachments: List[FileAttachment] = session.exec(
        select(FileAttachment).where(FileAttachment.path.ilike("%.pdf"))
    ).all()
    pdf_count = len(pdf_attachments)
    papers_with_pdf = {a.paper_id for a in pdf_attachments}

    chunk_rows = session.exec(select(Chunk.paper_id)).all()
    papers_with_chunks = {row[0] if isinstance(row, tuple) else row for row in chunk_rows}

    missing_papers = papers_with_pdf - papers_with_chunks

    chunked_paths = {row[0] if isinstance(row, tuple) else row for row in session.exec(select(Chunk.source_path)).all()}
    missing_pdfs = [p for p in pdf_attachments if p.path not in chunked_paths]

    sample = [{"paper_id": m.paper_id, "path": m.path} for m in missing_pdfs[:sample_missing]]

    summary_rows = session.exec(select(Summary)).all()
    papers_with_summary = {row.paper_id for row in summary_rows}
    missing_summary = len(papers_with_pdf - papers_with_summary)

    return {
        "pdf_count": pdf_count,
        "papers_with_pdf": len(papers_with_pdf),
        "papers_with_chunks": len(papers_with_chunks),
        "missing_papers": len(missing_papers),
        "missing_pdfs": len(missing_pdfs),
        "sample_missing": sample,
        "summary_rows": len(summary_rows),
        "papers_with_summary": len(papers_with_summary),
        "missing_summary": missing_summary,
    }


class ClearSummaryRequest(BaseModel):
    paper_id: int


@router.post("/clear_summary")
def clear_summary(req: ClearSummaryRequest, session: Session = Depends(get_db_session)):
    # delete summary and tags for a paper
    summary_rows = session.exec(select(Summary).where(Summary.paper_id == req.paper_id)).all()
    tag_rows = session.exec(select(Tag).where(Tag.paper_id == req.paper_id)).all()
    for row in summary_rows:
        session.delete(row)
    for row in tag_rows:
        session.delete(row)
    session.commit()
    return {"status": "ok", "deleted_summary": len(summary_rows), "deleted_tags": len(tag_rows)}
