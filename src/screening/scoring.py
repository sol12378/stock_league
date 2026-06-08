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
        "negative_ocf_years_3y",
        "operating_cf_years_available",
    ]
    if raw.empty or "code" not in raw.columns:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for code, group in raw.sort_values("submit_date").groupby("code"):
        operating_income = pd.to_numeric(group["operating_income"], errors="coerce").dropna().tail(3)
        operating_cf = pd.to_numeric(group["operating_cf"], errors="coerce").dropna().tail(3)
        rows.append(
            {
                "code": str(code),
                "operating_loss_years_3y": int((operating_income < 0).sum()),
                "operating_income_years_available": int(operating_income.notna().sum()),
                "negative_ocf_years_3y": int((operating_cf < 0).sum()),
                "operating_cf_years_available": int(operating_cf.notna().sum()),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _financial_like_mask(df: pd.DataFrame) -> pd.Series:
    sector = df.get("sector_33", pd.Series("", index=df.index)).fillna("").astype(str)
    sector_17 = df.get("sector_17", pd.Series("", index=df.index)).fillna("").astype(str)
    code = df.get("code", pd.Series("", index=df.index)).fillna("").astype(str)
    name = df.get("company_name", pd.Series("", index=df.index)).fillna("").astype(str)
    is_financial = _truthy(df.get("is_financial", pd.Series(False, index=df.index)))
    finance_sectors = {
        "Banks",
        "Insurance",
        "Securities and Commodities Futures",
        "Other Financing Business",
    }
    return (
        is_financial
        | sector.isin(finance_sectors)
        | sector_17.str.contains("BANKS|FINANCIAL|INSURANCE", case=False, na=False)
        | code.isin({"6178"})
        | name.str.contains("BANK|INSURANCE|SECURITIES|FINANCIAL|JAPAN POST HOLDINGS", case=False, na=False)
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
    negative_ocf_years = _numeric(df, "negative_ocf_years_3y").fillna(0)
    operating_cf_years = _numeric(df, "operating_cf_years_available").fillna(0)

    reasons: dict[str, pd.Series] = {
        "missing_financial_data": base_liquidity
        & (
            assets.isna()
            | equity.isna()
            | equity_ratio.isna()
            | operating_income.isna()
            | roe.isna()
            | (~financial_like & (revenue.isna() | operating_margin.isna() | operating_cf.isna() | ocf_margin.isna()))
        ),
        "low_equity_ratio": base_liquidity
        & (
            (~financial_like & (equity_ratio < 0.10))
            | (financial_like & ((equity_ratio < 0.02) | (equity <= 0)))
        ),
        "repeated_operating_loss": base_liquidity
        & (operating_income_years >= 2)
        & (operating_loss_years >= 2)
        & (operating_income < 0)
        & (operating_margin < -0.03),
        "repeated_negative_operating_cf": base_liquidity
        & ~financial_like
        & (operating_cf_years >= 2)
        & (negative_ocf_years >= 2),
        "excessive_leverage": base_liquidity
        & (
            (~financial_like & ((liabilities_to_equity > 8) | (equity <= 0)))
            | (financial_like & ((liabilities_to_equity > 50) | (equity <= 0)))
        ),
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
            (assets <= 0)
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
    reason_frame = reason_frame[base_liquidity & ~eligible].copy()
    reason_frame.to_csv(config.data_processed_dir / "investment_eligibility_exclusions.csv", index=False)

    counts = pd.DataFrame(
        [{"reason": reason, "excluded_companies": int(mask.fillna(False).sum())} for reason, mask in reasons.items()]
    )
    counts.loc[len(counts)] = {
        "reason": "unique_excluded_total",
        "excluded_companies": int((base_liquidity & failed).sum()),
    }
    counts.to_csv(config.data_processed_dir / "investment_eligibility_exclusion_summary.csv", index=False)
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

    df["profitability_score"] = average_z(df, ["operating_margin", "roe", "equity_ratio"])
    df["cash_generation_score"] = average_z(df, ["ocf_margin"])
    df["stability_score"] = average_z(df.assign(neg_vol=-df["annual_volatility"].fillna(0)), ["neg_vol"])
    df["competitive_position_score"] = average_z(df, ["rd_ratio", "operating_margin"])
    df["moat_score"] = (
        0.35 * df["profitability_score"]
        + 0.25 * df["cash_generation_score"]
        + 0.20 * df["stability_score"]
        + 0.20 * df["competitive_position_score"]
    )

    df["transformation_score"] = (
        0.35 * zscore(_safe_inverse(df["pbr_for_score"])).fillna(0)
        + 0.20 * zscore(_safe_inverse(df["pe_for_score"])).fillna(0)
        + 0.20 * average_z(df, ["revenue_growth", "operating_income_growth"]).fillna(0)
        + 0.15 * zscore(df["dividend_yield_clean"]).fillna(0)
    )

    for bucket in FUTURE_KEYWORDS:
        df[f"{bucket}_exposure"] = df.apply(lambda row: _future_exposure(row, bucket), axis=1)
    df["intangible_investment_score"] = zscore(df.get("rd_ratio", pd.Series(np.nan, index=df.index))).fillna(0)
    df["future_moat_score"] = (
        0.30 * zscore(df["ai_infrastructure_exposure"]).fillna(0)
        + 0.25 * df["intangible_investment_score"]
        + 0.20 * zscore(df["automation_exposure"]).fillna(0)
        + 0.15 * zscore(df["data_software_exposure"]).fillna(0)
        + 0.10 * zscore(df["trust_security_exposure"]).fillna(0)
    )

    df["valuation_score"] = (
        0.50 * zscore(_safe_inverse(df["pe_for_score"])).fillna(0)
        + 0.35 * zscore(_safe_inverse(df["pbr_for_score"])).fillna(0)
        + 0.15 * zscore(df["dividend_yield_clean"]).fillna(0)
    )
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
    investable_base = liquid_20m_60d & (df["price_history_days"].fillna(0) >= 500)
    df["price_available"] = price_available
    df["liquid_20m_60d"] = liquid_20m_60d
    df["investment_eligible"], _ = _investment_eligibility(df, investable_base, config)
    if preliminary:
        df.loc[df["close"].notna() & (df["close"] > 0), "investment_eligible"] = True
    scored_mask = df["investment_eligible"] & df["adjusted_bb_score"].notna()
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
