"""Part 7: NEW4AXIS_SPEC_v1 の完全実装。確定版の20社とポートフォリオを出す。

仕様: outputs/stockleague_edition/NEW4AXIS_SPEC_v1.md

v1 からの変更点(実装して分かったこと):
  - Price軸の時価総額を「実勢の発行済株式数 × 基準日終値」で作る(09_fetch_shares.py)。
    XBRLの株式数・1株当たり数値は提出時点の基準なので、提出後に分割した会社で
    分割比率のぶん過小になり、Price軸の最上位に張り付いていた。実測:
      6648 かわでん   XBRL 4,192,000 → 実勢 16,015,485 (3.82倍) PBR 0.3 → 3.58
      3798 ULSグループ XBRL 6,228,800 → 実勢 56,578,380 (9.08倍) PBR 0.3 → 2.39
      5729 日本精鉱   XBRL 2,605,900 → 実勢  9,802,968 (3.76倍) PBR 0.3 → 1.14
  - 益回り・純資産倍率は集計値(純利益・自己資本)÷時価総額で作る。1株当たり方式より
    分割に強い。XBRLのEPS/BPS(08_extract_per_share.py)は突合用に残す。
  - 1単元が上限8%を超えて買えない銘柄は選抜から外し、次点を繰り上げる
  - 余剰現金は「目標比率から最も遠い銘柄」へ1単元ずつ配る

財務はPITパネルの各社最新提出分に統一する。株価・業種・流動性・Future点は scores.csv。

出力: work/new_4axis_screen/out/final_*.csv / final_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"

N_PICK, SECTOR_CAP = 20, 2
CAPITAL, TARGET_W, MAX_W, LOT = 5_000_000, 0.05, 0.08, 100
PER_LO, PER_HI, PBR_LO, PBR_HI = 0.0, 120.0, 0.0, 20.0   # Step 0 条件9
EPS_CONSISTENCY_TOL = 0.20                                # 報告EPS と 純利益/株数 の許容乖離

MOAT = ["gp_to_assets", "op_margin", "roa", "ocf_margin", "equity_ratio"]
CHANGE = ["piotroski_f_score", "delta_roa", "delta_gross_margin",
          "delta_asset_turnover", "revenue_growth", "oi_growth"]
PRICE = ["earnings_to_price", "book_to_market"]
AXES = ["moat_p", "change_p", "future_p", "price_p"]


def pctrank(s: pd.Series) -> pd.Series:
    """0-100の順位点。同値は平均順位。欠測はNaNのまま(ゼロ埋め禁止)。"""
    return s.rank(pct=True, method="average").mul(100.0)


def blend(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """成分を順位点にして単純平均。欠測成分は平均から外す。"""
    return pd.DataFrame({c: pctrank(df[c]) for c in cols}).mean(axis=1, skipna=True)


def allocate(sel: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """均等5%を単元株に落とし、余りは目標から最も遠い銘柄へ1単元ずつ配る。"""
    sel = sel.copy()
    target = CAPITAL * TARGET_W
    cap = CAPITAL * MAX_W
    sel["lot_cost"] = sel["price_used"] * LOT
    sel["units"] = np.maximum(1, np.round(target / sel["lot_cost"])).astype(int)
    sel["cost"] = sel["units"] * sel["lot_cost"]
    # 上限8%を超えたら削る
    over = sel["cost"] > cap
    sel.loc[over, "units"] = np.floor(cap / sel.loc[over, "lot_cost"]).astype(int)
    sel["cost"] = sel["units"] * sel["lot_cost"]

    cash = CAPITAL - sel["cost"].sum()
    # 買いすぎていたら、目標から最も上振れている銘柄から1単元ずつ削る
    while cash < 0:
        cand = sel[sel["units"] > 1].sort_values("cost", ascending=False)
        if cand.empty:
            cand = sel.sort_values("cost", ascending=False)
        i = cand.index[0]
        sel.at[i, "units"] -= 1
        sel.at[i, "cost"] -= sel.at[i, "lot_cost"]
        cash += sel.at[i, "lot_cost"]
    # 余りを目標から最も下振れている銘柄へ
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
    pshare = pd.read_csv(OUT / "per_share_values.csv", dtype={"code": str})
    live = pd.read_csv(OUT / "shares_live.csv", dtype={"code": str}).dropna(subset=["code"])
    live = live.drop_duplicates("code")

    panel = panel.sort_values(["code", "fiscal_year"])
    for src, dst in [("revenue", "revenue_growth"), ("operating_income", "oi_growth")]:
        prev = panel.groupby("code")[src].shift(1)
        panel[dst] = (panel[src] - prev) / prev.abs().replace(0, np.nan)
    fin = panel.groupby("code", as_index=False).last()

    d = scores[["code", "company_name", "company_name_ja", "sector_33", "market",
                "scale_category", "close", "avg_trading_value_60d",
                "future_moat_score", "investment_eligible"]].merge(
        fin[["code", "fiscal_year", "shares_outstanding_pti", "revenue", "operating_income",
             "net_income", "total_assets", "equity", "operating_cf", "leverage", "roa",
             "gross_profitability", "piotroski_f_score",
             "piotroski_f_score_available_components", "delta_roa", "delta_gross_margin",
             "delta_asset_turnover", "revenue_growth", "oi_growth"]],
        on="code", how="left",
    ).merge(pshare[["code", "eps", "bps"]], on="code", how="left"
    ).merge(live[["code", "shares_live", "last_price", "market_cap_live"]], on="code", how="left")

    # ---------- Price軸の素材: 実勢株式数 × 現在株価 ----------
    # 株価と株数の基準日を揃えるのが要点。6月終値と現在の株数を掛けると、
    # 6〜8月に分割した23社で時価総額が分割比率のぶんズレる。
    d["price_used"] = d["last_price"].fillna(d["close"]).where(lambda s: s > 0)
    d["price_source"] = np.where(d["last_price"].notna(), "live", "close_20260601")
    d["shares_used"] = d["shares_live"].fillna(d["shares_outstanding_pti"])
    d["shares_source"] = np.where(d["shares_live"].notna(), "live", "xbrl")
    d["market_cap"] = d["market_cap_live"].fillna(d["shares_used"] * d["price_used"])
    mc = d["market_cap"].where(d["market_cap"] > 0)
    d["per"] = mc / d["net_income"].where(d["net_income"] > 0)
    d["pbr"] = mc / d["equity"].where(d["equity"] > 0)
    d["earnings_to_price"] = d["net_income"] / mc
    d["book_to_market"] = d["equity"] / mc

    # XBRL株式数からの乖離 = 提出後の分割・増減資
    factor = (d["shares_live"] / d["shares_outstanding_pti"]).replace([np.inf, -np.inf], np.nan)
    d["share_factor"] = factor
    d["post_filing_split"] = factor.notna() & (factor >= 1.5)
    rep["share_source"] = {
        "live_fetched": int(d["shares_live"].notna().sum()),
        "eligible_with_live": int((base_pre := d["investment_eligible"].fillna(False).astype(bool)
                                   ).sum() and (d["shares_live"].notna() & base_pre).sum()),
        "fallback_to_xbrl": int((d["shares_live"].isna() & base_pre).sum()),
        "post_filing_split_detected": int((d["post_filing_split"] & base_pre).sum()),
        "median_factor": round(float(factor[base_pre].median()), 4),
        "note": "XBRLの株式数は提出時点の基準。実勢値との比が1.5倍以上なら提出後の分割",
    }
    split_jun_aug = (d["close"] / d["last_price"]).ge(1.8)
    rep["price_source"] = {
        "basis": "実勢株価(取得日)。6月終値との比が1.8倍以上=その間に分割した銘柄",
        "live_price": int(d["last_price"].notna().sum()),
        "fallback_close": int(d["last_price"].isna().sum()),
        "split_between_jun_and_now": int(split_jun_aug.fillna(False).sum()),
    }
    # 参考: XBRL報告EPSとの突合(Price軸には使わない)
    eps_calc = d["net_income"] / d["shares_used"].where(d["shares_used"] > 0)
    eps_adj = d["eps"] / factor.where(factor > 0, 1.0)
    ratio = (eps_calc / eps_adj.where(eps_adj != 0)).abs()
    d["eps_inconsistent"] = ratio.notna() & ~ratio.between(1 - EPS_CONSISTENCY_TOL,
                                                           1 + EPS_CONSISTENCY_TOL)
    rep["eps_cross_check"] = {
        "checked": int(ratio.notna().sum()),
        "disagree_over_20pct": int(d["eps_inconsistent"].sum()),
        "disagree_pct": round(float(d["eps_inconsistent"].mean() * 100), 1),
        "note": "純利益÷株数 と 分割調整したXBRL報告EPS の突合。Price軸の採否には使わない",
    }

    # ---------- Step 0 ----------
    base = d["investment_eligible"].fillna(False).astype(bool)
    cond9_fail = ((d["per"].notna() & ((d["per"] <= PER_LO) | (d["per"] > PER_HI)))
                  | (d["pbr"].notna() & ((d["pbr"] <= PBR_LO) | (d["pbr"] > PBR_HI))))
    has_mc = d["market_cap"].notna() & (d["market_cap"] > 0)
    d["eligible"] = base & ~cond9_fail & has_mc
    rep["step0"] = {
        "universe": int(len(d)),
        "eligible_conditions_1_8": int(base.sum()),
        "excluded_by_condition9_valuation": int((base & cond9_fail).sum()),
        "excluded_no_market_cap": int((base & ~cond9_fail & ~has_mc).sum()),
        "eligible_final": int(d["eligible"].sum()),
    }
    u = d[d["eligible"]].copy()

    # ---------- Step 1 ----------
    u["gp_to_assets"] = u["gross_profitability"]
    u["op_margin"] = u["operating_income"] / u["revenue"].replace(0, np.nan)
    u["ocf_margin"] = u["operating_cf"] / u["revenue"].replace(0, np.nan)
    u["equity_ratio"] = 1.0 - u["leverage"]
    u["moat_p"] = blend(u, MOAT)
    u["change_p"] = blend(u, CHANGE)
    u["future_p"] = pctrank(u["future_moat_score"])
    u["price_p"] = blend(u, PRICE)

    rep["component_coverage_pct"] = {c: round(float(u[c].notna().mean() * 100), 1)
                                     for c in MOAT + CHANGE + PRICE}
    rep["piotroski_available_components_mean"] = round(
        float(u["piotroski_f_score_available_components"].mean()), 2)
    rep["axis_distinct_values"] = {a: int(u[a].nunique()) for a in AXES}
    rep["axis_spearman"] = u[AXES].corr(method="spearman").round(3).to_dict()
    rep["valuation_distribution"] = {
        "per_median": round(float(u["per"].median()), 2),
        "pbr_median": round(float(u["pbr"].median()), 2),
        "pbr_below_1_pct": round(float((u["pbr"] < 1).mean() * 100), 1),
    }

    # ---------- Step 2 ----------
    u["total"] = u[AXES].mean(axis=1)
    var = u["total"].var()
    rep["effective_weight_variance_share"] = {
        a: round(float(0.25 * u[a].cov(u["total"]) / var), 4) for a in AXES}
    rep["all_four_axes_above"] = {str(t): int((u[AXES] >= t).all(axis=1).sum())
                                  for t in [50, 60, 70, 80, 90]}

    # ---------- Step 3 ----------
    u["lot_cost"] = u["price_used"] * LOT
    buyable = u["lot_cost"] <= CAPITAL * MAX_W
    rep["step3_buyability"] = {
        "not_buyable_within_cap": int((~buyable).sum()),
        "note": f"1単元が{int(CAPITAL*MAX_W):,}円(上限{MAX_W:.0%})を超える銘柄は選抜対象から外し次点を繰り上げる",
    }

    def pick(df: pd.DataFrame, cap: int | None) -> pd.DataFrame:
        df = df.sort_values("total", ascending=False)
        out, cnt = [], {}
        for _, r in df.iterrows():
            if cap is not None and cnt.get(r["sector_33"], 0) >= cap:
                continue
            out.append(r)
            cnt[r["sector_33"]] = cnt.get(r["sector_33"], 0) + 1
            if len(out) == N_PICK:
                break
        return pd.DataFrame(out)

    pool = u[buyable].copy()
    top = pick(pool, SECTOR_CAP).reset_index(drop=True)
    nodiv = pick(pool, None)
    rep["step3"] = {
        "pool": int(len(pool)),
        "sectors_with_cap": int(top["sector_33"].nunique()),
        "sectors_without_cap": int(nodiv["sector_33"].nunique()),
        "mean_total_with_cap": round(float(top["total"].mean()), 2),
        "mean_total_without_cap": round(float(nodiv["total"].mean()), 2),
        "nodiv_top_sector_share": nodiv["sector_33"].value_counts().head(2).to_dict(),
        "sector_counts": top["sector_33"].value_counts().to_dict(),
        "market_counts": top["market"].value_counts().to_dict(),
        "scale_counts": top["scale_category"].fillna("区分なし").value_counts().to_dict(),
    }

    # ---------- Step 4 ----------
    top, cash = allocate(top)
    rep["step4"] = {
        "capital": CAPITAL, "lot_size": LOT, "target_weight_pct": TARGET_W * 100,
        "max_weight_pct": MAX_W * 100,
        "invested": int(top["cost"].sum()),
        "cash_left": int(cash),
        "cash_left_pct": round(float(cash / CAPITAL * 100), 2),
        "weight_min_pct": round(float(top["weight_pct"].min()), 2),
        "weight_max_pct": round(float(top["weight_pct"].max()), 2),
        "weight_sd_pct": round(float(top["weight_pct"].std()), 2),
    }

    # ---------- 比較 ----------
    cur = pd.read_csv(ROOT / "data/processed/portfolio.csv", dtype={"code": str})
    cur_in_u = u[u["code"].isin(cur["code"])]
    rep["vs_current_v10"] = {
        "overlap": int(len(set(top["code"]) & set(cur["code"]))),
        "overlap_codes": sorted(set(top["code"]) & set(cur["code"])),
        "current_matched_in_universe": int(len(cur_in_u)),
        "current_axis_medians": {a: round(float(cur_in_u[a].median()), 1) for a in AXES},
        "new_axis_medians": {a: round(float(top[a].median()), 1) for a in AXES},
        "current_total_median_percentile": round(
            float(pctrank(u["total"])[cur_in_u.index].median()), 1),
    }
    rep["top20_profile"] = {
        "per_median": round(float(top["per"].median()), 1),
        "pbr_median": round(float(top["pbr"].median()), 2),
        "market_cap_median_oku": round(float(top["market_cap"].median() / 1e8), 1),
        "adv60_median_oku": round(float(top["avg_trading_value_60d"].median() / 1e8), 2),
        "roe_median": round(float((top["net_income"] / top["equity"]).median() * 100), 1),
        "total_min": round(float(top["total"].min()), 1),
        "total_max": round(float(top["total"].max()), 1),
    }

    keep = ["code", "company_name_ja", "company_name", "sector_33", "market", "scale_category",
            "fiscal_year", "price_used", "market_cap", "per", "pbr", "shares_source",
            "post_filing_split", "avg_trading_value_60d",
            "moat_p", "change_p", "future_p", "price_p", "total",
            "units", "shares", "cost", "weight_pct"]
    top[keep].to_csv(OUT / "final_top20.csv", index=False)
    u[["code", "company_name_ja", "sector_33", "price_used", "market_cap", "per", "pbr"]
      + AXES + ["total"]].sort_values("total", ascending=False).to_csv(
        OUT / "final_all_eligible.csv", index=False)
    (OUT / "final_summary.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print()
    print(top[["code", "company_name_ja", "sector_33", "price_used", "per", "pbr", "shares_source",
               "moat_p", "change_p", "future_p", "price_p", "total",
               "shares", "cost", "weight_pct"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
