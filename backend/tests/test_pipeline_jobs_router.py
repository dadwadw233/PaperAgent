from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import pipeline as pipeline_router


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(pipeline_router.router)
    return TestClient(app)


def test_pipeline_jobs_list(monkeypatch):
    monkeypatch.setattr(
        pipeline_router,
        "list_pipeline_jobs",
        lambda limit=50, job_type=None: [
            {
                "job_id": "job-1",
                "job_type": "embed_chunks",
                "status": "failed",
                "running": False,
                "returncode": -1,
                "params": {},
                "stats": {},
            }
        ],
    )
    client = build_client()
    resp = client.get("/pipeline/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["job_id"] == "job-1"


def test_pipeline_job_resume_success(monkeypatch):
    monkeypatch.setattr(pipeline_router, "resume_pipeline_job", lambda job_id: {"job_id": "new-job-id"})
    client = build_client()
    resp = client.post("/pipeline/jobs/old-job-id/resume")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == "new-job-id"


def test_pipeline_job_resume_error(monkeypatch):
    monkeypatch.setattr(pipeline_router, "resume_pipeline_job", lambda job_id: {"error": "job not found"})
    client = build_client()
    resp = client.post("/pipeline/jobs/unknown/resume")
    assert resp.status_code == 400
    assert "job not found" in resp.json()["detail"]
