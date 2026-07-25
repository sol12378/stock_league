# -*- coding: utf-8 -*-
"""図表Ⅲ-2 累積リターン(3年)。v10: 主対照=新バフェット型20社(期首加重)、参考=同(期末加重)。
図内タイトルは入れない(番号はキャプションに一元化)。凡例は「本ＰＦ(20社)」。"""
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Hiragino Sans"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
SPLIT = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
C = json.load(open(ED / "control_comparison_v10.json"))
W = C["weights"]

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
need = set(W["ours"]) | set(W["graham20"]) | set(W["buf20_start3y"]) | {"1306.T", "^N225"}
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f
sub = wide.tail(756).ffill()


def rebal(w):
    ok = [t for t in w if t in sub.columns and sub[t].notna().sum() >= 754]
    ww = pd.Series({t: w[t] for t in ok})
    ww /= ww.sum()
    r = sub[list(ww.index)].pct_change(fill_method=None).dropna()
    return (1 + (r * ww.values).sum(axis=1)).cumprod()


lines = {
    "本ＰＦ（20社）": (rebal(W["ours"]), "#c0392b", 3.0, "-"),
    "新バフェット型・期首加重（主対照）": (rebal(W["buf20_start3y"]), "#e67e22", 2.0, "--"),
    "新バフェット型・期末加重（参考）": (rebal(W["buf20_end"]), "#8e44ad", 1.8, (0, (5, 1, 1, 1))),
    "純正グレアム型（参考）": (rebal(W["graham20"]), "#16a085", 1.8, "-."),
    "ＴＯＰＩＸ": ((1 + sub["1306.T"].pct_change(fill_method=None)).cumprod().dropna(), "#7f8c8d", 1.8, ":"),
    "日経平均": ((1 + sub["^N225"].pct_change(fill_method=None)).cumprod().dropna(), "#aaaaaa", 1.5, ":"),
}
fig, ax = plt.subplots(figsize=(9, 5.2))
idx0 = lines["ＴＯＰＩＸ"][0].index
for k, (v, c, lw, ls) in lines.items():
    v = (v / v.iloc[0]).reindex(idx0).ffill()
    ax.plot(v.index, v.values, label=f"{k}（×{v.iloc[-1]:.2f}）", color=c, lw=lw, ls=ls)
ax.set_ylabel("累積（期首=1.0）")
ax.legend(fontsize=9, loc="upper left")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(ED / "assets/cum_v10.png", dpi=150)
plt.close(fig)
print("written -> assets/cum_v10.png",
      {k: round(float((v[0] / v[0].iloc[0]).iloc[-1]), 2) for k, v in lines.items()})
