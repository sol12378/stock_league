# -*- coding: utf-8 -*-
"""V7 の20社データ(data_real_v7.json)を生成。数値は正典(scores/fundamentals/prices/portfolio_v7)から自動計算。
証拠水準(evid)・theme は暫定(要IR最終確認)。distress系は全社黒字通過のためFalse。"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"
CAP = 5_000_000

pf = json.load(open(WORK / "portfolio_v7.json"))
w_v7 = pf["weights_v7"]
tbl = pd.read_csv(ED / "portfolio_v7_table.csv", dtype={"code": str}); tbl["code"] = tbl["code"].str.zfill(4)

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False); s["code"] = s["code"].str.zfill(4)
for c in ["equity", "net_income", "shares_outstanding", "annual_volatility", "avg_trading_value_60d",
          "transformation_score", "future_moat_score", "moat_score", "roe", "operating_margin",
          "equity_ratio", "revenue_growth", "operating_income_growth",
          "operating_loss_years_3y", "net_loss_years_3y", "negative_ocf_years_3y"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
fn = pd.read_csv(ROOT / "data/processed/fundamentals_clean.csv", dtype={"code": str}); fn["code"] = fn["code"].str.zfill(4)
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
last_px = px.sort_values("date").groupby("ticker")["adj_close"].last()
S = s.set_index("code"); FJA = fn.set_index("code")["company_name_ja"].to_dict()

# theme / 証拠水準(暫定) / 事業1行(要IR検証) を code で
META = {
 "3092": ("platform", 3, "国内最大級のファッションEC「ZOZOTOWN」を運営"),
 "4716": ("software", 3, "企業向けデータベース・クラウド（米Oracle日本法人）"),
 "8136": ("ip", 3, "ハローキティ等のキャラクターIP・ライセンス事業"),
 "6920": ("semiconductor", 3, "半導体マスク欠陥検査装置（EUV向けで世界的地位）"),
 "7014": ("shipbuilding", 2, "船舶建造（ばら積み船等）※循環業のため守での扱いは要検討"),
 "9022": ("infrastructure", 3, "東海道新幹線を運営、リニア中央新幹線を建設中"),
 "9503": ("power", 2, "電力事業（原発再稼働を推進）"),
 "9513": ("power", 2, "卸電力（水力・火力・再エネ）、脱炭素で変革"),
 "1662": ("energy", 2, "石油・天然ガスの探鉱開発（E&P）、資源高・株主還元"),
 "5214": ("materials", 2, "特殊ガラス（ディスプレイ・医薬・繊維用）"),
 "6777": ("optical", 3, "波長可変レーザ・光通信部品（AIデータセンター向け）"),
 "6871": ("semiconductor", 3, "半導体プローブカード（先端ウエハテスト用）"),
 "6590": ("semiconductor", 2, "半導体・FPD製造装置（洗浄・成膜・検査）"),
 "6387": ("semiconductor", 2, "化合物半導体（GaN/SiC）向け薄膜・エッチング装置"),
 "6627": ("semiconductor", 2, "半導体ウエハテスト受託（テストハウス）"),
 "6861": ("automation", 3, "FA（工場自動化）センサ・測定器"),
 "7725": ("semiconductor", 2, "半導体イメージセンサ検査用光源装置等"),
 "6929": ("sensor", 3, "赤外線センサ等のセンサ"),
 "3449": ("materials", 2, "金属フレキシブルチューブ・配管継手"),
 "4971": ("chemicals", 2, "プリント基板・半導体向け薬品（表面処理）"),
}
role_en = {"守 完成した堀": "Buffett Core", "破 変わる堀": "Transformation Core",
           "離 生まれる堀": "Emerging Core", "両立型": "Dual Moat", "分散役": "Bridge / Diversifier"}

D = {}
for _, r in tbl.iterrows():
    c = r["code"]; row = S.loc[c]; tk = c + ".T"
    price = float(last_px.get(tk, np.nan))
    mktcap = price * float(row["shares_outstanding"])
    w = float(w_v7[tk]); amt = int(w * CAP)     # 目標金額配分(単元未満株OK・端数切捨で¥500万以内)
    qty = round(amt / price, 2) if price > 0 else 0  # 端株(小数)可
    theme, evid, biz = META[c]
    D[c] = {
        "code": int(c), "name": row["company_name"], "name_ja": FJA.get(c, row["company_name"]),
        "sector": row["sector_33"], "role": role_en[r["role"]], "role_jp": r["role"], "theme": theme,
        "business": biz, "evid": evid,
        "bm": round(float(row["equity"]) / mktcap, 3) if mktcap > 0 else None,
        "ep": round(float(row["net_income"]) / mktcap, 4) if mktcap > 0 else None,
        "roe": float(r["roe_pct"]) / 100 if pd.notna(r["roe_pct"]) else None,
        "moat_hensa": int(r["moat_hensa"]), "fmoat_hensa": int(r["fmoat_hensa"]),
        "tsc": round(float(row["transformation_score"]), 2) if pd.notna(row["transformation_score"]) else None,
        "mktcap_oku": round(mktcap / 1e8, 0), "adv_oku": round(float(row["avg_trading_value_60d"]) / 1e8, 2) if pd.notna(row["avg_trading_value_60d"]) else None,
        "vol1y": round(float(row["annual_volatility"]), 3),
        "opm": round(float(row["operating_margin"]), 3) if pd.notna(row["operating_margin"]) else None,
        "eqr": round(float(row["equity_ratio"]), 3) if pd.notna(row["equity_ratio"]) else None,
        "rev_g": round(float(row["revenue_growth"]), 3) if pd.notna(row["revenue_growth"]) else None,
        "oi_g": round(float(row["operating_income_growth"]), 3) if pd.notna(row["operating_income_growth"]) else None,
        "loss_free": bool((row["operating_loss_years_3y"] == 0) and (row["net_loss_years_3y"] == 0) and (row["negative_ocf_years_3y"] == 0)),
        "price": round(price, 1), "w": round(w, 4), "amtL1": int(amt), "qtyL1": qty,
        "frac_shares": True,
        "neg_eq": False, "pers_loss": False, "neg_cfo": False,
    }
json.dump(D, open(ED / "data_real_v7.json", "w"), ensure_ascii=False, indent=1)
inv = sum(v["amtL1"] for v in D.values())
print(f"data_real_v7.json: {len(D)}社 / L1投資額計={inv:,}円 (5,000,000中)")
by_role = {}
for v in D.values(): by_role.setdefault(v["role_jp"], []).append(v["name_ja"][:8])
for k, vs in by_role.items(): print(f"  {k}: {len(vs)}社")
print("evid分布:", pd.Series([v["evid"] for v in D.values()]).value_counts().to_dict())
print("written ->", ED / "data_real_v7.json")
