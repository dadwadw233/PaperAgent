import argparse
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


TERMINAL_JOB_STATUS = {"succeeded", "failed", "stopped", "interrupted"}


@dataclass(frozen=True)
class StageSpec:
    start_path: str
    status_path: str
    stop_path: str
    default_payload: Dict[str, Any]


STAGES = {
    "process_pdfs": StageSpec(
        start_path="/pipeline/process_pdfs/start",
        status_path="/pipeline/process_pdfs/status",
        stop_path="/pipeline/process_pdfs/stop",
        default_payload={"chunk_size": 1200, "overlap": 200, "skip_existing": True},
    ),
    "embed_chunks": StageSpec(
        start_path="/pipeline/embed_chunks/start",
        status_path="/pipeline/embed_chunks/status",
        stop_path="/pipeline/embed_chunks/stop",
        default_payload={"batch_size": 16, "skip_existing": True},
    ),
    "summarize": StageSpec(
        start_path="/pipeline/summarize/start",
        status_path="/pipeline/summarize/status",
        stop_path="/pipeline/summarize/stop",
        default_payload={"chunk_chars": 4000, "skip_existing": True, "dry_run": False},
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test local RAG pipeline with optional interrupt/resume.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--request-timeout", type=int, default=30)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--stage-timeout", type=int, default=1800)
    parser.add_argument("--skip-process-pdfs", action="store_true")
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--skip-summarize", action="store_true")
    parser.add_argument("--process-limit", type=int, default=50)
    parser.add_argument("--embed-limit", type=int, default=500)
    parser.add_argument("--summarize-limit", type=int, default=100)
    parser.add_argument(
        "--interrupt-stage",
        choices=["none", "process_pdfs", "embed_chunks", "summarize"],
        default="embed_chunks",
    )
    parser.add_argument("--interrupt-after", type=float, default=3.0)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--chat-query", default="Summarize the key method trends across the library with citations.")
    parser.add_argument("--chat-scope", choices=["library", "paper"], default="library")
    parser.add_argument("--paper-id", type=int, default=None)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=6)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--chat-timeout", type=int, default=120)
    return parser.parse_args()


def build_url(api_base: str, path: str) -> str:
    return api_base.rstrip("/") + path


def assert_ok(resp: httpx.Response, action: str) -> Dict[str, Any]:
    if not resp.is_success:
        raise RuntimeError(f"{action} failed: status={resp.status_code}, body={(resp.text or '')[:400]}")
    return resp.json()


def wait_for_terminal_status(
    client: httpx.Client,
    api_base: str,
    stage: str,
    job_id: str,
    poll_interval: float,
    stage_timeout: int,
) -> Dict[str, Any]:
    deadline = time.time() + max(10, stage_timeout)
    status_path = STAGES[stage].status_path
    while time.time() < deadline:
        resp = client.get(build_url(api_base, status_path), params={"job_id": job_id})
        status = assert_ok(resp, f"{stage} status")
        current = status.get("status")
        if current in TERMINAL_JOB_STATUS:
            return status
        if not status.get("running", False) and current:
            return status
        time.sleep(max(0.3, poll_interval))
    raise TimeoutError(f"{stage} job {job_id} did not finish within {stage_timeout}s")


