import argparse
import concurrent.futures
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


DEFAULT_THRESHOLDS = {
    "retrieval_hit_rate": 0.85,
    "citation_valid_rate": 1.0,
    "answer_grounded_rate": 0.8,
    "p95_latency_ms": 8000,
}


def load_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        data = data["cases"]
    if not isinstance(data, list) or not data:
        raise RuntimeError("Evaluation cases must be a non-empty JSON array.")
    return data


def has_valid_citations(answer: str, citations: List[Dict[str, Any]]) -> bool:
    if not citations:
        return False
    valid_indices = {str(item.get("index")) for item in citations}
    found = set()
    for token in answer.split("["):
        if "]" not in token:
            continue
        idx = token.split("]", 1)[0].strip()
        if idx.isdigit():
            found.add(idx)
    if not found:
        return False
    return found.issubset(valid_indices)


def answer_grounded(answer: str) -> bool:
    paragraphs = [line.strip() for line in answer.split("\n") if line.strip()]
    if not paragraphs:
        return False
    grounded_count = sum(1 for line in paragraphs if "[" in line and "]" in line)
    return grounded_count / len(paragraphs) >= 0.7


def retrieval_hit(answer: str, citations: List[Dict[str, Any]], expected_terms: List[str]) -> bool:
    if not expected_terms:
        return True
    text_blob = (answer or "").lower() + "\n" + "\n".join((c.get("snippet") or "").lower() for c in citations)
    return all(term.lower() in text_blob for term in expected_terms)


def percentile_95(values: List[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[94]


def evaluate_case(api_base: str, case: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    payload = {
        "query": case["query"],
        "scope": case.get("scope", "library"),
        "paper_id": case.get("paper_id"),
        "candidate_k": case.get("candidate_k", 20),
        "final_k": case.get("final_k", 6),
        "rerank": case.get("rerank", True),
        "require_citations": case.get("require_citations", True),
    }
    started = time.perf_counter()
    case_id = case.get("id")
    expected_terms = case.get("expected_terms") or []
    try:
        resp = httpx.post(f"{api_base.rstrip('/')}/chat", json=payload, timeout=timeout)
        latency_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "id": case_id,
            "ok": False,
            "latency_ms": int(latency_ms),
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "citation_valid": False,
            "grounded_valid": False,
            "retrieval_valid": False,
        }

    if not resp.is_success:
        return {
            "id": case_id,
            "ok": False,
            "status_code": resp.status_code,
            "error": (resp.text or "")[:300],
            "latency_ms": int(latency_ms),
            "citation_valid": False,
            "grounded_valid": False,
            "retrieval_valid": False,
        }

    data = resp.json()
    answer = data.get("answer") or ""
    citations = data.get("citations") or []
    citation_valid = has_valid_citations(answer, citations)
    grounded_valid = answer_grounded(answer)
    retrieval_valid = retrieval_hit(answer, citations, expected_terms)
    return {
        "id": case_id,
        "ok": citation_valid and grounded_valid and retrieval_valid,
        "citation_valid": citation_valid,
        "grounded_valid": grounded_valid,
        "retrieval_valid": retrieval_valid,
        "latency_ms": int(latency_ms),
    }


def evaluate(api_base: str, cases: List[Dict[str, Any]], workers: int = 1, timeout: int = 120) -> Dict[str, Any]:
    total = len(cases)
    case_results: List[Dict[str, Any]] = []
    latencies: List[float] = []

    if workers <= 1:
        for case in cases:
            item = evaluate_case(api_base=api_base, case=case, timeout=timeout)
            case_results.append(item)
            latencies.append(float(item.get("latency_ms", 0)))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(evaluate_case, api_base, case, timeout): idx
                for idx, case in enumerate(cases)
            }
            ordered: Dict[int, Dict[str, Any]] = {}
            for future in concurrent.futures.as_completed(future_map):
                idx = future_map[future]
                try:
                    ordered[idx] = future.result()
                except Exception as exc:
                    ordered[idx] = {
                        "id": cases[idx].get("id"),
                        "ok": False,
                        "latency_ms": 0,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:300],
                        "citation_valid": False,
                        "grounded_valid": False,
                        "retrieval_valid": False,
                    }
            for idx in range(total):
                item = ordered[idx]
                case_results.append(item)
                latencies.append(float(item.get("latency_ms", 0)))

    citation_ok = sum(1 for item in case_results if item.get("citation_valid"))
    grounded_ok = sum(1 for item in case_results if item.get("grounded_valid"))
    retrieval_ok = sum(1 for item in case_results if item.get("retrieval_valid"))
    failed_cases = [item for item in case_results if not item.get("ok")]

    summary = {
        "total_cases": total,
        "retrieval_hit_rate": retrieval_ok / total if total else 0.0,
        "citation_valid_rate": citation_ok / total if total else 0.0,
        "answer_grounded_rate": grounded_ok / total if total else 0.0,
        "p95_latency_ms": percentile_95(latencies),
        "avg_latency_ms": statistics.mean(latencies) if latencies else 0.0,
        "workers": workers,
        "timeout_seconds": timeout,
        "failed_count": len(failed_cases),
        "failed_cases": failed_cases,
        "cases": case_results,
    }
    return summary


