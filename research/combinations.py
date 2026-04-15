"""Pairwise and triple signal combination testing.

For each combination of 2 or 3 trigger signals:
  - composite = mean(signals) where at least one signal != 0, else 0
  - evaluated with the same metrics as individual signals
  - results ranked by OOS IC per asset per horizon

C(14,2) = 91 pairs  +  C(14,3) = 364 triples  =  455 combinations total
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from research.evaluation import evaluate_signal
from research.signals import TRIGGER_SIGNALS


def _composite_signal(signals_df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Mean of selected signal columns; 0 where all are zero."""
    sub = signals_df[cols].copy()
    any_nonzero = (sub != 0).any(axis=1)
    composite = sub.mean(axis=1)
    composite[~any_nonzero] = 0.0
    return composite


def test_combinations(
    signals_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    horizons: list[int],
    max_k: int = 3,
) -> pd.DataFrame:
    """Test all k=2 and k=3 combinations of TRIGGER_SIGNALS.

    Returns a long-format DataFrame with columns:
        combo, k, signal_list, horizon, split, IC, IC_tstat,
        hit_rate, avg_ret, sharpe, max_dd, trigger_rate, n_obs
    """
    available = [s for s in TRIGGER_SIGNALS if s in signals_df.columns]
    rows = []

    for k in range(2, max_k + 1):
        for combo in combinations(available, k):
            combo_name = "+".join(combo)
            composite = _composite_signal(signals_df, list(combo))
            for h in horizons:
                tgt_col = f"fwd_ret_{h}w"
                if tgt_col not in targets_df.columns:
                    continue
                tgt = targets_df[tgt_col]
                for split in ("is", "oos"):
                    result = evaluate_signal(composite, tgt, h, split)
                    result["combo"] = combo_name
                    result["k"] = k
                    result["signal_list"] = list(combo)
                    rows.append(result)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    cols = ["combo", "k", "signal_list", "horizon", "split",
            "IC", "IC_tstat", "hit_rate", "avg_ret", "sharpe",
            "max_dd", "trigger_rate", "n_obs"]
    return df[cols]


def top_combinations(
    combo_results: pd.DataFrame,
    n_top: int = 5,
) -> pd.DataFrame:
    """Return the top N combinations per horizon ranked by OOS IC."""
    oos = combo_results[combo_results["split"] == "oos"].copy()
    oos["abs_IC"] = oos["IC"].abs()
    top = (
        oos.sort_values("abs_IC", ascending=False)
        .groupby("horizon")
        .head(n_top)
        .drop(columns=["abs_IC"])
        .reset_index(drop=True)
    )
    return top
