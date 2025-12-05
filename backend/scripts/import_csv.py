import argparse
from pathlib import Path
from typing import Optional

from backend.app.services.importer import ingest_csv


def main():
    parser = argparse.ArgumentParser(description="Import Zotero CSV into local database.")
    parser.add_argument("--csv", type=Path, required=True, help="Path to Zotero CSV file.")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for a quick smoke test.")
    args = parser.parse_args()
    result = ingest_csv(args.csv, limit=args.limit)
    print(
        f"Ingest complete. inserted={result['inserted']}, skipped(existing)={result['skipped']}, total_rows={result['total_rows']}"
    )
    if result["non_papers"]:
        print("\nDetected non-paper items (Item Type):")
        for p in result["non_papers"]:
            title = (p.get('title') or '').strip()
            print(f"- {p.get('item_type') or ''} | {p.get('key')} | {title[:80]}")
    else:
        print("\nNo non-paper items detected.")


if __name__ == "__main__":
    main()
