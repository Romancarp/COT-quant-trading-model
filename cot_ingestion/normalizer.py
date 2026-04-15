from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CanonicalPositionRecord:
    report_date: date
    as_of_date: date | None
    report_format: str
    futures_only_or_combined: str | None
    cftc_contract_market_code: str
    market_name: str
    trader_category: str
    long_pos: int
    short_pos: int
    open_interest: int
    source_file: str | None
    source_hash: str | None


def parse_int(value) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "")
    if text in {"", ".", "nan", "None"}:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def hash_source(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
