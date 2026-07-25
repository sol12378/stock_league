# -*- coding: utf-8 -*-
"""V7 頑健性(条件③): 守の品質ゲート閾値/ランク/セクター上限を摂動し、守5・価格可能ユニバースの安定を実測。
＋重み方式(均等/役割予算/最小分散)と多期間は既存results参照。出力: robustness_v7.json"""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"; WORK = ROOT / "work/pure_buffett_benchmark"
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False); s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def tr(c): return s[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "revenue_growth", "operating_income_growth",
          "operating_loss_years_3y", "net_loss_years_3y", "negative_ocf_years_3y", "shares_outstanding", "net_income", "equity"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
last = px.sort_values("date").groupby("ticker")["adj_close"].last()
s["mcap"] = s.ticker.map(last) * s.shares_outstanding; s["ey"] = s.net_income / s.mcap
base = tr("investment_eligible") & ~tr("is_financial") & tr("price_available") & tr("liquid_20m_60d")

def shu5(roe=0.15, opm=0.10, eqr=0.50, need_growth=True, need_noloss=True, rankby="greenblatt", cap=2):
    m = base & (s.roe >= roe) & (s.operating_margin >= opm) & (s.equity_ratio >= eqr) & (s.operating_cf > 0) & (s.ey > 0) & s.mcap.notna()
    if need_noloss:
        m = m & (s.operating_loss_years_3y == 0) & (s.net_loss_years_3y == 0) & (s.negative_ocf_years_3y == 0)
    if need_growth:
        m = m & (s.revenue_growth >= 0) & (s.operating_income_growth >= 0)
    q = s[m].copy()
    if rankby == "greenblatt":
        q["r"] = q.roe.rank(ascending=False) + q.ey.rank(ascending=False)
    else:
        q["r"] = q.roe.rank(ascending=False)
    q = q.sort_values("r"); cnt, out = {}, []
    for _, r in q.iterrows():
        if cnt.get(r.sector_33, 0) >= cap: continue
        cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1; out.append(r.code)
        if len(out) == 5: break
    return out

BASE = shu5()
variants = {
    "ＲＯＥ閾値 12%": shu5(roe=0.12), "ＲＯＥ閾値 18%": shu5(roe=0.18),
    "営業利益率 5%": shu5(opm=0.05), "自己資本比率 40%": shu5(eqr=0.40),
    "増収増益ゲート外す": shu5(need_growth=False), "無赤字ゲート外す": shu5(need_noloss=False),
    "順位=ＲＯＥのみ": shu5(rankby="roe"), "同一業種上限 3": shu5(cap=3),
}
rows = {"基準(守5)": BASE}
rows.update(variants)
ov = {k: len(set(v) & set(BASE)) for k, v in variants.items()}
out = {"base_shu5": BASE, "variants": {k: v for k, v in variants.items()},
       "overlap_with_base": ov, "min_overlap": min(ov.values()), "n_variants": len(ov)}
json.dump(out, open(ED / "robustness_v7.json", "w"), ensure_ascii=False, indent=1)
print("守5基準:", BASE)
for k, v in variants.items():
    print(f"  {k:18} 一致{ov[k]}/5  {v}")
print("最小一致:", out["min_overlap"], "/5  (摂動", len(ov), "通り)")
