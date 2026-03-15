import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from backend.app.db import create_db_engine
from backend.app.models import JobRun
from backend.scripts.embed_chunks import (
    embed_chunks as embed_chunks_fn,
    fetch_chunks,
    get_embedding_endpoint_config,
)
from backend.scripts.process_pdfs import ingest_pdfs
from backend.scripts.summarize_papers import process_papers

JOB_DIR = Path(".pipeline_jobs")
JOB_DIR.mkdir(exist_ok=True)

JOB_STATUS_RUNNING = "running"
JOB_STATUS_STOPPING = "stopping"
JOB_STATUS_STOPPED = "stopped"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_INTERRUPTED = "interrupted"

JOB_TYPE_PROCESS_PDFS = "process_pdfs"
JOB_TYPE_EMBED_CHUNKS = "embed_chunks"
JOB_TYPE_SUMMARIZE = "summarize"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _json_loads(payload: Optional[str], default: Any) -> Any:
    if not payload:
        return default
    try:
        return json.loads(payload)
    except Exception:
        return default


def _is_running_status(status: str) -> bool:
    return status in {JOB_STATUS_RUNNING, JOB_STATUS_STOPPING}


def _classify_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "timeout" in text:
        return "timeout"
    if "network" in text or "connection" in text:
        return "network_error"
    if "http_status" in text:
        return "upstream_http_error"
    return exc.__class__.__name__


class JobStatus:
    def __init__(self):
        self.running = True
        self.returncode: Optional[int] = None
        self.log_path: Optional[Path] = None
        self.stats: Dict[str, Any] = {
            "processed_papers": 0,
            "processed_pdfs": 0,
            "total_pdfs": 0,
            "papers_with_pdf": 0,
            "total_papers": 0,
            "inserted": 0,
            "skipped": 0,
            "processed": 0,
            "errors": 0,
            "current_paper_id": None,
            "current_paper_title": "",
            "current_pdf": None,
            "embedded": 0,
            "total_chunks": 0,
            "missing_files": 0,
            "embedded_skipped": 0,
        }
        self.last_message: str = ""
        self._lock = threading.Lock()
        self._stop_event: Optional[threading.Event] = None

    def stop(self, code: int):
        with self._lock:
            self.running = False
            self.returncode = code

    def set_log(self, path: Path):
        with self._lock:
            self.log_path = path

    def set_stop_event(self, event: threading.Event):
        with self._lock:
            self._stop_event = event

    def signal_stop(self):
        with self._lock:
            if self._stop_event:
                self._stop_event.set()

    def update(self, payload: Dict[str, Any]):
        with self._lock:
            error = payload.get("error")
            stage = payload.get("stage")
            paper_title = payload.get("paper_title")
            if error:
                self.last_message = f"{stage or 'error'}: {error}"
            elif stage:
                if paper_title:
                    self.last_message = f"{stage} · {paper_title}"
                else:
                    self.last_message = stage
            for key in [
                "processed_papers",
                "processed_pdfs",
                "total_pdfs",
                "total_papers",
                "inserted",
                "skipped",
                "papers_with_pdf",
                "chunks_inserted",
                "chunks_skipped",
                "processed",
                "errors",
                "current_paper_id",
                "current_paper_title",
                "current_pdf",
                "embedded",
                "total_chunks",
                "missing_files",
                "embedded_skipped",
            ]:
                if key in payload:
                    self.stats[key] = payload[key]


jobs: Dict[str, JobStatus] = {}
summarize_jobs: Dict[str, JobStatus] = {}
embed_jobs: Dict[str, JobStatus] = {}


def _create_job_record(
    job_id: str,
    job_type: str,
    params: Dict[str, Any],
    log_path: Path,
    resumed_from_id: Optional[str] = None,
):
    engine = create_db_engine()
    now = _utcnow()
    with Session(engine) as session:
        session.add(
            JobRun(
                id=job_id,
                job_type=job_type,
                status=JOB_STATUS_RUNNING,
                params_json=_json_dumps(params),
                progress_json=_json_dumps({}),
                result_json=None,
                error_type=None,
                error_message=None,
                last_message="starting",
                log_path=str(log_path),
                resumed_from_id=resumed_from_id,
                started_at=now,
                updated_at=now,
                finished_at=None,
            )
        )
        session.commit()


