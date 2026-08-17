# -*- coding: utf-8 -*-
"""チームFB検証: 守る堀→破る堀→離れる堀 を順に AND スクリーニングして20社取れるか。

出力: and_feasibility.json (数値はすべて実測)
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUTJ = Path(__file__).with_name("and_feasibility.json")

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)
s["ticker"] = s["code"] + ".T"


def truthy(df, c):
    return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])


num = ["adjusted_bb_score", "moat_score", "future_moat_score", "transformation_score", "roe",
       "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
       "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
       "negative_ocf_years_3y", "operating_income", "net_income", "equity",
       "shares_outstanding", "annual_volatility", "avg_trading_value_60d"]
for c in num:
    s[c] = pd.to_numeric(s[c], errors="coerce")

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
histd = px.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())
s["histd"] = s["ticker"].map(histd).fillna(0)
last_px = px.sort_values("date").groupby("ticker")["adj_close"].last()
s["mcap"] = s.ticker.map(last_px) * s.shares_outstanding
s["ey"] = s.net_income / s.mcap

base = (truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")
        & truthy(s, "liquid_20m_60d") & (s.histd >= 756))
B = s[base].copy()
R = {"n_universe": int(len(s)), "n_base": int(base.sum())}

# ---------------------------------------------------------------- 0) 構造的検査
# category は3スコアの argmax → 3カテゴリの AND は定義上ゼロ
cat = s.category.value_counts().to_dict()
R["category_counts"] = {k: int(v) for k, v in cat.items()}
R["category_is_argmax_exclusive"] = True
R["and_of_three_categories"] = 0

# 3スコアの相関(base母集団・順位相関)
sc = ["moat_score", "transformation_score", "future_moat_score"]
R["spearman_base"] = B[sc].corr(method="spearman").round(4).to_dict()
R["pearson_base"] = B[sc].corr().round(4).to_dict()

# 離スコアの飽和(同点)構造
fm = B["future_moat_score"].round(6)
vc = fm.value_counts()
R["future_moat_ties"] = {
    "n_base": int(len(fm)),
    "n_distinct_values": int(fm.nunique()),
    "largest_tie_value": float(vc.index[0]),
    "largest_tie_n": int(vc.iloc[0]),
    "top3_tie_ns": [int(x) for x in vc.head(3).tolist()],
}

# ---------------------------------------------------------------- 1) 提案どおりの逐次AND(ハードゲート)
SHU = ((B.roe >= 0.15) & (B.operating_margin >= 0.10) & (B.equity_ratio >= 0.50)
       & (B.operating_loss_years_3y == 0) & (B.net_loss_years_3y == 0)
       & (B.negative_ocf_years_3y == 0) & (B.operating_cf > 0)
       & (B.revenue_growth >= 0) & (B.operating_income_growth >= 0))

steps = []
cur = B.copy()
steps.append({"step": "0 適格母集団(base)", "n": int(len(cur))})
cur = cur[SHU.reindex(cur.index).fillna(False)]
steps.append({"step": "1 守る堀ゲート(ROE15/OPM10/自己資本50/無赤字/OCF>0/増収増益)", "n": int(len(cur))})

# 破る堀ゲート: v9本文と同じ「transformation_score が基準超」= Transformation Moat 相当の閾値を
# カテゴリではなくスコア閾値として使う(排他性を外す)。基準は base の transformation_score 中位。
thr_tr = float(B.transformation_score.median())
R["transformation_threshold_median_base"] = round(thr_tr, 6)
cur_ha = cur[(cur.transformation_score > thr_tr) & (cur.operating_income > 0)
             & (cur.net_income > 0) & (cur.roe >= 0.05)]
steps.append({"step": "2 破る堀ゲート(変革スコア>base中位・黒字・ROE>=5%)", "n": int(len(cur_ha))})

thr_fm = float(B.future_moat_score.median())
cur_ri = cur_ha[cur_ha.future_moat_score > thr_fm]
steps.append({"step": "3 離れる堀ゲート(未来スコア>base中位)", "n": int(len(cur_ri))})

cur_pr = cur_ri[(cur_ri.ey > 0) & cur_ri.mcap.notna()]
steps.append({"step": "4 価格順位可能(益回り>0・時価総額あり)", "n": int(len(cur_pr))})
R["sequential_and_median_thresholds"] = steps
R["survivors_median"] = sorted(cur_pr.code.tolist())
R["survivors_median_names"] = cur_pr.set_index("code")["company_name"].to_dict()

# ---------------------------------------------------------------- 2) 閾値グリッド(何%上位まで緩めれば20社?)
grid = []
for q in [0.50, 0.40, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]:
    t_tr = B.transformation_score.quantile(1 - q)
    t_fm = B.future_moat_score.quantile(1 - q)
    t_mo = B.moat_score.quantile(1 - q)
    # (a) 守=ハードゲート版
    a = cur[(cur.transformation_score >= t_tr) & (cur.future_moat_score >= t_fm)
            & (cur.operating_income > 0) & (cur.net_income > 0) & (cur.roe >= 0.05)]
    # (b) 守もスコア上位q版(3スコアすべて上位q%)
    b = B[(B.moat_score >= t_mo) & (B.transformation_score >= t_tr) & (B.future_moat_score >= t_fm)
          & (B.operating_income > 0) & (B.net_income > 0) & (B.roe >= 0.05)]
    grid.append({
        "top_q": q,
        "n_hardgate_shu_AND_tr_AND_fm": int(len(a)),
        "n_all_three_scores_top_q": int(len(b)),
        "n_sectors_b": int(b.sector_33.nunique()),
        "expected_if_independent": round(len(B) * q ** 3, 2),
    })
R["threshold_grid"] = grid

# ---------------------------------------------------------------- 3) 2ゲートずつのAND(どこで詰まるか)
pairs = {}
for q in [0.50, 0.30, 0.20, 0.10]:
    t_tr = B.transformation_score.quantile(1 - q)
    t_fm = B.future_moat_score.quantile(1 - q)
    t_mo = B.moat_score.quantile(1 - q)
    pairs[str(q)] = {
        "moat_only": int((B.moat_score >= t_mo).sum()),
        "tr_only": int((B.transformation_score >= t_tr).sum()),
        "fm_only": int((B.future_moat_score >= t_fm).sum()),
        "moat_AND_tr": int(((B.moat_score >= t_mo) & (B.transformation_score >= t_tr)).sum()),
        "moat_AND_fm": int(((B.moat_score >= t_mo) & (B.future_moat_score >= t_fm)).sum()),
        "tr_AND_fm": int(((B.transformation_score >= t_tr) & (B.future_moat_score >= t_fm)).sum()),
        "all_three": int(((B.moat_score >= t_mo) & (B.transformation_score >= t_tr)
                          & (B.future_moat_score >= t_fm)).sum()),
    }
R["pairwise_and"] = pairs

# ---------------------------------------------------------------- 4) 守ゲート通過162社の中での破・離の分布
q162 = cur.copy()
R["shu_gate_n"] = int(len(q162))
R["shu_gate_transformation_pctile_mean"] = round(float(
    q162.transformation_score.apply(lambda v: (B.transformation_score < v).mean()).mean()), 4)
R["shu_gate_future_pctile_mean"] = round(float(
    q162.future_moat_score.apply(lambda v: (B.future_moat_score < v).mean()).mean()), 4)
R["shu_gate_n_above_median_tr"] = int((q162.transformation_score > thr_tr).sum())
R["shu_gate_n_above_median_fm"] = int((q162.future_moat_score > thr_fm).sum())

# ---------------------------------------------------------------- 5) 離の「検証パス」(実需確認7社)とのAND
SEMI = ["6777", "6871", "6590", "6387", "6627", "6951", "6941"]
semi = B[B.code.isin(SEMI)].copy()
semi_flags = []
for _, r in semi.iterrows():
    semi_flags.append({
        "code": r.code, "name": r.company_name,
        "roe": None if pd.isna(r.roe) else round(float(r.roe), 4),
        "operating_margin": None if pd.isna(r.operating_margin) else round(float(r.operating_margin), 4),
        "equity_ratio": None if pd.isna(r.equity_ratio) else round(float(r.equity_ratio), 4),
        "passes_shu_gate": bool(r.code in set(q162.code)),
        "tr_above_median": bool(r.transformation_score > thr_tr),
    })
R["verified_semi_vs_shu_gate"] = semi_flags
R["verified_semi_pass_shu"] = int(sum(x["passes_shu_gate"] for x in semi_flags))

# ---------------------------------------------------------------- 6) 現行20社が各ゲートを通るか
P20 = ["3092", "4716", "7014", "8136", "6920", "9022", "9513", "9503", "1662", "5214",
       "6777", "6871", "6590", "6387", "6627", "6861", "7725", "6929", "3449", "4971"]
rows = []
shu_codes = set(q162.code)
for c in P20:
    r = s[s.code == c]
    if r.empty:
        rows.append({"code": c, "in_base": False}); continue
    r = r.iloc[0]
    rows.append({
        "code": c, "name": r.company_name, "in_base": bool(c in set(B.code)),
        "shu_gate": bool(c in shu_codes),
        "tr_gt_median": bool(r.transformation_score > thr_tr),
        "fm_gt_median": bool(r.future_moat_score > thr_fm),
        "n_gates_passed": int(c in shu_codes) + int(r.transformation_score > thr_tr)
                          + int(r.future_moat_score > thr_fm),
    })
R["current20_gate_matrix"] = rows
R["current20_pass_all_three"] = int(sum(x.get("n_gates_passed", 0) == 3 for x in rows))
R["current20_pass_counts"] = {str(k): int(sum(x.get("n_gates_passed", -1) == k for x in rows))
                              for k in [0, 1, 2, 3]}

OUTJ.write_text(json.dumps(R, ensure_ascii=False, indent=1))
print(json.dumps(R, ensure_ascii=False, indent=1))
