from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUT = ROOT / "submission_assets" / "phase1"
CHARTS = OUT / "charts"
SCRIPT_OUT = ROOT / "submission_assets" / "scripts"
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/stock_league_mpl_cache")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp/stock_league_xdg_cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

FINANCIAL_SECTORS = {
    "Banks",
    "Insurance",
    "Securities and Commodities Futures",
    "Other Financing Business",
    "銀行業",
    "保険業",
    "証券、商品先物取引業",
    "その他金融業",
}

PHASE1_TOTAL_CAPITAL = 5_000_000
FINAL_COUNT = 20


@dataclass(frozen=True)
class Phase1Data:
    scores: pd.DataFrame
    raw: pd.DataFrame
    prices: pd.DataFrame
    universe: pd.DataFrame


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    SCRIPT_OUT.mkdir(parents=True, exist_ok=True)


def bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def num(series: pd.Series | float | int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    out = num(a) / num(b).replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    s = num(series)
    if s.notna().sum() < 5:
        return s
    lo = s.quantile(lower)
    hi = s.quantile(upper)
    return s.clip(lo, hi)


def tercile(series: pd.Series, high_is_good: bool = True) -> pd.Series:
    s = num(series)
    labels = ["Low", "Mid", "High"] if high_is_good else ["High", "Mid", "Low"]
    out = pd.Series("Unavailable", index=s.index, dtype="object")
    valid = s.dropna()
    if valid.nunique() < 3:
        out.loc[s.notna()] = "Mid"
        return out
    try:
        out.loc[s.notna()] = pd.qcut(s.loc[s.notna()], 3, labels=labels, duplicates="drop").astype(str)
    except ValueError:
        out.loc[s.notna()] = "Mid"
    return out


def load_data() -> Phase1Data:
    scores = pd.read_csv(DATA / "scores.csv", dtype={"code": str})
    raw = pd.read_csv(DATA / "fundamentals_raw.csv", dtype={"code": str})
    universe = pd.read_csv(DATA / "universe.csv", dtype={"code": str})
    prices = pd.read_parquet(DATA / "prices_daily.parquet")
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    return Phase1Data(scores=scores, raw=raw, prices=prices, universe=universe)


def write_inventory(data: Phase1Data) -> None:
    files = [
        DATA / "universe.csv",
        DATA / "scores.csv",
        DATA / "fundamentals_clean.csv",
        DATA / "fundamentals_raw.csv",
        DATA / "latest_prices.csv",
        DATA / "yfinance_metrics.csv",
        DATA / "prices_daily.parquet",
    ]
    rows = []
    md = [
        "# Phase1 Data Inventory",
        "",
        "Phase1 uses only public price and accounting fields already present in the repository.",
        "Future Moat, AI keyword, Transformation, and existing proprietary BEYOND BUFFETT scores are not used for selection.",
        "",
    ]
    for path in files:
        if not path.exists():
            continue
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path, nrows=50)
        cols = list(df.columns)
        rows.append(
            {
                "file": str(path.relative_to(ROOT)),
                "format": path.suffix.lstrip("."),
                "row_count": len(pd.read_parquet(path)) if path.suffix == ".parquet" else sum(1 for _ in path.open()) - 1,
                "column_count": len(cols),
                "code_column": "code" if "code" in cols else "",
                "ticker_column": "ticker" if "ticker" in cols else "",
                "date_columns": ";".join([c for c in cols if "date" in c.lower() or "period" in c.lower()]),
                "columns": ";".join(cols),
            }
        )
        md.extend(
            [
                f"## {path.relative_to(ROOT)}",
                "",
                f"- Columns: {', '.join(cols)}",
                f"- Code column: {'code' if 'code' in cols else 'not present'}",
                f"- Ticker column: {'ticker' if 'ticker' in cols else 'not present'}",
                f"- Date columns: {', '.join([c for c in cols if 'date' in c.lower() or 'period' in c.lower()]) or 'none'}",
                "",
            ]
        )
    md.extend(
        [
            "## Missing Variables For Original Academic Formulas",
            "",
            "- Gross Profitability: gross profit or cost of goods sold is not available, so the Novy-Marx original formula is unavailable.",
            "- QMJ full: payout, equity issuance, debt issuance, idiosyncratic volatility, earnings volatility, and full growth components are unavailable.",
            "- Piotroski full: gross margin, current ratio, and common equity issuance are unavailable; available-signal reliability is reported.",
            "- Ohlson O-Score: GNP, working capital, current assets, current liabilities, FFO, and CHIN inputs are unavailable.",
            "- Altman Z-Score: working capital and retained earnings are unavailable; original Altman Z is therefore unavailable.",
            "",
        ]
    )
    (OUT / "data_inventory.md").write_text("\n".join(md), encoding="utf-8")
    pd.DataFrame(rows).to_csv(OUT / "input_file_map.csv", index=False)


