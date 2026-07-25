# -*- coding: utf-8 -*-
"""新バフェット型の対照群を 12社(現行)/15社(業種上限飽和)/20社(全プール) で再計算し、
v9本文の結論(条件④)がどう動くかを検証する。方法は build_report_data_v7.py と同一。"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
WORK = ROOT / "work/pure_buffett_benchmark"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
W3Y, W1Y = 756, 252

pf = json.load(open(WORK / "portfolio_v7.json"))
w_v7 = pf["weights_v7"]
buf12_published = pf["buf12"]

# --- priceableプール再現(build_pure_buffett.pyと同一) ---
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)
s["ticker"] = s["code"] + ".T"

def truthy(df, col):
    return df[col].astype(str).str.lower().isin(["true", "1", "1.0"])

elig = s[truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")].copy()
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "net_income", "equity",
          "revenue_growth", "operating_income_growth", "operating_loss_years_3y",
          "net_loss_years_3y", "negative_ocf_years_3y", "shares_outstanding"]:
    elig[c] = pd.to_numeric(elig[c], errors="coerce")

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
last_px = px.sort_values("date").groupby("ticker")["adj_close"].last()
elig["price"] = elig["ticker"].map(last_px)
elig["mcap"] = elig["price"] * elig["shares_outstanding"]
elig["ey"] = elig["net_income"] / elig["mcap"]
elig["pbr"] = elig["mcap"] / elig["equity"]

quality = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
               (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
               (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
               (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)].copy()
p = quality.dropna(subset=["ey", "pbr", "mcap"])
p = p[p.ey > 0].copy()
p["r_q"] = p.roe.rank(ascending=False)
p["r_p"] = p.ey.rank(ascending=False)
p["mf"] = p.r_q + p.r_p
p = p.sort_values("mf")
assert len(p) == 20, len(p)

def pick(df, n, sector_cap=2):
    cnt, picked = {}, []
    for _, r in df.iterrows():
        sec = r["sector_33"]
        if cnt.get(sec, 0) >= sector_cap:
            continue
        cnt[sec] = cnt.get(sec, 0) + 1
        picked.append(r["code"])
        if len(picked) == n:
            break
    return picked

buf12 = pick(p, 12)
buf15 = pick(p, 99)          # 業種2社上限の飽和点(=15)
buf20 = list(p["code"])      # 全プール(業種上限なし)
assert buf12 == buf12_published, (buf12, buf12_published)
assert len(buf15) == 15

def capweight(codes):
    mc = p.set_index("code").loc[codes, "mcap"]
    w = (mc / mc.sum()).clip(upper=0.25)
    w /= w.sum()
    return {c + ".T": float(w[c]) for c in codes}

controls = {"buf12(現行)": capweight(buf12), "buf15(業種上限飽和)": capweight(buf15), "buf20(全プール)": capweight(buf20)}

# --- 価格パネル(v7と同一規約) ---
need = set(w_v7) | {"1306.T", "^N225"}
for w in controls.values():
    need |= set(w)
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f

def rebal_daily(weights, window):
    tks = [t for t in weights if t in wide.columns]
    sub = wide[tks].tail(window).ffill()
    ok = [t for t in tks if sub[t].notna().sum() >= window - 2]
    w = pd.Series({t: weights[t] for t in ok}); w /= w.sum()
    r = wide[list(w.index)].tail(window).ffill().pct_change(fill_method=None).dropna()
    return (r[w.index] * w.values).sum(axis=1)

def idx_daily(t, window):
    return wide[t].tail(window).pct_change(fill_method=None).dropna()

def block(rp, rb):
    rb = rb.reindex(rp.index)
    ar = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    mdd = lambda x: float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); a = ar(rp)
    te = float((rp - rb).std() * np.sqrt(ANN))
    return {"ann": a, "ex_topix": a - ar(rb), "sharpe": a / vol, "mdd": mdd(rp),
            "beta": float(rp.cov(rb) / rb.var()),
            "ir": float((rp - rb).mean() * ANN / te) if te > 0 else None}

def nw_t(x):
    x = x.dropna().values; n = len(x)
    xbar = x.mean(); e = x - xbar
    L = int(np.floor(4 * (n / 100) ** (2 / 9)))
    g0 = (e @ e) / n; lrv = g0
    for j in range(1, L + 1):
        gj = (e[j:] @ e[:-j]) / n; lrv += 2 * (1 - j / (L + 1)) * gj
    return float(xbar / np.sqrt(lrv / n))

name_map = p.set_index("code")
print("=== 追加される銘柄 ===")
for label, codes in [("13-15位(buf15で追加)", buf15[12:]), ("業種上限で外れていた5社(buf20で追加)", [c for c in buf20 if c not in buf15])]:
    for c in (codes if isinstance(codes, list) else [codes]):
        r = name_map.loc[c]
        print(f"  {label}: {c} {r['sector_33']} mcap={r['mcap']/1e8:,.0f}億円")

for wn, win in [("3y", W3Y), ("1y", W1Y)]:
    rb = idx_daily("1306.T", win)
    r_ours = rebal_daily(w_v7, win)
    b_ours = block(r_ours, rb)
    print(f"\n=== {wn} ===")
    print(f"{'PF':24s} {'年率':>7s} {'対TOPIX':>8s} {'Sharpe':>7s} {'MDD':>7s} {'β':>5s} {'IR':>6s}  vs本PF NW-t")
    print(f"{'本PF(20社)':24s} {b_ours['ann']*100:6.1f}% {b_ours['ex_topix']*100:+7.1f}p {b_ours['sharpe']:7.2f} {b_ours['mdd']*100:6.1f}% {b_ours['beta']:5.2f} {b_ours['ir']:6.2f}")
    for name, w in controls.items():
        r_c = rebal_daily(w, win)
        b = block(r_c, rb)
        t = nw_t(r_ours - r_c.reindex(r_ours.index))
        print(f"{name:24s} {b['ann']*100:6.1f}% {b['ex_topix']*100:+7.1f}p {b['sharpe']:7.2f} {b['mdd']*100:6.1f}% {b['beta']:5.2f} {b['ir']:6.2f}  t={t:+.2f}")
