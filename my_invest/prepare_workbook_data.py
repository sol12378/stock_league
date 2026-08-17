from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


OUT_DIR = Path("outputs/tenbagger_screen_20260814")


def clean(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        return value.item()
    return value


def records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    return [{col: clean(row.get(col)) for col in columns} for _, row in df.iterrows()]


def main() -> None:
    df = pd.read_csv(OUT_DIR / "screening_all_companies.csv", dtype={"code": str, "doc_id": str})
    df["code"] = df["code"].str.zfill(4)
    df["raw_excel_row"] = range(2, len(df) + 2)

    all_columns = [
        "screen_rank", "code", "ticker", "company_name", "market", "sector_33",
        "revenue_p0", "revenue_p1", "revenue_p2", "revenue_p3", "revenue_p4",
        "operating_income_current", "listing_date_for_test", "listing_date_source",
        "top_shareholder_name", "top_shareholder_ratio", "leader_names",
        "c4_leader_top_holder_strict", "c4_owner_proxy_broad", "first_price_date",
        "doc_id", "revenue_concept", "operating_income_concept", "period_end_latest",
        "fiscal_period_days", "shares_outstanding_pti", "close", "latest_date",
        "avg_trading_value_60d", "annual_volatility", "max_drawdown", "investment_eligible",
        "investment_exclusion_reasons", "adjusted_bb_score", "score_rank", "category",
        "purchase_risk_notes", "submit_date", "period_start_latest", "history_listing_date",
        "history_listing_evidence", "matched_leader", "company_name_ja", "scale_category",
    ]
    strict4 = df[df["strict_overlap_count"] == 4].copy()
    cagr4 = df[df["cagr_overlap_count"] == 4].copy()
    candidate_union = df[
        (df["strict_overlap_count"] >= 3)
        | (df["cagr_overlap_count"] >= 3)
        | (df["cagr_owner_proxy_overlap_count"] >= 3)
    ].copy()
    c1 = df[df["c1_cagr_20"]].sort_values(
        ["c1_each_yoy_20", "revenue_cagr_4y"], ascending=[False, False]
    )
    c2 = df[df["c2_operating_margin_10"]].sort_values("operating_margin_latest", ascending=False)
    c3 = df[df["c3_listed_within_5y"]].sort_values(
        ["strict_overlap_count", "cagr_overlap_count", "listing_date_for_test"], ascending=[False, False, False]
    )
    c4 = df[df["c4_owner_proxy_broad"]].sort_values(
        ["c4_leader_top_holder_strict", "top_shareholder_ratio"], ascending=[False, False]
    )

    checks = json.loads((OUT_DIR / "checks.json").read_text(encoding="utf-8"))
    payload = {
        "as_of": "2026-08-14",
        "price_as_of": str(df["latest_date"].dropna().max()),
        "universe_effective": "2026-04-30",
        "checks": checks,
        "all": records(df, all_columns),
        "strict4_rows": strict4["raw_excel_row"].tolist(),
        "cagr4_rows": cagr4["raw_excel_row"].tolist(),
        "candidate_rows": candidate_union["raw_excel_row"].tolist(),
        "c1_rows": c1["raw_excel_row"].tolist(),
        "c2_rows": c2["raw_excel_row"].tolist(),
        "c3_rows": c3["raw_excel_row"].tolist(),
        "c4_rows": c4["raw_excel_row"].tolist(),
        "local_sources": [
            {
                "item": "上場銘柄母集団",
                "path": str((Path("../data/processed/universe.csv")).resolve()),
                "as_of": "2026-04-30",
                "notes": "東証内国株式 3,649社",
                "url": "https://www.jpx.co.jp/listing/co-search/",
            },
            {
                "item": "有価証券報告書XBRL",
                "path": str((Path("../data/raw/edinet/xbrl.zip")).resolve()),
                "as_of": "各社最新有報（2026-08-14以前）",
                "notes": "売上5期、大株主、役員、沿革を抽出。doc_idを全銘柄シートに記録",
                "url": "https://www.fsa.go.jp/search/20130917.html",
            },
            {
                "item": "株価日次",
                "path": str((Path("../data/processed/prices_daily.parquet")).resolve()),
                "as_of": str(df["latest_date"].dropna().max()),
                "notes": "初回取引日、価格、流動性、リスク指標",
                "url": "https://www.jpx.co.jp/listing/co-search/",
            },
            {
                "item": "既存投資適格性・リスクスコア",
                "path": str((Path("../data/processed/scores.csv")).resolve()),
                "as_of": "2026-06-01",
                "notes": "スクリーニング4条件とは独立した警告として利用",
                "url": "",
            },
        ],
    }
    (OUT_DIR / "workbook_data.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
