from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import chat as chat_router


def build_client() -> TestClient:
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
    monkeypatch.setattr(chat_router, "call_chat", lambda cfg, system_prompt, user_prompt: "The method is robust [1].")

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

    def fake_call_chat(cfg, system_prompt, user_prompt):
        calls["count"] += 1
        if calls["count"] == 1:
            return "This answer forgot citations."
        return "This answer includes citations [1]."

    monkeypatch.setattr(chat_router, "call_chat", fake_call_chat)
    client = build_client()
    resp = client.post("/chat", json={"query": "Explain this.", "scope": "library"})
    assert resp.status_code == 200
    assert calls["count"] == 2
