# -*- coding: utf-8 -*-
"""v5 統合検証スクリプト(WP0.1 + 0.2 + 0.3 の単一正典)。

v4からの是正:
 - WP0.1 指数系列の欠測補完: 1306.T は 2025-10-24(通常営業日)が源データparquetで欠測。
   v4の pct_change(fill_method=None) 経路では欠測前後2日がNaN化し +2.29% の値動きが
   累積から脱落 → TOPIX年率が過小(3y 0.2406 / 1y 0.4066)。本スクリプトは価格を前方補完
   してから version 非依存の pct_change(fill_method=None) を用い、脱落を防ぐ。
   構成銘柄(本PF・対照群)には内部欠測が無いことを assert し、補完は指数系列のみに限定・記録。
 - WP0.2 バイ&ホールド(株数固定)系列も併算(運用実態=株数固定に対応する規約)。
 - WP0.3 有意性: 対対照群・対TOPIX の日次超過リターンの t 値(素・Newey-West)を出力。

規律: 期間・分割補正・指標定義は phase5_validation.py / make_control_comparison.py と同一。
出力(すべて v5 名前空間。v4期ファイルは不可侵):
  control_comparison_v5.json / bh_metrics_v5.json / significance_v5.json / assets/cum3y_series_v5.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
ANN = 252

# --- portfolio (ours) weights ---
alloc = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
alloc["code_n"] = alloc["code_n"].astype(str).str.zfill(4)
alloc["ticker"] = alloc["code_n"] + ".T"
w_ours = alloc.set_index("ticker")["target_weight_final"]

# --- control (pure Buffett) 20 names: same lineage, sector<=2, equal weight ---
pool = pd.read_csv(ROOT / "outputs/phase1_top5/phase1_top5_candidate_pool.csv")
pool["code"] = pool["code"].astype(str).str.zfill(4)
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
assert len(control_codes) == 20
top5 = list(pd.read_csv(ROOT / "outputs/phase1_top5/phase1_buffett_core_top5.csv")["code"].astype(str).str.zfill(4))
assert control_codes[:5] == top5, f"lineage mismatch: {control_codes[:5]} vs {top5}"
ctrl_tickers = [c + ".T" for c in control_codes]
w_ctrl = pd.Series(1.0 / 20, index=ctrl_tickers)

# --- prices ---
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                     columns=["date", "ticker", "adj_close"])
need = set(w_ours.index) | set(ctrl_tickers) | {"1306.T", "^N225"}
px = px[px["ticker"].isin(need)]
wide = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
wide.index = pd.to_datetime(wide.index)
missing = sorted(need - set(wide.columns))
assert not missing, f"missing price series: {missing}"

# split fix (1306.T unadjusted 1:10 on 2026-03-30)
SPLIT = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
for t, (d0, factor) in SPLIT.items():
    wide.loc[wide.index >= d0, t] = wide.loc[wide.index >= d0, t] * factor

# WP0.1 gap repair --------------------------------------------------------
INDEX_TICKERS = {"1306.T", "^N225"}
interior = wide.isna() & wide.ffill().notna() & wide.bfill().notna()
for t in wide.columns:
    if t in INDEX_TICKERS:
        continue
    assert not interior[t].any(), (
        f"interior price gap in constituent {t} on "
        f"{[str(d.date()) for d in wide.index[interior[t]]]}: fix upstream, do not silently fill")
gap_repair = {t: [str(d.date()) for d in wide.index[interior[t]]]
              for t in INDEX_TICKERS if interior[t].any()}
print("[WP0.1 gap repair] index-series forward-filled:", gap_repair)
wide = wide.ffill()
ret = wide.pct_change(fill_method=None)  # version-independent; interior gaps already filled


def ann_ret(x):
    x = x.dropna()
    return float((1 + x).prod() ** (ANN / len(x)) - 1)


def mdd(x):
    c = (1 + x.dropna()).cumprod()
    return float((c / c.cummax() - 1).min())


def metrics(window, w):
    """daily-rebalanced fixed-weight (v4 regime)."""
    r = ret.tail(window)
    rp = (r[w.index] * w.values).sum(axis=1)
    rb, rn = r["1306.T"], r["^N225"]
    vol = float(rp.std() * np.sqrt(ANN))
    beta = float(rp.cov(rb) / rb.var())
    te = float((rp - rb).std() * np.sqrt(ANN))
    ir = float((rp - rb).mean() * ANN / te) if te > 0 else float("nan")
    return {
        "ann_return": round(ann_ret(rp), 4), "topix_ann_return": round(ann_ret(rb), 4),
        "nikkei_ann_return": round(ann_ret(rn), 4),
        "excess_vs_topix": round(ann_ret(rp) - ann_ret(rb), 4),
        "volatility": round(vol, 4), "max_drawdown": round(mdd(rp), 4),
        "topix_max_drawdown": round(mdd(rb), 4), "beta_vs_topix": round(beta, 3),
        "information_ratio": round(ir, 3),
    }, rp


def bh_metrics(window, w):
    """WP0.2 buy-and-hold (fixed shares from window start; weights drift)."""
    p = wide.tail(window)[w.index]
    norm = p / p.iloc[0]
    V = (norm * w.values).sum(axis=1)
    rp = V.pct_change().dropna()
    rb = ret.tail(window)["1306.T"]
    return {
        "ann_return": round(ann_ret(rp), 4),
        "excess_vs_topix": round(ann_ret(rp) - ann_ret(rb), 4),
        "volatility": round(float(rp.std() * np.sqrt(ANN)), 4),
        "max_drawdown": round(mdd(rp), 4),
    }


def nw_tstat(x, lag=None):
    """Newey-West t-stat of mean(x)=0 for a daily series x."""
    x = x.dropna().values
    n = len(x)
    mu = x.mean()
    e = x - mu
    if lag is None:
        lag = int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    gamma0 = (e @ e) / n
    var = gamma0
    for L in range(1, lag + 1):
        w_b = 1.0 - L / (lag + 1.0)
        cov = (e[L:] @ e[:-L]) / n
        var += 2 * w_b * cov
    se = np.sqrt(var / n)
    return {"mean_daily": float(mu), "ann_excess": float(mu * ANN),
            "t_plain": float(mu / (x.std(ddof=1) / np.sqrt(n))),
            "t_newey_west": float(mu / se), "nobs": int(n), "nw_lag": int(lag)}


# --- compute all ---
res = {"ours": {}, "control": {}}
series = {}
for name, w in [("ours", w_ours), ("control", w_ctrl)]:
    for wn, win in [("3y", 756), ("1y", 252)]:
        st, rp = metrics(win, w)
        res[name][wn] = st
        if wn == "3y":
            series[name] = rp

bh = {"ours": {}, "control": {}}
for name, w in [("ours", w_ours), ("control", w_ctrl)]:
    for wn, win in [("3y", 756), ("1y", 252)]:
        bh[name][wn] = bh_metrics(win, w)

# significance: daily excess of ours over control and over TOPIX
sig = {}
for wn, win in [("3y", 756), ("1y", 252)]:
    r = ret.tail(win)
    rp_o = (r[w_ours.index] * w_ours.values).sum(axis=1)
    rp_c = (r[w_ctrl.index] * w_ctrl.values).sum(axis=1)
    rb = r["1306.T"]
    sig[wn] = {
        "ours_vs_control": nw_tstat(rp_o - rp_c),
        "ours_vs_topix": nw_tstat(rp_o - rb),
    }

# cumulative 3y series for the figure
r3 = ret.tail(756)
cum = pd.DataFrame({
    "ours": (1 + series["ours"]).cumprod(),
    "control": (1 + series["control"]).cumprod(),
    "topix": (1 + r3["1306.T"]).cumprod(),
    "nikkei": (1 + r3["^N225"]).cumprod(),
})
cum.index.name = "date"
cum.to_csv(ED / "assets/cum3y_series_v5.csv")

res["control_members"] = control_rows
res["gap_repair"] = gap_repair
res["method"] = ("control=phase1固定順プール(本PFのBuffett Coreと同一系譜)上位から業種2社上限で20社・等金額。"
                 "指標/期間/補正はphase5と同一。WP0.1: 指数系列の欠測(1306.T 2025-10-24)を前方補完し、"
                 "version非依存のpct_change(fill_method=None)で算出。")
json.dump(res, open(ED / "control_comparison_v5.json", "w"), ensure_ascii=False, indent=1)
json.dump({"framing": "buy-and-hold (fixed shares) — matches the stated holding policy; "
                       "daily-rebalanced figures are in control_comparison_v5.json",
           "ours": bh["ours"], "control": bh["control"]},
          open(ED / "bh_metrics_v5.json", "w"), ensure_ascii=False, indent=1)
json.dump({"note": "daily excess-return t-stats. Multiple-testing context: 16-way ablation etc. "
                   "argues for cautious reading (White 2000; Romano-Wolf 2005).",
           **sig}, open(ED / "significance_v5.json", "w"), ensure_ascii=False, indent=1)

# --- diff vs committed v4 JSON ---
v4 = json.load(open(ED / "control_comparison.json"))
print("\n=== v4 -> v5 diff (key metrics) ===")
for name in ("ours", "control"):
    for wn in ("3y", "1y"):
        for k in ("ann_return", "topix_ann_return", "excess_vs_topix", "beta_vs_topix",
                  "max_drawdown", "information_ratio"):
            a, b = v4[name][wn].get(k), res[name][wn].get(k)
            flag = "" if a == b else "  <-- CHANGED"
            if flag:
                print(f"{name}.{wn}.{k}: {a} -> {b}{flag}")
print("\nBH (WP0.2):", json.dumps(bh, ensure_ascii=False))
print("\nSignificance (WP0.3):")
for wn in ("3y", "1y"):
    for comp in ("ours_vs_control", "ours_vs_topix"):
        s = sig[wn][comp]
        print(f"  {wn} {comp}: ann_excess={s['ann_excess']:.4f} "
              f"t_plain={s['t_plain']:.2f} t_NW={s['t_newey_west']:.2f} (lag {s['nw_lag']}, n={s['nobs']})")