def run_stage(
    client: httpx.Client,
    api_base: str,
    stage: str,
    payload: Dict[str, Any],
    interrupt: bool,
    interrupt_after: float,
    poll_interval: float,
    stage_timeout: int,
) -> Dict[str, Any]:
    spec = STAGES[stage]
    started = assert_ok(client.post(build_url(api_base, spec.start_path), json=payload), f"{stage} start")
    job_id = started.get("job_id")
    if not job_id:
        raise RuntimeError(f"{stage} start response missing job_id: {started}")

    result: Dict[str, Any] = {
        "stage": stage,
        "started_job_id": job_id,
        "interrupted": False,
    }

    if interrupt:
        time.sleep(max(0.2, interrupt_after))
        assert_ok(
            client.post(build_url(api_base, spec.stop_path), json={"job_id": job_id}),
            f"{stage} stop",
        )
        first_terminal = wait_for_terminal_status(
            client=client,
            api_base=api_base,
            stage=stage,
            job_id=job_id,
            poll_interval=poll_interval,
            stage_timeout=stage_timeout,
        )
        result["interrupted"] = True
        result["first_terminal_status"] = first_terminal.get("status")

        resumed = assert_ok(
            client.post(build_url(api_base, f"/pipeline/jobs/{job_id}/resume")),
            f"{stage} resume",
        )
        resumed_job_id = resumed.get("job_id")
        if not resumed_job_id:
            raise RuntimeError(f"{stage} resume response missing job_id: {resumed}")
        resumed_terminal = wait_for_terminal_status(
            client=client,
            api_base=api_base,
            stage=stage,
            job_id=resumed_job_id,
            poll_interval=poll_interval,
            stage_timeout=stage_timeout,
        )
        result["resumed_job_id"] = resumed_job_id
        result["final_status"] = resumed_terminal.get("status")
        result["final_error"] = resumed_terminal.get("error_message")
    else:
        terminal = wait_for_terminal_status(
            client=client,
            api_base=api_base,
            stage=stage,
            job_id=job_id,
            poll_interval=poll_interval,
            stage_timeout=stage_timeout,
        )
        result["final_status"] = terminal.get("status")
        result["final_error"] = terminal.get("error_message")

    if result["final_status"] not in {"succeeded", "stopped"}:
        raise RuntimeError(
            f"{stage} finished with unexpected status={result['final_status']} error={result.get('final_error')}"
        )
    return result


def citations_valid(answer: str, citations: Any) -> bool:
    if not isinstance(citations, list) or not citations:
        return False
    valid = {str(item.get("index")) for item in citations}
    found = set()
    for token in (answer or "").split("["):
        if "]" not in token:
            continue
        idx = token.split("]", 1)[0].strip()
        if idx.isdigit():
            found.add(idx)
    return bool(found) and found.issubset(valid)


def run_chat_check(client: httpx.Client, args: argparse.Namespace) -> Dict[str, Any]:
    payload = {
        "query": args.chat_query,
        "scope": args.chat_scope,
        "paper_id": args.paper_id,
        "candidate_k": args.candidate_k,
        "final_k": args.final_k,
        "rerank": not args.no_rerank,
        "require_citations": True,
    }
    resp = client.post(build_url(args.api_base, "/chat"), json=payload, timeout=max(10, args.chat_timeout))
    data = assert_ok(resp, "chat")
    answer = data.get("answer") or ""
    citations = data.get("citations") or []
    if not citations_valid(answer, citations):
        raise RuntimeError("chat check failed: citations are missing or invalid")
    return {
        "citations": len(citations),
        "retrieval_meta": data.get("retrieval_meta"),
    }


def main():
    args = parse_args()
    enabled_stages = []
    if not args.skip_process_pdfs:
        enabled_stages.append("process_pdfs")
    if not args.skip_embed:
        enabled_stages.append("embed_chunks")
    if not args.skip_summarize:
        enabled_stages.append("summarize")
    if not enabled_stages and args.skip_chat:
        raise RuntimeError("Nothing to run: all pipeline stages and chat check are skipped.")

    summary: Dict[str, Any] = {
        "api_base": args.api_base,
        "started_at": int(time.time()),
        "stages": [],
        "chat": None,
    }

    timeout = httpx.Timeout(timeout=max(5, args.request_timeout))
    with httpx.Client(timeout=timeout) as client:
        health = assert_ok(client.get(build_url(args.api_base, "/health")), "health")
        if health.get("status") != "ok":
            raise RuntimeError(f"health check failed: {health}")

        for stage in enabled_stages:
            payload = dict(STAGES[stage].default_payload)
            if stage == "process_pdfs":
                payload["limit"] = args.process_limit
            elif stage == "embed_chunks":
                payload["limit_chunks"] = args.embed_limit
            elif stage == "summarize":
                payload["limit"] = args.summarize_limit

            stage_result = run_stage(
                client=client,
                api_base=args.api_base,
                stage=stage,
                payload=payload,
                interrupt=(args.interrupt_stage == stage),
                interrupt_after=args.interrupt_after,
                poll_interval=args.poll_interval,
                stage_timeout=args.stage_timeout,
            )
            summary["stages"].append(stage_result)

        if not args.skip_chat:
            summary["chat"] = run_chat_check(client, args)

    summary["finished_at"] = int(time.time())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
