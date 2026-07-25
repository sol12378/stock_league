# -*- coding: utf-8 -*-
"""純正バフェットポートフォリオ(対照群)の構築と比較指標の計算。
規律:
 - 対照群 = phase1正典の固定順候補プール(outputs/phase1_top5/phase1_top5_candidate_pool.csv、
   本PFのBuffett Core 5社と同一系譜)の上から、Top5選定と同じ「同一業種は原則2社まで」を
   適用して20社。等金額(比べるのは選定ルールの差だけにするため)。後から入れ替えない。
 - 指標・期間・データ補正は phase5_validation.py と同一(756/252営業日、固定重み日次リバランス、
   1306.T の未調整分割を2026-03-30以降×10補正、TOPIX代理=1306.T、日経=^N225)。
出力: control_comparison.json / assets/cum3y_series.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"

pool = pd.read_csv(ROOT / "outputs/phase1_top5/phase1_top5_candidate_pool.csv")
pool["code"] = pool["code"].astype(str).str.zfill(4)

# 対照群20社: プール順のまま、同一業種は2社まで(Top5と同じ原則)
sector_count: dict = {}
control_codes, control_rows = [], []
for _, r in pool.iterrows():
    sec = r["sector"]
    if sector_count.get(sec, 0) >= 2:
        continue
    sector_count[sec] = sector_count.get(sec, 0) + 1
    control_codes.append(r["code"])
    control_rows.append({"code": r["code"], "name": r["company_name"], "sector": sec})
    if len(control_codes) == 20:
        break
assert len(control_codes) == 20, f"control only {len(control_codes)}"
top5 = list(pd.read_csv(ROOT / "outputs/phase1_top5/phase1_buffett_core_top5.csv")["code"].astype(str).str.zfill(4))
assert control_codes[:5] == top5, f"lineage mismatch: {control_codes[:5]} vs {top5}"

alloc = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
alloc["code_n"] = alloc["code_n"].astype(str).str.zfill(4)
alloc["ticker"] = alloc["code_n"] + ".T"
w_ours = alloc.set_index("ticker")["target_weight_final"]

ctrl_tickers = [c + ".T" for c in control_codes]
w_ctrl = pd.Series(1.0 / 20, index=ctrl_tickers)

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                     columns=["date", "ticker", "adj_close"])
need = set(w_ours.index) | set(ctrl_tickers) | {"1306.T", "^N225"}
px = px[px["ticker"].isin(need)]
wide = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
missing = sorted(need - set(wide.columns))
print("price coverage: need", len(need), "have", len(need) - len(missing), "missing:", missing)
assert not missing, "missing price series"

for t, (d0, factor) in {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}.items():
    wide.loc[wide.index >= d0, t] = wide.loc[wide.index >= d0, t] * factor

ret = wide.pct_change()
ANN = 252


def stats_for(window, w):
    r = ret.tail(window)
    rp = (r[w.index] * w.values).sum(axis=1)
    rb = r["1306.T"]; rn = r["^N225"]
    ann_ret = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    mdd = lambda x: float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN))
    beta = float(rp.cov(rb) / rb.var())
    te = float((rp - rb).std() * np.sqrt(ANN))
    ir = float((rp - rb).mean() * ANN / te) if te > 0 else float("nan")
    return {
        "ann_return": round(ann_ret(rp), 4), "topix_ann_return": round(ann_ret(rb), 4),
        "nikkei_ann_return": round(ann_ret(rn), 4), "excess_vs_topix": round(ann_ret(rp) - ann_ret(rb), 4),
        "volatility": round(vol, 4), "max_drawdown": round(mdd(rp), 4),
        "topix_max_drawdown": round(mdd(rb), 4), "beta_vs_topix": round(beta, 3),
        "information_ratio": round(ir, 3),
    }, rp


res = {}
series = {}
for name, w in [("ours", w_ours), ("control", w_ctrl)]:
    res[name] = {}
    for wname, win in [("3y", 756), ("1y", 252)]:
        st, rp = stats_for(win, w)
        res[name][wname] = st
        if wname == "3y":
            series[name] = rp

# 3年の累積系列(図用)
r3 = ret.tail(756)
cum = pd.DataFrame({
    "ours": (1 + series["ours"]).cumprod(),
    "control": (1 + series["control"]).cumprod(),
    "topix": (1 + r3["1306.T"]).cumprod(),
    "nikkei": (1 + r3["^N225"]).cumprod(),
})
cum.index.name = "date"
cum.to_csv(ED / "assets/cum3y_series.csv")

res["control_members"] = control_rows
res["method"] = ("control=phase1固定順プール(本PFのBuffett Coreと同一系譜)上位から業種2社上限で20社・等金額。"
                 "指標/期間/補正はphase5_validation.pyと同一。")
json.dump(res, open(ED / "control_comparison.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("ours", "control")}, ensure_ascii=False, indent=1))
print("phase5 summaryとの突合(ours 3y):")
p5 = json.load(open(OUT / "phase5_verification_and_ablation/phase5_validation_summary.json"))
print(" phase5:", p5["window_3y"]["port_ann_return"], "| now:", res["ours"]["3y"]["ann_return"])
