"""Screen for signals with high OOS IC and sufficient trade frequency.

Uses continuous signals (no threshold) — IC measured on raw signal values.
Shows results at each horizon so the IC vs frequency tradeoff is visible.
"""
from __future__ import annotations
import sys, math, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm

from config import SOURCE_ASSETS_ORDER
from research.data_loader import build_panel
from research.signals import compute_all_signals, ALL_SIGNALS
from research.targets import compute_targets
from research.evaluation import _split_indices

HORIZONS = [1, 2, 4, 6, 8]

def oos_ic(signal: pd.Series, target: pd.Series, horizon: int) -> tuple[float, float, int]:
    n = len(signal)
    _, oos_sl, _ = _split_indices(n)
    s = signal.iloc[oos_sl]
    t = target.iloc[oos_sl]
    both = pd.concat([s, t], axis=1).dropna()
    if len(both) < 10:
        return np.nan, np.nan, 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ic, _ = spearmanr(both.iloc[:,0], both.iloc[:,1])
    y, x = both.iloc[:,1].values, sm.add_constant(both.iloc[:,0].values)
    try:
        tstat = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": horizon}).tvalues[1]
    except Exception:
        tstat = np.nan
    return float(ic), float(tstat), len(both)

rows = []
for asset in SOURCE_ASSETS_ORDER:
    panel = build_panel(asset)
    if panel.empty:
        continue
    signals_df = compute_all_signals(panel)
    targets_df = compute_targets(panel)
    for sig_col in ALL_SIGNALS:
        for h in HORIZONS:
            tgt_col = f"fwd_ret_{h}w"
            if tgt_col not in targets_df.columns:
                continue
            ic, tstat, n = oos_ic(signals_df[sig_col], targets_df[tgt_col], h)
            rows.append(dict(asset=asset, signal=sig_col, horizon=h,
                             IC=ic, tstat=tstat, n=n))

df = pd.DataFrame(rows)
df["abs_IC"] = df["IC"].abs()
df["abs_t"]  = df["tstat"].abs()

# Trades per year proxy: continuous signals are always "on" — effective independent
# entries per year = 52 / horizon (one position at a time, refreshed each horizon)
df["trades_yr"] = 52 / df["horizon"]

# --- Screen: |IC| > 0.25 AND |t| > 2.0, any horizon ---
screen = df[(df["abs_IC"] >= 0.25) & (df["abs_t"] >= 2.0)].copy()
screen = screen.sort_values(["abs_IC", "abs_t"], ascending=False)

print(f"\n{'='*85}")
print(f"SIGNALS WITH |OOS IC| >= 0.25 AND |t| >= 2.0  (continuous signal, all assets/horizons)")
print(f"{'='*85}")
print(f"{'Asset':<10} {'Signal':<35} {'Hor':>4} {'IC':>7} {'t':>7} {'Trades/yr':>10}")
print("-"*85)
for _, r in screen.iterrows():
    print(f"  {r['asset']:<8} {r['signal']:<35} {r['horizon']:>3}w {r['IC']:>+7.3f} "
          f"{r['tstat']:>+7.2f} {r['trades_yr']:>10.1f}")

# --- Summary: how many asset×signal pairs hit the screen at each horizon? ---
print(f"\n{'='*60}")
print("Pairs passing |IC|>=0.25 AND |t|>=2.0 by horizon")
print(f"{'='*60}")
for h in HORIZONS:
    sub = screen[screen["horizon"] == h]
    trades = 52 / h
    print(f"  {h}w ({trades:.0f} trades/yr): {len(sub):3d} pairs  "
          f"mean |IC|={sub['abs_IC'].mean():.3f}")

# --- For 4w specifically: what's available? ---
print(f"\n{'='*70}")
print("All 4w results |IC|>=0.20 AND |t|>=1.96 — the best available at 4w")
print(f"{'='*70}")
f4 = df[(df["horizon"]==4) & (df["abs_IC"]>=0.20) & (df["abs_t"]>=1.96)].sort_values("abs_IC", ascending=False)
for _, r in f4.iterrows():
    print(f"  {r['asset']:<10} {r['signal']:<35} IC={r['IC']:>+.3f}  t={r['tstat']:>+.2f}")
