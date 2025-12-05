from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Paper(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    item_type: Optional[str] = Field(default=None, index=True)
    title: Optional[str] = Field(default=None, index=True)
    authors: Optional[str] = Field(default=None)
    publication_title: Optional[str] = Field(default=None)
    publication_year: Optional[int] = Field(default=None, index=True)
    doi: Optional[str] = Field(default=None, index=True)
    url: Optional[str] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    date: Optional[str] = Field(default=None)
    date_added: Optional[datetime] = Field(default=None)
    date_modified: Optional[datetime] = Field(default=None)
    manual_tags: Optional[str] = Field(default=None)
    automatic_tags: Optional[str] = Field(default=None)
    extra: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    is_paper: bool = Field(default=True, index=True)
    raw_item_type: Optional[str] = Field(default=None)


class FileAttachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: Optional[int] = Field(default=None, foreign_key="paper.id", index=True)
    path: str
    attachment_type: Optional[str] = Field(default=None, index=True)


class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    source_path: Optional[str] = Field(default=None, index=True)
    seq: int = Field(index=True)
    hash: str = Field(index=True)
    content: str
    text_length: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ConfigEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    value: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Summary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    model: Optional[str] = Field(default=None, index=True)
    long_summary: Optional[str] = Field(default=None)
    one_liner: Optional[str] = Field(default=None)
    snarky_comment: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    tag_type: str = Field(index=True)  # e.g., domain/task/keyword
    value: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
