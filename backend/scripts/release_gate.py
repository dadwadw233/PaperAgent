import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_BASELINE_CASES = Path("backend/eval/rag_eval_cases_baseline_1500.json")
DEFAULT_FALLBACK_CASES = Path("backend/eval/rag_eval_cases.json")
DEFAULT_REPORTS_DIR = Path("backend/eval/reports")

RETRIEVAL_DROP_TOLERANCE = 0.005
CITATION_DROP_TOLERANCE = 0.0
GROUNDED_DROP_TOLERANCE = 0.005
P95_INCREASE_ABS_MS = 400.0
P95_INCREASE_RATIO = 0.08


def run(cmd: List[str], label: str):
    print(f"\n==> {label}: {' '.join(cmd)}")
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def frontend_gate_commands() -> List[List[str]]:
    return [
        ["npm", "--prefix", "frontend", "run", "test:run"],
        ["npm", "--prefix", "frontend", "run", "build"],
    ]


def choose_cases_path(explicit_cases: Optional[Path]) -> Path:
    if explicit_cases:
        return explicit_cases
    if DEFAULT_BASELINE_CASES.exists():
        return DEFAULT_BASELINE_CASES
    return DEFAULT_FALLBACK_CASES


def latest_previous_report(reports_dir: Path, current_report: Path) -> Optional[Path]:
    if not reports_dir.exists():
        return None
    candidates = sorted(reports_dir.glob("rag-baseline-*.json"))
    candidates = [path for path in candidates if path != current_report]
    if not candidates:
        return None
    return candidates[-1]


def load_summary(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compare_against_previous(previous: Dict[str, Any], current: Dict[str, Any]) -> List[str]:
    regressions: List[str] = []
    prev_retrieval = float(previous.get("retrieval_hit_rate", 0.0))
    cur_retrieval = float(current.get("retrieval_hit_rate", 0.0))
    if cur_retrieval < prev_retrieval - RETRIEVAL_DROP_TOLERANCE:
        regressions.append(
            f"retrieval_hit_rate regressed: {cur_retrieval:.3f} < {prev_retrieval:.3f} - {RETRIEVAL_DROP_TOLERANCE:.3f}"
        )

    prev_citation = float(previous.get("citation_valid_rate", 0.0))
    cur_citation = float(current.get("citation_valid_rate", 0.0))
    if cur_citation < prev_citation - CITATION_DROP_TOLERANCE:
        regressions.append(
            f"citation_valid_rate regressed: {cur_citation:.3f} < {prev_citation:.3f}"
        )

    prev_grounded = float(previous.get("answer_grounded_rate", 0.0))
    cur_grounded = float(current.get("answer_grounded_rate", 0.0))
    if cur_grounded < prev_grounded - GROUNDED_DROP_TOLERANCE:
        regressions.append(
            f"answer_grounded_rate regressed: {cur_grounded:.3f} < {prev_grounded:.3f} - {GROUNDED_DROP_TOLERANCE:.3f}"
        )

    prev_p95 = float(previous.get("p95_latency_ms", 0.0))
    cur_p95 = float(current.get("p95_latency_ms", 0.0))
    allowed_p95 = prev_p95 + max(P95_INCREASE_ABS_MS, prev_p95 * P95_INCREASE_RATIO)
    if cur_p95 > allowed_p95:
        regressions.append(
            f"p95_latency_ms regressed: {cur_p95:.1f} > allowed {allowed_p95:.1f} (prev={prev_p95:.1f})"
        )
    return regressions


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local release gate checks.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-regression-check", action="store_true")
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--eval-workers", type=int, default=3)
    parser.add_argument("--eval-timeout", type=int, default=180)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    return parser.parse_args(argv)


def main():
    args = parse_args()

    run([sys.executable, "-m", "compileall", "backend"], "Compile check")
    run([sys.executable, "-m", "pytest", "backend/tests", "-q"], "Backend tests")
    if not args.skip_frontend:
        for cmd, label in zip(frontend_gate_commands(), ["Frontend tests", "Frontend build"]):
            run(cmd, label)

    if args.skip_eval:
        print("\n[PASS] Release gate completed (evaluation skipped).")
        return

    cases_path = choose_cases_path(args.cases)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    output_json = args.reports_dir / f"rag-baseline-{ts}.json"
    output_md = args.reports_dir / f"rag-baseline-{ts}.md"

    run(
        [
            sys.executable,
            "backend/scripts/evaluate_rag.py",
            "--api-base",
            args.api_base,
            "--cases",
            str(cases_path),
            "--workers",
            str(max(1, args.eval_workers)),
            "--timeout",
            str(max(10, args.eval_timeout)),
            "--output",
            str(output_json),
            "--report",
            str(output_md),
        ],
        "RAG quality gate",
    )

    if args.skip_regression_check:
        print("\n[PASS] Release gate completed (regression comparison skipped).")
        return

    previous_report = latest_previous_report(args.reports_dir, output_json)
    if not previous_report:
        print("\n[PASS] Release gate completed (no previous baseline report found).")
        return

    previous_summary = load_summary(previous_report)
    current_summary = load_summary(output_json)
    regressions = compare_against_previous(previous_summary, current_summary)
    if regressions:
        print("\n[FAIL] Baseline regression detected against previous report:")
        print(f"- previous: {previous_report}")
        print(f"- current: {output_json}")
        for item in regressions:
            print(f"- {item}")
        raise SystemExit(1)

    print("\n[PASS] Release gate completed.")


if __name__ == "__main__":
    main()
