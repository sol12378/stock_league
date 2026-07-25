# -*- coding: utf-8 -*-
"""図表Ⅲ-7 累積リターン(3年・本PF/新バフェット/グレアム/TOPIX/日経)。固定重み日次リバランス(本編主規約)。"""
import json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Hiragino Sans"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"; WORK = ROOT / "work/pure_buffett_benchmark"
SPLIT = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
pf = json.load(open(WORK / "portfolio_v7.json")); w_v7 = pf["weights_v7"]; buf12 = pf["buf12"]
pool = pd.read_csv(ROOT / "outputs/phase1_top5/phase1_top5_candidate_pool.csv"); pool["code"] = pool["code"].astype(str).str.zfill(4)
sc, gc = {}, []
for _, r in pool.iterrows():
    if sc.get(r["sector"], 0) >= 2: continue
    sc[r["sector"]] = sc.get(r["sector"], 0) + 1; gc.append(r["code"])
    if len(gc) == 20: break
w_gra = {c + ".T": 1 / 20 for c in gc}
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False); s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
s["sh"] = pd.to_numeric(s["shares_outstanding"], errors="coerce")
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"]); px["date"] = pd.to_datetime(px["date"])
last = px.sort_values("date").groupby("ticker")["adj_close"].last()
mc = (s.set_index("code").loc[buf12, "ticker"].map(last) * s.set_index("code").loc[buf12, "sh"]); mc.index = buf12
wcap = (mc / mc.sum()).clip(upper=0.25); wcap /= wcap.sum(); w_buf = {c + ".T": float(wcap[c]) for c in buf12}
need = set(w_v7) | set(w_buf) | set(w_gra) | {"1306.T", "^N225"}
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] *= f
sub = wide.tail(756).ffill()
def rebal(w):
    ok = [t for t in w if t in sub.columns and sub[t].notna().sum() >= 750]
    ww = pd.Series({t: w[t] for t in ok}); ww /= ww.sum()
    r = sub[list(ww.index)].pct_change(fill_method=None).dropna()
    return (1 + (r * ww.values).sum(axis=1)).cumprod()
lines = {"本ＰＦ（離）": (rebal(w_v7), "#c0392b", 3.0, "-"),
         "新バフェット型": (rebal(w_buf), "#e67e22", 2.0, "--"),
         "純正グレアム型": (rebal(w_gra), "#16a085", 1.8, "-."),
         "ＴＯＰＩＸ": ((1 + sub["1306.T"].pct_change(fill_method=None)).cumprod().dropna(), "#7f8c8d", 1.8, ":"),
         "日経平均": ((1 + sub["^N225"].pct_change(fill_method=None)).cumprod().dropna(), "#aaaaaa", 1.5, ":")}
fig, ax = plt.subplots(figsize=(9, 5.2))
idx0 = lines["ＴＯＰＩＸ"][0].index
for k, (v, c, lw, ls) in lines.items():
    v = (v / v.iloc[0]).reindex(idx0).ffill()
    ax.plot(v.index, v.values, label=f"{k}（×{v.iloc[-1]:.2f}）", color=c, lw=lw, ls=ls)
ax.set_title("図表Ⅲ-7　累積リターンの比較（過去3年・期首=1）\n※2026年時点選定の自己検証。将来の成績予測ではない", fontsize=11)
ax.set_ylabel("累積（期首=1.0）"); ax.legend(fontsize=9, loc="upper left"); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(ED / "assets/cum_v7.png", dpi=150); plt.close(fig)
print("written -> assets/cum_v7.png  終値倍率:", {k: round(float((v[0] / v[0].iloc[0]).iloc[-1]), 2) for k, v in lines.items()})
