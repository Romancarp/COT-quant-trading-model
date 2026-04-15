"""COT Research Pipeline — top-level orchestration.

Usage
-----
# Full run (all 19 assets, all signals, all horizons):
    python run_research.py

# Fast smoke test (single asset, single horizon):
    python run_research.py --assets EUR --horizons 1

# Custom subset:
    python run_research.py --assets EUR,GBP,USD --horizons 1,2,4

# Skip FX pair confluence (faster):
    python run_research.py --no-fx-confluence

# Skip combination testing (much faster):
    python run_research.py --no-combinations

Output
------
    results/cot_research.docx
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow project-root imports
sys.path.insert(0, str(Path(__file__).parent))

from config import SOURCE_ASSETS_ORDER
from price_service import ensure_prices
from research.combinations import test_combinations
from research.data_loader import build_panel
from research.evaluation import evaluate_all
from research.report import generate_report
from research.signals import ALL_SIGNALS, TRIGGER_SIGNALS, compute_all_signals
from research.targets import HORIZONS as DEFAULT_HORIZONS, compute_targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run COT signal research pipeline.")
    parser.add_argument(
        "--assets",
        default=",".join(SOURCE_ASSETS_ORDER),
        help="Comma-separated asset list (default: all 19)",
    )
    parser.add_argument(
        "--horizons",
        default=",".join(str(h) for h in DEFAULT_HORIZONS),
        help="Comma-separated forward horizons in weeks (default: 1,2,4)",
    )
    parser.add_argument(
        "--no-combinations",
        action="store_true",
        help="Skip pairwise and triple combination testing",
    )
    parser.add_argument(
        "--no-fx-confluence",
        action="store_true",
        help="Skip FX pair confluence section in report",
    )
    parser.add_argument(
        "--output",
        default="results/cot_research.docx",
        help="Output path for the Word report",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    horizons = [int(h.strip()) for h in args.horizons.split(",") if h.strip()]

    print(f"\nCOT Research Pipeline")
    print(f"Assets : {assets}")
    print(f"Horizons: {horizons}w")
    print(f"Signals : {len(ALL_SIGNALS)} total, {len(TRIGGER_SIGNALS)} in combo pool")
    print()

    # ------------------------------------------------------------------ #
    # Step 0: Verify source contracts for each asset                      #
    # ------------------------------------------------------------------ #
    print("Step 0/4 — Verifying source contracts...")
    from research.verify_contracts import verify_contracts
    verify_contracts(assets)
    print()

    # ------------------------------------------------------------------ #
    # Step 1: Ensure prices are up to date                                #
    # ------------------------------------------------------------------ #
    print("Step 1/4 — Fetching missing price data...")
    for asset in assets:
        n = ensure_prices(asset)
        if n > 0:
            print(f"  {asset}: {n} new price rows")
    print("  Done.\n")

    # ------------------------------------------------------------------ #
    # Step 2: Build panels, compute signals and targets                   #
    # ------------------------------------------------------------------ #
    print("Step 2/4 — Building panels and computing signals...")
    all_panels: dict = {}
    all_signals_map: dict = {}
    all_targets_map: dict = {}

    for asset in assets:
        panel = build_panel(asset)
        if panel.empty:
            print(f"  {asset}: no data, skipping")
            continue

        sigs = compute_all_signals(panel)
        tgts = compute_targets(panel)

        n_is = int(len(panel) * 0.70)
        n_oos = int(len(panel) * 0.90) - n_is
        n_hold = len(panel) - n_is - n_oos
        print(f"  {asset}: {len(panel)} rows  (IS={n_is}, OOS={n_oos}, hold-out={n_hold})")

        all_panels[asset] = panel
        all_signals_map[asset] = sigs
        all_targets_map[asset] = tgts

    print()

    # ------------------------------------------------------------------ #
    # Step 3: Evaluate signals + combinations                             #
    # ------------------------------------------------------------------ #
    print("Step 3/4 — Evaluating signals...")
    all_asset_results: dict = {}
    all_combo_results: dict = {}

    for asset in all_panels:
        sigs = all_signals_map[asset]
        tgts = all_targets_map[asset]

        results = evaluate_all(sigs, tgts, ALL_SIGNALS, horizons)
        all_asset_results[asset] = results

        if not args.no_combinations:
            t0 = time.time()
            combo_results = test_combinations(sigs, tgts, horizons)
            elapsed = time.time() - t0
            all_combo_results[asset] = combo_results
            n_combos = len(combo_results["combo"].unique()) if not combo_results.empty else 0
            print(f"  {asset}: {len(results)} signal evaluations, {n_combos} combos in {elapsed:.1f}s")
        else:
            print(f"  {asset}: {len(results)} signal evaluations (combos skipped)")

    print()

    # ------------------------------------------------------------------ #
    # Step 4: Generate report                                             #
    # ------------------------------------------------------------------ #
    print("Step 4/4 — Generating Word report...")

    # For FX confluence we pass panels/signals/targets; if skipped, pass empty maps
    panels_for_report = all_panels if not args.no_fx_confluence else {}
    signals_for_report = all_signals_map if not args.no_fx_confluence else {}
    targets_for_report = all_targets_map if not args.no_fx_confluence else {}

    generate_report(
        all_panels=panels_for_report,
        all_signals_map=signals_for_report,
        all_targets_map=targets_for_report,
        all_asset_results=all_asset_results,
        all_combo_results=all_combo_results,
        assets=list(all_panels.keys()),
        signal_cols=ALL_SIGNALS,
        horizons=horizons,
        output_path=args.output,
    )

    # Print quick console summary
    print("\n=== Quick Summary (OOS IC, best horizon per signal per asset) ===")
    for asset, res in all_asset_results.items():
        if res.empty:
            continue
        oos = res[res["split"] == "oos"].copy()
        best = oos.reindex(oos["IC"].abs().sort_values(ascending=False).index).drop_duplicates("signal").head(3)
        print(f"\n{asset}:")
        for _, row in best.iterrows():
            print(f"  {row['signal']:35s} {row['horizon']}  IC={row['IC']:+.3f}  Sharpe={row['sharpe']:+.2f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
