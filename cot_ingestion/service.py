from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from config import COT_BACKFILL_YEARS, COT_REPORT_FORMATS
from cot_ingestion.client import CFTCClient
from cot_ingestion.mapping import derive_asset_rows
from cot_ingestion.normalizer import hash_source
from cot_ingestion.parsers import PARSER_MAP
from cot_ingestion.repository import COTRepository


@dataclass
class SyncResult:
    status: str
    new_rows: int
    updated_rows: int
    skipped_rows: int
    error_count: int
    latest_release: date | None


class COTIngestionService:
    def __init__(self, repository: COTRepository | None = None, client: CFTCClient | None = None):
        self.repo = repository or COTRepository()
        self.client = client or CFTCClient()

    def run_weekly_sync(self) -> SyncResult:
        self.repo.init_schema()
        run_id = self.repo.create_run()

        new_rows = 0
        updated_rows = 0
        skipped_rows = 0
        errors: list[str] = []
        latest = None

        try:
            latest = self.client.latest_release_date()
            last_state = self.repo.get_state("last_successful_release")
            if last_state and date.fromisoformat(last_state) >= latest:
                self.repo.finish_run(run_id, "success", 0, 0, 0, 0, {"message": "no new release"})
                return SyncResult("success", 0, 0, 0, 0, latest)

            start_year = (date.fromisoformat(last_state).year if last_state else latest.year - COT_BACKFILL_YEARS)
            end_year = latest.year
            all_records = []

            for report_format in COT_REPORT_FORMATS:
                parser = PARSER_MAP.get(report_format)
                if not parser:
                    errors.append(f"unsupported report format: {report_format}")
                    self.repo.log_error(run_id, report_format, None, "config", "unsupported report format")
                    continue

                for year in range(start_year, end_year + 1):
                    try:
                        payload = self.client.fetch_year(report_format, year)
                        src_hash = hash_source(payload.frame.to_csv(index=False).encode("utf-8"))
                        records = parser(payload.frame, payload.source_file, src_hash)
                        all_records.extend(records)
                    except Exception as exc:
                        msg = str(exc)
                        errors.append(msg)
                        self.repo.log_error(run_id, report_format, str(year), "fetch_or_parse", msg)

            inserted, updated = self.repo.upsert_canonical(all_records)
            new_rows += inserted
            updated_rows += updated

            derived = derive_asset_rows(all_records, preferred_formats={"legacy_fut"})
            d_ins, d_upd = self.repo.upsert_derived(derived)
            new_rows += d_ins
            updated_rows += d_upd

            status = "success" if not errors else "partial"
            self.repo.set_state("last_successful_release", latest.isoformat())
            self.repo.finish_run(
                run_id,
                status,
                new_rows,
                updated_rows,
                skipped_rows,
                len(errors),
                {"latest_release": latest.isoformat(), "errors": errors[:20]},
            )
            return SyncResult(status, new_rows, updated_rows, skipped_rows, len(errors), latest)
        except Exception as exc:
            self.repo.log_error(run_id, "service", None, "fatal", str(exc))
            self.repo.finish_run(run_id, "failed", new_rows, updated_rows, skipped_rows, len(errors) + 1, {"fatal": str(exc)})
            return SyncResult("failed", new_rows, updated_rows, skipped_rows, len(errors) + 1, latest)

    def run_backfill(self, start_date: date, end_date: date) -> SyncResult:
        self.repo.init_schema()
        run_id = self.repo.create_run()

        new_rows = 0
        updated_rows = 0
        skipped_rows = 0
        errors: list[str] = []

        try:
            all_records = []
            for report_format in COT_REPORT_FORMATS:
                parser = PARSER_MAP.get(report_format)
                if not parser:
                    errors.append(f"unsupported report format: {report_format}")
                    self.repo.log_error(run_id, report_format, None, "config", "unsupported report format")
                    continue

                for year in range(start_date.year, end_date.year + 1):
                    try:
                        payload = self.client.fetch_year(report_format, year)
                        src_hash = hash_source(payload.frame.to_csv(index=False).encode("utf-8"))
                        records = parser(payload.frame, payload.source_file, src_hash)
                        all_records.extend(r for r in records if start_date <= r.report_date <= end_date)
                    except Exception as exc:
                        msg = str(exc)
                        errors.append(msg)
                        self.repo.log_error(run_id, report_format, str(year), "fetch_or_parse", msg)

            inserted, updated = self.repo.upsert_canonical(all_records)
            new_rows += inserted
            updated_rows += updated

            derived = derive_asset_rows(all_records, preferred_formats={"legacy_fut"})
            d_ins, d_upd = self.repo.upsert_derived(derived)
            new_rows += d_ins
            updated_rows += d_upd

            status = "success" if not errors else "partial"
            self.repo.finish_run(
                run_id,
                status,
                new_rows,
                updated_rows,
                skipped_rows,
                len(errors),
                {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "errors": errors[:20]},
            )
            return SyncResult(status, new_rows, updated_rows, skipped_rows, len(errors), end_date)
        except Exception as exc:
            self.repo.log_error(run_id, "service", None, "fatal", str(exc))
            self.repo.finish_run(run_id, "failed", new_rows, updated_rows, skipped_rows, len(errors) + 1, {"fatal": str(exc)})
            return SyncResult("failed", new_rows, updated_rows, skipped_rows, len(errors) + 1, end_date)
