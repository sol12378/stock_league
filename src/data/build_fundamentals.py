from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


def _safe_div(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series | float:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = numerator / denominator
    if isinstance(out, pd.Series):
        return out.replace([np.inf, -np.inf], np.nan)
    return np.nan if not np.isfinite(out) else out


def _latest_metric(group: pd.DataFrame, metric: str) -> float:
    values = group.sort_values("submit_date", ascending=False)[metric].dropna()
    return float(values.iloc[0]) if not values.empty else np.nan


def _growth_metric(group: pd.DataFrame, metric: str) -> float:
    clean = group.sort_values("submit_date").dropna(subset=[metric])
    clean = clean[clean[metric] > 0]
    if len(clean) < 2:
        return np.nan
    first = float(clean.iloc[0][metric])
    last = float(clean.iloc[-1][metric])
    years = max(1, len(clean) - 1)
    return (last / first) ** (1 / years) - 1 if first > 0 and last > 0 else np.nan


def _latest_text(group: pd.DataFrame, column: str) -> str:
    if group.empty or column not in group.columns:
        return ""
    values = group.sort_values("submit_date", ascending=False)[column].dropna().astype(str).str.strip()
    return values.iloc[0] if not values.empty else ""


def build_fundamentals(config: AppConfig) -> pd.DataFrame:
    logger = setup_logger("build_fundamentals", config.logs_dir)
    universe = pd.read_csv(config.data_processed_dir / "universe.csv", dtype={"code": str})
    metrics_path = config.data_processed_dir / "yfinance_metrics.csv"
    yf_metrics = pd.read_csv(metrics_path) if metrics_path.exists() else pd.DataFrame()
    raw_path = config.data_processed_dir / "fundamentals_raw.csv"
    raw = pd.read_csv(raw_path, dtype={"code": str}) if raw_path.exists() else pd.DataFrame()

    rows: list[dict[str, object]] = []
    for _, company in universe.iterrows():
        ticker = company["ticker"]
        code = company["code"]
        company_raw = raw[raw["code"] == code] if not raw.empty else pd.DataFrame()
        yf_row = (
            yf_metrics[yf_metrics["ticker"] == ticker].iloc[0].to_dict()
            if not yf_metrics.empty and (yf_metrics["ticker"] == ticker).any()
            else {}
        )

        latest: dict[str, float] = {}
        for metric in [
            "revenue",
            "operating_income",
            "ordinary_income",
            "net_income",
            "total_assets",
            "equity",
            "operating_cf",
            "investing_cf",
            "financing_cf",
            "rd_expense",
            "capex",
            "employees",
        ]:
            latest[metric] = _latest_metric(company_raw, metric) if not company_raw.empty else np.nan

        revenue = latest["revenue"]
        equity = latest["equity"]
        assets = latest["total_assets"]
        rows.append(
            {
                "code": code,
                "ticker": ticker,
                "company_name": company["company_name"],
                "company_name_ja": _latest_text(company_raw, "filer_name"),
                "market": company["market"],
                "sector_33": company["sector_33"],
                "sector_17": company["sector_17"],
                "scale_category": company["scale_category"],
                "is_financial": bool(company["is_financial"]),
                **latest,
                "revenue_growth": _growth_metric(company_raw, "revenue")
                if not company_raw.empty
                else np.nan,
                "operating_income_growth": _growth_metric(company_raw, "operating_income")
                if not company_raw.empty
                else np.nan,
                "operating_margin": _safe_div(latest["operating_income"], revenue),
                "roe": _safe_div(latest["net_income"], equity),
                "equity_ratio": _safe_div(equity, assets),
                "ocf_margin": _safe_div(latest["operating_cf"], revenue),
                "rd_ratio": _safe_div(latest["rd_expense"], revenue),
                "capex_ratio": _safe_div(latest["capex"], revenue),
                "market_cap": yf_row.get("market_cap", np.nan),
                "enterprise_value": yf_row.get("enterprise_value", np.nan),
                "trailing_pe": yf_row.get("trailing_pe", np.nan),
                "forward_pe": yf_row.get("forward_pe", np.nan),
                "price_to_book": yf_row.get("price_to_book", np.nan),
                "dividend_yield": yf_row.get("dividend_yield", np.nan),
                "beta": yf_row.get("beta", np.nan),
                "shares_outstanding": yf_row.get("shares_outstanding", np.nan),
                "ebitda": yf_row.get("ebitda", np.nan),
            }
        )

    fundamentals = pd.DataFrame(rows)
    fundamentals.to_csv(config.data_processed_dir / "fundamentals_clean.csv", index=False)
    logger.info("Wrote fundamentals_clean.csv with %s rows", len(fundamentals))
    return fundamentals


def main() -> None:
    build_fundamentals(load_config())


if __name__ == "__main__":
    main()
