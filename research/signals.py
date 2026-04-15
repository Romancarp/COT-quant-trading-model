"""All 16 COT-derived signals.

Each signal is a column in the returned DataFrame, aligned to the panel index.
All computations use only data available at or before report_date (rolling lookback).
No forward-looking data is used.

Signal categories
-----------------
Building blocks (continuous, not used in combo testing):
    nc_net_zscore, nc_cot_index_52w, nc_cot_index_156w,
    nc_net_chg, nc_net_chg_zscore, oi_rank, oi_chg_zscore,
    commit_ratio_rank, comm_net_rank, nr_net_rank

Trigger signals (used in combination testing, values: -1 / 0 / +1 or continuous):
    sig_momentum, sig_mean_reversion, sig_uncrowded_breakout,
    sig_oi_momentum, sig_cot_extreme_52w, sig_cot_extreme_156w,
    sig_commitment_extreme, sig_streak, sig_oi_accel,
    sig_nc_nr_divergence, sig_comm_nc_divergence, sig_zero_cross,
    sig_price_pos_divergence, sig_commercial_extreme
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Signals included in the combination testing pool
TRIGGER_SIGNALS = [
    "sig_momentum",
    "sig_mean_reversion",
    "sig_uncrowded_breakout",
    "sig_oi_momentum",
    "sig_cot_extreme_52w",
    "sig_cot_extreme_156w",
    "sig_commitment_extreme",
    "sig_streak",
    "sig_oi_accel",
    "sig_nc_nr_divergence",
    "sig_comm_nc_divergence",
    "sig_zero_cross",
    "sig_price_pos_divergence",
    "sig_commercial_extreme",
]

# All signals (building blocks + triggers)
ALL_SIGNALS = [
    "nc_net_zscore",
    "nc_cot_index_52w",
    "nc_cot_index_156w",
    "nc_net_chg",
    "nc_net_chg_zscore",
    "oi_rank",
    "oi_chg_zscore",
    "commit_ratio_rank",
    "comm_net_rank",
    "nr_net_rank",
] + TRIGGER_SIGNALS


def _streak(series: pd.Series) -> pd.Series:
    """Compute signed consecutive-direction streak for a change series."""
    direction = np.sign(series)
    streak = pd.Series(0.0, index=series.index)
    for i in range(1, len(direction)):
        d = direction.iloc[i]
        if d == 0 or np.isnan(d):
            streak.iloc[i] = 0.0
        elif d == direction.iloc[i - 1]:
            streak.iloc[i] = streak.iloc[i - 1] + d
        else:
            streak.iloc[i] = d
    return streak


def compute_all_signals(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute all signals from a panel produced by data_loader.build_panel().

    Returns a DataFrame with one column per signal, same index as panel.
    NaN where insufficient history exists for rolling windows.
    """
    MP = 26  # min_periods for 52-week rolling ops

    net = panel["net_pos"].copy()
    long_ = panel["long_pos"].copy()
    short_ = panel["short_pos"].copy()
    oi = panel["open_interest"].copy()
    close = panel["close"].copy()
    comm_net = panel["net_pos_comm"].copy()
    nr_net = panel["net_pos_nr"].copy()

    out = pd.DataFrame(index=panel.index)

    # ------------------------------------------------------------------ #
    # Building blocks                                                      #
    # ------------------------------------------------------------------ #

    roll52_mean = net.rolling(52, min_periods=MP).mean()
    roll52_std = net.rolling(52, min_periods=MP).std(ddof=1)
    out["nc_net_zscore"] = (net - roll52_mean) / roll52_std.replace(0, np.nan)

    out["nc_cot_index_52w"] = net.rolling(52, min_periods=MP).rank(pct=True)
    out["nc_cot_index_156w"] = net.rolling(156, min_periods=52).rank(pct=True)

    out["nc_net_chg"] = net.diff(1)

    chg = out["nc_net_chg"]
    chg_mean = chg.rolling(52, min_periods=MP).mean()
    chg_std = chg.rolling(52, min_periods=MP).std(ddof=1)
    out["nc_net_chg_zscore"] = (chg - chg_mean) / chg_std.replace(0, np.nan)

    out["oi_rank"] = oi.rolling(52, min_periods=MP).rank(pct=True)

    oi_pct_chg = oi.pct_change(1)
    oi_pc_mean = oi_pct_chg.rolling(52, min_periods=MP).mean()
    oi_pc_std = oi_pct_chg.rolling(52, min_periods=MP).std(ddof=1)
    out["oi_chg_zscore"] = (oi_pct_chg - oi_pc_mean) / oi_pc_std.replace(0, np.nan)

    denom = (long_ + short_).replace(0, np.nan)
    commit_ratio = long_ / denom
    out["commit_ratio_rank"] = commit_ratio.rolling(52, min_periods=MP).rank(pct=True)

    out["comm_net_rank"] = comm_net.rolling(52, min_periods=MP).rank(pct=True)
    out["nr_net_rank"] = nr_net.rolling(52, min_periods=MP).rank(pct=True)

    # ------------------------------------------------------------------ #
    # Trigger signals                                                      #
    # ------------------------------------------------------------------ #

    nc_zscore = out["nc_net_zscore"]
    nc_idx52 = out["nc_cot_index_52w"]
    nc_idx156 = out["nc_cot_index_156w"]
    net_chg_z = out["nc_net_chg_zscore"]
    oi_rnk = out["oi_rank"]
    oi_chg_z = out["oi_chg_zscore"]
    cr_rank = out["commit_ratio_rank"]
    comm_rank = out["comm_net_rank"]
    nr_rank = out["nr_net_rank"]

    # Signal 1: Momentum with high/low rank
    sig_mom = np.where(
        (net_chg_z >= 1.5) & (nc_idx52 >= 0.75), 1.0,
        np.where(
            (net_chg_z <= -1.5) & (nc_idx52 <= 0.25), -1.0, 0.0
        )
    )
    out["sig_momentum"] = pd.Series(sig_mom, index=panel.index)

    # Signal 2: Mean reversion — extreme positioning then reversal
    prev_zscore = nc_zscore.shift(1)
    sig_mr = np.where(
        (prev_zscore >= 2.0) & (net_chg_z <= -1.5), -1.0,
        np.where(
            (prev_zscore <= -2.0) & (net_chg_z >= 1.5), 1.0, 0.0
        )
    )
    out["sig_mean_reversion"] = pd.Series(sig_mr, index=panel.index)

    # Signal 3: Uncrowded breakout — large change while positioning is neutral
    neutral = (nc_idx52 > 0.30) & (nc_idx52 < 0.70)
    sig_ub = np.where(
        neutral & (net_chg_z >= 1.5), 1.0,
        np.where(
            neutral & (net_chg_z <= -1.5), -1.0, 0.0
        )
    )
    out["sig_uncrowded_breakout"] = pd.Series(sig_ub, index=panel.index)

    # Signal 4: OI-weighted momentum (continuous)
    out["sig_oi_momentum"] = out["sig_momentum"] * oi_rnk

    # Signal 5: COT extreme 52-week (contrarian)
    sig_ext52 = np.where(
        nc_idx52 >= 0.90, 1.0,
        np.where(nc_idx52 <= 0.10, -1.0, 0.0)
    )
    out["sig_cot_extreme_52w"] = pd.Series(sig_ext52, index=panel.index)

    # Signal 6: COT extreme 156-week (contrarian)
    sig_ext156 = np.where(
        nc_idx156 >= 0.90, 1.0,
        np.where(nc_idx156 <= 0.10, -1.0, 0.0)
    )
    out["sig_cot_extreme_156w"] = pd.Series(sig_ext156, index=panel.index)

    # Signal 7: Commitment ratio extreme
    sig_cr = np.where(
        cr_rank >= 0.90, 1.0,
        np.where(cr_rank <= 0.10, -1.0, 0.0)
    )
    out["sig_commitment_extreme"] = pd.Series(sig_cr, index=panel.index)

    # Signal 8: Positioning streak (≥3 consecutive same-direction weeks)
    streak_raw = _streak(chg)
    out["sig_streak"] = streak_raw.where(streak_raw.abs() >= 3, 0.0)

    # Signal 9: OI acceleration (continuous z-score of OI % change)
    out["sig_oi_accel"] = oi_chg_z

    # Signal 10: NC vs Non-Reportable divergence
    out["sig_nc_nr_divergence"] = nc_idx52 - nr_rank

    # Signal 11: Commercial vs NC divergence (high = commercials long, NC short = bullish)
    out["sig_comm_nc_divergence"] = comm_rank - nc_idx52

    # Signal 12: Net position zero crossing
    prev_net = net.shift(1)
    sig_zc = np.where(
        (prev_net < 0) & (net > 0), 1.0,
        np.where(
            (prev_net > 0) & (net < 0), -1.0, 0.0
        )
    )
    out["sig_zero_cross"] = pd.Series(sig_zc, index=panel.index)

    # Signal 13: Price-positioning divergence
    price_rank = close.rolling(52, min_periods=MP).rank(pct=True)
    net_chg_4w = net_chg_z.rolling(4, min_periods=2).mean()
    sig_ppd = np.where(
        (price_rank >= 0.85) & (net_chg_4w <= -0.5), -1.0,
        np.where(
            (price_rank <= 0.15) & (net_chg_4w >= 0.5), 1.0, 0.0
        )
    )
    out["sig_price_pos_divergence"] = pd.Series(sig_ppd, index=panel.index)

    # Signal 14: Commercial extreme hedging (contrarian)
    sig_comm_ext = np.where(
        comm_rank <= 0.10, 1.0,
        np.where(comm_rank >= 0.90, -1.0, 0.0)
    )
    out["sig_commercial_extreme"] = pd.Series(sig_comm_ext, index=panel.index)

    return out
