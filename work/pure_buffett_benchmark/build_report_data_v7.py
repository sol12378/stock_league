# -*- coding: utf-8 -*-
"""V7 レポート用データ層: 3年/1年の比較指標＋Newey-West有意性。
対照= 真バフェットTop12(主対照) / 純正グレアム20(参考・旧式) / TOPIX / 日経。
規約: 買い持ち(BH・株数固定)で統一(多期間"超える"検証と同一)。phase5計測(1306×10・fill_method=None)。
出力: control_comparison_v7.json / significance_v7.json
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
W3Y, W1Y = 756, 252

pf = json.load(open(WORK / "portfolio_v7.json"))
w_v7 = pf["weights_v7"]                       # V7 提出PF(役割予算)
buf12 = pf["buf12"]                            # 真バフェットTop12

# 純正グレアム20(旧式・参考): phase1固定順プール上位・同一業種2社まで・等金額
pool = pd.read_csv(ROOT / "outputs/phase1_top5/phase1_top5_candidate_pool.csv")
pool["code"] = pool["code"].astype(str).str.zfill(4)
sc, gcodes = {}, []
for _, r in pool.iterrows():
    if sc.get(r["sector"], 0) >= 2: continue
    sc[r["sector"]] = sc.get(r["sector"], 0) + 1; gcodes.append(r["code"])
    if len(gcodes) == 20: break

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
first_valid = px.dropna(subset=["adj_close"]).groupby("ticker")["date"].min()
last_px = px.sort_values("date").groupby("ticker")["adj_close"].last()

# weights per basket
w_graham = {c + ".T": 1 / 20 for c in gcodes}
# buffett12 cap-weight(上限25%)
import pandas as _pd
sc_e = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
sc_e["code"] = sc_e["code"].str.zfill(4); sc_e["ticker"] = sc_e["code"] + ".T"
sc_e["sh"] = pd.to_numeric(sc_e["shares_outstanding"], errors="coerce")
sc_e["mc"] = sc_e.ticker.map(last_px) * sc_e.sh
mc = sc_e.set_index("code").loc[buf12, "mc"]; wcap = (mc / mc.sum()).clip(upper=0.25); wcap /= wcap.sum()
w_buf = {c + ".T": float(wcap[c]) for c in buf12}

need = set(w_v7) | set(w_buf) | set(w_graham) | {"1306.T", "^N225"}
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] *= f

def bh_daily(weights, window):
    tks = [t for t in weights if t in wide.columns]
    sub = wide[tks].tail(window).ffill()
    ok = [t for t in tks if sub[t].notna().sum() >= window - 2]
    w = pd.Series({t: weights[t] for t in ok}); w /= w.sum()
    sub = wide[list(w.index)].tail(window).ffill().dropna()
    shares = w / sub.iloc[0]
    return (sub * shares).sum(axis=1).pct_change(fill_method=None).dropna()

def rebal_daily(weights, window):
    """固定重み日次リバランス(v5主規約・裁定2)。"""
    tks = [t for t in weights if t in wide.columns]
    sub = wide[tks].tail(window).ffill()
    ok = [t for t in tks if sub[t].notna().sum() >= window - 2]
    w = pd.Series({t: weights[t] for t in ok}); w /= w.sum()
    r = wide[list(w.index)].tail(window).ffill().pct_change(fill_method=None).dropna()
    return (r[w.index] * w.values).sum(axis=1)

def idx_daily(t, window):
    return wide[t].tail(window).pct_change(fill_method=None).dropna()

def block(rp, rb, rn):
    rb = rb.reindex(rp.index); rn = rn.reindex(rp.index)
    ar = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    mdd = lambda x: float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); a = ar(rp)
    te = float((rp - rb).std() * np.sqrt(ANN))
    return {"ann_return": round(a, 4), "topix_ann_return": round(ar(rb), 4), "nikkei_ann_return": round(ar(rn), 4),
            "excess_vs_topix": round(a - ar(rb), 4), "volatility": round(vol, 4), "sharpe": round(a / vol, 3),
            "max_drawdown": round(mdd(rp), 4), "topix_max_drawdown": round(mdd(rb), 4),
            "beta_vs_topix": round(float(rp.cov(rb) / rb.var()), 3),
            "information_ratio": round(float((rp - rb).mean() * ANN / te), 3) if te > 0 else None}

def nw_t(x):
    x = x.dropna().values; n = len(x)
    if n < 10: return None
    xbar = x.mean(); e = x - xbar
    L = int(np.floor(4 * (n / 100) ** (2 / 9)))
    g0 = (e @ e) / n; lrv = g0
    for j in range(1, L + 1):
        gj = (e[j:] @ e[:-j]) / n; lrv += 2 * (1 - j / (L + 1)) * gj
    se = np.sqrt(lrv / n)
    return {"mean_excess_ann": round(float(xbar * ANN), 4), "t_plain": round(float(xbar / (x.std(ddof=1) / np.sqrt(n))), 2),
            "t_newey_west": round(float(xbar / se), 2), "nw_lag": L, "n": n}

COMP, SIG = {"ours": {}, "control_buffett": {}, "control_graham": {}}, {}
BH = {"ours": {}, "control_buffett": {}, "control_graham": {}}  # 参考(補遺)
for wn, win in [("3y", W3Y), ("1y", W1Y)]:
    rb, rn = idx_daily("1306.T", win), idx_daily("^N225", win)
    # 主規約=固定重み日次リバランス(v5裁定2・保守的)
    r_ours, r_buf, r_gra = rebal_daily(w_v7, win), rebal_daily(w_buf, win), rebal_daily(w_graham, win)
    COMP["ours"][wn] = block(r_ours, rb, rn)
    COMP["control_buffett"][wn] = block(r_buf, rb, rn)
    COMP["control_graham"][wn] = block(r_gra, rb, rn)
    idx = r_ours.index
    SIG[wn] = {"ours_vs_buffett": nw_t((r_ours - r_buf.reindex(idx))),
               "ours_vs_graham": nw_t((r_ours - r_gra.reindex(idx))),
               "ours_vs_topix": nw_t((r_ours - rb.reindex(idx)))}
    # 参考=BH(買い持ち)
    for nm, wt in [("ours", w_v7), ("control_buffett", w_buf), ("control_graham", w_graham)]:
        rp = bh_daily(wt, win); BH[nm][wn] = block(rp, rb, rn)

COMP["convention"] = "主規約=固定重み日次リバランス(v5裁定2・保守的)。BHは極端な複利で1年155%等のin-sample人工物になりやすいため参考(bh_reference)に降格。"
COMP["bh_reference"] = BH
COMP["method"] = "3y=756/1y=252営業日。1306.T×10補正(2026-03-30〜)。pct_change(fill_method=None)。TOPIX=1306.T・日経=^N225。"
COMP["baskets"] = {"ours_v7_rolebudget": list(w_v7), "control_buffett_top12": buf12, "control_graham20": gcodes}
json.dump(COMP, open(ED / "control_comparison_v7.json", "w"), ensure_ascii=False, indent=1)
json.dump(SIG, open(ED / "significance_v7.json", "w"), ensure_ascii=False, indent=1)

def show(tag, d):
    print(f'  {tag:22} 年率{d["ann_return"]*100:6.1f}% 対TOPIX{d["excess_vs_topix"]*100:+5.1f}pt σ{d["volatility"]*100:4.1f}% MDD{d["max_drawdown"]*100:6.1f}% β{d["beta_vs_topix"]:.2f} Sharpe{d["sharpe"]:.2f} IR{d["information_ratio"]:+.2f}')
for wn in ["3y", "1y"]:
    print(f'\n=== {wn} (TOPIX {COMP["ours"][wn]["topix_ann_return"]*100:.1f}% / 日経 {COMP["ours"][wn]["nikkei_ann_return"]*100:.1f}%) ===')
    show("V7提出PF(離)", COMP["ours"][wn]); show("真バフェットTop12", COMP["control_buffett"][wn]); show("純正グレアム20(参考)", COMP["control_graham"][wn])
    s = SIG[wn]
    print(f'  有意性(日次超過NW-t): vs真バフェット t={s["ours_vs_buffett"]["t_newey_west"]} / vsグレアム t={s["ours_vs_graham"]["t_newey_west"]} / vsTOPIX t={s["ours_vs_topix"]["t_newey_west"]}')
print("\nwritten -> control_comparison_v7.json / significance_v7.json")
