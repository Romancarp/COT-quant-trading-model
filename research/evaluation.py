"""Per-signal evaluation metrics with train/test split.

Split:
    in-sample (IS)  : first 70% of rows
    out-of-sample   : next 20% of rows
    hold-out        : final 10% — never used here

Metrics per signal × horizon:
    IC          Spearman rank correlation (all non-NaN rows)
    IC_tstat    Newey-West HAC adjusted t-statistic
    hit_rate    % of triggered rows where sign(signal) == sign(fwd_ret)
    avg_ret     mean(signal_sign * fwd_ret) on triggered rows
    sharpe      annualised Sharpe of the simple long/short strategy
    max_dd      maximum drawdown of cumulative strategy returns
    trigger_rate fraction of rows where signal != 0
    n_obs       number of valid observations used
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr


def _split_indices(n: int) -> tuple[slice, slice, slice]:
    is_end = int(n * 0.70)
    oos_end = int(n * 0.90)
    return slice(0, is_end), slice(is_end, oos_end), slice(oos_end, None)


def _max_drawdown(returns: pd.Series) -> float:
    returns = returns.dropna()
    if returns.empty:
        return float("nan")
    cum = (1 + returns).cumprod()
    roll_max = cum.expanding().max()
    dd = cum / roll_max - 1
    return float(dd.min())


def _ic_tstat_nw(signal: pd.Series, target: pd.Series, maxlags: int) -> float:
    """Newey-West HAC adjusted t-stat for the signal coefficient."""
    df = pd.concat([signal, target], axis=1).dropna()
    if len(df) < maxlags + 5:
        return float("nan")
    y = df.iloc[:, 1].values
    x = sm.add_constant(df.iloc[:, 0].values)
    try:
        model = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
        return float(model.tvalues[1])
    except Exception:
        return float("nan")


def evaluate_signal(
    signal: pd.Series,
    target: pd.Series,
    horizon: int,
    split: str = "is",
) -> dict:
    """Evaluate one signal against one forward-return target on a data slice.

    Parameters
    ----------
    signal  : signal values (any float, NaN where unavailable)
    target  : forward return values
    horizon : number of weeks ahead (used for Newey-West lag)
    split   : 'is' | 'oos' | 'holdout'
    """
    n = len(signal)
    is_sl, oos_sl, hold_sl = _split_indices(n)
    sl = {"is": is_sl, "oos": oos_sl, "holdout": hold_sl}[split]

    sig = signal.iloc[sl].copy()
    tgt = target.iloc[sl].copy()

    # align and drop NaN
    both = pd.concat([sig, tgt], axis=1).dropna()
    both.columns = ["sig", "tgt"]
    n_obs = len(both)

    if n_obs < 10:
        return _empty_result(split, horizon, n_obs)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ic_val, _ = spearmanr(both["sig"], both["tgt"])
    ic_tstat = _ic_tstat_nw(both["sig"], both["tgt"], maxlags=horizon)

    # triggered rows only (signal != 0)
    triggered = both[both["sig"] != 0].copy()
    n_triggered = len(triggered)
    trigger_rate = n_triggered / n_obs if n_obs > 0 else float("nan")

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
        hit_rate = float("nan")
        avg_ret = float("nan")
        sharpe = float("nan")
        max_dd = float("nan")

    return {
        "split": split,
        "horizon": f"{horizon}w",
        "IC": round(float(ic_val), 4) if not math.isnan(ic_val) else float("nan"),
        "IC_tstat": round(float(ic_tstat), 3),
        "hit_rate": round(hit_rate, 4) if not math.isnan(hit_rate) else float("nan"),
        "avg_ret": round(avg_ret, 5) if not math.isnan(avg_ret) else float("nan"),
        "sharpe": round(sharpe, 3) if not math.isnan(sharpe) else float("nan"),
        "max_dd": round(max_dd, 4) if not math.isnan(max_dd) else float("nan"),
        "trigger_rate": round(trigger_rate, 4),
        "n_obs": n_obs,
    }


def _empty_result(split: str, horizon: int, n_obs: int) -> dict:
    return {
        "split": split,
        "horizon": f"{horizon}w",
        "IC": float("nan"),
        "IC_tstat": float("nan"),
        "hit_rate": float("nan"),
        "avg_ret": float("nan"),
        "sharpe": float("nan"),
        "max_dd": float("nan"),
        "trigger_rate": float("nan"),
        "n_obs": n_obs,
    }


def evaluate_all(
    signals_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    signal_cols: list[str],
    horizons: list[int],
) -> pd.DataFrame:
    """Run evaluate_signal for every (signal, horizon, split) combination.

    Returns a long-format DataFrame with columns:
        signal, horizon, split, IC, IC_tstat, hit_rate, avg_ret,
        sharpe, max_dd, trigger_rate, n_obs
    """
    from research.targets import HORIZONS as DEFAULT_HORIZONS

    rows = []
    for sig_col in signal_cols:
        sig = signals_df[sig_col]
        for h in horizons:
            tgt_col = f"fwd_ret_{h}w"
            if tgt_col not in targets_df.columns:
                continue
            tgt = targets_df[tgt_col]
            for split in ("is", "oos"):
                result = evaluate_signal(sig, tgt, h, split)
                result["signal"] = sig_col
                rows.append(result)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    cols = ["signal", "horizon", "split", "IC", "IC_tstat", "hit_rate",
            "avg_ret", "sharpe", "max_dd", "trigger_rate", "n_obs"]
    return df[cols]