def _update_job_record(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    last_message: Optional[str] = None,
    finished: bool = False,
):
    engine = create_db_engine()
    with Session(engine) as session:
        row = session.get(JobRun, job_id)
        if not row:
            return
        if status is not None:
            row.status = status
        if progress is not None:
            row.progress_json = _json_dumps(progress)
        if result is not None:
            row.result_json = _json_dumps(result)
        if error_type is not None:
            row.error_type = error_type
        if error_message is not None:
            row.error_message = error_message
        if last_message is not None:
            row.last_message = last_message
        row.updated_at = _utcnow()
        if finished:
            row.finished_at = _utcnow()
        session.add(row)
        session.commit()


def _serialize_job(row: JobRun, include_log: bool = True) -> Dict[str, Any]:
    log_content = ""
    if include_log and row.log_path:
        try:
            p = Path(row.log_path)
            if p.exists():
                log_content = p.read_text(encoding="utf-8")
        except Exception:
            log_content = ""

    return {
        "job_id": row.id,
        "job_type": row.job_type,
        "status": row.status,
        "running": _is_running_status(row.status),
        "returncode": None if _is_running_status(row.status) else (0 if row.status == JOB_STATUS_SUCCEEDED else -1),
        "params": _json_loads(row.params_json, {}),
        "stats": _json_loads(row.progress_json, {}),
        "result": _json_loads(row.result_json, None),
        "error_type": row.error_type,
        "error_message": row.error_message,
        "last_message": row.last_message or "",
        "log_path": row.log_path,
        "log": log_content,
        "resumed_from_id": row.resumed_from_id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _fetch_job_row(job_id: str) -> Optional[JobRun]:
    engine = create_db_engine()
    with Session(engine) as session:
        return session.get(JobRun, job_id)


def mark_running_jobs_interrupted():
    engine = create_db_engine()
    with Session(engine) as session:
        rows = session.exec(
            select(JobRun).where(JobRun.status.in_([JOB_STATUS_RUNNING, JOB_STATUS_STOPPING]))
        ).all()
        now = _utcnow()
        for row in rows:
            row.status = JOB_STATUS_INTERRUPTED
            row.error_type = "process_restart"
            row.error_message = "Service restarted while job was running."
            row.last_message = "interrupted by service restart"
            row.updated_at = now
            row.finished_at = now
            session.add(row)
        session.commit()


def _run_process_job(
    job_id: str,
    status: JobStatus,
    stop_flag: threading.Event,
    log_path: Path,
    *,
    chunk_size: int,
    overlap: int,
    limit: Optional[int],
    skip_existing: bool,
):
    with log_path.open("w", encoding="utf-8") as lf:
        def log_line(msg: str):
            safe = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            lf.write(safe + "\n")
            lf.flush()

        def progress_cb(evt: Dict[str, Any]):
            status.update(evt)
            log_line(_json_dumps(evt))
            _update_job_record(
                job_id,
                status=JOB_STATUS_RUNNING,
                progress=status.stats,
                last_message=status.last_message,
            )

        try:
            ingest_pdfs(
                limit_papers=limit,
                chunk_size=chunk_size,
                overlap=overlap,
                progress_cb=progress_cb,
                stop_event=stop_flag,
                skip_existing=skip_existing,
            )
            if stop_flag.is_set() or status.returncode == -1:
                status.stop(-1)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_STOPPED,
                    progress=status.stats,
                    result={"stopped": True},
                    last_message=status.last_message or "stopped",
                    finished=True,
                )
            else:
                status.stop(0)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_SUCCEEDED,
                    progress=status.stats,
                    result={"finished": True},
                    last_message=status.last_message or "finished",
                    finished=True,
                )
        except Exception as exc:
            err_type = _classify_error(exc)
            log_line(f"error[{err_type}]: {exc}")
            status.stop(-1)
            final_status = JOB_STATUS_STOPPED if stop_flag.is_set() else JOB_STATUS_FAILED
            _update_job_record(
                job_id,
                status=final_status,
                progress=status.stats,
                error_type=err_type,
                error_message=str(exc),
                last_message=f"{err_type}: {exc}",
                finished=True,
            )


