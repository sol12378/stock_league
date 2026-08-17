# -*- coding: utf-8 -*-
"""多期間(レジーム感応度)検証: 固定バスケットが各相場でどう振る舞うか。

前提(査読防御): 全バスケットは2026-06の財務で選定→過去へ適用。よってこれは
「同一銘柄バスケットのレジーム感応度」の特性評価であり、ウォークフォワードの予測力ではない
(phase5と同じ in-sample 枠)。下げ相場での防御力=リスクの問いには答えられる。

バスケット(全て2026-06選定・固定):
  shu   真バフェット(割安×現在の堀)  = build_shuhari の score_shu 上位15
  ha    安全規律(低ボラ×優良)         = score_ha 上位15
  ri    未来の堀+安全規律             = score_ri 上位15
  ours  現行最終20社
  buf_lc 大型集中バフェット(時価総額加重top12) = build_pure_buffett
期間:
  full  2021-06 .. 2026-06 (全, 約4.85y)
  P1    2021-06 .. 2022-12  利上げ・バリュー相場(グロース調整)
  P2    2023-01 .. 2024-06  AI相場 前半
  P3    2024-07 .. 2026-06  直近(2024-08暴落を含む)
  crash 2024-07-25 .. 2024-08-09  日経暴落ストレス
計測: phase5規約(1306.T×10補正, pct_change fill_method=None, TOPIX=1306.T, 日経=^N225)。各期間内で買い持ち。
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

# ---- rebuild baskets (same rules as prior scripts) ----
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
elig = s[truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")].copy()
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
          "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "moat_score", "future_moat_score", "valuation_score",
          "annual_volatility", "stability_score", "net_income", "equity", "shares_outstanding"]:
    elig[c] = pd.to_numeric(elig[c], errors="coerce")

px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                         columns=["date", "ticker", "adj_close"])
px_all["date"] = pd.to_datetime(px_all["date"])
histmap = px_all.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())

Q = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
         (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
         (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
         (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)].copy()
Q["histdays"] = Q["ticker"].map(histmap).fillna(0)
Q = Q[Q.histdays >= 1000].copy()   # 多期間(全窓)を通せる履歴
def z(x): x = pd.to_numeric(x, errors="coerce"); return (x - x.mean()) / x.std(ddof=0)
Q["z_roe"], Q["z_moat"], Q["z_fmoat"] = z(Q.roe), z(Q.moat_score), z(Q.future_moat_score)
Q["z_val"], Q["z_lowvol"], Q["z_stab"] = z(Q.valuation_score), -z(Q.annual_volatility), z(Q.stability_score)
Q["score_shu"] = Q.z_roe + Q.z_moat + Q.z_val
Q["score_ha"] = Q.score_shu + Q.z_lowvol + Q.z_stab
Q["score_ri"] = Q.z_roe + Q.z_fmoat + Q.z_val + Q.z_lowvol
vol_med = Q.annual_volatility.median()

def select(df, score, n=15, cap=2, lowvol=False):
    d = df[df.annual_volatility <= vol_med] if lowvol else df
    d = d.sort_values(score, ascending=False); cnt, out = {}, []
    for _, r in d.iterrows():
        if cnt.get(r.sector_33, 0) >= cap: continue
        cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1; out.append(r.code)
        if len(out) == n: break
    return out

basket_codes = {"shu": select(Q, "score_shu"), "ha": select(Q, "score_ha", lowvol=True),
                "ri": select(Q, "score_ri", lowvol=True)}
# ours
alloc = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
alloc["ticker"] = alloc["code_n"].astype(str).str.zfill(4) + ".T"
w_ours = alloc.set_index("ticker")["target_weight_final"]
# canonical large-cap buffett (top12 cap-weight) — rebuild
elig["price_last"] = elig["ticker"].map(px_all.sort_values("date").groupby("ticker")["adj_close"].last())
elig["mcap"] = elig.price_last * elig.shares_outstanding; elig["ey"] = elig.net_income / elig.mcap
elig["pbr"] = elig.mcap / elig.equity
bq = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
          (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
          (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
          (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)].dropna(subset=["ey", "mcap"])
bq = bq[bq.ey > 0].copy()
bq["mf"] = bq.roe.rank(ascending=False) + bq.ey.rank(ascending=False)
buf_codes = select(bq.sort_values("mf"), "mf" if False else "roe") if False else None
# select top12 by mf with sector cap
d = bq.sort_values("mf"); cnt, buf = {}, []
for _, r in d.iterrows():
    if cnt.get(r.sector_33, 0) >= 2: continue
    cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1; buf.append(r.code)
    if len(buf) == 12: break
mc = bq.set_index("code").loc[buf, "mcap"]; wcap = (mc / mc.sum()).clip(upper=0.25); wcap = wcap / wcap.sum()
w_buf_lc = {c + ".T": float(wcap[c]) for c in buf}

# ---- panel ----
all_t = set()
for cs in basket_codes.values(): all_t |= {c + ".T" for c in cs}
all_t |= set(w_ours.index) | set(w_buf_lc)
need = all_t | {"1306.T", "^N225"}
wide = px_all[px_all.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] = wide.loc[wide.index >= d0, t] * f

PERIODS = {
    "full": ("2021-06-01", "2026-06-01"),
    "P1_2021-22利上げ": ("2021-06-01", "2022-12-31"),
    "P2_2023-24AI前半": ("2023-01-01", "2024-06-30"),
    "P3_2024-26直近": ("2024-07-01", "2026-06-01"),
    "crash_2024-08暴落": ("2024-07-25", "2024-08-09"),
}

first_valid = px_all.dropna(subset=["adj_close"]).groupby("ticker")["date"].min()

def bh_slice(tickers, weights, d0, d1):
    """買い持ち。始点(d0の5営業日以内)に存在する銘柄のみ採用し重みを再正規化。
    系列内の散発欠測はffill。被覆(採用数/総数)も返す。"""
    idx = wide.loc[d0:d1].index
    start = idx[0]
    cand = [t for t in tickers if t in wide.columns
            and pd.notna(first_valid.get(t, pd.NaT))
            and first_valid.get(t) <= start + pd.Timedelta(days=10)]
    if not cand:
        return pd.Series(dtype=float), 0, len(tickers)
    w = pd.Series({t: weights[t] for t in cand}); w = w / w.sum()
    sub = wide.loc[d0:d1, cand].ffill().dropna()
    shares = w / sub.iloc[0]
    val = (sub * shares).sum(axis=1)
    return val.pct_change(fill_method=None).dropna(), len(cand), len(tickers)

def idx_ret(t, d0, d1):
    x = wide.loc[d0:d1, t].dropna()
    return x.pct_change(fill_method=None).dropna()

def stats(rp, rb):
    n = len(rp)
    tot = float((1 + rp).prod() - 1)
    ann = float((1 + rp).prod() ** (ANN / n) - 1) if n > 20 else tot
    mdd = float(((1 + rp).cumprod() / (1 + rp).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN))
    rb = rb.reindex(rp.index)
    exc = ann - (float((1 + rb).prod() ** (ANN / n) - 1) if n > 20 else float((1 + rb).prod() - 1))
    beta = float(rp.cov(rb) / rb.var()) if rb.var() > 0 else float("nan")
    return {"total_return": round(tot, 4), "ann_return": round(ann, 4), "excess_vs_topix": round(exc, 4),
            "volatility": round(vol, 4), "sharpe": round(ann / vol, 3) if vol else None,
            "max_drawdown": round(mdd, 4), "beta": round(beta, 3), "days": n}

baskets = {"shu": ({c + ".T": 1 / len(basket_codes["shu"]) for c in basket_codes["shu"]}),
           "ha": ({c + ".T": 1 / len(basket_codes["ha"]) for c in basket_codes["ha"]}),
           "ri": ({c + ".T": 1 / len(basket_codes["ri"]) for c in basket_codes["ri"]}),
           "ours": w_ours.to_dict(), "buf_lc": w_buf_lc}

results = {}
for pname, (d0, d1) in PERIODS.items():
    rb = idx_ret("1306.T", d0, d1)
    results[pname] = {"topix": {**stats(rb, rb), "coverage": "20/20"}}
    for bname, w in baskets.items():
        rp, nused, ntot = bh_slice(list(w.keys()), w, d0, d1)
        rp = rp.reindex(rb.index).dropna()
        st = stats(rp, rb)
        st["coverage"] = f"{nused}/{ntot}"
        results[pname][bname] = st

json.dump({"results": results, "baskets": {k: basket_codes.get(k, list(baskets[k].keys())) for k in baskets},
           "note": "in-sample regime-sensitivity of FIXED baskets (2026-06 selection). NOT walk-forward. phase5-consistent."},
          open(WORK / "multiperiod_results.json", "w"), ensure_ascii=False, indent=2)

lab = {"shu": "守 真バフェット", "ha": "破 安全規律", "ri": "離 未来の堀+安全", "ours": "ours最終20", "buf_lc": "大型集中バフェット", "topix": "TOPIX"}
for pname in PERIODS:
    print(f"\n===== {pname} =====")
    print(f'{"":22}{"総ﾘﾀｰﾝ":>8}{"年率":>7}{"対TOPIX":>9}{"σ":>7}{"MDD":>8}{"β":>6}{"Sharpe":>8}{"採用":>7}')
    for k in ["topix", "shu", "buf_lc", "ha", "ri", "ours"]:
        st = results[pname][k]
        exc = f'{st["excess_vs_topix"]*100:+6.1f}pt' if k != "topix" else "   ---  "
        print(f'{lab[k]:22}{st["total_return"]*100:6.1f}%{st["ann_return"]*100:6.1f}%{exc:>9}{st["volatility"]*100:6.1f}%{st["max_drawdown"]*100:7.1f}%{st["beta"]:6.2f}{(st["sharpe"] if st["sharpe"] is not None else float("nan")):8.2f}{st["coverage"]:>7}')
print("\nwritten ->", WORK / "multiperiod_results.json")
