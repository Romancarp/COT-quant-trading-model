"""Builds a lag-aligned weekly panel of COT positions + prices per asset."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INVERT_SIGN_ASSETS
from data_service import load_single_asset_rows
from price_service import load_prices


def build_panel(asset: str) -> pd.DataFrame:
    """Return a weekly panel aligned so each COT row has its first tradeable price.

    COT data is as-of Tuesday; released Friday at 3:30 PM ET (too late to act).
    First realistic entry = close of the FOLLOWING Friday (release + 7 days).
    Each row therefore represents:
      - COT snapshot : Tuesday (report_date)
      - CFTC release : Friday of same week (release_date)
      - Tradeable entry : Friday close of the FOLLOWING week (price_date / close)

    Forward returns in targets.py are measured from that entry close forward,
    so fwd_ret_1w = return from entry to 1 week later, etc.

    Columns returned:
        report_date, release_date, price_date, close,
        long_pos, short_pos, open_interest, net_pos,
        long_pos_comm, short_pos_comm, open_interest_comm, net_pos_comm,
        long_pos_nr, short_pos_nr, open_interest_nr, net_pos_nr
    """
    # --- load positions ---
    nc = load_single_asset_rows(asset, "non_commercial").copy()
    comm = load_single_asset_rows(asset, "commercial").copy()
    nr = load_single_asset_rows(asset, "non_reportable").copy()

    if nc.empty:
        return pd.DataFrame()

    # rename commercial and NR columns to avoid clashes
    comm = comm.rename(columns={
        "long_pos": "long_pos_comm",
        "short_pos": "short_pos_comm",
        "open_interest": "open_interest_comm",
    })
    nr = nr.rename(columns={
        "long_pos": "long_pos_nr",
        "short_pos": "short_pos_nr",
        "open_interest": "open_interest_nr",
    })

    # merge all three groups on report_date
    cot = nc.merge(comm[["report_date", "long_pos_comm", "short_pos_comm", "open_interest_comm"]],
                   on="report_date", how="left")
    cot = cot.merge(nr[["report_date", "long_pos_nr", "short_pos_nr", "open_interest_nr"]],
                    on="report_date", how="left")

    # --- lag alignment ---
    # COT as-of Tuesday + 3 days = release Friday (3:30 PM ET — too late to act)
    # First tradeable entry = close of the FOLLOWING week (release_date + 7 days).
    cot["release_date"] = pd.to_datetime(cot["report_date"]) + pd.Timedelta(days=3)
    cot["entry_date"] = cot["release_date"] + pd.Timedelta(days=7)
    cot = cot.sort_values("entry_date").reset_index(drop=True)

    # --- prices ---
    prices = load_prices(asset).copy()
    if prices.empty:
        return pd.DataFrame()
    prices = prices.sort_values("price_date").reset_index(drop=True)
    prices["price_date"] = pd.to_datetime(prices["price_date"])

    # merge_asof: attach the first weekly close on or after entry_date
    # Normalise both keys to the same datetime precision (pandas 3 is strict about this)
    cot["entry_date"] = pd.to_datetime(cot["entry_date"]).astype("datetime64[us]")
    prices["price_date"] = prices["price_date"].astype("datetime64[us]")
    panel = pd.merge_asof(
        cot,
        prices,
        left_on="entry_date",
        right_on="price_date",
        direction="forward",
    )
    panel = panel.dropna(subset=["close"]).reset_index(drop=True)

    # --- ZAR sign inversion ---
    # CFTC ZAR futures are ZAR/USD but prices are USD/ZAR, so COT long = price down.
    # Swap long/short so that net_pos > 0 always means bullish for the price series.
    if asset in INVERT_SIGN_ASSETS:
        for suffix in ["", "_comm", "_nr"]:
            l_col = f"long_pos{suffix}"
            s_col = f"short_pos{suffix}"
            if l_col in panel.columns and s_col in panel.columns:
                panel[l_col], panel[s_col] = panel[s_col].copy(), panel[l_col].copy()

    # --- net position ---
    panel["net_pos"] = panel["long_pos"] - panel["short_pos"]
    panel["net_pos_comm"] = panel["long_pos_comm"].fillna(0) - panel["short_pos_comm"].fillna(0)
    panel["net_pos_nr"] = panel["long_pos_nr"].fillna(0) - panel["short_pos_nr"].fillna(0)

    panel = panel.sort_values("report_date").reset_index(drop=True)
    return panel