def _run_summarize_job(
    job_id: str,
    status: JobStatus,
    stop_flag: threading.Event,
    log_path: Path,
    *,
    limit: Optional[int],
    chunk_chars: int,
    skip_existing: bool,
    dry_run: bool,
):
    with log_path.open("w", encoding="utf-8") as lf:
        def log_line(msg: str):
            safe = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            lf.write(safe + "\n")
            lf.flush()

        def progress_cb(evt: Dict[str, Any]):
            status.update(evt)
            log_line(_json_dumps(evt))
            _update_job_record(
                job_id,
                status=JOB_STATUS_RUNNING,
                progress=status.stats,
                last_message=status.last_message,
            )

        try:
            process_papers(
                limit=limit,
                chunk_chars=chunk_chars,
                skip_existing=skip_existing,
                dry_run=dry_run,
                progress_cb=progress_cb,
                stop_event=stop_flag,
            )
            if stop_flag.is_set() or status.returncode == -1:
                status.stop(-1)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_STOPPED,
                    progress=status.stats,
                    result={"stopped": True},
                    last_message=status.last_message or "stopped",
                    finished=True,
                )
            else:
                status.stop(0)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_SUCCEEDED,
                    progress=status.stats,
                    result={"finished": True},
                    last_message=status.last_message or "finished",
                    finished=True,
                )
        except Exception as exc:
            err_type = _classify_error(exc)
            log_line(f"error[{err_type}]: {exc}")
            status.stop(-1)
            final_status = JOB_STATUS_STOPPED if stop_flag.is_set() else JOB_STATUS_FAILED
            _update_job_record(
                job_id,
                status=final_status,
                progress=status.stats,
                error_type=err_type,
                error_message=str(exc),
                last_message=f"{err_type}: {exc}",
                finished=True,
            )


def _run_embed_job(
    job_id: str,
    status: JobStatus,
    stop_flag: threading.Event,
    log_path: Path,
    *,
    limit_chunks: Optional[int],
    collection: str,
    persist_dir: str,
    batch_size: int,
    skip_existing: bool,
):
    with log_path.open("w", encoding="utf-8") as lf:
        def log_line(msg: str):
            safe = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            lf.write(safe + "\n")
            lf.flush()

        def progress_cb(evt: Dict[str, Any]):
            status.update(evt)
            log_line(_json_dumps(evt))
            _update_job_record(
                job_id,
                status=JOB_STATUS_RUNNING,
                progress=status.stats,
                last_message=status.last_message,
            )

        try:
            cfg = get_embedding_endpoint_config()
            engine = create_db_engine()
            with Session(engine) as session:
                chunks = fetch_chunks(session, limit=limit_chunks)
            total = len(chunks)
            status.update({"stage": "starting", "total_chunks": total, "embedded": 0, "embedded_skipped": 0})
            _update_job_record(
                job_id,
                status=JOB_STATUS_RUNNING,
                progress=status.stats,
                last_message=status.last_message,
            )
            if total == 0:
                status.stop(0)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_SUCCEEDED,
                    progress=status.stats,
                    result={"finished": True, "embedded": 0},
                    last_message="no chunks",
                    finished=True,
                )
                return
            embed_chunks_fn(
                collection_name=collection,
                persist_dir=persist_dir,
                chunks=chunks,
                cfg=cfg,
                batch_size=batch_size,
                progress_cb=progress_cb,
                skip_existing=skip_existing,
                stop_event=stop_flag,
            )
            if stop_flag.is_set() or status.returncode == -1:
                status.stop(-1)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_STOPPED,
                    progress=status.stats,
                    result={"stopped": True},
                    last_message=status.last_message or "stopped",
                    finished=True,
                )
            else:
                status.stop(0)
                _update_job_record(
                    job_id,
                    status=JOB_STATUS_SUCCEEDED,
                    progress=status.stats,
                    result={"finished": True, "embedded": status.stats.get("embedded", 0)},
                    last_message=status.last_message or "finished",
                    finished=True,
                )
        except Exception as exc:
            err_type = _classify_error(exc)
            log_line(f"error[{err_type}]: {exc}")
            status.stop(-1)
            final_status = JOB_STATUS_STOPPED if stop_flag.is_set() else JOB_STATUS_FAILED
            _update_job_record(
                job_id,
                status=final_status,
                progress=status.stats,
                error_type=err_type,
                error_message=str(exc),
                last_message=f"{err_type}: {exc}",
                finished=True,
            )


