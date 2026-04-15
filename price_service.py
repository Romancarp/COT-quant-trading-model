"""Fetch, store, and serve weekly close prices from Yahoo Finance."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import INVERT_SIGN_ASSETS, TICKER_MAP
from cot_ingestion.models import WeeklyPrice
from cot_ingestion.repository import COTRepository

log = logging.getLogger(__name__)

_repo = COTRepository()


# ---------------------------------------------------------------------------
# yfinance download
# ---------------------------------------------------------------------------

def fetch_weekly_prices(asset: str, start: str, end: str) -> pd.DataFrame:
    """Download weekly close prices from Yahoo Finance.

    Returns a DataFrame with columns ``[price_date, close]``.
    """
    ticker = TICKER_MAP.get(asset)
    if not ticker:
        return pd.DataFrame(columns=["price_date", "close"])

    df = yf.download(
        ticker, start=start, end=end,
        interval="1wk", auto_adjust=True, progress=False,
    )
    if df.empty:
        return pd.DataFrame(columns=["price_date", "close"])

    # yfinance may return multi-level columns when a single ticker is passed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Close"]].copy()
    df.columns = ["close"]
    df.index.name = "price_date"
    df = df.reset_index()
    df["price_date"] = pd.to_datetime(df["price_date"]).dt.date
    return df


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _session():
    return _repo.SessionLocal()


def upsert_prices(asset: str, ticker: str, rows: list[dict]) -> int:
    """Upsert weekly price rows.  Each dict has ``{price_date, close}``."""
    if not rows:
        return 0
    values = [
        {
            "asset": asset,
            "price_date": r["price_date"],
            "ticker": ticker,
            "close": float(r["close"]),
            "created_at": datetime.now(),
        }
        for r in rows
    ]
    batch_size = 250
    with _session() as s:
        for i in range(0, len(values), batch_size):
            batch = values[i : i + batch_size]
            stmt = sqlite_insert(WeeklyPrice).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["asset", "price_date"],
                set_={"close": stmt.excluded.close},
            )
            s.execute(stmt)
        s.commit()
    return len(values)


def load_prices(asset: str) -> pd.DataFrame:
    """Return all stored prices for *asset* as a DataFrame."""
    with _session() as s:
        stmt = (
            select(WeeklyPrice.price_date, WeeklyPrice.close)
            .where(WeeklyPrice.asset == asset)
            .order_by(WeeklyPrice.price_date)
        )
        rows = list(s.execute(stmt).all())
    if not rows:
        return pd.DataFrame(columns=["price_date", "close"])
    df = pd.DataFrame(rows, columns=["price_date", "close"])
    df["price_date"] = pd.to_datetime(df["price_date"])
    return df


def latest_price_date(asset: str) -> date | None:
    with _session() as s:
        stmt = (
            select(WeeklyPrice.price_date)
            .where(WeeklyPrice.asset == asset)
            .order_by(WeeklyPrice.price_date.desc())
            .limit(1)
        )
        row = s.execute(stmt).first()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# Orchestrator – incremental fetch
# ---------------------------------------------------------------------------

def ensure_prices(asset: str) -> int:
    """Fetch and store any missing price data for *asset*.

    Returns the number of rows upserted.  On first call fetches from 2016
    to match COT data range; subsequent calls only fetch new data.
    """
    ticker = TICKER_MAP.get(asset)
    if not ticker:
        return 0

    latest = latest_price_date(asset)
    fetch_start = (latest + timedelta(days=1)) if latest else date(2016, 1, 1)
    fetch_end = date.today() + timedelta(days=1)

    if fetch_start >= fetch_end:
        return 0

    df = fetch_weekly_prices(asset, start=fetch_start.isoformat(), end=fetch_end.isoformat())
    if df.empty:
        return 0

    return upsert_prices(asset, ticker, df.to_dict("records"))
