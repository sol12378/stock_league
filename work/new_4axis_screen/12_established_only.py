"""Part 12: 「自作の式をやめて、既存の名前のついた式だけでスクリーニングできるか」の検証。

各軸を、査読論文または著名な実務書で定義が確定している式に置き換えて実装し、
(a) そもそも計算できるか (b) 自作版と比べて予測力が落ちないか を測る。

割り当て:
  ① Moat   = Asness, Frazzini & Pedersen (2019) QMJ の Profitability
             = z平均( GPOA, ROE, ROA, CFOA, GMAR, −ACC )
               GPOA は Novy-Marx (2013)、ACC は Sloan (1996)
  ② Change = Piotroski (2000) F-Score 9項目
  ③ Future = Chan, Lakonishok & Sougiannis (2001) 研究開発集約度 (R&D/時価総額, R&D/売上)
  ④ Price  = Greenblatt (2005) 益回り EBIT/EV
             + Fama & French (1992) B/M + Basu (1977) E/P
  合成     = Greenblatt (2005) の順位合算方式
  Step 0   = Altman (1968) Z-Score + Amihud (2002) 流動性

比較対象:
  自作版 = 07_final_screen.py と同じ構成(順位点の単純平均)
  Greenblatt マジックフォーミュラ単体 (ROC + 益回り) も参考に測る

出力: work/new_4axis_screen/out/established_*.csv / established_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"
LIQUIDITY_YEN = 20_000_000

COHORTS = {"FY2024_252d": ("future_return_252d", 2024),
           "FY2025_126d": ("future_return_126d", 2025),
           "FY2023_252d": ("future_return_252d", 2023)}


def pctrank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").mul(100.0)


def zs(s: pd.Series) -> pd.Series:
    """QMJ は順位のz化を使う。外れ値に強く、論文の手順どおり。"""
    r = s.rank(method="average")
    return (r - r.mean()) / r.std()


def blend_rank(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return pd.DataFrame({c: pctrank(df[c]) for c in cols}).mean(axis=1, skipna=True)


def build(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    ta = d["total_assets"].where(d["total_assets"] > 0)
    sales = d["revenue"].where(d["revenue"] > 0)
    eq = d["equity"].where(d["equity"] > 0)
    mc = d["market_equity_pti"].where(d["market_equity_pti"] > 0)

    # ---- ① Moat: QMJ Profitability (Asness-Frazzini-Pedersen 2019) ----
    d["GPOA"] = d["gross_profit"] / ta            # Novy-Marx (2013)
    d["ROE"] = d["net_income"] / eq
    d["ROA"] = d["net_income"] / ta
    d["CFOA"] = d["operating_cf"] / ta
    d["GMAR"] = d["gross_profit"] / sales
    d["ACC"] = -(d["net_income"] - d["operating_cf"]) / ta   # Sloan (1996)、符号は低いほど良い
    d["qmj_profitability"] = pd.concat(
        [zs(d[c]) for c in ["GPOA", "ROE", "ROA", "CFOA", "GMAR", "ACC"]], axis=1
    ).mean(axis=1, skipna=True)

    # ---- ② Change: Piotroski (2000) F-Score 9項目 ----
    fcols = [c for c in d.columns if c.startswith("f_score_")]
    d["piotroski"] = d[fcols].sum(axis=1, min_count=1)

    # ---- ③ Future: Chan-Lakonishok-Sougiannis (2001) 研究開発集約度 ----
    rd = d["rd_expense"]
    d["rd_to_market"] = rd / mc
    d["rd_to_sales"] = rd / sales
    d["has_rd"] = rd.notna() & (rd > 0)
    # R&Dを開示していない企業は「研究開発をしていない」= 0 とする(ゼロ埋めではなく実態)
    d["cls_future"] = blend_rank(
        d.assign(rd_to_market=d["rd_to_market"].fillna(0.0),
                 rd_to_sales=d["rd_to_sales"].fillna(0.0)),
        ["rd_to_market", "rd_to_sales"])

    # ---- ④ Price ----
    ev = mc + d["interest_bearing_debt"].fillna(0) - d["cash"].fillna(0)
    d["enterprise_value"] = ev.where(ev > 0)
    ebit = d["operating_income"]
    d["greenblatt_ey"] = ebit / d["enterprise_value"]          # Greenblatt (2005) 益回り
    d["ff_btm"] = d["book_to_market"]                          # Fama-French (1992)
    d["basu_ep"] = d["earnings_to_price"]                      # Basu (1977)
    d["price_established"] = blend_rank(d, ["greenblatt_ey", "ff_btm", "basu_ep"])

    # ---- 参考: Greenblatt マジックフォーミュラ単体 ----
    nwc = d["current_assets"] - d["current_liabilities"]
    nfa = d["ppe"]
    cap_base = (nwc + nfa).where(lambda s: s > 0)
    d["greenblatt_roc"] = ebit / cap_base
    d["magic_formula"] = (d["greenblatt_roc"].rank(ascending=False)
                          + d["greenblatt_ey"].rank(ascending=False))   # 小さいほど良い

    # ---- 参考: Altman (1968) Z-Score ----
    d["altman_z"] = (1.2 * ((d["current_assets"] - d["current_liabilities"]) / ta)
                     + 1.4 * (d["retained_earnings"] / ta)
                     + 3.3 * (ebit / ta)
                     + 0.6 * (mc / d["liabilities"].where(d["liabilities"] > 0))
                     + 1.0 * (sales / ta))

    # ---- 自作版(07と同じ構成) ----
    d["op_margin"] = d["operating_income"] / sales
    d["ocf_margin"] = d["operating_cf"] / sales
    d["equity_ratio"] = 1.0 - d["leverage"]
    d["bespoke_moat"] = blend_rank(d, ["gross_profitability", "op_margin", "roa",
                                       "ocf_margin", "equity_ratio"])
    d["bespoke_change"] = blend_rank(d, ["piotroski_f_score", "delta_roa", "delta_gross_margin",
                                         "delta_asset_turnover", "revenue_growth", "oi_growth"])
    d["bespoke_future"] = pctrank(d["future_moat_score"])
    d["bespoke_price"] = blend_rank(d, ["earnings_to_price", "book_to_market"])
    return d


def main() -> None:
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False)
    # 年度別に取り直したもの。最新提出分だけを過去コホートに当てると前方視になるため、
    # 検証では必ず (code, fiscal_year) で結合する。
    ev = pd.read_csv(OUT / "ev_fields_all_years.csv", dtype={"code": str}).drop(
        columns=["status"]).drop_duplicates(["code", "fiscal_year"])
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str},
                         low_memory=False, usecols=["code", "future_moat_score"]
                         ).drop_duplicates("code")

    panel = panel.sort_values(["code", "fiscal_year"])
    for src, dst in [("revenue", "revenue_growth"), ("operating_income", "oi_growth")]:
        prev = panel.groupby("code")[src].shift(1)
        panel[dst] = (panel[src] - prev) / prev.abs().replace(0, np.nan)
    # パネル側の rd_expense / capex は抽出漏れで実質空なので、正しいタグで取り直した
    # ev_fields.csv の値に差し替える(列名衝突を避けるため先に落とす)
    panel = panel.drop(columns=[c for c in ["rd_expense", "capex", "cash", "ppe",
                                            "retained_earnings", "depreciation"]
                                if c in panel.columns])
    panel = panel.merge(ev, on=["code", "fiscal_year"], how="left").merge(
        scores, on="code", how="left")

    report: dict[str, object] = {
        "note": "追加抽出項目(R&D・現預金・有利子負債・利益剰余金・有形固定資産)は "
                "(code, fiscal_year) で結合しており、前方視は入っていない。",
    }
    per: dict[str, object] = {}

    for key, (retcol, year) in COHORTS.items():
        d = panel[panel["fiscal_year"] == year].copy()
        d = d[
            d["price_join_success"].fillna(False)
            & ~d["financial_exclusion_flag"].fillna(False)
            & ~d["negative_equity_flag"].fillna(False)
            & (d["decision_adv60"].fillna(0) >= LIQUIDITY_YEN)
            & d[retcol].notna()
        ].copy()
        d = build(d)
        ret = d[retcol]

        established = ["qmj_profitability", "piotroski", "cls_future", "price_established"]
        bespoke = ["bespoke_moat", "bespoke_change", "bespoke_future", "bespoke_price"]
        d["total_established"] = pd.DataFrame(
            {c: pctrank(d[c]) for c in established}).mean(axis=1)
        d["total_bespoke"] = pd.DataFrame(
            {c: pctrank(d[c]) for c in bespoke}).mean(axis=1)
        d["total_magic"] = -pctrank(d["magic_formula"])   # 順位合算は小さいほど良い

        yr: dict[str, object] = {
            "n": int(len(d)),
            "coverage_pct": {c: round(float(d[c].notna().mean() * 100), 1) for c in
                             ["GPOA", "ROE", "ROA", "CFOA", "GMAR", "ACC", "piotroski",
                              "rd_to_market", "greenblatt_ey", "greenblatt_roc",
                              "ff_btm", "basu_ep", "altman_z"]},
            "rd_disclosed_pct": round(float(d["has_rd"].mean() * 100), 1),
            "altman_distress_pct": round(float((d["altman_z"] < 1.81).mean() * 100), 1),
            "rank_ic": {},
            "decile_spread": {},
        }
        for c in established + bespoke + ["total_established", "total_bespoke",
                                          "total_magic", "altman_z", "greenblatt_roc"]:
            yr["rank_ic"][c] = round(float(d[c].corr(ret, method="spearman")), 4)
            q = pd.qcut(d[c].rank(method="first"), 10, labels=False)
            yr["decile_spread"][c] = round(
                float(ret[q == 9].mean() - ret[q == 0].mean()), 4)

        # 既存式版と自作版の順位はどれだけ一致するか
        yr["agreement"] = {
            "spearman_total": round(float(
                d["total_established"].corr(d["total_bespoke"], method="spearman")), 3),
            "moat": round(float(d["qmj_profitability"].corr(d["bespoke_moat"], method="spearman")), 3),
            "change": round(float(d["piotroski"].corr(d["bespoke_change"], method="spearman")), 3),
            "future": round(float(d["cls_future"].corr(d["bespoke_future"], method="spearman")), 3),
            "price": round(float(d["price_established"].corr(d["bespoke_price"], method="spearman")), 3),
        }
        # 既存式どうしの相関(二重計上のチェック)
        yr["axis_corr_established"] = d[established].corr(method="spearman").round(3).to_dict()
        # Future軸は業種ラベルか
        dm = pd.get_dummies(d["sector_33"]).astype(float).to_numpy()
        X = np.column_stack([np.ones(len(d)), dm])
        yr["r2_vs_sector33"] = {}
        for c in ["qmj_profitability", "piotroski", "cls_future", "price_established",
                  "bespoke_future"]:
            y = d[c].fillna(d[c].median()).to_numpy()
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            yr["r2_vs_sector33"][c] = round(
                float(1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()), 4)

        per[key] = yr
        d[["code", "company_name", "sector_33"] + established + bespoke
          + ["total_established", "total_bespoke", "altman_z", "magic_formula", retcol]
          ].to_csv(OUT / f"established_scored_{key}.csv", index=False)
        print(f"[{key}] n={len(d)} 完了")

    report["cohorts"] = per
    (OUT / "established_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for k, v in per.items():
        rows.append({"cohort": k, **{f"IC_{c}": v["rank_ic"][c] for c in
                                     ["qmj_profitability", "piotroski", "cls_future",
                                      "price_established", "total_established",
                                      "total_bespoke", "total_magic"]}})
    print()
    print(pd.DataFrame(rows).to_string(index=False))
    print()
    for k, v in per.items():
        print(k, "一致度:", v["agreement"], "| R&D開示率:", v["rd_disclosed_pct"], "%")


if __name__ == "__main__":
    main()
