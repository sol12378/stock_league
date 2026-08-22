from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

import run_tenbagger_screen as base


ROOT = Path("..").resolve()
OUT_DIR = Path("outputs/tenbagger_screen_20250630")
AS_OF_DATE = pd.Timestamp("2025-06-30 23:59:59")
PRICE_AS_OF_DATE = pd.Timestamp("2025-06-30")
LISTING_CUTOFF = pd.Timestamp("2020-06-30")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = pd.read_parquet(
        ROOT / "data/processed/prices_daily.parquet",
        columns=["date", "ticker", "close", "adj_close", "volume"],
    )
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices = prices[prices["date"] <= PRICE_AS_OF_DATE].copy()
    price_dates = prices.groupby("ticker")["date"].agg(
        first_price_date="min", last_price_date="max"
    ).reset_index()

    docs = pd.read_csv(
        ROOT / "data/processed/edinet_documents.csv",
        dtype={"code": str, "doc_id": str},
    )
    docs["code"] = docs["code"].str.zfill(4)
    docs["submit_date_parsed"] = pd.to_datetime(docs["submit_date"], errors="coerce")
    docs = docs[docs["submit_date_parsed"] <= AS_OF_DATE].sort_values(
        ["code", "submit_date_parsed"]
    )
    latest_docs = docs.groupby("code", as_index=False).tail(1)

    # Build the investable reconstruction exclusively from pre-cutoff-dated
    # EDINET submissions and pre-cutoff price observations. Do not use a later
    # JPX membership snapshot, which would leak future survival/delisting state.
    universe = latest_docs[["code", "filer_name"]].copy()
    universe = universe.rename(columns={"filer_name": "company_name"})
    universe["ticker"] = universe["code"] + ".T"
    universe["market"] = "not used (historical reconstruction)"
    universe["sector_33"] = "not used (historical reconstruction)"
    universe = universe.merge(price_dates[["ticker", "first_price_date"]], on="ticker", how="inner")
    universe = universe[universe["first_price_date"] <= PRICE_AS_OF_DATE].copy()

    extracted_rows = []
    with zipfile.ZipFile(ROOT / "data/raw/edinet/xbrl.zip") as outer:
        available = set(outer.namelist())
        total = len(latest_docs)
        for idx, row in enumerate(latest_docs.itertuples(index=False), start=1):
            member = f"xbrl/{row.doc_id}.zip"
            record = {
                "code": row.code,
                "doc_id": row.doc_id,
                "filer_name": row.filer_name,
                "submit_date": row.submit_date,
                "period_start_latest": row.period_start,
                "period_end_latest": row.period_end,
            }
            try:
                extracted = (
                    base.extract_one_document(outer.read(member))
                    if member in available
                    else {"parse_error": "nested zip missing"}
                )
            except Exception as exc:
                extracted = {"parse_error": f"{type(exc).__name__}: {exc}"}
            extracted_rows.append({**record, **extracted})
            if idx % 500 == 0 or idx == total:
                print(f"parsed {idx}/{total}", flush=True)

    extracted_df = pd.DataFrame(extracted_rows)
    extracted_df.to_csv(OUT_DIR / "xbrl_latest_extracted.csv", index=False)

    results = universe.merge(extracted_df, on="code", how="left").merge(
        price_dates, on="ticker", how="left", suffixes=("", "_prices")
    )
    for i in range(1, 5):
        results[f"revenue_growth_{i}"] = [
            base.growth_rate(cur, prior)
            for cur, prior in zip(results[f"revenue_p{i}"], results[f"revenue_p{i-1}"])
        ]
    results["revenue_cagr_4y"] = [
        base.safe_cagr(cur, prior, 4)
        for cur, prior in zip(results["revenue_p4"], results["revenue_p0"])
    ]
    results["revenue_5y_complete"] = results[
        [f"revenue_p{i}" for i in range(5)]
    ].notna().all(axis=1)
    results["c1_each_yoy_20"] = (
        results[[f"revenue_growth_{i}" for i in range(1, 5)]].ge(0.20).all(axis=1)
        & results["revenue_5y_complete"]
    )
    results["c1_cagr_20"] = (
        results["revenue_cagr_4y"].ge(0.20) & results["revenue_5y_complete"]
    )
    results["operating_margin_latest"] = (
        results["operating_income_current"] / results["revenue_p4"].replace(0, np.nan)
    )
    results["c2_operating_margin_10"] = results["operating_margin_latest"].ge(0.10)
    results["listing_date_proxy"] = results["history_listing_date"].fillna(
        results["first_price_date"].dt.strftime("%Y-%m-%d")
    )
    results["listing_date_for_test"] = pd.to_datetime(
        results["listing_date_proxy"], errors="coerce"
    )
    price_history_floor = prices["date"].min()
    reliable_first_trade = results["first_price_date"] > price_history_floor + pd.Timedelta(days=7)
    results.loc[reliable_first_trade, "listing_date_for_test"] = results.loc[
        reliable_first_trade, "first_price_date"
    ]
    results["listing_date_source"] = np.where(
        reliable_first_trade,
        "local_price_first_trade",
        np.where(
            results["history_listing_date"].notna(),
            "EDINET_company_history",
            "not_identified_before_local_window",
        ),
    )
    results["c3_listed_within_5y"] = results["listing_date_for_test"].ge(LISTING_CUTOFF)
    results["c4_leader_top_holder_strict"] = (
        results["leader_is_top_shareholder"].fillna(False).astype(bool)
    )
    results["c4_owner_proxy_broad"] = (
        results["c4_leader_top_holder_strict"]
        | results["top_holder_is_individual"].fillna(False).astype(bool)
    )

    strict_cols = [
        "c1_each_yoy_20",
        "c2_operating_margin_10",
        "c3_listed_within_5y",
        "c4_leader_top_holder_strict",
    ]
    cagr_cols = [
        "c1_cagr_20",
        "c2_operating_margin_10",
        "c3_listed_within_5y",
        "c4_leader_top_holder_strict",
    ]
    results["strict_overlap_count"] = results[strict_cols].sum(axis=1)
    results["cagr_overlap_count"] = results[cagr_cols].sum(axis=1)

    latest_price = (
        prices.sort_values("date").groupby("ticker", as_index=False).tail(1)[
            ["ticker", "date", "close", "adj_close"]
        ].rename(columns={"date": "price_date"})
    )
    shares = pd.read_csv(
        ROOT / "outputs/phase2_top1200_walkforward_perfect_fix/xbrl_facts/edinet_xbrl_extended_facts.csv",
        usecols=["code", "doc_id", "shares_outstanding_pti"],
        dtype={"code": str, "doc_id": str},
    )
    shares["code"] = shares["code"].str.zfill(4)
    shares = shares.drop_duplicates("doc_id", keep="last")
    results = results.merge(shares, on=["code", "doc_id"], how="left").merge(
        latest_price, on="ticker", how="left"
    )
    results["market_cap_proxy_jpy"] = results["close"] * results["shares_outstanding_pti"]
    results["price_to_sales_proxy"] = (
        results["market_cap_proxy_jpy"] / results["revenue_p4"].replace(0, np.nan)
    )

    stats_rows = []
    for ticker, group in prices.sort_values("date").groupby("ticker"):
        group = group.dropna(subset=["adj_close"])
        returns = group["adj_close"].pct_change().dropna()
        running_max = group["adj_close"].cummax()
        drawdown = group["adj_close"] / running_max - 1
        recent = group[group["date"] > PRICE_AS_OF_DATE - pd.Timedelta(days=100)]
        stats_rows.append(
            {
                "ticker": ticker,
                "annual_volatility": returns.std(ddof=1) * np.sqrt(252) if len(returns) > 1 else np.nan,
                "max_drawdown": drawdown.min() if len(drawdown) else np.nan,
                "avg_trading_value_60d": (recent.tail(60)["close"] * recent.tail(60)["volume"]).mean(),
                "history_days": len(group),
            }
        )
    results = results.merge(pd.DataFrame(stats_rows), on="ticker", how="left")

    results = results.sort_values(
        ["strict_overlap_count", "cagr_overlap_count", "revenue_cagr_4y", "operating_margin_latest"],
        ascending=[False, False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    results.insert(0, "screen_rank", np.arange(1, len(results) + 1))
    results.to_csv(OUT_DIR / "screening_all_companies.csv", index=False)
    results[(results["strict_overlap_count"] >= 3) | (results["cagr_overlap_count"] >= 3)].to_csv(
        OUT_DIR / "ranked_candidates.csv", index=False
    )

    checks = {
        "cutoff_timestamp": AS_OF_DATE.isoformat(),
        "price_cutoff": PRICE_AS_OF_DATE.date().isoformat(),
        "universe_rows_pre_cutoff_records": int(len(universe)),
        "latest_docs": int(len(latest_docs)),
        "max_selected_submit_date": str(pd.to_datetime(extracted_df["submit_date"]).max()),
        "max_price_date": str(prices["date"].max()),
        "parsed_rows": int(extracted_df["parse_error"].isna().sum()),
        "five_year_revenue_coverage": int(results["revenue_5y_complete"].sum()),
        "strict_four_condition_matches": int((results["strict_overlap_count"] == 4).sum()),
        "cagr_four_condition_matches": int((results["cagr_overlap_count"] == 4).sum()),
        "future_submit_rows": int((pd.to_datetime(extracted_df["submit_date"]) > AS_OF_DATE).sum()),
        "future_price_rows": int((prices["date"] > PRICE_AS_OF_DATE).sum()),
    }
    (OUT_DIR / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2), flush=True)
    print(
        results[results["strict_overlap_count"] == 4][
            [
                "code", "company_name", "revenue_cagr_4y", "operating_margin_latest",
                "listing_date_for_test", "top_shareholder_name", "top_shareholder_ratio",
                "market_cap_proxy_jpy", "price_to_sales_proxy", "submit_date",
            ]
        ].to_string(index=False),
        flush=True,
    )


if __name__ == "__main__":
    main()
