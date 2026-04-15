"""Forward return targets at 1w, 2w, and 4w horizons.

Each row in the panel corresponds to one COT release week.
The `close` column is the first tradeable Friday close (lag-adjusted).
Shifting by N rows gives the close N weeks later — no data leakage
because the COT signal is only available at row T, and we're measuring
what happens from row T to row T+N.

The last N rows will have NaN targets — never impute these.
"""

from __future__ import annotations

import pandas as pd

HORIZONS = [1, 2, 4, 6, 8]
TARGET_COLS = [f"fwd_ret_{n}w" for n in HORIZONS]


def compute_targets(panel: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with forward return columns aligned to panel index."""
    close = panel["close"].copy()
    out = pd.DataFrame(index=panel.index)
    for n in HORIZONS:
        out[f"fwd_ret_{n}w"] = close.shift(-n) / close - 1
    return out
