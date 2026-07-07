from __future__ import annotations

import argparse
import re

import numpy as np
import pandas as pd

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger
from src.utils.prices import repair_split_jumps


FUTURE_KEYWORDS = {
    "ai_infrastructure": [
        "semiconductor",
        "chip",
        "gpu",
        "hbm",
        "data center",
        "datacenter",
        "optical",
        "fiber",
        "electric",
        "power",
        "server",
        "air conditioning",
        "electronics",
    ],
    "automation": [
        "robot",
        "automation",
        "factory",
        "fa",
        "control",
        "sensor",
        "machinery",
        "precision",
    ],
    "data_software": [
        "software",
        "cloud",
        "saas",
        "system",
        "data",
        "digital",
        "information",
        "communication",
    ],
    "trust_security": [
        "security",
        "cyber",
        "inspection",
        "quality",
        "testing",
        "audit",
        "risk",
        "insurance",
    ],
}

EXPERIMENT_ID = "exp001"

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


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return numeric
    low = numeric.quantile(lower)
    high = numeric.quantile(upper)
    return numeric.clip(low, high)


def zscore(series: pd.Series) -> pd.Series:
    numeric = winsorize(series)
    mean = numeric.mean(skipna=True)
    std = numeric.std(skipna=True)
    if not np.isfinite(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (numeric - mean) / std


def average_z(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    parts = [zscore(df[col]) if col in df.columns else pd.Series(np.nan, index=df.index) for col in columns]
    combined = pd.concat(parts, axis=1)
    return combined.fillna(0).mean(axis=1)


def masked_zscore(series: pd.Series, mask: pd.Series) -> pd.Series:
    out = pd.Series(0.0, index=series.index)
    mask = mask.fillna(False).astype(bool)
    if mask.any():
        out.loc[mask] = zscore(series.loc[mask]).fillna(0)
    return out


def average_series(parts: list[pd.Series]) -> pd.Series:
    if not parts:
        return pd.Series(dtype=float)
    combined = pd.concat(parts, axis=1)
    return combined.fillna(0).mean(axis=1)


def _score_percentile(series: pd.Series, mask: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=series.index)
    valid = mask.fillna(False).astype(bool) & numeric.notna()
    if valid.any():
        out.loc[valid] = numeric.loc[valid].rank(pct=True, method="average")
    return out


def _score_rank(series: pd.Series, mask: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=series.index)
    valid = mask.fillna(False).astype(bool) & numeric.notna()
    if valid.any():
        out.loc[valid] = numeric.loc[valid].rank(ascending=False, method="min")
    return out


def _safe_inverse(series: pd.Series, positive_only: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if positive_only:
        numeric = numeric.where(numeric > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1 / numeric
    return inv.replace([np.inf, -np.inf], np.nan)


def _truthy(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float) != 0
    return series.fillna("").astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _latest_history_counts(raw: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "code",
        "operating_loss_years_3y",
        "operating_income_years_available",
        "ordinary_loss_years_3y",
        "ordinary_income_years_available",
        "net_loss_years_3y",
        "net_income_years_available",
        "negative_ocf_years_3y",
        "operating_cf_years_available",
    ]
    if raw.empty or "code" not in raw.columns:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for code, group in raw.sort_values("submit_date").groupby("code"):
        operating_income = pd.to_numeric(group["operating_income"], errors="coerce").dropna().tail(3)
        ordinary_income = pd.to_numeric(group["ordinary_income"], errors="coerce").dropna().tail(3)
        net_income = pd.to_numeric(group["net_income"], errors="coerce").dropna().tail(3)
        operating_cf = pd.to_numeric(group["operating_cf"], errors="coerce").dropna().tail(3)
        rows.append(
            {
                "code": str(code),
                "operating_loss_years_3y": int((operating_income < 0).sum()),
                "operating_income_years_available": int(operating_income.notna().sum()),
                "ordinary_loss_years_3y": int((ordinary_income < 0).sum()),
                "ordinary_income_years_available": int(ordinary_income.notna().sum()),
                "net_loss_years_3y": int((net_income < 0).sum()),
                "net_income_years_available": int(net_income.notna().sum()),
                "negative_ocf_years_3y": int((operating_cf < 0).sum()),
                "operating_cf_years_available": int(operating_cf.notna().sum()),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _financial_like_mask(df: pd.DataFrame) -> pd.Series:
    sector = df.get("sector_33", pd.Series("", index=df.index)).fillna("").astype(str)
    return sector.isin(FINANCIAL_SECTORS)


def _write_financial_handling_outputs(
    df: pd.DataFrame,
    reasons: dict[str, pd.Series],
    eligible: pd.Series,
    config: AppConfig,
) -> None:
    financial = _financial_like_mask(df)
    liquid = _truthy(df.get("liquid_20m_60d", pd.Series(False, index=df.index)))
    reason_columns = list(reasons)
    reason_bits = pd.DataFrame({reason: mask.fillna(False) for reason, mask in reasons.items()})
    exclusion_reasons = reason_bits.apply(
        lambda row: ";".join([column for column, value in row.items() if bool(value)]),
        axis=1,
    )

    summary = pd.DataFrame(
        [
            {"item": "experiment_id", "value": EXPERIMENT_ID},
            {"item": "financial_sector_companies", "value": int(financial.sum())},
            {"item": "financial_sector_liquid_20m_60d", "value": int((financial & liquid).sum())},
            {
                "item": "financial_sector_excluded_after_liquidity",
                "value": int((financial & liquid & ~eligible).sum()),
            },
            {
                "item": "financial_sector_investment_eligible",
                "value": int((financial & liquid & eligible).sum()),
            },
            {
                "item": "different_handling",
                "value": (
                    "No mechanical low_equity_ratio, repeated_negative_operating_cf, "
                    "excessive_leverage, operating_margin_outlier, or ROIC-style exclusion; "
                    "use ROE, ordinary/net profit continuity, valuation outliers, price/liquidity, "
                    "and core data availability instead."
                ),
            },
            {
                "item": "unavailable_financial_specific_data",
                "value": "Bank capital adequacy, non-performing loan ratios, and insurer solvency margin are not available in the current structured dataset.",
            },
        ]
    )
    summary.to_csv(config.data_processed_dir / "financial_sector_handling_summary.csv", index=False)

    check = df.loc[financial & liquid, [
        "code",
        "ticker",
        "company_name",
        "market",
        "sector_33",
        "roe",
        "ordinary_income",
        "net_income",
        "price_to_book",
        "trailing_pe",
        "avg_trading_value_60d",
        "price_history_days",
    ]].copy()
    check["investment_eligible"] = eligible.loc[check.index].to_numpy()
    for reason in reason_columns:
        check[reason] = reason_bits.loc[check.index, reason].to_numpy()
    check["exclusion_reasons"] = exclusion_reasons.loc[check.index].to_numpy()
    check.to_csv(config.data_processed_dir / "financial_sector_exclusion_check.csv", index=False)

    score_cols = [
        "code",
        "ticker",
        "company_name",
        "market",
        "sector_33",
        "investment_eligible",
        "profitability_score",
        "cash_generation_score",
        "stability_score",
        "competitive_position_score",
        "moat_component_profitability",
        "moat_component_cashflow",
        "moat_component_stability",
        "moat_component_competitive_position",
        "moat_score",
        "transformation_component_valuation_gap",
        "transformation_component_capital_efficiency",
        "transformation_component_shareholder_return",
        "transformation_component_reform_signal",
        "transformation_score",
        "future_moat_component_ai_infrastructure",
        "future_moat_component_intangible_asset",
        "future_moat_component_automation",
        "future_moat_component_data",
        "future_moat_component_trust",
        "future_moat_score",
        "valuation_score",
        "momentum_score",
        "risk_score",
        "adjusted_bb_score",
    ]
    score_frame = df.loc[financial].copy()
    score_frame["investment_eligible"] = eligible.loc[score_frame.index].to_numpy()
    existing_score_cols = [column for column in score_cols if column in score_frame.columns]
    score_frame[existing_score_cols].to_csv(
        config.data_processed_dir / "financial_sector_score_components.csv",
        index=False,
    )


def _investment_eligibility(
    df: pd.DataFrame,
    base_liquidity: pd.Series,
    config: AppConfig,
) -> tuple[pd.Series, pd.DataFrame]:
    raw_path = config.data_processed_dir / "fundamentals_raw.csv"
    raw = pd.read_csv(raw_path, dtype={"code": str}) if raw_path.exists() else pd.DataFrame()
    history = _latest_history_counts(raw)
    if not history.empty:
        history_cols = [column for column in history.columns if column != "code"]
        merged_history = df[["code"]].merge(history, on="code", how="left")
        for column in history_cols:
            df[column] = merged_history[column].to_numpy()

    financial_like = _financial_like_mask(df)
    df["is_financial_like"] = financial_like
    assets = _numeric(df, "total_assets")
    equity = _numeric(df, "equity")
    revenue = _numeric(df, "revenue")
    operating_income = _numeric(df, "operating_income")
    operating_cf = _numeric(df, "operating_cf")
    equity_ratio = _numeric(df, "equity_ratio")
    roe = _numeric(df, "roe")
    operating_margin = _numeric(df, "operating_margin")
    ocf_margin = _numeric(df, "ocf_margin")
    pe = _numeric(df, "pe_for_score").fillna(_numeric(df, "trailing_pe")).fillna(_numeric(df, "forward_pe"))
    pbr = _numeric(df, "pbr_for_score").fillna(_numeric(df, "price_to_book"))
    liabilities_to_equity = (assets - equity) / equity.replace(0, np.nan)

    operating_loss_years = _numeric(df, "operating_loss_years_3y").fillna(0)
    operating_income_years = _numeric(df, "operating_income_years_available").fillna(0)
    ordinary_loss_years = _numeric(df, "ordinary_loss_years_3y").fillna(0)
    ordinary_income_years = _numeric(df, "ordinary_income_years_available").fillna(0)
    net_loss_years = _numeric(df, "net_loss_years_3y").fillna(0)
    net_income_years = _numeric(df, "net_income_years_available").fillna(0)
    negative_ocf_years = _numeric(df, "negative_ocf_years_3y").fillna(0)
    operating_cf_years = _numeric(df, "operating_cf_years_available").fillna(0)
    price_history_days = _numeric(df, "price_history_days").fillna(0)

    reasons: dict[str, pd.Series] = {
        "missing_financial_data": base_liquidity
        & (
            assets.isna()
            | equity.isna()
            | roe.isna()
            | (
                financial_like
                & (
                    _numeric(df, "ordinary_income").isna()
                    & _numeric(df, "net_income").isna()
                )
            )
            | (
                ~financial_like
                & (
                    equity_ratio.isna()
                    | operating_income.isna()
                    | revenue.isna()
                    | operating_margin.isna()
                    | operating_cf.isna()
                    | ocf_margin.isna()
                )
            )
        ),
        "low_equity_ratio": base_liquidity
        & ~financial_like
        & (equity_ratio < 0.10),
        "ticker_or_join_mismatch": base_liquidity
        & (
            df["ticker"].fillna("").astype(str).str.len().eq(0)
            | df["code"].fillna("").astype(str).str.len().eq(0)
            | df.get("company_name", pd.Series("", index=df.index)).fillna("").astype(str).str.len().eq(0)
        ),
        "repeated_operating_loss": base_liquidity
        & ~financial_like
        & (operating_income_years >= 2)
        & (operating_loss_years >= 2)
        & (operating_income < 0)
        & (operating_margin < -0.03),
        "repeated_profit_loss": base_liquidity
        & financial_like
        & (
            ((ordinary_income_years >= 2) & (ordinary_loss_years >= 2) & (_numeric(df, "ordinary_income") < 0))
            | ((net_income_years >= 2) & (net_loss_years >= 2) & (_numeric(df, "net_income") < 0))
        ),
        "repeated_negative_operating_cf": base_liquidity
        & ~financial_like
        & (operating_cf_years >= 2)
        & (negative_ocf_years >= 2),
        "excessive_leverage": base_liquidity
        & ~financial_like
        & ((liabilities_to_equity > 8) | (equity <= 0)),
        "extreme_valuation_outlier": base_liquidity
        & (
            (pe.notna() & ((pe <= 0) | (pe > 120)))
            | (pbr.notna() & ((pbr <= 0) | (pbr > 20)))
        ),
        "extreme_profitability_outlier": base_liquidity
        & (
            (roe.notna() & ((roe < -0.50) | (roe > 0.80)))
            | (~financial_like & operating_margin.notna() & ((operating_margin < -0.50) | (operating_margin > 1.00)))
        ),
        "other_data_quality_issue": base_liquidity
        & (
            (price_history_days < 500)
            | (assets <= 0)
            | (~financial_like & (revenue <= 0))
            | (~financial_like & (equity_ratio > 1.20))
            | (~financial_like & ocf_margin.notna() & (ocf_margin.abs() > 3))
        ),
    }

    failed = pd.Series(False, index=df.index)
    for mask in reasons.values():
        failed |= mask.fillna(False)

    eligible = base_liquidity & ~failed
    reason_frame = pd.DataFrame({"code": df["code"], "ticker": df["ticker"]})
    reason_frame["company_name"] = df.get("company_name_ja", df.get("company_name", "")).fillna(
        df.get("company_name", "")
    )
    reason_frame["market"] = df.get("market", "")
    reason_frame["sector_33"] = df.get("sector_33", "")
    reason_frame["is_financial_like"] = financial_like
    reason_frame["liquidity_passed"] = base_liquidity
    for reason, mask in reasons.items():
        reason_frame[reason] = mask.fillna(False)
    reason_columns = list(reasons)
    reason_frame["investment_eligible"] = eligible
    reason_frame["exclusion_reasons"] = reason_frame[reason_columns].apply(
        lambda row: ";".join([column for column, value in row.items() if bool(value)]),
        axis=1,
    )

    all_reason_bits = reason_frame[reason_columns].copy()
    all_reasons = all_reason_bits.apply(
        lambda row: ";".join([column for column, value in row.items() if bool(value)]),
        axis=1,
    )
    price_available = _truthy(df.get("price_available", pd.Series(False, index=df.index)))
    df["investment_exclusion_reasons"] = ""
    df.loc[~price_available, "investment_exclusion_reasons"] = "price_unavailable"
    df.loc[price_available & ~base_liquidity, "investment_exclusion_reasons"] = "low_liquidity"
    df.loc[base_liquidity & ~eligible, "investment_exclusion_reasons"] = all_reasons.loc[
        base_liquidity & ~eligible
    ].to_numpy()

    reason_frame = reason_frame[base_liquidity & ~eligible].copy()
    missing_reason = reason_frame["exclusion_reasons"].fillna("").astype(str).str.len() == 0
    if missing_reason.any():
        reason_frame.loc[missing_reason, "other_data_quality_issue"] = True
        reason_frame.loc[missing_reason, "exclusion_reasons"] = "other_data_quality_issue"
    reason_frame.to_csv(config.data_processed_dir / "investment_eligibility_exclusions.csv", index=False)

    counts = pd.DataFrame(
        [
            {"summary_type": "reason_count_overlapping", "reason": reason, "excluded_companies": int(mask.fillna(False).sum())}
            for reason, mask in reasons.items()
        ]
    )
    counts.loc[len(counts)] = {
        "summary_type": "unique_company_count",
        "reason": "unique_excluded_total",
        "excluded_companies": int((base_liquidity & ~eligible).sum()),
    }
    counts.to_csv(config.data_processed_dir / "investment_eligibility_exclusion_summary.csv", index=False)
    _write_financial_handling_outputs(df, reasons, eligible, config)
    return eligible, reason_frame


def _load_prices(config: AppConfig) -> pd.DataFrame:
    path = config.data_processed_dir / "prices_daily.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def compute_price_features(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame()
    working = prices.copy()
    working["price_for_return"] = working["adj_close"].fillna(working["close"])
    rows: list[dict[str, object]] = []
    for ticker, group in working.sort_values("date").groupby("ticker"):
        close = repair_split_jumps(group["price_for_return"]).dropna()
        if len(close) < 2:
            continue
        returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        cumulative = close / close.iloc[0]
        drawdown = cumulative / cumulative.cummax() - 1
        one_month = close.iloc[-1] / close.iloc[-22] - 1 if len(close) > 22 else 0
        twelve_month = close.iloc[-1] / close.iloc[-253] - 1 if len(close) > 253 else close.iloc[-1] / close.iloc[0] - 1
        rows.append(
            {
                "ticker": ticker,
                "daily_return_mean": returns.mean(),
                "annual_volatility": returns.std() * np.sqrt(252),
                "max_drawdown": drawdown.min(),
                "return_12m_ex_1m": twelve_month - one_month,
                "cumulative_return": close.iloc[-1] / close.iloc[0] - 1,
                "price_history_days": len(close),
            }
        )
    return pd.DataFrame(rows)


def _keyword_count(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if re.search(rf"\b{re.escape(keyword.lower())}\b", lowered))


def _future_exposure(row: pd.Series, bucket: str) -> float:
    text = " ".join(
        str(row.get(col, ""))
        for col in ["company_name", "sector_33", "sector_17", "market", "scale_category"]
    )
    score = _keyword_count(text, FUTURE_KEYWORDS[bucket])
    sector = str(row.get("sector_33", ""))
    sector_17 = str(row.get("sector_17", ""))
    if bucket == "ai_infrastructure" and sector in {
        "Electric Appliances",
        "Machinery",
        "Chemicals",
        "Nonferrous Metals",
        "Metal Products",
        "Precision Instruments",
    }:
        score += 2
    if bucket == "automation" and (sector in {"Machinery", "Electric Appliances", "Precision Instruments"} or "AUTOMOBILES" in sector_17):
        score += 2
    if bucket == "data_software" and sector in {"Information & Communication", "Services"}:
        score += 2
    if bucket == "trust_security" and sector in {"Services", "Information & Communication", "Insurance"}:
        score += 1
    return np.log1p(score)


def _category(row: pd.Series) -> str:
    components = {
        "Core Moat": row.get("moat_score", 0),
        "Transformation Moat": row.get("transformation_score", 0),
        "Future Moat": row.get("future_moat_score", 0),
    }
    best = max(components, key=components.get)
    if row.get("adjusted_bb_score", 0) > 0 and row.get("avg_trading_value_60d", 0) < 50_000_000:
        return "Discovery"
    return best


def score_universe(config: AppConfig, preliminary: bool = False) -> pd.DataFrame:
    logger = setup_logger("scoring", config.logs_dir)
    universe = pd.read_csv(config.data_processed_dir / "universe.csv", dtype={"code": str})
    latest_path = config.data_processed_dir / "latest_prices.csv"
    latest = pd.read_csv(latest_path) if latest_path.exists() else pd.DataFrame()
    fundamentals_path = config.data_processed_dir / "fundamentals_clean.csv"
    fundamentals = pd.read_csv(fundamentals_path, dtype={"code": str}) if fundamentals_path.exists() else universe.copy()
    price_features = compute_price_features(_load_prices(config))

    df = universe.merge(latest, on="ticker", how="left")
    df = df.merge(price_features, on="ticker", how="left")
    keep_cols = [c for c in fundamentals.columns if c not in df.columns or c in {"ticker", "code"}]
    df = df.merge(fundamentals[keep_cols], on=["ticker", "code"], how="left")

    if "dividend_yield" in df.columns:
        dy = pd.to_numeric(df["dividend_yield"], errors="coerce")
        df["dividend_yield_clean"] = dy.where(dy <= 1, dy / 100)
    else:
        df["dividend_yield_clean"] = np.nan

    pe = pd.to_numeric(df.get("trailing_pe", np.nan), errors="coerce").fillna(
        pd.to_numeric(df.get("forward_pe", np.nan), errors="coerce")
    )
    df["pe_for_score"] = pe.where(pe > 0)
    df["pbr_for_score"] = pd.to_numeric(df.get("price_to_book", np.nan), errors="coerce").where(
        lambda s: s > 0
    )
    df["is_financial_like"] = _financial_like_mask(df)
    financial_mask = df["is_financial_like"].fillna(False).astype(bool)
    nonfinancial_mask = ~financial_mask

    ordinary_income = _numeric(df, "ordinary_income")
    net_income = _numeric(df, "net_income")
    revenue = _numeric(df, "revenue")
    equity = _numeric(df, "equity")
    assets = _numeric(df, "total_assets")
    ordinary_margin = ordinary_income / revenue.replace(0, np.nan)
    net_margin = net_income / revenue.replace(0, np.nan)
    df["ordinary_margin"] = ordinary_margin.replace([np.inf, -np.inf], np.nan)
    df["net_margin"] = net_margin.replace([np.inf, -np.inf], np.nan)

    df["profitability_score"] = average_z(df, ["operating_margin", "roe", "equity_ratio"])
    df["cash_generation_score"] = average_z(df, ["ocf_margin"])
    df["stability_score"] = average_z(df.assign(neg_vol=-df["annual_volatility"].fillna(0)), ["neg_vol"])
    df["competitive_position_score"] = average_z(df, ["rd_ratio", "operating_margin"])
    financial_profitability = average_series(
        [
            masked_zscore(df["roe"], financial_mask),
            masked_zscore(df["net_margin"], financial_mask),
            masked_zscore(_safe_inverse(df["pbr_for_score"]), financial_mask),
        ]
    )
    financial_cash_generation = average_series(
        [
            masked_zscore(df["roe"], financial_mask),
            masked_zscore(df["dividend_yield_clean"], financial_mask),
            masked_zscore(_safe_inverse(df["pe_for_score"]), financial_mask),
        ]
    )
    financial_stability = average_series(
        [
            masked_zscore(-df["annual_volatility"].fillna(0), financial_mask),
            masked_zscore(_numeric(df, "operating_income_growth"), financial_mask),
            masked_zscore(_numeric(df, "revenue_growth"), financial_mask),
        ]
    )
    financial_competitive = average_series(
        [
            masked_zscore(np.log1p(assets.where(assets > 0)), financial_mask),
            masked_zscore(np.log1p(equity.where(equity > 0)), financial_mask),
            masked_zscore(np.log1p(df["avg_trading_value_60d"].where(df["avg_trading_value_60d"] > 0)), financial_mask),
        ]
    )
    df.loc[financial_mask, "profitability_score"] = financial_profitability.loc[financial_mask]
    df.loc[financial_mask, "cash_generation_score"] = financial_cash_generation.loc[financial_mask]
    df.loc[financial_mask, "stability_score"] = financial_stability.loc[financial_mask]
    df.loc[financial_mask, "competitive_position_score"] = financial_competitive.loc[financial_mask]
    df["score_treatment"] = np.where(
        financial_mask,
        "financial_sector_relative_roe_profit_stability_valuation",
        "general_operating_margin_ocf_leverage_quality",
    )
    df["moat_score"] = (
        0.35 * df["profitability_score"]
        + 0.25 * df["cash_generation_score"]
        + 0.20 * df["stability_score"]
        + 0.20 * df["competitive_position_score"]
    )
    df["moat_component_profitability"] = df["profitability_score"]
    df["moat_component_cashflow"] = df["cash_generation_score"]
    df["moat_component_stability"] = df["stability_score"]
    df["moat_component_competitive_position"] = df["competitive_position_score"]

    valuation_gap_component = average_series(
        [
            zscore(_safe_inverse(df["pbr_for_score"])).fillna(0),
            zscore(_safe_inverse(df["pe_for_score"])).fillna(0),
        ]
    )
    capital_efficiency_component = average_z(df, ["roe", "revenue_growth", "operating_income_growth"]).fillna(0)
    shareholder_return_component = zscore(df["dividend_yield_clean"]).fillna(0)
    reform_signal_component = average_z(df, ["operating_income_growth", "revenue_growth"]).fillna(0)
    df["transformation_score"] = (
        0.35 * zscore(_safe_inverse(df["pbr_for_score"])).fillna(0)
        + 0.20 * zscore(_safe_inverse(df["pe_for_score"])).fillna(0)
        + 0.20 * average_z(df, ["revenue_growth", "operating_income_growth"]).fillna(0)
        + 0.15 * zscore(df["dividend_yield_clean"]).fillna(0)
    )
    financial_transformation = (
        0.35 * masked_zscore(_safe_inverse(df["pbr_for_score"]), financial_mask)
        + 0.25 * masked_zscore(_safe_inverse(df["pe_for_score"]), financial_mask)
        + 0.20 * masked_zscore(df["roe"], financial_mask)
        + 0.20 * masked_zscore(df["dividend_yield_clean"], financial_mask)
    )
    df.loc[financial_mask, "transformation_score"] = financial_transformation.loc[financial_mask]
    financial_valuation_gap = average_series(
        [
            masked_zscore(_safe_inverse(df["pbr_for_score"]), financial_mask),
            masked_zscore(_safe_inverse(df["pe_for_score"]), financial_mask),
        ]
    )
    financial_capital_efficiency = masked_zscore(df["roe"], financial_mask)
    financial_shareholder_return = masked_zscore(df["dividend_yield_clean"], financial_mask)
    financial_reform_signal = average_series(
        [
            masked_zscore(df["roe"], financial_mask),
            masked_zscore(df["return_12m_ex_1m"], financial_mask),
        ]
    )
    df["transformation_component_valuation_gap"] = valuation_gap_component
    df["transformation_component_capital_efficiency"] = capital_efficiency_component
    df["transformation_component_shareholder_return"] = shareholder_return_component
    df["transformation_component_reform_signal"] = reform_signal_component
    df.loc[financial_mask, "transformation_component_valuation_gap"] = financial_valuation_gap.loc[
        financial_mask
    ]
    df.loc[financial_mask, "transformation_component_capital_efficiency"] = financial_capital_efficiency.loc[
        financial_mask
    ]
    df.loc[financial_mask, "transformation_component_shareholder_return"] = financial_shareholder_return.loc[
        financial_mask
    ]
    df.loc[financial_mask, "transformation_component_reform_signal"] = financial_reform_signal.loc[
        financial_mask
    ]

    for bucket in FUTURE_KEYWORDS:
        df[f"{bucket}_exposure"] = df.apply(lambda row: _future_exposure(row, bucket), axis=1)
    df["intangible_investment_score"] = zscore(df.get("rd_ratio", pd.Series(np.nan, index=df.index))).fillna(0)
    df["future_moat_component_ai_infrastructure"] = zscore(df["ai_infrastructure_exposure"]).fillna(0)
    df["future_moat_component_intangible_asset"] = df["intangible_investment_score"]
    df["future_moat_component_automation"] = zscore(df["automation_exposure"]).fillna(0)
    df["future_moat_component_data"] = zscore(df["data_software_exposure"]).fillna(0)
    df["future_moat_component_trust"] = zscore(df["trust_security_exposure"]).fillna(0)
    df["future_moat_score"] = (
        0.30 * df["future_moat_component_ai_infrastructure"]
        + 0.25 * df["future_moat_component_intangible_asset"]
        + 0.20 * df["future_moat_component_automation"]
        + 0.15 * df["future_moat_component_data"]
        + 0.10 * df["future_moat_component_trust"]
    )
    future_flag_labels = {
        "ai_infrastructure": "半導体・光通信・データセンター・電力",
        "automation": "電子部品・精密機器・省人化",
        "data_software": "クラウド・SaaS・業務データ",
        "trust_security": "セキュリティ・監査・信頼",
    }

    def _future_flags(row: pd.Series) -> str:
        flags = [
            label
            for bucket, label in future_flag_labels.items()
            if float(row.get(f"{bucket}_exposure", 0) or 0) > 0
        ]
        return ";".join(flags)

    def _future_evidence(row: pd.Series) -> str:
        evidence = []
        for bucket, keywords in FUTURE_KEYWORDS.items():
            if float(row.get(f"{bucket}_exposure", 0) or 0) > 0:
                evidence.append(f"{bucket}: {', '.join(keywords[:6])}")
        return "; ".join(evidence)

    df["future_moat_category_flags"] = df.apply(_future_flags, axis=1)
    df["future_moat_keyword_evidence"] = df.apply(_future_evidence, axis=1)

    df["valuation_score"] = (
        0.50 * zscore(_safe_inverse(df["pe_for_score"])).fillna(0)
        + 0.35 * zscore(_safe_inverse(df["pbr_for_score"])).fillna(0)
        + 0.15 * zscore(df["dividend_yield_clean"]).fillna(0)
    )
    financial_valuation = (
        0.45 * masked_zscore(_safe_inverse(df["pe_for_score"]), financial_mask)
        + 0.40 * masked_zscore(_safe_inverse(df["pbr_for_score"]), financial_mask)
        + 0.15 * masked_zscore(df["dividend_yield_clean"], financial_mask)
    )
    df.loc[financial_mask, "valuation_score"] = financial_valuation.loc[financial_mask]
    df["bb_score"] = (
        0.30 * df["moat_score"]
        + 0.25 * df["transformation_score"]
        + 0.30 * df["future_moat_score"]
        + 0.15 * df["valuation_score"]
    )
    df["momentum_score"] = zscore(df["return_12m_ex_1m"]).fillna(0)
    df["risk_score"] = average_z(
        df.assign(max_drawdown_abs=df["max_drawdown"].abs()),
        ["annual_volatility", "max_drawdown_abs"],
    ).fillna(0)
    df["adjusted_bb_score"] = df["bb_score"] + 0.10 * df["momentum_score"] - 0.10 * df["risk_score"]

    price_available = df["close"].notna() & (df["close"] > 0)
    liquid_20m_60d = price_available & (df["avg_trading_value_60d"].fillna(0) >= 20_000_000)
    df["price_available"] = price_available
    df["liquid_20m_60d"] = liquid_20m_60d
    df["investment_eligible"], _ = _investment_eligibility(df, liquid_20m_60d, config)
    if preliminary:
        df.loc[df["close"].notna() & (df["close"] > 0), "investment_eligible"] = True
    scored_mask = df["investment_eligible"].fillna(False).astype(bool)
    df["score_calculation_target"] = scored_mask
    for score_name in [
        "moat_score",
        "transformation_score",
        "future_moat_score",
        "valuation_score",
        "momentum_score",
        "risk_score",
        "adjusted_bb_score",
    ]:
        prefix = score_name.removesuffix("_score")
        df[f"{prefix}_rank"] = _score_rank(df[score_name], scored_mask)
        df[f"{prefix}_percentile"] = _score_percentile(df[score_name], scored_mask)
    df["category"] = df.apply(_category, axis=1)
    df = df.sort_values("adjusted_bb_score", ascending=False).reset_index(drop=True)
    df["score_rank"] = np.arange(1, len(df) + 1)
    df.to_csv(config.data_processed_dir / "scores.csv", index=False)

    summary = pd.DataFrame(
        [
            {"stage": "universe", "count": len(df)},
            {"stage": "price_available", "count": int(price_available.sum())},
            {"stage": "liquid_20m_60d", "count": int(liquid_20m_60d.sum())},
            {"stage": "investment_eligible", "count": int(df["investment_eligible"].sum())},
            {"stage": "scored", "count": int(scored_mask.sum())},
        ]
    )
    summary.to_csv(config.data_processed_dir / "screening_summary.csv", index=False)
    logger.info("Wrote scores.csv with %s rows", len(df))
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preliminary", action="store_true")
    args = parser.parse_args()
    score_universe(load_config(), preliminary=args.preliminary)


if __name__ == "__main__":
    main()
