# -*- coding: utf-8 -*-
"""STOCKリーグ提出版の表紙（紺×ティール・タイポグラフィ主体・A4全面）。
入賞作の全面ビジュアル表紙に倣う。写真は権利上使わず、デザイン面で構成。
チーム情報は記入欄。300dpi A4 PNG を出力し、docx で全面配置する。"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

plt.rcParams["font.family"] = "Hiragino Sans"
OUT = Path(__file__).parent.parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#16324F"; NAVY2 = "#1F4568"; TEAL = "#2F6D5F"; TEAL_L = "#5E9B8C"
GOLD = "#C9A227"; WHITE = "#FFFFFF"; PALE = "#D7E3EC"

W, H = 8.27, 11.69  # A4 inches
fig = plt.figure(figsize=(W, H), dpi=300)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 141.4); ax.axis("off")

# background: deep navy with vertical gradient
grad = np.linspace(0, 1, 500).reshape(-1, 1)
ax.imshow(grad, extent=[0, 100, 0, 141.4], aspect="auto", origin="lower",
          cmap=matplotlib.colors.LinearSegmentedColormap.from_list("nv", [NAVY, "#0D2233"]))

# three moat "generations" as layered horizon bands (完成・変化・新生)
for i, (y0, col, al) in enumerate([(38, TEAL, .30), (46, TEAL, .45), (54, TEAL_L, .60)]):
    band = Polygon([(0, y0), (100, y0 + 9), (100, y0 + 13.5), (0, y0 + 4.5)],
                   closed=True, facecolor=col, alpha=al, edgecolor="none")
    ax.add_patch(band)
# rising sun accent over the newest moat
ax.scatter([78], [66.5], s=5200, c=GOLD, alpha=.92, zorder=5)
ax.scatter([78], [66.5], s=11500, c=GOLD, alpha=.22, zorder=4)

# diagonal corner ribbons (top-left / bottom-right) like prize covers
ax.add_patch(Polygon([(0, 141.4), (46, 141.4), (0, 122)], closed=True, facecolor=NAVY2, edgecolor="none"))
ax.add_patch(Polygon([(100, 0), (54, 0), (100, 19)], closed=True, facecolor=NAVY2, edgecolor="none"))

# top-left: entry meta
meta = ["応募区分：大学部門", "チーム名：［　　　　　　　　］", "チームＩＤ：［　　　　　　　］"]
for k, m in enumerate(meta):
    ax.text(3, 137.5 - k * 4.0, m, color=WHITE, fontsize=13, fontweight="bold", ha="left", va="top")

# main title block
ax.text(50, 96, "BEYOND", color=WHITE, fontsize=52, fontweight="bold",
        ha="center", va="center", family="Times New Roman")
ax.text(50, 84, "BUFFETT", color=WHITE, fontsize=52, fontweight="bold",
        ha="center", va="center", family="Times New Roman")
ax.plot([22, 78], [77.5, 77.5], color=GOLD, lw=1.6)
ax.text(50, 72.5, "堀 は 、時 を こ え て 広 が る", color=PALE, fontsize=17, ha="center", va="center")
ax.text(50, 30, "完成した堀 ・ 変わる堀 ・ 生まれる堀\n三世代のMoatでつくる日本株ポートフォリオ",
        color=PALE, fontsize=12.5, ha="center", va="center", linespacing=1.7)

# bottom-right: school/members
bot = ["学校：［　　　　　　　　　］　学年：［　　］", "メンバー：［　　　　　　　　　　　　　　］", "指導教員：［　　　　　　　　　］"]
for k, m in enumerate(bot):
    ax.text(97, 13.5 - k * 4.0, m, color=WHITE, fontsize=12, fontweight="bold", ha="right", va="top")

fig.savefig(OUT / "cover.png", dpi=300)
plt.close(fig)
print("wrote", OUT / "cover.png")
