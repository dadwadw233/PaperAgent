import argparse
import json
import os
from typing import Any, Dict, List, Optional

import httpx
from chromadb import Client
from chromadb.config import Settings
from sqlmodel import Session, select

from backend.app.db import create_db_engine, init_db
from backend.app.models import Chunk, Paper


def get_chroma_client(persist_directory: str) -> Client:
    return Client(Settings(is_persistent=True, persist_directory=persist_directory))


def get_embedding_endpoint_config() -> Dict[str, str]:
    base_url = os.getenv("EMBED_BASE_URL") or os.getenv("LLM_BASE_URL")
    model = os.getenv("EMBED_MODEL") or os.getenv("LLM_MODEL")
    api_key = os.getenv("EMBED_API_KEY") or os.getenv("LLM_API_KEY")
    if not base_url or not model or not api_key:
        raise RuntimeError("Missing embedding configuration (EMBED_BASE_URL/EMBED_MODEL/EMBED_API_KEY).")
    return {"base_url": base_url, "model": model, "api_key": api_key}


def embed_chunks(
    collection_name: str,
    persist_dir: str,
    chunks: List[Chunk],
    cfg: Dict[str, str],
    batch_size: int = 16,
    progress_cb=None,
    skip_existing: bool = True,
    stop_event=None,
) -> int:
    client = get_chroma_client(persist_dir)
    collection = client.get_or_create_collection(collection_name)
    inserted = 0
    skipped = 0
    effective_total = len(chunks)

    def embed_texts(texts: List[str]) -> List[List[float]]:
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
        payload = {"model": cfg["model"], "input": texts}
        url = cfg["base_url"].rstrip("/") + "/embeddings"
        resp = httpx.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # Expect OpenAI-style response: {"data": [{"embedding": [...]}]}
        return [item["embedding"] for item in data["data"]]

    total = len(chunks)
    for start in range(0, total, batch_size):
        if stop_event and stop_event.is_set():
            break
        batch = chunks[start : start + batch_size]
        texts = [c.content for c in batch]
        ids = [f"chunk-{c.id}" for c in batch]
        if skip_existing:
            existing = collection.get(ids=ids)
            existing_ids = set(existing.get("ids", [])) if existing else set()
            if existing_ids:
                filtered = [(c, t, i) for c, t, i in zip(batch, texts, ids) if i not in existing_ids]
                skipped_now = len(batch) - len(filtered)
                skipped += skipped_now
                effective_total -= skipped_now
                batch = [c for c, _, _ in filtered]
                texts = [t for _, t, _ in filtered]
                ids = [i for _, _, i in filtered]
        if not batch:
            if progress_cb:
                progress_cb(
                    {
                        "stage": "embedding",
                        "embedded": inserted,
                        "total_chunks": max(effective_total, 0),
                        "embedded_skipped": skipped,
                        "batch": 0,
                        "last_chunk_id": None,
                    }
                )
            continue
        embeddings = embed_texts(texts)
        metadatas = [
            {
                "paper_id": c.paper_id,
                "chunk_id": c.id,
                "source_path": c.source_path,
                "seq": c.seq,
            }
            for c in batch
        ]
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        inserted += len(batch)
        if progress_cb:
            progress_cb(
                {
                    "stage": "embedding",
                    "embedded": inserted,
                    "embedded_skipped": skipped,
                    "total_chunks": max(effective_total, 0),
                    "batch": len(batch),
                    "last_chunk_id": batch[-1].id if batch else None,
                }
            )
    return inserted


def fetch_chunks(session: Session, limit: Optional[int] = None) -> List[Chunk]:
    stmt = select(Chunk).order_by(Chunk.id)
    if limit:
        stmt = stmt.limit(limit)
    return session.exec(stmt).all()


def main():
    parser = argparse.ArgumentParser(description="Embed chunks into Chroma vector store.")
    parser.add_argument("--limit-chunks", type=int, default=None, help="Limit number of chunks for a dry run.")
    parser.add_argument(
        "--persist-dir",
        type=str,
        default="./chroma_store",
        help="Chroma persistence directory.",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="paper_chunks",
        help="Chroma collection name.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    engine = create_db_engine()
    init_db(engine)
    cfg = get_embedding_endpoint_config()

    with Session(engine) as session:
        chunks = fetch_chunks(session, limit=args.limit_chunks)
    if not chunks:
        print("No chunks found. Run process_pdfs first.")
        return
    inserted = embed_chunks(
        collection_name=args.collection,
        persist_dir=args.persist_dir,
        chunks=chunks,
        cfg=cfg,
        batch_size=args.batch_size,
    )
    print(json.dumps({"embedded": inserted, "collection": args.collection, "persist_dir": args.persist_dir}))


if __name__ == "__main__":
    main()
