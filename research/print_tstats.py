"""Print OOS t-stats for top signals per asset to assess statistical significance.

Run: python -m research.print_tstats
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from config import SOURCE_ASSETS_ORDER
from research.data_loader import build_panel
from research.signals import compute_all_signals, ALL_SIGNALS
from research.targets import compute_targets
from research.evaluation import evaluate_all

HORIZONS = [1, 2, 4, 6, 8]

rows = []
for asset in SOURCE_ASSETS_ORDER:
    panel = build_panel(asset)
    if panel.empty:
        continue
    signals_df = compute_all_signals(panel)
    targets_df = compute_targets(panel)
    results = evaluate_all(signals_df, targets_df, ALL_SIGNALS, HORIZONS)
    oos = results[results["split"] == "oos"].copy()
    oos["asset"] = asset
    rows.append(oos)

df = pd.concat(rows, ignore_index=True)

# Filter to OOS, rank by |IC_tstat|
df["abs_tstat"] = df["IC_tstat"].abs()
df["sig_flag"] = df["abs_tstat"].apply(
    lambda t: "***" if t >= 2.58 else ("**" if t >= 1.96 else ("*" if t >= 1.65 else ""))
)

# Show only rows with |t| >= 1.65 (at least marginally significant)
sig = df[df["abs_tstat"] >= 1.65].copy()
sig = sig.sort_values("abs_tstat", ascending=False)

print(f"\n{'='*80}")
print("OOS Significant Signals  (* p<0.10  ** p<0.05  *** p<0.01, Newey-West HAC)")
print(f"{'='*80}")
print(f"{'Asset':<10} {'Signal':<35} {'Hor':<5} {'IC':>7} {'t-stat':>8} {'Hit%':>6} {'n':>5}  {'Sig'}")
print("-"*80)

for _, r in sig.iterrows():
    hit = f"{r['hit_rate']*100:.1f}" if not pd.isna(r["hit_rate"]) else "  n/a"
    print(
        f"{r['asset']:<10} {r['signal']:<35} {r['horizon']:<5} "
        f"{r['IC']:>7.3f} {r['IC_tstat']:>8.2f} {hit:>6} {int(r['n_obs']):>5}  {r['sig_flag']}"
    )

print(f"\nTotal significant: {len(sig)} / {len(df)} (IC threshold: |t|>=1.65)")

# Summary by signal: how many assets does each signal clear significance on?
print(f"\n{'='*60}")
print("Signal breadth — how many assets reach |t|>=1.96 (any horizon)?")
print(f"{'='*60}")
breadth = (
    df[df["abs_tstat"] >= 1.96]
    .groupby("signal")["asset"]
    .nunique()
    .sort_values(ascending=False)
)
for sig_name, count in breadth.items():
    print(f"  {sig_name:<35}  {count} assets")
