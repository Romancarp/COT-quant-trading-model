from __future__ import annotations

from typing import Callable

import pandas as pd

from cot_ingestion.normalizer import CanonicalPositionRecord, parse_int


def _first_col(columns: list[str], candidates: list[str]) -> str:
    for c in candidates:
        if c in columns:
            return c
    raise KeyError(f"none of columns found: {candidates}")


def _parse_generic(
    frame: pd.DataFrame,
    report_format: str,
    market_col_candidates: list[str],
    date_col_candidates: list[str],
    oi_col_candidates: list[str],
    contract_code_candidates: list[str],
    futures_combined_candidates: list[str],
    group_map: dict[str, tuple[str, str]],
    source_file: str,
    source_hash: str,
) -> list[CanonicalPositionRecord]:
    cols = list(frame.columns)
    market_col = _first_col(cols, market_col_candidates)
    date_col = _first_col(cols, date_col_candidates)
    oi_col = _first_col(cols, oi_col_candidates)
    code_col = _first_col(cols, contract_code_candidates)

    fut_col = next((c for c in futures_combined_candidates if c in cols), None)

    df = frame.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, market_col, code_col])

    out: list[CanonicalPositionRecord] = []
    for _, row in df.iterrows():
        for trader_category, (long_col, short_col) in group_map.items():
            if long_col not in df.columns or short_col not in df.columns:
                continue
            out.append(
                CanonicalPositionRecord(
                    report_date=row[date_col].date(),
                    as_of_date=row[date_col].date(),
                    report_format=report_format,
                    futures_only_or_combined=str(row[fut_col]) if fut_col else None,
                    cftc_contract_market_code=str(row[code_col]).strip(),
                    market_name=str(row[market_col]).strip(),
                    trader_category=trader_category,
                    long_pos=parse_int(row[long_col]),
                    short_pos=parse_int(row[short_col]),
                    open_interest=parse_int(row[oi_col]),
                    source_file=source_file,
                    source_hash=source_hash,
                )
            )
    return out


def parse_legacy_fut(frame: pd.DataFrame, source_file: str, source_hash: str) -> list[CanonicalPositionRecord]:
    return _parse_generic(
        frame,
        "legacy_fut",
        ["Market and Exchange Names"],
        ["As of Date in Form YYYY-MM-DD"],
        ["Open Interest (All)"],
        ["CFTC Contract Market Code", "CFTC_Contract_Market_Code"],
        ["FutOnly_or_Combined"],
        {
            "commercial": ("Commercial Positions-Long (All)", "Commercial Positions-Short (All)"),
            "non_commercial": ("Noncommercial Positions-Long (All)", "Noncommercial Positions-Short (All)"),
            "non_reportable": ("Nonreportable Positions-Long (All)", "Nonreportable Positions-Short (All)"),
        },
        source_file,
        source_hash,
    )


def parse_legacy_futopt(frame: pd.DataFrame, source_file: str, source_hash: str) -> list[CanonicalPositionRecord]:
    return _parse_generic(
        frame,
        "legacy_futopt",
        ["Market and Exchange Names"],
        ["As of Date in Form YYYY-MM-DD"],
        ["Open Interest (All)"],
        ["CFTC Contract Market Code", "CFTC_Contract_Market_Code"],
        ["FutOnly_or_Combined"],
        {
            "commercial": ("Commercial Positions-Long (All)", "Commercial Positions-Short (All)"),
            "non_commercial": ("Noncommercial Positions-Long (All)", "Noncommercial Positions-Short (All)"),
            "non_reportable": ("Nonreportable Positions-Long (All)", "Nonreportable Positions-Short (All)"),
        },
        source_file,
        source_hash,
    )


def parse_disaggregated_fut(frame: pd.DataFrame, source_file: str, source_hash: str) -> list[CanonicalPositionRecord]:
    return _parse_generic(
        frame,
        "disagg_fut",
        ["Market_and_Exchange_Names", "Market and Exchange Names"],
        ["Report_Date_as_YYYY-MM-DD", "As of Date in Form YYYY-MM-DD"],
        ["Open_Interest_All", "Open Interest (All)"],
        ["CFTC_Contract_Market_Code", "CFTC Contract Market Code"],
        ["FutOnly_or_Combined"],
        {
            "commercial": ("Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All"),
            "non_commercial": ("M_Money_Positions_Long_All", "M_Money_Positions_Short_All"),
            "non_reportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All"),
        },
        source_file,
        source_hash,
    )


def parse_disaggregated_futopt(frame: pd.DataFrame, source_file: str, source_hash: str) -> list[CanonicalPositionRecord]:
    return _parse_generic(
        frame,
        "disagg_futopt",
        ["Market_and_Exchange_Names", "Market and Exchange Names"],
        ["Report_Date_as_YYYY-MM-DD", "As of Date in Form YYYY-MM-DD"],
        ["Open_Interest_All", "Open Interest (All)"],
        ["CFTC_Contract_Market_Code", "CFTC Contract Market Code"],
        ["FutOnly_or_Combined"],
        {
            "commercial": ("Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All"),
            "non_commercial": ("M_Money_Positions_Long_All", "M_Money_Positions_Short_All"),
            "non_reportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All"),
        },
        source_file,
        source_hash,
    )


def parse_tff_fut(frame: pd.DataFrame, source_file: str, source_hash: str) -> list[CanonicalPositionRecord]:
    return _parse_generic(
        frame,
        "tff_fut",
        ["Market_and_Exchange_Names", "Market and Exchange Names"],
        ["Report_Date_as_YYYY-MM-DD", "As of Date in Form YYYY-MM-DD"],
        ["Open_Interest_All", "Open Interest (All)"],
        ["CFTC_Contract_Market_Code", "CFTC Contract Market Code"],
        ["FutOnly_or_Combined"],
        {
            "commercial": ("Dealer_Positions_Long_All", "Dealer_Positions_Short_All"),
            "non_commercial": ("Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All"),
            "non_reportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All"),
        },
        source_file,
        source_hash,
    )


def parse_tff_futopt(frame: pd.DataFrame, source_file: str, source_hash: str) -> list[CanonicalPositionRecord]:
    return _parse_generic(
        frame,
        "tff_futopt",
        ["Market_and_Exchange_Names", "Market and Exchange Names"],
        ["Report_Date_as_YYYY-MM-DD", "As of Date in Form YYYY-MM-DD"],
        ["Open_Interest_All", "Open Interest (All)"],
        ["CFTC_Contract_Market_Code", "CFTC Contract Market Code"],
        ["FutOnly_or_Combined"],
        {
            "commercial": ("Dealer_Positions_Long_All", "Dealer_Positions_Short_All"),
            "non_commercial": ("Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All"),
            "non_reportable": ("NonRept_Positions_Long_All", "NonRept_Positions_Short_All"),
        },
        source_file,
        source_hash,
    )


PARSER_MAP: dict[str, Callable[[pd.DataFrame, str, str], list[CanonicalPositionRecord]]] = {
    "legacy_fut": parse_legacy_fut,
    "legacy_futopt": parse_legacy_futopt,
    "disagg_fut": parse_disaggregated_fut,
    "disagg_futopt": parse_disaggregated_futopt,
    "disaggregated_fut": parse_disaggregated_fut,
    "disaggregated_futopt": parse_disaggregated_futopt,
    "tff_fut": parse_tff_fut,
    "tff_futopt": parse_tff_futopt,
    "traders_in_financial_futures_fut": parse_tff_fut,
    "traders_in_financial_futures_futopt": parse_tff_futopt,
}
