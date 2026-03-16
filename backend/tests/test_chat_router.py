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


def test_chat_stream_returns_sse_final_payload(monkeypatch):
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
        "call_chat_stream",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: iter(["Streamed ", "answer [1]."]),
    )

    client = build_client()
    with client.stream("POST", "/chat", json={"query": "What is the method?", "scope": "library", "stream": True}) as resp:
        assert resp.status_code == 200
        body = "".join(chunk for chunk in resp.iter_text())

    assert "event: delta" in body
    assert "event: final" in body
    assert "Streamed answer [1]." in body


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


def test_sort_and_select_contexts_keeps_pinned_rows():
    contexts = [
        {
            "paper_id": 1,
            "chunk_id": 11,
            "seq": 1,
            "vector_score": 0.01,
            "rerank_score": 0.0,
            "text": "Pinned summary",
            "pinned": True,
        },
        {
            "paper_id": 1,
            "chunk_id": 12,
            "seq": 2,
            "vector_score": 0.9,
            "rerank_score": 0.0,
            "text": "Regular chunk A",
        },
        {
            "paper_id": 1,
            "chunk_id": 13,
            "seq": 3,
            "vector_score": 0.8,
            "rerank_score": 0.0,
            "text": "Regular chunk B",
        },
    ]
    selected = chat_router.sort_and_select_contexts(
        query="limits",
        contexts=contexts,
        final_k=2,
        rerank=False,
        scope="paper",
    )
    chunk_ids = {item.get("chunk_id") for item in selected}
    assert 11 in chunk_ids


def test_chat_enforces_required_terms_for_comparison_query(monkeypatch):
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
                    "paper_id": 21,
                    "chunk_id": 2101,
                    "seq": 1,
                    "distance": 0.1,
                    "vector_score": 0.9,
                    "rerank_score": 0.0,
                    "text": "Context for comparison question.",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "call_chat",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: "Two approaches differ by tradeoff [1].",
    )
    client = build_client()
    resp = client.post(
        "/chat",
        json={
            "query": "Compare two representative approaches and their tradeoffs.",
            "scope": "library",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "tradeoff" in data["answer"].lower()
    assert "performance" in data["answer"].lower()


def test_chat_enforces_required_terms_for_chinese_pros_cons(monkeypatch):
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
                    "paper_id": 22,
                    "chunk_id": 2201,
                    "seq": 1,
                    "distance": 0.1,
                    "vector_score": 0.9,
                    "rerank_score": 0.0,
                    "text": "中文比较上下文",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "call_chat",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: "两类方法各有优势和局限 [1]。",
    )
    client = build_client()
    resp = client.post(
        "/chat",
        json={
            "query": "请比较两类主流方法的优缺点，并给出引用。",
            "scope": "library",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "优缺点" in data["answer"]


def test_chat_enforces_required_terms_for_challenge_evidence_query(monkeypatch):
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
                    "paper_id": 23,
                    "chunk_id": 2301,
                    "seq": 1,
                    "distance": 0.1,
                    "vector_score": 0.9,
                    "rerank_score": 0.0,
                    "text": "中文挑战与证据上下文",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "call_chat",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: "该方向存在多项难点 [1]。",
    )
    client = build_client()
    resp = client.post(
        "/chat",
        json={
            "query": "请总结这个方向的关键挑战，并给出证据。",
            "scope": "library",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "挑战" in data["answer"]
    assert "证据" in data["answer"]


def test_chat_reports_legacy_field_usage_in_retrieval_meta(monkeypatch):
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
                    "paper_id": 99,
                    "chunk_id": 9901,
                    "seq": 1,
                    "distance": 0.1,
                    "vector_score": 0.9,
                    "rerank_score": 0.0,
                    "text": "Legacy compatibility context",
                }
            ],
            "source_collection": "paper_chunks",
            "persist_dir": "./chroma_store",
        },
    )
    monkeypatch.setattr(
        chat_router,
        "call_chat",
        lambda cfg, system_prompt, user_prompt, max_tokens=320, timeout_seconds=8: "Legacy mapping still works [1].",
    )
    client = build_client()
    resp = client.post(
        "/chat",
        json={
            "query": "legacy path check",
            "scope": "library",
            "top_k": 3,
            "max_chunks": 12,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    used = data["retrieval_meta"]["legacy_fields_used"]
    assert "top_k" in used
    assert "max_chunks" in used
    assert data["retrieval_meta"]["legacy_fields_deprecation"] is not None
    assert "2026-06-30" in data["retrieval_meta"]["legacy_fields_deprecation"]
