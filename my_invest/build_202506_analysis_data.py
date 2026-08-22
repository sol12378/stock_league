from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("..").resolve()
OUT = Path("outputs/tenbagger_screen_20250630")
CUTOFF = pd.Timestamp("2025-06-30")


# Values below are only from disclosures published by 2025-06-30. Growth rates
# follow the issuer's same-basis year-on-year presentation where available.
FORECASTS = {
    "9338": (46.2, 39.3, "2025-05-14", "2025/12 Q1", "https://www2.jpx.co.jp/disc/93380/140120250514549526.pdf", "連結→連結"),
    "5032": (16.6, 19.8, "2025-06-11", "2025/4 results; 2026/4 range midpoint", "https://www2.jpx.co.jp/disc/50320/140120250611586982.pdf", "単体→単体・予想レンジ中点"),
    "5253": (21.0, 2.5, "2025-05-13", "2025/3 results; 2026/3 plan", "https://www2.jpx.co.jp/disc/52530/140120250513546153.pdf", "連結→連結"),
    "5575": (28.0, 25.0, "2025-04-14", "2025/5 Q3", "https://www2.jpx.co.jp/disc/55750/140120250414515466.pdf", "単体→単体"),
    "5136": (48.3, 96.9, "2025-06-16", "2025/10 H1", "https://www2.jpx.co.jp/disc/51360/140120250616590989.pdf", "連結→連結（企業結合再測定後）"),
    "5588": (38.4, 30.4, "2025-05-15", "2025/12 Q1", "https://www2.jpx.co.jp/disc/55880/140120250515553285.pdf", "単体→単体"),
    "4377": (37.5, 43.3, "2025-05-14", "2025/12 Q1", "https://www2.jpx.co.jp/disc/43770/140120250514552532.pdf", "連結→連結"),
    "9237": (56.4, 20.6, "2025-06-13", "2025/11 H1", "https://www2.jpx.co.jp/disc/92370/140120250613589639.pdf", "連結予想／履歴は単体中心"),
    "4019": (30.6, -55.4, "2025-05-15", "2025/12 Q1", "https://www2.jpx.co.jp/disc/40190/140120250515554790.pdf", "連結→連結（履歴スクリーニングは単体）"),
    "5038": (30.2, 31.5, "2025-05-14", "2025/12 Q1", "https://www2.jpx.co.jp/disc/50380/140120250514552171.pdf", "単体→単体"),
    "5132": (35.4, 119.4, "2025-06-11", "2025/10 H1", "https://contents.xj-storage.jp/xcontents/AS09142/980ced2b/52aa/4cbc/aa61/4801aa82e8c7/140120250611586970.pdf", "単体→単体"),
    "9225": (20.4, -35.1, "2025-05-09", "2025/9 H1", "https://www2.jpx.co.jp/disc/92250/140120250509537793.pdf", "連結予想／履歴は単体中心"),
    "4071": (27.4, 23.6, "2025-05-14", "2025/9 H1", "https://www2.jpx.co.jp/disc/40710/140120250514552334.pdf", "連結→連結"),
}


def constant_years(rate: float, target: float = 2.0) -> float:
    if not np.isfinite(rate) or rate <= 0:
        return np.nan
    return math.log(target) / math.log1p(rate)


def durable_years(initial: float, target: float, max_years: int = 25) -> float:
    if not np.isfinite(initial) or initial <= 0:
        return np.nan
    floor = 0.12 if initial >= 0.12 else initial
    multiple = 1.0
    for year in range(1, max_years + 1):
        growth = max(floor, initial * (0.88 ** (year - 1)))
        multiple *= 1.0 + growth
        if multiple >= target:
            return float(year)
    return np.nan


