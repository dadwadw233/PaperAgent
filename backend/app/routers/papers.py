from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from backend.app.db import create_db_engine, get_session
from backend.app.models import FileAttachment, Paper, Summary, Tag


router = APIRouter(prefix="/papers", tags=["papers"])

DEFAULT_SEARCH_FIELDS = ["title", "abstract"]
SUMMARY_FIELD_KEYS = {"summary_long", "summary_one_liner", "summary_snarky"}
FIELD_COLUMN_MAP = {
    "title": Paper.title,
    "abstract": Paper.abstract,
    "authors": Paper.authors,
    "summary_long": Summary.long_summary,
    "summary_one_liner": Summary.one_liner,
    "summary_snarky": Summary.snarky_comment,
}


def parse_search_fields(raw: Optional[str]) -> List[str]:
    if not raw:
        return DEFAULT_SEARCH_FIELDS
    tokens = [token.strip().lower() for token in raw.split(",") if token.strip()]
    expanded: List[str] = []
    for token in tokens:
        if token == "summary":
            expanded.extend(SUMMARY_FIELD_KEYS)
        elif token == "title_abstract":
            expanded.extend(["title", "abstract", "authors"])  # 包含作者
        elif token in FIELD_COLUMN_MAP:
            expanded.append(token)
    return expanded or DEFAULT_SEARCH_FIELDS


def get_db_session():
    engine = create_db_engine()
    with get_session(engine) as session:
        yield session


@router.get("")
def list_papers(
    q: Optional[str] = Query(default=None, description="Search in title/abstract"),
    item_type: Optional[str] = Query(default=None),
    search_fields: Optional[str] = Query(
        default=None,
        description="指定检索字段（逗号分隔），可选：title, abstract, authors, title_abstract, summary, summary_long, summary_one_liner, summary_snarky",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
):
    stmt = select(Paper).where(Paper.is_paper == True)
    if q:
        like = f"%{q}%"
        fields = parse_search_fields(search_fields)
        needs_summary_join = any(field in SUMMARY_FIELD_KEYS for field in fields)
        if needs_summary_join:
            stmt = stmt.outerjoin(Summary, Summary.paper_id == Paper.id)
        conditions = []
        for field in fields:
            column = FIELD_COLUMN_MAP.get(field)
            if not column:
                continue
            conditions.append(column.ilike(like))
        if not conditions:
            conditions = [Paper.title.ilike(like), Paper.abstract.ilike(like)]
        stmt = stmt.where(or_(*conditions))
        if needs_summary_join:
            stmt = stmt.distinct()
    if item_type:
        stmt = stmt.where(Paper.item_type == item_type)
    total = session.exec(
        select(func.count()).select_from(stmt.subquery())
    ).one()
    rows: List[Paper] = session.exec(
        stmt.order_by(Paper.id).offset(offset).limit(limit)
    ).all()
    return {
        "total": total,
        "items": [
            {
                "id": p.id,
                "key": p.key,
                "title": p.title,
                "item_type": p.item_type,
                "year": p.publication_year,
                "doi": p.doi,
                "url": p.url,
            }
            for p in rows
        ],
    }


@router.get("/{paper_id}")
def get_paper(paper_id: int, session: Session = Depends(get_db_session)):
    paper = session.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    summary = session.exec(select(Summary).where(Summary.paper_id == paper_id)).first()
    tags = session.exec(select(Tag).where(Tag.paper_id == paper_id)).all()
    attachments = session.exec(select(FileAttachment).where(FileAttachment.paper_id == paper_id)).all()
    return {
        "id": paper.id,
        "key": paper.key,
        "title": paper.title,
        "authors": paper.authors,
        "item_type": paper.item_type,
        "year": paper.publication_year,
        "doi": paper.doi,
        "url": paper.url,
        "abstract": paper.abstract,
        "manual_tags": paper.manual_tags,
        "automatic_tags": paper.automatic_tags,
        "summary": {
            "long_summary": summary.long_summary if summary else None,
            "one_liner": summary.one_liner if summary else None,
            "snarky_comment": summary.snarky_comment if summary else None,
            "model": summary.model if summary else None,
        },
        "tags": [{"type": t.tag_type, "value": t.value} for t in tags],
        "attachments": [{"path": a.path, "type": a.attachment_type} for a in attachments],
    }
