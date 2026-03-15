from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import chat as chat_router


def build_client() -> TestClient:
    chat_router.VECTOR_BACKEND_DISABLED_UNTIL = 0
    chat_router.VECTOR_BACKEND_DISABLED_REASON = ""
    app = FastAPI()
    app.include_router(chat_router.router)
    return TestClient(app)


def test_chat_scope_paper_requires_paper_id(monkeypatch):
    monkeypatch.setattr(chat_router, "read_config", lambda session: {})
    client = build_client()

    resp = client.post("/chat", json={"query": "What is the method?", "scope": "paper"})
    assert resp.status_code == 400
    assert "paper_id is required" in resp.json()["detail"]


def test_chat_returns_citations_and_retrieval_meta(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "read_config",
        lambda session: {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "local-model",
            "LLM_API_KEY": "dummy",
            "CHROMA_PERSIST_DIR": "./chroma_store",
            "CHROMA_COLLECTION": "paper_chunks",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "ensure_embedding_cfg",
        lambda cfg: {"base_url": "http://localhost:11434/v1", "model": "embed-model", "api_key": "dummy"},
    )
    monkeypatch.setattr(
        chat_router,
        "fetch_embedding_contexts",
        lambda cfg, query, candidate_k, paper_filter_id: {
            "contexts": [
                {
                    "paper_id": 12,
                    "chunk_id": 1001,
                    "seq": 3,
                    "distance": 0.1,
                    "vector_score": 0.91,
                    "rerank_score": 0.0,
                    "text": "This paper introduces a robust retrieval strategy.",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "call_chat",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: "The method is robust [1].",
    )

    client = build_client()
    resp = client.post("/chat", json={"query": "What is the method?", "scope": "library"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert data["citations"]
    assert data["citations"][0]["paper_id"] == 12
    assert data["retrieval_meta"]["scope"] == "library"
    assert data["retrieval_meta"]["final_k_used"] == 1


def test_chat_retries_once_when_citations_missing(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "read_config",
        lambda session: {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "local-model",
            "LLM_API_KEY": "dummy",
            "CHROMA_PERSIST_DIR": "./chroma_store",
            "CHROMA_COLLECTION": "paper_chunks",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "ensure_embedding_cfg",
        lambda cfg: {"base_url": "http://localhost:11434/v1", "model": "embed-model", "api_key": "dummy"},
    )
    monkeypatch.setattr(
        chat_router,
        "fetch_embedding_contexts",
        lambda cfg, query, candidate_k, paper_filter_id: {
            "contexts": [
                {
                    "paper_id": 8,
                    "chunk_id": 99,
                    "seq": 1,
                    "distance": 0.2,
                    "vector_score": 0.8,
                    "rerank_score": 0.0,
                    "text": "Context with enough evidence for a grounded answer.",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    calls = {"count": 0}

    def fake_call_chat(cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8):
        calls["count"] += 1
        if calls["count"] == 1:
            return "This answer forgot citations."
        return "This answer includes citations [1]."

    monkeypatch.setattr(chat_router, "call_chat", fake_call_chat)
    client = build_client()
    resp = client.post("/chat", json={"query": "Explain this.", "scope": "library"})
    assert resp.status_code == 200
    assert calls["count"] == 2


def test_chat_falls_back_to_lexical_when_vector_retrieval_fails(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "read_config",
        lambda session: {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "local-model",
            "LLM_API_KEY": "dummy",
            "CHROMA_PERSIST_DIR": "./chroma_store",
            "CHROMA_COLLECTION": "paper_chunks",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "ensure_embedding_cfg",
        lambda cfg: {"base_url": "http://localhost:11434/v1", "model": "embed-model", "api_key": "dummy"},
    )

    def fail_vector(*args, **kwargs):
        raise RuntimeError("chroma index load failed")

    monkeypatch.setattr(chat_router, "fetch_embedding_contexts", fail_vector)
    monkeypatch.setattr(
        chat_router,
        "fetch_lexical_contexts",
        lambda session, query, candidate_k, paper_filter_id: {
            "contexts": [
                {
                    "paper_id": 42,
                    "chunk_id": 4242,
                    "seq": 2,
                    "distance": None,
                    "vector_score": 0.75,
                    "rerank_score": 0.0,
                    "text": "Fallback lexical context that still supports grounded answers.",
                }
            ],
            "source_collection": "sqlite_chunk_lexical",
            "persist_dir": None,
        },
    )
    monkeypatch.setattr(
        chat_router,
        "call_chat",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: "Fallback answer [1].",
    )

    client = build_client()
    resp = client.post("/chat", json={"query": "What changed?", "scope": "library"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrieval_meta"]["retrieval_backend"] == "lexical_fallback"
    assert "chroma index load failed" in data["retrieval_meta"]["retrieval_fallback_reason"]


def test_chat_repairs_invalid_citations_without_third_llm_retry(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "read_config",
        lambda session: {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "local-model",
            "LLM_API_KEY": "dummy",
            "CHROMA_PERSIST_DIR": "./chroma_store",
            "CHROMA_COLLECTION": "paper_chunks",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "ensure_embedding_cfg",
        lambda cfg: {"base_url": "http://localhost:11434/v1", "model": "embed-model", "api_key": "dummy"},
    )
    monkeypatch.setattr(
        chat_router,
        "fetch_embedding_contexts",
        lambda cfg, query, candidate_k, paper_filter_id: {
            "contexts": [
                {
                    "paper_id": 9,
                    "chunk_id": 901,
                    "seq": 4,
                    "distance": 0.1,
                    "vector_score": 0.91,
                    "rerank_score": 0.0,
                    "text": "Evidence block for citation repair test.",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    calls = {"count": 0}

    def fake_call_chat(cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8):
        calls["count"] += 1
        if calls["count"] == 1:
            return "Bad refs [99]."
        return "Still bad refs [77]."

    monkeypatch.setattr(chat_router, "call_chat", fake_call_chat)
    client = build_client()
    resp = client.post("/chat", json={"query": "Explain this paper.", "scope": "library"})
    assert resp.status_code == 200
    data = resp.json()
    assert "[1]" in data["answer"]
    assert calls["count"] == 2
    assert data["retrieval_meta"]["citation_repair_applied"] is True


def test_chat_uses_fallback_answer_when_llm_times_out(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "read_config",
        lambda session: {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "local-model",
            "LLM_API_KEY": "dummy",
            "CHROMA_PERSIST_DIR": "./chroma_store",
            "CHROMA_COLLECTION": "paper_chunks",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "ensure_embedding_cfg",
        lambda cfg: {"base_url": "http://localhost:11434/v1", "model": "embed-model", "api_key": "dummy"},
    )
    monkeypatch.setattr(
        chat_router,
        "fetch_embedding_contexts",
        lambda cfg, query, candidate_k, paper_filter_id: {
            "contexts": [
                {
                    "paper_id": 10,
                    "chunk_id": 1001,
                    "seq": 1,
                    "distance": 0.1,
                    "vector_score": 0.8,
                    "rerank_score": 0.0,
                    "text": "Fallback should use this context text directly for fast answer generation.",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )

    def fail_llm(*args, **kwargs):
        raise chat_router.HTTPException(status_code=502, detail="LLM request failed (timeout)")

    monkeypatch.setattr(chat_router, "call_chat", fail_llm)
    client = build_client()
    resp = client.post("/chat", json={"query": "Summarize quickly", "scope": "library"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrieval_meta"]["llm_fallback_used"] is True
    assert "[1]" in data["answer"]
