from __future__ import annotations

import argparse
from datetime import date, datetime

from cot_ingestion.service import COTIngestionService


def main() -> int:
    current_year = datetime.now().year

    parser = argparse.ArgumentParser(description="Sync COT reports into local SQLite/PostgreSQL database.")
    parser.add_argument("--start-year", type=int, default=current_year - 1, help="first year to fetch")
    parser.add_argument("--end-year", type=int, default=current_year, help="last year to fetch")
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise SystemExit("start-year must be <= end-year")

    svc = COTIngestionService()
    result = svc.run_backfill(date(args.start_year, 1, 1), date(args.end_year, 12, 31))
    print(result)

    return 0 if result.status in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
