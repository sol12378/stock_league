# -*- coding: utf-8 -*-
"""守破離(真バフェット=守)の事前定義的構築と検証。

規律(査読防御): スコアは全て単位重み(+1)のzスコア合成。係数を「勝つように」調整しない。
同一ユニバース(クオリティ関門通過166社)・同一構築(上位15・同一セクター上限2・等金額・買い持ち)。
差は「スコア=思想」だけ。出た数字をそのまま報告。計測はphase5規約に完全一致。

  守 (Buffett faithful) : z(ROE)+z(moat)+z(valuation)                 … 割安×優良(現在の堀)
  破 (Buffett done right): 守 + z(low_vol)+z(stability) & 低ボラ半分に限定 … 本人が実は持つ「安全(低β/低ボラ)」規律を復元
  離 (beyond Buffett)   : z(ROE)+z(future_moat)+z(valuation)+z(low_vol) … 現在の堀→「未来の堀」に差し替え, 破の安全規律は維持
参考: canonical large-cap Buffett (時価総額加重・買い持ち) = pure_buffett_results の buffett_capw_bh。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
WORK = ROOT / "work/pure_buffett_benchmark"

ANN = 252
WINDOWS = {"3y": 756, "1y": 252}
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

# ---------------- quality universe Q ----------------
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
elig = s[truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")].copy()
numc = ["roe", "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
        "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
        "negative_ocf_years_3y", "moat_score", "future_moat_score", "valuation_score",
        "annual_volatility", "stability_score"]
for c in numc:
    elig[c] = pd.to_numeric(elig[c], errors="coerce")
Q = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
         (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
         (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
         (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)].copy()

# price panel + history filter
px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                         columns=["date", "ticker", "adj_close"])
histmap = px_all.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())
Q["histdays"] = Q["ticker"].map(histmap).fillna(0)
Q = Q[Q.histdays >= 756].copy()   # 3年BH可能のみ

def z(x):
    x = pd.to_numeric(x, errors="coerce")
    return (x - x.mean()) / x.std(ddof=0)

Q["z_roe"] = z(Q.roe); Q["z_moat"] = z(Q.moat_score); Q["z_fmoat"] = z(Q.future_moat_score)
Q["z_val"] = z(Q.valuation_score); Q["z_lowvol"] = -z(Q.annual_volatility); Q["z_stab"] = z(Q.stability_score)

Q["score_shu"] = Q.z_roe + Q.z_moat + Q.z_val
Q["score_ha"] = Q.z_roe + Q.z_moat + Q.z_val + Q.z_lowvol + Q.z_stab
Q["score_ri"] = Q.z_roe + Q.z_fmoat + Q.z_val + Q.z_lowvol

vol_med = Q.annual_volatility.median()

def select(df, score, n=15, sector_cap=2, lowvol_only=False):
    d = df.copy()
    if lowvol_only:
        d = d[d.annual_volatility <= vol_med]
    d = d.sort_values(score, ascending=False)
    cnt, picked = {}, []
    for _, r in d.iterrows():
        sec = r["sector_33"]
        if cnt.get(sec, 0) >= sector_cap:
            continue
        cnt[sec] = cnt.get(sec, 0) + 1
        picked.append(r["code"])
        if len(picked) == n:
            break
    return picked

sel_shu = select(Q, "score_shu")
sel_ha = select(Q, "score_ha", lowvol_only=True)
sel_ri = select(Q, "score_ri", lowvol_only=True)

# ---------------- backtest harness (phase5-consistent) ----------------
def load_panel(tickers):
    need = set(tickers) | {"1306.T", "^N225"}
    p = px_all[px_all["ticker"].isin(need)]
    wide = p.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
    for t, (d0, f) in SPLIT_FIXES.items():
        if t in wide.columns:
            wide.loc[wide.index >= d0, t] = wide.loc[wide.index >= d0, t] * f
    return wide

def stats(rp, rb, rn):
    ar = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    mdd = lambda x: float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); beta = float(rp.cov(rb) / rb.var())
    te = float((rp - rb).std() * np.sqrt(ANN)); ir = float((rp - rb).mean() * ANN / te) if te > 0 else float("nan")
    a = ar(rp)
    return {"ann_return": round(a, 4), "excess_vs_topix": round(a - ar(rb), 4),
            "volatility": round(vol, 4), "sharpe": round(a / vol, 3) if vol else None,
            "max_drawdown": round(mdd(rp), 4), "beta_vs_topix": round(beta, 3),
            "information_ratio": round(ir, 3)}

def bh_returns(wide, codes, window):
    tks = [c + ".T" for c in codes if c + ".T" in wide.columns]
    sub = wide[tks].tail(window)
    w = pd.Series(1.0 / len(tks), index=tks)
    shares = w / sub.iloc[0]
    val = (sub * shares).sum(axis=1)
    return val.pct_change(fill_method=None).dropna()

all_codes = set(sel_shu) | set(sel_ha) | set(sel_ri)
wide = load_panel([c + ".T" for c in all_codes])
rbF = wide["1306.T"].pct_change(fill_method=None); rnF = wide["^N225"].pct_change(fill_method=None)

results = {}
for wn, win in WINDOWS.items():
    results[wn] = {}
    for name, codes in [("shu_buffett", sel_shu), ("ha_safe", sel_ha), ("ri_futuremoat", sel_ri)]:
        rp = bh_returns(wide, codes, win); idx = rp.index
        results[wn][name] = stats(rp, rbF.reindex(idx), rnF.reindex(idx))
        results[wn][name]["topix_ann_return"] = round(float((1 + rbF.reindex(idx)).prod() ** (ANN / len(idx)) - 1), 4)

def profile(codes):
    d = Q[Q.code.isin(codes)]
    return {"roe_med": round(float(d.roe.median()), 3), "vol_med": round(float(d.annual_volatility.median()), 3),
            "moat_med": round(float(d.moat_score.median()), 3), "fmoat_med": round(float(d.future_moat_score.median()), 3),
            "n": len(codes)}

members = {name: [{"code": r.code, "name": r.company_name, "sector": r.sector_33,
                   "roe": round(float(r.roe), 3), "vol": round(float(r.annual_volatility), 3),
                   "moat": round(float(r.moat_score), 3), "fmoat": round(float(r.future_moat_score), 3)}
                  for _, r in Q[Q.code.isin(codes)].iterrows()]
           for name, codes in [("shu", sel_shu), ("ha", sel_ha), ("ri", sel_ri)]}

json.dump({"results": results,
           "profiles": {"shu": profile(sel_shu), "ha": profile(sel_ha), "ri": profile(sel_ri)},
           "members": members,
           "note": "score=unit-weight z composites (no tuning). universe=Q(166 quality, >=756d). top15/sector<=2/equal-weight/buy-hold. phase5-consistent."},
          open(WORK / "shuhari_results.json", "w"), ensure_ascii=False, indent=2)

# ---------------- console ----------------
lab = {"shu_buffett": "守 真バフェット(割安×現在の堀)", "ha_safe": "破 安全規律を復元(低ボラ×優良)",
       "ri_futuremoat": "離 未来の堀(future moat)+安全規律"}
for wn in ["3y", "1y"]:
    tp = results[wn]["shu_buffett"]["topix_ann_return"] * 100
    print(f"\n===== {wn} (TOPIX={tp:.1f}%) =====")
    print(f'{"":34}{"年率":>7}{"対TOPIX":>9}{"σ":>7}{"MDD":>8}{"β":>6}{"Sharpe":>8}')
    for k in ["shu_buffett", "ha_safe", "ri_futuremoat"]:
        st = results[wn][k]
        print(f'{lab[k]:34}{st["ann_return"]*100:6.1f}%{st["excess_vs_topix"]*100:+8.1f}pt{st["volatility"]*100:6.1f}%{st["max_drawdown"]*100:7.1f}%{st["beta_vs_topix"]:6.2f}{st["sharpe"]:8.2f}')
print("\nprofiles:", json.dumps({k: profile(v) for k, v in [("shu", sel_shu), ("ha", sel_ha), ("ri", sel_ri)]}, ensure_ascii=False))
for tag, codes in [("守", sel_shu), ("破", sel_ha), ("離", sel_ri)]:
    names = [f"{r.code} {str(r.company_name)[:14]}" for _, r in Q[Q.code.isin(codes)].sort_values("annual_volatility").iterrows()]
    print(f"\n{tag} ({len(codes)}社):", " / ".join(names))
print("\nwritten ->", WORK / "shuhari_results.json")
