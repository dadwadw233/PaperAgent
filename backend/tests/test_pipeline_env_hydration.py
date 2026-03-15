from backend.app.services import pipeline


class _DummyThread:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def start(self):
        return None


def _patch_job_side_effects(monkeypatch):
    monkeypatch.setattr(pipeline, "_create_job_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.threading, "Thread", _DummyThread)


def test_start_embed_job_hydrates_env_from_config(monkeypatch):
    _patch_job_side_effects(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_load_config_values",
        lambda keys: {
            "EMBED_BASE_URL": "http://embed.local/v1",
            "EMBED_MODEL": "text-embedding-3-large",
            "EMBED_API_KEY": "embed-key",
        },
    )
    monkeypatch.delenv("EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("EMBED_MODEL", raising=False)
    monkeypatch.delenv("EMBED_API_KEY", raising=False)

    job_id = pipeline.start_embed_job(
        limit_chunks=None,
        collection="paper_chunks",
        persist_dir="./chroma_store",
        batch_size=16,
        skip_existing=True,
    )

    assert job_id
    assert pipeline.os.getenv("EMBED_BASE_URL") == "http://embed.local/v1"
    assert pipeline.os.getenv("EMBED_MODEL") == "text-embedding-3-large"
    assert pipeline.os.getenv("EMBED_API_KEY") == "embed-key"
    pipeline.embed_jobs.pop(job_id, None)


def test_start_embed_job_keeps_existing_env(monkeypatch):
    _patch_job_side_effects(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_load_config_values",
        lambda keys: {
            "EMBED_BASE_URL": "http://from-config/v1",
            "EMBED_MODEL": "config-model",
            "EMBED_API_KEY": "config-key",
        },
    )
    monkeypatch.setenv("EMBED_BASE_URL", "http://from-env/v1")
    monkeypatch.setenv("EMBED_MODEL", "env-model")
    monkeypatch.setenv("EMBED_API_KEY", "env-key")

    job_id = pipeline.start_embed_job(
        limit_chunks=None,
        collection="paper_chunks",
        persist_dir="./chroma_store",
        batch_size=16,
        skip_existing=True,
    )

    assert job_id
    assert pipeline.os.getenv("EMBED_BASE_URL") == "http://from-env/v1"
    assert pipeline.os.getenv("EMBED_MODEL") == "env-model"
    assert pipeline.os.getenv("EMBED_API_KEY") == "env-key"
    pipeline.embed_jobs.pop(job_id, None)


def test_start_summarize_job_hydrates_llm_env_from_config(monkeypatch):
    _patch_job_side_effects(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_load_config_values",
        lambda keys: {
            "LLM_BASE_URL": "http://llm.local/v1",
            "LLM_MODEL": "gpt-4.1-mini",
            "LLM_API_KEY": "llm-key",
        },
    )
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    job_id = pipeline.start_summarize_job(
        limit=None,
        chunk_chars=4000,
        skip_existing=True,
        dry_run=False,
    )

    assert job_id
    assert pipeline.os.getenv("LLM_BASE_URL") == "http://llm.local/v1"
    assert pipeline.os.getenv("LLM_MODEL") == "gpt-4.1-mini"
    assert pipeline.os.getenv("LLM_API_KEY") == "llm-key"
    pipeline.summarize_jobs.pop(job_id, None)
