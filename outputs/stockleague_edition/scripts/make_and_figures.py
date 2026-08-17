# -*- coding: utf-8 -*-
"""AND スクリーニング解説資料の図(PDF)。すべて実測値から作る。"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False
HERE = Path(__file__).parent
FIG = HERE / "and_figures"; FIG.mkdir(exist_ok=True)
SLE = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/stockleague_edition")

FEAS = json.loads((SLE / "and_feasibility.json").read_text())
FRONT = json.loads((SLE / "and_frontier.json").read_text())
BT = json.loads((SLE / "and_backtest.json").read_text())

DK, MD, LT, LT2 = "0.22", "0.55", "0.80", "0.93"
ACC = "#1f4e79"; WARN = "#a33"


# ============================================================ F1 直列ふるい
fig, ax = plt.subplots(figsize=(7.4, 2.9)); ax.set_xlim(0, 10.4); ax.set_ylim(0, 3.4); ax.axis("off")
steps = FEAS["sequential_and_median_thresholds"]
labels = ["適格な会社\n(出発点)", "① 守る堀\nのふるい", "② 破る堀\nのふるい", "③ 離れる堀\nのふるい"]
ns = [steps[0]["n"], steps[1]["n"], steps[2]["n"], steps[3]["n"]]
x = 0.25
for i, (lab, n) in enumerate(zip(labels, ns)):
    w = 2.15
    fc = LT2 if i == 0 else LT
    ax.add_patch(FancyBboxPatch((x, 1.15), w, 1.5, boxstyle="round,pad=0.03,rounding_size=0.08",
                                fc=fc, ec="black", lw=1.0))
    ax.text(x + w / 2, 2.25, lab, ha="center", va="center", fontsize=9.5, fontweight="bold")
    ax.text(x + w / 2, 1.55, f"{n:,} 社", ha="center", va="center", fontsize=13, color=ACC,
            fontweight="bold")
    if i < 3:
        ax.add_patch(FancyArrowPatch((x + w + 0.03, 1.9), (x + w + 0.45, 1.9),
                                     arrowstyle="-|>", mutation_scale=13, lw=1.3, color="black"))
    x += w + 0.5
ax.text(5.2, 0.62, "社数だけを見れば 77 社。ここまでは「20社は取れそう」に見える。",
        ha="center", va="center", fontsize=9.5)
ax.text(5.2, 0.18, "取れないのは、この後に「同じ業種は2社まで」という分散のルールがあるから(図4)。",
        ha="center", va="center", fontsize=9.5, color=WARN)
fig.savefig(FIG / "f1_funnel.png", dpi=300, bbox_inches="tight"); plt.close(fig)


# ============================================================ F2 掛け算の壁
fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), gridspec_kw={"width_ratios": [1, 1.15]})
ax = axes[0]
qs = np.linspace(0.05, 0.60, 200); N = FRONT["N_base"]
ax.plot(qs * 100, N * qs, color=MD, lw=1.4, ls=":", label="ふるい1枚 ($Nq$)")
ax.plot(qs * 100, N * qs ** 2, color=MD, lw=1.4, ls="--", label="2枚重ね ($Nq^2$)")
ax.plot(qs * 100, N * qs ** 3, color=ACC, lw=2.0, label="3枚重ね ($Nq^3$)")
ax.axhline(20, color=WARN, lw=1.2)
ax.text(57, 24, "20社", color=WARN, fontsize=9, ha="right")
qn = FRONT["q_needed_for_20_indep"] * 100
ax.axvline(qn, color=WARN, lw=1.0, ls="-.")
ax.text(qn + 1.5, 700, f"上位{qn:.1f}%", color=WARN, fontsize=9)
ax.set_yscale("log"); ax.set_xlabel("各ふるいの厳しさ（上位何％を通すか）", fontsize=9)
ax.set_ylabel("残る会社数（対数）", fontsize=9)
ax.tick_params(labelsize=8); ax.legend(fontsize=7.5, loc="lower right", framealpha=0.9)
ax.grid(alpha=0.25, lw=0.5)
ax.set_title("3枚重ねると急激に減る", fontsize=10)

ax = axes[1]
g = pd.DataFrame(FRONT["frontier"])
g = g[g.pool_n > 0]
ax.plot(g.q_each_gate * 100, g.pool_n, "o-", color=ACC, lw=1.6, ms=4.5, label="実測（AND通過社数）")
ax.plot(g.q_each_gate * 100, g.naive_indep_expect, "s--", color=MD, lw=1.2, ms=3.5,
        label="独立なら（$Nq^3$）")
ax.axhline(20, color=WARN, lw=1.2); ax.text(48, 23, "20社", color=WARN, fontsize=9, ha="right")
ax.set_yscale("log"); ax.set_xlabel("各ふるいの厳しさ（上位何％）", fontsize=9)
ax.set_ylabel("AND を通った社数（対数）", fontsize=9)
ax.tick_params(labelsize=8); ax.legend(fontsize=7.5, loc="upper left", framealpha=0.9)
ax.grid(alpha=0.25, lw=0.5)
ax.set_title("実測も理屈どおりに減る", fontsize=10)
fig.tight_layout()
fig.savefig(FIG / "f2_multiply.png", dpi=300, bbox_inches="tight"); plt.close(fig)


# ============================================================ F3 エリートは別人
fig, ax = plt.subplots(figsize=(7.4, 2.5)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.2); ax.axis("off")
ov = FEAS.get("top20_overlap", FRONT["top20_overlap"])
cx = [2.4, 5.0, 7.6]; labs = ["守る堀\nTop20", "破る堀\nTop20", "離れる堀\nTop20"]
for x, lab in zip(cx, labs):
    ax.add_patch(Circle((x, 1.75), 1.15, fc=LT, ec="black", lw=1.1, alpha=0.75))
    ax.text(x, 1.75, lab, ha="center", va="center", fontsize=9.5, fontweight="bold")
pairs = [(3.7, "守∩破\n= 1社"), (6.3, "破∩離\n= 0社")]
for x, t in pairs:
    ax.text(x, 0.62, t, ha="center", va="center", fontsize=9, color=WARN, fontweight="bold")
ax.text(5.0, 3.0, "三層の「最優秀20社」は、ほとんど重ならない（守∩離も 0 社／3つ全部は 0 社）",
        ha="center", va="center", fontsize=9.5)
fig.savefig(FIG / "f3_overlap.png", dpi=300, bbox_inches="tight"); plt.close(fig)


# ============================================================ F4 業種の壁
fig, ax = plt.subplots(figsize=(7.4, 2.7))
g = pd.DataFrame(FRONT["frontier"]); g = g[g.pool_n > 0].copy()
xx = np.arange(len(g)); w = 0.27
ax.bar(xx - w, g.max20_cap2, w, color=ACC, label="同業種2社まで（現行の分散ルール）")
ax.bar(xx, g.max20_cap3, w, color=MD, label="3社まで")
ax.bar(xx + w, g.max20_cap4, w, color=LT, edgecolor="black", lw=0.5, label="4社まで")
ax.axhline(20, color=WARN, lw=1.4)
ax.text(-0.35, 21.0, "20社に届くライン", color=WARN, fontsize=9, ha="left")
ax.set_xticks(xx); ax.set_xticklabels([f"上位{int(q*100)}%" if q != 0.224 else "上位22%"
                                       for q in g.q_each_gate], fontsize=8)
ax.set_xlabel("各ふるいの厳しさ", fontsize=9)
ax.set_ylabel("組める最大社数", fontsize=9)
ax.tick_params(labelsize=8); ax.legend(fontsize=8, loc="center right", framealpha=0.95)
ax.grid(axis="y", alpha=0.25, lw=0.5); ax.set_ylim(0, 36)
ax.set_title("同業種2社までを守ると、どんなに緩めても最大16社（青）", fontsize=10)
fig.tight_layout(); fig.savefig(FIG / "f4_sector_ceiling.png", dpi=300, bbox_inches="tight"); plt.close(fig)


# ============================================================ F5 離ゲートは業種ラベル
ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def T(c): return s[c].astype(str).str.lower().isin(["true", "1", "1.0"])
s["future_moat_score"] = pd.to_numeric(s.future_moat_score, errors="coerce")
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
h = px.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum()); s["histd"] = s.ticker.map(h).fillna(0)
base = T("investment_eligible") & ~T("is_financial") & T("price_available") & T("liquid_20m_60d") & (s.histd >= 756)
B = s[base].copy()
B["pass"] = B.future_moat_score > B.future_moat_score.median()
JP = {"Precision Instruments": "精密機器", "Electric Appliances": "電気機器",
      "Electric Power and Gas": "電力・ガス", "Nonferrous Metals": "非鉄金属", "Chemicals": "化学",
      "Metal Products": "金属製品", "Machinery": "機械", "Information & Communication": "情報・通信",
      "Transportation Equipment": "輸送用機器", "Services": "サービス", "Real Estate": "不動産",
      "Retail Trade": "小売", "Textiles and Apparels": "繊維", "Other Products": "その他製品",
      "Land Transportation": "陸運", "Iron and Steel": "鉄鋼",
      "Glass and Ceramics Products": "ガラス・土石", "Foods": "食品", "Construction": "建設",
      "Wholesale Trade": "卸売"}
gg = B.groupby("sector_33")["pass"].agg(["mean", "size"])
gg = gg[gg["size"] >= 20].sort_values("mean", ascending=True)
gg.index = [JP.get(i, i) for i in gg.index]
fig, ax = plt.subplots(figsize=(7.4, 4.0))
cols = [ACC if v > 0.5 else LT for v in gg["mean"]]
ax.barh(range(len(gg)), gg["mean"] * 100, color=cols, edgecolor="black", lw=0.4)
ax.set_yticks(range(len(gg))); ax.set_yticklabels(gg.index, fontsize=8.5)
ax.set_xlabel("「離れる堀のふるい」の通過率（％）", fontsize=9)
ax.set_xlim(0, 118); ax.tick_params(labelsize=8); ax.grid(axis="x", alpha=0.25, lw=0.5)
for i, v in enumerate(gg["mean"] * 100):
    ax.text(v + 1.5, i, f"{v:.0f}%", va="center", fontsize=8,
            color=ACC if v > 50 else "0.35")
ax.set_title("通過率は 100％ か 0％ のどちらか — 会社ではなく業種を判定している", fontsize=10)
fig.tight_layout(); fig.savefig(FIG / "f5_sector_dummy.png", dpi=300, bbox_inches="tight"); plt.close(fig)


# ============================================================ F6 実際に組んで測った
full = BT["results"]["full_21-26"]
cur = full["現行20社 (役割予算=提出版)"]; a14 = full["A1c4_逐次AND_業種上限4 (等ウェイト)"]
d_cur = BT["designs"]["現行20社_役割分担"]; d_a14 = BT["designs"]["A1c4_逐次AND_業種上限4"]
metrics = [("年率リターン\n(％・高いほど良い)", cur["ann_return"] * 100, a14["ann_return"] * 100, "{:.1f}"),
           ("シャープ比率\n(効率・高いほど良い)", cur["sharpe"], a14["sharpe"], "{:.2f}"),
           ("最大下落率\n(％・浅いほど良い)", cur["max_drawdown"] * 100, a14["max_drawdown"] * 100, "{:.1f}"),
           ("業種の数\n(多いほど分散)", d_cur["n_sectors"], d_a14["n_sectors"], "{:.0f}")]
fig, axes = plt.subplots(1, 4, figsize=(7.4, 2.6))
for ax, (name, v1, v2, fmt) in zip(axes, metrics):
    bars = ax.bar([0, 1], [v1, v2], width=0.62, color=[ACC, LT], edgecolor="black", lw=0.6)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["現行\n20社", "AND\n20社"], fontsize=8.5)
    ax.set_title(name, fontsize=8.5)
    ax.tick_params(labelsize=8); ax.grid(axis="y", alpha=0.22, lw=0.5)
    for b, v in zip(bars, [v1, v2]):
        off = (max(abs(v1), abs(v2)) * 0.06) * (1 if v >= 0 else -1)
        ax.text(b.get_x() + b.get_width() / 2, v + off, fmt.format(v),
                ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5, fontweight="bold")
    lo = min(0, v1, v2); hi = max(0, v1, v2)
    ax.set_ylim(lo - abs(hi - lo) * 0.22, hi + abs(hi - lo) * 0.28)
fig.suptitle("AND で無理に20社を組むと、4つの物差しすべてで現行に届かない（2021年6月〜2026年6月）",
             fontsize=9.5, y=1.04)
fig.tight_layout(); fig.savefig(FIG / "f6_result.png", dpi=300, bbox_inches="tight"); plt.close(fig)

print("figures ->", FIG)
for p in sorted(FIG.glob("*.png")): print("  ", p.name)
