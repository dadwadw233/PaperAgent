import os
from typing import Dict, List, Optional

import httpx
from chromadb import Client
from chromadb.config import Settings
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from backend.app.db import create_db_engine, get_session
from backend.app.routers.config import read_config


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    paper_id: Optional[int] = None
    top_k: int = 4


def get_db_session():
    engine = create_db_engine()
    with get_session(engine) as session:
        yield session


def get_chroma_client(persist_directory: str) -> Client:
    return Client(Settings(is_persistent=True, persist_directory=persist_directory))


def ensure_embedding_cfg(cfg: Dict[str, str]) -> Dict[str, str]:
    base_url = cfg.get("EMBED_BASE_URL") or cfg.get("LLM_BASE_URL")
    model = cfg.get("EMBED_MODEL") or cfg.get("LLM_MODEL")
    api_key = cfg.get("EMBED_API_KEY") or cfg.get("LLM_API_KEY")
    if not base_url or not model or not api_key:
        raise HTTPException(status_code=400, detail="Missing embedding configuration. Set EMBED_* or LLM_*.")
    return {"base_url": base_url, "model": model, "api_key": api_key}


def embed_texts(texts: List[str], cfg: Dict[str, str]) -> List[List[float]]:
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "input": texts}
    url = cfg["base_url"].rstrip("/") + "/embeddings"
    resp = httpx.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def call_chat(model_cfg: Dict[str, str], system_prompt: str, user_prompt: str) -> str:
    base_url = model_cfg.get("LLM_BASE_URL") or ""
    model = model_cfg.get("LLM_MODEL") or ""
    api_key = model_cfg.get("LLM_API_KEY") or ""
    if not base_url or not model or not api_key:
        raise HTTPException(status_code=400, detail="Missing LLM configuration. Set LLM_BASE_URL/LLM_MODEL/LLM_API_KEY.")
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected LLM response") from None


@router.post("")
def chat(req: ChatRequest, session: Session = Depends(get_db_session)):
    cfg = read_config(session)
    embed_cfg = ensure_embedding_cfg(cfg)
    persist_dir = cfg.get("CHROMA_PERSIST_DIR") or "./chroma_store"
    collection_name = cfg.get("CHROMA_COLLECTION") or "paper_chunks"

    client = get_chroma_client(persist_dir)
    collection = client.get_or_create_collection(collection_name)

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is empty")
    query_vec = embed_texts([req.query], embed_cfg)[0]

    where = {"paper_id": req.paper_id} if req.paper_id else None
    result = collection.query(
        query_embeddings=[query_vec],
        n_results=max(1, min(req.top_k, 10)),
        where=where,
    )
    docs = result.get("documents", [[]])[0] if result else []
    metas = result.get("metadatas", [[]])[0] if result else []
    distances = result.get("distances", [[]])[0] if result else []

    contexts = []
    for doc, meta, dist in zip(docs, metas, distances):
        contexts.append(
            {
                "paper_id": meta.get("paper_id"),
                "chunk_id": meta.get("chunk_id"),
                "seq": meta.get("seq"),
                "score": dist,
                "text": doc,
            }
        )

    context_text = "\n\n".join(
        f"[{idx+1}] (paper {c.get('paper_id')}) {c.get('text')}" for idx, c in enumerate(contexts)
    )
    if not context_text:
        context_text = "No context found. Answer cautiously and say you have no retrieval context."

    system_prompt = (
        "You are a concise research assistant. Use the provided context snippets to answer the user."
        " If the answer is not in context, say you are unsure. Keep responses short (<=120 words)."
    )
    user_prompt = f"User question: {req.query}\n\nContext:\n{context_text}"

    answer = call_chat(cfg, system_prompt, user_prompt)
    return {"answer": answer, "contexts": contexts, "source_collection": collection_name, "persist_dir": persist_dir}
