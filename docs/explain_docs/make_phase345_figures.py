# -*- coding: utf-8 -*-
"""phase3/4/5 方法論レポート用の図（PDF, figures/ 配下）。
phase1/2 レポートの図と同じく簡潔・モノクロ基調。実データ準拠。"""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False
HERE = Path(__file__).parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
LF = HERE.parent.parent / "outputs/beyond_buffett_fable_loop_final"
DK, MD, LT, LT2 = "0.25", "0.55", "0.82", "0.92"


def rbox(ax, x, y, w, h, text, fc, tc="black", fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc=fc, ec="black", lw=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal")


# ---- p3: 三世代の堀（時間軸） ----
fig, ax = plt.subplots(figsize=(7.4, 2.5)); ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis("off")
ax.annotate("", xy=(9.7, 0.42), xytext=(0.3, 0.42), arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2))
ax.text(9.7, 0.18, "時間軸", ha="right", fontsize=8)
for x, t, b, fc in [(0.4, "完成した堀", "Buffett Core 5\n（Phase1 Top5 固定）", LT2),
                    (3.5, "変わる堀", "Transformation 5\n資本効率改善×割安", LT),
                    (6.6, "生まれる堀", "Emerging 5\nAI 基盤への実需接続", MD)]:
    rbox(ax, x, 1.45, 2.8, 0.95, t, fc, fs=10, bold=True, tc="white" if fc == MD else "black")
    rbox(ax, x, 0.62, 2.8, 0.72, b, "white", fs=7.5)
ax.text(5.0, 2.72, "（＋Dual Moat 3・Bridge 2）", ha="center", fontsize=7.5, style="italic")
fig.savefig(FIG / "p3_timeaxis.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- p3: Evidence Level 分布（実データ） ----
fig, ax = plt.subplots(figsize=(4.6, 2.5))
ax.bar(["Level 3", "Level 2", "Level 1"], [15, 4, 1], color=[DK, MD, LT], edgecolor="black")
for i, v in enumerate([15, 4, 1]):
    ax.text(i, v + 0.3, str(v), ha="center", fontsize=10, fontweight="bold")
ax.set_ylabel("社数"); ax.set_ylim(0, 17); ax.spines[["top", "right"]].set_visible(False)
fig.savefig(FIG / "p3_evidence_dist.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- p3: 除外862社の内訳（実データ） ----
lab = ["AIキーワード\nのみ", "上位互換\nあり", "distress/\n品質", "バリュー\nトラップ", "低PBR\nのみ"]
val = [577, 221, 32, 17, 15]
fig, ax = plt.subplots(figsize=(6.2, 2.6))
ax.bar(lab, val, color=[DK, MD, LT, LT, LT2], edgecolor="black")
for i, v in enumerate(val):
    ax.text(i, v + 12, str(v), ha="center", fontsize=9, fontweight="bold")
ax.set_ylabel("社数"); ax.spines[["top", "right"]].set_visible(False)
fig.savefig(FIG / "p3_rejected.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- p4: 役割予算（実データ） ----
fig, ax = plt.subplots(figsize=(6.4, 2.4))
roles = ["Buffett\nCore", "Transformation\nCore", "Emerging\nCore", "Dual\nMoat", "Bridge"]
buds = [25, 25, 25, 15, 10]
ax.bar(roles, buds, color=[DK, MD, MD, LT, LT2], edgecolor="black")
for i, v in enumerate(buds):
    ax.text(i, v + 0.7, f"{v}%", ha="center", fontsize=9, fontweight="bold")
ax.set_ylabel("役割予算（%）"); ax.set_ylim(0, 29); ax.spines[["top", "right"]].set_visible(False)
fig.savefig(FIG / "p4_role_budget.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- p4: L=1 vs L=100 執行（実データ） ----
fig, ax = plt.subplots(figsize=(5.2, 2.5))
ax.bar(["L=1（単元未満株）", "L=100（実単元）"], [99.0, 46.7], color=[DK, LT], edgecolor="black")
for i, v in enumerate([99.0, 46.7]):
    ax.text(i, v + 2, f"{v}%", ha="center", fontsize=10, fontweight="bold")
ax.set_ylabel("予算消化率（%）"); ax.set_ylim(0, 112); ax.spines[["top", "right"]].set_visible(False)
ax.text(1, 20, "9社が購入不可", ha="center", fontsize=8)
fig.savefig(FIG / "p4_lot.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- p5: アブレーション（実データ CSV） ----
abl = pd.read_csv(LF / "phase5_verification_and_ablation/ablation_results.csv")
fig, ax = plt.subplots(figsize=(7.4, 2.7))
cols = [DK if v == "A8" else (LT if o >= 15 else MD) for v, o in zip(abl["variant"], abl["overlap_with_final20"])]
ax.bar(abl["variant"], abl["overlap_with_final20"], color=cols, edgecolor="black")
ax.axhline(20, color="black", lw=0.8, ls=":"); ax.axhline(15, color="0.4", lw=0.8, ls="--")
ax.set_ylabel("Final20 との一致数"); ax.set_ylim(0, 22)
ax.spines[["top", "right"]].set_visible(False)
mi = int(abl["overlap_with_final20"].idxmin())
ax.annotate("A8=7（最小）", xy=(mi, 7), xytext=(mi + 1.4, 11), fontsize=8,
            arrowprops=dict(arrowstyle="->", lw=0.9))
fig.savefig(FIG / "p5_ablation.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---- p5: 役割寄与（実データ JSON） ----
s = json.load(open(LF / "phase5_verification_and_ablation/phase5_validation_summary.json"))
rc = s["role_contribution_3y"]
fig, ax = plt.subplots(figsize=(6.4, 2.5))
keys = list(rc.keys()); vals = [rc[k] * 100 for k in keys]
ax.bar([k.replace(" ", "\n") for k in keys], vals, color=[DK, MD, LT, LT, LT2], edgecolor="black")
for i, v in enumerate(vals):
    ax.text(i, v + 4, f"{v:.0f}", ha="center", fontsize=8.5)
ax.set_ylabel("3年累積への寄与（%pt）"); ax.spines[["top", "right"]].set_visible(False)
fig.savefig(FIG / "p5_role_contrib.png", dpi=300, bbox_inches="tight"); plt.close(fig)

print("wrote 7 figures to", FIG)
