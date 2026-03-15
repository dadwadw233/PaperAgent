from pathlib import Path

from backend.scripts import release_gate


def test_frontend_gate_commands_default_order():
    commands = release_gate.frontend_gate_commands()
    assert commands == [
        ["npm", "--prefix", "frontend", "run", "test:run"],
        ["npm", "--prefix", "frontend", "run", "build"],
    ]


def test_parse_args_supports_skip_frontend():
    args = release_gate.parse_args(["--skip-frontend"])
    assert args.skip_frontend is True


def test_choose_cases_path_prefers_explicit(tmp_path):
    explicit = tmp_path / "custom.json"
    explicit.write_text("[]", encoding="utf-8")
    chosen = release_gate.choose_cases_path(explicit)
    assert chosen == explicit


def test_latest_previous_report_ignores_current(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    p1 = reports_dir / "rag-baseline-20260101-000001.json"
    p2 = reports_dir / "rag-baseline-20260101-000002.json"
    p3 = reports_dir / "rag-baseline-20260101-000003.json"
    for path in [p1, p2, p3]:
        path.write_text("{}", encoding="utf-8")
    latest = release_gate.latest_previous_report(reports_dir, p3)
    assert latest == p2


def test_compare_against_previous_accepts_improvement():
    previous = {
        "retrieval_hit_rate": 0.95,
        "citation_valid_rate": 1.0,
        "answer_grounded_rate": 0.97,
        "p95_latency_ms": 7000.0,
    }
    current = {
        "retrieval_hit_rate": 0.97,
        "citation_valid_rate": 1.0,
        "answer_grounded_rate": 0.98,
        "p95_latency_ms": 6600.0,
    }
    assert release_gate.compare_against_previous(previous, current) == []


def test_compare_against_previous_detects_regression():
    previous = {
        "retrieval_hit_rate": 1.0,
        "citation_valid_rate": 1.0,
        "answer_grounded_rate": 1.0,
        "p95_latency_ms": 6000.0,
    }
    current = {
        "retrieval_hit_rate": 0.98,
        "citation_valid_rate": 0.99,
        "answer_grounded_rate": 0.97,
        "p95_latency_ms": 9000.0,
    }
    issues = release_gate.compare_against_previous(previous, current)
    issue_blob = "\n".join(issues)
    assert "retrieval_hit_rate regressed" in issue_blob
    assert "citation_valid_rate regressed" in issue_blob
    assert "answer_grounded_rate regressed" in issue_blob
    assert "p95_latency_ms regressed" in issue_blob
