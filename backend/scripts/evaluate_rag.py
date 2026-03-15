import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

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


def evaluate(api_base: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    client = httpx.Client(timeout=120)
    total = len(cases)
    citation_ok = 0
    grounded_ok = 0
    retrieval_ok = 0
    latencies: List[float] = []
    case_results: List[Dict[str, Any]] = []

    for case in cases:
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
        resp = client.post(f"{api_base.rstrip('/')}/chat", json=payload)
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)
        if not resp.is_success:
            case_results.append(
                {
                    "id": case.get("id"),
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:300],
                    "latency_ms": int(latency_ms),
                }
            )
            continue
        data = resp.json()
        answer = data.get("answer") or ""
        citations = data.get("citations") or []
        expected_terms = case.get("expected_terms") or []

        citation_valid = has_valid_citations(answer, citations)
        grounded_valid = answer_grounded(answer)
        retrieval_valid = retrieval_hit(answer, citations, expected_terms)
        citation_ok += 1 if citation_valid else 0
        grounded_ok += 1 if grounded_valid else 0
        retrieval_ok += 1 if retrieval_valid else 0
        case_results.append(
            {
                "id": case.get("id"),
                "ok": citation_valid and grounded_valid and retrieval_valid,
                "citation_valid": citation_valid,
                "grounded_valid": grounded_valid,
                "retrieval_valid": retrieval_valid,
                "latency_ms": int(latency_ms),
            }
        )

    summary = {
        "total_cases": total,
        "retrieval_hit_rate": retrieval_ok / total,
        "citation_valid_rate": citation_ok / total,
        "answer_grounded_rate": grounded_ok / total,
        "p95_latency_ms": percentile_95(latencies),
        "avg_latency_ms": statistics.mean(latencies) if latencies else 0.0,
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


def main():
    parser = argparse.ArgumentParser(description="Evaluate local RAG quality and enforce release thresholds.")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("backend/eval/rag_eval_cases.json"),
        help="JSON file containing evaluation prompts and optional expectations.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Do not fail with non-zero exit code when thresholds are not met.",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    summary = evaluate(args.api_base, cases)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    failures = check_thresholds(summary, DEFAULT_THRESHOLDS)
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
