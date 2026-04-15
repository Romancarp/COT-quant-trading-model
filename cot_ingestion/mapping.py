from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from config import ASSET_CONFIG, SOURCE_ASSETS_ORDER
from cot_ingestion.normalizer import CanonicalPositionRecord


@dataclass(frozen=True)
class DerivedPositionRecord:
    asset: str
    trader_group: str
    report_date: date
    long_pos: int
    short_pos: int
    open_interest: int


def resolve_asset(market_name: str) -> str | None:
    name = market_name.strip()
    u = name.upper()
    for asset in SOURCE_ASSETS_ORDER:
        cfg = ASSET_CONFIG[asset]
        exact = cfg.get("exact_names", [])
        if exact and any(name.upper() == x.upper() for x in exact):
            return asset
        if not exact and any(k.upper() in u for k in cfg.get("keywords", [])):
            return asset
    return None


def _match_priority(asset: str, market_name: str) -> int | None:
    name = market_name.strip().upper()
    cfg = ASSET_CONFIG[asset]
    exact = [x.upper() for x in cfg.get("exact_names", [])]
    for idx, candidate in enumerate(exact):
        if name == candidate:
            return idx
    if not exact:
        for idx, keyword in enumerate(cfg.get("keywords", [])):
            if keyword.upper() in name:
                return 1000 + idx
    return None


def _preferred_format_for_asset(asset: str) -> str:
    return "legacy_fut"


def derive_asset_rows(canonical_records: list[CanonicalPositionRecord], preferred_formats: set[str]) -> list[DerivedPositionRecord]:
    selected: dict[tuple[str, str, date], tuple[int, CanonicalPositionRecord]] = {}

    for r in canonical_records:
        asset = resolve_asset(r.market_name)
        if not asset:
            continue
        preferred = _preferred_format_for_asset(asset)
        if preferred_formats and preferred not in preferred_formats:
            continue
        if r.report_format != preferred:
            continue
        priority = _match_priority(asset, r.market_name)
        if priority is None:
            continue
        key = (asset, r.trader_category, r.report_date)
        if key not in selected or priority < selected[key][0]:
            selected[key] = (priority, r)

    return [
        DerivedPositionRecord(
            asset=k[0],
            trader_group=k[1],
            report_date=k[2],
            long_pos=v[1].long_pos,
            short_pos=v[1].short_pos,
            open_interest=v[1].open_interest,
        )
        for k, v in selected.items()
    ]
