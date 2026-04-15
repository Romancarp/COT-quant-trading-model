"""Static configuration and lookup tables for COT data ingestion and pricing."""

from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("cot_data.db")
DB_URL = os.getenv("COT_DB_URL", f"sqlite:///{DB_PATH.as_posix()}")
TABLE_NAME = "cot_positions"

# Source and ingestion settings
COT_SOURCE_MODE = os.getenv("COT_SOURCE_MODE", "cftc_preferred")
COT_REPORT_FORMATS = [
    x.strip()
    for x in os.getenv(
        "COT_REPORT_FORMATS",
        "legacy_fut,legacy_futopt,disagg_fut,disagg_futopt,tff_fut,tff_futopt",
    ).split(",")
    if x.strip()
]
COT_BACKFILL_YEARS = int(os.getenv("COT_BACKFILL_YEARS", "10"))
COT_HTTP_TIMEOUT = int(os.getenv("COT_HTTP_TIMEOUT", "30"))
COT_HTTP_RETRIES = int(os.getenv("COT_HTTP_RETRIES", "3"))

# Scheduler settings
COT_SCHED_ENABLED = os.getenv("COT_SCHED_ENABLED", "true").lower() == "true"
COT_SCHED_DAY = os.getenv("COT_SCHED_DAY", "fri")
COT_SCHED_HOUR = int(os.getenv("COT_SCHED_HOUR", "20"))
COT_SCHED_MINUTE = int(os.getenv("COT_SCHED_MINUTE", "0"))
COT_SCHED_TZ = os.getenv("COT_SCHED_TZ", "UTC")
INGEST_RUN_ON_STARTUP = os.getenv("INGEST_RUN_ON_STARTUP", "false").lower() == "true"

FOREX_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "NZD", "AUD", "CHF", "ZAR"]
STOCK_ASSETS = ["SPX500", "RUSSEL", "NIKKEI", "NASDAQ", "DOW"]
COMMODITY_ASSETS = ["USOIL", "SILVER", "GOLD", "PLATINUM", "COPPER"]

SOURCE_ASSETS_ORDER = FOREX_CURRENCIES + STOCK_ASSETS + COMMODITY_ASSETS

# Canonical -> derived mapping rules.
ASSET_CONFIG = {
    "USD": {
        "exact_names": ["U.S. DOLLAR INDEX - ICE FUTURES U.S.", "USD INDEX - ICE FUTURES U.S."],
        "keywords": ["DOLLAR INDEX", "USDX"],
    },
    "EUR": {"exact_names": ["EURO FX - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["EURO FX"]},
    "GBP": {"exact_names": ["BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["BRITISH POUND"]},
    "JPY": {"exact_names": ["JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["JAPANESE YEN"]},
    "CAD": {"exact_names": ["CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["CANADIAN DOLLAR"]},
    "NZD": {
        "exact_names": ["NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE", "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE"],
        "keywords": ["NEW ZEALAND DOLLAR", "NZ DOLLAR"],
    },
    "AUD": {"exact_names": ["AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["AUSTRALIAN DOLLAR"]},
    "CHF": {"exact_names": ["SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["SWISS FRANC"]},
    "ZAR": {
        "exact_names": ["SOUTH AFRICAN RAND - CHICAGO MERCANTILE EXCHANGE", "SO AFRICAN RAND - CHICAGO MERCANTILE EXCHANGE"],
        "keywords": ["SOUTH AFRICAN RAND", "SO AFRICAN RAND"],
    },
    "SPX500": {"exact_names": ["S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["S&P 500"]},
    "RUSSEL": {"exact_names": ["RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE", "E-MINI RUSSELL 2000 INDEX - CHICAGO MERCANTILE EXCHANGE", "RUSSELL 2000 MINI INDEX FUTURE - ICE FUTURES U.S."], "keywords": []},
    "NIKKEI": {
        "exact_names": [
            "NIKKEI STOCK AVERAGE - CHICAGO MERCANTILE EXCHANGE",
            "NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE",
        ],
        "keywords": ["NIKKEI STOCK AVERAGE"],
    },
    "NASDAQ": {"exact_names": ["NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE"], "keywords": ["NASDAQ-100"]},
    "DOW": {"exact_names": ["DJIA Consolidated - CHICAGO BOARD OF TRADE"], "keywords": ["DJIA"]},
    "USOIL": {
        "exact_names": [
            "WTI FINANCIAL CRUDE OIL - NEW YORK MERCANTILE EXCHANGE",
            "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
            "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
        ],
        "keywords": [],
    },
    "SILVER": {"exact_names": ["SILVER - COMMODITY EXCHANGE INC."], "keywords": ["SILVER"]},
    "GOLD": {"exact_names": ["GOLD - COMMODITY EXCHANGE INC."], "keywords": []},
    "PLATINUM": {"exact_names": ["PLATINUM - NEW YORK MERCANTILE EXCHANGE"], "keywords": ["PLATINUM"]},
    "COPPER": {"exact_names": ["COPPER- #1 - COMMODITY EXCHANGE INC.", "COPPER-GRADE #1 - COMMODITY EXCHANGE INC."], "keywords": []},
}

# Yahoo Finance ticker mapping for each asset.
TICKER_MAP = {
    "USD": "DX-Y.NYB",
    "EUR": "6E=F",
    "GBP": "6B=F",
    "JPY": "6J=F",
    "CAD": "6C=F",
    "AUD": "6A=F",
    "NZD": "6N=F",
    "CHF": "6S=F",
    "ZAR": "USDZAR=X",
    "SPX500": "^GSPC",
    "RUSSEL": "^RUT",
    "NIKKEI": "^N225",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "USOIL": "CL=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "PLATINUM": "PL=F",
    "COPPER": "HG=F",
}

# Assets where the price quote is inverted relative to COT long direction.
INVERT_SIGN_ASSETS = {"ZAR"}
