#!/usr/bin/env python
"""図表 II-1 スクリーニング全体像 — STOCK League 風の funnel（守→破→離）。
Hiragino Sans, print-friendly (teal monochrome-safe)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.family"] = "Hiragino Sans"
FIGDIR = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/beyond_buffett_fable_loop_final/phase7_final_report/final_figures")
TEAL = "#2F6D5F"; TEAL2 = "#5E9B8C"; LIGHT = "#DCE8E4"

fig, ax = plt.subplots(figsize=(9, 5.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

# funnel trapezoids for the 守 path (staged screening)
stages = [
    ("非金融普通株　3,099 社", 9.3, 8.2),
    ("Value×Quality 通過　583 社", 8.2, 7.1),
    ("Piotroski / Sloan / distress　90 社", 7.1, 6.0),
    ("流動性フィルタ　77 社", 6.0, 4.9),
]
for i, (label, ytop, ybot) in enumerate(stages):
    wt = 7.2 - i * 1.3
    wb = 7.2 - (i + 1) * 1.3
    cx = 3.4
    poly = Polygon([(cx - wt / 2, ytop), (cx + wt / 2, ytop),
                    (cx + wb / 2, ybot), (cx - wb / 2, ybot)],
                   closed=True, fc=LIGHT if i % 2 else "#EAF1EE", ec=TEAL, lw=1.2)
    ax.add_patch(poly)
    ax.text(cx, (ytop + ybot) / 2, label, ha="center", va="center", fontsize=8.5)

# 守 Top5 fixed box
ax.add_patch(FancyBboxPatch((1.3, 3.3), 4.2, 1.1, boxstyle="round,pad=0.03,rounding_size=0.08",
                            fc=TEAL, ec="black", lw=1.2))
ax.text(3.4, 3.85, "守：Buffett Core Top5（固定）", ha="center", va="center",
        fontsize=10, color="white", fontweight="bold")

# 破 universe box (parallel, right)
ax.add_patch(FancyBboxPatch((6.2, 6.0), 3.4, 2.4, boxstyle="round,pad=0.03,rounding_size=0.08",
                            fc="#EAF1EE", ec=TEAL, lw=1.2))
ax.text(7.9, 7.9, "破：式は不変、", ha="center", fontsize=9)
ax.text(7.9, 7.45, "閾値・分位・候補数を最適化", ha="center", fontsize=8.5)
ax.text(7.9, 6.9, "候補宇宙 Top1200", ha="center", fontsize=11, color=TEAL, fontweight="bold")
ax.text(7.9, 6.4, "（Top2000 は参照群）", ha="center", fontsize=7.5)

# arrow 破 -> 離
ax.add_patch(FancyArrowPatch((7.9, 6.0), (7.9, 5.0), arrowstyle="-|>", mutation_scale=16, lw=1.3, color=TEAL))

# 離 Final20 box
ax.add_patch(FancyBboxPatch((5.0, 3.0), 4.6, 2.0, boxstyle="round,pad=0.03,rounding_size=0.08",
                            fc=TEAL2, ec="black", lw=1.4))
ax.text(7.3, 4.55, "離：変わる Moat・生まれる Moat を測定", ha="center", fontsize=8.5, color="white")
ax.text(7.3, 3.95, "最終 20 社（Final20）", ha="center", fontsize=12, color="white", fontweight="bold")
ax.text(7.3, 3.4, "Buffett5＋Trans5＋Emerg5＋Dual3＋Bridge2", ha="center", fontsize=7.5, color="white")

# 守Top5 -> Final20 arrow (fixed carry)
ax.add_patch(FancyArrowPatch((5.5, 3.85), (6.2, 3.85), arrowstyle="-|>", mutation_scale=14, lw=1.3, color="black"))
ax.text(5.85, 4.15, "固定継承", ha="center", fontsize=7)

ax.text(5.0, 1.9, "守：完成された Moat（先行研究式を不変）", ha="center", fontsize=8, color=TEAL)
ax.text(5.0, 1.5, "破：候補宇宙の形成（式の使い方を最適化）", ha="center", fontsize=8, color=TEAL)
ax.text(5.0, 1.1, "離：三世代 Moat の構築（時間軸拡張）", ha="center", fontsize=8, color=TEAL)

fig.tight_layout()
fig.savefig(FIGDIR / "screening_funnel.png", dpi=200, facecolor="white", bbox_inches="tight")
print("wrote", FIGDIR / "screening_funnel.png")
