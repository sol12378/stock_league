"""Part 4: 現在の選定基準日で、Price軸の欠測を直したうえで新4軸案を実行する。

Price軸の直し方: yfinance(売買代金上位300社のみ)ではなく、XBRLから取れる発行済株式数
(PITパネルの shares_outstanding_pti の各社最新値)×現在株価 で時価総額を作り、
益回り(純利益/時価総額)と純資産倍率の逆数(自己資本/時価総額)を全社で計算する。

出力: work/new_4axis_screen/out/repaired_*.csv / repaired_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"
N_PICK, SECTOR_CAP = 20, 2


def pr(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").mul(100.0)


def blend(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return pd.DataFrame({c: pr(df[c]) for c in cols}).mean(axis=1, skipna=True)


def pick(d: pd.DataFrame, key: str, n: int, cap: int | None) -> pd.DataFrame:
    d = d.sort_values(key, ascending=False)
    if cap is None:
        return d.head(n)
    out, counts = [], {}
    for _, row in d.iterrows():
        sec = row["sector_33"]
        if counts.get(sec, 0) >= cap:
            continue
        out.append(row)
        counts[sec] = counts.get(sec, 0) + 1
        if len(out) == n:
            break
    return pd.DataFrame(out)


def main() -> None:
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False,
                        usecols=["code", "fiscal_year", "shares_outstanding_pti"])
    shares = (
        panel.dropna(subset=["shares_outstanding_pti"])
        .sort_values("fiscal_year")
        .groupby("code", as_index=False)
        .last()
        .rename(columns={"shares_outstanding_pti": "shares_xbrl", "fiscal_year": "shares_fy"})
    )

    d = scores[scores["investment_eligible"].fillna(False).astype(bool)].copy()
    d = d.merge(shares, on="code", how="left")

    report: dict[str, object] = {"eligible": int(len(d))}
    report["shares_coverage"] = {
        "yfinance_only": int(d["shares_outstanding"].notna().sum()),
        "xbrl_repaired": int(d["shares_xbrl"].notna().sum()),
        "xbrl_repaired_pct": round(float(d["shares_xbrl"].notna().mean() * 100), 1),
        "shares_fy_distribution": d["shares_fy"].value_counts(dropna=False).astype(int).to_dict(),
    }
    # yfinance と XBRL の株式数が一致するか(直し方の妥当性チェック)
    both = d[d["shares_outstanding"].notna() & d["shares_xbrl"].notna()]
    ratio = both["shares_xbrl"] / both["shares_outstanding"]
    report["shares_cross_check_vs_yfinance"] = {
        "n": int(len(both)),
        "median_ratio": round(float(ratio.median()), 4),
        "within_5pct": int((ratio.between(0.95, 1.05)).sum()),
        "within_5pct_share": round(float(ratio.between(0.95, 1.05).mean() * 100), 1),
    }

    d["market_cap_repaired"] = d["shares_xbrl"] * d["close"]
    mc = d["market_cap_repaired"].where(d["market_cap_repaired"] > 0)
    d["earnings_to_price"] = d["net_income"] / mc
    d["book_to_market"] = d["equity"] / mc

    d["moat_p"] = blend(d, ["operating_margin", "roe", "equity_ratio", "ocf_margin"])
    d["change_p"] = blend(d, ["revenue_growth", "operating_income_growth"])
    d["future_p"] = blend(d, ["future_moat_score"])
    d["price_p_repaired"] = blend(d, ["earnings_to_price", "book_to_market"])
    d["price_p_asis"] = pr(d["valuation_score"])

    for tag, pcol in [("repaired", "price_p_repaired"), ("asis", "price_p_asis")]:
        d[f"total_{tag}"] = d[["moat_p", "change_p", "future_p", pcol]].mean(axis=1)

    report["price_axis_coverage"] = {
        "asis_movable_companies": int(d["valuation_score"].ne(0).sum()),
        "asis_movable_pct": round(float(d["valuation_score"].ne(0).mean() * 100), 1),
        "repaired_movable_companies": int(d["price_p_repaired"].notna().sum()),
        "repaired_movable_pct": round(float(d["price_p_repaired"].notna().mean() * 100), 1),
        "asis_price_p_distinct": int(d["price_p_asis"].nunique()),
        "repaired_price_p_distinct": int(d["price_p_repaired"].nunique()),
    }
    report["spearman_asis_vs_repaired_price"] = round(
        float(d["price_p_asis"].corr(d["price_p_repaired"], method="spearman")), 4
    )

    cols = ["code", "company_name", "company_name_ja", "sector_33", "scale_category",
            "market_cap_repaired", "avg_trading_value_60d", "earnings_to_price", "book_to_market",
            "moat_p", "change_p", "future_p", "price_p_repaired", "price_p_asis"]
    top_rep = pick(d, "total_repaired", N_PICK, SECTOR_CAP)
    top_asis = pick(d, "total_asis", N_PICK, SECTOR_CAP)
    top_rep[cols + ["total_repaired"]].to_csv(OUT / "repaired_top20_sectorcap2.csv", index=False)
    top_asis[cols + ["total_asis"]].to_csv(OUT / "asis_recomputed_top20_sectorcap2.csv", index=False)

    cur = pd.read_csv(ROOT / "data/processed/portfolio.csv", dtype={"code": str})
    report["top20_comparison"] = {
        "repaired_vs_asis_overlap": int(len(set(top_rep["code"]) & set(top_asis["code"]))),
        "repaired_vs_current_v10_overlap": int(len(set(top_rep["code"]) & set(cur["code"]))),
        "asis_vs_current_v10_overlap": int(len(set(top_asis["code"]) & set(cur["code"]))),
        "repaired_median_mcap_oku": round(float(top_rep["market_cap_repaired"].median() / 1e8), 1),
        "repaired_median_adv_oku": round(float(top_rep["avg_trading_value_60d"].median() / 1e8), 2),
        "repaired_sector_counts": top_rep["sector_33"].value_counts().to_dict(),
        "repaired_scale_counts": top_rep["scale_category"].fillna("区分なし").value_counts().to_dict(),
        "repaired_axis_profile": {
            a: {"min": round(float(top_rep[a].min()), 1),
                "median": round(float(top_rep[a].median()), 1),
                "max": round(float(top_rep[a].max()), 1)}
            for a in ["moat_p", "change_p", "future_p", "price_p_repaired"]
        },
    }

    # 現行20社が新4軸でどこにいるか
    cur_scored = d[d["code"].isin(cur["code"])]
    report["current_v10_portfolio_under_new_axes"] = {
        "n_matched": int(len(cur_scored)),
        "median_total_repaired_percentile": round(
            float(pr(d["total_repaired"])[cur_scored.index].median()), 1
        ),
        "axis_medians": {
            a: round(float(cur_scored[a].median()), 1)
            for a in ["moat_p", "change_p", "future_p", "price_p_repaired"]
        },
    }

    d[["code", "company_name", "sector_33", "market_cap_repaired", "moat_p", "change_p",
       "future_p", "price_p_repaired", "price_p_asis", "total_repaired", "total_asis"]
      ].to_csv(OUT / "repaired_all_eligible_scored.csv", index=False)
    (OUT / "repaired_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print(top_rep[["code", "company_name", "sector_33", "moat_p", "change_p", "future_p",
                   "price_p_repaired", "total_repaired"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