def check_thresholds(summary: Dict[str, Any], thresholds: Dict[str, float]) -> List[str]:
    failures: List[str] = []
    if summary["retrieval_hit_rate"] < thresholds["retrieval_hit_rate"]:
        failures.append(
            f"retrieval_hit_rate {summary['retrieval_hit_rate']:.3f} < {thresholds['retrieval_hit_rate']:.3f}"
        )
    if summary["citation_valid_rate"] < thresholds["citation_valid_rate"]:
        failures.append(
            f"citation_valid_rate {summary['citation_valid_rate']:.3f} < {thresholds['citation_valid_rate']:.3f}"
        )
    if summary["answer_grounded_rate"] < thresholds["answer_grounded_rate"]:
        failures.append(
            f"answer_grounded_rate {summary['answer_grounded_rate']:.3f} < {thresholds['answer_grounded_rate']:.3f}"
        )
    if summary["p95_latency_ms"] > thresholds["p95_latency_ms"]:
        failures.append(
            f"p95_latency_ms {summary['p95_latency_ms']:.1f} > {thresholds['p95_latency_ms']:.1f}"
        )
    return failures


def write_markdown_report(
    summary: Dict[str, Any],
    thresholds: Dict[str, float],
    threshold_failures: List[str],
    report_path: Path,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# RAG Evaluation Baseline Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total cases: {summary['total_cases']}")
    lines.append(f"- Failed cases: {summary['failed_count']}")
    lines.append(f"- retrieval_hit_rate: {summary['retrieval_hit_rate']:.3f} (target >= {thresholds['retrieval_hit_rate']:.3f})")
    lines.append(f"- citation_valid_rate: {summary['citation_valid_rate']:.3f} (target = {thresholds['citation_valid_rate']:.3f})")
    lines.append(f"- answer_grounded_rate: {summary['answer_grounded_rate']:.3f} (target >= {thresholds['answer_grounded_rate']:.3f})")
    lines.append(f"- p95_latency_ms: {summary['p95_latency_ms']:.1f} (target <= {thresholds['p95_latency_ms']:.1f})")
    lines.append(f"- avg_latency_ms: {summary['avg_latency_ms']:.1f}")
    lines.append("")
    lines.append("## Threshold Check")
    lines.append("")
    if threshold_failures:
        lines.append("- Result: FAIL")
        for item in threshold_failures:
            lines.append(f"- {item}")
    else:
        lines.append("- Result: PASS")
    lines.append("")
    lines.append("## Failed Cases")
    lines.append("")
    if not summary["failed_cases"]:
        lines.append("- None")
    else:
        for item in summary["failed_cases"][:100]:
            case_id = item.get("id")
            latency_ms = item.get("latency_ms")
            err = item.get("error") or ""
            reasons = []
            if not item.get("citation_valid", False):
                reasons.append("citation_invalid")
            if not item.get("grounded_valid", False):
                reasons.append("grounding_invalid")
            if not item.get("retrieval_valid", False):
                reasons.append("retrieval_miss")
            if item.get("status_code"):
                reasons.append(f"http_{item['status_code']}")
            if item.get("error_type"):
                reasons.append(item["error_type"])
            reason_text = ",".join(reasons) if reasons else "unknown"
            lines.append(f"- {case_id}: {reason_text}, latency_ms={latency_ms}, error={err}")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate local RAG quality and enforce release thresholds.")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("backend/eval/rag_eval_cases.json"),
        help="JSON file containing evaluation prompts and optional expectations.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel worker count for /chat evaluation requests.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to save JSON summary.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to save Markdown report.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Do not fail with non-zero exit code when thresholds are not met.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cases = load_cases(args.cases)
    summary = evaluate(
        api_base=args.api_base,
        cases=cases,
        workers=max(1, args.workers),
        timeout=max(10, args.timeout),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[INFO] Wrote JSON summary to {args.output}")

    failures = check_thresholds(summary, DEFAULT_THRESHOLDS)
    if args.report:
        write_markdown_report(summary, DEFAULT_THRESHOLDS, failures, args.report)
        print(f"[INFO] Wrote markdown report to {args.report}")

    if failures:
        print("\n[FAIL] Threshold checks failed:")
        for item in failures:
            print(f"- {item}")
        if not args.no_fail:
            raise SystemExit(1)
    else:
        print("\n[PASS] All threshold checks passed.")


if __name__ == "__main__":
    main()
