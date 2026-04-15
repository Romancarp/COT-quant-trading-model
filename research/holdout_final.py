"""Final holdout evaluation — nr_net_rank > 0.85 threshold, 4w, 7 assets.

Run once. Accept the result.
Contamination note: holdout rows for this signal were never previously examined.
Prior holdout test (sig_mean_reversion) fired 1 trade and was uninformative.
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
from research.evaluation import _split_indices, _max_drawdown

ASSETS  = ["EUR", "CAD", "JPY", "AUD", "GBP", "USD", "PLATINUM"]
SIGNAL  = "nr_net_rank"
CUTOFF  = 0.85
HORIZON = 4

def evaluate(signal: pd.Series, target: pd.Series, sl: slice) -> dict:
    s = signal.iloc[sl]; t = target.iloc[sl]
    both = pd.concat([s, t], axis=1).dropna()
    both.columns = ["s", "t"]
    n = len(both)
    if n < 5:
        return dict(IC=np.nan, tstat=np.nan, hit=np.nan, avg_ret=np.nan,
                    sharpe=np.nan, max_dd=np.nan, n=n, n_trig=0)
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
    if n_trig >= 3:
        ss = np.sign(trig["s"])
        hit = (ss == np.sign(trig["t"])).mean()
        signed = ss * trig["t"]
        avg_ret = signed.mean()
        std_ret = signed.std(ddof=1)
        sharpe = avg_ret / std_ret * math.sqrt(52) if std_ret > 0 else np.nan
        max_dd = _max_drawdown(signed)
    else:
        hit = avg_ret = sharpe = max_dd = np.nan
    return dict(IC=float(ic), tstat=float(tstat),
                hit=float(hit) if not np.isnan(hit) else np.nan,
                avg_ret=float(avg_ret) if not np.isnan(avg_ret) else np.nan,
                sharpe=float(sharpe) if not np.isnan(sharpe) else np.nan,
                max_dd=float(max_dd) if not np.isnan(max_dd) else np.nan,
                n=n, n_trig=n_trig)

print("=" * 70)
print("FINAL HOLDOUT  —  nr_net_rank > 0.85  |  4w  |  Accept the result")
print("=" * 70)

# Also show OOS side-by-side for comparison
results = []
for asset in ASSETS:
    panel = build_panel(asset)
    if panel.empty: continue
    signals_df = compute_all_signals(panel)
    targets_df = compute_targets(panel)

    raw = signals_df[SIGNAL]
    tgt = targets_df[f"fwd_ret_{HORIZON}w"]

    sig = pd.Series(0.0, index=raw.index)
    sig[raw >= CUTOFF]       = -1.0   # high NR long = dumb money = bearish
    sig[raw <= (1 - CUTOFF)] =  1.0

    n = len(panel)
    _, oos_sl, hold_sl = _split_indices(n)

    hold_dates = panel["report_date"].iloc[hold_sl]
    date_range = f"{str(hold_dates.iloc[0])[:10]} to {str(hold_dates.iloc[-1])[:10]}"

    r_oos  = evaluate(sig, tgt, oos_sl)
    r_hold = evaluate(sig, tgt, hold_sl)

    results.append(dict(asset=asset, date_range=date_range, **{f"hold_{k}": v for k, v in r_hold.items()},
                        **{f"oos_{k}": v for k, v in r_oos.items()}))

    print(f"\n  {asset}  holdout: {date_range}  (n={r_hold['n']}, trades={r_hold['n_trig']})")
    hit_h = f"{r_hold['hit']*100:.1f}%" if not np.isnan(r_hold.get('hit', np.nan)) else "n/a"
    hit_o = f"{r_oos['hit']*100:.1f}%"  if not np.isnan(r_oos.get('hit', np.nan))  else "n/a"
    print(f"    {'':10} {'IC':>7}  {'t':>6}  {'Hit':>6}  {'Trades':>7}")
    print(f"    {'OOS':10} {r_oos['IC']:>+7.3f}  {r_oos['tstat']:>+6.2f}  {hit_o:>6}  {r_oos['n_trig']:>7}")
    print(f"    {'HOLDOUT':10} {r_hold['IC']:>+7.3f}  {r_hold['tstat']:>+6.2f}  {hit_h:>6}  {r_hold['n_trig']:>7}  << final verdict")

df = pd.DataFrame(results)
print(f"\n{'='*70}")
print("AGGREGATE")
print(f"{'='*70}")
for split, prefix in [("OOS", "oos"), ("HOLDOUT", "hold")]:
    ics    = df[f"{prefix}_IC"].dropna()
    hits   = df[f"{prefix}_hit"].dropna()
    trades = df[f"{prefix}_n_trig"].sum()
    print(f"\n  {split}:")
    print(f"    Mean IC         : {ics.mean():>+.3f}")
    print(f"    % assets pos IC : {(ics > 0).mean()*100:.0f}%")
    print(f"    Mean hit rate   : {hits.mean()*100:.1f}%")
    print(f"    Total trades    : {trades}")

print(f"\n  OOS period  ~2.5 years  |  Holdout period ~15 months")
print(f"  Significance note: holdout has ~8 trades/asset — use direction not magnitude")
