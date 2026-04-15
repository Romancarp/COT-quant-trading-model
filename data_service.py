"""Read/query helpers backed by SQLAlchemy repository."""

from __future__ import annotations

import pandas as pd

from cot_ingestion.repository import COTRepository

_repo = COTRepository()


def init_db() -> None:
    _repo.init_schema()


def load_single_asset_rows(asset: str, report_type: str) -> pd.DataFrame:
    rows = _repo.fetch_derived_rows(asset, report_type)
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows, columns=["report_date", "long_pos", "short_pos", "open_interest"])
    frame["report_date"] = pd.to_datetime(frame["report_date"], errors="coerce")
    return frame.dropna(subset=["report_date"])


def load_asset_rows(asset: str, report_type: str) -> pd.DataFrame:
    return load_single_asset_rows(asset, report_type)


def has_data(asset: str, report_type: str) -> bool:
    return _repo.has_derived_data(asset, report_type)
