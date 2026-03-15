import argparse
import subprocess
import sys


def run(cmd: list[str], label: str):
    print(f"\n==> {label}: {' '.join(cmd)}")
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main():
    parser = argparse.ArgumentParser(description="Run local release gate checks.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-eval", action="store_true")
    args = parser.parse_args()

    run([sys.executable, "-m", "compileall", "backend"], "Compile check")
    run([sys.executable, "-m", "pytest", "backend/tests", "-q"], "Backend tests")
    if not args.skip_eval:
        run(
            [
                sys.executable,
                "backend/scripts/evaluate_rag.py",
                "--api-base",
                args.api_base,
            ],
            "RAG quality gate",
        )
    print("\n[PASS] Release gate completed.")


if __name__ == "__main__":
    main()
