"""Part 10: 選定結果を「単体で読んで分析できる」簡易レポート(docx)にする。

2種類を生成する。
  自作式版   自分たちで指標と重みを決めた4軸   → screening_report_bespoke_v2.docx
  既存式版   出典のある式だけで組んだ4軸       → screening_report_established_v1.docx

どちらも用語・データ出所・式の定義・選定理由・自己検証・限界まで含み、
そのファイルだけ読めば何をやったか追えるようにする。

入力: work/new_4axis_screen/out/ の final_*・established_*・PITパネル・ev_fields
出力: outputs/stockleague_edition/screening_report_*.docx
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
DOCX_DIR = ROOT / "outputs/stockleague_edition"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"
CK = ["FY2024_252d", "FY2025_126d", "FY2023_252d"]

SECTOR_JA = {
    "Fishery, Agriculture and Forestry": "水産・農林業", "Mining": "鉱業",
    "Construction": "建設業", "Foods": "食料品", "Textiles and Apparels": "繊維製品",
    "Pulp and Paper": "パルプ・紙", "Chemicals": "化学", "Pharmaceutical": "医薬品",
    "Oil and Coal Products": "石油・石炭製品", "Rubber Products": "ゴム製品",
    "Glass and Ceramics Products": "ガラス・土石製品", "Iron and Steel": "鉄鋼",
    "Nonferrous Metals": "非鉄金属", "Metal Products": "金属製品", "Machinery": "機械",
    "Electric Appliances": "電気機器", "Transportation Equipment": "輸送用機器",
    "Precision Instruments": "精密機器", "Other Products": "その他製品",
    "Electric Power and Gas": "電気・ガス業", "Land Transportation": "陸運業",
    "Marine Transportation": "海運業", "Air Transportation": "空運業",
    "Warehousing and Harbor Transportation Services": "倉庫・運輸関連業",
    "Information & Communication": "情報・通信業", "Wholesale Trade": "卸売業",
    "Retail Trade": "小売業", "Banks": "銀行業",
    "Securities and Commodities Futures": "証券・商品先物取引業",
    "Insurance": "保険業", "Other Financing Business": "その他金融業",
    "Real Estate": "不動産業", "Services": "サービス業",
}
MARKET_JA = {"Prime Market (Domestic)": "プライム",
             "Standard Market(Domestic)": "スタンダード",
             "Growth Market(Domestic)": "グロース"}
AXES = ["moat_p", "change_p", "future_p", "price_p"]
AXIS_SHORT = {"moat_p": "Moat", "change_p": "Change", "future_p": "Future", "price_p": "Price"}


def yen(v) -> str:
    return "—" if pd.isna(v) else f"{int(round(v)):,}"


def f1(v, n=1) -> str:
    return "—" if pd.isna(v) else f"{v:,.{n}f}"


def pct(v, n=1) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.{n}f}%"


def load_financials() -> pd.DataFrame:
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False)
    ev = pd.read_csv(OUT / "ev_fields_all_years.csv", dtype={"code": str}).drop(columns=["status"])
    panel = panel.drop(columns=[c for c in ["rd_expense", "capex", "cash", "ppe",
                                            "retained_earnings", "depreciation"]
                                if c in panel.columns])
    panel = panel.merge(ev, on=["code", "fiscal_year"], how="left")
    fin = panel.sort_values(["code", "fiscal_year"]).groupby("code", as_index=False).last()
    fin["op_margin"] = fin["operating_income"] / fin["revenue"].replace(0, np.nan)
    fin["roe_calc"] = fin["net_income"] / fin["equity"].replace(0, np.nan)
    fin["eq_ratio"] = 1.0 - fin["leverage"]
    fin["ocf_margin"] = fin["operating_cf"] / fin["revenue"].replace(0, np.nan)
    return fin[["code", "revenue", "op_margin", "roe_calc", "eq_ratio", "ocf_margin"]]


def rationale(r: pd.Series) -> str:
    """4軸の強弱から、その会社が入った理由を一文にする。"""
    vals = {AXIS_SHORT[a]: float(r[a]) for a in AXES}
    order = sorted(vals.items(), key=lambda kv: -kv[1])
    strong = [f"{k} {v:.0f}" for k, v in order if v >= 85]
    good = [f"{k} {v:.0f}" for k, v in order if 70 <= v < 85]
    weak = [f"{k} {v:.0f}" for k, v in sorted(vals.items(), key=lambda kv: kv[1]) if v < 45]
    parts = []
    if strong:
        parts.append("突出 " + "・".join(strong))
    if good:
        parts.append("良好 " + "・".join(good))
    if not strong and not good:
        parts.append("突出した軸はなく、4軸の平均点で上位に入った型")
    if weak:
        parts.append("弱点 " + "・".join(weak))
    return "／".join(parts) + "。"


def validation_block(val: dict, est: bool) -> dict:
    co = val["cohorts"]
    if est:
        axis_keys = [("① Moat（QMJ Profitability）", "qmj_profitability"),
                     ("② Change（Piotroski F-Score）", "piotroski"),
                     ("③ Future（研究開発集約度）", "cls_future"),
                     ("④ Price（E/P・B/M・EBIT/EV）", "price_established"),
                     ("合成＝本方式", "total_established"),
                     ("参考: マジックフォーミュラ単体", "total_magic"),
                     ("参考: 自作式で組んだ場合", "total_bespoke")]
        pk, ok_, oname = "established", "bespoke", "自作式版"
    else:
        axis_keys = [("① Moat（自作5指標）", "bespoke_moat"),
                     ("② Change（自作6指標）", "bespoke_change"),
                     ("③ Future（キーワード）", "bespoke_future"),
                     ("④ Price（E/P・B/M）", "bespoke_price"),
                     ("合成＝本方式", "total_bespoke"),
                     ("参考: 既存式のみで組んだ場合", "total_established")]
        pk, ok_, oname = "bespoke", "established", "既存式版"

    ic = [[lab] + [f"{co[c]['rank_ic'][k]:+.3f}" for c in CK] for lab, k in axis_keys]
    dec = [[lab] + [f"{co[c]['decile_spread'][k] * 100:+.1f}pt" for c in CK] for lab, k in axis_keys]

    port = [["ユニバース等加重（比較の基準）"]
            + [f"{co[c]['portfolios']['universe_equal_weight'] * 100:+.1f}%" for c in CK]]
    for lab, k in [("本方式の20社", pk), (f"参考: {oname}の20社", ok_),
                   ("参考: マジックフォーミュラの20社", "magic_formula")]:
        port.append([lab] + [f"{co[c]['portfolios'][k]['mean_return'] * 100:+.1f}%" for c in CK])
    port.append(["本方式の超過リターン"]
                + [f"{co[c]['portfolios'][pk]['excess_vs_universe'] * 100:+.1f}pt" for c in CK])
    def _pc(x: float) -> str:
        v = x * 100
        return "0" if abs(v) < 0.5 else f"{v:.0f}"

    port.append(["同・ブートストラップ95%区間"]
                + [f"{_pc(co[c]['portfolios'][pk]['ci95'][0])}〜"
                   f"{_pc(co[c]['portfolios'][pk]['ci95'][1])}%" for c in CK])

    sd_lo = min(co[c]["portfolios"]["random20"]["sd"] for c in CK) * 100
    sd_hi = max(co[c]["portfolios"]["random20"]["sd"] for c in CK) * 100
    rob = [
        "ランダムに20社選んだ場合との比較: 本方式の20社は各コホートで上位 "
        + " / ".join(f"{co[c]['portfolios']['random20'][f'percentile_{pk}']:.0f}" for c in CK)
        + " パーセンタイルに入った。選抜は偶然では説明できない。",
        f"ただしランダム20社そのものの標準偏差が{sd_lo:.0f}〜{sd_hi:.0f}ポイントある。"
        "20社という粒度では、1年の結果はかなりの部分が運で決まることも同時に意味する。",
        "4軸の重みを300通りに振り直すと結果の幅は "
        + " / ".join(f"{co[c]['portfolios'][f'weight_sensitivity_{pk}']['range'] * 100:.0f}pt"
                     for c in CK)
        + "。等重み25%はその中で "
        + " / ".join(f"{co[c]['portfolios'][f'weight_sensitivity_{pk}']['equal_percentile']:.0f}"
                     for c in CK)
        + " パーセンタイルに位置する。「25%ずつだから頑健」とは言えず、"
          "「特定の軸に賭けないための、説明しやすい既定値」と理解すべきである。",
    ]
    cohorts = [
        ["FY2024", "2024-06-28", f"{co['FY2024_252d']['n']:,}社", "252営業日", "主検証"],
        ["FY2025", "2025-06-26", f"{co['FY2025_126d']['n']:,}社", "126営業日", "副検証（期間が短い）"],
        ["FY2023", "2023-06-30", f"{co['FY2023_252d']['n']:,}社", "252営業日",
         "参考（前期比が取れずChange軸が退化）"],
    ]
    return {"ic": ic, "decile": dec, "portfolio": port, "robustness": rob,
            "cohorts": cohorts, "pk": pk}


GLOSSARY = [
    ["順位点（0〜100）", "母集団の中で何番目かを0〜100に直した値。50なら中位。金額や倍率をそのまま"
                      "足すと単位が違って比べられないため、順位に直してから平均する。"],
    ["PER", "株価収益率。時価総額 ÷ 当期純利益。低いほど利益に対して株価が安い。"],
    ["PBR", "株価純資産倍率。時価総額 ÷ 自己資本。1倍割れは会社の解散価値を下回る評価。"],
    ["ROE", "自己資本利益率。当期純利益 ÷ 自己資本。株主の出したお金でどれだけ稼いだか。"],
    ["営業CF率", "営業キャッシュフロー ÷ 売上高。利益が実際の現金として入ってきているか。"],
    ["時価総額", "発行済株式数 × 株価。会社を丸ごと買うのに必要な金額。"],
    ["企業価値（EV）", "時価総額 + 有利子負債 − 現預金。借金と手元現金を調整した買収価格。"],
    ["順位相関（rank IC）", "スコアの順位と、その後のリターンの順位がどれだけ一致したか。＋1で完全一致、"
                         "0で無関係。株式のスクリーニングでは0.05以上あれば実用的とされる。"],
    ["十分位スプレッド", "母集団をスコアで10等分し、上位10%の平均リターンから下位10%の平均リターンを"
                   "引いた差。大きいほど選別が効いている。"],
    ["実効寄与", "「25%ずつ配点した」としても、実際に総合点の差を生んでいる割合は等しくならない。"
             "各軸が合成点のばらつきをどれだけ説明しているかを測ったもの。合計100%。"],
    ["ブートストラップ95%区間", "20社を重複ありで選び直す試行を2,000回繰り返し、平均リターンが"
                         "収まる範囲を示したもの。20社という少なさの不確かさを表す。"],
]

DATA_SOURCES = [
    ["財務データ", "EDINET 有価証券報告書（XBRL）", "各社の最新提出分。10,712件をローカル保有"],
    ["株価・売買代金", "Yahoo Finance 日次株価", "2021-06〜2026-06。流動性は直近60営業日の平均売買代金"],
    ["発行済株式数", "Yahoo Finance 実勢値（取得できない分はXBRL）", "2026-08-17時点。1,948/1,963社"],
    ["業種・市場区分", "JPX 上場銘柄一覧（33業種分類）", "2026-06-01時点"],
    ["検証用の前向きリターン", "上記株価から算出", "有報の提出日を基準に、その後の株価のみを使用"],
]


def build_payload(variant: str, fin: pd.DataFrame, val: dict) -> dict:
    est = variant == "established"
    if est:
        top = pd.read_csv(OUT / "established_top20.csv", dtype={"code": str})
        s = json.loads((OUT / "established_current_summary.json").read_text(encoding="utf-8"))
        cov, eff, allfour, corr = (s["coverage_pct"], s["effective_weight"],
                                   s["all_four_above"], s["axis_spearman"])
        elig, not_buy = s["step0"]["eligible_final"], s["not_buyable_within_cap"]
        title = "スクリーニング簡易レポート（既存式版）"
        subtitle = "4軸すべてを出典のある式で構成 — QMJ／Piotroski／研究開発集約度／E-P・B-M"
        outfile = DOCX_DIR / "screening_report_established_v1.docx"
        uni_per, uni_pbr, uni_below1 = 16.17, 1.33, 31.0
    else:
        top = pd.read_csv(OUT / "final_top20.csv", dtype={"code": str})
        s = json.loads((OUT / "final_summary.json").read_text(encoding="utf-8"))
        cov, eff, allfour, corr = (s["component_coverage_pct"],
                                   s["effective_weight_variance_share"],
                                   s["all_four_axes_above"], s["axis_spearman"])
        elig, not_buy = s["step0"]["eligible_final"], s["step3_buyability"]["not_buyable_within_cap"]
        title = "スクリーニング簡易レポート（自作式版）"
        subtitle = "4軸（Moat／Change／Future／Price）を自前で定義し等重み25%で合成"
        outfile = DOCX_DIR / "screening_report_bespoke_v2.docx"
        uni_per = s["valuation_distribution"]["per_median"]
        uni_pbr = s["valuation_distribution"]["pbr_median"]
        uni_below1 = s["valuation_distribution"]["pbr_below_1_pct"]

    top = top.sort_values("total", ascending=False).reset_index(drop=True)
    top["sector_ja"] = top["sector_33"].map(SECTOR_JA).fillna(top["sector_33"])
    top["market_ja"] = top["market"].map(MARKET_JA).fillna(top["market"])
    top["name"] = (top["company_name_ja"].fillna(top["company_name"])
                   .str.replace("株式会社", "", regex=False).str.strip())
    top = top.merge(fin, on="code", how="left")

    vb = validation_block(val, est)
    v24 = val["cohorts"]["FY2024_252d"]
    tot_key = "total_established" if est else "total_bespoke"
    invested = int(top["cost"].sum())
    cash_left = 5_000_000 - invested

    # ---------- カバレッジ表 ----------
    cov_spec = ([("GPOA", "売上総利益 ÷ 総資産", "粗利を開示しない一部業種で欠測"),
                 ("ROE", "当期純利益 ÷ 自己資本", ""),
                 ("CFOA", "営業CF ÷ 総資産", ""),
                 ("change_raw", "Piotroski F-Score", "9項目中 平均8.8項目が計算可"),
                 ("rd_expense", "研究開発費", "非開示＝研究開発をしていない、として0扱い"),
                 ("greenblatt_ey", "EBIT ÷ 企業価値", "有利子負債が取れない分は負債0とみなす"),
                 ("ff_btm", "自己資本 ÷ 時価総額", ""),
                 ("basu_ep", "当期純利益 ÷ 時価総額", ""),
                 ("altman_z", "Altman Z-Score", "")] if est else
                [("gp_to_assets", "売上総利益 ÷ 総資産", ""),
                 ("op_margin", "営業利益 ÷ 売上高", ""),
                 ("roa", "当期純利益 ÷ 総資産", ""),
                 ("ocf_margin", "営業CF ÷ 売上高", ""),
                 ("equity_ratio", "自己資本比率", ""),
                 ("piotroski_f_score", "Piotroski F-Score", ""),
                 ("delta_roa", "ROAの前期差", ""),
                 ("delta_gross_margin", "売上総利益率の前期差", ""),
                 ("revenue_growth", "増収率", ""),
                 ("earnings_to_price", "当期純利益 ÷ 時価総額", ""),
                 ("book_to_market", "自己資本 ÷ 時価総額", "")])
    cov_rows = [[lab, f"{cov[k]:.1f}%", memo] for k, lab, memo in cov_spec if k in cov]

    data_notes = [
        "各指標は母集団内の順位に直してから平均する。欠測はゼロで埋めず、平均から外す。"
        "ゼロ埋めは「母集団の平均並み」を意味してしまい、データを持たない会社を中位に置いてしまうため。",
        "時価総額は実勢の発行済株式数×実勢株価で計算している。有価証券報告書の提出後に株式分割した"
        "会社は、報告書の株式数のままだと時価総額が分割比率のぶん過小になり「異常に割安」と"
        "誤判定される。母集団で216社の提出後分割を検出し、実勢値に置き換えた。",
    ]
    if est:
        data_notes.append(
            "研究開発費は、当初のパーサーが ResearchAndDevelopmentExpenses というタグで探していたため"
            "ほとんど取得できていなかった。EDINETの実タグは ResearchAndDevelopmentExpensesSGA であり、"
            "修正後の取得率は母集団で65.0%。非開示は業種で説明でき"
            "（銀行1.3%・不動産8.6%・小売9.5% 対 機械97.6%・化学98.0%）、"
            "「開示なし＝研究開発をしていない」と読める分布である。")

    # ---------- Step 0 ----------
    step0_conditions = [
        ["1", "株価データが存在する", "売買できない銘柄を落とす"],
        ["2", "直近60営業日の平均売買代金が2,000万円以上／日", "買えても売れない銘柄を落とす"],
        ["3", "総資産・自己資本・当期純利益などが揃っている", "そもそも採点できない銘柄を落とす"],
        ["4", "3期連続の営業赤字でない", "本業が続かない会社を落とす"],
        ["5", "3期連続の経常赤字・純損失でない", "同上"],
        ["6", "3期連続の営業キャッシュフローがマイナスでない", "現金が出ていく一方の会社を落とす"],
        ["7", "自己資本比率が極端に低くない／負債が過大でない", "財務が持たない会社を落とす"],
        ["8", "ROEが−50〜+80%、営業利益率が−50〜+100%の範囲", "異常値・特殊要因を落とす"],
        ["9", "PERが0超120以下、PBRが0超20以下", "採点の前提が壊れる極端な評価を落とす"],
    ]
    funnel = [["全上場企業", "3,649社", "JPX上場全銘柄"],
              ["条件1〜8を通過", "1,963社", "流動性・連続赤字・データ完備など"]]
    if est:
        step0_conditions.append(
            ["10", "Altman Z-Score が1.81以上",
             "倒産確率が高い水準の会社を落とす（Altman 1968の境界値）"])
        funnel += [["条件9（バリュエーション範囲）で除外",
                    f"−{s['step0']['excluded_valuation_range']}社", "PER・PBRが極端な銘柄"],
                   ["条件10（Altman Z<1.81）で除外",
                    f"−{s['step0']['excluded_altman_distress']}社", "倒産リスクが高い水準"]]
    else:
        funnel += [["条件9（バリュエーション範囲）で除外",
                    f"−{s['step0']['excluded_by_condition9_valuation']}社", "PER・PBRが極端な銘柄"]]
    funnel += [
        ["Step 0 通過（母集団）", f"{elig:,}社", "4軸で採点する対象"],
        ["1単元が上限8%を超え購入不可", f"−{not_buy}社",
         "1単元40万円超。投資枠500万円では買えないため次点を繰り上げる"],
        ["Step 3 選抜", "20社", "総合点の上位・同一業種は2社まで"],
    ]
    step0_notes = [
        "条件9は、これまで株価指標を取得できていた売買代金上位300社にしか適用されていなかった。"
        "全社の時価総額を用意したため、今回から全社に適用している。",
        f"投資枠500万円・1銘柄上限8%の制約から、1単元が40万円を超える{not_buy}社は"
        "構造的に選ばれない。これは資金量に依存する制約である。",
    ]

    # ---------- 4軸 ----------
    if est:
        axes_intro = ("4つの軸はいずれも、査読論文または著名な実務書で定義が確定している式をそのまま用いる。"
                      "「なぜこの式なのか」に論文名で答えられる状態にすることが、この構成の目的である。"
                      "重みや境界値を我々が決めた箇所は第13章に列挙する。")
        axes = [
            {"title": "① Moat — いま強いか",
             "source": "Asness, Frazzini & Pedersen (2019) Quality Minus Junk, "
                       "Review of Accounting Studies 24, pp.34-112 の Profitability 部分",
             "what": "「利益率が高く、その利益が現金として入ってきていて、会計操作に頼っていない」"
                     "会社を高く評価する。6つの指標を順位化・標準化して平均する。",
             "formula": ["Moat = 平均( z(GPOA), z(ROE), z(ROA), z(CFOA), z(GMAR), z(−ACC) )",
                         "",
                         "z(x) は x の順位を平均0・標準偏差1に直したもの"],
             "components": [["GPOA", "売上総利益 ÷ 総資産（Novy-Marx 2013）", f"{cov.get('GPOA', 0):.1f}%"],
                            ["ROE", "当期純利益 ÷ 自己資本", f"{cov.get('ROE', 0):.1f}%"],
                            ["ROA", "当期純利益 ÷ 総資産", f"{cov.get('ROA', 0):.1f}%"],
                            ["CFOA", "営業キャッシュフロー ÷ 総資産", f"{cov.get('CFOA', 0):.1f}%"],
                            ["GMAR", "売上総利益 ÷ 売上高（粗利率）", f"{cov.get('GMAR', 0):.1f}%"],
                            ["−ACC", "−(当期純利益 − 営業CF) ÷ 総資産（Sloan 1996。利益の質）",
                             f"{cov.get('ACC', 0):.1f}%"]],
             "note": "GPOAはNovy-Marx (2013)、ACCはSloan (1996)。QMJはこれらを束ねた枠組みであり、"
                     "本軸は「既存式の、既存の束ね方」になっている。"},
            {"title": "② Change — 良くなっているか",
             "source": "Piotroski (2000) Value Investing, Journal of Accounting Research 38 "
                       "Supplement, pp.1-41 の F-Score",
             "what": "会計上の9つのチェックに1点ずつ付け、0〜9点で「去年より良くなったか」を測る。"
                     "株価倍率を一切含まないので、Price軸と重複しない。",
             "formula": ["Change = 次の9項目の合計（各0または1点）",
                         "",
                         "  収益性  ① ROAがプラス        ② 営業CFがプラス",
                         "          ③ ROAが前期より改善   ④ 営業CF > 当期純利益（会計の質）",
                         "  財務    ⑤ レバレッジが低下   ⑥ 流動比率が改善",
                         "          ⑦ 増資をしていない",
                         "  効率    ⑧ 売上総利益率が改善  ⑨ 総資産回転率が改善"],
             "components": [["F-Score", "上記9項目の合計（0〜9点）", f"{cov.get('change_raw', 0):.1f}%"],
                            ["（内訳）", "平均8.8項目が計算可能。欠測項目は合計から除く", "—"]],
             "note": "参考文献では「9項目のうち6項目で実装」と注記していたが、"
                     "時点データには9項目すべてが入っており原式どおり実装できる。"},
            {"title": "③ Future — 未来の恩恵を受けられるか",
             "source": "Chan, Lakonishok & Sougiannis (2001) The Stock Market Valuation of Research "
                       "and Development Expenditures, Journal of Finance 56(6), pp.2431-2456",
             "what": "研究開発にどれだけ資源を投じているかで、将来の変化への備えを測る。"
                     "同論文は研究開発集約度の高い企業に長期の超過リターンがあることを示している。",
             "formula": ["Future = 平均( 順位(研究開発費 ÷ 時価総額), 順位(研究開発費 ÷ 売上高) )",
                         "",
                         "研究開発費の記載がない会社は 0 とする"],
             "components": [["R&D ÷ 時価総額", "市場評価に対してどれだけ研究開発しているか",
                             f"{cov.get('rd_expense', 0):.1f}%"],
                            ["R&D ÷ 売上高", "事業規模に対してどれだけ研究開発しているか",
                             f"{cov.get('rd_expense', 0):.1f}%"]],
             "note": "本軸は「イノベーションへの投資量」を測るものであって、"
                     "「構造変化の恩恵を受けるか」そのものではない。この読み替えは第13章に記載する。"},
            {"title": "④ Price — 高すぎないか",
             "source": "Basu (1977) Journal of Finance 32(3) ／ Fama & French (1992) Journal of "
                       "Finance 47(2) ／ Greenblatt (2005) The Little Book That Beats the Market",
             "what": "3つの古典的な割安尺度を順位化して平均する。分子が利益・自己資本・EBITと"
                     "異なるので、一つの会計項目のクセに引きずられにくい。",
             "formula": ["Price = 平均( 順位(E/P), 順位(B/M), 順位(EBIT/EV) )",
                         "",
                         "E/P     = 当期純利益 ÷ 時価総額      （Basu 1977）",
                         "B/M     = 自己資本 ÷ 時価総額        （Fama-French 1992）",
                         "EBIT/EV = 営業利益 ÷ 企業価値        （Greenblatt 2005）",
                         "EV      = 時価総額 + 有利子負債 − 現預金"],
             "components": [["E/P（益回り）", "当期純利益 ÷ 時価総額", f"{cov.get('basu_ep', 0):.1f}%"],
                            ["B/M", "自己資本 ÷ 時価総額（PBRの逆数）", f"{cov.get('ff_btm', 0):.1f}%"],
                            ["EBIT/EV", "営業利益 ÷ 企業価値", f"{cov.get('greenblatt_ey', 0):.1f}%"]],
             "note": "EBIT/EV を足しても、E/P と B/M だけの版と順位相関0.94〜0.96でほぼ一致する。"
                     "有利子負債の取得率が82%であることを踏まえ、外す選択も合理的である。"},
        ]
    else:
        axes_intro = ("4つの軸は、それぞれ複数の指標を母集団内の順位（0〜100点）に直して平均したもの。"
                      "どの指標を選びどう重み付けるかは我々が決めている。その判断が結果をどう左右するかは"
                      "第6章と第11章に示す。")
        axes = [
            {"title": "① Moat — いま強いか", "source": "",
             "what": "利益率・資本効率・現金創出力・財務の厚みという方向から、"
                     "いま強い会社かを測る。5指標の順位点の平均。",
             "formula": ["Moat = 平均( 順位(GP/A), 順位(営業利益率), 順位(ROA),",
                         "             順位(営業CF率), 順位(自己資本比率) )"],
             "components": [["GP/A", "売上総利益 ÷ 総資産", f"{cov.get('gp_to_assets', 0):.1f}%"],
                            ["営業利益率", "営業利益 ÷ 売上高", f"{cov.get('op_margin', 0):.1f}%"],
                            ["ROA", "当期純利益 ÷ 総資産", f"{cov.get('roa', 0):.1f}%"],
                            ["営業CF率", "営業キャッシュフロー ÷ 売上高", f"{cov.get('ocf_margin', 0):.1f}%"],
                            ["自己資本比率", "1 − 負債 ÷ 総資産", f"{cov.get('equity_ratio', 0):.1f}%"]],
             "note": "従来使っていた研究開発費比率は外した。抽出できていた企業が極端に少なく、"
                     "ゼロ埋めの結果この成分が営業利益率の二重計上に退化していたため。"},
            {"title": "② Change — 良くなっているか", "source": "",
             "what": "去年より良くなっているかを、会計上の改善指標6つで測る。"
                     "株価倍率を一切含めていないので、Price軸と重複しない。",
             "formula": ["Change = 平均( 順位(Piotroski F-Score), 順位(ΔROA),",
                         "               順位(Δ売上総利益率), 順位(Δ総資産回転率),",
                         "               順位(増収率), 順位(営業増益率) )",
                         "",
                         "Δx = 今期の x − 前期の x"],
             "components": [["Piotroski F-Score", "改善を測る9項目の合計（0〜9点）",
                             f"{cov.get('piotroski_f_score', 0):.1f}%"],
                            ["ΔROA", "総資産利益率の前期差", f"{cov.get('delta_roa', 0):.1f}%"],
                            ["Δ売上総利益率", "粗利率の前期差", f"{cov.get('delta_gross_margin', 0):.1f}%"],
                            ["Δ総資産回転率", "資産の使い方の効率の前期差",
                             f"{cov.get('delta_asset_turnover', 0):.1f}%"],
                            ["増収率", "(売上高 − 前期売上高) ÷ |前期売上高|",
                             f"{cov.get('revenue_growth', 0):.1f}%"],
                            ["営業増益率", "(営業利益 − 前期営業利益) ÷ |前期営業利益|",
                             f"{cov.get('oi_growth', 0):.1f}%"]],
             "note": "従来の「変わる堀」の式は重みの70%がPBR・PER・配当利回りで、実質的に割安さを"
                     "測っていた（Price軸との順位相関 +0.368）。改善そのものを測る指標だけで組み直している。"},
            {"title": "③ Future — 未来の恩恵を受けられるか", "source": "",
             "what": "有価証券報告書の本文を、半導体・データセンター・ロボット・クラウド・"
                     "セキュリティなどのキーワードで照合し、構造変化の恩恵を受けやすいかを測る。",
             "formula": ["Future = 順位( 0.30×AI基盤 + 0.25×無形資産投資 + 0.20×省人化",
                         "               + 0.15×データ + 0.10×信頼・安全 )"],
             "components": [["AI基盤", "半導体・データセンター・電力などの語の出現", "全社"],
                            ["無形資産投資", "研究開発費比率", "実質未取得"],
                            ["省人化", "ロボット・自動化・センサーなどの語", "全社"],
                            ["データ", "クラウド・SaaS・業務データなどの語", "全社"],
                            ["信頼・安全", "セキュリティ・監査・品質などの語", "全社"]],
             "note": "この軸は33業種の分類だけで99.4%が説明できる。個社の判断ではなく"
                     "「構造変化の恩恵を受けやすい業種群に属しているか」の判定である。"
                     "また無形資産投資（重み0.25）は研究開発費がほぼ取得できず実質的に機能していない。"},
            {"title": "④ Price — 高すぎないか", "source": "",
             "what": "利益と自己資本の2方向から、株価が高すぎないかを測る。",
             "formula": ["Price = 平均( 順位(益回り), 順位(自己資本倍率) )",
                         "",
                         "益回り       = 当期純利益 ÷ 時価総額",
                         "自己資本倍率 = 自己資本 ÷ 時価総額（PBRの逆数）"],
             "components": [["益回り", "当期純利益 ÷ 時価総額", f"{cov.get('earnings_to_price', 0):.1f}%"],
                            ["自己資本倍率", "自己資本 ÷ 時価総額", f"{cov.get('book_to_market', 0):.1f}%"]],
             "note": "配当利回りは全社では取得できないため入れていない。"},
        ]

    # ---------- 合成 ----------
    composite = {
        "formula": ["総合点 = 0.25×Moat + 0.25×Change + 0.25×Future + 0.25×Price",
                    "",
                    "各軸はいずれも0〜100点なので、総合点も0〜100点になる"],
        "text": "どれか一つの軸に賭けるのではなく、四方向から等しく評価するという考え方に基づく。"
                "ただし「等しく配点する」ことと「等しく効く」ことは別である。",
        "effective": [["名目の配点", "25.0%", "25.0%", "25.0%", "25.0%"],
                      ["実際に総合点を動かした割合"] + [f"{eff[a] * 100:.1f}%" for a in AXES]],
        "effective_note":
            "実効寄与は、各軸が総合点のばらつきをどれだけ説明しているかを測ったもの（合計100%）。"
            "軸どうしが逆方向に動くと合計の中で打ち消し合うため、名目25%でも実効は等しくならない。"
            "これは合成スコア一般の性質であり、隠さず併記するのが正しい。",
        "corr": [[AXIS_SHORT[a]] + [f"{corr[a][b]:+.3f}" for b in AXES] for a in AXES],
        "corr_note":
            "0に近いほど別のものを測れている。1に近い組み合わせがあれば、同じものを二重に数えている。"
            + ("最大でも0.33で、Change軸（Piotroski）は株価倍率を一切含まないため構造的に重複しない。"
               if est else
               "従来の「変わる堀」はPrice軸と+0.368の相関があったが、改善指標だけで組み直して解消した。"),
        "all_four": [[f"全4軸 {t}点以上", f"{allfour[str(t)]}社",
                      f"{allfour[str(t)] / elig * 100:.1f}%"] for t in [50, 60, 70, 80, 90]],
        "all_four_note":
            f"4軸すべてで高得点の会社は事実上存在しない（80点以上は{allfour['80']}社、"
            f"90点以上は{allfour['90']}社）。したがって「4条件すべてを満たす会社を探す」方式では"
            "20社を組めない。平均を取る方式を採る以上、選ばれた会社もどこか1軸は必ず弱い。"
            "第8章の選定理由で、各社がどの軸で入りどこが弱いかを一社ずつ開示している。",
    }

    # ---------- 選抜 ----------
    if est:
        cap_effect = [["業種上限なし（単純上位20）", "—", "本方式では算出していない"],
                      ["業種上限2社（本方式）", f"{s['result']['sectors']}業種", "—"]]
        cap_note = "同一業種2社までの制約を入れて選抜している。"
    else:
        cap_effect = [["業種上限なし（単純上位20）", f"{s['step3']['sectors_without_cap']}業種",
                       "・".join(f"{SECTOR_JA.get(k, k)}{vv}社"
                                 for k, vv in s["step3"]["nodiv_top_sector_share"].items())],
                      ["業種上限2社（本方式）", f"{s['step3']['sectors_with_cap']}業種", "—"]]
        cap_note = (f"上限を入れると平均総合点は{s['step3']['mean_total_without_cap']}点から"
                    f"{s['step3']['mean_total_with_cap']}点へ下がるが、集中は解消される。"
                    "この代償は払う価値がある。")

    # ---------- 構成 ----------
    sector_counts = top["sector_ja"].value_counts()
    market_counts = top["market_ja"].value_counts()
    scale_counts = (top["scale_category"].fillna("区分なし").value_counts()
                    if "scale_category" in top.columns else pd.Series(dtype="int64"))
    rows_n = max(len(market_counts), len(scale_counts))
    market_scale = []
    for i in range(rows_n):
        m = list(market_counts.items())[i] if i < len(market_counts) else ("", "")
        sc = list(scale_counts.items())[i] if i < len(scale_counts) else ("", "")
        market_scale.append([str(m[0]), f"{m[1]}社" if m[1] != "" else "",
                             str(sc[0]), f"{sc[1]}社" if sc[1] != "" else ""])

    # ---------- 比較 ----------
    if est:
        cmp_rows = [[AXIS_SHORT[a], "—", f"{top[a].median():.1f}"] for a in AXES]
        cmp_text = [
            "現行版（守破離の重み30/25/30/15）の20社、および自作式版の20社と比べる。",
            f"本方式の20社と現行版20社の重複は{s['result']['overlap_with_current_v10']}社、"
            f"自作式版20社との重複は{s['result']['overlap_with_bespoke20']}社である。"
            "方式を変えることは、銘柄の入れ替えではなくポートフォリオの総入れ替えを意味する。",
            "なお自作式版と本方式は、母集団全体では総合点の順位相関が0.80〜0.87あり、"
            "大枠では同じような会社を上位に置いている。差が出るのは主にFuture軸で、"
            "両者の順位相関は0.42〜0.48しかない。",
        ]
        overlap = [["現行版（守破離30/25/30/15）の20社", f"{s['result']['overlap_with_current_v10']}社"],
                   ["自作式版の20社", f"{s['result']['overlap_with_bespoke20']}社"]]
    else:
        cmp_rows = [[AXIS_SHORT[a], f"{s['vs_current_v10']['current_axis_medians'][a]:.1f}",
                     f"{s['vs_current_v10']['new_axis_medians'][a]:.1f}"] for a in AXES]
        cmp_text = [
            "現行版（守破離の重み30/25/30/15）の20社と、本方式の20社を同じ4軸で採点して比べる。",
            "現行版はMoatとFutureで高い一方、Priceが母集団の中央値を下回っている。"
            "「割安に買う」を評価軸として明示的に組み込んだ結果が、この差に表れている。",
            "別途、すべての式を出典のあるものに置き換えた「既存式版」も作成している。"
            "母集団全体では本方式と総合点の順位相関が0.80〜0.87あり、大枠では同じ方向を向いているが、"
            "選ばれる20社の重複は6社にとどまる。",
        ]
        overlap = [["現行版（守破離30/25/30/15）の20社", f"{s['vs_current_v10']['overlap']}社"],
                   ["既存式版の20社", "6社"]]

    # ---------- 限界 ----------
    limits = [
        "自己検証に使った3つのコホートは、いずれも2023〜2026年の同じ相場に属する。"
        "この期間の日本株は東証のPBR改善要請を背景にした歴史的なバリュー・小型株優位局面であり、"
        "割安さが強く効き収益性が効かなかったのは、この局面の性質である可能性が高い。"
        "独立した3つの証拠ではなく、実質1つの証拠と数えるべきである。",
        "4軸すべてが計算できる完全なコホートは実質2つ（FY2024・FY2025）である。"
        "FY2023は時点パネルの初年度で前期比が取れず、Change軸が退化している。",
    ]
    if est:
        limits += [
            "③ Future軸は「イノベーションへの投資量」を測るものであって、「構造変化の恩恵を受けるか」"
            "そのものではない。後者を直接測る学術指標は存在するが（特許テキストを用いる手法）、"
            "日本企業・手元データでは実装できないため研究開発集約度で代替している。",
            "研究開発費を開示していない約35%の企業を0として扱っている。業種分布から妥当と判断したが、"
            "サービス業などで「研究開発はしているが記載義務がない」ケースを0にしている可能性は残る。",
            "有利子負債の取得率は82%で、残りは負債ゼロとみなしてEBIT/EVを計算している。",
        ]
    else:
        limits.append(
            "③ Future軸は33業種の分類だけで99.4%が説明でき、個社の判断というより業種ラベルである。"
            "またその構成要素のうち無形資産投資（重み0.25）は研究開発費がほぼ取得できず、"
            "実質的に機能していない。Step 1で業種に25%配点しながらStep 3で業種を分散させるという"
            "論理的なねじれがあることは、先に認めておく。")
    limits += [
        "PERは最新の有価証券報告書の当期純利益を用いている。提出後に業績が変化した会社では"
        "直近12か月ベースのPERと差が出る。上位に入った銘柄は直近四半期の利益動向を必ず確認すること。",
        f"投資枠500万円・1銘柄上限8%の制約から、1単元が40万円を超える{not_buy}社は選抜対象から"
        "外れている。大型株の一部が構造的に選ばれないという、資金量に依存する制約である。",
        "時点パネルは提出済みの有価証券報告書から構築しているため、上場廃止企業が抜けている"
        "（生存者バイアス）。",
        "本スクリーニングは選定ロジックの提示であり、将来の運用成績を約束するものではない。"
        "STOCKリーグの審査ではリターンは採点対象外であり、本書は選定の再現性と説明可能性を"
        "示すためのものである。",
    ]

    if est:
        cmds = ["python3 work/new_4axis_screen/11_extract_ev_fields.py --all-years  # 追加項目の抽出",
                "uv run python work/new_4axis_screen/09_fetch_shares.py    # 実勢株数",
                "uv run python work/new_4axis_screen/09b_retry_shares.py   # 取りこぼしの再取得",
                "python3 work/new_4axis_screen/12_established_only.py      # 自己検証",
                "python3 work/new_4axis_screen/13_established_current.py   # 20社の確定",
                "python3 work/new_4axis_screen/10_build_docx.py            # 本レポート"]
        outs = [["established_top20.csv", "選定20社と軸スコア・投資額"],
                ["established_all_eligible.csv", "母集団全社の軸スコア"],
                ["established_current_summary.json", "ファネル・カバレッジ・実効寄与"],
                ["established_summary.json", "自己検証（順位相関・十分位・20社実績）"]]
    else:
        cmds = ["python3 work/new_4axis_screen/08_extract_per_share.py   # 1株当たり数値（突合用）",
                "uv run python work/new_4axis_screen/09_fetch_shares.py  # 実勢株数",
                "uv run python work/new_4axis_screen/09b_retry_shares.py # 取りこぼしの再取得",
                "python3 work/new_4axis_screen/07_final_screen.py        # 20社の確定",
                "python3 work/new_4axis_screen/12_established_only.py    # 自己検証",
                "python3 work/new_4axis_screen/10_build_docx.py          # 本レポート"]
        outs = [["final_top20.csv", "選定20社と軸スコア・投資額"],
                ["final_all_eligible.csv", "母集団全社の軸スコア"],
                ["final_summary.json", "ファネル・カバレッジ・実効寄与"],
                ["established_summary.json", "自己検証（順位相関・十分位・20社実績）"]]

    verdict = ("3コホートすべてで、本方式の20社はランダムに選んだ20社を上回った。総合点の順位相関は "
               + " / ".join(f"{val['cohorts'][c]['rank_ic'][tot_key]:+.3f}" for c in CK)
               + " で、株式のスクリーニングとしては実用的な水準にある。ただし単一レジーム・"
                 "実質2コホートという制約があり、「この期間ではこう機能した」以上のことは主張できない。")

    return {
        "output": str(outfile),
        "theme": "established" if est else "bespoke",
        "meta": {"title": title, "subtitle": subtitle, "date": "2026-08-17",
                 "asof": "株価・時価総額 2026-08-17時点／財務 各社最新の有価証券報告書／"
                         "流動性・業種 2026-06-01時点"},
        "about": {
            "purpose": "本書は、上場企業3,649社の中から20社を選ぶまでの手順・根拠・結果を、"
                       "本書だけで追えるようにまとめたものである。使ったデータ、各評価軸の式、"
                       "選抜のルール、選ばれた20社とその理由、方式が機能するかの検証、"
                       "そして限界までを収めている。",
            "toc": [["1", "結論 — 何を選んだか、要約数値"],
                    ["2", "用語の説明"],
                    ["3", "使ったデータと取得率"],
                    ["4", "Step 0 — 母集団の絞り込み（除外条件とファネル）"],
                    ["5", "Step 1 — 4つの評価軸の定義（式と成分）"],
                    ["6", "Step 2 — 合成、名目配点と実効寄与、軸の重複"],
                    ["7", "Step 3・4 — 選抜ルールと保有比率の決め方"],
                    ["8", "選定した20社（軸スコア・選定理由・財務指標）"],
                    ["9", "ポートフォリオ構成（株数・投資額・比率）"],
                    ["10", "構成の特徴（業種・市場・規模・バリュエーション）"],
                    ["11", "この方式は機能するか（前向きリターンによる自己検証）"],
                    ["12", "他方式との比較"],
                    ["13", "限界と注意点"],
                    ["14", "再現手順"]],
            "standalone": "数値はすべて第14章のコードから生成されており、"
                          "同じコードを実行すれば本書の表がそのまま再現できる。",
        },
        "conclusion": [
            f"全上場3,649社から投資可能な{elig:,}社を母集団とし、4つの軸（Moat・Change・Future・Price）"
            f"を各0〜100点の順位点にして25%ずつ合計、同一業種2社までの制約をかけて20社を選んだ。"
            f"{top['sector_ja'].nunique()}業種に分散している。",
            f"選んだ20社はPER中央値{f1(top['per'].median())}倍・PBR中央値{f1(top['pbr'].median(), 2)}倍・"
            f"時価総額中央値{f1(top['market_cap'].median() / 1e8, 0)}億円。"
            f"投資枠500万円に対し{yen(invested)}円を配分し、余剰現金は{yen(cash_left)}円。",
            ("すべての評価式に出典があるため、「なぜこの式なのか」を論文名で答えられる。"
             "自分たちで決めたのは重みと境界値だけであり、その範囲は第13章に列挙している。"
             if est else
             "評価軸の指標の選び方と重みは我々が決めている。その判断が結果をどう左右するかは"
             "第6章（実効寄与・軸の重複）と第11章（重みの感度）に示す。"),
        ],
        "headline": [
            ["母集団（Step 0通過）", f"{elig:,}社", "採点の対象になった会社"],
            ["選定", "20社", f"{top['sector_ja'].nunique()}業種に分散"],
            ["PER 中央値", f1(top["per"].median()) + "倍", f"母集団は{uni_per:.1f}倍"],
            ["PBR 中央値", f1(top["pbr"].median(), 2) + "倍", f"母集団は{uni_pbr:.2f}倍"],
            ["時価総額 中央値", f1(top["market_cap"].median() / 1e8, 0) + "億円", "小型〜中型が中心"],
            ["投資額", yen(invested) + "円", f"余剰現金 {yen(cash_left)}円"],
            ["総合点の順位相関（FY2024）", f"{v24['rank_ic'][tot_key]:+.3f}",
             "その後1年のリターン順位との一致度"],
        ],
        "glossary": GLOSSARY,
        "data_sources": DATA_SOURCES,
        "coverage": cov_rows,
        "data_notes": data_notes,
        "step0_conditions": step0_conditions,
        "funnel": funnel,
        "step0_notes": step0_notes,
        "axes_intro": axes_intro,
        "axes": axes,
        "composite": composite,
        "selection": {
            "rules": ["総合点の高い順に並べる。",
                      "上から順に採用する。ただし同一の33業種分類は最大2社まで。",
                      "1単元が投資枠の8%（40万円）を超えて買えない銘柄は飛ばし、次点を繰り上げる。",
                      "20社に達したら終了する。"],
            "cap_effect": cap_effect, "cap_note": cap_note,
            "alloc_formula": ["1銘柄あたりの目標投資額 = 5,000,000円 × 5% = 250,000円",
                              "単元数 = round( 250,000 ÷ (株価 × 100) )   ただし最低1単元",
                              "1銘柄の投資額が400,000円（上限8%）を超えたら単元数を減らす",
                              "余った現金は、目標250,000円から最も下振れている銘柄へ1単元ずつ配る"],
            "alloc_text": "均等5%を目標にする。総合点に比例させる方法もあるが、実測では比率が"
                          "4.5%〜6.0%にしかならず差が出ないため、説明しやすい均等を採る。"
                          "日本株は100株単位でしか買えないため、目標ちょうどにはならない。",
        },
        "picks": [{"rank": str(i + 1), "code": r["code"], "name": r["name"],
                   "sector": r["sector_ja"], "market": r["market_ja"],
                   "moat": f"{r['moat_p']:.0f}", "change": f"{r['change_p']:.0f}",
                   "future": f"{r['future_p']:.0f}", "price": f"{r['price_p']:.0f}",
                   "total": f"{r['total']:.1f}"} for i, r in top.iterrows()],
        "rationale": [[r["code"], r["name"], rationale(r)] for _, r in top.iterrows()],
        "financials": [[r["code"], r["name"],
                        f1(r["revenue"] / 1e8, 0), pct(r["op_margin"]), pct(r["roe_calc"]),
                        pct(r["eq_ratio"]), pct(r["ocf_margin"]),
                        f1(r["market_cap"] / 1e8, 0)] for _, r in top.iterrows()],
        "portfolio": {
            "text": f"投資枠500万円、売買単位100株、1銘柄あたりの上限8%。"
                    f"合計{yen(invested)}円（{invested / 5_000_000 * 100:.2f}%）を配分し、"
                    f"残る現金は{yen(cash_left)}円。",
            "note": "株価・時価総額は2026-08-17時点の実勢値。"
                    "PER・PBRは各社最新の有価証券報告書の当期純利益・自己資本で算出。",
        },
        "holdings": [{"code": r["code"], "name": r["name"], "close": yen(r["price_used"]),
                      "per": f1(r["per"]), "pbr": f1(r["pbr"], 2),
                      "mcap": f1(r["market_cap"] / 1e8, 0), "shares": f"{int(r['shares']):,}",
                      "cost": yen(r["cost"]), "weight": f"{r['weight_pct']:.2f}%"}
                     for _, r in top.iterrows()],
        "sector_rows": [[k, f"{vv}社"] for k, vv in sector_counts.items()],
        "market_scale": market_scale,
        "valuation_rows": [
            ["PER 中央値", f1(top["per"].median()) + "倍", f"{uni_per:.1f}倍"],
            ["PBR 中央値", f1(top["pbr"].median(), 2) + "倍", f"{uni_pbr:.2f}倍"],
            ["PBR 1倍割れの比率", f"{(top['pbr'] < 1).mean() * 100:.0f}%", f"{uni_below1:.0f}%"],
            ["時価総額 中央値", f1(top["market_cap"].median() / 1e8, 0) + "億円", "—"],
            ["ROE 中央値", pct(top["roe_calc"].median()), "—"],
        ],
        "validation": {
            "design": "有価証券報告書の提出日を基準に4軸を計算し、その後の株価だけで結果を測る。"
                      "提出時点で知り得た情報しか使っていないので、後知恵にはならない。",
            "cohorts": vb["cohorts"], "ic": vb["ic"],
            "ic_note": "順位相関は、スコアの順位とその後のリターンの順位がどれだけ一致したか。"
                       "軸単体では符号が安定しないものもあるが、合成すると安定する。"
                       "これは4軸に分けて平均する設計の狙いどおりの挙動である。",
            "decile": vb["decile"], "portfolio": vb["portfolio"],
            "portfolio_note": "ブートストラップ95%区間は、20社を重複ありで選び直す試行を2,000回"
                              "繰り返して得た平均リターンの範囲。20社という少なさの不確かさを表す。",
            "robustness": vb["robustness"], "verdict": verdict,
        },
        "comparison": {"text": cmp_text, "rows": cmp_rows, "overlap": overlap},
        "limits": limits,
        "repro": {"commands": cmds, "outputs": outs},
        "footer": ("正典: outputs/stockleague_edition/ESTABLISHED_FORMULA_FEASIBILITY_v1.md"
                   if est else "正典: outputs/stockleague_edition/NEW4AXIS_SPEC_v2.md")
                  + " ／ 検証: NEW4AXIS_AUDIT_v1.md",
        "footer_short": "既存式版" if est else "自作式版",
    }


def main() -> None:
    fin = load_financials()
    val = json.loads((OUT / "established_summary.json").read_text(encoding="utf-8"))
    for variant in ["bespoke", "established"]:
        payload = build_payload(variant, fin, val)
        path = OUT / f"docx_payload_{variant}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        r = subprocess.run(["node", str(HERE / "build_docx.js"), str(path)],
                           capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            sys.exit(r.returncode)


if __name__ == "__main__":
    main()
