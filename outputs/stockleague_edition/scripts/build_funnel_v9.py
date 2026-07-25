# -*- coding: utf-8 -*-
"""V9 スクリーニング全枝ファネルの正典を生成する。
単一のbase(適格×流動性×価格履歴3年)から、守・破・離・両立・分散の各枝の社数を
build_portfolio_v7.py と同一のガード・同一の選定順序で再計算し、
出口の20社が portfolio_v7.json と完全一致することを assert する(実装＝レポート一致)。
出力: funnel_branches_v9.json"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["adjusted_bb_score", "moat_score", "future_moat_score", "roe", "operating_margin",
          "equity_ratio", "operating_cf", "revenue_growth", "operating_income_growth",
          "operating_loss_years_3y", "net_loss_years_3y", "negative_ocf_years_3y",
          "operating_income", "net_income", "shares_outstanding"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
histd = px.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())
s["histd"] = s["ticker"].map(histd).fillna(0)
last_px = px.sort_values("date").groupby("ticker")["adj_close"].last()
s["mcap"] = s.ticker.map(last_px) * s.shares_outstanding
s["ey"] = s.net_income / s.mcap

# ---- スクリーニング0: 共通の関所(幹) ----
m_nonfin = ~truthy(s, "is_financial") & truthy(s, "price_available")
m_invest = m_nonfin & truthy(s, "investment_eligible")
m_liquid = m_invest & truthy(s, "liquid_20m_60d")
m_base = m_liquid & (s.histd >= 756)
common = [
    {"id": "0-1", "label": "金融を除く普通株(価格データあり)", "n": int(m_nonfin.sum())},
    {"id": "0-2", "label": "投資適格(監理・整理銘柄等を除外)", "n": int(m_invest.sum())},
    {"id": "0-3", "label": "流動性 60日平均売買代金の基準", "n": int(m_liquid.sum())},
    {"id": "0-4", "label": "価格履歴3年(756営業日)＝検証可能性", "n": int(m_base.sum())},
]
base = m_base
info = s.set_index("code")

# ---- スクリーニング1: 守(品質七関門→価格ランク→Top5) ----
gates = [
    ("1-1", "高収益 ＲＯＥ≥15％", s.roe >= 0.15),
    ("1-2", "堀・価格支配力 営業利益率≥10％", s.operating_margin >= 0.10),
    ("1-3", "財務健全 自己資本比率≥50％", s.equity_ratio >= 0.50),
    ("1-4", "予測可能性 直近3期無赤字", (s.operating_loss_years_3y == 0) & (s.net_loss_years_3y == 0) & (s.negative_ocf_years_3y == 0)),
    ("1-5", "現金創出 営業ＣＦ＞0", s.operating_cf > 0),
    ("1-6", "非縮小 増収かつ増益", (s.revenue_growth >= 0) & (s.operating_income_growth >= 0)),
]
shu_steps, m = [], base.copy()
for gid, label, cond in gates:
    m = m & cond
    shu_steps.append({"id": gid, "label": label, "n": int(m.sum())})
n_quality = int(m.sum())
m_price = m & (s.ey > 0) & s.mcap.notna()
shu_steps.append({"id": "1-7", "label": "価格ランク可能(時価総額データあり・益回り＞0)", "n": int(m_price.sum())})
# Greenblatt(ROE順位+益回り順位)・同一業種2社まで → Top12(新バフェット) / 守5=上位5
bq = s[m_price].copy()
bq["mf"] = bq.roe.rank(ascending=False) + bq.ey.rank(ascending=False)
_cnt, buf12 = {}, []
for _, r in bq.sort_values("mf").iterrows():
    if _cnt.get(r.sector_33, 0) >= 2: continue
    _cnt[r.sector_33] = _cnt.get(r.sector_33, 0) + 1; buf12.append(r.code)
    if len(buf12) == 12: break
shu5 = buf12[:5]
shu_steps.append({"id": "1-8", "label": "割安×優良の複合順位＋同一業種2社まで → Top5固定", "n": 5})

# ---- 選定カスケード(build_portfolio_v7.py と同一順序: 守→両立→離→破→分散) ----
GLOBAL_CAP, ROE_FLOOR = 99, 0.05
gsec = {}
def gpick(df, score, n, exclude, asc=False, role_cap=2):
    pool = df[~df.code.isin(exclude)].sort_values(score, ascending=asc)
    rcnt, out = {}, []
    for _, r in pool.iterrows():
        sec = r.sector_33
        if gsec.get(sec, 0) >= GLOBAL_CAP: continue
        if rcnt.get(sec, 0) >= role_cap: continue
        rcnt[sec] = rcnt.get(sec, 0) + 1; gsec[sec] = gsec.get(sec, 0) + 1
        out.append(r.code)
        if len(out) == n: break
    return out

picked = set(shu5)
for c in shu5: gsec[info.loc[c, "sector_33"]] = gsec.get(info.loc[c, "sector_33"], 0) + 1
black = (s.operating_income > 0) & (s.net_income > 0)
roe5 = s.roe >= ROE_FLOOR

# 両立型3(min判定・現在×未来の両上位)
dual_pool = s[base & black & roe5].copy()
n_dual_pool = int(len(dual_pool))
dual_pool["rboth"] = dual_pool.moat_score.rank(ascending=False) + dual_pool.future_moat_score.rank(ascending=False)
dual3 = gpick(dual_pool, "rboth", 3, picked, asc=True); picked |= set(dual3)

# 離5(事業検証リスト: 開示セグメントでAI・半導体の実需を確認した7社・うち予備2)
SEMI_VERIFIED = ["6777", "6871", "6590", "6387", "6627", "6951", "6941"]
elig_codes = set(s[base & black & roe5].code)
umare5 = [c for c in SEMI_VERIFIED if c in elig_codes and c not in picked][:5]
for c in umare5: gsec[info.loc[c, "sector_33"]] = gsec.get(info.loc[c, "sector_33"], 0) + 1
picked |= set(umare5)

# 破5(変革分類×黒字×ROE≥5%→変革の点数順・業種上限2)
m_ha0 = base & (s.category == "Transformation Moat")
m_ha1 = m_ha0 & black
m_ha2 = m_ha1 & roe5
ha_steps = [
    {"id": "2-1", "label": "変わる堀に分類(変革の点数＞基準)", "n": int(m_ha0.sum()),
     "n_all": int((s.category == "Transformation Moat").sum())},
    {"id": "2-2", "label": "黒字(営業利益・純利益がプラス)", "n": int(m_ha1.sum())},
    {"id": "2-3", "label": "最低限の収益性 ＲＯＥ≥5％", "n": int(m_ha2.sum())},
]
haru5 = gpick(s[m_ha2], "adjusted_bb_score", 5, picked); picked |= set(haru5)
ha_steps.append({"id": "2-4", "label": "変わる堀の点数の上位＋同一業種2社まで", "n": 5})

# 分散役2(未使用業種から総合点上位)
used_sectors = set(info.loc[list(picked), "sector_33"])
bridge_pool = s[base & black & roe5 & (~s.sector_33.isin(used_sectors)) & (~s.code.isin(picked))]
n_bridge_pool = int(len(bridge_pool))
bridge2 = gpick(bridge_pool, "adjusted_bb_score", 2, picked, role_cap=1)

# ---- 離の分岐の実証(キーワード経路の破棄) ----
fm_all = int((s.category == "Future Moat").sum())
fm_base = int((base & (s.category == "Future Moat")).sum())
tie_val = float(info.loc["6920", "future_moat_score"])  # レーザーテックの点
m_tie = s.future_moat_score.sub(tie_val).abs() < 1e-9
n_tie = int(m_tie.sum())
tie_codes = set(s[m_tie].code)
# 実需と無関係の業種の会社が最先端(レーザーテック)と同点に並ぶ実例(コード実在をassert)
for c in ["6745", "7762", "6741", "6920"]:  # ホーチキ(火災報知機)・シチズン(時計)・日本信号・レーザーテック
    assert c in tie_codes, f"tie example {c} not at tie value"
ri = {
    "keyword_path": {"fm_category_all": fm_all, "fm_category_base": fm_base,
                     "tie_value": round(tie_val, 4), "tie_n": n_tie,
                     "tie_examples": "火災報知機のホーチキ・時計のシチズン・鉄道信号の日本信号が、半導体マスク検査で世界唯一のレーザーテックと同点",
                     "note": "社名・業種等へのキーワード照合で加点されるため電気機器などの業種はほぼ一律に高得点＝点数では選別不能(経路を破棄)"},
    "verified_path": [
        {"id": "3-2", "label": "事業セグメント開示でＡＩ・半導体の実需を確認", "n": len(SEMI_VERIFIED),
         "note": "候補として精査した中で実需接続を確認できた7社(うち2社は予備)"},
        {"id": "3-3", "label": "適格ガード(黒字・ＲＯＥ≥5％・流動性・履歴3年)", "n": len(umare5)},
    ],
}

# ---- 出口20社の完全一致assert(実装＝レポート一致) ----
pf = json.load(open(WORK / "portfolio_v7.json", encoding="utf-8"))
w_keys = {k.replace(".T", "") for k in pf["weights_v7"].keys()}
final20 = set(shu5) | set(haru5) | set(umare5) | set(dual3) | set(bridge2)
assert len(final20) == 20, f"final={len(final20)}"
assert final20 == w_keys, f"mismatch: only_here={sorted(final20 - w_keys)} only_pf={sorted(w_keys - final20)}"
assert shu5 == ["3092", "4716", "7014", "8136", "6920"], shu5

out = {
    "n_records": int(len(s)),
    "common": common,
    "n_nonfin": int(m_nonfin.sum()), "n_eligible": int(m_liquid.sum()), "n_base": int(m_base.sum()),
    "shu": {"steps": shu_steps, "n_quality": n_quality, "n_priceable": int(m_price.sum()), "top5": shu5, "top12": buf12},
    "ha": {"steps": ha_steps, "picked": haru5},
    "ri": ri, "ri_picked": umare5,
    "dual": {"pool_n": n_dual_pool, "picked": dual3,
             "label": "黒字×ＲＯＥ≥5％の適格プールから、現在の堀×未来の堀の両順位がともに上位(業種上限2)"},
    "bridge": {"pool_n": n_bridge_pool, "picked": bridge2,
               "label": "20社で未使用の業種に限り、総合点の上位(業種上限1)"},
    "note": "全社数は scores.csv・prices_daily.parquet から build_portfolio_v7.py と同一ガード・同一順序で再計算。出口20社の一致を assert 済み。",
}
json.dump(out, open(ED / "funnel_branches_v9.json", "w"), ensure_ascii=False, indent=1)
print("=== V9 全枝ファネル ===")
print(f"幹: 記録{out['n_records']:,} → 非金融{out['n_nonfin']:,} → 適格+流動性{out['n_eligible']:,} → base(履歴3年){out['n_base']:,}")
print("守:", " → ".join(f"{st['n']:,}" for st in shu_steps))
print("破:", " → ".join(f"{st['n']:,}" for st in ha_steps), "| picked:", haru5)
print(f"離: キーワード分類{fm_all:,}(base内{fm_base:,})→破棄 / 検証7→適格{len(umare5)} | picked:", umare5)
print(f"両立: プール{n_dual_pool:,}→3 {dual3} / 分散: プール{n_bridge_pool:,}→2 {bridge2}")
print(f"同点タイ: 値{tie_val:.4f} × {n_tie:,}社")
print("assert PASS: 出口20社 = portfolio_v7.json")
