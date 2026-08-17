# -*- coding: utf-8 -*-
"""逐次AND(守→破→離)で20社を実際に組成し、現行20社・TOPIXと同一規約で比較。

計測規約は work/pure_buffett_benchmark/build_portfolio_v7.py と同一
(1306.T=TOPIX連動ETFをベンチマーク、ANN=252、期間4区分、buy&hold)。
in-sample の自己検証であることは現行と同じ。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUTJ = Path(__file__).with_name("and_backtest.json")
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["adjusted_bb_score", "moat_score", "future_moat_score", "transformation_score", "roe",
          "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
          "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "operating_income", "net_income", "equity",
          "shares_outstanding", "annual_volatility"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")

px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px_all["date"] = pd.to_datetime(px_all["date"])
histd = px_all.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())
s["histd"] = s["ticker"].map(histd).fillna(0)
first_valid = px_all.dropna(subset=["adj_close"]).groupby("ticker")["date"].min()
last_px = px_all.sort_values("date").groupby("ticker")["adj_close"].last()
s["mcap"] = s.ticker.map(last_px) * s.shares_outstanding
s["ey"] = s.net_income / s.mcap

base = (truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")
        & truthy(s, "liquid_20m_60d") & (s.histd >= 756))
B = s[base].copy()
info = s.set_index("code")
names = s.set_index("code")["company_name"].to_dict()

SHU = ((B.roe >= 0.15) & (B.operating_margin >= 0.10) & (B.equity_ratio >= 0.50)
       & (B.operating_loss_years_3y == 0) & (B.net_loss_years_3y == 0)
       & (B.negative_ocf_years_3y == 0) & (B.operating_cf > 0)
       & (B.revenue_growth >= 0) & (B.operating_income_growth >= 0))
PROF = (B.operating_income > 0) & (B.net_income > 0) & (B.roe >= 0.05)
thr_tr = float(B.transformation_score.median())
thr_fm = float(B.future_moat_score.median())


def pick(df, score, n, cap=2, asc=False):
    cnt, out = {}, []
    for _, r in df.sort_values(score, ascending=asc).iterrows():
        if cnt.get(r.sector_33, 0) >= cap: continue
        cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1
        out.append(r.code)
        if len(out) == n: break
    return out


designs = {}
# --- A1: 提案どおりの逐次AND(守ハードゲート → 破:変革>中位 → 離:未来>中位)→ bb上位20(業種上限2)
poolA1 = B[SHU & PROF & (B.transformation_score > thr_tr) & (B.future_moat_score > thr_fm)]
designs["A1_逐次AND_中位閾値"] = {"pool_n": int(len(poolA1)), "codes": pick(poolA1, "adjusted_bb_score", 20)}
# --- A2: 3スコアそろって上位30%(守もスコア化)→ bb上位20
q = 0.30
tm, tt, tf = (B.moat_score.quantile(1 - q), B.transformation_score.quantile(1 - q),
              B.future_moat_score.quantile(1 - q))
poolA2 = B[PROF & (B.moat_score >= tm) & (B.transformation_score >= tt) & (B.future_moat_score >= tf)]
designs["A2_3スコア上位30%AND"] = {"pool_n": int(len(poolA2)), "codes": pick(poolA2, "adjusted_bb_score", 20)}
# --- A1c4 / A2c4: 同じプールで業種上限を4に緩めて20社を成立させる版
designs["A1c4_逐次AND_業種上限4"] = {"pool_n": int(len(poolA1)), "codes": pick(poolA1, "adjusted_bb_score", 20, cap=4)}
designs["A2c4_上位30%AND_業種上限4"] = {"pool_n": int(len(poolA2)), "codes": pick(poolA2, "adjusted_bb_score", 20, cap=4)}
# --- A3: 離を「事業検証済み7社」に限定した厳格AND
SEMI = ["6777", "6871", "6590", "6387", "6627", "6951", "6941"]
poolA3 = B[SHU & PROF & (B.transformation_score > thr_tr) & (B.code.isin(SEMI))]
designs["A3_厳格AND_離は事業検証"] = {"pool_n": int(len(poolA3)), "codes": sorted(poolA3.code.tolist())}
# --- A4: 順位和(AND緩和版) 3スコアの順位和が良い20社(全ゲート通過は要求しない)
poolA4 = B[PROF].copy()
poolA4["rsum"] = (poolA4.moat_score.rank(ascending=False) + poolA4.transformation_score.rank(ascending=False)
                  + poolA4.future_moat_score.rank(ascending=False))
designs["A4_3スコア順位和上位"] = {"pool_n": int(len(poolA4)), "codes": pick(poolA4, "rsum", 20, asc=True)}
# --- 現行20社(v7=v10/v11の正典)
CUR = ["3092", "4716", "7014", "8136", "6920", "9022", "9513", "9503", "1662", "5214",
       "6777", "6871", "6590", "6387", "6627", "6861", "7725", "6929", "3449", "4971"]
designs["現行20社_役割分担"] = {"pool_n": None, "codes": CUR}

W_CUR_ROLE = {}
for cs, bud in [(CUR[0:5], .28), (CUR[5:10], .28), (CUR[10:15], .28), (CUR[15:18], .10), (CUR[18:20], .06)]:
    for c in cs: W_CUR_ROLE[c + ".T"] = bud / len(cs)
tot = sum(W_CUR_ROLE.values()); W_CUR_ROLE = {k: v / tot for k, v in W_CUR_ROLE.items()}

need = {c + ".T" for d in designs.values() for c in d["codes"]} | {"1306.T"}
wide = px_all[px_all.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] *= f


def bh(weights, d0, d1):
    idx = wide.loc[d0:d1].index; start = idx[0]
    cand = [t for t in weights if t in wide.columns and pd.notna(first_valid.get(t, pd.NaT))
            and first_valid.get(t) <= start + pd.Timedelta(days=10)]
    if not cand: return pd.Series(dtype=float), 0, len(weights)
    w = pd.Series({t: weights[t] for t in cand}); w /= w.sum()
    sub = wide.loc[d0:d1, cand].ffill().dropna(); shares = w / sub.iloc[0]
    return (sub * shares).sum(axis=1).pct_change(fill_method=None).dropna(), len(cand), len(weights)


def stats(rp, rb):
    m = len(rp)
    if m < 5: return {k: None for k in ["ann_return", "excess_vs_topix", "volatility", "sharpe", "max_drawdown", "beta"]}
    ann = float((1 + rp).prod() ** (ANN / m) - 1)
    mdd = float(((1 + rp).cumprod() / (1 + rp).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); rb = rb.reindex(rp.index)
    annb = float((1 + rb).prod() ** (ANN / m) - 1)
    return {"ann_return": round(ann, 4), "excess_vs_topix": round(ann - annb, 4), "volatility": round(vol, 4),
            "sharpe": round(ann / vol, 3) if vol else None, "max_drawdown": round(mdd, 4),
            "beta": round(float(rp.cov(rb) / rb.var()), 3) if rb.var() > 0 else None}


PERIODS = {"full_21-26": ("2021-06-01", "2026-06-01"), "P1_利上21-22": ("2021-06-01", "2022-12-31"),
           "P2_AI前半23-24": ("2023-01-01", "2024-06-30"), "P3_直近24-26": ("2024-07-01", "2026-06-01")}

out = {"thresholds": {"transformation_median": round(thr_tr, 6), "future_moat_median": round(thr_fm, 6)},
       "designs": {}, "results": {}}
for k, d in designs.items():
    codes = d["codes"]
    sec = pd.Series([info.loc[c, "sector_33"] for c in codes]).value_counts()
    out["designs"][k] = {
        "pool_n": d["pool_n"], "n_picked": len(codes), "codes": codes,
        "names": [str(names[c]) for c in codes],
        "n_sectors": int(len(sec)) if len(codes) else 0,
        "max_sector_n": int(sec.max()) if len(codes) else 0,
        "sector_hhi": round(float(((sec / len(codes)) ** 2).sum()), 3) if codes else None,
        "roe_median": round(float(pd.Series([info.loc[c, "roe"] for c in codes]).median()) * 100, 1) if codes else None,
        "overlap_with_current": sorted(set(codes) & set(CUR)),
    }

for p, (d0, d1) in PERIODS.items():
    rb = wide.loc[d0:d1, "1306.T"].pct_change(fill_method=None).dropna()
    res = {"topix_ann": round(float((1 + rb).prod() ** (ANN / len(rb)) - 1), 4)}
    for k, d in designs.items():
        codes = d["codes"]
        if len(codes) < 2:
            res[k + " (等ウェイト)"] = {"note": "社数不足で組成不能", "n": len(codes)}
            continue
        w = {c + ".T": 1 / len(codes) for c in codes}
        r, nu, _ = bh(w, d0, d1); r = r.reindex(rb.index).dropna()
        res[k + " (等ウェイト)"] = {**stats(r, rb), "coverage": f"{nu}/{len(codes)}"}
    r, nu, _ = bh(W_CUR_ROLE, d0, d1); r = r.reindex(rb.index).dropna()
    res["現行20社 (役割予算=提出版)"] = {**stats(r, rb), "coverage": f"{nu}/20"}
    out["results"][p] = res

OUTJ.write_text(json.dumps(out, ensure_ascii=False, indent=1))

# --- 表示 ---
print("=== 組成可否 ===")
for k, v in out["designs"].items():
    print(f'{k:28} pool={v["pool_n"]} 採用={v["n_picked"]}社 業種数={v["n_sectors"]} 最大業種={v["max_sector_n"]} HHI={v["sector_hhi"]} ROE中央={v["roe_median"]}% 現行と重複={len(v["overlap_with_current"])}社')
print()
for p in PERIODS:
    r = out["results"][p]
    print(f'--- {p}  (TOPIX 年率{r["topix_ann"]*100:.1f}%) ---')
    for k, v in r.items():
        if k == "topix_ann": continue
        if "note" in v: print(f'  {k:36} {v["note"]} ({v["n"]}社)'); continue
        print(f'  {k:36} 年率{v["ann_return"]*100:7.1f}% 対TOPIX{v["excess_vs_topix"]*100:+6.1f}pt σ{v["volatility"]*100:5.1f}% MDD{v["max_drawdown"]*100:7.1f}% β{v["beta"]:.2f} Sharpe{v["sharpe"]:5.2f} [{v["coverage"]}]')
    print()
print("written ->", OUTJ)
