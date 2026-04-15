"""Verify which source contracts were mapped to each asset in the canonical DB.

Run this BEFORE running the full research pipeline to confirm the right
COT contracts are being used (e.g. 'GOLD - COMMODITY EXCHANGE INC.' and
not 'GOLD MINI' or 'E-MICRO GOLD').

Usage:
    python -m research.verify_contracts
    python -m research.verify_contracts --assets GOLD,SILVER,EUR
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import pandas as pd
from sqlalchemy import select, func

from config import DB_URL, SOURCE_ASSETS_ORDER, ASSET_CONFIG
from cot_ingestion.models import CanonicalPosition
from cot_ingestion.repository import COTRepository
from cot_ingestion.mapping import resolve_asset


def verify_contracts(assets: list[str]) -> None:
    repo = COTRepository(DB_URL)

    print(f"\n{'='*70}")
    print("COT Contract Verification")
    print(f"{'='*70}\n")

    with repo.SessionLocal() as s:
        # Fetch all distinct market_names from canonical table with row counts
        stmt = (
            select(
                CanonicalPosition.market_name,
                CanonicalPosition.report_format,
                func.count().label("n_rows"),
                func.min(CanonicalPosition.report_date).label("first_date"),
                func.max(CanonicalPosition.report_date).label("last_date"),
            )
            .where(CanonicalPosition.report_format == "legacy_fut")
            .group_by(CanonicalPosition.market_name, CanonicalPosition.report_format)
            .order_by(CanonicalPosition.market_name)
        )
        rows = list(s.execute(stmt).all())

    if not rows:
        print("No canonical data found. Run sync_cot.py first.")
        return

    # Group by resolved asset
    mapped: dict[str, list] = {a: [] for a in assets}
    unmapped = []

    for market_name, report_format, n_rows, first_date, last_date in rows:
        resolved = resolve_asset(market_name)
        if resolved in assets:
            mapped[resolved].append({
                "market_name": market_name,
                "format": report_format,
                "n_rows": n_rows,
                "first": str(first_date)[:10],
                "last": str(last_date)[:10],
            })

    # Print per asset
    issues_found = False
    for asset in assets:
        contracts = mapped[asset]
        expected = ASSET_CONFIG.get(asset, {}).get("exact_names", [])

        print(f"  {asset}")
        print(f"  Expected exact name(s): {expected}")

        if not contracts:
            print(f"  *** NO CONTRACTS MAPPED — asset will have no data ***\n")
            issues_found = True
            continue

        for c in contracts:
            match_marker = "OK" if c["market_name"] in expected else "*** UNEXPECTED ***"
            print(f"    [{match_marker}] {c['market_name']}")
            print(f"           rows={c['n_rows']}  {c['first']} to {c['last']}")
            if match_marker != "OK":
                issues_found = True

        if len(contracts) > 1:
            # Only flag as an issue if date ranges overlap (genuine duplicate)
            # Sequential name changes (CFTC renames) are expected and fine
            has_overlap = False
            for i, a in enumerate(contracts):
                for b in contracts[i+1:]:
                    if a["first"] <= b["last"] and b["first"] <= a["last"]:
                        has_overlap = True
            if has_overlap:
                print(f"  *** OVERLAPPING DATE RANGES — possible duplicate contract data ***")
                issues_found = True
            else:
                print(f"  (Note: {len(contracts)} sequential contracts — CFTC rename, OK)")

        print()

    if issues_found:
        print("ACTION REQUIRED: Fix ASSET_CONFIG in config.py and re-run sync_cot.py.")
    else:
        print("All contracts verified OK.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assets",
        default=",".join(SOURCE_ASSETS_ORDER),
        help="Comma-separated assets to check (default: all)",
    )
    args = parser.parse_args()
    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    verify_contracts(assets)


if __name__ == "__main__":
    main()
