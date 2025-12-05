import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from backend.app.db import create_db_engine, get_session
from backend.app.services.importer import ingest_csv


router = APIRouter(prefix="/import", tags=["import"])


def get_db_session():
    engine = create_db_engine()
    with get_session(engine) as session:
        yield session


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(..., description="Zotero 导出的 CSV 文件"),
    limit: Optional[int] = None,
    session: Session = Depends(get_db_session),
):
    # session is injected for future use (e.g., permissions); ingest_csv opens its own engine/session.
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    # Save to temp file then ingest.
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存临时文件失败: {exc}") from exc

    try:
        result = ingest_csv(tmp_path, limit=limit)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "status": "ok",
        "inserted": result["inserted"],
        "skipped": result["skipped"],
        "total_rows": result["total_rows"],
        "non_papers": result["non_papers"],
    }
