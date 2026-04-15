"""Compare Option 1 (continuous rank) vs Option 2 (relaxed mean reversion).

OOS slice only. Universe: EUR, CAD, JPY, AUD, GBP, USD, PLATINUM. Horizon: 4w.
"""
from __future__ import annotations
import sys, math, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm

from research.data_loader import build_panel
from research.signals import compute_all_signals
from research.targets import compute_targets
from research.evaluation import _split_indices

ASSETS  = ["EUR", "CAD", "JPY", "AUD", "GBP", "USD", "PLATINUM"]
HORIZON = 4

def ic_stats(signal: pd.Series, target: pd.Series, sl: slice) -> dict:
    sig = signal.iloc[sl]
    tgt = target.iloc[sl]
    both = pd.concat([sig, tgt], axis=1).dropna()
    both.columns = ["s", "t"]
    n = len(both)
    if n < 10:
        return dict(IC=np.nan, tstat=np.nan, hit=np.nan, trigger=np.nan, n=n, n_trig=0)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ic, _ = spearmanr(both["s"], both["t"])

    y, x = both["t"].values, sm.add_constant(both["s"].values)
    try:
        tstat = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": HORIZON}).tvalues[1]
    except Exception:
        tstat = np.nan

    trig = both[both["s"] != 0]
    n_trig = len(trig)
    trigger = n_trig / n
    hit = (np.sign(trig["s"]) == np.sign(trig["t"])).mean() if n_trig >= 5 else np.nan
    return dict(IC=round(float(ic),3), tstat=round(float(tstat),2),
                hit=round(float(hit),3) if not np.isnan(hit) else np.nan,
                trigger=round(trigger,3), n=n, n_trig=n_trig)

def relaxed_mean_rev(panel: pd.DataFrame, z_thresh: float, chg_thresh: float) -> pd.Series:
    """Recompute sig_mean_reversion with custom thresholds."""
    net = panel["net_pos"]
    zscore = (net - net.rolling(52).mean()) / net.rolling(52).std()
    chg    = net.diff(1)
    chg_z  = (chg - chg.rolling(52).mean()) / chg.rolling(52).std()
    sig = pd.Series(0.0, index=panel.index)
    bear = (zscore.shift(1) >=  z_thresh) & (chg_z <= -chg_thresh)
    bull = (zscore.shift(1) <= -z_thresh) & (chg_z >=  chg_thresh)
    sig[bear] = -1.0
    sig[bull] =  1.0
    return sig.fillna(0)

def rank_threshold(panel: pd.DataFrame, col: str, cutoff: float) -> pd.Series:
    """Binary signal from continuous rank: +1 if rank < (1-cutoff), -1 if rank > cutoff."""
    signals_df = compute_all_signals(panel)
    rank = signals_df[col]
    sig = pd.Series(0.0, index=panel.index)
    sig[rank >= cutoff] = -1.0       # extreme long NC → bearish
    sig[rank <= (1 - cutoff)] = 1.0  # extreme short NC → bullish
    return sig

# --- variants to test ---
VARIANTS = [
    # (label, type, params)
    ("MeanRev z=2.0 chg=1.5 [original]", "meanrev", (2.0, 1.5)),
    ("MeanRev z=1.5 chg=1.0 [relaxed]",  "meanrev", (1.5, 1.0)),
    ("MeanRev z=1.5 chg=1.5 [moderate]", "meanrev", (1.5, 1.5)),
    ("MeanRev z=1.0 chg=0.5 [loose]",    "meanrev", (1.0, 0.5)),
    ("nc_cot_index_52w > 0.80",           "rank",    ("nc_cot_index_52w", 0.80)),
    ("nc_cot_index_52w > 0.75",           "rank",    ("nc_cot_index_52w", 0.75)),
    ("nr_net_rank > 0.75 [contrarian]",   "rank",    ("nr_net_rank", 0.75)),
    ("nr_net_rank > 0.70 [contrarian]",   "rank",    ("nr_net_rank", 0.70)),
]

rows = []
for asset in ASSETS:
    panel = build_panel(asset)
    if panel.empty:
        continue
    signals_df = compute_all_signals(panel)
    targets_df = compute_targets(panel)
    tgt = targets_df[f"fwd_ret_{HORIZON}w"]
    _, oos_sl, _ = _split_indices(len(panel))

    for label, vtype, params in VARIANTS:
        if vtype == "meanrev":
            sig = relaxed_mean_rev(panel, *params)
        else:
            col, cutoff = params
            # nr_net_rank is inverted: high nr = dumb money long = bearish
            rank = signals_df[col]
            sig = pd.Series(0.0, index=panel.index)
            if col == "nr_net_rank":
                sig[rank >= cutoff]       = -1.0
                sig[rank <= (1 - cutoff)] =  1.0
            else:
                sig[rank >= cutoff]       = -1.0
                sig[rank <= (1 - cutoff)] =  1.0

        r = ic_stats(sig, tgt, oos_sl)
        r["asset"]   = asset
        r["variant"] = label
        rows.append(r)

df = pd.DataFrame(rows)

# --- summary table per variant ---
print(f"\n{'='*95}")
print(f"OOS COMPARISON — IC, trigger rate, trades/year  (7 assets, 4w horizon, ~128 OOS weeks each)")
print(f"{'='*95}")
print(f"{'Variant':<42} {'Mean IC':>8} {'% pos IC':>9} {'Mean |t|':>9} "
      f"{'Trig%':>7} {'Trades/yr':>10} {'Hit%':>7}")
print("-"*95)

for label, _, _ in VARIANTS:
    sub = df[df["variant"] == label].copy()
    mean_ic   = sub["IC"].mean()
    pct_pos   = (sub["IC"] > 0).mean() * 100
    mean_t    = sub["tstat"].abs().mean()
    mean_trig = sub["trigger"].mean() * 100
    # trades/yr per asset: trigger_rate × 52 weeks / 4w hold = independent entries
    trades_yr = sub["trigger"].mean() * 52 / HORIZON
    mean_hit  = sub["hit"].mean() * 100 if sub["hit"].notna().any() else float("nan")
    print(f"  {label:<40} {mean_ic:>+8.3f} {pct_pos:>8.0f}% {mean_t:>9.2f} "
          f"{mean_trig:>6.1f}% {trades_yr:>10.1f} {mean_hit:>6.1f}%")

# --- per-asset detail for key variants ---
KEY = ["MeanRev z=1.5 chg=1.0 [relaxed]", "nr_net_rank > 0.75 [contrarian]"]
for label in KEY:
    sub = df[df["variant"] == label]
    print(f"\n  Detail: {label}")
    print(f"  {'Asset':<12} {'IC':>7} {'t':>7} {'Hit%':>7} {'Trig%':>7} {'OOS trades':>11}")
    for _, r in sub.iterrows():
        hit = f"{r['hit']*100:.1f}" if not np.isnan(r["hit"]) else "  n/a"
        print(f"    {r['asset']:<10} {r['IC']:>+7.3f} {r['tstat']:>+7.2f} "
              f"{hit:>7} {r['trigger']*100:>6.1f}% {r['n_trig']:>10}")
