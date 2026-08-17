# -*- coding: utf-8 -*-
"""欠測監査の追補: 報告書の記述と実装の不一致を実測で確定する。

missingness_audit.json に D11〜D15 を追記する。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
J = Path(__file__).with_name("missingness_audit.json")
R = json.loads(J.read_text())

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["adjusted_bb_score", "transformation_score", "moat_score", "roe", "operating_income",
          "net_income", "operating_margin", "competitive_position_score", "rd_ratio",
          "avg_trading_value_60d"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
h = px.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum()); s["histd"] = s.ticker.map(h).fillna(0)
base = (truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")
        & truthy(s, "liquid_20m_60d") & (s.histd >= 756))
B = s[base].copy()
nm = s.set_index("code")["company_name"].to_dict()


def pick(df, score, n, cap=2, asc=False):
    cnt, out = {}, []
    for _, r in df.sort_values(score, ascending=asc).iterrows():
        if cnt.get(r.sector_33, 0) >= cap: continue
        cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1
        out.append(r.code)
        if len(out) == n: break
    return out


# ============ D11: 式(10)は全社が Lite形。フル形の R・K は1社も値を持たない ============
f20 = pd.read_csv(ROOT / "outputs/beyond_buffett_fable_loop_final/phase3_moat_construction/final20_selected.csv",
                  dtype={"code": str}, low_memory=False)
cand = pd.read_csv(ROOT / "outputs/beyond_buffett_fable_loop_final/phase3_moat_construction/final20_candidates.csv",
                   dtype={"code": str}, low_memory=False)
R["D11_formula10_lite_fallback"] = {
    "報告書v10_v11が印字する重み": {"V割安": 0.20, "C資本効率": 0.22, "R株主還元": 0.16,
                          "K改革開示": 0.17, "E実行": 0.13, "Q ワナ耐性": 0.12},
    "実際に使われた形": "lite (30/20/20/20/10)",
    "候補_method内訳": {str(k): int(v) for k, v in cand.transformation_score_method.value_counts(dropna=False).items()},
    "最終20社_method内訳": {str(k): int(v) for k, v in f20.transformation_score_method.value_counts(dropna=False).items()},
    "shareholder_alignment_score_notna_候補": int(cand.shareholder_alignment_score.notna().sum()),
    "reform_evidence_score_notna_候補": int(cand.reform_evidence_score.notna().sum()),
    "候補社数": int(len(cand)),
    "欠測した重みの合計": 0.16 + 0.17,
    "欠測した重みの割合": round((0.16 + 0.17) / 1.00, 3),
    "code": "phase3_common.py:387-390 enough = notna(shareholder, reform).all() → 偽なら 'lite_due_to_missing_shareholder_or_reform_inputs'",
    "開示履歴": "v5/v6の技術補遺B-3は『フル形は構造的に到達不能』と開示していたが、v10で補遺を廃止した際に開示も消え、本文はフル形の重みを掲載している",
}

# ============ D12: 破5の並べ替えキーは adjusted_bb_score(報告書は「変わる堀の点数の上位」) ============
picked_before = {"3092", "4716", "7014", "8136", "6920", "6861", "7725", "6929",
                 "6777", "6871", "6590", "6387", "6627"}
pool = B[(B.category == "Transformation Moat") & (B.operating_income > 0) & (B.net_income > 0)
         & (B.roe >= 0.05) & (~B.code.isin(picked_before))]
by_bb = pick(pool, "adjusted_bb_score", 5)
by_tr = pick(pool, "transformation_score", 5)
R["D12_ha5_ranking_key"] = {
    "正典ビルダー": "work/pure_buffett_benchmark/build_portfolio_v7.py: gpick(trans_pool, 'adjusted_bb_score', 5, picked)",
    "報告書のファネル2-4ラベル": "変わる堀の点数の上位＋同一業種2社まで",
    "adjusted_bb_score順(=実装・提出20社と一致)": [{"code": c, "name": str(nm[c])} for c in by_bb],
    "transformation_score順(=ラベルどおりに解釈した場合)": [{"code": c, "name": str(nm[c])} for c in by_tr],
    "重複社数": len(set(by_bb) & set(by_tr)),
    "note": "並べ替えキーの15%(valuation_score)は base の92.2%で厳密に0。破5の順位は実質 yf カバー組の中で決まる",
}

# ============ D13: 流動性しきい値の記述(1,000万円)と実装(2,000万円)の不一致 ============
atv = s.avg_trading_value_60d.fillna(0)
pa = truthy(s, "price_available")
R["D13_liquidity_threshold_mismatch"] = {
    "実装": "scoring.py:764 avg_trading_value_60d >= 20_000_000 (=2,000万円/日)",
    "報告書v10_v11の記述": "式(7)の説明『1日あたり1,000万円を基準とする』/ 判定表『約0.1億円以上』/『(実装どおりに開示)』",
    "通過社数_1000万円基準": int((pa & (atv >= 10_000_000)).sum()),
    "通過社数_2000万円基準": int((pa & (atv >= 20_000_000)).sum()),
    "記述と実装で説明が食い違う社数": int((pa & (atv >= 10_000_000)).sum() - (pa & (atv >= 20_000_000)).sum()),
    "最終20社への影響": "なし(20社はいずれも基準を大きく超える)。開示の誤りであって結果の誤りではない",
}

# ============ D14: competitive_position_score は営業利益率の複製 ============
def z(x):
    x = pd.to_numeric(x, errors="coerce"); x = x.clip(x.quantile(.01), x.quantile(.99))
    return (x - x.mean()) / x.std()


zm = z(s.operating_margin)
ratio = (s.competitive_position_score / zm).replace([np.inf, -np.inf], np.nan)
R["D14_competitive_position_duplication"] = {
    "code": 'competitive_position_score = average_z(df, ["rd_ratio", "operating_margin"])',
    "rd_ratio_notna_universe": int(s.rd_ratio.notna().sum()), "universe_n": int(len(s)),
    "rd_expense_notna": 2, "capex_notna": 0,
    "corr(competitive_position, z(operating_margin))": round(float(s.competitive_position_score.corr(zm)), 4),
    "比 competitive/z(margin) の中央値": round(float(ratio.median()), 4),
    "moat_scoreの実効重み": {"営業利益率": round(0.35 / 3 + 0.20 * 0.5, 4), "ＲＯＥ": round(0.35 / 3, 4),
                       "自己資本比率": round(0.35 / 3, 4), "営業ＣＦ率": 0.25, "低ボラティリティ": 0.20},
    "note": "rd_ratio が実質全社欠測でゼロ埋めされるため、『競争優位』枠(重み0.20)は 0.5×z(営業利益率) に退化。"
            "営業利益率は収益性枠にも入っており二重計上。堀の4本柱は実質3本柱",
    "v11の開示状況": "離(生まれる堀)の無形資産項については v11 が開示済み。守(moat_score)側の同一欠陥は未開示",
}

# ============ D15: 反実仮想まとめ(欠測を外すと選抜はどれだけ変わるか) ============
SHU = ((B.roe >= 0.15) & (B.operating_margin >= 0.10) & (B.equity_ratio >= 0.50)
       & (B.operating_loss_years_3y.astype(float) == 0) & (B.net_loss_years_3y.astype(float) == 0)
       & (B.negative_ocf_years_3y.astype(float) == 0) & (B.operating_cf.astype(float) > 0)
       & (B.revenue_growth.astype(float) >= 0) & (B.operating_income_growth.astype(float) >= 0))
R["D15_counterfactual_summary"] = {
    "守5": {"現行": R["D5_counterfactual_shu5"]["現行守5"],
           "ROE順のみ": R["D5_counterfactual_shu5"]["ROE順のみ守5"],
           "重複": R["D5_counterfactual_shu5"]["重複"]},
    "破5": {"現行": R["D4_counterfactual_ha5"]["現行の破5(adjusted_bb順)"],
           "yf限定フィールドを外す": R["D4_counterfactual_ha5"]["yf限定フィールドを外した場合の破5"],
           "重複": R["D4_counterfactual_ha5"]["重複社数"]},
    "note": "守は3/5一致(品質ゲート自体はEDINET財務のみで頑健)。破は0/5一致=yf由来フィールドの在庫が選抜を決めている",
}

J.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str))
for k in ["D11_formula10_lite_fallback", "D12_ha5_ranking_key", "D13_liquidity_threshold_mismatch",
          "D14_competitive_position_duplication", "D15_counterfactual_summary"]:
    print("##", k); print(json.dumps(R[k], ensure_ascii=False, indent=1))
