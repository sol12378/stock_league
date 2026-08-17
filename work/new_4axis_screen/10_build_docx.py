"""Part 10: 選定結果を簡易レポート(docx)にする。

入力: work/new_4axis_screen/out/final_top20.csv / final_summary.json
出力: outputs/stockleague_edition/screening_report_v1.docx

docx-js(Node)へ渡すJSONを組み立て、build_docx.js を呼ぶ。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
DOCX = ROOT / "outputs/stockleague_edition/screening_report_v1.docx"

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
MARKET_JA = {
    "Prime Market (Domestic)": "プライム",
    "Standard Market(Domestic)": "スタンダード",
    "Growth Market(Domestic)": "グロース",
}


def yen(v: float) -> str:
    return f"{int(round(v)):,}"


def main() -> None:
    top = pd.read_csv(OUT / "final_top20.csv", dtype={"code": str})
    s = json.loads((OUT / "final_summary.json").read_text(encoding="utf-8"))

    top = top.sort_values("total", ascending=False).reset_index(drop=True)
    top["sector_ja"] = top["sector_33"].map(SECTOR_JA).fillna(top["sector_33"])
    top["market_ja"] = top["market"].map(MARKET_JA).fillna(top["market"])
    top["name"] = (top["company_name_ja"].fillna(top["company_name"])
                   .str.replace("株式会社", "", regex=False).str.strip())

    sector_counts = top["sector_ja"].value_counts()
    market_counts = top["market_ja"].value_counts()
    scale_counts = top["scale_category"].fillna("区分なし").value_counts()

    payload = {
        "output": str(DOCX),
        "meta": {
            "title": "新スクリーニング 簡易レポート",
            "subtitle": "4軸（Moat／Change／Future／Price）等重み25%",
            "date": "2026-08-17",
            "asof": "株価・時価総額 2026-08-17時点／財務 各社最新の有価証券報告書／流動性・業種 2026-06-01時点",
        },
        "summary": {
            "universe": s["step0"]["universe"],
            "eligible": s["step0"]["eligible_final"],
            "picked": len(top),
            "sectors": int(top["sector_ja"].nunique()),
            "per_median": s["top20_profile"]["per_median"],
            "pbr_median": s["top20_profile"]["pbr_median"],
            "mcap_median": s["top20_profile"]["market_cap_median_oku"],
            "roe_median": s["top20_profile"]["roe_median"],
            "adv_median": s["top20_profile"]["adv60_median_oku"],
            "invested": yen(s["step4"]["invested"]),
            "cash": yen(s["step4"]["cash_left"]),
            "cash_pct": s["step4"]["cash_left_pct"],
            "w_min": s["step4"]["weight_min_pct"],
            "w_max": s["step4"]["weight_max_pct"],
            "overlap": s["vs_current_v10"]["overlap"],
        },
        "funnel": [c for c in [
            ["全上場企業", f"{s['step0']['universe']:,}社", "JPX上場全銘柄"],
            ["条件1〜8 通過", f"{s['step0']['eligible_conditions_1_8']:,}社",
             "流動性2,000万円/日・3期連続赤字なし・財務データ完備など"],
            ["条件9（バリュエーション範囲）で除外",
             f"−{s['step0']['excluded_by_condition9_valuation']}社",
             "PER 0以下/120超、PBR 0以下/20超。今回から全社に適用"],
            ["Step 0 通過（母集団）", f"{s['step0']['eligible_final']:,}社", "4軸で採点する対象"],
            ["1単元が上限8%を超え購入不可", f"−{s['step3_buyability']['not_buyable_within_cap']}社",
             "1単元40万円超。投資枠500万円の制約で買えないため次点を繰り上げる"],
            ["選抜対象プール", f"{s['step3']['pool']:,}社", "ここから総合点順に採る"],
            ["Step 3 選抜", f"{len(top)}社", "総合点の上位・同一業種は2社まで"],
        ] if not c[1].startswith(("−0社", "0社"))],
        "axes": [
            ["① Moat（いま強いか）",
             "売上総利益/総資産、営業利益率、ROA、営業CF率、自己資本比率",
             "5指標の順位点の平均"],
            ["② Change（良くなっているか）",
             "Piotroski Fスコア、ΔROA、Δ売上総利益率、Δ総資産回転率、増収率、営業増益率",
             "6指標の順位点の平均。株価倍率は含めない"],
            ["③ Future（構造変化の恩恵）",
             "EDINET本文のキーワード照合（AI基盤0.30／無形資産0.25／省人化0.20／データ0.15／信頼0.10）",
             "合成値の順位点"],
            ["④ Price（高すぎないか）",
             "益回り（純利益/時価総額）、自己資本/時価総額",
             "2指標の順位点の平均"],
        ],
        "effective_weight": [
            ["名目", "25.0%", "25.0%", "25.0%", "25.0%"],
            ["実効（分散寄与）",
             f"{s['effective_weight_variance_share']['moat_p']*100:.1f}%",
             f"{s['effective_weight_variance_share']['change_p']*100:.1f}%",
             f"{s['effective_weight_variance_share']['future_p']*100:.1f}%",
             f"{s['effective_weight_variance_share']['price_p']*100:.1f}%"],
        ],
        "picks": [
            {
                "rank": str(i + 1), "code": r["code"], "name": r["name"],
                "sector": r["sector_ja"], "market": r["market_ja"],
                "moat": f"{r['moat_p']:.0f}", "change": f"{r['change_p']:.0f}",
                "future": f"{r['future_p']:.0f}", "price": f"{r['price_p']:.0f}",
                "total": f"{r['total']:.1f}",
            }
            for i, r in top.iterrows()
        ],
        "holdings": [
            {
                "code": r["code"], "name": r["name"],
                "close": yen(r["price_used"]),
                "per": "—" if pd.isna(r["per"]) else f"{r['per']:.1f}",
                "pbr": "—" if pd.isna(r["pbr"]) else f"{r['pbr']:.2f}",
                "mcap": f"{r['market_cap']/1e8:,.0f}",
                "shares": f"{int(r['shares']):,}",
                "cost": yen(r["cost"]),
                "weight": f"{r['weight_pct']:.2f}%",
            }
            for _, r in top.iterrows()
        ],
        "totals": {
            "cost": yen(top["cost"].sum()),
            "weight": f"{top['weight_pct'].sum():.2f}%",
        },
        "sector_rows": [[k, f"{v}社"] for k, v in sector_counts.items()],
        "market_rows": [[k, f"{v}社"] for k, v in market_counts.items()],
        "scale_rows": [[str(k), f"{v}社"] for k, v in scale_counts.items()],
        "compare": [
            ["Moat", f"{s['vs_current_v10']['current_axis_medians']['moat_p']:.1f}",
             f"{s['vs_current_v10']['new_axis_medians']['moat_p']:.1f}"],
            ["Change", f"{s['vs_current_v10']['current_axis_medians']['change_p']:.1f}",
             f"{s['vs_current_v10']['new_axis_medians']['change_p']:.1f}"],
            ["Future", f"{s['vs_current_v10']['current_axis_medians']['future_p']:.1f}",
             f"{s['vs_current_v10']['new_axis_medians']['future_p']:.1f}"],
            ["Price", f"{s['vs_current_v10']['current_axis_medians']['price_p']:.1f}",
             f"{s['vs_current_v10']['new_axis_medians']['price_p']:.1f}"],
        ],
        "notes": s.get("notes", []),
        "extra": {
            "split_detected": s["share_source"]["post_filing_split_detected"],
            "split_jun_aug": s["price_source"]["split_between_jun_and_now"],
            "not_buyable": s["step3_buyability"]["not_buyable_within_cap"],
            "live_shares": s["share_source"]["eligible_with_live"],
            "fallback": s["share_source"]["fallback_to_xbrl"],
            "all4_60": s["all_four_axes_above"]["60"],
            "all4_70": s["all_four_axes_above"]["70"],
            "all4_80": s["all_four_axes_above"]["80"],
            "sectors_nodiv": s["step3"]["sectors_without_cap"],
            "nodiv_top": "・".join(
                f"{SECTOR_JA.get(k, k)}{v}社" for k, v in s["step3"]["nodiv_top_sector_share"].items()),
            "mean_with_cap": s["step3"]["mean_total_with_cap"],
            "mean_without_cap": s["step3"]["mean_total_without_cap"],
            "per_median_universe": s["valuation_distribution"]["per_median"],
            "pbr_median_universe": s["valuation_distribution"]["pbr_median"],
            "pbr_below1": s["valuation_distribution"]["pbr_below_1_pct"],
        },
    }

    payload_path = OUT / "docx_payload.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "build_docx.js"), str(payload_path)],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode != 0:
        sys.exit(r.returncode)
    print(f"生成: {DOCX}")


if __name__ == "__main__":
    main()
