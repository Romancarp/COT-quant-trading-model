"""Final holdout evaluation for the committed strategy specification.

Strategy:
    Universe  : EUR, CAD, JPY, AUD, GBP, USD, PLATINUM
    Signal    : sig_mean_reversion
    Horizon   : 4w
    Sizing    : equal weight, one position per asset
    Tested    : signal directional accuracy only (not execution)

This script is run ONCE. Results are the unbiased estimate of signal efficacy.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import math
import warnings
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm

from research.data_loader import build_panel
from research.signals import compute_all_signals
from research.targets import compute_targets
from research.evaluation import _split_indices, _max_drawdown

ASSETS   = ["EUR", "CAD", "JPY", "AUD", "GBP", "USD", "PLATINUM"]
SIGNAL   = "sig_mean_reversion"
HORIZON  = 4

def evaluate_holdout(signal: pd.Series, target: pd.Series) -> dict:
    n = len(signal)
    _, _, hold_sl = _split_indices(n)

    sig = signal.iloc[hold_sl].copy()
    tgt = target.iloc[hold_sl].copy()

    both = pd.concat([sig, tgt], axis=1).dropna()
    both.columns = ["sig", "tgt"]
    n_obs = len(both)

    if n_obs < 10:
        return {"IC": float("nan"), "IC_tstat": float("nan"),
                "hit_rate": float("nan"), "avg_ret": float("nan"),
                "sharpe": float("nan"), "max_dd": float("nan"),
                "trigger_rate": float("nan"), "n_obs": n_obs}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ic_val, _ = spearmanr(both["sig"], both["tgt"])

    # Newey-West HAC t-stat
    df2 = both.copy()
    y = df2["tgt"].values
    x = sm.add_constant(df2["sig"].values)
    try:
        model = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": HORIZON})
        ic_tstat = float(model.tvalues[1])
    except Exception:
        ic_tstat = float("nan")

    triggered = both[both["sig"] != 0].copy()
    n_triggered = len(triggered)
    trigger_rate = n_triggered / n_obs

    if n_triggered >= 5:
        sig_sign = np.sign(triggered["sig"])
        correct = (sig_sign == np.sign(triggered["tgt"])).sum()
        hit_rate = correct / n_triggered
        signed_rets = sig_sign * triggered["tgt"]
        avg_ret = float(signed_rets.mean())
        std_ret = float(signed_rets.std(ddof=1))
        sharpe = (avg_ret / std_ret * math.sqrt(52)) if std_ret > 0 else float("nan")
        max_dd = _max_drawdown(signed_rets)
    else:
        hit_rate = avg_ret = sharpe = max_dd = float("nan")

    return {
        "IC": round(float(ic_val), 4),
        "IC_tstat": round(ic_tstat, 3),
        "hit_rate": round(hit_rate, 4) if not math.isnan(hit_rate) else float("nan"),
        "avg_ret": round(avg_ret, 5) if not math.isnan(avg_ret) else float("nan"),
        "sharpe": round(sharpe, 3) if not math.isnan(sharpe) else float("nan"),
        "max_dd": round(max_dd, 4) if not math.isnan(max_dd) else float("nan"),
        "trigger_rate": round(trigger_rate, 4),
        "n_obs": n_obs,
        "n_triggered": n_triggered,
    }


print("=" * 70)
print("FINAL HOLDOUT EVALUATION — read once, accept the result")
print(f"Signal: {SIGNAL}  |  Horizon: {HORIZON}w  |  Universe: {', '.join(ASSETS)}")
print("=" * 70)

results = []
panels  = {}
for asset in ASSETS:
    panel = build_panel(asset)
    if panel.empty:
        print(f"  {asset}: no data")
        continue
    panels[asset] = panel
    signals_df = compute_all_signals(panel)
    targets_df = compute_targets(panel)

    tgt_col = f"fwd_ret_{HORIZON}w"
    r = evaluate_holdout(signals_df[SIGNAL], targets_df[tgt_col])
    r["asset"] = asset
    results.append(r)

    # holdout date range
    n = len(panel)
    _, _, hold_sl = _split_indices(n)
    hold_dates = panel["report_date"].iloc[hold_sl]
    date_range = f"{str(hold_dates.iloc[0])[:10]} to {str(hold_dates.iloc[-1])[:10]}"
    print(f"\n  {asset}  [{date_range}]  n={r['n_obs']} triggered={r['n_triggered']}")
    print(f"    IC={r['IC']:+.3f}  t={r['IC_tstat']:+.2f}  "
          f"hit={r['hit_rate']*100:.1f}%  avg_ret={r['avg_ret']*100:+.3f}%  "
          f"Sharpe={r['sharpe']:+.2f}  MaxDD={r['max_dd']*100:.1f}%")

# Aggregate
df = pd.DataFrame(results)
valid = df.dropna(subset=["IC"])

print(f"\n{'='*70}")
print("AGGREGATE ACROSS UNIVERSE")
print(f"{'='*70}")
mean_ic      = valid["IC"].mean()
pct_pos_ic   = (valid["IC"] > 0).mean() * 100
mean_hit     = valid["hit_rate"].mean()
mean_sharpe  = valid["sharpe"].mean()
total_trades = valid["n_triggered"].sum()

print(f"  Mean IC           : {mean_ic:+.3f}")
print(f"  % assets pos IC   : {pct_pos_ic:.0f}%")
print(f"  Mean hit rate     : {mean_hit*100:.1f}%")
print(f"  Mean ann. Sharpe  : {mean_sharpe:+.2f}")
print(f"  Total trades fired: {total_trades}")
print(f"\n  Significance guide: |t|>1.65 (*), >1.96 (**), >2.58 (***)")
print(f"  Note: holdout period ~15 months. Low power — direction matters more than magnitude.")
