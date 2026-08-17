"""Part 5: Price軸の直しに残る誤差(株式分割・複数株式種類)を計測して手当てする。

問題: 株価系列(Yahoo)は分割を遡って調整済みだが、XBRLの発行済株式数は「その提出時点」の値。
      提出後に分割した会社は 時価総額=株数×株価 が分割比率のぶん過小 → 益回り・純資産倍率が過大
      → Price軸の最上位に張り付く。yfinance実測のある163社で誤差率を測り、ガードを入れる。

出力: work/new_4axis_screen/out/splitguard_*.csv / splitguard_summary.json
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
PER_FLOOR, PBR_FLOOR = 3.0, 0.30


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
                        usecols=["code", "fiscal_year", "shares_issued", "shares_outstanding_pti",
                                 "decision_close", "market_equity_pti", "net_income", "equity"])
    report: dict[str, object] = {}

    # ---- 1. 連続する提出書類の株数比から分割を検出(過去分は捕まる) ----
    ps = panel.dropna(subset=["shares_issued"]).sort_values(["code", "fiscal_year"])
    ps["ratio_vs_prev"] = ps.groupby("code")["shares_issued"].transform(lambda s: s / s.shift(1))
    detected = ps[ps["ratio_vs_prev"] >= 1.8]
    report["split_detected_between_filings"] = {
        "n_events": int(len(detected)),
        "n_codes": int(detected["code"].nunique()),
        "ratio_histogram": detected["ratio_vs_prev"].round(0).value_counts().head(8).astype(int).to_dict(),
    }

    # ---- 2. yfinance実測がある163社を正解として、XBRL株数の誤差率を測る ----
    last = ps.groupby("code", as_index=False).last().rename(
        columns={"shares_outstanding_pti": "sh_xbrl", "fiscal_year": "sh_fy"})
    d = scores[scores["investment_eligible"].fillna(False).astype(bool)].merge(
        last[["code", "sh_xbrl", "sh_fy"]], on="code", how="left")
    truth = d[d["shares_outstanding"].notna() & d["sh_xbrl"].notna()].copy()
    truth["ratio"] = truth["sh_xbrl"] / truth["shares_outstanding"]
    report["xbrl_shares_error_vs_yfinance"] = {
        "n_checked": int(len(truth)),
        "within_5pct_pct": round(float(truth["ratio"].between(0.95, 1.05).mean() * 100), 1),
        "within_20pct_pct": round(float(truth["ratio"].between(0.80, 1.20).mean() * 100), 1),
        "materially_wrong_pct": round(float((~truth["ratio"].between(0.80, 1.20)).mean() * 100), 1),
        "understated_mcap_cases": int((truth["ratio"] < 0.8).sum()),
        "overstated_mcap_cases": int((truth["ratio"] > 1.2).sum()),
        "note": "ratio<0.8 は提出後の株式分割、ratio>1.2 は優先株など複数株式種類の合算が主因",
    }

    # ---- 3. 株数の優先順位: yfinance実測 > XBRL ----
    d["shares_used"] = d["shares_outstanding"].fillna(d["sh_xbrl"])
    d["shares_source"] = np.where(d["shares_outstanding"].notna(), "yfinance", "xbrl")
    d["mc"] = d["shares_used"] * d["close"]
    mc = d["mc"].where(d["mc"] > 0)
    d["per"] = mc / d["net_income"].where(d["net_income"] > 0)
    d["pbr"] = mc / d["equity"].where(d["equity"] > 0)
    d["earnings_to_price"] = d["net_income"] / mc
    d["book_to_market"] = d["equity"] / mc

    # ---- 4. 実装不能なほど安い = 株数が疑わしい、というフラグ ----
    d["valuation_implausible"] = (
        (d["per"] < PER_FLOOR) | (d["pbr"] < PBR_FLOOR)
    ).fillna(False)
    report["implausible_valuation_flag"] = {
        "per_floor": PER_FLOOR, "pbr_floor": PBR_FLOOR,
        "n_flagged": int(d["valuation_implausible"].sum()),
        "flagged_pct": round(float(d["valuation_implausible"].mean() * 100), 1),
        "flagged_by_source": d.groupby("shares_source")["valuation_implausible"].sum().astype(int).to_dict(),
        "flag_rate_by_source_pct": (d.groupby("shares_source")["valuation_implausible"].mean() * 100).round(1).to_dict(),
    }
    report["valuation_distribution"] = {
        "per_median": round(float(d["per"].median()), 2),
        "pbr_median": round(float(d["pbr"].median()), 2),
        "pbr_below_1_pct": round(float((d["pbr"] < 1).mean() * 100), 1),
    }

    # ---- 5. 4軸とトップ20(フラグ込み / フラグ除外) ----
    d["moat_p"] = blend(d, ["operating_margin", "roe", "equity_ratio", "ocf_margin"])
    d["change_p"] = blend(d, ["revenue_growth", "operating_income_growth"])
    d["future_p"] = blend(d, ["future_moat_score"])

    outs = {}
    for tag, sub in [("with_flagged", d), ("excl_flagged", d[~d["valuation_implausible"]].copy())]:
        sub = sub.copy()
        sub["price_p"] = blend(sub, ["earnings_to_price", "book_to_market"])
        sub["total"] = sub[["moat_p", "change_p", "future_p", "price_p"]].mean(axis=1)
        top = pick(sub, "total", N_PICK, SECTOR_CAP)
        outs[tag] = top
        top[["code", "company_name", "company_name_ja", "sector_33", "scale_category",
             "shares_source", "mc", "per", "pbr", "avg_trading_value_60d",
             "moat_p", "change_p", "future_p", "price_p", "total"]].to_csv(
            OUT / f"splitguard_top20_{tag}.csv", index=False)

    a, b = set(outs["with_flagged"]["code"]), set(outs["excl_flagged"]["code"])
    cur = pd.read_csv(ROOT / "data/processed/portfolio.csv", dtype={"code": str})
    report["top20"] = {
        "overlap_with_vs_excl_flagged": len(a & b),
        "n_flagged_inside_top20_with": int(outs["with_flagged"]["valuation_implausible"].sum()),
        "excl_flagged_vs_current_v10_overlap": len(b & set(cur["code"])),
        "excl_flagged_median_mcap_oku": round(float(outs["excl_flagged"]["mc"].median() / 1e8), 1),
        "excl_flagged_median_per": round(float(outs["excl_flagged"]["per"].median()), 1),
        "excl_flagged_median_pbr": round(float(outs["excl_flagged"]["pbr"].median()), 2),
        "excl_flagged_sector_counts": outs["excl_flagged"]["sector_33"].value_counts().to_dict(),
    }

    # ---- 6. PIT検証側は分割誤差にどれだけさらされているか ----
    pit = panel.dropna(subset=["market_equity_pti"]).copy()
    pit["per_pit"] = pit["market_equity_pti"] / pit["net_income"].where(pit["net_income"] > 0)
    pit["pbr_pit"] = pit["market_equity_pti"] / pit["equity"].where(pit["equity"] > 0)
    report["pit_panel_exposure"] = {
        str(y): {
            "n": int(len(g)),
            "implausible_pct": round(
                float(((g["per_pit"] < PER_FLOOR) | (g["pbr_pit"] < PBR_FLOOR)).mean() * 100), 1),
            "per_median": round(float(g["per_pit"].median()), 2),
            "pbr_median": round(float(g["pbr_pit"].median()), 2),
        }
        for y, g in pit[pit["fiscal_year"].isin([2023, 2024, 2025])].groupby("fiscal_year")
    }
    report["pit_panel_exposure"]["note"] = (
        "PIT側は提出日から意思決定日までが1〜3か月と短いため、分割ズレの露出は現在時点スクリーンより小さい"
    )

    d.to_csv(OUT / "splitguard_all_eligible.csv", index=False)
    (OUT / "splitguard_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("=== フラグ除外後の上位20社 ===")
    print(outs["excl_flagged"][["code", "company_name", "sector_33", "per", "pbr",
                                "moat_p", "change_p", "future_p", "price_p", "total"]]
          .round(1).to_string(index=False))


if __name__ == "__main__":
    main()