def start_process_pdfs(
    chunk_size: int,
    overlap: int,
    limit: Optional[int],
    skip_existing: bool = True,
    resumed_from_id: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    log_path = JOB_DIR / f"{job_id}.log"
    status = JobStatus()
    status.set_log(log_path)
    stop_flag = threading.Event()
    status.set_stop_event(stop_flag)
    jobs[job_id] = status
    _create_job_record(
        job_id,
        JOB_TYPE_PROCESS_PDFS,
        {
            "chunk_size": chunk_size,
            "overlap": overlap,
            "limit": limit,
            "skip_existing": skip_existing,
        },
        log_path=log_path,
        resumed_from_id=resumed_from_id,
    )
    threading.Thread(
        target=_run_process_job,
        kwargs={
            "job_id": job_id,
            "status": status,
            "stop_flag": stop_flag,
            "log_path": log_path,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "limit": limit,
            "skip_existing": skip_existing,
        },
        daemon=True,
    ).start()
    return job_id


def start_summarize_job(
    limit: Optional[int],
    chunk_chars: int,
    skip_existing: bool,
    dry_run: bool,
    resumed_from_id: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    log_path = JOB_DIR / f"{job_id}.log"
    status = JobStatus()
    status.set_log(log_path)
    stop_flag = threading.Event()
    status.set_stop_event(stop_flag)
    summarize_jobs[job_id] = status
    _create_job_record(
        job_id,
        JOB_TYPE_SUMMARIZE,
        {
            "limit": limit,
            "chunk_chars": chunk_chars,
            "skip_existing": skip_existing,
            "dry_run": dry_run,
        },
        log_path=log_path,
        resumed_from_id=resumed_from_id,
    )
    threading.Thread(
        target=_run_summarize_job,
        kwargs={
            "job_id": job_id,
            "status": status,
            "stop_flag": stop_flag,
            "log_path": log_path,
            "limit": limit,
            "chunk_chars": chunk_chars,
            "skip_existing": skip_existing,
            "dry_run": dry_run,
        },
        daemon=True,
    ).start()
    return job_id


def start_embed_job(
    limit_chunks: Optional[int],
    collection: str,
    persist_dir: str,
    batch_size: int,
    skip_existing: bool = True,
    resumed_from_id: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    log_path = JOB_DIR / f"{job_id}.log"
    status = JobStatus()
    status.set_log(log_path)
    stop_flag = threading.Event()
    status.set_stop_event(stop_flag)
    embed_jobs[job_id] = status
    _create_job_record(
        job_id,
        JOB_TYPE_EMBED_CHUNKS,
        {
            "limit_chunks": limit_chunks,
            "collection": collection,
            "persist_dir": persist_dir,
            "batch_size": batch_size,
            "skip_existing": skip_existing,
        },
        log_path=log_path,
        resumed_from_id=resumed_from_id,
    )
    threading.Thread(
        target=_run_embed_job,
        kwargs={
            "job_id": job_id,
            "status": status,
            "stop_flag": stop_flag,
            "log_path": log_path,
            "limit_chunks": limit_chunks,
            "collection": collection,
            "persist_dir": persist_dir,
            "batch_size": batch_size,
            "skip_existing": skip_existing,
        },
        daemon=True,
    ).start()
    return job_id


def get_job_status(job_id: str) -> Dict[str, Any]:
    row = _fetch_job_row(job_id)
    if not row:
        return {"error": "job not found"}
    return _serialize_job(row, include_log=True)


def get_summarize_status(job_id: str) -> Dict[str, Any]:
    return get_job_status(job_id)


def get_embed_status(job_id: str) -> Dict[str, Any]:
    return get_job_status(job_id)


def _stop_runtime_job(job_id: str, runtime_map: Dict[str, JobStatus]) -> Dict[str, str]:
    row = _fetch_job_row(job_id)
    if not row:
        return {"error": "job not found"}
    if row.status in {JOB_STATUS_SUCCEEDED, JOB_STATUS_FAILED, JOB_STATUS_INTERRUPTED, JOB_STATUS_STOPPED}:
        return {"status": row.status}
    runtime = runtime_map.get(job_id)
    if runtime:
        runtime.signal_stop()
        runtime.stop(-1)
    _update_job_record(
        job_id,
        status=JOB_STATUS_STOPPED,
        progress=runtime.stats if runtime else _json_loads(row.progress_json, {}),
        error_type="user_stop",
        error_message="Stopped by user request.",
        last_message="stopped by user",
        finished=True,
    )
    return {"status": "stopped"}


def stop_summarize_job(job_id: str) -> Dict[str, str]:
    return _stop_runtime_job(job_id, summarize_jobs)


def stop_process_pdfs_job(job_id: str) -> Dict[str, str]:
    return _stop_runtime_job(job_id, jobs)


def stop_embed_job(job_id: str) -> Dict[str, str]:
    return _stop_runtime_job(job_id, embed_jobs)


def list_pipeline_jobs(limit: int = 50, job_type: Optional[str] = None) -> List[Dict[str, Any]]:
    engine = create_db_engine()
    with Session(engine) as session:
        if job_type:
            stmt = select(JobRun).where(JobRun.job_type == job_type).order_by(JobRun.updated_at.desc()).limit(limit)
        else:
            stmt = select(JobRun).order_by(JobRun.updated_at.desc()).limit(limit)
        rows = session.exec(stmt).all()
        return [_serialize_job(row, include_log=False) for row in rows]


def get_pipeline_job(job_id: str) -> Optional[Dict[str, Any]]:
    row = _fetch_job_row(job_id)
    if not row:
        return None
    return _serialize_job(row, include_log=True)


def resume_pipeline_job(job_id: str) -> Dict[str, Any]:
    row = _fetch_job_row(job_id)
    if not row:
        return {"error": "job not found"}
    if row.status not in {JOB_STATUS_INTERRUPTED, JOB_STATUS_FAILED, JOB_STATUS_STOPPED}:
        return {"error": f"job cannot be resumed from status={row.status}"}

    params = _json_loads(row.params_json, {})
    if row.job_type == JOB_TYPE_PROCESS_PDFS:
        new_id = start_process_pdfs(
            chunk_size=int(params.get("chunk_size", 1200)),
            overlap=int(params.get("overlap", 200)),
            limit=params.get("limit"),
            skip_existing=True,
            resumed_from_id=job_id,
        )
    elif row.job_type == JOB_TYPE_EMBED_CHUNKS:
        new_id = start_embed_job(
            limit_chunks=params.get("limit_chunks"),
            collection=str(params.get("collection", "paper_chunks")),
            persist_dir=str(params.get("persist_dir", "./chroma_store")),
            batch_size=int(params.get("batch_size", 16)),
            skip_existing=True,
            resumed_from_id=job_id,
        )
    elif row.job_type == JOB_TYPE_SUMMARIZE:
        new_id = start_summarize_job(
            limit=params.get("limit"),
            chunk_chars=int(params.get("chunk_chars", 4000)),
            skip_existing=True,
            dry_run=bool(params.get("dry_run", False)),
            resumed_from_id=job_id,
        )
    else:
        return {"error": f"unknown job type: {row.job_type}"}
    return {"job_id": new_id}
