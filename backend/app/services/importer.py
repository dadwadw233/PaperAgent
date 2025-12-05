from pathlib import Path
from typing import Dict, List, Optional, Tuple
import csv

from dateutil import parser as dateparser
from sqlmodel import Session, select

from backend.app.db import create_db_engine, init_db
from backend.app.models import FileAttachment, Paper


NON_PAPER_TYPES = {
    "book",
    "webpage",
    "magazinearticle",
    "blogpost",
    "patent",
    "video",
    "presentation",
    "report",
    "thesis",
}

PAPER_TYPES = {
    "preprint",
    "journalarticle",
    "conferencepaper",
    "paper",
    "article",
    "manuscript",
}


def normalize_item_type(value: str) -> str:
    return value.replace(" ", "").lower()


def is_paper(item_type: str) -> bool:
    normalized = normalize_item_type(item_type)
    if normalized in PAPER_TYPES:
        return True
    if normalized in NON_PAPER_TYPES:
        return False
    return True


def parse_date(value: str):
    if not value:
        return None
    try:
        return dateparser.parse(value)
    except (ValueError, TypeError):
        return None


def split_attachments(value: str) -> List[str]:
    if not value:
        return []
    parts = [v.strip() for v in value.split(";") if v.strip()]
    return parts


def load_csv_rows(csv_path: Path, limit: Optional[int] = None):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if limit:
            rows = rows[:limit]
        return rows


def upsert_paper(session: Session, row: dict) -> Tuple[Paper, bool]:
    item_type_raw = row.get("Item Type") or ""
    paper_flag = is_paper(item_type_raw)
    key = row.get("Key")
    existing = session.exec(select(Paper).where(Paper.key == key)).first()
    if existing:
        return existing, False

    paper = Paper(
        key=key,
        item_type=normalize_item_type(item_type_raw) if item_type_raw else None,
        title=row.get("Title"),
        authors=row.get("Author"),
        publication_title=row.get("Publication Title"),
        publication_year=int(row["Publication Year"]) if row.get("Publication Year") else None,
        doi=row.get("DOI"),
        url=row.get("Url"),
        abstract=row.get("Abstract Note"),
        date=row.get("Date"),
        date_added=parse_date(row.get("Date Added")),
        date_modified=parse_date(row.get("Date Modified")),
        manual_tags=row.get("Manual Tags"),
        automatic_tags=row.get("Automatic Tags"),
        extra=row.get("Extra"),
        notes=row.get("Notes"),
        is_paper=paper_flag,
        raw_item_type=item_type_raw or None,
    )
    session.add(paper)
    session.flush()
    return paper, True


def attach_files(session: Session, paper: Paper, file_field: str):
    paths = split_attachments(file_field)
    if not paths:
        return
    existing = {
        fa.path for fa in session.exec(select(FileAttachment).where(FileAttachment.paper_id == paper.id)).all()
    }
    for path_str in paths:
        if path_str in existing:
            continue
        attachment = FileAttachment(
            paper_id=paper.id,
            path=path_str,
            attachment_type="file",
        )
        session.add(attachment)
        existing.add(path_str)


def ingest_csv(csv_path: Path, limit: Optional[int] = None) -> Dict:
    engine = create_db_engine()
    init_db(engine)
    rows = load_csv_rows(csv_path, limit=limit)
    inserted = 0
    skipped = 0
    non_papers_info: List[Dict] = []
    with Session(engine) as session:
        for row in rows:
            paper, created = upsert_paper(session, row)
            if created:
                inserted += 1
            else:
                skipped += 1
            if not paper.is_paper:
                non_papers_info.append(
                    {
                        "id": paper.id,
                        "key": paper.key,
                        "title": paper.title,
                        "item_type": paper.raw_item_type or paper.item_type,
                    }
                )
            attach_files(session, paper, row.get("File Attachments") or "")
        session.commit()

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_rows": len(rows),
        "non_papers": non_papers_info,
    }
