"""Find the threshold level that hits ~24 trades/year with highest IC.

Tests nc_cot_index_52w and nr_net_rank at several cutoff levels.
Shows trades/year (portfolio total), IC, and hit rate per threshold.
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
CUTOFFS = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90]

def evaluate(signal: pd.Series, target: pd.Series, sl: slice) -> dict:
    s = signal.iloc[sl]; t = target.iloc[sl]
    both = pd.concat([s, t], axis=1).dropna()
    both.columns = ["s", "t"]
    n = len(both)
    if n < 5:
        return dict(IC=np.nan, tstat=np.nan, hit=np.nan, n_trig=0, trig_rate=0)
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
    hit = (np.sign(trig["s"]) == np.sign(trig["t"])).mean() if n_trig >= 5 else np.nan
    return dict(IC=float(ic), tstat=float(tstat), hit=float(hit) if not np.isnan(hit) else np.nan,
                n_trig=n_trig, trig_rate=n_trig/n)

# Load panels once
panels = {}
signals_all = {}
targets_all = {}
for asset in ASSETS:
    p = build_panel(asset)
    if p.empty: continue
    panels[asset] = p
    signals_all[asset] = compute_all_signals(p)
    targets_all[asset] = compute_targets(p)

SIGNAL_CONFIGS = [
    ("nc_cot_index_52w", "NC COT Index 52w", False),  # high = NC very long = bearish
    ("nr_net_rank",      "NR Net Rank (contrarian)", False),  # high NR long = bearish
    ("comm_net_rank",    "Commercial Net Rank", True),   # high comm long = bullish, so invert threshold
]

for sig_col, label, invert in SIGNAL_CONFIGS:
    print(f"\n{'='*80}")
    print(f"{label}  |  4w horizon  |  OOS only")
    print(f"{'='*80}")
    print(f"{'Cutoff':<10} {'Trades/yr':>10} {'Mean IC':>9} {'% pos IC':>9} "
          f"{'Mean |t|':>9} {'Hit%':>7} {'Trades avail':>13}")
    print("-"*80)

    for cutoff in CUTOFFS:
        ics, tstats, hits, trade_counts = [], [], [], []
        for asset in panels:
            _, oos_sl, _ = _split_indices(len(panels[asset]))
            raw = signals_all[asset][sig_col]
            tgt = targets_all[asset][f"fwd_ret_{HORIZON}w"]

            sig = pd.Series(0.0, index=raw.index)
            if invert:
                sig[raw >= cutoff]       =  1.0
                sig[raw <= (1 - cutoff)] = -1.0
            else:
                sig[raw >= cutoff]       = -1.0
                sig[raw <= (1 - cutoff)] =  1.0

            r = evaluate(sig, tgt, oos_sl)
            ics.append(r["IC"])
            tstats.append(abs(r["tstat"]))
            hits.append(r["hit"])
            # trades/yr per asset: trigger_rate × 52 / 4 (independent 4w entries)
            trade_counts.append(r["trig_rate"] * 52 / HORIZON)

        mean_ic   = np.nanmean(ics)
        pct_pos   = np.mean([v > 0 for v in ics if not np.isnan(v)]) * 100
        mean_t    = np.nanmean(tstats)
        mean_hit  = np.nanmean([h for h in hits if not np.isnan(h)]) * 100
        total_trd = sum(trade_counts)

        print(f"  >{cutoff:.2f}/<{1-cutoff:.2f}   {total_trd:>10.1f} {mean_ic:>+9.3f} "
              f"{pct_pos:>8.0f}% {mean_t:>9.2f} {mean_hit:>6.1f}% "
              f"   [target=24]")

    # Per-asset detail at the cutoff closest to 24 trades/yr
    print(f"\n  Per-asset at cutoff 0.80 (closest to target):")
    print(f"  {'Asset':<10} {'IC':>7} {'t':>7} {'Hit%':>7} {'Trades/yr':>10}")
    for asset in panels:
        _, oos_sl, _ = _split_indices(len(panels[asset]))
        raw = signals_all[asset][sig_col]
        tgt = targets_all[asset][f"fwd_ret_{HORIZON}w"]
        sig = pd.Series(0.0, index=raw.index)
        cutoff = 0.80
        if invert:
            sig[raw >= cutoff] = 1.0; sig[raw <= (1-cutoff)] = -1.0
        else:
            sig[raw >= cutoff] = -1.0; sig[raw <= (1-cutoff)] = 1.0
        r = evaluate(sig, tgt, oos_sl)
        hit = f"{r['hit']*100:.1f}" if not np.isnan(r["hit"]) else "  n/a"
        trd = r["trig_rate"] * 52 / HORIZON
        print(f"    {asset:<8} IC={r['IC']:>+.3f}  t={r['tstat']:>+.2f}  "
              f"hit={hit}  trades/yr={trd:.1f}")
