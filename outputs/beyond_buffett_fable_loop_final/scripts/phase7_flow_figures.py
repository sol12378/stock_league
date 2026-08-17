#!/usr/bin/env python
"""Redraw the three phase flow diagrams (守/破/離) as clean HORIZONTAL,
page-fitting figures, replacing the tall top-down mermaid renders that
overflowed. Unified teal / Hiragino style, monochrome-safe."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/beyond_buffett_fable_loop_final")
DIRS = [OUT / "phase7_final_report/final_figures", OUT / "figures"]
TEAL = "#2F6D5F"; TEAL2 = "#5E9B8C"; LT = "#DCE8E4"; LT2 = "#EAF1EE"


def save(fig, name):
    for d in DIRS:
        fig.savefig(d / name, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def rbox(ax, x, y, w, h, text, fc, ec="black", fs=8, tc="black", bold=False, lw=1.1, dash=None):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                       fc=fc, ec=ec, lw=lw)
    if dash:
        p.set_linestyle((0, dash))
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal")


def arrow(ax, x0, y0, x1, y1, color="black"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.2, color=color))


# ---- 守: screening cascade (log-scaled horizontal funnel) -----------------
stages = [("全対象\n非金融普通株", 3099), ("Value\nB/M・E/P", 2740),
          ("Quality\nGP", 583), ("財務健全性\nPiotroski", 146),
          ("利益の質\nSloan", 112), ("Distress\nガードレール", 90),
          ("流動性", 77), ("Buffett Core\nTop5", 5)]
fig, ax = plt.subplots(figsize=(9.2, 3.4))
ax.set_xlim(0, len(stages)); ax.set_ylim(0, 1); ax.axis("off")
maxlog = np.log10(3099)
for i, (lab, n) in enumerate(stages):
    hh = 0.25 + 0.55 * (np.log10(n) / maxlog)      # bar height ∝ log(n)
    y = 0.5 - hh / 2
    last = i == len(stages) - 1
    rbox(ax, i + 0.08, y, 0.84, hh, f"{lab}\nn = {n:,}",
         fc=TEAL if last else (LT if i % 2 else LT2),
         tc="white" if last else "black", fs=7.2, bold=last,
         lw=1.6 if last else 1.1)
    if i:
        arrow(ax, i - 0.02, 0.5, i + 0.06, 0.5, color=TEAL)
ax.text(len(stages) / 2, 0.99, "守：段階的スクリーニング（先行研究式は不変、n の推移）",
        ha="center", va="top", fontsize=9.5, fontweight="bold", color=TEAL)
save(fig, "phase1_flow.png")

# ---- 破: candidate-universe formation --------------------------------------
fig, ax = plt.subplots(figsize=(9.2, 3.4))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
rbox(ax, 0.2, 3.4, 3.0, 3.2,
     "式は不変\n使い方を最適化\n\n重み・ペナルティ\nTopN・業種調整\n欠損処理\n（ランダムサーチ）",
     fc=LT2, fs=8)
arrow(ax, 3.2, 5.0, 4.0, 5.0, color=TEAL)
# nested universe bands
bands = [("Top2000（参照群）", 4.0, 9.7, 1.2, 8.8, "#FFFFFF", "#999999", (0, (4, 3))),
         ("Top1200（正式母集団）", 4.4, 9.3, 2.4, 7.6, LT, TEAL, None),
         ("Top300", 4.9, 8.3, 3.6, 6.4, TEAL2, "black", None),
         ("Top100", 5.4, 7.0, 4.6, 5.2, TEAL, "black", None)]
for lab, x0, x1, y0, y1, fc, ec, dash in bands:
    p = FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0.02,rounding_size=0.06",
                       fc=fc, ec=ec, lw=1.6 if "1200" in lab else 1.1)
    if dash:
        p.set_linestyle(dash)
    ax.add_patch(p)
    tc = "white" if lab == "Top100" else (TEAL if "1200" in lab else "black")
    ax.text((x0 + x1) / 2, y1 - 0.45, lab, ha="center", va="center",
            fontsize=8.2, color=tc, fontweight="bold" if "1200" in lab else "normal")
ax.text(5.0, 1.5, "Phase1 Top5 カバレッジ 5/5・HHI 0.0707・最大業種 11.6%", ha="center", fontsize=7.6, color=TEAL)
ax.text(5.0, 0.8, "※ Phase2 スコアは最終スコアに使わない（離へ候補＋確認フラグを引き渡し）", ha="center", fontsize=7.6)
ax.text(5.0, 9.99, "破：候補宇宙の形成（Top1200 を正式母集団に採用）",
        ha="center", va="top", fontsize=9.5, fontweight="bold", color=TEAL)
save(fig, "phase2_flow.png")

# ---- 離: three-generation moat construction --------------------------------
fig, ax = plt.subplots(figsize=(9.2, 3.6))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
# left: two score axes + evidence
rbox(ax, 0.2, 6.3, 3.0, 2.6, "変わる Moat\nTransformation Score\n（式 II-12）", fc=LT, fs=8)
rbox(ax, 0.2, 3.3, 3.0, 2.6, "生まれる Moat\nEmerging Score\n（式 II-13）", fc=LT, fs=8)
rbox(ax, 0.2, 0.6, 3.0, 2.2, "Evidence Level\n5 系統に分離\n（式 II-14）", fc=LT2, fs=8)
# middle: roles
roles = [("Buffett Core 5\n（守 Top5 固定）", TEAL, "white"),
         ("Transformation Core 5", TEAL2, "white"),
         ("Emerging Core 5", TEAL2, "white"),
         ("Dual Moat 3", LT, "black"),
         ("Bridge / Diversifier 2", LT2, "black")]
for i, (lab, fc, tc) in enumerate(roles):
    y = 8.1 - i * 1.65
    rbox(ax, 4.2, y, 3.0, 1.35, lab, fc=fc, tc=tc, fs=7.8,
         bold=(i == 0), lw=1.6 if i == 0 else 1.1)
    arrow(ax, 3.2, 5.0, 4.15, y + 0.7, color=TEAL)
    arrow(ax, 7.2, y + 0.7, 8.0, 5.0, color=TEAL)
# right: final20
rbox(ax, 8.0, 3.7, 1.8, 2.6, "最終\n20 社\nFinal20", fc=TEAL, tc="white", fs=10, bold=True, lw=1.8)
ax.text(5.0, 9.99, "離：三世代 Moat の構築（Evidence Level で証拠を分離）",
        ha="center", va="top", fontsize=9.5, fontweight="bold", color=TEAL)
save(fig, "phase3_flow.png")

print("wrote phase1_flow / phase2_flow / phase3_flow (horizontal) to", [str(d) for d in DIRS])
