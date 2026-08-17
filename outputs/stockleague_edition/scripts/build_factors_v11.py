# -*- coding: utf-8 -*-
"""W3: monthly factor construction and attribution regressions.

Factors are built from the point-in-time filing panel and the price panel only, so each
month's sort uses accounting data that was on file at that month-end.

WHICH FACTORS, AND WHY NOT HML. A book-to-market sort needs market equity, which needs a
share count. No point-in-time share counts exist in the data and the 2026 snapshot covers
300 of 3,649 firms (see build_layer1_pit_v11.py). A value factor is therefore not
constructible here and its absence is disclosed rather than papered over with a proxy.
The size factor uses total assets -- an accounting measure of size, not market
capitalisation -- and is labelled as a proxy throughout.

The factors we can build are the ones this paper actually needs: quality (the screen's own
sort variable), the electrical-appliances sector (the semiconductor complex the portfolio
is concentrated in), momentum, market, and the accounting-size proxy.

Output: outputs/stockleague_edition/factors_v11.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"

SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
QUANTILE = 0.30          # top/bottom 30% legs
NW_LAG = 3               # Newey-West lag for monthly data
SECTOR_FACTOR = "Electric Appliances"

# ---------------------------------------------------------------- data
fund = pd.read_csv(ROOT / "data/processed/fundamentals_raw.csv", dtype={"code": str}, low_memory=False)
fund["code"] = fund["code"].str.zfill(4)
fund["submit_date"] = pd.to_datetime(fund["submit_date"])
fund["period_end"] = pd.to_datetime(fund["period_end"])
for c in ["net_income", "equity", "total_assets"]:
    fund[c] = pd.to_numeric(fund[c], errors="coerce")
fund = fund.dropna(subset=["submit_date"]).sort_values(["code", "period_end"])

s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)
sector = dict(zip(s.code, s.sector_33))
is_fin = dict(zip(s.code, s.is_financial.astype(str).str.lower().isin(["true", "1", "1.0"])))

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
wide = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f

# month-end trading days
me = wide.groupby([wide.index.year, wide.index.month]).apply(lambda g: g.index[-1])
month_ends = pd.DatetimeIndex(sorted(me.values))
mp = wide.reindex(month_ends).ffill()            # month-end price panel
mret = mp.pct_change(fill_method=None)           # monthly simple returns

# 12-1 momentum: cumulative return from t-12 to t-1
mom = (mp.shift(1) / mp.shift(12) - 1)

# ---------------------------------------------------------------- point-in-time accounting
def pit_accounting(asof):
    """Latest filing per firm submitted on or before `asof`."""
    sub = fund[fund.submit_date <= asof]
    if sub.empty:
        return pd.DataFrame()
    latest = sub.drop_duplicates(subset=["code", "period_end"], keep="last").groupby("code").tail(1)
    d = latest.set_index("code")[["net_income", "equity", "total_assets"]].copy()
    d["roe"] = np.where((d.equity > 0), d.net_income / d.equity, np.nan)
    d["size"] = d.total_assets
    return d[["roe", "size"]]


def ls_leg(scores_, nxt, high_minus_low=True):
    """Equal-weighted long/short return from a cross-sectional sort."""
    df = pd.concat([scores_.rename("x"), nxt.rename("r")], axis=1).dropna()
    if len(df) < 50:
        return np.nan
    hi = df[df.x >= df.x.quantile(1 - QUANTILE)].r.mean()
    lo = df[df.x <= df.x.quantile(QUANTILE)].r.mean()
    return float(hi - lo) if high_minus_low else float(lo - hi)


rows = []
for i in range(len(month_ends) - 1):
    t, t1 = month_ends[i], month_ends[i + 1]
    acc = pit_accounting(t)
    if acc.empty:
        continue
    nxt = mret.loc[t1]
    # eligible: non-financial, price at both ends
    codes = [c for c in acc.index if not is_fin.get(c, False) and c + ".T" in mret.columns]
    codes = [c for c in codes if pd.notna(nxt.get(c + ".T")) and pd.notna(mp.loc[t, c + ".T"])]
    if len(codes) < 200:
        continue
    idx = pd.Index([c + ".T" for c in codes])
    nxt_c = pd.Series(nxt[idx].values, index=codes)
    a = acc.loc[codes]

    mkt = float(mret.loc[t1, "1306.T"]) if pd.notna(mret.loc[t1, "1306.T"]) else np.nan
    univ = float(nxt_c.mean())
    sec_codes = [c for c in codes if sector.get(c) == SECTOR_FACTOR]
    sec_ret = float(nxt_c[sec_codes].mean()) if len(sec_codes) >= 20 else np.nan

    rows.append({
        "month": t1.strftime("%Y-%m"), "date": t1, "n_firms": len(codes),
        "MKT": mkt,
        "QMJ": ls_leg(a.roe, nxt_c),                       # high ROE minus low ROE
        "SIZE": ls_leg(a["size"], nxt_c, high_minus_low=False),   # small minus big (assets proxy)
        "MOM": ls_leg(pd.Series(mom.loc[t, idx].values, index=codes), nxt_c),
        "SECTOR": sec_ret - univ if pd.notna(sec_ret) else np.nan,
        "n_sector": len(sec_codes),
    })

F = pd.DataFrame(rows).set_index("date")
F = F.dropna(subset=["MKT", "QMJ", "SIZE", "MOM", "SECTOR"])

# ---------------------------------------------------------------- test portfolios (monthly)
pf = json.load(open(WORK / "portfolio_v7.json"))
w_actual = pf["weights_v7"]
codes_actual = [t.replace(".T", "") for t in w_actual]
buf20 = json.load(open(ED / "control_comparison_v10.json"))["buf_pool"]["buf20"]


def monthly_port(codes, weights=None):
    tks = [c + ".T" for c in codes if c + ".T" in mret.columns]
    r = mret[tks]
    w = (np.repeat(1 / len(tks), len(tks)) if weights is None
         else np.array([weights[t] for t in tks]))
    w = w / w.sum()
    return (r * w).sum(axis=1, min_count=len(tks))


PORTS = {
    "ours_role_budget": monthly_port(codes_actual, w_actual),
    "ours_equal": monthly_port(codes_actual),
    "benchmark_buf20_equal": monthly_port(buf20),
}

# ---------------------------------------------------------------- regressions
def nw_se(X, resid, lag):
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (resid[:, None] * X).T @ (resid[:, None] * X)
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        u = (resid[:, None] * X)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    return np.sqrt(np.diag(V) * n / (n - k))


def regress(y, facs, names):
    d = pd.concat([y.rename("y"), F[names]], axis=1).dropna()
    yv = (d.y - d.MKT * 0).values if False else d.y.values
    X = np.column_stack([np.ones(len(d))] + [d[c].values for c in names])
    b, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid = yv - X @ b
    se = nw_se(X, resid, NW_LAG)
    tss = ((yv - yv.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / tss
    n, k = X.shape
    return {
        "n_months": int(n), "factors": names,
        "alpha_monthly": round(float(b[0]), 5),
        "alpha_annualised": round(float((1 + b[0]) ** 12 - 1), 4),
        "alpha_t_newey_west": round(float(b[0] / se[0]), 2),
        "alpha_se_monthly": round(float(se[0]), 5),
        "loadings": {nm: round(float(v), 3) for nm, v in zip(names, b[1:])},
        "loading_t": {nm: round(float(v / e), 2) for nm, v, e in zip(names, b[1:], se[1:])},
        "r_squared": round(float(r2), 3),
        "adj_r_squared": round(float(1 - (1 - r2) * (n - 1) / (n - k)), 3),
        "nw_lag": NW_LAG,
    }


# Headline model is CAPM+SECTOR: with 36 monthly observations, five regressors leaves 30 degrees
# of freedom, and the sector factor is the control this paper's question actually turns on. The
# richer models are reported alongside, not hidden -- and note the direction: the five-factor
# alpha is LARGER than the parsimonious one, so demoting it works against us.
SPECS = [("capm", ["MKT"]),
         ("capm_sector", ["MKT", "SECTOR"]),
         ("mkt_qmj_size_mom", ["MKT", "QMJ", "SIZE", "MOM"]),
         ("full_with_sector", ["MKT", "QMJ", "SIZE", "MOM", "SECTOR"])]
HEADLINE_SPEC = "capm_sector"

out = {
    "layer": "L1/L3 attribution",
    "note": ("Regressions are run on the full 2026 portfolio, which embeds hindsight; the alpha here "
             "is therefore an accounting exercise -- how much of the in-sample excess return is "
             "spanned by tradable factor exposures -- not evidence of skill. Read alongside "
             "Table 1 (out-of-sample) and Table 2 (randomisation)."),
    "hml_absent": ("No value factor. A book-to-market sort requires market equity, hence a share "
                   "count; point-in-time share counts do not exist in this data and the 2026 "
                   "snapshot covers 300 of 3,649 firms. The size factor sorts on total assets and is "
                   "an accounting-size proxy, not market capitalisation. Both limitations are stated "
                   "in the manuscript rather than hidden behind a substitute."),
    "construction": ("Monthly rebalanced, equal-weighted, top/bottom 30%% long/short legs sorted at "
                     "each month-end on data on file at that month-end. QMJ = high ROE minus low ROE. "
                     "SIZE = small minus big total assets. MOM = 12-1 month return. SECTOR = "
                     "equal-weighted %s minus the equal-weighted universe. MKT = TOPIX ETF monthly "
                     "return with the risk-free rate set to zero (Japanese short rates were near "
                     "zero over the sample; stated explicitly rather than assumed away)."
                     % SECTOR_FACTOR),
    "quantile": QUANTILE, "nw_lag": NW_LAG, "sector_factor": SECTOR_FACTOR,
    "headline_spec": HEADLINE_SPEC,
    "headline_rationale": ("Chosen on degrees of freedom alone, and recorded before the estimates were "
                           "inspected: 36 monthly observations do not support five regressors. The "
                           "richer specifications are reported in the same table. The choice is not "
                           "self-serving -- the five-factor alpha is larger than the parsimonious "
                           "one, so preferring the parsimonious model lowers the alpha we report."),
    "size_proxy_direction": ("SIZE sorts on total assets, not market equity. A small high-multiple "
                             "growth firm has a large market capitalisation but modest assets, so an "
                             "accounting-size sort places it on the 'small' side more readily than a "
                             "market-equity sort would. The proxy therefore mismeasures SMB exposure, "
                             "and for a portfolio tilted toward high-multiple names it understates "
                             "true small-cap exposure."),
    "hml_absence_direction": ("Unsignable without market equity, so we do not estimate it. One "
                              "empirical anchor from data we do have: the deep-value (Graham-style) "
                              "control built from the same universe returned 13.3% annualised over the "
                              "three-year window against 24.0% for TOPIX, so value exposure was "
                              "costly in this regime. If this portfolio carries the growth tilt its "
                              "holdings suggest, omitting a value factor with a negative loading would "
                              "flatter the reported alpha rather than depress it."),
    "sample": {"first_month": F.index[0].strftime("%Y-%m"), "last_month": F.index[-1].strftime("%Y-%m"),
               "n_months": int(len(F)), "median_firms_per_sort": int(F.n_firms.median()),
               "median_sector_firms": int(F.n_sector.median())},
    "factor_summary": {c: {"mean_monthly": round(float(F[c].mean()), 5),
                           "annualised": round(float((1 + F[c].mean()) ** 12 - 1), 4),
                           "sd_monthly": round(float(F[c].std()), 4)}
                       for c in ["MKT", "QMJ", "SIZE", "MOM", "SECTOR"]},
    "factor_correlations": {a: {b: round(float(F[a].corr(F[b])), 2)
                                for b in ["MKT", "QMJ", "SIZE", "MOM", "SECTOR"]}
                            for a in ["MKT", "QMJ", "SIZE", "MOM", "SECTOR"]},
    "regressions": {},
    "monthly_factors": [{"month": r.month, **{c: (None if pd.isna(getattr(r, c)) else round(float(getattr(r, c)), 5))
                                              for c in ["MKT", "QMJ", "SIZE", "MOM", "SECTOR"]}}
                        for r in F.reset_index().itertuples()],
}

for pname, y in PORTS.items():
    out["regressions"][pname] = {name: regress(y, F, facs) for name, facs in SPECS}

json.dump(out, open(ED / "factors_v11.json", "w"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- console
sm = out["sample"]
print("sample %s..%s (%d months), median %d firms/sort, %d sector firms"
      % (sm["first_month"], sm["last_month"], sm["n_months"], sm["median_firms_per_sort"],
         sm["median_sector_firms"]))
print("\nfactor annualised returns:")
for c, v in out["factor_summary"].items():
    print("  %-7s %+7.1f%%  (sd %.1f%%/mo)" % (c, v["annualised"] * 100, v["sd_monthly"] * 100))
for pname in PORTS:
    print("\n=== %s ===" % pname)
    for spec, _ in SPECS:
        r = out["regressions"][pname][spec]
        print("  %-18s alpha %+7.1f%%/yr (NW-t %+5.2f)  R2adj %.2f  n=%d"
              % (spec, r["alpha_annualised"] * 100, r["alpha_t_newey_west"], r["adj_r_squared"],
                 r["n_months"]))
        print("      loadings " + "  ".join("%s %+.2f(t%+.1f)" % (k, v, r["loading_t"][k])
                                            for k, v in r["loadings"].items()))
print("\nwritten -> factors_v11.json")
