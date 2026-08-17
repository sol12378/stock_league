# -*- coding: utf-8 -*-
"""v10 のスクリーニング・対照群・数値の欠陥監査。すべて実測。"""
import json, re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
OUT = Path(__file__).with_name("v10_audit.json")
R = {}
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

CC = json.loads((ED / "control_comparison_v10.json").read_text())
F9 = json.loads((ED / "funnel_branches_v9.json").read_text())
buf20 = CC["buf_pool"]["buf20"]; buf12 = CC["buf_pool"]["buf12"]; buf15 = CC["buf_pool"]["buf15"]
OUR20 = (F9["shu"]["top5"] + F9["ha"]["picked"] + F9["ri_picked"]
         + F9["dual"]["picked"] + F9["bridge"]["picked"])

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
s["shares_outstanding"] = pd.to_numeric(s.shares_outstanding, errors="coerce")
nm = s.set_index("code")["company_name"].to_dict()
shares = s.set_index("code")["shares_outstanding"]

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                     columns=["date", "ticker", "close", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
adj = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
raw = px.pivot_table(index="date", columns="ticker", values="close").sort_index()

# ============ V10-A: 主対照と本PFの重複 ============
ov = sorted(set(buf20) & set(OUR20))
R["A_control_overlap"] = {
    "主対照(新バフェット型20社)": buf20,
    "本PF20社": OUR20,
    "重複社数": len(ov),
    "重複銘柄": [{"code": c, "name": str(nm.get(c)), "本PFでの役割":
                 "守5" if c in F9["shu"]["top5"] else ("離5" if c in F9["ri_picked"] else "その他")}
                for c in ov],
    "重複率": round(len(ov) / 20, 3),
    "note": "守5は定義上『新バフェット品質順位のTop5』なので必ず主対照に含まれる。"
            "対照群の35%が本PFそのものであり、差の検定(t=1.01)は独立2群の比較ではない",
}

# ============ V10-B: 主対照の「20社」はデータ可用性で決まっている ============
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "net_income",
          "revenue_growth", "operating_income_growth", "operating_loss_years_3y",
          "net_loss_years_3y", "negative_ocf_years_3y"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
elig = s[truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")].copy()
last_adj = adj.ffill().iloc[-1]
elig["mcap"] = elig.ticker.map(last_adj) * elig.shares_outstanding
elig["ey"] = elig.net_income / elig.mcap
Q = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50)
         & (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0)
         & (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0)
         & (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)]
R["B_control_size_is_data_artifact"] = {
    "品質関門通過": int(len(Q)),
    "時価総額データあり(=主対照の全量)": int(Q.mcap.notna().sum()),
    "コード上の扱い": "build_control_v10.py: assert len(p) == 20  ← 20という数を前提に固定",
    "buf15の作り方": "pick(p, 99) で99社要求 → 業種上限2で15社しか取れない(=15も選択ではない)",
    "note": "本文は主対照を『社数を切らない20社』と説明するが、20は品質162社のうち"
            "時価総額データがある社数。感応度の『社数3通り(12/15/20)』のうち20と15は"
            "データと業種上限で決まっており、独立した3つの選択肢ではない",
}

# ============ V10-C: 期首加重の株数と株価の整合性 ============
W3Y = 756
sub_adj = adj[[c + ".T" for c in buf20]].tail(W3Y).ffill()
sub_raw = raw[[c + ".T" for c in buf20]].tail(W3Y).ffill()
p0_adj = sub_adj.iloc[0]; p0_raw = sub_raw.iloc[0]


def wts(p0, cap=0.25):
    mc = pd.Series({c: float(p0[c + ".T"]) * float(shares[c]) for c in buf20})
    w = (mc / mc.sum()).clip(upper=cap); w = w / w.sum()
    return w


w_adj = wts(p0_adj); w_raw = wts(p0_raw)
diff = (w_adj - w_raw).abs()
R["C_start_weight_consistency"] = {
    "実装": 'px_ref = adj_close(配当・分割調整後)の期首値 × shares_outstanding(2026年時点の株数)',
    "本文の主張": "期首加重＝各測定窓の期首株価×発行済株数(＝当時実際に組めた重み)",
    "問題1": "shares_outstanding は2026年時点の1点のみ。3年前の株数ではないので"
             "『当時実際に組めた重み』にはならない(自己株買い・増資・分割で株数は動く)",
    "問題2": "adj_close は配当・分割調整後の系列。調整後株価×現在株数は時価総額ではない",
    "未調整closeで組み直した場合の重み乖離": {
        "最大乖離pt": round(float(diff.max()) * 100, 2),
        "最大乖離銘柄": str(diff.idxmax()) + " " + str(nm.get(diff.idxmax(), "")),
        "合計絶対乖離pt": round(float(diff.sum()) * 100, 2),
        "上位5銘柄": [{"code": c, "adj基準%": round(float(w_adj[c]) * 100, 2),
                    "close基準%": round(float(w_raw[c]) * 100, 2),
                    "差pt": round(float(w_adj[c] - w_raw[c]) * 100, 2), "name": str(nm.get(c))}
                   for c in diff.sort_values(ascending=False).head(5).index],
    },
    "上限25%の再正規化後の逸脱": {
        "adj基準の最大ウェイト%": round(float(w_adj.max()) * 100, 2),
        "cap違反(>25%)": bool(w_adj.max() > 0.2501),
        "note": "clip→再正規化を1回だけ行うため、再正規化後に上限を超えうる",
    },
}

