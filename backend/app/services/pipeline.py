import json
import threading
import uuid
from pathlib import Path
from typing import Dict, Optional

from backend.scripts.process_pdfs import ingest_pdfs
from backend.scripts.summarize_papers import process_papers

JOB_DIR = Path(".pipeline_jobs")
JOB_DIR.mkdir(exist_ok=True)


class JobStatus:
    def __init__(self):
        self.running = True
        self.returncode: Optional[int] = None
        self.log_path: Optional[Path] = None
        self.stats: Dict = {
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

    def update(self, payload: Dict):
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
            ]:
                if key in payload:
                    self.stats[key] = payload[key]


jobs: Dict[str, JobStatus] = {}
summarize_jobs: Dict[str, JobStatus] = {}


def start_process_pdfs(chunk_size: int, overlap: int, limit: Optional[int]) -> str:
    job_id = str(uuid.uuid4())
    log_path = JOB_DIR / f"{job_id}.log"
    status = JobStatus()
    status.set_log(log_path)
    jobs[job_id] = status

    def runner():
        with log_path.open("w", encoding="utf-8") as lf:
            def log_line(msg: str):
                # 防止奇异字符导致写文件报错
                safe = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                lf.write(safe + "\n")
                lf.flush()

            def progress_cb(evt: Dict):
                status.update(evt)
                log_line(json.dumps(evt, ensure_ascii=False))

            try:
                ingest_pdfs(limit_papers=limit, chunk_size=chunk_size, overlap=overlap, progress_cb=progress_cb)
                status.stop(0)
            except Exception as exc:
                log_line(f"error: {exc}")
                status.stop(1)

    threading.Thread(target=runner, daemon=True).start()
    return job_id


def get_job_status(job_id: str) -> Dict:
    status = jobs.get(job_id)
    if not status:
        return {"error": "job not found"}
    log_content = ""
    if status.log_path and status.log_path.exists():
        log_content = status.log_path.read_text()
    return {
        "running": status.running,
        "returncode": status.returncode,
        "log": log_content,
        "stats": status.stats,
        "last_message": status.last_message,
    }


def start_summarize_job(limit: Optional[int], chunk_chars: int, skip_existing: bool, dry_run: bool) -> str:
    job_id = str(uuid.uuid4())
    log_path = JOB_DIR / f"{job_id}.log"
    status = JobStatus()
    status.set_log(log_path)
    stop_flag = threading.Event()
    status.set_stop_event(stop_flag)
    summarize_jobs[job_id] = status

    def runner():
        with log_path.open("w", encoding="utf-8") as lf:
            def log_line(msg: str):
                safe = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                lf.write(safe + "\n")
                lf.flush()

            def progress_cb(evt: Dict):
                status.update(evt)
                log_line(json.dumps(evt, ensure_ascii=False))

            try:
                process_papers(
                    limit=limit,
                    chunk_chars=chunk_chars,
                    skip_existing=skip_existing,
                    dry_run=dry_run,
                    progress_cb=progress_cb,
                    stop_event=stop_flag,
                )
                status.stop(0)
            except Exception as exc:
                log_line(f"error: {exc}")
                status.stop(1)
            summarize_jobs[job_id] = status  # ensure latest stored

    threading.Thread(target=runner, daemon=True).start()
    return job_id


def get_summarize_status(job_id: str) -> Dict:
    status = summarize_jobs.get(job_id)
    if not status:
        return {"error": "job not found"}
    log_content = ""
    if status.log_path and status.log_path.exists():
        log_content = status.log_path.read_text()
    return {
        "running": status.running,
        "returncode": status.returncode,
        "log": log_content,
        "stats": status.stats,
        "last_message": status.last_message,
    }


def stop_summarize_job(job_id: str) -> Dict:
    # Signal the summarize thread to stop and mark the job as stopped.
    status = summarize_jobs.get(job_id)
    if not status:
        return {"error": "job not found"}
    status.signal_stop()
    status.stop(-1)
    return {"status": "stopped"}
