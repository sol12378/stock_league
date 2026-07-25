# -*- coding: utf-8 -*-
"""V9 スクリーニング章の図版4点を生成(全社数は funnel_branches_v9.json から自動転記)。
fig2_overview_v9: 章頭の全体設計図(優勝レポート式バナー＋二層番号＋段見出しに N社→M社)
fig2_shu_v9: 守の階段ファネル / fig2_ha_v9: 破のミニファネル / fig2_ri_v9: 離の分岐図"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch

plt.rcParams["font.family"] = "Hiragino Sans"
ED = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/outputs/stockleague_edition")
F = json.load(open(ED / "funnel_branches_v9.json", encoding="utf-8"))
A = ED / "assets"

NAVY = "#16324F"; TEAL = "#2F6D5F"; GOLD = "#9A6A1F"; GRAY = "#4A5A6A"; SLATE = "#5B6B7C"
LIGHT = {NAVY: "#E3E9F0", TEAL: "#E1EBE7", GOLD: "#F3EAD6", GRAY: "#E8ECEF", SLATE: "#E9EDF1"}

def _n(x): return f"{x:,}"

# ============ fig2_overview_v9 全体設計図 ============
fig, ax = plt.subplots(figsize=(7.4, 7.42), dpi=200)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

def banner(y, h, color, left, right):
    ax.add_patch(FancyBboxPatch((1.2, y), 97.6, h, boxstyle="round,pad=0.12,rounding_size=0.5",
                                fc=color, ec="none"))
    ax.add_patch(Rectangle((1.2, y), 1.6, h, fc="black", ec="none", alpha=0.35))
    ax.text(4.2, y + h / 2, left, ha="left", va="center", fontsize=11.0, color="white", fontweight="bold")
    ax.text(97.2, y + h / 2, right, ha="right", va="center", fontsize=11.4, color="white", fontweight="bold")

def strip(y, h, color, num, label, right, width=86, dead=False):
    x0 = 7.5
    fc = LIGHT[color] if not dead else "#F2F2F2"
    ax.add_patch(FancyBboxPatch((x0, y), width, h, boxstyle="round,pad=0.1,rounding_size=0.4",
                                fc=fc, ec="none"))
    ax.add_patch(Rectangle((x0, y), 7.4, h, fc=color if not dead else "#9AA3AB", ec="none"))
    ax.text(x0 + 3.7, y + h / 2, num, ha="center", va="center", fontsize=9.8, color="white", fontweight="bold")
    ax.text(x0 + 9.4, y + h / 2, label, ha="left", va="center", fontsize=10.2,
            color="#333333" if not dead else "#777777")
    ax.text(x0 + width - 1.2, y + h / 2, right, ha="right", va="center", fontsize=10.4,
            color=color if not dead else "#8A2020", fontweight="bold")
    ax.plot([x0, x0 + width], [y - 0.35, y - 0.35], ls=":", lw=0.8, color="#8899AA")

y = 100.0
BH, SH, GAP, SGAP = 4.9, 3.72, 1.1, 0.5

# --- S0 共通の関所 ---
c = F["common"]
y -= BH
banner(y, BH, GRAY, "スクリーニング0：共通の関所（全銘柄共通の出発点）", f"{_n(F['n_nonfin'])}社 → {_n(F['n_base'])}社")
rows0 = [("0-1", "金融を除く普通株（価格データあり）", f"{_n(c[0]['n'])}社"),
         ("0-2", "投資適格＋流動性（60日平均売買代金）", f"→ {_n(F['n_eligible'])}社"),
         ("0-3", "価格履歴3年＝過去へ当てて検証できる", f"→ {_n(F['n_base'])}社")]
for i, (num, lab, r) in enumerate(rows0):
    y -= (SH + SGAP)
    strip(y, SH, GRAY, num, lab, r, width=86 - i * 3)
y -= GAP

# --- S1 守 ---
sh = F["shu"]["steps"]
y -= BH
banner(y, BH, NAVY, "スクリーニング1：守 ― 完成した堀（品質の七関門）", f"{_n(F['n_base'])}社 → 5社")
rows1 = [("1-1", "品質の七関門（高収益・堀・財務・無赤字・現金・非縮小）",
          f"{_n(sh[0]['n'])} →…→ {_n(F['shu']['n_quality'])}社"),
         ("1-7", "価格ランク可能（時価総額データあり）", f"→ {_n(F['shu']['n_priceable'])}社"),
         ("1-8", "割安×優良の複合順位＋同一業種2社まで", "→ 5社に固定")]
for i, (num, lab, r) in enumerate(rows1):
    y -= (SH + SGAP)
    strip(y, SH, NAVY, num, lab, r, width=86 - i * 4)
y -= GAP

# --- S2 破 ---
ha = F["ha"]["steps"]
y -= BH
banner(y, BH, TEAL, "スクリーニング2：破 ― 変わる堀（割安×変革）", f"{_n(F['n_base'])}社 → 5社")
rows2 = [("2-1", "変わる堀に分類（変革の点数）", f"→ {_n(ha[0]['n'])}社"),
         ("2-2", "黒字（営業利益・純利益プラス）", f"→ {_n(ha[1]['n'])}社"),
         ("2-3", "最低限の収益性 ＲＯＥ≧5％", f"→ {_n(ha[2]['n'])}社"),
         ("2-4", "変わる堀の点数の上位＋同一業種2社まで", "→ 5社")]
for i, (num, lab, r) in enumerate(rows2):
    y -= (SH + SGAP)
    strip(y, SH, TEAL, num, lab, r, width=86 - i * 4)
y -= GAP

# --- S3 離 ---
ri = F["ri"]
y -= BH
banner(y, BH, GOLD, "スクリーニング3：離 ― 生まれる堀（ＡＩ・半導体の実需）", f"{_n(F['n_base'])}社 → 5社")
y -= (SH + SGAP)
strip(y, SH, GOLD, "3-1", f"キーワードの点数は使わない（{_n(ri['keyword_path']['tie_n'])}社が同点＝選別不能）",
      "× 経路を破棄", width=86, dead=True)
y -= (SH + SGAP)
strip(y, SH, GOLD, "3-2", "事業セグメント開示でＡＩ・半導体の実需を確認", f"→ {ri['verified_path'][0]['n']}社", width=82)
y -= (SH + SGAP)
strip(y, SH, GOLD, "3-3", "適格ガード（黒字・ＲＯＥ≧5％・流動性・履歴3年）", "→ 5社", width=78)
y -= GAP

# --- S4 両立・分散 ---
y -= BH
banner(y, BH, SLATE, "スクリーニング4：両立型・分散役（支え役）", f"適格プール → 3社＋2社")
y -= (SH + SGAP)
strip(y, SH, SLATE, "4-1", "両立型＝現在の堀×未来の堀の両順位が上位", f"{_n(F['dual']['pool_n'])}社 → 3社", width=86)
y -= (SH + SGAP)
strip(y, SH, SLATE, "4-2", "分散役＝20社で未使用の業種から総合点上位", f"{_n(F['bridge']['pool_n'])}社 → 2社", width=82)
y -= GAP * 1.2

# --- 合流 ---
y -= (BH + 0.8)
ax.add_patch(FancyBboxPatch((1.2, y), 97.6, BH + 0.8, boxstyle="round,pad=0.12,rounding_size=0.5",
                            fc="#0F2438", ec="none"))
ax.text(50, y + (BH + 0.8) / 2, "最終ポートフォリオ 20社 ＝ 守5 ＋ 破5 ＋ 離5 ＋ 両立型3 ＋ 分散役2",
        ha="center", va="center", fontsize=12.6, color="white", fontweight="bold")
plt.tight_layout(pad=0.25)
fig.savefig(A / "fig2_overview_v9.png", dpi=200, facecolor="white")
plt.close(fig)

# ============ fig2_shu_v9 守の階段ファネル ============
steps = [("適格（共通の関所）", F["n_base"], "#7A8CA0")]
for st in F["shu"]["steps"][:6]:
    steps.append((st["label"].replace("≥", "≧"), st["n"], NAVY))
steps.append(("価格ランク可能", F["shu"]["n_priceable"], "#3D5A7A"))
steps.append(("完成した堀 Top5（固定）", 5, "#B8862B"))
fig, ax = plt.subplots(figsize=(7.4, 4.5), dpi=200)
ax.set_xlim(0, 100); ax.set_ylim(0, len(steps) + 0.4); ax.axis("off")
import math
maxn = F["n_base"]
for i, (lab, n, col) in enumerate(steps):
    yy = len(steps) - 1 - i
    w = 12 + 74 * (math.log10(max(n, 1)) / math.log10(maxn))
    ax.add_patch(FancyBboxPatch((13, yy + 0.14), w, 0.74, boxstyle="round,pad=0.06,rounding_size=0.18",
                                fc=col, ec="none", alpha=0.94 if i else 0.75))
    ax.text(13 + 1.2, yy + 0.51, lab, ha="left", va="center", fontsize=10.6, color="white", fontweight="bold")
    ax.text(13 + w + 1.4, yy + 0.51, f"{n:,}社", ha="left", va="center", fontsize=11.6,
            color=col, fontweight="bold")
    ax.text(11.5, yy + 0.51, f"1-{i}" if 0 < i <= 6 else ("" if i == 0 else ("1-7" if i == 7 else "1-8")),
            ha="right", va="center", fontsize=9.6, color="#666666")
plt.tight_layout(pad=0.3)
fig.savefig(A / "fig2_shu_v9.png", dpi=200, facecolor="white")
plt.close(fig)

# ============ fig2_ha_v9 破のミニファネル ============
ha = F["ha"]["steps"]
hsteps = [("適格（共通の関所）", F["n_base"], "#7A8CA0"),
          ("変わる堀に分類（変革の点数）", ha[0]["n"], TEAL),
          ("黒字（営業利益・純利益）", ha[1]["n"], TEAL),
          ("最低限の収益性 ＲＯＥ≧5％", ha[2]["n"], TEAL),
          ("点数上位＋業種上限2", 5, "#B8862B")]
fig, ax = plt.subplots(figsize=(7.4, 3.1), dpi=200)
ax.set_xlim(0, 100); ax.set_ylim(0, len(hsteps) + 0.4); ax.axis("off")
for i, (lab, n, col) in enumerate(hsteps):
    yy = len(hsteps) - 1 - i
    w = 12 + 74 * (math.log10(max(n, 1)) / math.log10(F["n_base"]))
    ax.add_patch(FancyBboxPatch((13, yy + 0.14), w, 0.74, boxstyle="round,pad=0.06,rounding_size=0.18",
                                fc=col, ec="none", alpha=0.94 if i else 0.75))
    ax.text(13 + 1.2, yy + 0.51, lab, ha="left", va="center", fontsize=10.6, color="white", fontweight="bold")
    ax.text(13 + w + 1.4, yy + 0.51, f"{n:,}社", ha="left", va="center", fontsize=11.6, color=col, fontweight="bold")
    if i: ax.text(11.5, yy + 0.51, f"2-{i}", ha="right", va="center", fontsize=9.6, color="#666666")
plt.tight_layout(pad=0.3)
fig.savefig(A / "fig2_ha_v9.png", dpi=200, facecolor="white")
plt.close(fig)

# ============ fig2_ri_v9 離の分岐図 ============
ri = F["ri"]
fig, ax = plt.subplots(figsize=(7.4, 3.7), dpi=200)
ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")
# 起点(左上)
ax.add_patch(FancyBboxPatch((2, 44), 28, 10, boxstyle="round,pad=0.2,rounding_size=1.2", fc="#7A8CA0", ec="none"))
ax.text(16, 49, f"適格 {_n(F['n_base'])}社\n（共通の関所）", ha="center", va="center", fontsize=10.2, color="white", fontweight="bold")
# 破棄経路(右上)
ax.annotate("", xy=(38, 49), xytext=(30, 49), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#999999"))
ax.add_patch(FancyBboxPatch((38, 44), 60, 10, boxstyle="round,pad=0.2,rounding_size=1.2", fc="#F4F4F4", ec="#BBBBBB", lw=1))
ax.text(41, 51.2, f"3-1　キーワードの点数（未来分類 全上場{_n(ri['keyword_path']['fm_category_all'])}社・適格内{_n(ri['keyword_path']['fm_category_base'])}社）", ha="left", va="center", fontsize=9.4, color="#555555", fontweight="bold")
ax.text(41, 46.8, f"全上場で{_n(ri['keyword_path']['tie_n'])}社が同点＝点数では選別できない", ha="left", va="center", fontsize=9.8, color="#8A2020")
ax.text(96.4, 46.8, "× 破棄", ha="right", va="center", fontsize=11.0, color="#8A2020", fontweight="bold")
# 同点の例(破棄ボックスの直下・グレー)
ax.text(41, 40.0, "同点の例：火災報知機・時計・鉄道信号の会社が、半導体マスク検査で世界唯一の\nレーザーテックと同点（社名・業種へのキーワード照合が生む飽和）",
        ha="left", va="center", fontsize=8.8, color="#666666")
# 採用経路(左から下へ)
ax.annotate("", xy=(30, 27), xytext=(16, 44), arrowprops=dict(arrowstyle="-|>", lw=2.0, color=GOLD,
                                                              connectionstyle="angle,angleA=-90,angleB=180,rad=5"))
ax.add_patch(FancyBboxPatch((30, 21), 68, 12, boxstyle="round,pad=0.2,rounding_size=1.2", fc=LIGHT[GOLD], ec=GOLD, lw=1.2))
ax.text(33, 29.6, "3-2　事業セグメントの開示でＡＩ・半導体の実需を確認する", ha="left", va="center", fontsize=10.2, color="#333333", fontweight="bold")
ax.text(33, 25.0, f"→ 実需を確認できた {ri['verified_path'][0]['n']}社（うち予備2社）", ha="left", va="center", fontsize=10.2, color=GOLD, fontweight="bold")
# 適格ガード→5社(下段・全幅)
ax.annotate("", xy=(64, 13), xytext=(64, 21), arrowprops=dict(arrowstyle="-|>", lw=2.0, color=GOLD))
ax.add_patch(FancyBboxPatch((2, 3.5), 96, 9, boxstyle="round,pad=0.2,rounding_size=1.2", fc=GOLD, ec="none"))
ax.text(50, 8, "3-3　適格ガード（黒字・ＲＯＥ≧5％・流動性・履歴3年）→ 生まれる堀 5社に確定",
        ha="center", va="center", fontsize=10.8, color="white", fontweight="bold")
plt.tight_layout(pad=0.3)
fig.savefig(A / "fig2_ri_v9.png", dpi=200, facecolor="white")
plt.close(fig)

for f in ["fig2_overview_v9", "fig2_shu_v9", "fig2_ha_v9", "fig2_ri_v9"]:
    from PIL import Image
    im = Image.open(A / f"{f}.png")
    print(f, im.size, f"{im.size[0]/200*25.4:.0f}x{im.size[1]/200*25.4:.0f}mm")