# ============ V10-D: 期間中に株式分割があった銘柄(close と adj_close の乖離で検出) ============
splits = []
for c in buf20 + OUR20:
    t = c + ".T"
    if t not in raw.columns: continue
    r = raw[t].tail(W3Y).ffill(); a = adj[t].tail(W3Y).ffill()
    if r.isna().all() or a.isna().all(): continue
    ratio = (r / a).dropna()
    if len(ratio) < 10: continue
    rel = float(ratio.max() / ratio.min())
    if rel > 1.5:
        splits.append({"code": c, "name": str(nm.get(c)), "close/adj比の変動倍率": round(rel, 2),
                       "in_control": c in buf20, "in_ourPF": c in OUR20})
R["D_split_or_dividend_distortion"] = {
    "検出銘柄(close/adj比が1.5倍以上動いた=分割か多額配当)": splits,
    "note": "この銘柄群では『調整後株価×現在株数』が当時の時価総額から大きく外れる。"
            "期首加重の主系列に直接影響する",
}

# ============ V10-E: 主対照の全指標を照合(本文『3年は6指標すべて上回る』) ============
o3 = CC["ours"]["3y"]; c3 = CC["control_buffett20_start"]["3y"]
o1 = CC["ours"]["1y"]; c1 = CC["control_buffett20_start"]["1y"]
def cmp6(o, c):
    return {
        "リターン": {"ours": o["ann_return"], "control": c["ann_return"], "ours勝ち": o["ann_return"] > c["ann_return"]},
        "ボラティリティ(低いほど良)": {"ours": o["volatility"], "control": c["volatility"], "ours勝ち": o["volatility"] < c["volatility"]},
        "シャープ": {"ours": o["sharpe"], "control": c["sharpe"], "ours勝ち": o["sharpe"] > c["sharpe"]},
        "最大下落(浅いほど良)": {"ours": o["max_drawdown"], "control": c["max_drawdown"], "ours勝ち": o["max_drawdown"] > c["max_drawdown"]},
        "ベータ(低いほど良)": {"ours": o["beta_vs_topix"], "control": c["beta_vs_topix"], "ours勝ち": o["beta_vs_topix"] < c["beta_vs_topix"]},
        "情報比": {"ours": o["information_ratio"], "control": c["information_ratio"], "ours勝ち": o["information_ratio"] > c["information_ratio"]},
    }
R["E_six_metric_claim"] = {"3y": cmp6(o3, c3), "1y": cmp6(o1, c1)}
R["E_six_metric_claim"]["3y_勝ち数"] = sum(v["ours勝ち"] for v in R["E_six_metric_claim"]["3y"].values())
R["E_six_metric_claim"]["1y_勝ち数"] = sum(v["ours勝ち"] for v in R["E_six_metric_claim"]["1y"].values())
R["E_six_metric_claim"]["MDD差pt_3y"] = round((o3["max_drawdown"] - c3["max_drawdown"]) * 100, 2)

# ============ V10-F: 本文テキストの主張と実装の一致チェック ============
src = (ED / "scripts/build_contest_v10.py").read_text()
checks = {
    "流動性しきい値を1,000万円と記述": "1日あたり1,000万円を基準とする" in src,
    "実装は2,000万円": "20_000_000" in (ROOT / "src/screening/scoring.py").read_text(),
    "『(実装どおりに開示)』と明記": "(実装どおりに開示)" in src,
    "式10をフル形6項目で印字": "Ｒ＝株主還元の強化(0.16)" in src,
    "Ｒ・Ｋが未計算である旨の開示": ("株主還元" in src and "取得できず" in src) or "lite" in src.lower(),
    "離のキーワード飽和を開示": "飽和" in src,
    "時価総額データ在庫の注記(ファネル1-7)": "時価総額データの在庫がなく" in src,
    "研究開発費のゼロ埋めを開示": "ゼロ埋め" in src or "研究開発費比率" in src,
    "守の競争優位が営業利益率の複製である旨": "二重計上" in src or "競争優位" in src and "複製" in src,
    "主対照と本PFの重複社数を明記": "重複" in src and ("7社" in src or "７社" in src),
    "主対照の20社がデータ可用性由来である旨": "時価総額データ" in src,
}
R["F_text_vs_implementation"] = checks
m = re.search(r"変わる堀の点数の上位", src)
R["F_funnel_2_4_label"] = {"本文に『変わる堀の点数の上位』がある": bool(m),
                           "実装の並べ替えキー": "adjusted_bb_score (build_portfolio_v7.py)"}

# ============ V10-G: 局面の期間定義とデータ終端 ============
R["G_phase_windows"] = {
    "PHASES_P3の定義": "2024-07-01 〜 2026-06-30",
    "価格データの最終日": str(adj.index.max().date()),
    "note": "P3の終端はデータ終端(2026-06-01)で切れる。本文が『2026年6月30日まで』と読める表記なら不正確",
    "3年窓の実際の期間": f"{str(adj.tail(W3Y).index.min().date())} 〜 {str(adj.tail(W3Y).index.max().date())}",
}

OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str))
print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
