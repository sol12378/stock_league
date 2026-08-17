# -*- coding: utf-8 -*-
"""逐次ANDの実現可能フロンティア: 閾値 q を緩めたとき「20社・業種上限c」が成立するか。"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["adjusted_bb_score", "moat_score", "future_moat_score", "transformation_score", "roe",
          "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
          "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "operating_income", "net_income"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
h = px.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum()); s["histd"] = s.ticker.map(h).fillna(0)
base = (truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")
        & truthy(s, "liquid_20m_60d") & (s.histd >= 756))
B = s[base].copy()
N = len(B)
PROF = (B.operating_income > 0) & (B.net_income > 0) & (B.roe >= 0.05)


def maxpick(df, cap):
    """業種上限capのもとで採用可能な最大社数(=Σ min(業種社数, cap))。"""
    vc = df.sector_33.value_counts()
    return int(np.minimum(vc, cap).sum())


rows = []
for q in [0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.224, 0.20, 0.15, 0.10, 0.05, 0.02]:
    tm = B.moat_score.quantile(1 - q); tt = B.transformation_score.quantile(1 - q)
    tf = B.future_moat_score.quantile(1 - q)
    p = B[PROF & (B.moat_score >= tm) & (B.transformation_score >= tt) & (B.future_moat_score >= tf)]
    rows.append({
        "q_each_gate": q, "pool_n": len(p), "n_sectors": int(p.sector_33.nunique()),
        "max20_cap2": maxpick(p, 2), "max20_cap3": maxpick(p, 3), "max20_cap4": maxpick(p, 4),
        "ok_20_cap2": maxpick(p, 2) >= 20, "ok_20_cap4": maxpick(p, 4) >= 20,
        "top_sector_share": round(float(p.sector_33.value_counts(normalize=True).iloc[0]), 3) if len(p) else None,
        "naive_indep_expect": round(N * q ** 3, 1),
    })
front = pd.DataFrame(rows)
print(f"=== 逐次AND(3スコアそろって上位q%)のフロンティア  base N={N} ===")
print(front.to_string(index=False))

# --- 現行(OR/役割)設計の選抜率との比較 ---
SHU = ((B.roe >= 0.15) & (B.operating_margin >= 0.10) & (B.equity_ratio >= 0.50)
       & (B.operating_loss_years_3y == 0) & (B.net_loss_years_3y == 0)
       & (B.negative_ocf_years_3y == 0) & (B.operating_cf > 0)
       & (B.revenue_growth >= 0) & (B.operating_income_growth >= 0))
print(f"\n現行設計の各役割の選抜率(base {N}社に対して):")
print("  守: 品質ゲート通過 %d社(上位%.1f%%)→ そこから5社 = 上位%.2f%%" % (
    int(SHU.sum()), 100 * SHU.sum() / N, 100 * 5 / N))
print("  AND設計で20社を得るには各ゲートを上位%.1f%%までしか絞れない(独立仮定 q=(20/N)^(1/3))" % (
    100 * (20 / N) ** (1 / 3)))

# --- 各ゲート単独で「上位20社」を取ったときの重複 ---
top20 = {}
for c, lab in [("moat_score", "守(堀)"), ("transformation_score", "破(変革)"), ("future_moat_score", "離(未来)")]:
    top20[lab] = set(B.nlargest(20, c).code)
print("\n各スコア単独Top20の重複社数:")
labs = list(top20)
for i in range(3):
    for j in range(i + 1, 3):
        print(f"  {labs[i]} ∩ {labs[j]} = {len(top20[labs[i]] & top20[labs[j]])}社")
print(f"  3つすべて = {len(top20[labs[0]] & top20[labs[1]] & top20[labs[2]])}社")

Path(__file__).with_name("and_frontier.json").write_text(
    json.dumps({"N_base": N, "frontier": rows,
                "shu_gate_n": int(SHU.sum()),
                "q_needed_for_20_indep": round(float((20 / N) ** (1 / 3)), 4),
                "top20_overlap": {f"{labs[i]}∩{labs[j]}": len(top20[labs[i]] & top20[labs[j]])
                                  for i in range(3) for j in range(i + 1, 3)},
                "top20_all_three": len(top20[labs[0]] & top20[labs[1]] & top20[labs[2]])},
               ensure_ascii=False, indent=1))
