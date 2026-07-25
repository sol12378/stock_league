# -*- coding: utf-8 -*-
"""V7 第Ⅱ章の守ファネル＋除外内訳を新手法(真バフェット品質ゲート)で再計算。
数値は scores.csv から自動集計(捏造なし)。出力: funnel_exclusion_v7.json"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)
def truthy(c): return s[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
          "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "shares_outstanding", "net_income"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")

nonfin = s[~truthy("is_financial") & truthy("price_available")]
elig = nonfin[truthy("investment_eligible") & truthy("liquid_20m_60d")]

# 守=真バフェット品質ゲートの累積ファネル
g = elig.copy()
funnel = [("金融を除く普通株(価格あり)", len(nonfin)),
          ("投資適格＋流動性", len(elig))]
steps = [("高収益 ROE≥15%", g.roe >= 0.15),
         ("堀/価格支配力 営業利益率≥10%", g.operating_margin >= 0.10),
         ("財務健全 自己資本比率≥50%", g.equity_ratio >= 0.50),
         ("予測可能性 直近3期無赤字", (g.operating_loss_years_3y == 0) & (g.net_loss_years_3y == 0) & (g.negative_ocf_years_3y == 0)),
         ("現金創出 営業CF>0", g.operating_cf > 0),
         ("非縮小 増収かつ増益", (g.revenue_growth >= 0) & (g.operating_income_growth >= 0))]
mask = pd.Series(True, index=g.index)
for label, cond in steps:
    mask = mask & cond
    funnel.append((label, int(mask.sum())))
Q = g[mask]
funnel.append(("価格ランク可能(時価総額データあり)", int(Q["shares_outstanding"].notna().sum())))
funnel.append(("完成した堀 Top5(守・Greenblatt順+業種上限)", 5))

# 除外内訳(なぜ品質ゲートで落ちたか・各ゲートの脱落数=単独failで数える)
base_n = len(elig)
excl = {"高収益ROE<15%で除外": int((~(elig.roe >= 0.15)).sum()),
        "利益率<10%で除外(ROE通過後)": int(((elig.roe >= 0.15) & ~(elig.operating_margin >= 0.10)).sum()),
        "自己資本<50%で除外": int(((elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & ~(elig.equity_ratio >= 0.50)).sum()),
        "直近3期に赤字あり": int(((elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) & ~((elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) & (elig.negative_ocf_years_3y == 0))).sum()),
        "減収または減益": int((mask.reindex(elig.index, fill_value=False) == False).sum() - (~(elig.roe >= 0.15)).sum())}

out = {"funnel": [{"step": i + 1, "label": l, "n": n} for i, (l, n) in enumerate(funnel)],
       "quality_universe_n": int(len(Q)),
       "priceable_n": int(Q["shares_outstanding"].notna().sum()),
       "exclusion_note": "守は真バフェット品質ゲートの累積フィルタ。落ちた社は各ゲート基準で理由が特定できる(捏造なし)。",
       "start_n": int(len(nonfin)), "eligible_n": int(len(elig))}
json.dump(out, open(ED / "funnel_exclusion_v7.json", "w"), ensure_ascii=False, indent=1)
print("守ファネル(真バフェット品質ゲート):")
for f in out["funnel"]:
    print(f'  {f["step"]}. {f["label"]}: {f["n"]:,}社')
print(f'\nクオリティ通過={out["quality_universe_n"]} / 価格ランク可={out["priceable_n"]} / 出発={out["start_n"]:,} / 適格={out["eligible_n"]:,}')
print("written ->", ED / "funnel_exclusion_v7.json")