def price_path_stats(group: pd.DataFrame) -> dict[str, object]:
    group = group.sort_values("date").dropna(subset=["adj_close"]).copy()
    dates = group["date"].to_numpy(dtype="datetime64[D]")
    px = group["adj_close"].astype(float).to_numpy()
    n = len(px)
    doubled = np.zeros(n, dtype=bool)
    days = np.full(n, np.nan)
    for i in range(n):
        hits = np.flatnonzero(px[i:] >= 2.0 * px[i])
        if len(hits):
            j = i + int(hits[0])
            doubled[i] = True
            days[i] = float((dates[j] - dates[i]).astype("timedelta64[D]").astype(int))
    first_days = days[0] if n and doubled[0] else np.nan
    return {
        "price_history_start": str(pd.Timestamp(dates[0]).date()) if n else None,
        "price_history_end": str(pd.Timestamp(dates[-1]).date()) if n else None,
        "observations": n,
        "first_observation_close_adj": px[0] if n else np.nan,
        "last_close_adj": px[-1] if n else np.nan,
        "max_close_adj": np.nanmax(px) if n else np.nan,
        "max_multiple_from_first": np.nanmax(px) / px[0] if n else np.nan,
        "first_observation_to_2x_days": first_days,
        "rolling_buy_dates_doubled": int(doubled.sum()),
        "rolling_buy_dates_total": n,
        "rolling_attainment_rate": doubled.mean() if n else np.nan,
        "attainment_days_median": np.nanmedian(days) if doubled.any() else np.nan,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    screen = pd.read_csv(OUT / "screening_all_companies.csv", dtype={"code": str})
    strict = screen[screen["strict_overlap_count"] == 4].copy()
    strict["code"] = strict["code"].str.zfill(4)
    strict["ticker"] = strict["ticker"].astype(str)

    input_rows = []
    for row in strict.itertuples(index=False):
        rev_g, op_g, source_date, source_label, source_url, basis = FORECASTS[row.code]
        input_rows.append({
            "code": row.code,
            "ticker": row.ticker,
            "company_name": row.company_name,
            "market": row.market,
            "sector": row.sector_33,
            "historical_revenue_cagr_4y": row.revenue_cagr_4y,
            "latest_operating_margin": row.operating_margin_latest,
            "forecast_revenue_growth": rev_g / 100.0,
            "forecast_operating_profit_growth": op_g / 100.0,
            "forecast_source_date": source_date,
            "forecast_source_label": source_label,
            "forecast_source_url": source_url,
            "comparison_basis": basis,
            "listing_date": row.listing_date_for_test,
            "listing_date_source": row.listing_date_source,
            "top_shareholder_name": row.top_shareholder_name,
            "top_shareholder_ratio": row.top_shareholder_ratio,
            "close_2025_06_30": row.close,
            "shares_outstanding_latest_pre_cutoff": row.shares_outstanding_pti,
            "market_cap_proxy_jpy": row.market_cap_proxy_jpy,
            "price_to_sales_proxy": row.price_to_sales_proxy,
            "annual_volatility_pre_cutoff": row.annual_volatility,
            "max_drawdown_pre_cutoff": row.max_drawdown,
            "avg_trading_value_60d_jpy": row.avg_trading_value_60d,
            "latest_annual_report_submit_date": row.submit_date,
            "latest_annual_report_doc_id": row.doc_id,
        })
    inputs = pd.DataFrame(input_rows)
    inputs.to_csv(OUT / "candidate_inputs_20250630.csv", index=False)

    model_rows = []
    for row in inputs.itertuples(index=False):
        initial = max(0.0, min(0.50,
            0.20 * row.historical_revenue_cagr_4y
            + 0.40 * row.forecast_revenue_growth
            + 0.40 * row.forecast_operating_profit_growth
        ))
        model_rows.append({
            "code": row.code,
            "company_name": row.company_name,
            "historical_revenue_cagr_4y": row.historical_revenue_cagr_4y,
            "forecast_revenue_growth": row.forecast_revenue_growth,
            "forecast_operating_profit_growth": row.forecast_operating_profit_growth,
            "durability_adjusted_initial_growth": initial,
            "historical_cagr_constant_years": constant_years(row.historical_revenue_cagr_4y),
            "forecast_op_growth_constant_years": constant_years(row.forecast_operating_profit_growth),
            "years_per_plus_25pct": durable_years(initial, 1.6),
            "years_per_flat": durable_years(initial, 2.0),
            "years_per_minus_25pct": durable_years(initial, 2.0 / 0.75),
            "years_10pct_dilution": durable_years(initial, 2.2),
            "market_cap_proxy_jpy": row.market_cap_proxy_jpy,
            "double_market_cap_proxy_jpy": row.market_cap_proxy_jpy * 2,
            "price_to_sales_proxy": row.price_to_sales_proxy,
            "comparison_basis": row.comparison_basis,
        })
    model = pd.DataFrame(model_rows).sort_values(
        ["years_per_flat", "price_to_sales_proxy"], na_position="last"
    ).reset_index(drop=True)
    model.insert(0, "model_rank", np.arange(1, len(model) + 1))
    model.to_csv(OUT / "double_13_period_model_20250630.csv", index=False)

    condition_summary = pd.DataFrame([
        {"metric": "reconstructible_universe", "count": len(screen), "definition": "later local snapshot, observable by 2025-06-30"},
        {"metric": "five_year_revenue_complete", "count": int(screen["revenue_5y_complete"].sum()), "definition": "five same-series annual revenue observations"},
        {"metric": "each_of_four_yoy_revenue_growth_ge_20pct", "count": int(screen["c1_each_yoy_20"].sum()), "definition": "strict condition 1"},
        {"metric": "four_year_revenue_cagr_ge_20pct", "count": int(screen["c1_cagr_20"].sum()), "definition": "relaxed condition 1"},
        {"metric": "latest_operating_margin_ge_10pct", "count": int(screen["c2_operating_margin_10"].sum()), "definition": "condition 2"},
        {"metric": "listed_within_five_years", "count": int(screen["c3_listed_within_5y"].sum()), "definition": "condition 3"},
        {"metric": "leader_is_top_shareholder", "count": int(screen["c4_leader_top_holder_strict"].sum()), "definition": "condition 4"},
        {"metric": "strict_four_condition_matches", "count": int((screen["strict_overlap_count"] == 4).sum()), "definition": "all strict conditions"},
        {"metric": "cagr_four_condition_matches", "count": int((screen["cagr_overlap_count"] == 4).sum()), "definition": "CAGR variant"},
    ])
    condition_summary.to_csv(OUT / "condition_summary_20250630.csv", index=False)

    universe_audit = pd.DataFrame([
        {"stage": "latest_edinet_document_by_cutoff", "count": 3577, "max_information_date": "2025-06-30 16:46", "post_cutoff_rows": 0},
        {"stage": "matched_pre_cutoff_price_history", "count": len(screen), "max_information_date": "2025-06-30", "post_cutoff_rows": 0},
        {"stage": "five_year_revenue_complete", "count": int(screen["revenue_5y_complete"].sum()), "max_information_date": "2025-06-30", "post_cutoff_rows": 0},
        {"stage": "strict_four_condition_matches", "count": int((screen["strict_overlap_count"] == 4).sum()), "max_information_date": "2025-06-30", "post_cutoff_rows": 0},
    ])
    universe_audit.to_csv(OUT / "universe_reconstruction_audit_20250630.csv", index=False)

    prices = pd.read_parquet(
        ROOT / "data/processed/prices_daily.parquet",
        columns=["date", "ticker", "adj_close"],
    )
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices = prices[prices["date"] <= CUTOFF]
    stats = []
    for row in inputs.itertuples(index=False):
        s = price_path_stats(prices[prices["ticker"] == row.ticker])
        stats.append({"code": row.code, "company_name": row.company_name, **s})
    price_stats = pd.DataFrame(stats)
    price_stats.to_csv(OUT / "price_history_test_20250630.csv", index=False)

    audit = {
        "hard_cutoff": "2025-06-30 23:59:59 JST",
        "candidate_count": int(len(inputs)),
        "max_annual_report_submit_date": str(pd.to_datetime(inputs["latest_annual_report_submit_date"]).max()),
        "max_forecast_source_date": str(pd.to_datetime(inputs["forecast_source_date"]).max().date()),
        "max_price_history_date": str(pd.to_datetime(price_stats["price_history_end"]).max().date()),
        "post_cutoff_annual_report_rows": int((pd.to_datetime(inputs["latest_annual_report_submit_date"]) > CUTOFF).sum()),
        "post_cutoff_forecast_rows": int((pd.to_datetime(inputs["forecast_source_date"]) > CUTOFF).sum()),
        "post_cutoff_price_rows": int((pd.to_datetime(price_stats["price_history_end"]) > CUTOFF).sum()),
        "uses_realized_returns_after_cutoff": False,
        "universe_limitation": "Rebuilt only from local EDINET submissions dated by cutoff and price observations dated by cutoff; the local archive may not be a complete historical exchange master.",
    }
    (OUT / "leak_audit_20250630.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(model.to_string(index=False))
    print(price_stats.to_string(index=False))
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
