#!/usr/bin/env python
"""Monochrome (grayscale) figures for the student-prize (academic) report.
Print-safe: grays + hatching + line styles, no color."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/final_revision/final_figures")
OUT.mkdir(parents=True, exist_ok=True)
DK = "0.25"; MD = "0.55"; LT = "0.85"; LT2 = "0.92"


def rbox(ax, x, y, w, h, text, fc, ec="black", fs=8, tc="black", bold=False, lw=1.1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal")


def arrow(ax, x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=13, lw=1.2, color="black"))


def save(fig, name):
    fig.savefig(OUT / name, dpi=220, facecolor="white", bbox_inches="tight"); plt.close(fig)


# --- 研究全体の流れ（守・破・離） ---
fig, ax = plt.subplots(figsize=(9, 2.9)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.2); ax.axis("off")
stages = [(0.1, "守（Phase1）", "完成された Moat\n先行研究式で抽出\nTop5 を固定", LT2),
          (2.05, "破（Phase2）", "候補宇宙の形成\n式不変で閾値最適化\nTop1200", LT),
          (4.0, "離（Phase3）", "変わる／生まれる\nMoat を測定\nFinal20", MD),
          (5.95, "配分（Phase4）", "役割予算×\nリスク調整", LT),
          (7.9, "検証（Phase5）", "in-sample の\nリスク特性確認", LT2)]
for x, t, b, fc in stages:
    rbox(ax, x, 1.55, 1.75, 1.25, t, fc, fs=10, bold=True, tc="white" if fc == MD else "black")
    rbox(ax, x, 0.2, 1.75, 1.15, b, "white", fs=7.3)
    if x > 0.1:
        arrow(ax, x - 0.28, 2.15, x + 0.02, 2.15)
save(fig, "kenkyu_flow.png")

# --- Phase1 段階的スクリーニング（ファネル・全段階） ---
funnel = [("東証上場・非金融普通株", 3099), ("B/M・E/P 算出可能", 2740),
          ("Value 条件通過", 583), ("Piotroski 通過", 146),
          ("Sloan 通過", 112), ("Distress 通過", 90),
          ("流動性通過", 77), ("Buffett Core Top5", 5)]
fig, ax = plt.subplots(figsize=(8.6, 4.3)); ax.axis("off")
ax.set_xlim(0, 10); ax.set_ylim(0, len(funnel) + 0.5)
maxlog = np.log10(3099)
for i, (lab, n) in enumerate(funnel):
    y = len(funnel) - i
    w = 1.2 + 7.0 * (np.log10(n) / maxlog)
    x0 = (10 - w) / 2
    last = i == len(funnel) - 1
    ax.add_patch(plt.Rectangle((x0, y - 0.42), w, 0.72, facecolor=(DK if last else (LT if i % 2 else LT2)),
                               edgecolor="black", lw=1.4 if last else 1.0))
    ax.text(5, y - 0.06, f"{lab}　n = {n:,}", ha="center", va="center",
            fontsize=8.2, color="white" if last else "black", fontweight="bold" if last else "normal")
    if i:
        ax.annotate("", xy=(5, y + 0.30), xytext=(5, y + 0.58), arrowprops=dict(arrowstyle="-|>", color="0.4", lw=1))
save(fig, "phase1_funnel.png")

# --- Moat の時間軸拡張 ---
fig, ax = plt.subplots(figsize=(9, 3.0)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.2); ax.axis("off")
ax.annotate("", xy=(9.7, 0.5), xytext=(0.3, 0.5), arrowprops=dict(arrowstyle="-|>", color="black", lw=1.3))
ax.text(9.7, 0.24, "時間軸", ha="right", fontsize=9)
gens = [(0.4, "完成された Moat", "Buffett Core 5\n（Phase1 Top5 固定）\nValue×Quality", LT2),
        (3.5, "変わる Moat", "Transformation 5\n資本効率改善・株主還元\n＝低 PBR ではない", LT),
        (6.6, "生まれる Moat", "Emerging 5\nAI 基盤・半導体・光通信\n＝AI キーワードではない", MD)]
for x, t, b, fc in gens:
    rbox(ax, x, 1.6, 2.8, 1.0, t, fc, fs=10.5, bold=True, tc="white" if fc == MD else "black")
    rbox(ax, x, 0.72, 2.8, 0.8, b, "white", fs=7.4)
    ax.annotate("", xy=(x + 1.4, 0.7), xytext=(x + 1.4, 0.55), arrowprops=dict(arrowstyle="-|>", color="0.4", lw=1))
ax.text(5.0, 3.05, "（＋ Dual Moat 3・Bridge / Diversifier 2）", ha="center", fontsize=8, style="italic")
save(fig, "moat_timeaxis.png")

print("wrote kenkyu_flow / phase1_funnel / moat_timeaxis (grayscale) to", OUT)
