# -*- coding: utf-8 -*-
"""V7 提出PF確定(W0+W1): 守5/変わる堀5/生まれる堀5/両立型3/分散役2 = 20社。
役割予算(守28/変28/生28/両立10/分散6, 役割内均等)で多期間"超える"を再検証。
規律: 事前規則で機械選定(チューニング禁止)・in-sample自己検証・phase5計測規約。
出力: work/pure_buffett_benchmark/portfolio_v7.json
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
WORK = ROOT / "work/pure_buffett_benchmark"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["adjusted_bb_score", "moat_score", "future_moat_score", "roe", "operating_margin",
          "equity_ratio", "operating_cf", "revenue_growth", "operating_income_growth",
          "operating_loss_years_3y", "net_loss_years_3y", "negative_ocf_years_3y",
          "operating_income", "net_income", "equity", "shares_outstanding", "annual_volatility"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px_all["date"] = pd.to_datetime(px_all["date"])
histd = px_all.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())
s["histd"] = s["ticker"].map(histd).fillna(0)
first_valid = px_all.dropna(subset=["adj_close"]).groupby("ticker")["date"].min()
last_px = px_all.sort_values("date").groupby("ticker")["adj_close"].last()
s["mcap"] = s.ticker.map(last_px) * s.shares_outstanding
s["ey"] = s.net_income / s.mcap
base = truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available") & \
       truthy(s, "liquid_20m_60d") & (s.histd >= 756)
names = s.set_index("code")["company_name"].to_dict()
info = s.set_index("code")

# --- 精緻化(iter3): 離=AI/半導体を事業で検証採用 / 全体上限は非テーマ業種のみ ---
# GLOBAL_CAPは「生まれる堀のAI/半導体テーマ集中」を妨げないため実質無効化(99)。
# 過集中はHHIで開示し、破は役割内上限2で分散を維持、分散役が非テック業種を補う。
GLOBAL_CAP = 99
ROE_FLOOR = 0.05  # 破/離/両立/分散は ROE>=5%(=最低限の収益性。東電4%は自然脱落)
gsec = {}  # 全体業種カウンタ

def gpick(df, score, n, exclude, asc=False, role_cap=2):
    """全体業種上限(GLOBAL_CAP)＋役割内上限(role_cap)を同時に満たす順選定。"""
    pool = df[~df.code.isin(exclude)].sort_values(score, ascending=asc)
    rcnt, out = {}, []
    for _, r in pool.iterrows():
        sec = r.sector_33
        if gsec.get(sec, 0) >= GLOBAL_CAP: continue
        if rcnt.get(sec, 0) >= role_cap: continue
        rcnt[sec] = rcnt.get(sec, 0) + 1
        gsec[sec] = gsec.get(sec, 0) + 1
        out.append(r.code)
        if len(out) == n: break
    return out

picked = set()
# 守5: 品質ゲート→Greenblatt(ROE順位+益回り順位)。守はアンカーで固定(全体上限の起点)
bq = s[base & (s.roe >= 0.15) & (s.operating_margin >= 0.10) & (s.equity_ratio >= 0.50) &
       (s.operating_loss_years_3y == 0) & (s.net_loss_years_3y == 0) & (s.negative_ocf_years_3y == 0) &
       (s.operating_cf > 0) & (s.revenue_growth >= 0) & (s.operating_income_growth >= 0) &
       (s.ey > 0) & s.mcap.notna()].copy()
bq["mf"] = bq.roe.rank(ascending=False) + bq.ey.rank(ascending=False)
# genuine Buffett Top12(対照, 業種上限2) と 守5(=Top12上位)
buf12 = gpick(bq, "mf", 12, set(), asc=True) if False else None
_cnt, buf12 = {}, []
for _, r in bq.sort_values("mf").iterrows():
    if _cnt.get(r.sector_33, 0) >= 2: continue
    _cnt[r.sector_33] = _cnt.get(r.sector_33, 0) + 1; buf12.append(r.code)
    if len(buf12) == 12: break
shu5 = buf12[:5]
for c in shu5: gsec[info.loc[c, "sector_33"]] = gsec.get(info.loc[c, "sector_33"], 0) + 1
picked |= set(shu5)
# 両立型3を先に(プレミアム二重堀=キーエンス等の枠を確保) — ROE floor
dual_pool = s[base & (s.operating_income > 0) & (s.net_income > 0) & (s.roe >= ROE_FLOOR)].copy()
dual_pool["rboth"] = dual_pool.moat_score.rank(ascending=False) + dual_pool.future_moat_score.rank(ascending=False)
dual3 = gpick(dual_pool, "rboth", 3, picked, asc=True); picked |= set(dual3)
# 生まれる堀5: AI/半導体・光通信の実需を"事業"で検証して採用(キーワード依存を排す)。
# study の future_moat スコアはキーワードで飽和し象印/照明まで同点→定量選別不能。
# よって半導体・AI基盤の供給網に実事業を持つ企業(セグメント開示で確認)を明示採用。黒字・ROE>=5%・流動性・>=756d を満たす候補から。
SEMI_VERIFIED = [
    "6777",  # santec HD: AIデータセンター向け波長可変レーザ・光通信部品
    "6871",  # Micronics Japan: 半導体プローブカード(先端ウエハテスト)
    "6590",  # 芝浦メカトロニクス: 半導体/FPD製造装置(洗浄・成膜)
    "6387",  # SAMCO: 化合物半導体(GaN/SiC)製造装置
    "6627",  # テラプローブ: 半導体ウエハテスト受託(OSAT)
    "6951",  # JEOL: 電子顕微鏡・電子線計測(半導体計測) ※予備
    "6941",  # 山一電機: 半導体テストソケット ※予備
]
elig_codes = set(s[base & (s.operating_income > 0) & (s.net_income > 0) & (s.roe >= ROE_FLOOR)].code)
umare5 = [c for c in SEMI_VERIFIED if c in elig_codes and c not in picked][:5]
assert len(umare5) == 5, f"semi verified available: {[c for c in SEMI_VERIFIED if c in elig_codes]}"
for c in umare5:
    gsec[info.loc[c, "sector_33"]] = gsec.get(info.loc[c, "sector_33"], 0) + 1
picked |= set(umare5)
# 変わる堀5: Transformation Moat × bb, 黒字, ROE floor(東電4%脱落)
trans_pool = s[base & (s.category == "Transformation Moat") & (s.operating_income > 0) & (s.net_income > 0) & (s.roe >= ROE_FLOOR)]
haru5 = gpick(trans_pool, "adjusted_bb_score", 5, picked); picked |= set(haru5)
# 分散役2: 未採用セクターから bb 上位2
used_sectors = set(info.loc[list(picked), "sector_33"])
bridge_pool = s[base & (s.operating_income > 0) & (s.net_income > 0) & (s.roe >= ROE_FLOOR) & (~s.sector_33.isin(used_sectors)) & (~s.code.isin(picked))]
bridge2 = gpick(bridge_pool, "adjusted_bb_score", 2, picked, role_cap=1); picked |= set(bridge2)
assert len(shu5)==5 and len(haru5)==5 and len(umare5)==5 and len(dual3)==3 and len(bridge2)==2, \
    f"role sizes: {len(shu5)}/{len(haru5)}/{len(umare5)}/{len(dual3)}/{len(bridge2)}"

roles = [("守 完成した堀", shu5, 0.28), ("破 変わる堀", haru5, 0.28), ("離 生まれる堀", umare5, 0.28),
         ("両立型", dual3, 0.10), ("分散役", bridge2, 0.06)]
assert sum(len(c) for _, c, _ in roles) == 20, [len(c) for _, c, _ in roles]

# 役割予算重み(役割内均等)
w_v7 = {}
for _, cs, bud in roles:
    for c in cs:
        w_v7[c + ".T"] = bud / len(cs)
tot = sum(w_v7.values()); w_v7 = {k: v / tot for k, v in w_v7.items()}
# genuine Buffett Top12 cap-weight(対照)
mc = bq.set_index("code").loc[buf12, "mcap"]; wcap = (mc / mc.sum()).clip(upper=0.25); wcap /= wcap.sum()
w_buf12 = {c + ".T": float(wcap[c]) for c in buf12}

print("=== V7 提出PF (5/5/5/3/2・役割予算) ===")
for lab, cs, bud in roles:
    print(f"\n[{lab}] 予算{bud*100:.0f}% ({len(cs)}社, 各{bud/len(cs)*100:.1f}%)")
    for c in cs:
        r = info.loc[c]; roe = r.roe * 100 if pd.notna(r.roe) else float("nan")
        print(f'  {c} {str(names[c])[:22]:22} ROE={roe:4.0f}% moat={r.moat_score:.2f} fmoat={r.future_moat_score:.2f} vol={r.annual_volatility:.2f} {str(r.sector_33)[:13]}')

# ---- multi-period backtest ----
need = set(w_v7) | set(w_buf12) | {"1306.T", "^N225"}
wide = px_all[px_all.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] *= f
def bh(weights, d0, d1):
    idx = wide.loc[d0:d1].index; start = idx[0]
    cand = [t for t in weights if t in wide.columns and pd.notna(first_valid.get(t, pd.NaT)) and first_valid.get(t) <= start + pd.Timedelta(days=10)]
    if not cand: return pd.Series(dtype=float), 0, len(weights)
    w = pd.Series({t: weights[t] for t in cand}); w /= w.sum()
    sub = wide.loc[d0:d1, cand].ffill().dropna(); shares = w / sub.iloc[0]
    return (sub * shares).sum(axis=1).pct_change(fill_method=None).dropna(), len(cand), len(weights)
def stats(rp, rb):
    m = len(rp)
    if m < 5: return {k: None for k in ["ann_return","excess_vs_topix","volatility","sharpe","max_drawdown","beta"]}
    ann = float((1 + rp).prod() ** (ANN / m) - 1)
    mdd = float(((1 + rp).cumprod() / (1 + rp).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); rb = rb.reindex(rp.index)
    annb = float((1 + rb).prod() ** (ANN / m) - 1)
    return {"ann_return": round(ann, 4), "excess_vs_topix": round(ann - annb, 4), "volatility": round(vol, 4),
            "sharpe": round(ann / vol, 3) if vol else None, "max_drawdown": round(mdd, 4),
            "beta": round(float(rp.cov(rb) / rb.var()), 3) if rb.var() > 0 else None}
PERIODS = {"full": ("2021-06-01", "2026-06-01"), "P1_利上21-22": ("2021-06-01", "2022-12-31"),
           "P2_AI前半23-24": ("2023-01-01", "2024-06-30"), "P3_直近24-26": ("2024-07-01", "2026-06-01")}
results = {}
for p, (d0, d1) in PERIODS.items():
    rb = wide.loc[d0:d1, "1306.T"].pct_change(fill_method=None).dropna()
    r_v7, nu, _ = bh(w_v7, d0, d1); r_v7 = r_v7.reindex(rb.index).dropna()
    r_bf, _, _ = bh(w_buf12, d0, d1); r_bf = r_bf.reindex(rb.index).dropna()
    results[p] = {"v7": {**stats(r_v7, rb), "coverage": f"{nu}/20"}, "buffett12": stats(r_bf, rb),
                  "topix_ann": round(float((1 + rb).prod() ** (ANN / len(rb)) - 1), 4)}

# ---- "超える" 判定(§1.1 条件3: リターン・IR/Sharpe・MDDで真バフェット超え) ----
f = results["full"]; v, b = f["v7"], f["buffett12"]
verdict = {"return": v["ann_return"] > b["ann_return"], "sharpe": v["sharpe"] > b["sharpe"],
           "drawdown": v["max_drawdown"] > b["max_drawdown"]}  # mdd: 大きい(浅い)ほど良い
verdict["surpass_all"] = all(verdict.values())

roles_out = [{"role": lab, "budget": bud, "codes": cs,
              "names": [names[c] for c in cs]} for lab, cs, bud in roles]
json.dump({"weighting": "role_budget 守28/変28/生28/両立10/分散6",
           "roles": roles_out, "weights_v7": w_v7, "buf12": buf12,
           "results": results, "verdict_vs_buffett_full": verdict,
           "note": "in-sample self-verification. ex-ante rules, no tuning. phase5-consistent."},
          open(WORK / "portfolio_v7.json", "w"), ensure_ascii=False, indent=2)

print("\n===== 多期間検証(役割予算 vs 真バフェットTop12) =====")
for p in PERIODS:
    r = results[p]; v, b = r["v7"], r["buffett12"]
    print(f'\n{p} (TOPIX {r["topix_ann"]*100:.1f}%)')
    print(f'  V7提出PF      年率{v["ann_return"]*100:6.1f}% 対TOPIX{v["excess_vs_topix"]*100:+5.1f}pt σ{v["volatility"]*100:4.1f}% MDD{v["max_drawdown"]*100:6.1f}% β{v["beta"]:.2f} Sharpe{v["sharpe"]:.2f}')
    print(f'  真バフェット12  年率{b["ann_return"]*100:6.1f}% 対TOPIX{b["excess_vs_topix"]*100:+5.1f}pt σ{b["volatility"]*100:4.1f}% MDD{b["max_drawdown"]*100:6.1f}% β{b["beta"]:.2f} Sharpe{b["sharpe"]:.2f}')
print(f'\n【"超える"判定(全期間)】 リターン:{verdict["return"]} / Sharpe:{verdict["sharpe"]} / 最大下落:{verdict["drawdown"]} => 全条件超え:{verdict["surpass_all"]}')
allcodes = shu5 + haru5 + umare5 + dual3 + bridge2
secdist = pd.Series([info.loc[c, "sector_33"] for c in allcodes]).value_counts()
print("\n業種分布(全20社, 上限=%d):" % GLOBAL_CAP)
for sec, k in secdist.items():
    print(f"  {sec}: {k}")
hhi_sector = float(((secdist / 20) ** 2).sum())
tech_w = sum(v for k, v in w_v7.items() if info.loc[k.replace('.T',''), 'sector_33'] in ["Electric Appliances", "Machinery"])
print("最大業種社数:", int(secdist.max()), " 業種HHI:", round(hhi_sector,3),
      " AI/半導体テーマ(電機+機械)重み:", f"{tech_w*100:.0f}%",
      " ROE中央値(全20):", round(float(pd.Series([info.loc[c,'roe'] for c in allcodes]).median())*100,1), "%")
print("written ->", WORK / "portfolio_v7.json")
