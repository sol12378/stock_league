# -*- coding: utf-8 -*-
"""STOCKリーグ提出版・レビュー対応図表(全面日本語・印刷実寸で10pt前後を確保)。
canvas幅を印刷幅(168mm≒6.7in)に合わせ、縮小による文字つぶれを防ぐ。
出力先: stockleague_edition/assets/
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# 書体規定: 図表はサンセリフ体(欧文・数字=Helvetica、和文=ヒラギノ角ゴにフォールバック)
plt.rcParams["font.family"] = ["Helvetica", "Hiragino Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ASSETS = ROOT / "outputs/stockleague_edition/assets"
P5 = ROOT / "outputs/beyond_buffett_fable_loop_final/phase5_verification_and_ablation"

NAVY = "#16324F"; TEAL = "#2F6D5F"; TEAL_L = "#5E9B8C"; SAGE = "#8FB0A5"; GRAYG = "#B9C6C0"
GOLD_BG = "#F5EBD0"
# 検証済みカテゴリカル4色(全ペアCVD/通常視PASS)
G_BLUE, G_GREEN, G_MAGENTA, G_YELLOW = "#2a78d6", "#008300", "#e87ba4", "#eda100"


def save(fig, name):
    fig.savefig(ASSETS / name, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def box(ax, x, y, w, h, text, fc, ec="black", fs=10, tc="black", bold=False, lw=1.2, dash=None, rs=0.04):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.012,rounding_size={rs}",
                       fc=fc, ec=ec, lw=lw)
    if dash:
        p.set_linestyle((0, dash))
    ax.add_patch(p)
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                color=tc, fontweight="bold" if bold else "normal", linespacing=1.4)


def arrow(ax, x0, y0, x1, y1, color="black", lw=1.5, ms=13):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=ms, lw=lw, color=color,
                                 shrinkA=0, shrinkB=0))


# ================= 図表Ⅰ-1 三世代の堀 =================
def fig1_moat():
    fig, ax = plt.subplots(figsize=(6.8, 3.05))
    ax.set_xlim(0, 12); ax.set_ylim(0, 9.4); ax.axis("off")
    cols = [
        (0.3, NAVY, "完成した堀", "すでに強みが\n出来上がった会社。\n守の式だけで選んだ\n5社を固定。\n割安×優良×壊れにくい"),
        (4.15, TEAL, "変わる堀", "資本効率の改革で\nこれから強くなる\n会社 5社。\n“安いだけの会社”\nとは区別する"),
        (8.0, TEAL_L, "生まれる堀", "AI・半導体・光通信の\n実需で強みが生まれる\n会社 5社。\n“名前だけのAI関連”\nとは区別する"),
    ]
    for x, c, head, detail in cols:
        box(ax, x + 0.9, 8.0, 1.9, 0.95, head, fc=c, tc="white", fs=11, bold=True)
        box(ax, x, 3.6, 3.7, 4.0, detail, fc="white", ec=c, fs=9.5, lw=1.8)
        arrow(ax, x + 1.85, 7.98, x + 1.85, 7.68, color=c, lw=1.8, ms=11)
    arrow(ax, 0.25, 2.85, 11.85, 2.85, color="black", lw=1.6, ms=14)
    for x, lab in [(2.15, "現在(完成)"), (6.0, "近い未来(変化)"), (9.85, "少し先の未来(新生)")]:
        ax.text(x, 2.45, lab, ha="center", va="top", fontsize=9.5)
    ax.text(11.8, 3.05, "時間軸", ha="right", va="bottom", fontsize=10, fontweight="bold")
    box(ax, 0.3, 0.25, 11.4, 1.35,
        "＋ 両立型3社(変わる×生まれる の両方が高い)\n＋ 分散役2社(業種・テーマの偏りを整える)　＝ 合計 20社",
        fc="#F0F0EE", ec="#666666", fs=9.5, lw=1.1)
    save(fig, "fig1_moat.png")


# ================= 図表Ⅱ-2 守の絞り込み(縦型・幅と色=残存数) =================
def fig2_shu():
    stages = [
        ("全対象 ― 金融を除く普通株", 3099), ("割安か ― 純資産・利益で測る", 2740),
        ("収益力は本物か ― 粗利÷総資産", 583), ("財務は健全か ― 6項目チェック", 146),
        ("利益は本物か ― 現金の裏づけ", 112), ("危険はないか ― 債務超過など除外", 90),
        ("実際に買えるか ― 売買のしやすさ", 77), ("完成した堀 Top5", 5),
    ]
    n_st = len(stages)
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.set_xlim(0, 10); ax.set_ylim(0, n_st); ax.axis("off")
    maxlog = np.log10(3099)
    light = np.array([0.91, 0.95, 0.93]); dark = np.array([0.10, 0.30, 0.26])
    minw = 3.4
    for i, (lab, n) in enumerate(stages):
        t = 1 - np.log10(max(n, 1)) / maxlog
        w = minw + (8.6 - minw) * (np.log10(max(n, 1)) / maxlog)
        y = n_st - 1 - i
        last = i == n_st - 1
        rgb = NAVY if last else tuple(light + (dark - light) * t)
        tc = "white" if (last or t > 0.52) else "black"
        box(ax, 4.6 - w / 2, y + 0.10, w, 0.8, "", fc=rgb, lw=1.5 if last else 1.0, rs=0.03)
        ax.text(4.6, y + 0.5, lab, ha="center", va="center", fontsize=9.6,
                color=tc, fontweight="bold" if last else "normal")
        ax.text(4.6 + w / 2 + 0.15, y + 0.5, f"{n:,}社", ha="left", va="center",
                fontsize=10, fontweight="bold", color="#333333")
    save(fig, "fig2_shu.png")


# ================= 図表Ⅱ-3 破: 候補リストの入れ子 =================
def fig2_ha():
    fig, ax = plt.subplots(figsize=(6.8, 4.05))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10.2); ax.axis("off")
    box(ax, 0.1, 2.6, 3.2, 5.6,
        "式は変えない。\n変えるのは“使い方”だけ\n・各指標の重み\n・減点の強さ\n・候補を何社まで\n　広げるか\n・業種の偏りの調整\n・データ欠けの扱い",
        fc="#EAF1EE", ec=TEAL, fs=9.5, lw=1.6)
    ax.text(1.7, 2.25, "多数の組合せを試し、\n最も安定な設定を選ぶ", ha="center", va="top", fontsize=9)
    arrow(ax, 3.38, 5.4, 4.0, 5.4, color=TEAL, lw=2.0, ms=15)
    ax.text(6.95, 9.75, "最適化後の点数で全社を並べ、上から区切った“入れ子”", ha="center", va="center",
            fontsize=9.8, fontweight="bold", color=NAVY)
    box(ax, 4.1, 0.9, 5.7, 8.4, "", fc="white", ec="#888888", fs=9, lw=1.2, dash=(4, 3))
    ax.text(6.95, 8.9, "Top2000(参照・念のため広めに保存)", ha="center", fontsize=9.5, color="#555555")
    box(ax, 4.45, 1.3, 5.0, 7.1, "", fc="#DCE8E4", ec=TEAL, fs=9, lw=2.0)
    ax.text(6.95, 8.2, "Top1200(正式採用)", ha="center", va="top", fontsize=11, fontweight="bold", color=TEAL)
    ax.text(6.95, 7.6, "守の5社は全員この中に含まれる", ha="center", va="top", fontsize=9.2)
    box(ax, 4.95, 1.75, 4.0, 5.05, "", fc="#9CC2B7", ec="black", fs=9, lw=1.1)
    ax.text(6.95, 6.6, "Top300 ― 後の検査A9\n「もし300社に絞っていたら」で使用",
            ha="center", va="top", fontsize=9.2, fontweight="bold")
    box(ax, 5.45, 2.15, 3.0, 3.0, "", fc=TEAL, ec="black", fs=9, lw=1.1)
    ax.text(6.95, 4.95, "Top100 ― 後の検査A8\n「もし100社に\n絞っていたら」で使用",
            ha="center", va="top", fontsize=9.2, fontweight="bold", color="white")
    save(fig, "fig2_ha.png")


# ================= 図表Ⅱ-6 離: 1対1の矢印 =================
def fig2_ri():
    fig, ax = plt.subplots(figsize=(6.9, 3.65))
    ax.set_xlim(0, 13); ax.set_ylim(0, 10); ax.axis("off")
    srcs = [
        (8.35, NAVY, "守Top5\n(完成した堀・そのまま)"),
        (6.05, TEAL, "変わる堀の点数\n式(10)"),
        (3.75, TEAL_L, "生まれる堀の点数\n式(11)"),
        (1.45, GRAYG, "業種・テーマの\n分散条件"),
    ]
    for y, c, lab in srcs:
        box(ax, 0.15, y, 2.9, 1.5, lab, fc="white", ec=c, fs=9, lw=1.8)
    box(ax, 3.75, 0.9, 1.5, 7.2,
        "証拠の関所\n式(12)\n\n接点だけの\n会社を\n通さない\n\n(両立型は\n厳しい方の\n証拠で判定)", fc=GOLD_BG, ec="#B08514", fs=8.4, lw=1.5)
    roles = [
        (8.35, NAVY, "white", "完成した堀 5社(固定)"),
        (6.7, TEAL, "white", "変わる堀 5社"),
        (5.05, SAGE, "black", "両立型 3社(両方高い)"),
        (3.4, TEAL_L, "black", "生まれる堀 5社"),
        (1.75, GRAYG, "black", "分散役 2社"),
    ]
    for y, c, tc, lab in roles:
        box(ax, 6.15, y, 3.55, 1.3, lab, fc=c, tc=tc, fs=9.8, bold=True, lw=1.2)
    arrow(ax, 3.1, 9.1, 6.1, 9.0, color=NAVY, lw=1.8)
    ax.text(4.6, 9.35, "そのまま固定", ha="center", fontsize=8.6, color=NAVY)
    arrow(ax, 3.1, 6.8, 3.72, 6.8, color=TEAL, lw=1.8)
    arrow(ax, 5.28, 7.0, 6.1, 7.35, color=TEAL, lw=1.8)
    arrow(ax, 5.28, 6.3, 6.1, 5.85, color=SAGE, lw=1.8)
    arrow(ax, 3.1, 4.5, 3.72, 4.5, color=TEAL_L, lw=1.8)
    arrow(ax, 5.28, 4.15, 6.1, 4.05, color=TEAL_L, lw=1.8)
    arrow(ax, 5.28, 5.0, 6.1, 5.55, color=SAGE, lw=1.8)
    ax.text(5.68, 6.62, "両方高い", ha="center", fontsize=8, color="#3F6A5E", rotation=-24)
    arrow(ax, 3.1, 2.2, 3.72, 2.2, color="#8A9A93", lw=1.8)
    arrow(ax, 5.28, 2.3, 6.1, 2.4, color="#8A9A93", lw=1.8)
    box(ax, 10.65, 4.15, 2.2, 1.9, "最終\n20社", fc=NAVY, tc="white", fs=12.5, bold=True, lw=1.8)
    for y, _, _, _ in roles:
        arrow(ax, 9.75, y + 0.65, 10.63, 5.1, color="#444444", lw=1.2, ms=10)
    save(fig, "fig2_ri.png")


# ================= 図表Ⅱ-7 壊れにくさ検査(横棒・グループ色分け) =================
ABL_LABEL = {
    "A1": "変わる堀の点だけで選ぶ", "A2": "生まれる堀の点だけで選ぶ",
    "A3": "証拠の関所なし", "A4": "割安のワナ減点なし", "A5": "話題先行の減点なし",
    "A6": "データ信頼度なし", "A7": "業種の上限なし", "A8": "候補を100社に絞る",
    "A9": "候補を300社に絞る", "A10": "候補1,200社全体", "A11": "基準線5社の固定なし",
    "A12": "両立型の枠なし", "A13": "分散役の枠なし", "A14": "証拠水準2以上の条件なし",
    "A15": "改革の証拠なし", "A16": "AIキーワード減点を限定",
}
GROUPS = [
    ("点の付け方を変える", G_BLUE, ["A1", "A2"]),
    ("減点・証拠の条件を外す", G_GREEN, ["A3", "A4", "A5", "A6", "A14", "A15", "A16"]),
    ("候補の広さを変える", G_MAGENTA, ["A8", "A9", "A10"]),
    ("役割の枠を外す", G_YELLOW, ["A7", "A11", "A12", "A13"]),
]


def fig2_ablation():
    rows = {r["variant"]: int(r["overlap_with_final20"])
            for r in csv.DictReader(open(P5 / "ablation_results.csv", encoding="utf-8"))}
    fig, ax = plt.subplots(figsize=(6.9, 5.1))
    y = 0
    ys, vals, cols, labs, edges = [], [], [], [], []
    headers = []
    for gname, gc, mem in GROUPS:
        headers.append((y, gname, gc))
        y -= 0.95
        for m in mem:
            ys.append(y); vals.append(rows[m]); cols.append(gc)
            labs.append(f"{ABL_LABEL[m]}({m})")
            edges.append("black" if m in ("A8", "A11") else "white")
            y -= 0.8
        y -= 0.45
    bars = ax.barh(ys, vals, height=0.62, color=cols, zorder=3)
    for b, e in zip(bars, edges):
        b.set_edgecolor(e); b.set_linewidth(1.6 if e == "black" else 1.0)
    for yy, v, m in zip(ys, vals, [l[l.find("(") + 1:-1] for l in labs]):
        note = ""
        if m == "A8":
            note = " ← 最小。候補の広さが選定の背骨"
        elif m == "A11":
            note = " ← 基準線5社は“意図した固定”"
        ax.text(v + 0.25, yy, f"{v}{note}", va="center", fontsize=9.3,
                fontweight="bold" if note else "normal")
    for hy, gname, gc in headers:
        ax.add_patch(FancyBboxPatch((-8.6, hy - 0.28), 0.45, 0.56, boxstyle="square,pad=0",
                                    fc=gc, ec="none", clip_on=False))
        ax.text(-8.0, hy, gname, va="center", ha="left", fontsize=10, fontweight="bold", clip_on=False)
    ax.set_yticks(ys); ax.set_yticklabels(labs, fontsize=9.3)
    ax.axvline(20, color="#333333", ls=":", lw=1.1, zorder=2)
    ax.axvline(15, color="#777777", ls="--", lw=1.1, zorder=2)
    ax.text(20, 0.75, "20 = 全部一致", ha="center", fontsize=9, va="bottom")
    ax.text(15, 0.75, "15以上 = 安定", ha="center", fontsize=9, va="bottom", color="#555555")
    ax.set_xlim(0, 24.5); ax.set_ylim(y + 0.2, 1.15)
    ax.set_xticks([0, 5, 10, 15, 20]); ax.tick_params(axis="x", labelsize=9.5)
    ax.set_xlabel("最終20社と一致した社数(20社中)", fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#999999")
    fig.tight_layout()
    save(fig, "fig2_ablation.png")


# ================= 図表Ⅲ-7 累積リターン比較(3年・対照群つき) =================
def fig3_cum():
    import pandas as _pd
    cum = _pd.read_csv(ASSETS / "cum3y_series.csv", parse_dates=["date"]).set_index("date")
    cum = cum / cum.iloc[0]
    fig, ax = plt.subplots(figsize=(6.8, 2.9))
    style = [("ours", "本ポートフォリオ", NAVY, "-", 2.2),
             ("control", "純正バフェット(対照群)", TEAL, "--", 1.8),
             ("topix", "TOPIX(市場平均)", "#777777", "-", 1.3),
             ("nikkei", "日経平均", "#AAAAAA", ":", 1.5)]
    for col, lab, c, ls, lw in style:
        ax.plot(cum.index, cum[col], color=c, ls=ls, lw=lw, label=lab)
        ax.annotate(f"{cum[col].iloc[-1]:.2f}", xy=(cum.index[-1], cum[col].iloc[-1]),
                    xytext=(4, 0), textcoords="offset points", fontsize=9, color=c,
                    va="center", fontweight="bold")
    ax.set_ylabel("累積(期首=1)", fontsize=10)
    ax.legend(fontsize=9, loc="upper left", frameon=False)
    ax.tick_params(labelsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#999999"); ax.spines["bottom"].set_color("#999999")
    ax.margins(x=0.02)
    fig.tight_layout()
    save(fig, "fig3_cum.png")


# ================= 図表Ⅲ-8 役割別寄与 =================
def fig3_roles():
    js = json.load(open(P5 / "phase5_validation_summary.json", encoding="utf-8"))
    rc = js["role_contribution_3y"]
    order = ["Emerging Core", "Transformation Core", "Bridge / Diversifier", "Dual Moat", "Buffett Core"]
    jp = {"Emerging Core": "生まれる堀", "Transformation Core": "変わる堀",
          "Bridge / Diversifier": "分散役", "Dual Moat": "両立型", "Buffett Core": "完成した堀"}
    cols = {"Emerging Core": TEAL_L, "Transformation Core": TEAL, "Bridge / Diversifier": GRAYG,
            "Dual Moat": SAGE, "Buffett Core": NAVY}
    total = sum(rc.values())
    fig, ax = plt.subplots(figsize=(6.7, 2.15))
    ys = np.arange(len(order))[::-1]
    for y, k in zip(ys, order):
        share = rc[k] / total * 100
        ax.barh(y, share, height=0.62, color=cols[k], edgecolor="white", lw=1.1, zorder=3)
        ax.text(share + 1.0, y, f"{share:.0f}%", va="center", fontsize=10)
    ax.set_yticks(ys); ax.set_yticklabels([jp[k] for k in order], fontsize=10)
    ax.set_xlim(0, 92)
    ax.set_xlabel("過去3年の値上がり寄与の割合(寄与合計に対する％・選定に使った期間)", fontsize=9.5)
    ax.tick_params(axis="x", labelsize=9.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#999999"); ax.spines["bottom"].set_color("#999999")
    fig.tight_layout()
    save(fig, "fig3_roles.png")


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    fig1_moat(); fig2_shu(); fig2_ha(); fig2_ri(); fig2_ablation(); fig3_cum(); fig3_roles()
    print("done")
