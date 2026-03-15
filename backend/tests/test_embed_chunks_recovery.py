from backend.app.models import Chunk
from backend.scripts import embed_chunks as embed_script


class FakeCollection:
    def __init__(self, broken: bool):
        self.broken = broken
        self.upsert_calls = 0
        self.upserted_ids = []

    def get(self, ids):
        if self.broken:
            raise RuntimeError(
                "Error executing plan: Error sending backfill request to compactor: "
                "Error constructing hnsw segment reader: Error creating hnsw segment reader: "
                "Error loading hnsw index"
            )
        return {"ids": []}

    def upsert(self, ids, embeddings, metadatas, documents):
        if self.broken:
            raise RuntimeError(
                "Error executing plan: Error sending backfill request to compactor: "
                "Error constructing hnsw segment reader: Error creating hnsw segment reader: "
                "Error loading hnsw index"
            )
        self.upsert_calls += 1
        self.upserted_ids.extend(ids)


class FakeClient:
    def __init__(self):
        self._broken = FakeCollection(broken=True)
        self._healthy = FakeCollection(broken=False)
        self.deleted = 0
        self._use_healthy = False

    @property
    def healthy_collection(self):
        return self._healthy

    def get_or_create_collection(self, _name: str):
        return self._healthy if self._use_healthy else self._broken

    def delete_collection(self, _name: str):
        self.deleted += 1
        self._use_healthy = True


def _fake_embed_response(url, headers, payload, timeout, retries):
    return {
        "data": [{"embedding": [0.1, 0.2, 0.3]} for _ in payload["input"]],
    }


def test_embed_chunks_rebuilds_collection_once_on_hnsw_load_error(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(embed_script, "get_chroma_client", lambda persist_directory: fake_client)
    monkeypatch.setattr(embed_script, "post_json_with_retry", _fake_embed_response)

    chunks = [
        Chunk(id=1, paper_id=1, source_path="a.pdf", seq=0, hash="h1", content="alpha", text_length=5),
        Chunk(id=2, paper_id=1, source_path="a.pdf", seq=1, hash="h2", content="beta", text_length=4),
    ]
    inserted = embed_script.embed_chunks(
        collection_name="paper_chunks",
        persist_dir="./chroma_store",
        chunks=chunks,
        cfg={"base_url": "http://localhost:11434/v1", "model": "e", "api_key": "k"},
        batch_size=2,
        skip_existing=True,
    )
    assert fake_client.deleted == 1
    assert inserted == 2
    assert fake_client.healthy_collection.upsert_calls == 1
    assert fake_client.healthy_collection.upserted_ids == ["chunk-1", "chunk-2"]


def test_embed_chunks_hnsw_recovery_only_attempted_once(monkeypatch):
    class AlwaysBrokenClient(FakeClient):
        def get_or_create_collection(self, _name: str):
            return self._broken

        def delete_collection(self, _name: str):
            self.deleted += 1

    broken_client = AlwaysBrokenClient()
    monkeypatch.setattr(embed_script, "get_chroma_client", lambda persist_directory: broken_client)
    monkeypatch.setattr(embed_script, "post_json_with_retry", _fake_embed_response)

    chunks = [Chunk(id=1, paper_id=1, source_path="a.pdf", seq=0, hash="h1", content="alpha", text_length=5)]
    try:
        embed_script.embed_chunks(
            collection_name="paper_chunks",
            persist_dir="./chroma_store",
            chunks=chunks,
            cfg={"base_url": "http://localhost:11434/v1", "model": "e", "api_key": "k"},
            batch_size=1,
            skip_existing=True,
        )
        assert False, "Expected embed_chunks to raise after one failed recovery attempt"
    except RuntimeError as exc:
        assert "Error loading hnsw index" in str(exc)
    assert broken_client.deleted == 1


def test_embed_chunks_partial_run_does_not_rebuild_hnsw(monkeypatch):
    broken_client = FakeClient()
    monkeypatch.setattr(embed_script, "get_chroma_client", lambda persist_directory: broken_client)
    monkeypatch.setattr(embed_script, "post_json_with_retry", _fake_embed_response)

    chunks = [Chunk(id=1, paper_id=1, source_path="a.pdf", seq=0, hash="h1", content="alpha", text_length=5)]
    try:
        embed_script.embed_chunks(
            collection_name="paper_chunks",
            persist_dir="./chroma_store",
            chunks=chunks,
            cfg={"base_url": "http://localhost:11434/v1", "model": "e", "api_key": "k"},
            batch_size=1,
            skip_existing=True,
            allow_hnsw_rebuild=False,
        )
        assert False, "Expected partial run to fail without attempting HNSW rebuild"
    except RuntimeError as exc:
        assert "Auto-rebuild is disabled for partial embedding runs" in str(exc)
    assert broken_client.deleted == 0