def latest_raw_frames(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    r = raw.copy()
    r["period_end"] = pd.to_datetime(r["period_end"], errors="coerce")
    r["submit_date"] = pd.to_datetime(r["submit_date"], errors="coerce")
    r = r.sort_values(["code", "period_end"], ascending=[True, False])
    current = r.groupby("code").nth(0).reset_index()
    previous = r.groupby("code").nth(1).reset_index()
    return current, previous


def data_available_mask(df: pd.DataFrame) -> pd.Series:
    required = [
        "total_assets",
        "equity",
        "roe",
        "revenue",
        "operating_income",
        "operating_cf",
    ]
    mask = bool_series(df["price_available"]) & (num(df["price_history_days"]).fillna(0) >= 500)
    for col in required:
        mask &= num(df[col]).notna()
    return mask


def build_universe(scores: pd.DataFrame) -> pd.DataFrame:
    df = scores.copy()
    is_financial = df["sector_33"].isin(FINANCIAL_SECTORS) | bool_series(df.get("is_financial", False))
    data_available = data_available_mask(df)
    included = (~is_financial) & data_available
    reasons = []
    for _, row in df.iterrows():
        row_reasons = []
        if row.get("sector_33") in FINANCIAL_SECTORS or bool(row.get("is_financial", False)):
            row_reasons.append("financial_sector_excluded")
        if not bool(row.get("price_available")):
            row_reasons.append("price_unavailable")
        if float(row.get("price_history_days") or 0) < 500:
            row_reasons.append("price_history_lt_500")
        for col in ["total_assets", "equity", "roe", "revenue", "operating_income", "operating_cf"]:
            if pd.isna(row.get(col)):
                row_reasons.append(f"missing_{col}")
        reasons.append(";".join(row_reasons))
    out = pd.DataFrame(
        {
            "code": df["code"],
            "ticker": df["ticker"],
            "company_name": df["company_name"],
            "sector": df["sector_33"],
            "market_segment": df["market"],
            "is_financial": is_financial,
            "is_common_stock": True,
            "data_available": data_available,
            "included_phase1": included,
            "exclusion_reason": reasons,
        }
    )
    out.to_csv(OUT / "phase1_universe.csv", index=False)
    out.loc[~out["included_phase1"]].to_csv(OUT / "universe_exclusion_reasons.csv", index=False)
    summary = pd.DataFrame(
        [
            {"item": "raw_universe_count", "count": len(out)},
            {"item": "common_stock_count", "count": int(out["is_common_stock"].sum())},
            {"item": "after_financial_exclusion_count", "count": int((~is_financial).sum())},
            {"item": "after_data_availability_count", "count": int(((~is_financial) & data_available).sum())},
            {"item": "final_phase1_universe_count", "count": int(included.sum())},
        ]
    )
    summary.to_csv(OUT / "universe_summary.csv", index=False)
    return out


def compute_value_metrics(scores: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    df = scores.merge(universe[["code", "included_phase1"]], on="code", how="left")
    pbr = num(df["price_to_book"]).where(num(df["price_to_book"]) > 0)
    per = num(df["trailing_pe"]).fillna(num(df["forward_pe"])).where(
        num(df["trailing_pe"]).fillna(num(df["forward_pe"])) > 0
    )
    market_equity = num(df["market_cap"])
    book_equity = num(df["equity"])
    estimated_market_equity = book_equity * pbr
    market_equity_for_value = market_equity.fillna(estimated_market_equity)
    b_m = safe_div(book_equity, market_equity_for_value).where(book_equity > 0)
    e_p = safe_div(num(df["net_income"]), market_equity_for_value).where(num(df["net_income"]) > 0)
    fallback_b_m = 1 / pbr
    fallback_e_p = 1 / per
    out = pd.DataFrame(
        {
            "code": df["code"],
            "ticker": df["ticker"],
            "company_name": df["company_name"],
            "included_phase1": df["included_phase1"].fillna(False),
            "book_equity": book_equity,
            "market_equity": market_equity_for_value,
            "market_equity_method": np.where(market_equity.notna(), "yfinance_market_cap", "equity_times_pbr"),
            "B_M": b_m.fillna(fallback_b_m),
            "PBR": pbr,
            "E_P": e_p.fillna(fallback_e_p),
            "PER": per,
            "positive_earnings_flag": num(df["net_income"]) > 0,
            "value_metric_available": b_m.fillna(fallback_b_m).notna() & e_p.fillna(fallback_e_p).notna(),
        }
    )
    out.to_csv(OUT / "value_metrics.csv", index=False)
    summary = out[["B_M", "PBR", "E_P", "PER"]].describe().T.reset_index().rename(columns={"index": "metric"})
    summary["available_count"] = out[["B_M", "PBR", "E_P", "PER"]].notna().sum().values
    summary.to_csv(OUT / "value_metric_summary.csv", index=False)
    return out


def compute_quality_metrics(scores: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    df = scores.merge(universe[["code", "included_phase1"]], on="code", how="left")
    assets = num(df["total_assets"])
    equity = num(df["equity"])
    revenue = num(df["revenue"])
    operating_income = num(df["operating_income"])
    net_income = num(df["net_income"])
    out = pd.DataFrame(
        {
            "code": df["code"],
            "ticker": df["ticker"],
            "company_name": df["company_name"],
            "included_phase1": df["included_phase1"].fillna(False),
            "gross_profit": np.nan,
            "gross_profitability": np.nan,
            "gross_profitability_available": False,
            "gross_profitability_note": "Unavailable: gross profit and cost of goods sold are absent from input data.",
            "ROA": safe_div(net_income, assets),
            "ROE": num(df["roe"]).fillna(safe_div(net_income, equity)),
            "CFO_assets": safe_div(num(df["operating_cf"]), assets),
            "gross_margin": np.nan,
            "asset_turnover": safe_div(revenue, assets),
            "operating_profitability": safe_div(operating_income, equity),
            "asset_growth": np.nan,
        }
    )
    out.to_csv(OUT / "quality_metrics.csv", index=False)
    qmj = out[["code", "ticker", "company_name"]].copy()
    qmj["qmj_quality"] = np.nan
    qmj["qmj_full_available"] = False
    qmj["unavailable_reason"] = (
        "QMJ full unavailable: missing gross profit, full payout/issuance variables, "
        "idiosyncratic volatility, earnings volatility, and full multi-year growth inputs."
    )
    qmj.to_csv(OUT / "qmj_metrics.csv", index=False)
    (OUT / "qmj_availability_report.md").write_text(
        "\n".join(
            [
                "# QMJ Availability Report",
                "",
                "QMJ full is unavailable in Phase1 because required inputs are absent from the local public-data set.",
                "The implementation does not create a proprietary simplified QMJ score.",
                "",
                "Unavailable inputs include gross profit / COGS, net payout yield, equity issuance, debt issuance,",
                "idiosyncratic volatility, earnings volatility, and the full set of QMJ growth and payout components.",
                "",
                "Selection therefore relies on published Value screens, available Piotroski signals, Sloan accruals,",
                "and reporting-only profitability fields such as ROA, ROE, CFO/assets, asset turnover, and operating profitability.",
            ]
        ),
        encoding="utf-8",
    )
    summary = out[["ROA", "ROE", "CFO_assets", "asset_turnover", "operating_profitability"]].describe().T
    summary.reset_index(names="metric").to_csv(OUT / "quality_metric_summary.csv", index=False)
    return out


def compute_piotroski(data: Phase1Data) -> pd.DataFrame:
    current, previous = latest_raw_frames(data.raw)
    p = previous.add_suffix("_prev")
    df = current.merge(p, left_on="code", right_on="code_prev", how="left")
    for col in ["net_income", "total_assets", "operating_cf", "revenue", "equity"]:
        df[col] = num(df[col])
        df[f"{col}_prev"] = num(df[f"{col}_prev"])
    df["ROA"] = safe_div(df["net_income"], df["total_assets"])
    df["ROA_prev"] = safe_div(df["net_income_prev"], df["total_assets_prev"])
    df["CFO_assets"] = safe_div(df["operating_cf"], df["total_assets"])
    df["asset_turnover"] = safe_div(df["revenue"], df["total_assets"])
    df["asset_turnover_prev"] = safe_div(df["revenue_prev"], df["total_assets_prev"])
    df["leverage"] = safe_div(df["total_assets"] - df["equity"], df["total_assets"])
    df["leverage_prev"] = safe_div(df["total_assets_prev"] - df["equity_prev"], df["total_assets_prev"])
    signals = pd.DataFrame(
        {
            "code": df["code"],
            "ticker": df["ticker"],
            "company_name": df["filer_name"],
            "F_ROA": (df["ROA"] > 0),
            "F_CFO": (df["operating_cf"] > 0),
            "F_DROA": (df["ROA"] > df["ROA_prev"]),
            "F_ACCRUAL": (df["CFO_assets"] > df["ROA"]),
            "F_DMARGIN": np.nan,
            "F_DTURN": (df["asset_turnover"] > df["asset_turnover_prev"]),
            "F_DLEVER": (df["leverage"] < df["leverage_prev"]),
            "F_DLIQUID": np.nan,
            "EQ_OFFER": np.nan,
        }
    )
    signal_cols = [
        "F_ROA",
        "F_CFO",
        "F_DROA",
        "F_ACCRUAL",
        "F_DMARGIN",
        "F_DTURN",
        "F_DLEVER",
        "F_DLIQUID",
        "EQ_OFFER",
    ]
    for col in signal_cols:
        if signals[col].dtype == bool:
            signals[col] = signals[col].astype(int)
    signals["F_SCORE"] = signals[signal_cols].fillna(0).sum(axis=1).astype(int)
    signals["available_signal_count"] = signals[signal_cols].notna().sum(axis=1)
    signals["missing_signal_count"] = signals[signal_cols].isna().sum(axis=1)
    signals["fscore_reliability_flag"] = np.where(
        signals["missing_signal_count"].eq(0),
        "full_9_signal",
        "partial_available_signals_only",
    )
    signals.to_csv(OUT / "piotroski_fscore.csv", index=False)
    summary = []
    for col in signal_cols + ["F_SCORE"]:
        summary.append(
            {
                "signal": col,
                "available_count": int(signals[col].notna().sum()),
                "positive_or_score_sum": float(signals[col].fillna(0).sum()),
            }
        )
    pd.DataFrame(summary).to_csv(OUT / "piotroski_signal_summary.csv", index=False)
    return signals


def compute_accruals(data: Phase1Data, universe: pd.DataFrame) -> pd.DataFrame:
    current, previous = latest_raw_frames(data.raw)
    p = previous[["code", "total_assets"]].rename(columns={"total_assets": "total_assets_prev"})
    df = current.merge(p, on="code", how="left")
    df = df.merge(universe[["code", "included_phase1"]], on="code", how="left")
    avg_assets = (num(df["total_assets"]) + num(df["total_assets_prev"])) / 2
    accruals = safe_div(num(df["net_income"]) - num(df["operating_cf"]), avg_assets)
    out = pd.DataFrame(
        {
            "code": df["code"],
            "ticker": df["ticker"],
            "company_name": df["filer_name"],
            "included_phase1": df["included_phase1"].fillna(False),
            "accruals": accruals,
            "accruals_winsorized": winsorize(accruals),
            "accruals_method": np.where(num(df["operating_cf"]).notna(), "Sloan_CFO_based", "unavailable"),
            "net_income": num(df["net_income"]),
            "operating_cash_flow": num(df["operating_cf"]),
            "average_total_assets": avg_assets,
        }
    )
    eligible = out["included_phase1"].fillna(False)
    out["accruals_rank"] = out.loc[eligible, "accruals_winsorized"].rank(method="min", ascending=True)
    bad_threshold = out.loc[eligible, "accruals_winsorized"].quantile(0.70)
    out["high_accrual_flag"] = out["accruals_winsorized"] > bad_threshold
    out.to_csv(OUT / "accruals_metrics.csv", index=False)
    (OUT / "accruals_method_report.md").write_text(
        "\n".join(
            [
                "# Sloan Accruals Method Report",
                "",
                "Accruals are calculated with Sloan's CFO-based simplified form:",
                "",
                "`Accruals = (Net Income - Operating Cash Flow) / Average Total Assets`",
                "",
                "Balance-sheet approximation is not used because current assets, cash, current liabilities,",
                "short-term debt, taxes payable, and depreciation are unavailable.",
                "",
                f"High-accrual exclusion threshold is the Phase1 universe 70th percentile: {bad_threshold:.6f}.",
            ]
        ),
        encoding="utf-8",
    )
    return out


def compute_distress(data: Phase1Data, universe: pd.DataFrame) -> pd.DataFrame:
    scores = data.scores.merge(universe[["code", "included_phase1"]], on="code", how="left")
    liabilities = num(scores["total_assets"]) - num(scores["equity"])
    altman_partial = (
        3.3 * safe_div(num(scores["operating_income"]), num(scores["total_assets"]))
        + 0.6 * safe_div(num(scores["market_cap"]), liabilities)
        + 1.0 * safe_div(num(scores["revenue"]), num(scores["total_assets"]))
    )
    out = pd.DataFrame(
        {
            "code": scores["code"],
            "ticker": scores["ticker"],
            "company_name": scores["company_name"],
            "included_phase1": scores["included_phase1"].fillna(False),
            "o_score": np.nan,
            "o_score_available": False,
            "o_score_failure_probability": np.nan,
            "altman_z": np.nan,
            "altman_z_available": False,
            "altman_partial_z_for_reference_only": altman_partial,
            "distress_exclusion_flag": False,
            "notes": "Original Ohlson and Altman formulas unavailable with current inputs; no distress exclusion applied.",
        }
    )
    out.to_csv(OUT / "distress_metrics.csv", index=False)
    (OUT / "ohlson_implementation_report.md").write_text(
        "\n".join(
            [
                "# Ohlson O-Score Implementation Report",
                "",
                "Ohlson O-Score is not calculated in Phase1.",
                "",
                "Required inputs missing from the local data include GNP price-level index, working capital,",
                "current liabilities, current assets, funds from operations, and CHIN. The implementation does",
                "not replace GNP with log(total assets), because that would be a material departure from the original formula.",
            ]
        ),
        encoding="utf-8",
    )
    (OUT / "altman_implementation_report.md").write_text(
        "\n".join(
            [
                "# Altman Z-Score Implementation Report",
                "",
                "Original Altman Z-Score is not calculated in Phase1 because working capital and retained earnings",
                "are unavailable. A partial reference-only value is exported, but it is not used for selection or exclusion.",
                "",
                "The report also notes that the original Altman model was designed for public manufacturing firms,",
                "so absolute thresholds are not applied to the Japanese all-industry universe.",
            ]
        ),
        encoding="utf-8",
    )
    return out


def build_screening(
    universe: pd.DataFrame,
    value: pd.DataFrame,
    quality: pd.DataFrame,
    fscore: pd.DataFrame,
    accruals: pd.DataFrame,
    distress: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = (
        universe[universe["included_phase1"]]
        .merge(value, on=["code", "ticker", "company_name"], how="left")
        .merge(quality, on=["code", "ticker", "company_name"], how="left", suffixes=("", "_quality"))
        .merge(fscore, on=["code", "ticker"], how="left", suffixes=("", "_fscore"))
        .merge(accruals[["code", "accruals", "accruals_winsorized", "high_accrual_flag"]], on="code", how="left")
        .merge(distress[["code", "o_score", "altman_z", "distress_exclusion_flag"]], on="code", how="left")
    )
    base["sector"] = base["sector"].fillna(base.get("sector_33", ""))
    base["market_cap_for_tiebreak"] = num(base["market_equity"]).fillna(num(base.get("market_cap", np.nan)))
    base["value_metric_available"] = base["B_M"].notna() & base["E_P"].notna()
    base["value_pass"] = False
    value_available = base["value_metric_available"]
    bm_threshold = base.loc[value_available, "B_M"].quantile(0.70)
    ep_threshold_50 = base.loc[value_available & (base["E_P"] > 0), "E_P"].quantile(0.50)
    ep_threshold_60 = base.loc[value_available & (base["E_P"] > 0), "E_P"].quantile(0.40)
    base.loc[value_available, "value_pass"] = (base["B_M"] >= bm_threshold) & (base["E_P"] >= ep_threshold_50)
    base["value_pass_ep60_fallback"] = False
    base.loc[value_available, "value_pass_ep60_fallback"] = (base["B_M"] >= bm_threshold) & (base["E_P"] >= ep_threshold_60)
    base["quality_pass"] = base["F_SCORE"] >= 6
    base["quality_pass_fscore5_fallback"] = base["F_SCORE"] >= 5
    accrual_threshold = base["accruals_winsorized"].quantile(0.70)
    base["earnings_quality_pass"] = base["accruals_winsorized"].notna() & (base["accruals_winsorized"] <= accrual_threshold)
    base["distress_pass"] = ~base["distress_exclusion_flag"].fillna(False)
    strict = base["value_pass"] & base["quality_pass"] & base["earnings_quality_pass"] & base["distress_pass"]
    fallback = (
        base["value_pass_ep60_fallback"]
        & base["quality_pass_fscore5_fallback"]
        & base["earnings_quality_pass"]
        & base["distress_pass"]
    )
    base["included_candidate_strict"] = strict
    base["included_candidate"] = fallback
    base["value_bucket"] = tercile(base["B_M"], True) + "_BM/" + tercile(base["E_P"], True) + "_EP"
    base["quality_bucket"] = "F_SCORE_" + base["F_SCORE"].fillna(-1).astype(int).astype(str)
    base["qmj_quality"] = np.nan
    base["notes"] = np.where(
        base["included_candidate_strict"],
        "Strict Phase1 candidate.",
        np.where(base["included_candidate"], "Fallback candidate: F-Score >= 5 and E/P top 60% used because strict screen produced fewer than 20 names.", ""),
    )

    steps = []
    current = pd.Series(True, index=base.index)

    def add_step(step: str, criterion: str, mask: pd.Series, source: str, explanation: str) -> None:
        nonlocal current
        before = int(current.sum())
        current = current & mask.fillna(False)
        after = int(current.sum())
        steps.append(
            {
                "step": step,
                "criterion": criterion,
                "count_before": before,
                "count_after": after,
                "removed_count": before - after,
                "explanation": explanation,
                "source_paper": source,
            }
        )

    add_step("0_universe", "included_phase1 == True", pd.Series(True, index=base.index), "Repository data audit", "Non-financial, price history >= 500 days, and minimum financial fields available.")
    add_step("1_value", "B/M top 30% and positive E/P top 50%", base["value_pass"], "Fama-French; Basu", "Strict value screen.")
    add_step("2_quality_financial_strength", "available Piotroski F-Score >= 6", base["quality_pass"], "Piotroski (2000)", "Financial strength screen using available signals.")
    add_step("3_earnings_quality", "Sloan accruals not in worst 30%", base["earnings_quality_pass"], "Sloan (1996)", "High accrual firms excluded.")
    add_step("4_distress", "Ohlson/Altman extreme tail exclusion if available", base["distress_pass"], "Ohlson; Altman", "No exclusion applied because original formulas are unavailable.")
    steps_df = pd.DataFrame(steps)
    steps_df.to_csv(OUT / "screening_steps.csv", index=False)
    funnel = steps_df[["step", "count_after"]].rename(columns={"count_after": "count"})
    funnel.to_csv(OUT / "screening_funnel.csv", index=False)

    candidate_cols = [
        "code",
        "ticker",
        "company_name",
        "sector",
        "market_segment",
        "B_M",
        "E_P",
        "gross_profitability",
        "qmj_quality",
        "F_SCORE",
        "accruals",
        "o_score",
        "altman_z",
        "value_bucket",
        "quality_bucket",
        "included_candidate",
        "included_candidate_strict",
        "notes",
    ]
    base.rename(columns={"F_SCORE": "f_score"}).to_csv(OUT / "phase1_candidates.csv", index=False)
    base[candidate_cols].rename(columns={"F_SCORE": "f_score"}).to_csv(OUT / "phase1_candidates_core.csv", index=False)
    (OUT / "screening_funnel_report.md").write_text(
        "\n".join(
            [
                "# Phase1 Screening Funnel Report",
                "",
                f"Strict academic screens produced {int(strict.sum())} candidates.",
                "Because fewer than 20 names survived, the pre-specified fallback is reported and used for the final 20:",
                "",
                "- Keep B/M top 30%.",
                "- Relax E/P from top 50% to top 60%.",
                "- Relax available Piotroski F-Score from >= 6 to >= 5.",
                "- Keep Sloan accruals worst-30% exclusion.",
                "- Do not use backtest results to alter membership.",
                "",
                f"Fallback candidate count: {int(fallback.sum())}.",
            ]
        ),
        encoding="utf-8",
    )
    return base, steps_df, funnel


def select_final20(candidates: pd.DataFrame) -> pd.DataFrame:
    pool = candidates[candidates["included_candidate"]].copy()
    pool["sort_f_score"] = num(pool["F_SCORE"]).fillna(-1)
    pool["sort_accruals"] = num(pool["accruals_winsorized"]).fillna(np.inf)
    pool["sort_profitability"] = num(pool["operating_profitability"]).fillna(-np.inf)
    pool["sort_market_cap"] = num(pool["market_cap_for_tiebreak"]).fillna(-np.inf)
    selected = pool.sort_values(
        ["sort_f_score", "sort_accruals", "sort_profitability", "sort_market_cap"],
        ascending=[False, True, False, False],
    ).head(FINAL_COUNT)
    if len(selected) < FINAL_COUNT:
        reserve = candidates[~candidates["code"].isin(selected["code"])].copy()
        reserve = reserve[reserve["value_metric_available"] & reserve["earnings_quality_pass"]].copy()
        reserve["sort_f_score"] = num(reserve["F_SCORE"]).fillna(-1)
        reserve["sort_accruals"] = num(reserve["accruals_winsorized"]).fillna(np.inf)
        reserve["sort_profitability"] = num(reserve["operating_profitability"]).fillna(-np.inf)
        reserve["sort_market_cap"] = num(reserve["market_cap_for_tiebreak"]).fillna(-np.inf)
        selected = pd.concat(
            [
                selected,
                reserve.sort_values(
                    ["sort_f_score", "sort_accruals", "sort_profitability", "sort_market_cap"],
                    ascending=[False, True, False, False],
                ).head(FINAL_COUNT - len(selected)),
            ],
            ignore_index=True,
        )
    selected = selected.reset_index(drop=True)
    selected["rank"] = np.arange(1, len(selected) + 1)
    selected["final_weight"] = 1 / FINAL_COUNT
    selected["investment_amount_yen"] = PHASE1_TOTAL_CAPITAL / FINAL_COUNT
    selected["selection_reason"] = selected.apply(
        lambda r: (
            f"B/M={r['B_M']:.3f}, E/P={r['E_P']:.3f}, available F-Score={int(r['F_SCORE'])}, "
            f"Sloan accruals={r['accruals']:.3f}; selected by pre-specified Phase1 fallback/tie-break."
        ),
        axis=1,
    )
    selected["caution"] = (
        "Gross Profitability, QMJ full, Ohlson O-Score, and original Altman Z are unavailable with current inputs."
    )
    out = pd.DataFrame(
        {
            "rank": selected["rank"],
            "code": selected["code"],
            "ticker": selected["ticker"],
            "company_name": selected["company_name"],
            "sector": selected["sector"],
            "market_segment": selected["market_segment"],
            "market_cap": selected["market_cap_for_tiebreak"],
            "B_M": selected["B_M"],
            "E_P": selected["E_P"],
            "gross_profitability": selected["gross_profitability"],
            "qmj_quality": np.nan,
            "f_score": selected["F_SCORE"],
            "accruals": selected["accruals"],
            "o_score": selected["o_score"],
            "altman_z": selected["altman_z"],
            "value_bucket": selected["value_bucket"],
            "quality_bucket": selected["quality_bucket"],
            "final_weight": selected["final_weight"],
            "investment_amount_yen": selected["investment_amount_yen"],
            "selection_reason": selected["selection_reason"],
            "caution": selected["caution"],
        }
    )
    out.to_csv(OUT / "phase1_final20.csv", index=False)
    candidates.assign(
        value_tercile_BM=tercile(candidates["B_M"], True),
        value_tercile_EP=tercile(candidates["E_P"], True),
        quality_tercile="F_SCORE_" + candidates["F_SCORE"].fillna(-1).astype(int).astype(str),
    ).to_csv(OUT / "phase1_double_sort.csv", index=False)
    (OUT / "final20_selection_reason.md").write_text(
        "\n".join(
            [
                "# Phase1 Final 20 Selection Reason",
                "",
                "Strict Phase1 screens produced fewer than 20 companies, so the pre-specified fallback was used.",
                "The fallback keeps the same academic logic but relaxes E/P from top 50% to top 60% and available",
                "Piotroski F-Score from >= 6 to >= 5. Backtest results are not used for membership changes.",
                "",
                "Tie-break order:",
                "",
                "1. Higher available Piotroski F-Score",
                "2. Lower Sloan accruals",
                "3. Higher operating profitability",
                "4. Larger market capitalization",
                "",
                "Final weights are equal at 5% each, or 250,000 yen per company for a 5,000,000 yen portfolio.",
            ]
        ),
        encoding="utf-8",
    )
    return out


def portfolio_returns(prices: pd.DataFrame, final20: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tickers = final20["ticker"].tolist()
    px = prices[prices["ticker"].isin(tickers)][["date", "ticker", "adj_close"]].dropna()
    wide = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    rets = wide.pct_change(fill_method=None).dropna(how="all")
    equal_ret = rets.mean(axis=1, skipna=True).rename("phase1_portfolio")
    bench_ticker = "1306.T" if "1306.T" in prices["ticker"].unique() else "1321.T"
    bench_px = prices[prices["ticker"].eq(bench_ticker)][["date", "adj_close"]].dropna().set_index("date").sort_index()
    bench_ret = bench_px["adj_close"].pct_change(fill_method=None).rename(bench_ticker)
    returns = pd.concat([equal_ret, bench_ret], axis=1).dropna()
    return returns, rets.loc[returns.index, [c for c in rets.columns if c in tickers]]


def max_drawdown(series: pd.Series) -> float:
    nav = (1 + series.fillna(0)).cumprod()
    return float((nav / nav.cummax() - 1).min())


def annual_return(series: pd.Series) -> float:
    if series.empty:
        return np.nan
    nav = (1 + series.fillna(0)).prod()
    years = len(series) / 252
    return float(nav ** (1 / years) - 1) if years > 0 else np.nan


def validate_portfolio(data: Phase1Data, final20: pd.DataFrame) -> None:
    returns, stock_returns = portfolio_returns(data.prices, final20)
    p = returns.iloc[:, 0]
    b = returns.iloc[:, 1]
    p_ann = annual_return(p)
    p_vol = float(p.std() * math.sqrt(252))
    b_ann = annual_return(b)
    b_vol = float(b.std() * math.sqrt(252))
    sharpe = p_ann / p_vol if p_vol else np.nan
    bench_sharpe = b_ann / b_vol if b_vol else np.nan
    x = b.to_numpy()
    y = p.to_numpy()
    beta, alpha_daily = np.polyfit(x, y, 1) if len(returns) > 2 and np.nanstd(x) > 0 else (np.nan, np.nan)
    alpha_ann = float((1 + alpha_daily) ** 252 - 1) if pd.notna(alpha_daily) else np.nan
    pd.DataFrame(
        [
            {
                "portfolio": "Phase1 Buffett Proxy equal weight",
                "start_date": returns.index.min().date(),
                "end_date": returns.index.max().date(),
                "observations": len(returns),
                "annual_return": p_ann,
                "annual_volatility": p_vol,
                "sharpe_ratio_rf0": sharpe,
                "max_drawdown": max_drawdown(p),
            },
            {
                "portfolio": returns.columns[1],
                "start_date": returns.index.min().date(),
                "end_date": returns.index.max().date(),
                "observations": len(returns),
                "annual_return": b_ann,
                "annual_volatility": b_vol,
                "sharpe_ratio_rf0": bench_sharpe,
                "max_drawdown": max_drawdown(b),
            },
        ]
    ).to_csv(OUT / "backtest_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "benchmark": returns.columns[1],
                "risk_free_rate_assumption": 0.0,
                "daily_alpha": alpha_daily,
                "annualized_alpha": alpha_ann,
                "beta": beta,
                "observations": len(returns),
            }
        ]
    ).to_csv(OUT / "jensen_alpha.csv", index=False)
    cov = stock_returns.cov() * 252
    n = len(final20)
    w = np.repeat(1 / n, n)
    cov_aligned = cov.reindex(index=final20["ticker"], columns=final20["ticker"]).fillna(0)
    variance = float(w @ cov_aligned.to_numpy() @ w)
    pd.DataFrame(
        [{"portfolio_variance_annualized": variance, "portfolio_volatility_annualized": math.sqrt(max(variance, 0)), "method": "Markowitz equal-weight covariance"}]
    ).to_csv(OUT / "portfolio_variance.csv", index=False)
    final20.groupby("sector", dropna=False)["final_weight"].sum().reset_index(name="weight").to_csv(
        OUT / "sector_allocation.csv", index=False
    )
    metric_cols = ["B_M", "E_P", "gross_profitability", "f_score", "accruals", "o_score", "altman_z"]
    final20[metric_cols].describe().T.reset_index(names="metric").to_csv(
        OUT / "final20_metric_distribution.csv", index=False
    )

    funnel = pd.read_csv(OUT / "screening_funnel.csv")
    plt.figure(figsize=(8, 5))
    plt.bar(funnel["step"], funnel["count"], color="#234f68")
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Companies")
    plt.title("Phase1 Screening Funnel")
    plt.tight_layout()
    plt.savefig(CHARTS / "phase1_screening_funnel.png", dpi=180)
    plt.close()

    sector = final20.groupby("sector")["final_weight"].sum().sort_values(ascending=True)
    plt.figure(figsize=(8, 5))
    plt.barh(sector.index, sector.values, color="#4b7f52")
    plt.xlabel("Weight")
    plt.title("Phase1 Sector Allocation")
    plt.tight_layout()
    plt.savefig(CHARTS / "phase1_sector_allocation.png", dpi=180)
    plt.close()

    nav = (1 + returns).cumprod()
    plt.figure(figsize=(8, 5))
    plt.plot(nav.index, nav.iloc[:, 0], label="Phase1")
    plt.plot(nav.index, nav.iloc[:, 1], label=returns.columns[1])
    plt.legend()
    plt.title("Phase1 Backtest vs Benchmark")
    plt.tight_layout()
    plt.savefig(CHARTS / "phase1_backtest_vs_benchmark.png", dpi=180)
    plt.close()

    corr = stock_returns.corr().reindex(index=final20["ticker"], columns=final20["ticker"])
    plt.figure(figsize=(8, 7))
    plt.imshow(corr.fillna(0), cmap="RdBu_r", vmin=-1, vmax=1)
    plt.colorbar(label="Correlation")
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=90, fontsize=6)
    plt.yticks(range(len(corr.index)), corr.index, fontsize=6)
    plt.title("Phase1 Final20 Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(CHARTS / "phase1_correlation_heatmap.png", dpi=180)
    plt.close()


def write_missingness_and_winsor_logs(
    value: pd.DataFrame,
    quality: pd.DataFrame,
    fscore: pd.DataFrame,
    accruals: pd.DataFrame,
    distress: pd.DataFrame,
) -> None:
    frames = {
        "value_metrics": value,
        "quality_metrics": quality,
        "piotroski_fscore": fscore,
        "accruals_metrics": accruals,
        "distress_metrics": distress,
    }
    rows = []
    for name, df in frames.items():
        for col in df.columns:
            rows.append(
                {
                    "table": name,
                    "column": col,
                    "missing_count": int(df[col].isna().sum()),
                    "missing_rate": float(df[col].isna().mean()),
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "missingness_report.csv", index=False)
    acc = accruals["accruals"]
    pd.DataFrame(
        [
            {
                "metric": "accruals",
                "winsor_lower": 0.01,
                "winsor_upper": 0.99,
                "raw_min": acc.min(),
                "raw_max": acc.max(),
                "winsor_min": winsorize(acc).min(),
                "winsor_max": winsorize(acc).max(),
            }
        ]
    ).to_csv(OUT / "winsorize_log.csv", index=False)


def write_reports(final20: pd.DataFrame, screening: pd.DataFrame) -> None:
    final_table = final20[["rank", "code", "ticker", "company_name", "sector", "B_M", "E_P", "f_score", "accruals"]]
    final_md = markdown_table(final_table)
    strict_count = int(screening["included_candidate_strict"].sum())
    fallback_count = int(screening["included_candidate"].sum())
    reports = {
        "phase1_methodology.md": [
            "# Phase1 Methodology",
            "",
            "Phase1 constructs a Buffett Proxy Portfolio using only academic formulas, rank screens, and exclusion rules.",
            "It does not use the existing proprietary MOAT, Transformation, Future Moat, AI keyword, or BEYOND BUFFETT scores.",
            "",
            "The proxy follows Buffett's Alpha: public-data replication is limited to cheap, safe, high-quality stocks.",
            "Financial sectors are excluded because bank, insurance, securities, and other financing firms have different balance-sheet structures.",
            "",
            "Strict screens use B/M top 30%, E/P top 50%, available Piotroski F-Score >= 6, and Sloan accruals outside the worst 30%.",
            f"The strict screen produced {strict_count} companies, so the pre-specified fallback produced {fallback_count} candidates for final selection.",
            "",
            "Accounting data uses submitted EDINET records where available. Where exact availability dates cannot be fully aligned, look-ahead risk is disclosed.",
        ],
        "phase1_formula_reference.md": [
            "# Phase1 Formula Reference",
            "",
            "- Buffett's Alpha: design background only.",
            "- B/M = Book Equity / Market Equity; implemented where PBR or market capitalization is available.",
            "- E/P = Earnings / Market Equity; implemented for positive earnings and positive market equity/PER.",
            "- Gross Profitability = Gross Profit / Total Assets; unavailable because gross profit/COGS is absent.",
            "- QMJ full: unavailable; no simplified proprietary QMJ is created.",
            "- Piotroski F-Score: available-signal version reported; gross margin, current ratio, and equity issuance signals unavailable.",
            "- Sloan Accruals = (Net Income - Operating Cash Flow) / Average Total Assets; implemented.",
            "- Ohlson O-Score: unavailable; original inputs missing and no GNP substitution is made.",
            "- Altman Z-Score: original formula unavailable; partial reference-only field exported but not used.",
            "- Markowitz variance, Sharpe ratio, Jensen alpha: validation only, not selection.",
        ],
        "phase1_final20_report.md": [
            "# Phase1 Final20 Report",
            "",
            "The final portfolio is equal weighted at 5% per company.",
            "",
            final_md,
            "",
            "Interpretation: the list is a Buffett Proxy selected from value, available financial-strength, and earnings-quality filters.",
            "It is not a claim to reproduce Buffett's actual portfolio process.",
        ],
        "phase1_limitations.md": [
            "# Phase1 Limitations",
            "",
            "- Buffett's insurance float, private acquisitions, manager assessment, negotiation power, tax effects, and relationship capital are not reproducible from public data.",
            "- Gross Profitability, QMJ full, Ohlson O-Score, and original Altman Z-Score cannot be fully implemented with current inputs.",
            "- Market capitalization/PBR/PER availability is limited in yfinance-derived data, reducing value metric coverage.",
            "- Financial firms are excluded; this improves comparability but may exclude Buffett-like financial franchises.",
            "- Survivorship bias and data availability bias remain.",
            "- Backtests are validation only and do not guarantee future performance.",
        ],
        "README_phase1_reproducibility.md": [
            "# README Phase1 Reproducibility",
            "",
            "Run from the repository root:",
            "",
            "```bash",
            "python3 scripts/phase1_generate_report_assets.py",
            "```",
            "",
            "Inputs are under `data/processed/`. Outputs are under `submission_assets/phase1/`.",
            "Audit `missingness_report.csv`, `qmj_availability_report.md`, `ohlson_implementation_report.md`, and `altman_implementation_report.md` before using the results in a report.",
        ],
    }
    for name, lines in reports.items():
        (OUT / name).write_text("\n".join(lines), encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    display = df.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
        else:
            display[col] = display[col].fillna("").astype(str)
    headers = list(display.columns)
    rows = display.values.tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("|", "/") for value in row) + " |")
    return "\n".join(lines)


def write_script_manifest() -> None:
    names = [
        "phase1_build_universe.py",
        "phase1_compute_metrics.py",
        "phase1_screening.py",
        "phase1_select_final20.py",
        "phase1_validate_portfolio.py",
        "phase1_generate_report_assets.py",
    ]
    for name in names:
        text = (
            "from pathlib import Path\n"
            "import runpy\n\n"
            "ROOT = Path(__file__).resolve().parents[2]\n"
            "runpy.run_path(str(ROOT / 'scripts' / 'phase1_generate_report_assets.py'), run_name='__main__')\n"
        )
        (SCRIPT_OUT / name).write_text(text, encoding="utf-8")
    shutil.copy2(Path(__file__), SCRIPT_OUT / "phase1_generate_report_assets_full.py")


def main() -> None:
    ensure_dirs()
    data = load_data()
    write_inventory(data)
    universe = build_universe(data.scores)
    value = compute_value_metrics(data.scores, universe)
    quality = compute_quality_metrics(data.scores, universe)
    fscore = compute_piotroski(data)
    accruals = compute_accruals(data, universe)
    distress = compute_distress(data, universe)
    screening, _, _ = build_screening(universe, value, quality, fscore, accruals, distress)
    final20 = select_final20(screening)
    validate_portfolio(data, final20)
    write_missingness_and_winsor_logs(value, quality, fscore, accruals, distress)
    write_reports(final20, screening)
    write_script_manifest()
    print(f"Wrote Phase1 assets to {OUT}")
    print(f"Phase1 universe: {int(universe['included_phase1'].sum())}")
    print(f"Strict candidates: {int(screening['included_candidate_strict'].sum())}")
    print(f"Fallback candidates: {int(screening['included_candidate'].sum())}")
    print("Final20:")
    print(final20[["rank", "code", "ticker", "company_name"]].to_string(index=False))


if __name__ == "__main__":
    main()
