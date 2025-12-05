"""
Remove duplicate attachments per paper (same path).
Keeps the first record per (paper_id, path), deletes the rest.
"""

from collections import defaultdict

from sqlmodel import Session, select

from backend.app.db import create_db_engine, init_db
from backend.app.models import FileAttachment


def dedupe():
    engine = create_db_engine()
    init_db(engine)
    to_delete_ids = []
    with Session(engine) as session:
        rows = session.exec(select(FileAttachment).order_by(FileAttachment.paper_id, FileAttachment.id)).all()
        seen = defaultdict(set)  # paper_id -> set(paths)
        for row in rows:
            if row.path in seen[row.paper_id]:
                to_delete_ids.append(row.id)
            else:
                seen[row.paper_id].add(row.path)
        if to_delete_ids:
            for del_id in to_delete_ids:
                obj = session.get(FileAttachment, del_id)
                if obj:
                    session.delete(obj)
            session.commit()
    print({"deleted": len(to_delete_ids)})


if __name__ == "__main__":
    dedupe()
