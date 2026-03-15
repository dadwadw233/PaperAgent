import re
import time
from typing import Any, Dict, List, Optional

from chromadb import Client
from chromadb.config import Settings
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Session, select

from backend.app.db import create_db_engine, get_session
from backend.app.models import Chunk
from backend.app.routers.config import read_config
from backend.app.services.http_client import ExternalServiceError, post_json_with_retry


router = APIRouter(prefix="/chat", tags=["chat"])

CITATION_PATTERN = re.compile(r"\[(\d+)\]")


class ChatRequest(BaseModel):
    query: str
    scope: str = "library"  # library|paper
    paper_id: Optional[int] = None
    candidate_k: int = 20
    final_k: int = 6
    rerank: bool = True
    require_citations: bool = True
    # Legacy fields (kept for one release cycle)
    top_k: Optional[int] = None
    use_embeddings: Optional[bool] = None
    send_full_text: Optional[bool] = None
    max_chunks: Optional[int] = None


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
    try:
        data = post_json_with_retry(url, headers=headers, payload=payload, timeout=60, retries=2)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding request failed ({exc.category}): {exc.message}") from exc
    return [item["embedding"] for item in data.get("data", [])]


def build_context_from_chunks(
    session: Session,
    paper_id: int,
    max_chars: int = 12000,
    max_chunks: int = 10,
) -> List[Dict[str, Any]]:
    stmt = (
        select(Chunk)
        .where(Chunk.paper_id == paper_id)
        .order_by(Chunk.seq)
        .limit(max_chunks * 3)
    )
    rows: List[Chunk] = session.exec(stmt).all()
    contexts: List[Dict[str, Any]] = []
    total_chars = 0
    for row in rows:
        if total_chars >= max_chars or len(contexts) >= max_chunks:
            break
        if not row.content:
            continue
        contexts.append(
            {
                "paper_id": row.paper_id,
                "chunk_id": row.id,
                "seq": row.seq,
                "distance": None,
                "vector_score": 0.0,
                "rerank_score": 0.0,
                "text": row.content,
            }
        )
        total_chars += len(row.content)
    return contexts


def normalize_chat_options(req: ChatRequest) -> Dict[str, Any]:
    scope = (req.scope or "library").strip().lower()
    if scope not in {"library", "paper"}:
        scope = "library"
    final_k = max(1, min(req.final_k, 20))
    if req.top_k is not None and req.final_k == 6:
        final_k = max(1, min(req.top_k, 20))
    if req.max_chunks is not None and req.final_k == 6:
        final_k = max(1, min(req.max_chunks, 50))
    candidate_k = max(final_k, min(req.candidate_k, 100))
    rerank = bool(req.rerank)
    require_citations = bool(req.require_citations)
    legacy_direct_mode = False

    if req.use_embeddings is False:
        # Keep compatibility for one version cycle.
        legacy_direct_mode = True
        scope = "paper"
        rerank = False
    if req.send_full_text:
        legacy_direct_mode = True
        scope = "paper"
        rerank = False
        final_k = max(final_k, req.max_chunks or 50)
        candidate_k = max(candidate_k, final_k)

    if scope == "paper" and not req.paper_id:
        raise HTTPException(status_code=400, detail="paper_id is required when scope=paper")

    return {
        "scope": scope,
        "paper_id": req.paper_id,
        "candidate_k": candidate_k,
        "final_k": final_k,
        "rerank": rerank,
        "require_citations": require_citations,
        "legacy_direct_mode": legacy_direct_mode,
    }


