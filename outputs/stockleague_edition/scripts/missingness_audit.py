# -*- coding: utf-8 -*-
"""データ欠測がスクリーニングを歪めていないかの徹底監査。

読む: data/processed/{scores,universe,latest_prices,yfinance_metrics,fundamentals_clean}.csv
出す: missingness_audit.json  (全数値は実測)
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = Path(__file__).with_name("missingness_audit.json")
R = {}

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
yf = pd.read_csv(ROOT / "data/processed/yfinance_metrics.csv")
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
NUM = ["moat_score", "transformation_score", "future_moat_score", "valuation_score", "bb_score",
       "adjusted_bb_score", "momentum_score", "risk_score", "roe", "operating_margin", "equity_ratio",
       "operating_cf", "revenue_growth", "operating_income_growth", "operating_loss_years_3y",
       "net_loss_years_3y", "negative_ocf_years_3y", "operating_income", "net_income", "revenue",
       "equity", "total_assets", "shares_outstanding", "market_cap", "trailing_pe", "forward_pe",
       "price_to_book", "dividend_yield", "beta", "annual_volatility", "max_drawdown", "rd_ratio",
       "ocf_margin", "return_12m_ex_1m", "avg_trading_value_60d", "pe_for_score", "pbr_for_score",
       "dividend_yield_clean", "profitability_score", "stability_score", "cash_generation_score",
       "competitive_position_score", "intangible_investment_score",
       "transformation_component_valuation_gap", "future_moat_component_intangible_asset"]
for c in NUM:
    if c in s.columns: s[c] = pd.to_numeric(s[c], errors="coerce")

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
h = px.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum()); s["histd"] = s.ticker.map(h).fillna(0)
last_px = px.sort_values("date").groupby("ticker")["adj_close"].last()
s["mcap"] = s.ticker.map(last_px) * s.shares_outstanding
s["ey"] = s.net_income / s.mcap

base_m = (truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")
          & truthy(s, "liquid_20m_60d") & (s.histd >= 756))
B = s[base_m].copy()
s["has_yf"] = s.ticker.isin(set(yf.ticker))
B["has_yf"] = B.ticker.isin(set(yf.ticker))
N = len(B)

# =====================================================================
# 欠陥1: yfinance 由来指標は「売買代金上位300社」しか取得されていない
# =====================================================================
liq_rank = s.sort_values("avg_trading_value_60d", ascending=False).reset_index(drop=True)
liq_rank["liq_rank"] = np.arange(1, len(liq_rank) + 1)
rk = liq_rank.set_index("ticker")["liq_rank"]
yfr = rk.reindex(yf.ticker).dropna()
R["D1_yfinance_truncation"] = {
    "yfinance_metrics_rows": int(len(yf)),
    "universe_rows": int(len(s)),
    "fetch_code": "fetch_yfinance.py: liquid_tickers=売買代金降順ソート → fetch_quote_metrics(limit=quote_metrics_limit)",
    "liquidity_rank_of_fetched_min": int(yfr.min()), "liquidity_rank_of_fetched_max": int(yfr.max()),
    "fetched_are_exactly_top300_by_liquidity": bool(set(yfr.astype(int)) == set(range(1, len(yf) + 1))),
    "note": "無作為欠測ではなく、売買代金の上位から決定論的に切られている(=規模と完全相関)",
    "coverage_universe": round(float(s.has_yf.mean()), 4),
    "coverage_base": round(float(B.has_yf.mean()), 4),
    "n_covered_base": int(B.has_yf.sum()), "n_base": N,
}
# 規模別・市場別カバレッジ
R["D1_coverage_by_scale"] = {str(k): {"n": int(v["has_yf"].size), "covered": int(v["has_yf"].sum()),
                                      "rate": round(float(v["has_yf"].mean()), 3)}
                             for k, v in B.groupby(B.scale_category.fillna("(欠損)"))[["has_yf"]]}
R["D1_coverage_by_market"] = {str(k): {"n": int(v["has_yf"].size), "covered": int(v["has_yf"].sum()),
                                       "rate": round(float(v["has_yf"].mean()), 3)}
                              for k, v in B.groupby(B.market.fillna("(欠損)"))[["has_yf"]]}
# 売買代金の分位別
B["_liqq"] = pd.qcut(B.avg_trading_value_60d, 5, labels=["Q1最小", "Q2", "Q3", "Q4", "Q5最大"])
R["D1_coverage_by_liquidity_quintile"] = {str(k): round(float(v.mean()), 3)
                                          for k, v in B.groupby("_liqq", observed=True)["has_yf"]}

# =====================================================================
# 欠陥2: 欠測を .fillna(0) = 母集団平均として扱う → スコアが「平均」に化ける
# =====================================================================
def zero_share(col, sub=None):
    d = (sub if sub is not None else B)[col]
    return round(float((d.round(10) == 0).mean()), 4)

R["D2_exact_zero_share_in_base"] = {
    "valuation_score": zero_share("valuation_score"),
    "transformation_component_valuation_gap": zero_share("transformation_component_valuation_gap"),
    "future_moat_component_intangible_asset": zero_share("future_moat_component_intangible_asset"),
    "momentum_score": zero_share("momentum_score"),
    "risk_score": zero_share("risk_score"),
    "note": "0 は『平均並み』の意味を持つため、欠測企業は自動的に中央付近に置かれる(除外もされない)",
}
R["D2_valuation_score_zero_by_coverage"] = {
    "yf有り_zero率": zero_share("valuation_score", B[B.has_yf]),
    "yf無し_zero率": zero_share("valuation_score", B[~B.has_yf]),
    "yf無し社数": int((~B.has_yf).sum()),
}

# =====================================================================
# 欠陥3: transformation_score は重み合計0.90、うち0.70がyf限定フィールド
# =====================================================================
R["D3_transformation_formula"] = {
    "weights_in_code": {"z(1/PBR)": 0.35, "z(1/PE)": 0.20, "avg_z(売上・営利成長)": 0.20, "z(配当利回り)": 0.15},
    "weight_sum": 0.90,
    "weight_on_yf_only_fields": 0.35 + 0.20 + 0.15,
    "share_of_weight_yf_only": round((0.35 + 0.20 + 0.15) / 0.90, 3),
    "note": "yf無し企業では PBR/PE/配当の3項が全て厳密に0 → transformation = 0.20×成長zスコアのみ",
}
for lab, sub in [("yf有り", B[B.has_yf]), ("yf無し", B[~B.has_yf])]:
    R["D3_transformation_formula"][f"{lab}_std"] = round(float(sub.transformation_score.std()), 4)
    R["D3_transformation_formula"][f"{lab}_mean"] = round(float(sub.transformation_score.mean()), 4)
    R["D3_transformation_formula"][f"{lab}_max"] = round(float(sub.transformation_score.max()), 4)
    R["D3_transformation_formula"][f"{lab}_n"] = int(len(sub))
# ランク汚染: 上位k社のうちyf有りの割合
def topk_cov(col, ks=(5, 10, 20, 50, 100)):
    o = {}
    for k in ks:
        t = B.nlargest(k, col)
        o[f"top{k}"] = {"yf有り": int(t.has_yf.sum()), "率": round(float(t.has_yf.mean()), 3)}
    return o
R["D3_rank_contamination"] = {
    "transformation_score": topk_cov("transformation_score"),
    "valuation_score": topk_cov("valuation_score"),
    "bb_score": topk_cov("bb_score"),
    "adjusted_bb_score": topk_cov("adjusted_bb_score"),
    "moat_score": topk_cov("moat_score"),
    "future_moat_score": topk_cov("future_moat_score"),
    "base_baseline_rate": round(float(B.has_yf.mean()), 3),
}

# =====================================================================
# 欠陥4: 破5(変わる堀)の選定は yf カバレッジで決まっていないか
# =====================================================================
HA5 = ["9022", "9513", "9503", "1662", "5214"]
SHU5 = ["3092", "4716", "7014", "8136", "6920"]
RI5 = ["6777", "6871", "6590", "6387", "6627"]
DUAL3 = ["6861", "7725", "6929"]
BR2 = ["3449", "4971"]
P20 = SHU5 + HA5 + RI5 + DUAL3 + BR2
covmap = dict(zip(s.code, s.has_yf))
R["D4_selected20_yf_coverage"] = {
    "守5": {c: bool(covmap.get(c)) for c in SHU5},
    "破5": {c: bool(covmap.get(c)) for c in HA5},
    "離5": {c: bool(covmap.get(c)) for c in RI5},
    "両立3": {c: bool(covmap.get(c)) for c in DUAL3},
    "分散2": {c: bool(covmap.get(c)) for c in BR2},
    "20社中yf有り": int(sum(bool(covmap.get(c)) for c in P20)),
    "base平均カバレッジ": round(float(B.has_yf.mean()), 3),
}
# 反実仮想: transformation を「全社で計算可能な成長項だけ」で作り直すと破5は変わるか
PROF = (B.operating_income > 0) & (B.net_income > 0) & (B.roe >= 0.05)
trans_pool = B[(B.category == "Transformation Moat") & PROF].copy()


def pick(df, score, n, cap=2, asc=False):
    cnt, out = {}, []
    for _, r in df.sort_values(score, ascending=asc).iterrows():
        if cnt.get(r.sector_33, 0) >= cap: continue
        cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1
        out.append(r.code)
        if len(out) == n: break
    return out


def z(x):
    x = pd.to_numeric(x, errors="coerce"); lo, hi = x.quantile(.01), x.quantile(.99); x = x.clip(lo, hi)
    sd = x.std()
    return (x - x.mean()) / sd if sd and np.isfinite(sd) else pd.Series(0.0, index=x.index)


B["trans_growth_only"] = (z(B.revenue_growth).fillna(0) + z(B.operating_income_growth).fillna(0)) / 2
trans_pool["trans_growth_only"] = B.loc[trans_pool.index, "trans_growth_only"]
alt = pick(trans_pool, "trans_growth_only", 5)
R["D4_counterfactual_ha5"] = {
    "現行の破5(adjusted_bb順)": HA5,
    "現行の破5の名前": [str(s.set_index('code').loc[c, 'company_name']) for c in HA5],
    "yf限定フィールドを外した場合の破5": alt,
    "yf限定を外した破5の名前": [str(s.set_index('code').loc[c, 'company_name']) for c in alt],
    "重複社数": len(set(HA5) & set(alt)),
    "note": "『変わる堀』プール自体も category=argmax(transformation_score) で決まるため、yf限定フィールドが選抜を支配",
}
# Transformation Moat カテゴリ自体のyfカバレッジ
tm = B[B.category == "Transformation Moat"]
R["D4_transformation_moat_category"] = {
    "n": int(len(tm)), "yf有り": int(tm.has_yf.sum()), "率": round(float(tm.has_yf.mean()), 3),
    "base平均": round(float(B.has_yf.mean()), 3),
}

# =====================================================================
# 欠陥5: 守5 の Greenblatt 順位は時価総額必須 → 162社中20社しか候補になれない
# =====================================================================
SHU = ((B.roe >= 0.15) & (B.operating_margin >= 0.10) & (B.equity_ratio >= 0.50)
       & (B.operating_loss_years_3y == 0) & (B.net_loss_years_3y == 0)
       & (B.negative_ocf_years_3y == 0) & (B.operating_cf > 0)
       & (B.revenue_growth >= 0) & (B.operating_income_growth >= 0))
Q = B[SHU].copy()
Qp = Q[(Q.ey > 0) & Q.mcap.notna()]
R["D5_shu_gate_price_rankable"] = {
    "品質ゲート通過": int(len(Q)),
    "時価総額データあり": int(Q.mcap.notna().sum()),
    "益回り>0も満たす": int(len(Qp)),
    "データ欠測だけで守5候補から外れた社数": int(len(Q) - Q.mcap.notna().sum()),
    "外れた割合": round(float(1 - Q.mcap.notna().mean()), 3),
    "外れた企業のROE中央値": round(float(Q[Q.mcap.isna()].roe.median()) * 100, 1),
    "残った企業のROE中央値": round(float(Q[Q.mcap.notna()].roe.median()) * 100, 1),
    "外れた企業の売買代金中央値_百万円": round(float(Q[Q.mcap.isna()].avg_trading_value_60d.median()) / 1e6, 1),
    "残った企業の売買代金中央値_百万円": round(float(Q[Q.mcap.notna()].avg_trading_value_60d.median()) / 1e6, 1),
    "note": "『162社から5社』ではなく実質『20社から5社』。落ちた142社はROEが低いのではなく売買代金が小さい",
}
# 反実仮想: ROE順位だけで守5を選ぶと?
Q["roe_rank_only"] = Q.roe.rank(ascending=False)
alt_shu = pick(Q, "roe_rank_only", 5, asc=True)
R["D5_counterfactual_shu5"] = {
    "現行守5": SHU5, "ROE順のみ守5": alt_shu, "重複": len(set(SHU5) & set(alt_shu)),
    "ROE順のみ守5の名前": [str(s.set_index('code').loc[c, 'company_name']) for c in alt_shu],
}

# =====================================================================
# 欠陥6: 守ゲートの各条件で NaN が黙って False 扱い(=除外記録に残らない)
# =====================================================================
fields = ["roe", "operating_margin", "equity_ratio", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "operating_cf", "revenue_growth", "operating_income_growth"]
R["D6_shu_gate_nan_counts_in_base"] = {f: int(B[f].isna().sum()) for f in fields}
R["D6_shu_gate_nan_any"] = int(B[fields].isna().any(axis=1).sum())
R["D6_note"] = "NaN>=0.15 は False。欠測企業は『不合格』として静かに落ち、exclusion_record に理由が残らない"

# =====================================================================
# 欠陥7: stability_score = z(-annual_volatility.fillna(0)) → 欠測が最高評価
# =====================================================================
R["D7_stability_fillna_bug"] = {
    "code": 'average_z(df.assign(neg_vol=-df["annual_volatility"].fillna(0)), ["neg_vol"])',
    "universe_vol_nan": int(s.annual_volatility.isna().sum()),
    "base_vol_nan": int(B.annual_volatility.isna().sum()),
    "vol_min_observed": round(float(s.annual_volatility.min()), 4),
    "note": "欠測→neg_vol=0。観測値の neg_vol は全て負なので、欠測企業は安定性で最上位になる",
}
if int(s.annual_volatility.isna().sum()):
    nanv = s[s.annual_volatility.isna()]
    R["D7_stability_fillna_bug"]["欠測企業のstability_score中央値"] = round(float(nanv.stability_score.median()), 4)
    R["D7_stability_fillna_bug"]["観測企業のstability_score中央値"] = round(
        float(s[s.annual_volatility.notna()].stability_score.median()), 4)
    R["D7_stability_fillna_bug"]["欠測企業のstability_percentile"] = round(
        float((s.stability_score < nanv.stability_score.median()).mean()), 4)

# =====================================================================
# 欠陥8: average_z の欠測=0 埋めが品質スコアを平均へ縮める
# =====================================================================
prof_cols = ["operating_margin", "roe", "equity_ratio"]
nmiss = B[prof_cols].isna().sum(axis=1)
R["D8_average_z_shrinkage"] = {
    "profitability_score の材料": prof_cols,
    "欠測列数の分布": {str(k): int(v) for k, v in nmiss.value_counts().sort_index().items()},
    "note": "材料3つ中1つ欠測なら z の平均が 2/3 に縮む(除外ではなく平均寄せ)。競争優位・現金創出も同型",
    "rd_ratio_nan_base": int(B.rd_ratio.isna().sum()),
    "rd_ratio_nan_rate_base": round(float(B.rd_ratio.isna().mean()), 3),
    "note2": "rd_ratio は future_moat の無形資産項(重み0.25)の材料。欠測は0=平均扱い",
}

# =====================================================================
# 欠陥9: ファネルのラベルずれ(流動性の脱落を『投資適格』段に押し込んでいる)
# =====================================================================
R["D9_funnel_label_mismatch"] = {
    "screening_summary": {"universe": 3649, "price_available": int(truthy(s, "price_available").sum()),
                          "liquid_20m_60d": int(truthy(s, "liquid_20m_60d").sum()),
                          "investment_eligible": int(truthy(s, "investment_eligible").sum())},
    "報告書のファネル(funnel_branches_v9.json)": {
        "0-1 金融を除く普通株(価格データあり)": 3481,
        "0-2 投資適格(監理・整理銘柄等を除外)": 1819,
        "0-3 流動性 60日平均売買代金の基準": 1819,
        "0-4 価格履歴3年": 1791},
    "実際の内訳": "liquid_20m_60d(売買代金2000万円/日)で 3648→2560 = 1,088社脱落。適格性の理由別除外は 597社(unique)",
    "note": "報告書は 3481→1819 の 1,662社を『投資適格(監理・整理銘柄等を除外)』に帰属させ、次の『流動性』段の脱落を0にしている。実態は逆で、脱落の主因は流動性しきい値",
}

# =====================================================================
# 欠陥10: 益回り(ey)の分母が「最新株価×株式数」= 期末時価総額
# =====================================================================
R["D10_ey_lookahead"] = {
    "code": 's["mcap"] = last_px * shares_outstanding ; s["ey"] = net_income / mcap',
    "note": "守5の Greenblatt 順位に使う益回りの分母が『直近(=期末)株価』。値上がりした銘柄は益回りが下がり不利、下落銘柄は有利。選定時点(2026-04-30)より後の価格情報が順位付けに混入する",
    "last_price_date": str(px.date.max().date()),
    "effective_date": "20260430",
}

OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str))
print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
