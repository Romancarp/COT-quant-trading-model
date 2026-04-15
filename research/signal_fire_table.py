"""Generate a historical table of every COT signal fire for manual TA backtesting.

Output: results/signal_fires.csv

Columns:
    entry_date      - Friday you would enter (following Friday after COT release)
    report_date     - COT report as-of date (Tuesday)
    asset           - asset name
    direction       - LONG or SHORT
    nr_net_rank     - signal value (0-1, >0.85 = short, <0.15 = long)
    entry_price     - closing price on entry_date
    price_1w        - price 1 week later
    price_2w        - price 2 weeks later
    price_4w        - price 4 weeks later
    ret_1w          - % return if held 1w (direction-adjusted)
    ret_2w          - % return if held 2w (direction-adjusted)
    ret_4w          - % return if held 4w (direction-adjusted)
    correct_4w      - YES/NO was the direction right at 4w
    split           - IS / OOS / HOLDOUT (which data period)
    prev_4w_ret     - price return in the 4 weeks BEFORE entry (context for chart)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import build_panel
from research.signals import compute_all_signals
from research.evaluation import _split_indices

ASSETS  = ["EUR", "CAD", "JPY", "AUD", "GBP", "USD", "PLATINUM"]
SIGNAL  = "nr_net_rank"
CUTOFF  = 0.85

rows = []

for asset in ASSETS:
    panel = build_panel(asset)
    if panel.empty:
        continue

    signals_df = compute_all_signals(panel)
    rank       = signals_df[SIGNAL]
    prices     = panel["close"].values
    dates      = pd.to_datetime(panel["entry_date"]).dt.date
    report_dates = pd.to_datetime(panel["report_date"]).dt.date
    n          = len(panel)

    _, oos_sl, hold_sl = _split_indices(n)

    def split_label(i):
        if i < oos_sl.start:   return "IS"
        if i < hold_sl.start:  return "OOS"
        return "HOLDOUT"

    for i in range(n):
        r = rank.iloc[i]
        if r >= CUTOFF:
            direction = "SHORT"
            sign = -1.0
        elif r <= (1 - CUTOFF):
            direction = "LONG"
            sign = 1.0
        else:
            continue

        ep = prices[i]
        if ep == 0 or np.isnan(ep):
            continue

        def pret(j):
            if j >= n or np.isnan(prices[j]) or prices[j] == 0:
                return np.nan
            return (prices[j] / ep - 1) * sign

        ret_1w = pret(i + 1)
        ret_2w = pret(i + 2)
        ret_4w = pret(i + 4)

        # Prior 4w context
        prev_4w = (ep / prices[i - 4] - 1) if i >= 4 and prices[i-4] > 0 else np.nan

        correct = ""
        if not np.isnan(ret_4w):
            correct = "YES" if ret_4w > 0 else "NO"

        rows.append(dict(
            entry_date    = str(dates.iloc[i]),
            report_date   = str(report_dates.iloc[i]),
            asset         = asset,
            direction     = direction,
            nr_net_rank   = round(float(r), 3),
            entry_price   = round(float(ep), 5),
            price_1w      = round(float(prices[i+1]), 5) if i+1 < n else None,
            price_2w      = round(float(prices[i+2]), 5) if i+2 < n else None,
            price_4w      = round(float(prices[i+4]), 5) if i+4 < n else None,
            ret_1w_pct    = round(ret_1w * 100, 3) if not np.isnan(ret_1w) else None,
            ret_2w_pct    = round(ret_2w * 100, 3) if not np.isnan(ret_2w) else None,
            ret_4w_pct    = round(ret_4w * 100, 3) if not np.isnan(ret_4w) else None,
            correct_4w    = correct,
            split         = split_label(i),
            prev_4w_ret_pct = round(prev_4w * 100, 3) if not np.isnan(prev_4w) else None,
        ))

df = pd.DataFrame(rows)
df = df.sort_values(["asset", "entry_date"]).reset_index(drop=True)

Path("results").mkdir(exist_ok=True)
df.to_csv("results/signal_fires.csv", index=False)

# Summary
print(f"\nTotal signal fires: {len(df)}")
print(f"\nBy asset and split:")
summary = df.groupby(["asset", "split"]).agg(
    fires    = ("entry_date", "count"),
    hit_rate = ("correct_4w", lambda x: (x == "YES").sum() / len(x) * 100),
    avg_ret  = ("ret_4w_pct", "mean"),
).round(1)
print(summary.to_string())
print(f"\nSaved to: results/signal_fires.csv")
print(f"\nHow to use:")
print(f"  For each row, go to the chart of that asset on entry_date.")
print(f"  Note whether a TA entry (pullback, key level, pattern) was available")
print(f"  within the week before entry_date.")
print(f"  Compare your TA entry result vs the mechanical ret_4w_pct.")
print(f"  If TA entries consistently improve the outcome, the execution layer adds edge.")
