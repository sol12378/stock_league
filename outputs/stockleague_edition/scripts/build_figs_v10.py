# -*- coding: utf-8 -*-
"""v10 図版: 図内タイトルを削除(番号はキャプションに一元化)。三世代の堀の概念図と、合流図の2点を再生成。"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Hiragino Sans"
matplotlib.rcParams["axes.unicode_minus"] = False
import numpy as np

ED = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/stockleague_edition")
# ---- 図表Ⅰ-1 三世代の堀 コンセプト(v7・③-1: 上段細く/下段広く文字大) ----
fig, ax = plt.subplots(figsize=(9.2, 5.0)); ax.axis("off")
gens = [("完成した堀", "#16324F", "いま強みが完成\n（新バフェット品質）\n守：高ROE大型優良 5社"),
        ("変わる堀", "#2F6D5F", "東証改革でこれから強くなる\n（割安×変革）\n破：変わる堀 5社"),
        ("生まれる堀", "#5E9B8C", "AI・半導体の実需で新たに生まれる\n（事業で検証）\n離：生まれる堀 5社")]
xw = 0.30; gap = 0.035; x0 = 0.03
for i, (name, col, desc) in enumerate(gens):
    x = x0 + i * (xw + gap)
    ax.add_patch(plt.Rectangle((x, 0.80), xw, 0.10, color=col))          # 上段(細)
    ax.text(x + xw / 2, 0.85, name, ha="center", va="center", color="white", fontsize=13, fontweight="bold")
    ax.add_patch(plt.Rectangle((x, 0.34), xw, 0.42, facecolor="#EAF1EE", edgecolor=col, linewidth=2))  # 下段(広)
    ax.text(x + xw / 2, 0.55, desc, ha="center", va="center", fontsize=11, color="#222")
    ax.annotate("", xy=(x + xw / 2, 0.77), xytext=(x + xw / 2, 0.80), arrowprops=dict(arrowstyle="-", color=col))
ax.annotate("", xy=(0.97, 0.28), xytext=(0.03, 0.28), arrowprops=dict(arrowstyle="->", color="#666", lw=1.5))
for i, t in enumerate(["現在", "近い未来", "少し先の未来"]):
    ax.text(x0 + i * (xw + gap) + xw / 2, 0.24, t, ha="center", fontsize=9, color="#666")
ax.text(0.985, 0.28, "時間軸", ha="right", va="bottom", fontsize=10, fontweight="bold", color="#666")
ax.add_patch(plt.Rectangle((0.03, 0.06), 0.94, 0.12, facecolor="#F0F0EE", edgecolor="#888"))
ax.text(0.5, 0.12, "＋ 両立型3社（変わる×生まれるが両方高い）　＋ 分散役2社（業種・テーマの偏りを整える）　＝ 合計20社",
        ha="center", va="center", fontsize=10.5)
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
fig.tight_layout(); fig.savefig(ED / "assets/fig1_moat_v10.png", dpi=150); plt.close(fig)
NAVY, TEAL, TEALL, SAGE, GRAYG, GOLDBG = "#16324F", "#2F6D5F", "#5E9B8C", "#8FB0A5", "#B9C6C0", "#F5EBD0"

def box(ax, x, y, w, h, text, fc, ec=None, tc="#222", fs=10, bold=False):
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec or fc, linewidth=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc, fontsize=fs,
            fontweight="bold" if bold else "normal")

def arrow(ax, x1, y1, x2, y2, col="#555"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color=col, lw=1.6))

# ---- 図表Ⅱ-7 離(選定フロー・③-4: 矢印起点修正・日本語ラベル) ----
fig, ax = plt.subplots(figsize=(9.6, 5.2)); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
# 左: 選定の物差し4つ
srcs = [("守：新バフェット品質ゲート", NAVY, 0.80), ("破：変わる堀の点数（式10）", TEAL, 0.60),
        ("離：生まれる堀の点数（式11）", TEALL, 0.40), ("業種・テーマの分散条件", GRAYG, 0.20)]
for t, c, y in srcs:
    box(ax, 0.02, y - 0.06, 0.28, 0.12, t, "#EAF1EE", c, fs=9.5)
# 中央: 証拠の関所
box(ax, 0.35, 0.06, 0.17, 0.20, "証拠の関所（式12）\n事業の開示で実需を確認", GOLDBG, "#B08514", fs=9.5, bold=True)
# 右: 役割5つ(日本語)
roles = [("完成した堀 5社", NAVY, 0.80, "white"), ("変わる堀 5社", TEAL, 0.62, "white"),
         ("生まれる堀 5社", TEALL, 0.44, "white"), ("両立型 3社", SAGE, 0.28, "#222"),
         ("分散役 2社", GRAYG, 0.14, "#222")]
for t, c, y, tc in roles:
    box(ax, 0.60, y - 0.055, 0.24, 0.11, t, c, c, tc=tc, fs=10, bold=True)
# 矢印(③-4の正しい起点): 守→完成(関所を通さず直結) / 変わる式→変わる / 生まれる式→生まれる / 関所→両立&分散
arrow(ax, 0.30, 0.80, 0.60, 0.80, NAVY)                       # 守→完成した堀(直結)
ax.text(0.45, 0.83, "そのまま固定", ha="center", fontsize=8, color=NAVY)
arrow(ax, 0.30, 0.60, 0.60, 0.625, TEAL)                      # 変わる式→変わる堀
arrow(ax, 0.30, 0.40, 0.60, 0.46, TEALL)                      # 生まれる式→生まれる堀
arrow(ax, 0.30, 0.18, 0.35, 0.17, "#B08514")                 # 分散条件→関所
arrow(ax, 0.52, 0.18, 0.60, 0.28, "#B08514")                 # 関所→両立型
arrow(ax, 0.52, 0.14, 0.60, 0.14, "#B08514")                 # 関所→分散役
# 最終20社
box(ax, 0.88, 0.40, 0.10, 0.20, "最終\n20社", NAVY, NAVY, tc="white", fs=11, bold=True)
for _, _, y, _ in roles:
    arrow(ax, 0.84, y, 0.88, 0.50, "#999")
fig.tight_layout(); fig.savefig(ED / "assets/fig2_merge_v10.png", dpi=150); plt.close(fig)
print("written -> assets/fig1_moat_v10.png / fig2_merge_v10.png")
