#!/usr/bin/env python
"""Phase7 conceptual figures (I-1, II-2, V-1, V-5) — monochrome, print-friendly,
Japanese labels via Hiragino Sans. Data-backed where relevant (V-5 from final20)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.font_manager as fm
import pandas as pd

plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
FIGDIR = OUT / "phase7_final_report/final_figures"
FIGDIR.mkdir(parents=True, exist_ok=True)


def box(ax, x, y, w, h, text, fc="0.93", ec="black", fs=10, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=16, lw=1.3, color="black"))


# --- 図表 I-1 研究全体の流れ ------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 3.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 3.2); ax.axis("off")
stages = [
    (0.1, "Phase1\n守", "完成Moat抽出\n先行研究式\n→Top5固定", "0.85"),
    (2.05, "Phase2\n破", "式不変で\n閾値最適化\n→Top1200", "0.90"),
    (4.0, "Phase3\n離", "変わるMoat\n生まれるMoat\n→Final20", "0.80"),
    (5.95, "Phase4\n配分", "役割予算×\nリスク調整\n式(14)", "0.90"),
    (7.9, "Phase5\n検証", "市場比較\nAblation\nリスク", "0.90"),
]
for x, title, body, fc in stages:
    box(ax, x, 1.5, 1.7, 1.3, title, fc=fc, fs=12, bold=True)
    box(ax, x, 0.15, 1.7, 1.15, body, fc="white", fs=8)
    if x > 0.1:
        arrow(ax, x - 0.32, 2.15, x, 2.15)
ax.text(5.0, 3.05, "図全体：バフェットの Moat を時間軸拡張する「守・破・離」パイプライン",
        ha="center", fontsize=9, style="italic")
fig.tight_layout(); fig.savefig(FIGDIR / "study_flow.png", dpi=200, facecolor="white"); plt.close(fig)

# --- 図表 II-2 守・破・離の役割 --------------------------------------------
fig, ax = plt.subplots(figsize=(8.5, 3.0))
ax.set_xlim(0, 9); ax.set_ylim(0, 3); ax.axis("off")
cols = [
    ("守（Phase1）", "完成された Moat", "先行研究式を変えず\n段階的スクリーニング\nTop5 を Buffett Core に固定", "0.88"),
    ("破（Phase2）", "候補宇宙の拡張", "式は不変、閾値・分位・\n通過条件・候補数を最適化\nTop1200 形成", "0.93"),
    ("離（Phase3）", "Moat の時間軸拡張", "変わる Moat・生まれる Moat\nを測定し Final20 構築\n先行研究式の再構成", "0.80"),
]
for i, (t, sub, body, fc) in enumerate(cols):
    x = 0.2 + i * 3.0
    box(ax, x, 1.7, 2.7, 1.15, t + "\n" + sub, fc=fc, fs=11, bold=True)
    box(ax, x, 0.15, 2.7, 1.4, body, fc="white", fs=8.5)
    if i > 0:
        arrow(ax, x - 0.3, 2.27, x, 2.27)
fig.tight_layout(); fig.savefig(FIGDIR / "shu_ha_ri.png", dpi=200, facecolor="white"); plt.close(fig)

# --- 図表 V-1 Moat の時間軸拡張 --------------------------------------------
fig, ax = plt.subplots(figsize=(9, 3.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 3.2); ax.axis("off")
arrow(ax, 0.3, 0.5, 9.7, 0.5)
ax.text(9.7, 0.25, "時間軸", ha="right", fontsize=9)
gens = [
    (0.5, "完成された Moat", "Buffett Core 5社\n（Phase1 Top5 固定）\nValue×Quality×低リスク", "0.82"),
    (3.6, "変わる Moat", "Transformation 5社\n資本効率改善・株主還元\n＝低PBRではない", "0.90"),
    (6.7, "生まれる Moat", "Emerging 5社\nAI基盤・半導体・光通信\n＝AIキーワードではない", "0.86"),
]
for x, t, body, fc in gens:
    box(ax, x, 1.6, 2.7, 1.0, t, fc=fc, fs=11, bold=True)
    box(ax, x, 0.7, 2.7, 0.8, body, fc="white", fs=8)
    arrow(ax, x + 1.35, 0.7, x + 1.35, 0.55)
ax.text(5.0, 3.0, "図全体：完成・変化・新生の三世代 Moat（＋Dual Moat 3社・Bridge 2社）",
        ha="center", fontsize=9, style="italic")
fig.tight_layout(); fig.savefig(FIGDIR / "moat_timeaxis.png", dpi=200, facecolor="white"); plt.close(fig)

# --- 図表 V-5 Final20 役割マトリクス（データ由来） -------------------------
f20 = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
role_order = ["Buffett Core", "Transformation Core", "Emerging Core", "Dual Moat", "Bridge / Diversifier"]
fig, ax = plt.subplots(figsize=(9.5, 5.2)); ax.axis("off")
rows = [["役割", "銘柄（コード）", "業種", "テーマ", "Ev.", "目標比率"]]
for role in role_order:
    sub = f20[f20.final_role == role]
    for _, r in sub.iterrows():
        rows.append([role, f"{r.company_name[:16]} ({int(r.code_n)})", r.sector[:14],
                     r.theme, f"L{int(r.final_evidence_level)}", f"{r.target_weight_final*100:.1f}%"])
tbl = ax.table(cellText=rows[1:], colLabels=rows[0], loc="center", cellLoc="left")
tbl.auto_set_font_size(False); tbl.set_fontsize(7.5); tbl.scale(1, 1.25)
for j in range(6):
    tbl[0, j].set_facecolor("0.75"); tbl[0, j].set_text_props(fontweight="bold")
shade = {"Buffett Core": "0.97", "Transformation Core": "0.90", "Emerging Core": "0.84",
         "Dual Moat": "0.93", "Bridge / Diversifier": "0.98"}
for i, row in enumerate(rows[1:], start=1):
    for j in range(6):
        tbl[i, j].set_facecolor(shade[row[0]])
# no baked-in title: the docx/PDF adds the 図表番号 caption below the image
fig.tight_layout(); fig.savefig(FIGDIR / "role_matrix.png", dpi=200, facecolor="white",
                                bbox_inches="tight"); plt.close(fig)

print("wrote study_flow / shu_ha_ri / moat_timeaxis / role_matrix to", FIGDIR)
