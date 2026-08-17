# -*- coding: utf-8 -*-
"""W1 / Layer 1: point-in-time (as-of) out-of-sample validation.

Pre-registered in V11_PROGRESS.md before execution (2026-07-25, iteration 1).

Only filings whose `submit_date` precedes the as-of date enter the screen, so the
selection at each as-of date could have been formed in real time.  The
three-consecutive-loss-free gate of the contest edition is *translated* into
"loss-free over the periods available at the as-of date", because at 2024-10-01
only two fiscal years are on file for most firms.  The translation is disclosed
in the manuscript (V11_PLAN.md §0.5).

Outputs: outputs/stockleague_edition/layer1_pit_v11.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
AS_OF = ["2024-10-01", "2025-04-01", "2025-10-01"]
END = pd.Timestamp("2026-06-01")
SECTOR_CAP = 2

# ---------------------------------------------------------------- data
fund = pd.read_csv(ROOT / "data/processed/fundamentals_raw.csv", dtype={"code": str}, low_memory=False)
fund["code"] = fund["code"].str.zfill(4)
fund["submit_date"] = pd.to_datetime(fund["submit_date"])
fund["period_end"] = pd.to_datetime(fund["period_end"])
for c in ["revenue", "operating_income", "net_income", "equity", "total_assets", "operating_cf"]:
    fund[c] = pd.to_numeric(fund[c], errors="coerce")

scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
scores["code"] = scores["code"].str.zfill(4)
attrs = scores.set_index("code")[["sector_33", "shares_outstanding", "is_financial", "company_name"]]
attrs["shares_outstanding"] = pd.to_numeric(attrs["shares_outstanding"], errors="coerce")
is_fin = attrs["is_financial"].astype(str).str.lower().isin(["true", "1", "1.0"])

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
wide = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f


# ---------------------------------------------------------------- screen
def pit_screen(as_of):
    """Quality gate using only filings submitted before `as_of`."""
    d = pd.Timestamp(as_of)
    sub = fund[fund.submit_date < d].sort_values(["code", "period_end"])
    n_docs, n_firms = len(sub), sub.code.nunique()
    # de-duplicate: keep the last filing per (code, period_end)
    sub = sub.drop_duplicates(subset=["code", "period_end"], keep="last")
    g = sub.groupby("code")
    counts = g.size()
    multi = counts[counts >= 2].index
    rows = []
    for code in multi:
        h = sub[sub.code == code]
        cur, prev = h.iloc[-1], h.iloc[-2]
        eq, rev = cur.equity, cur.revenue
        if not (pd.notna(eq) and eq > 0 and pd.notna(rev) and rev > 0):
            continue
        rows.append({
            "code": code, "n_periods": len(h),
            "roe": cur.net_income / eq if pd.notna(cur.net_income) else np.nan,
            "operating_margin": cur.operating_income / rev if pd.notna(cur.operating_income) else np.nan,
            "equity_ratio": eq / cur.total_assets if pd.notna(cur.total_assets) and cur.total_assets > 0 else np.nan,
            "operating_cf": cur.operating_cf,
            "revenue_growth": rev / prev.revenue - 1 if pd.notna(prev.revenue) and prev.revenue > 0 else np.nan,
            "oi_growth": (cur.operating_income / prev.operating_income - 1
                          if pd.notna(prev.operating_income) and prev.operating_income > 0
                          and pd.notna(cur.operating_income) else np.nan),
            "op_loss_avail": int((h.operating_income.fillna(0) <= 0).sum()),
            "net_loss_avail": int((h.net_income.fillna(0) <= 0).sum()),
            "neg_ocf_avail": int((h.operating_cf.fillna(0) < 0).sum()),
            "net_income": cur.net_income,
        })
    c = pd.DataFrame(rows).set_index("code")
    c = c.join(attrs[["sector_33", "shares_outstanding"]])
    c["is_financial"] = is_fin.reindex(c.index).fillna(False)
    funnel = {"as_of": as_of, "filings_on_file": int(n_docs), "firms_on_file": int(n_firms),
              "firms_with_2plus_periods": int(len(multi)), "firms_screenable": int(len(c))}

    q = c[(~c.is_financial) & (c.roe >= 0.15) & (c.operating_margin >= 0.10)
          & (c.equity_ratio >= 0.50) & (c.operating_cf > 0)
          & (c.revenue_growth >= 0) & (c.oi_growth >= 0)
          & (c.op_loss_avail == 0) & (c.net_loss_avail == 0) & (c.neg_ocf_avail == 0)].copy()
    funnel["passed_quality_gate"] = int(len(q))

    # price at the as-of date (last trading day strictly before it)
    hist = wide.loc[wide.index < d].ffill()
    px_asof = hist.iloc[-1] if len(hist) else pd.Series(dtype=float)
    q["price_asof"] = q.index.map(lambda x: px_asof.get(x + ".T", np.nan))
    q["mcap"] = q.price_asof * q.shares_outstanding  # available for 300 firms only; not used for ranking
    q = q.dropna(subset=["price_asof"])
    funnel["with_price_series"] = int(len(q))
    funnel["with_share_count"] = int(q.shares_outstanding.notna().sum())
    return q, funnel


def rank_pick(q, formula, n, cap=SECTOR_CAP):
    """Rank-sum selection with a per-sector cap. formula in {'roe_only','roe_margin'}.

    Both formulas use only quantities computable from the filings on file at the as-of date.
    The contest edition's rank-sum uses an earnings yield, which needs a share count; see
    `ranking_deviation` in the output for why that is not point-in-time reproducible.
    """
    d = q.copy()
    d["r_q"] = d.roe.rank(ascending=False)
    d["r_m"] = d.operating_margin.rank(ascending=False)
    d["mf"] = d.r_q if formula == "roe_only" else d.r_q + d.r_m
    d = d.sort_values(["mf", "r_q"])
    cnt, picked = {}, []
    for code, r in d.iterrows():
        sec = r["sector_33"]
        if cnt.get(sec, 0) >= cap:
            continue
        cnt[sec] = cnt.get(sec, 0) + 1
        picked.append(code)
        if len(picked) == n:
            break
    return picked


# ---------------------------------------------------------------- forward measurement
def forward(codes, d0, weights=None):
    """Equal-weighted buy-and-hold (share count fixed) from d0 to END."""
    tks = [c + ".T" for c in codes]
    sub = wide.loc[(wide.index >= d0) & (wide.index <= END)]
    tks = [t for t in tks if t in sub.columns and pd.notna(sub[t].iloc[0])
           and sub[t].notna().sum() >= len(sub) - 5]
    if not tks:
        return None, "0/%d" % len(codes)
    sub = sub[tks].ffill()
    w = np.repeat(1 / len(tks), len(tks)) if weights is None else np.array([weights[t] for t in tks])
    w = w / w.sum()
    nav = (sub / sub.iloc[0] * w).sum(axis=1)
    return nav.pct_change().dropna(), "%d/%d" % (len(tks), len(codes))


def bench(t, d0):
    sub = wide.loc[(wide.index >= d0) & (wide.index <= END), t].ffill()
    return sub.pct_change().dropna()


def stats(r, rb):
    rb = rb.reindex(r.index).fillna(0.0)
    ar = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    mdd = lambda x: float(((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min())
    vol = float(r.std() * np.sqrt(ANN))
    te = float((r - rb).std() * np.sqrt(ANN))
    a = ar(r)
    ex = (r - rb).dropna()
    n = len(ex)
    t_plain = float(ex.mean() / (ex.std(ddof=1) / np.sqrt(n))) if n > 2 and ex.std() > 0 else None
    # Newey-West on the daily excess series (Layer 1 only: testing is permitted here)
    x = ex.values
    e = x - x.mean()
    L = int(np.floor(4 * (n / 100) ** (2 / 9)))
    lrv = (e @ e) / n
    for j in range(1, L + 1):
        lrv += 2 * (1 - j / (L + 1)) * ((e[j:] @ e[:-j]) / n)
    t_nw = float(x.mean() / np.sqrt(lrv / n)) if lrv > 0 else None
    return {"days": n, "total_return": round(float((1 + r).prod() - 1), 4),
            "ann_return": round(a, 4), "bench_ann_return": round(ar(rb), 4),
            "excess_ann": round(a - ar(rb), 4), "volatility": round(vol, 4),
            "sharpe": round(a / vol, 3) if vol > 0 else None,
            "max_drawdown": round(mdd(r), 4), "bench_max_drawdown": round(mdd(rb), 4),
            "beta_vs_bench": round(float(r.cov(rb) / rb.var()), 3) if rb.var() > 0 else None,
            "information_ratio": round(float((r - rb).mean() * ANN / te), 3) if te > 0 else None,
            "mean_excess_ann": round(float(ex.mean() * ANN), 4),
            "t_plain": round(t_plain, 2) if t_plain is not None else None,
            "t_newey_west": round(t_nw, 2) if t_nw is not None else None, "nw_lag": L}


# ---------------------------------------------------------------- run
out = {
    "layer": "L1",
    "preregistration": ("As-of dates, gate translation, ranking formulas, series definitions and the "
                        "equal-weighted buy-and-hold measurement convention were fixed in "
                        "V11_PROGRESS.md before any return was computed (2026-07-25)."),
    "gate_translation": ("The contest edition requires three consecutive loss-free years. At the earlier "
                         "as-of dates only two fiscal years are on file, so the gate is translated to "
                         "'loss-free over all periods available at the as-of date'. Number of available "
                         "periods is reported per as-of date."),
    "ranking_deviation": ("The contest selection ranks firms by rank(ROE) + rank(earnings yield). An "
                          "earnings yield requires a share count. No point-in-time share counts exist in "
                          "the data, and the 2026 snapshot covers only 300 of 3,649 listed firms -- a set "
                          "that was itself chosen by the 2026 scoring pipeline, so screening on it would "
                          "inject selection look-ahead into the as-of pool. The L1 ranking therefore uses "
                          "the quality leg only, rank(ROE), with rank(ROE)+rank(operating margin) as a "
                          "robustness check. This is a deviation from the contest formula: L1 validates "
                          "the quality gate and the quality ranking, not the valuation leg. Disclosed in "
                          "the Limitations section."),
    "convention": ("Equal-weighted, share-count-fixed buy-and-hold from the last trading day before the "
                   "as-of date to 2026-06-01. Benchmark = TOPIX ETF 1306.T (adjusted for the 2026-03-30 "
                   "ten-for-one split) and Nikkei 225. Sector cap = 2 firms per 33-sector code."),
    "as_of_dates": AS_OF, "end": str(END.date()), "sector_cap": SECTOR_CAP,
    "specification_count": {"as_of_dates": len(AS_OF), "series": 3, "ranking_formulas": 2,
                            "total": len(AS_OF) * 3 * 2},
    "funnels": {}, "selections": {}, "results": {},
}

for as_of in AS_OF:
    q, funnel = pit_screen(as_of)
    out["funnels"][as_of] = funnel
    d0 = wide.loc[wide.index < pd.Timestamp(as_of)].index[-1]
    rb_topix, rb_n225 = bench("1306.T", d0), bench("^N225", d0)
    funnel["measurement_start"] = str(d0.date())
    funnel["median_periods_available"] = float(q.n_periods.median()) if len(q) else None

    sel, res = {}, {}
    for formula in ["roe_only", "roe_margin"]:
        for n, name in [(5, "shu5"), (20, "buf20")]:
            codes = rank_pick(q, formula, n)
            key = f"{name}_{formula}"
            sel[key] = codes
            r, cov = forward(codes, d0)
            if r is None:
                continue
            res[key] = stats(r, rb_topix) | {"coverage": cov, "n_selected": len(codes)}
            res[key]["nikkei_ann_return"] = round(
                float((1 + rb_n225.reindex(r.index).fillna(0)).prod() ** (ANN / len(r)) - 1), 4)
    # whole pool, equal weighted (no choice of n)
    pool = list(q.index)
    sel["pool_eq"] = pool
    r, cov = forward(pool, d0)
    if r is not None:
        res["pool_eq"] = stats(r, rb_topix) | {"coverage": cov, "n_selected": len(pool)}
        res["pool_eq"]["nikkei_ann_return"] = round(
            float((1 + rb_n225.reindex(r.index).fillna(0)).prod() ** (ANN / len(r)) - 1), 4)
    out["selections"][as_of] = {k: [(c, str(attrs.company_name.get(c, ""))) for c in v]
                                if k != "pool_eq" else v for k, v in sel.items()}
    out["results"][as_of] = res

json.dump(out, open(ED / "layer1_pit_v11.json", "w"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- console
for as_of in AS_OF:
    f = out["funnels"][as_of]
    print(f"\n=== as-of {as_of} (start {f['measurement_start']}) ===")
    print("  funnel: on file %d firms / 2+ periods %d / screenable %d / gate %d / with price %d"
          % (f["firms_on_file"], f["firms_with_2plus_periods"], f["firms_screenable"],
             f["passed_quality_gate"], f["with_price_series"]))
    for k, v in out["results"][as_of].items():
        print("  %-18s n=%3d cov=%-7s ann=%7.1f%% topix=%6.1f%% ex=%+7.1fp sh=%5.2f mdd=%6.1f%% "
              "b=%5.2f NW-t=%s"
              % (k, v["n_selected"], v["coverage"], v["ann_return"] * 100, v["bench_ann_return"] * 100,
                 v["excess_ann"] * 100, v["sharpe"] or 0, v["max_drawdown"] * 100,
                 v["beta_vs_bench"] or 0, v["t_newey_west"]))
print("\nwritten -> layer1_pit_v11.json")
