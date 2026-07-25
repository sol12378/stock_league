# -*- coding: utf-8 -*-
"""v10 対照群の正典データ生成。

v9からの変更(V10_PLAN.md E-1):
  主対照 = 新バフェット型20社(品質関門を通過し価格順位を付けられた全プール)。
  重みは二通りを両建てで開示する。
    期首加重 = 各測定窓の期首株価×発行済株数(=当時実際に組めた重み。主系列)
    期末加重 = 直近株価×発行済株数(=実現リターンで膨らんだ事後の重み。最も厳しい仮想対照)
  社数(12/15/20)×重み(期首/期末/等金額)の全変形を感応度として開示する。
計測規約はv7と同一(756/252日・固定重み日次リバランス・1306.T×10補正)。
相場局面はbuild_multiperiod.pyと同一日付・各期間内買い持ち。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
W3Y, W1Y = 756, 252
PHASES = {
    "P1_2021-22利上げ": ("2021-06-01", "2022-12-31"),
    "P2_2023-24AI前半": ("2023-01-01", "2024-06-30"),
    "P3_2024-26直近": ("2024-07-01", "2026-06-30"),
    "crash_2024-08暴落": ("2024-07-25", "2024-08-09"),
}

pf = json.load(open(WORK / "portfolio_v7.json"))
w_v7 = pf["weights_v7"]
buf12_published = pf["buf12"]

# ---------- 新バフェット型プールの再現(build_pure_buffett.pyと同一) ----------
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

quality = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
               (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
               (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
               (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)].copy()
p = quality.dropna(subset=["ey", "mcap"])
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
buf15 = pick(p, 99)
buf20 = list(p["code"])
assert buf12 == buf12_published, (buf12, buf12_published)
assert len(buf15) == 15

# ---------- グレアム対照(v7と同一) ----------
pool = pd.read_csv(ROOT / "outputs/phase1_top5/phase1_top5_candidate_pool.csv")
pool["code"] = pool["code"].astype(str).str.zfill(4)
_sc, _g = {}, []
for _, r in pool.iterrows():
    if _sc.get(r["sector"], 0) >= 2:
        continue
    _sc[r["sector"]] = _sc.get(r["sector"], 0) + 1
    _g.append(r["code"])
    if len(_g) == 20:
        break
w_graham = {c + ".T": 1 / 20 for c in _g}

# ---------- 価格パネル ----------
need = set(w_v7) | set(w_graham) | {"1306.T", "^N225"} | {c + ".T" for c in buf20}
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f

shares = p.set_index("code")["shares_outstanding"]


def capweight(codes, window=None, cap=0.25):
    """時価総額加重。window=None なら期末株価、整数なら『その窓の期首株価』で加重。"""
    if window is None:
        px_ref = pd.Series({c: float(wide[c + ".T"].ffill().iloc[-1]) for c in codes})
    else:
        sub = wide.tail(window).ffill()
        px_ref = pd.Series({c: float(sub[c + ".T"].iloc[0]) for c in codes})
    mc = px_ref * shares.loc[codes]
    w = (mc / mc.sum()).clip(upper=cap)
    w /= w.sum()
    return {c + ".T": float(w[c]) for c in codes}


def eqweight(codes):
    return {c + ".T": 1 / len(codes) for c in codes}


def rebal_daily(weights, window):
    tks = [t for t in weights if t in wide.columns]
    sub = wide[tks].tail(window).ffill()
    ok = [t for t in tks if sub[t].notna().sum() >= window - 2]
    w = pd.Series({t: weights[t] for t in ok})
    w /= w.sum()
    r = wide[list(w.index)].tail(window).ffill().pct_change(fill_method=None).dropna()
    return (r[w.index] * w.values).sum(axis=1)


def idx_daily(t, window):
    return wide[t].tail(window).pct_change(fill_method=None).dropna()


def bh_period(weights, d0, d1):
    """期間内買い持ち(株数固定)。"""
    sub = wide.loc[(wide.index >= d0) & (wide.index <= d1)].ffill()
    tks = [t for t in weights if t in sub.columns and sub[t].notna().sum() >= len(sub) - 2 and pd.notna(sub[t].iloc[0])]
    w = pd.Series({t: weights[t] for t in tks})
    w /= w.sum()
    nav = (sub[list(w.index)] / sub[list(w.index)].iloc[0] * w.values).sum(axis=1)
    return nav.pct_change().dropna(), f"{len(tks)}/{len(weights)}"


def block(rp, rb):
    rb = rb.reindex(rp.index)
    ar = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    mdd = lambda x: float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN))
    a = ar(rp)
    te = float((rp - rb).std() * np.sqrt(ANN))
    return {"ann_return": round(a, 4), "topix_ann_return": round(ar(rb), 4),
            "excess_vs_topix": round(a - ar(rb), 4), "volatility": round(vol, 4),
            "sharpe": round(a / vol, 3), "max_drawdown": round(mdd(rp), 4),
            "topix_max_drawdown": round(mdd(rb), 4),
            "beta_vs_topix": round(float(rp.cov(rb) / rb.var()), 3),
            "information_ratio": round(float((rp - rb).mean() * ANN / te), 3) if te > 0 else None}


def nw(x):
    x = x.dropna().values
    n = len(x)
    xbar = x.mean()
    e = x - xbar
    L = int(np.floor(4 * (n / 100) ** (2 / 9)))
    g0 = (e @ e) / n
    lrv = g0
    for j in range(1, L + 1):
        lrv += 2 * (1 - j / (L + 1)) * ((e[j:] @ e[:-j]) / n)
    return {"mean_excess_ann": round(float(xbar * ANN), 4),
            "t_plain": round(float(xbar / (x.std(ddof=1) / np.sqrt(n))), 2),
            "t_newey_west": round(float(xbar / np.sqrt(lrv / n)), 2), "nw_lag": L, "n": n}


# ---------- 主系列 ----------
out = {"convention": ("主規約=固定重み日次リバランス(3年=756営業日・直近1年=252営業日)。"
                      "主対照=新バフェット型20社・期首時価総額加重(上限25%)。"
                      "併記=同20社・期末時価総額加重。参考=純正グレアム型20社(等金額)。"),
       "buf_pool": {"buf12": buf12, "buf15": buf15, "buf20": buf20},
       "graham20": _g}
sig = {}
sens = {}

for wn, win in [("3y", W3Y), ("1y", W1Y)]:
    rb = idx_daily("1306.T", win)
    rn = idx_daily("^N225", win)
    r_ours = rebal_daily(w_v7, win)
    series = {
        "ours": r_ours,
        "ours_equal": rebal_daily(eqweight([c.replace(".T", "") for c in w_v7]), win),
        "control_buffett20_start": rebal_daily(capweight(buf20, window=win), win),
        "control_buffett20_end": rebal_daily(capweight(buf20), win),
        "control_graham": rebal_daily(w_graham, win),
    }
    for k, r in series.items():
        b = block(r, rb)
        b["nikkei_ann_return"] = round(float((1 + rn.reindex(r.index)).prod() ** (ANN / len(r)) - 1), 4)
        out.setdefault(k, {})[wn] = b
    # レバレッジ参考(β・σを対照に合わせる)
    tgt = series["control_buffett20_end"].std()
    lev = float(tgt / r_ours.std())
    b = block(r_ours * lev, rb)
    b["leverage"] = round(lev, 2)
    b["nikkei_ann_return"] = round(float((1 + rn.reindex(r_ours.index)).prod() ** (ANN / len(r_ours)) - 1), 4)
    out.setdefault("ours_vol_matched", {})[wn] = b
    # 有意性
    sig[wn] = {
        "ours_vs_buffett20_start": nw(r_ours - series["control_buffett20_start"].reindex(r_ours.index)),
        "ours_vs_buffett20_end": nw(r_ours - series["control_buffett20_end"].reindex(r_ours.index)),
        "ours_vs_graham": nw(r_ours - series["control_graham"].reindex(r_ours.index)),
        "ours_vs_topix": nw(r_ours - rb.reindex(r_ours.index)),
    }
    # 感応度(社数×重み)
    for n, codes in [(12, buf12), (15, buf15), (20, buf20)]:
        for lab, w in [("期首加重", capweight(codes, window=win)), ("期末加重", capweight(codes)),
                       ("等金額", eqweight(codes))]:
            r = rebal_daily(w, win)
            bb = block(r, rb)
            sens.setdefault(f"{n}社_{lab}", {})[wn] = {
                "ann_return": bb["ann_return"], "sharpe": bb["sharpe"],
                "max_drawdown": bb["max_drawdown"], "beta_vs_topix": bb["beta_vs_topix"],
                "ours_minus": round(out["ours"][wn]["ann_return"] - bb["ann_return"], 4),
                "t_newey_west": nw(r_ours - r.reindex(r_ours.index))["t_newey_west"]}

# ---------- 相場局面 ----------
phases = {}
for pname, (d0, d1) in PHASES.items():
    rb, _ = bh_period({"1306.T": 1.0}, d0, d1)
    row = {}
    for k, w in [("ours", w_v7),
                 ("control_buffett20_start", capweight(buf20, window=W3Y)),
                 ("control_buffett20_end", capweight(buf20))]:
        r, cov = bh_period(w, d0, d1)
        b = block(r, rb)
        b["coverage"] = cov
        b["days"] = len(r)
        b["total_return"] = round(float((1 + r).prod() - 1), 4)
        row[k] = b
    row["topix"] = {"total_return": round(float((1 + rb).prod() - 1), 4),
                    "ann_return": round(float((1 + rb).prod() ** (ANN / len(rb)) - 1), 4),
                    "max_drawdown": round(float(((1 + rb).cumprod() / (1 + rb).cumprod().cummax() - 1).min()), 4)}
    phases[pname] = row

# ---------- 配分方式の頑健性(均等/役割予算/最小分散) ----------
from scipy.optimize import minimize

wv = {}
for wn, win in [("3y", W3Y), ("1y", W1Y)]:
    rb = idx_daily("1306.T", win)
    tks = list(w_v7)
    R = wide[tks].tail(win).ffill().pct_change(fill_method=None).dropna()
    cov = R.cov().values
    n = len(tks)
    res = minimize(lambda x: float(x @ cov @ x), np.repeat(1 / n, n), method="SLSQP",
                   bounds=[(0.0, 0.25)] * n,
                   constraints=[{"type": "eq", "fun": lambda x: x.sum() - 1}])
    w_mv = {t: float(v) for t, v in zip(tks, res.x)}
    for lab, w in [("均等", eqweight([c.replace(".T", "") for c in w_v7])),
                   ("役割予算(採用)", w_v7), ("最小分散", w_mv)]:
        b = block(rebal_daily(w, win), rb)
        wv.setdefault(lab, {})[wn] = {"ann_return": b["ann_return"], "sharpe": b["sharpe"],
                                      "max_drawdown": b["max_drawdown"],
                                      "vs_main_control": round(b["ann_return"] - out["control_buffett20_start"][wn]["ann_return"], 4)}
out["weighting_variants"] = wv

out["weights"] = {"ours": w_v7, "graham20": w_graham,
                  "buf20_start3y": capweight(buf20, window=W3Y), "buf20_end": capweight(buf20)}
out["sensitivity"] = sens
out["phases"] = phases
out["phase_convention"] = "各期間内は株数固定の買い持ち。期首加重は3年窓の期首株価で算出した重みを流用。"
json.dump(out, open(ED / "control_comparison_v10.json", "w"), ensure_ascii=False, indent=1)
json.dump(sig, open(ED / "significance_v10.json", "w"), ensure_ascii=False, indent=1)

# ---------- 画面出力 ----------
for wn in ["3y", "1y"]:
    print(f"\n=== {wn} ===")
    for k in ["ours", "ours_equal", "ours_vol_matched", "control_buffett20_start",
              "control_buffett20_end", "control_graham"]:
        b = out[k][wn]
        print(f"{k:26s} ann={b['ann_return']*100:6.1f}% sh={b['sharpe']:5.2f} mdd={b['max_drawdown']*100:6.1f}% "
              f"b={b['beta_vs_topix']:5.2f} ir={b['information_ratio']}")
    for k, v in sig[wn].items():
        print(f"  NW-t {k:28s} {v['t_newey_west']:+.2f} (mean_ex={v['mean_excess_ann']*100:+.1f}p)")
print("\n=== 感応度(3年 年率) ===")
for k, v in sens.items():
    print(f"{k:14s} 3y={v['3y']['ann_return']*100:6.1f}% (差{v['3y']['ours_minus']*100:+5.1f}p, t={v['3y']['t_newey_west']:+.2f})"
          f"  1y={v['1y']['ann_return']*100:6.1f}% (差{v['1y']['ours_minus']*100:+6.1f}p, t={v['1y']['t_newey_west']:+.2f})")
print("\n=== 相場局面(買い持ち) ===")
for pn, row in phases.items():
    print(pn, {k: (round(v['ann_return']*100, 1), round(v.get('sharpe', 0) or 0, 2), round(v['max_drawdown']*100, 1))
               for k, v in row.items()})
print("\nwritten -> control_comparison_v10.json / significance_v10.json")
