from __future__ import annotations

import argparse
from datetime import date

from cot_ingestion.service import COTIngestionService


def main() -> int:
    parser = argparse.ArgumentParser(description="COT ingestion service")
    parser.add_argument("--weekly", action="store_true", help="run weekly sync")
    parser.add_argument("--backfill", action="store_true", help="run backfill")
    parser.add_argument("--start", type=str, default="", help="start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default="", help="end date YYYY-MM-DD")
    args = parser.parse_args()

    svc = COTIngestionService()

    if args.backfill:
        if not args.start or not args.end:
            raise SystemExit("--backfill requires --start and --end")
        result = svc.run_backfill(date.fromisoformat(args.start), date.fromisoformat(args.end))
    else:
        result = svc.run_weekly_sync()

    print(result)
    return 0 if result.status in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
