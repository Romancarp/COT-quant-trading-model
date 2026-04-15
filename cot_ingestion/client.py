from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

import cot_reports as cot
import pandas as pd

from config import COT_HTTP_RETRIES


@dataclass
class SourcePayload:
    report_format: str
    year: int
    frame: pd.DataFrame
    source_file: str


class CFTCClient:
    """Client for CFTC/COT data using cot_reports (CFTC-backed source)."""

    _COT_REPORT_TYPE_MAP = {
        "legacy_fut": "legacy_fut",
        "legacy_futopt": "legacy_futopt",
        "disagg_fut": "disaggregated_fut",
        "disagg_futopt": "disaggregated_futopt",
        "disaggregated_fut": "disaggregated_fut",
        "disaggregated_futopt": "disaggregated_futopt",
        "tff_fut": "traders_in_financial_futures_fut",
        "tff_futopt": "traders_in_financial_futures_futopt",
        "traders_in_financial_futures_fut": "traders_in_financial_futures_fut",
        "traders_in_financial_futures_futopt": "traders_in_financial_futures_futopt",
    }

    def fetch_year(self, report_format: str, year: int) -> SourcePayload:
        cot_report_type = self._COT_REPORT_TYPE_MAP.get(report_format, report_format)
        last_error: Exception | None = None
        for attempt in range(1, COT_HTTP_RETRIES + 1):
            try:
                frame = cot.cot_year(year=year, cot_report_type=cot_report_type, store_txt=False, verbose=False)
                source_file = f"{report_format}_{year}.csv"
                return SourcePayload(report_format=report_format, year=year, frame=frame, source_file=source_file)
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt == COT_HTTP_RETRIES:
                    break
                time.sleep(2 ** attempt)
        raise RuntimeError(f"fetch failed for {report_format} {year}: {last_error}")

    def latest_release_date(self) -> date:
        year = pd.Timestamp.utcnow().year
        frame = cot.cot_year(year=year, cot_report_type="legacy_fut", store_txt=False, verbose=False)

        if "As of Date in Form YYYY-MM-DD" in frame.columns:
            d = pd.to_datetime(frame["As of Date in Form YYYY-MM-DD"], errors="coerce").max()
        else:
            d = pd.to_datetime(frame["Report_Date_as_YYYY-MM-DD"], errors="coerce").max()

        return d.date()
