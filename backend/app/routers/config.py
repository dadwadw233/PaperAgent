import os
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.app.db import create_db_engine, get_session
from backend.app.models import ConfigEntry


router = APIRouter(prefix="/config", tags=["config"])


def get_db_session():
    engine = create_db_engine()
    with get_session(engine) as session:
        yield session


# Keys we care about for front-end configuration.
CONFIG_KEYS: List[str] = [
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "EMBED_BASE_URL",
    "EMBED_MODEL",
    "EMBED_API_KEY",
    "EMBED_COLLECTION",
    "CHROMA_PERSIST_DIR",
    "CHROMA_COLLECTION",
]


def read_config(session: Session) -> Dict[str, str]:
    """Return config values (DB overrides env)."""
    rows = session.exec(select(ConfigEntry).where(ConfigEntry.key.in_(CONFIG_KEYS))).all()
    db_map = {row.key: row.value for row in rows if row.value is not None}
    merged: Dict[str, str] = {}
    for key in CONFIG_KEYS:
        merged[key] = db_map.get(key) or os.getenv(key) or ""
    return merged


@router.get("")
def get_config(session: Session = Depends(get_db_session)):
    return {"entries": read_config(session)}


@router.post("")
def upsert_config(payload: Dict[str, str], session: Session = Depends(get_db_session)):
    if not payload:
        raise HTTPException(status_code=400, detail="No config provided")
    for key, value in payload.items():
        if key not in CONFIG_KEYS:
            continue
        existing = session.exec(select(ConfigEntry).where(ConfigEntry.key == key)).first()
        if existing:
            existing.value = value
            session.add(existing)
        else:
            session.add(ConfigEntry(key=key, value=value))
    session.commit()
    return {"status": "ok", "entries": read_config(session)}