def tokenize_for_rerank(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", (text or "").lower())


def local_rerank_score(query: str, text: str) -> float:
    q_tokens = tokenize_for_rerank(query)
    if not q_tokens:
        return 0.0
    q_set = set(q_tokens)
    d_tokens = tokenize_for_rerank(text)
    if not d_tokens:
        return 0.0
    overlap = q_set.intersection(d_tokens)
    coverage = len(overlap) / max(len(q_set), 1)
    density = sum(d_tokens.count(token) for token in q_set) / max(len(d_tokens), 1)
    return (coverage * 0.75) + (density * 0.25)


def fetch_embedding_contexts(
    cfg: Dict[str, str],
    query: str,
    candidate_k: int,
    paper_filter_id: Optional[int],
) -> Dict[str, Any]:
    persist_dir = cfg.get("CHROMA_PERSIST_DIR") or "./chroma_store"
    collection_name = cfg.get("CHROMA_COLLECTION") or "paper_chunks"
    client = get_chroma_client(persist_dir)
    collection = client.get_or_create_collection(collection_name)
    query_vec = embed_texts([query], cfg)[0]
    where = {"paper_id": paper_filter_id} if paper_filter_id else None
    result = collection.query(
        query_embeddings=[query_vec],
        n_results=candidate_k,
        where=where,
    )
    docs = result.get("documents", [[]])[0] if result else []
    metas = result.get("metadatas", [[]])[0] if result else []
    distances = result.get("distances", [[]])[0] if result else []

    contexts: List[Dict[str, Any]] = []
    for doc, meta, dist in zip(docs, metas, distances):
        vector_score = 1.0 / (1.0 + float(dist)) if dist is not None else 0.0
        contexts.append(
            {
                "paper_id": meta.get("paper_id"),
                "chunk_id": meta.get("chunk_id"),
                "seq": meta.get("seq"),
                "distance": dist,
                "vector_score": vector_score,
                "rerank_score": 0.0,
                "text": doc,
            }
        )

    return {
        "contexts": contexts,
        "persist_dir": persist_dir,
        "source_collection": collection_name,
    }


def fetch_lexical_contexts(
    session: Session,
    query: str,
    candidate_k: int,
    paper_filter_id: Optional[int],
) -> Dict[str, Any]:
    tokens = [token for token in tokenize_for_rerank(query) if len(token) >= 2][:8]
    scan_limit = max(candidate_k * 25, 200)
    stmt = select(Chunk)
    if paper_filter_id:
        stmt = stmt.where(Chunk.paper_id == paper_filter_id)
    if tokens:
        stmt = stmt.where(or_(*[Chunk.content.contains(token) for token in tokens]))
    stmt = stmt.order_by(Chunk.created_at.desc()).limit(scan_limit)
    rows: List[Chunk] = session.exec(stmt).all()

    contexts: List[Dict[str, Any]] = []
    for row in rows:
        text = row.content or ""
        if not text.strip():
            continue
        lexical_score = local_rerank_score(query, text)
        if tokens and lexical_score <= 0:
            continue
        contexts.append(
            {
                "paper_id": row.paper_id,
                "chunk_id": row.id,
                "seq": row.seq,
                "distance": None,
                "vector_score": lexical_score,
                "rerank_score": 0.0,
                "text": text,
            }
        )

    if not contexts:
        fallback_stmt = select(Chunk)
        if paper_filter_id:
            fallback_stmt = fallback_stmt.where(Chunk.paper_id == paper_filter_id)
        fallback_stmt = fallback_stmt.order_by(Chunk.created_at.desc()).limit(candidate_k)
        for row in session.exec(fallback_stmt).all():
            if not (row.content or "").strip():
                continue
            contexts.append(
                {
                    "paper_id": row.paper_id,
                    "chunk_id": row.id,
                    "seq": row.seq,
                    "distance": None,
                    "vector_score": 0.0,
                    "rerank_score": 0.0,
                    "text": row.content,
                }
            )

    contexts.sort(key=lambda item: item.get("vector_score", 0.0), reverse=True)
    return {
        "contexts": contexts[:candidate_k],
        "persist_dir": None,
        "source_collection": "sqlite_chunk_lexical",
    }


def sort_and_select_contexts(
    query: str,
    contexts: List[Dict[str, Any]],
    final_k: int,
    rerank: bool,
    scope: str,
) -> List[Dict[str, Any]]:
    if rerank:
        for row in contexts:
            row["rerank_score"] = local_rerank_score(query, row.get("text") or "")
        contexts.sort(
            key=lambda item: (item.get("rerank_score", 0.0), item.get("vector_score", 0.0)),
            reverse=True,
        )
    else:
        contexts.sort(key=lambda item: item.get("vector_score", 0.0), reverse=True)

    per_paper_cap = final_k if scope == "paper" else 3
    paper_counts: Dict[str, int] = {}
    selected: List[Dict[str, Any]] = []
    for row in contexts:
        paper_key = str(row.get("paper_id") or "unknown")
        if paper_counts.get(paper_key, 0) >= per_paper_cap:
            continue
        selected.append(row)
        paper_counts[paper_key] = paper_counts.get(paper_key, 0) + 1
        if len(selected) >= final_k:
            break
    return selected


def apply_context_budget(contexts: List[Dict[str, Any]], char_budget: int = 12000) -> List[Dict[str, Any]]:
    total = 0
    trimmed: List[Dict[str, Any]] = []
    for row in contexts:
        if total >= char_budget:
            break
        text = row.get("text") or ""
        remain = char_budget - total
        if len(text) > remain:
            text = text[:remain]
        if not text.strip():
            continue
        item = dict(row)
        item["text"] = text
        trimmed.append(item)
        total += len(text)
    return trimmed


def build_citations(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    for idx, row in enumerate(contexts, start=1):
        citations.append(
            {
                "index": idx,
                "paper_id": row.get("paper_id"),
                "chunk_id": row.get("chunk_id"),
                "seq": row.get("seq"),
                "snippet": (row.get("text") or "")[:260],
                "score": {
                    "vector": row.get("vector_score"),
                    "rerank": row.get("rerank_score"),
                },
            }
        )
    return citations


def citations_are_valid(answer: str, citation_count: int) -> bool:
    refs = {int(item) for item in CITATION_PATTERN.findall(answer or "")}
    if not refs:
        return False
    return min(refs) >= 1 and max(refs) <= citation_count


def call_chat(model_cfg: Dict[str, str], system_prompt: str, user_prompt: str) -> str:
    base_url = model_cfg.get("LLM_BASE_URL") or ""
    model = model_cfg.get("LLM_MODEL") or ""
    api_key = model_cfg.get("LLM_API_KEY") or ""
    if not base_url or not model or not api_key:
        raise HTTPException(
            status_code=400,
            detail="Missing LLM configuration. Set LLM_BASE_URL/LLM_MODEL/LLM_API_KEY.",
        )
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    try:
        data = post_json_with_retry(url, headers=headers, payload=payload, timeout=120, retries=2)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed ({exc.category}): {exc.message}") from exc
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected LLM response") from None


@router.post("")
def chat(req: ChatRequest, session: Session = Depends(get_db_session)):
    started = time.perf_counter()
    cfg = read_config(session)
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is empty")

    opts = normalize_chat_options(req)
    retrieval_started = time.perf_counter()
    contexts: List[Dict[str, Any]] = []
    source_collection = None
    persist_dir = None
    retrieval_backend = "direct_chunks" if opts["legacy_direct_mode"] else "vector"
    retrieval_fallback_reason: Optional[str] = None

    if opts["legacy_direct_mode"]:
        contexts = build_context_from_chunks(
            session=session,
            paper_id=opts["paper_id"],
            max_chars=16000,
            max_chunks=opts["final_k"],
        )
    else:
        try:
            embed_cfg = ensure_embedding_cfg(cfg)
            search_result = fetch_embedding_contexts(
                cfg={**cfg, **embed_cfg},
                query=req.query,
                candidate_k=opts["candidate_k"],
                paper_filter_id=opts["paper_id"],
            )
        except Exception as exc:
            search_result = fetch_lexical_contexts(
                session=session,
                query=req.query,
                candidate_k=opts["candidate_k"],
                paper_filter_id=opts["paper_id"],
            )
            retrieval_backend = "lexical_fallback"
            retrieval_fallback_reason = str(exc)[:220]
        contexts = search_result["contexts"]
        source_collection = search_result["source_collection"]
        persist_dir = search_result["persist_dir"]

    contexts = sort_and_select_contexts(
        query=req.query,
        contexts=contexts,
        final_k=opts["final_k"],
        rerank=opts["rerank"] and not opts["legacy_direct_mode"],
        scope=opts["scope"],
    )
    contexts = apply_context_budget(contexts, char_budget=12000)
    citations = build_citations(contexts)
    retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

    context_text = "\n\n".join(
        f"[{idx}] (paper {c.get('paper_id')} chunk {c.get('chunk_id')} seq {c.get('seq')})\n{c.get('text')}"
        for idx, c in enumerate(contexts, start=1)
    )
    if not context_text:
        context_text = "No retrieval context available."

    base_system_prompt = (
        "You are a grounded research assistant. "
        "Answer using only the provided context. "
        "If context is insufficient, explicitly say you are unsure. "
        "Cite every important claim using [n] where n is a context index."
    )
    strict_system_prompt = (
        base_system_prompt
        + " Citation is mandatory: every paragraph must include at least one valid [n] citation."
    )
    user_prompt = (
        f"Question: {req.query}\n\n"
        "Context snippets:\n"
        f"{context_text}\n\n"
        "Return a concise answer with explicit inline citations."
    )

    generation_started = time.perf_counter()
    answer = call_chat(cfg, base_system_prompt, user_prompt)
    require_citations = opts["require_citations"] and len(citations) > 0
    if require_citations and not citations_are_valid(answer, len(citations)):
        answer = call_chat(cfg, strict_system_prompt, user_prompt)
    if require_citations and not citations_are_valid(answer, len(citations)):
        raise HTTPException(
            status_code=502,
            detail="LLM did not produce valid citations after retry.",
        )
    generation_ms = int((time.perf_counter() - generation_started) * 1000)
    total_ms = int((time.perf_counter() - started) * 1000)

    retrieval_meta = {
        "scope": opts["scope"],
        "paper_filter": opts["paper_id"],
        "candidate_k": opts["candidate_k"],
        "final_k_requested": opts["final_k"],
        "final_k_used": len(contexts),
        "rerank_enabled": opts["rerank"] and not opts["legacy_direct_mode"],
        "retrieval_backend": retrieval_backend,
        "retrieval_fallback_reason": retrieval_fallback_reason,
        "legacy_direct_mode": opts["legacy_direct_mode"],
        "context_char_budget": 12000,
        "timings_ms": {
            "retrieval": retrieval_ms,
            "generation": generation_ms,
            "total": total_ms,
        },
    }

    return {
        "answer": answer,
        "contexts": contexts,
        "citations": citations,
        "retrieval_meta": retrieval_meta,
        "source_collection": source_collection,
        "persist_dir": persist_dir,
    }
