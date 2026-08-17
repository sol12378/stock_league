"""Part 13: 既存式だけの構成を現在の基準日で実際に回し、20社が出るところまで確認する。

12_established_only.py は過去コホートでの予測力の比較。こちらは「本番で回るか」の確認。

構成(すべて出典のある式):
  Step 0  Amihud (2002) 流動性 / Altman (1968) Z-Score / 連続赤字・データ完備
  ① Moat   Asness-Frazzini-Pedersen (2019) QMJ Profitability
  ② Change Piotroski (2000) F-Score 9項目
  ③ Future Chan-Lakonishok-Sougiannis (2001) 研究開発集約度
  ④ Price  Greenblatt (2005) EBIT/EV + Fama-French (1992) B/M + Basu (1977) E/P
  合成    Greenblatt (2005) の順位合算方式(等重み)
  分散    同一33業種2社まで / 均等5%

出力: work/new_4axis_screen/out/established_top20.csv / established_current_summary.json
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
CAPITAL, TARGET_W, MAX_W, LOT = 5_000_000, 0.05, 0.08, 100
ALTMAN_DISTRESS = 1.81      # Altman (1968) のディストレス境界
AXES = ["moat_p", "change_p", "future_p", "price_p"]


def pctrank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").mul(100.0)


def zs(s: pd.Series) -> pd.Series:
    r = s.rank(method="average")
    return (r - r.mean()) / r.std()


def blend(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return pd.DataFrame({c: pctrank(df[c]) for c in cols}).mean(axis=1, skipna=True)


def pick(df: pd.DataFrame, key: str, cap: int | None) -> pd.DataFrame:
    df = df.sort_values(key, ascending=False)
    out, cnt = [], {}
    for _, r in df.iterrows():
        if cap is not None and cnt.get(r["sector_33"], 0) >= cap:
            continue
        out.append(r)
        cnt[r["sector_33"]] = cnt.get(r["sector_33"], 0) + 1
        if len(out) == N_PICK:
            break
    return pd.DataFrame(out)


def allocate(sel: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    sel = sel.copy()
    target, cap = CAPITAL * TARGET_W, CAPITAL * MAX_W
    sel["lot_cost"] = sel["price_used"] * LOT
    sel["units"] = np.maximum(1, np.round(target / sel["lot_cost"])).astype(int)
    sel["cost"] = sel["units"] * sel["lot_cost"]
    over = sel["cost"] > cap
    sel.loc[over, "units"] = np.floor(cap / sel.loc[over, "lot_cost"]).astype(int)
    sel["cost"] = sel["units"] * sel["lot_cost"]
    cash = CAPITAL - sel["cost"].sum()
    while cash < 0:
        cand = sel[sel["units"] > 1].sort_values("cost", ascending=False)
        i = (cand if not cand.empty else sel.sort_values("cost", ascending=False)).index[0]
        sel.at[i, "units"] -= 1
        sel.at[i, "cost"] -= sel.at[i, "lot_cost"]
        cash += sel.at[i, "lot_cost"]
    for _ in range(5000):
        room = sel[(sel["lot_cost"] <= cash) & (sel["cost"] + sel["lot_cost"] <= cap)]
        if room.empty:
            break
        i = (room["cost"] - target).idxmin()
        sel.at[i, "units"] += 1
        sel.at[i, "cost"] += sel.at[i, "lot_cost"]
        cash -= sel.at[i, "lot_cost"]
    sel["shares"] = sel["units"] * LOT
    sel["weight_pct"] = sel["cost"] / CAPITAL * 100
    return sel, float(cash)


def main() -> None:
    rep: dict[str, object] = {}
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False)
    ev = pd.read_csv(OUT / "ev_fields_all_years.csv", dtype={"code": str}).drop(columns=["status"])
    live = pd.read_csv(OUT / "shares_live.csv", dtype={"code": str}).dropna(
        subset=["code"]).drop_duplicates("code")

    panel = panel.drop(columns=[c for c in ["rd_expense", "capex", "cash", "ppe",
                                            "retained_earnings", "depreciation"]
                                if c in panel.columns])
    panel = panel.merge(ev, on=["code", "fiscal_year"], how="left")
    fin = panel.sort_values(["code", "fiscal_year"]).groupby("code", as_index=False).last()
    # 銘柄属性は scores.csv 側を正とする(パネルにも同名列があり衝突するため落とす)
    fin = fin.drop(columns=[c for c in ["company_name", "company_name_ja", "sector_33",
                                        "sector_17", "sector", "market", "is_financial"]
                            if c in fin.columns])

    d = scores[["code", "company_name", "company_name_ja", "sector_33", "market",
                "scale_category", "close", "avg_trading_value_60d", "investment_eligible"]].merge(
        fin, on="code", how="left").merge(
        live[["code", "shares_live", "last_price", "market_cap_live"]], on="code", how="left")

    d["price_used"] = d["last_price"].fillna(d["close"]).where(lambda s: s > 0)
    d["shares_used"] = d["shares_live"].fillna(d["shares_outstanding_pti"])
    d["market_cap"] = d["market_cap_live"].fillna(d["shares_used"] * d["price_used"])

    ta = d["total_assets"].where(d["total_assets"] > 0)
    sales = d["revenue"].where(d["revenue"] > 0)
    eqv = d["equity"].where(d["equity"] > 0)
    mc = d["market_cap"].where(d["market_cap"] > 0)
    ebit = d["operating_income"]

    # ---- ① QMJ Profitability ----
    d["GPOA"] = d["gross_profit"] / ta
    d["ROE"] = d["net_income"] / eqv
    d["ROA"] = d["net_income"] / ta
    d["CFOA"] = d["operating_cf"] / ta
    d["GMAR"] = d["gross_profit"] / sales
    d["ACC"] = -(d["net_income"] - d["operating_cf"]) / ta
    d["moat_raw"] = pd.concat([zs(d[c]) for c in ["GPOA", "ROE", "ROA", "CFOA", "GMAR", "ACC"]],
                              axis=1).mean(axis=1, skipna=True)
    # ---- ② Piotroski F-Score ----
    d["change_raw"] = d[[c for c in d.columns if c.startswith("f_score_")]].sum(axis=1, min_count=1)
    # ---- ③ CLS 研究開発集約度 ----
    d["rd_to_market"] = (d["rd_expense"] / mc).fillna(0.0)
    d["rd_to_sales"] = (d["rd_expense"] / sales).fillna(0.0)
    d["future_raw"] = blend(d, ["rd_to_market", "rd_to_sales"])
    # ---- ④ Price ----
    evv = mc + d["interest_bearing_debt"].fillna(0) - d["cash"].fillna(0)
    d["greenblatt_ey"] = ebit / evv.where(evv > 0)
    d["ff_btm"] = d["equity"] / mc
    d["basu_ep"] = d["net_income"] / mc
    d["price_raw"] = blend(d, ["greenblatt_ey", "ff_btm", "basu_ep"])
    # ---- Altman Z ----
    d["altman_z"] = (1.2 * ((d["current_assets"] - d["current_liabilities"]) / ta)
                     + 1.4 * (d["retained_earnings"] / ta)
                     + 3.3 * (ebit / ta)
                     + 0.6 * (mc / d["liabilities"].where(d["liabilities"] > 0))
                     + 1.0 * (sales / ta))
    d["per"] = mc / d["net_income"].where(d["net_income"] > 0)
    d["pbr"] = mc / eqv

    # ---- Step 0 ----
    base = d["investment_eligible"].fillna(False).astype(bool)
    val_ok = ~((d["per"].notna() & ((d["per"] <= 0) | (d["per"] > 120)))
               | (d["pbr"].notna() & ((d["pbr"] <= 0) | (d["pbr"] > 20))))
    z_ok = d["altman_z"].isna() | (d["altman_z"] >= ALTMAN_DISTRESS)
    has_mc = mc.notna()
    d["eligible"] = base & val_ok & z_ok & has_mc
    rep["step0"] = {
        "eligible_conditions_1_8": int(base.sum()),
        "excluded_valuation_range": int((base & ~val_ok).sum()),
        "excluded_altman_distress": int((base & val_ok & ~z_ok).sum()),
        "eligible_final": int(d["eligible"].sum()),
        "altman_threshold": ALTMAN_DISTRESS,
    }
    u = d[d["eligible"]].copy()

    for a, raw in zip(AXES, ["moat_raw", "change_raw", "future_raw", "price_raw"]):
        u[a] = pctrank(u[raw])
    u["total"] = u[AXES].mean(axis=1)

    rep["coverage_pct"] = {c: round(float(u[c].notna().mean() * 100), 1) for c in
                           ["GPOA", "ROE", "ROA", "CFOA", "GMAR", "ACC", "change_raw",
                            "rd_expense", "greenblatt_ey", "ff_btm", "basu_ep", "altman_z"]}
    rep["rd_disclosed_pct"] = round(float((u["rd_expense"] > 0).mean() * 100), 1)
    rep["axis_spearman"] = u[AXES].corr(method="spearman").round(3).to_dict()
    var = u["total"].var()
    rep["effective_weight"] = {a: round(float(0.25 * u[a].cov(u["total"]) / var), 4) for a in AXES}
    rep["all_four_above"] = {str(t): int((u[AXES] >= t).all(axis=1).sum())
                             for t in [50, 60, 70, 80, 90]}

    u["lot_cost"] = u["price_used"] * LOT
    pool = u[u["lot_cost"] <= CAPITAL * MAX_W].copy()
    rep["not_buyable_within_cap"] = int((~(u["lot_cost"] <= CAPITAL * MAX_W)).sum())
    top = pick(pool, "total", SECTOR_CAP).reset_index(drop=True)
    top, cash = allocate(top)

    bespoke = pd.read_csv(OUT / "final_top20.csv", dtype={"code": str})
    cur = pd.read_csv(ROOT / "data/processed/portfolio.csv", dtype={"code": str})
    rep["result"] = {
        "n": int(len(top)),
        "sectors": int(top["sector_33"].nunique()),
        "per_median": round(float(top["per"].median()), 1),
        "pbr_median": round(float(top["pbr"].median()), 2),
        "market_cap_median_oku": round(float(top["market_cap"].median() / 1e8), 1),
        "invested": int(top["cost"].sum()),
        "cash_left_pct": round(float(cash / CAPITAL * 100), 2),
        "overlap_with_bespoke20": int(len(set(top["code"]) & set(bespoke["code"]))),
        "overlap_with_current_v10": int(len(set(top["code"]) & set(cur["code"]))),
        "sector_counts": top["sector_33"].value_counts().to_dict(),
    }

    keep = ["code", "company_name_ja", "company_name", "sector_33", "market", "price_used",
            "market_cap", "per", "pbr", "altman_z", "rd_expense",
            "moat_p", "change_p", "future_p", "price_p", "total",
            "shares", "cost", "weight_pct"]
    top[keep].to_csv(OUT / "established_top20.csv", index=False)
    u[["code", "company_name_ja", "sector_33", "per", "pbr", "altman_z"] + AXES + ["total"]
      ].sort_values("total", ascending=False).to_csv(OUT / "established_all_eligible.csv", index=False)
    (OUT / "established_current_summary.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print()
    print(top[["code", "company_name_ja", "sector_33", "per", "pbr", "altman_z",
               "moat_p", "change_p", "future_p", "price_p", "total", "weight_pct"]
              ].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
