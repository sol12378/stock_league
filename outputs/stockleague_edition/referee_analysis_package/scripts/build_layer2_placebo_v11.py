# -*- coding: utf-8 -*-
"""W2 / Layer 2: randomisation inference on the full 20-firm portfolio.

Pre-registered in V11_PROGRESS.md before execution (iteration 2).

Layer 2 exists because the final portfolio includes fifteen firms chosen by reading
disclosures in 2026. That selection is not reproducible point-in-time, so its measured
performance carries hindsight by construction and conventional tests would be
meaningless. Instead we ask a question that hindsight does not spoil: among portfolios
of the same size drawn from the same 2026 guard-passing pool -- and, in the stratified
variant, from the same sector composition -- where does the actual portfolio sit?

REPORTED: percentiles only. No t-statistics, no use of the word "significant" (gate G3).

Output: outputs/stockleague_edition/layer2_placebo_v11.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"

SEED = 20260725
N_DRAWS = 10_000
ANN = 252
W3Y = 756
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

# ---------------------------------------------------------------- the actual portfolio
pf = json.load(open(WORK / "portfolio_v7.json"))
w_actual = pf["weights_v7"]
codes_actual = [t.replace(".T", "") for t in w_actual]

# ---------------------------------------------------------------- the 2026 guard pool
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)


def truthy(col):
    return s[col].astype(str).str.lower().isin(["true", "1", "1.0"])


for c in ["net_income", "roe", "price_history_days"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")

pool_mask = (truthy("investment_eligible") & truthy("price_available") & ~truthy("is_financial")
             & truthy("liquid_20m_60d") & (s.net_income > 0) & (s.roe >= 0.05)
             & (s.price_history_days >= W3Y))
pool = s[pool_mask][["code", "sector_33", "company_name"]].dropna(subset=["sector_33"]).copy()
pool_codes = pool.code.tolist()

# ---------------------------------------------------------------- prices
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
need = set(c + ".T" for c in pool_codes) | set(w_actual) | {"1306.T"}
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f

win = wide.tail(W3Y).ffill()
rets = win.pct_change(fill_method=None).iloc[1:]          # daily simple returns, 755 rows
usable = [t for t in win.columns if win[t].notna().sum() >= W3Y - 2 and pd.notna(win[t].iloc[0])]
pool = pool[pool.code.isin([t.replace(".T", "") for t in usable])]
pool_codes = pool.code.tolist()
sector_of = dict(zip(pool.code, pool.sector_33))

rb = rets["1306.T"].dropna()
R = rets[[t for t in usable if t != "1306.T"]].fillna(0.0)
cols = {t: i for i, t in enumerate(R.columns)}
Rv = R.values
rb_v = rb.reindex(R.index).fillna(0.0).values
bench_ann = float((1 + rb_v).prod() ** (ANN / len(rb_v)) - 1)
bench_var = rb_v.var()


def metrics(r):
    """r: daily return vector of a fixed-weight, daily-rebalanced portfolio."""
    a = float((1 + r).prod() ** (ANN / len(r)) - 1)
    vol = float(r.std() * np.sqrt(ANN))
    nav = (1 + r).cumprod()
    mdd = float((nav / np.maximum.accumulate(nav) - 1).min())
    beta = float(np.cov(r, rb_v)[0, 1] / bench_var)
    return a, (a / vol if vol > 0 else np.nan), mdd, beta


def port_returns(codes, weights=None):
    idx = [cols[c + ".T"] for c in codes if c + ".T" in cols]
    if not idx:
        return None
    w = (np.repeat(1 / len(idx), len(idx)) if weights is None
         else np.array([weights[c + ".T"] for c in codes if c + ".T" in cols]))
    w = w / w.sum()
    return Rv[:, idx] @ w


# ---------------------------------------------------------------- actual portfolio
actual = {}
for lab, w in [("ours_equal", None), ("ours_role_budget", w_actual)]:
    a, sh, mdd, b = metrics(port_returns(codes_actual, w))
    actual[lab] = {"ann_return": round(a, 4), "sharpe": round(sh, 3),
                   "max_drawdown": round(mdd, 4), "beta_vs_topix": round(b, 3)}

# ---------------------------------------------------------------- placebo draws
rng = np.random.default_rng(SEED)
n_hold = len(codes_actual)

# sector composition of the actual portfolio, mapped onto the pool's sector labels
act_sec = pd.Series([sector_of.get(c) for c in codes_actual])
sec_target = act_sec.value_counts().to_dict()
by_sector = {sec: pool[pool.sector_33 == sec].code.tolist() for sec in sec_target}
shortfall = {sec: max(0, k - len(by_sector.get(sec, []))) for sec, k in sec_target.items()}

draws = {"unstratified": [], "sector_matched": []}
all_idx = np.array([cols[c + ".T"] for c in pool_codes if c + ".T" in cols])
sec_idx = {sec: np.array([cols[c + ".T"] for c in v if c + ".T" in cols]) for sec, v in by_sector.items()}

for _ in range(N_DRAWS):
    pick = rng.choice(all_idx, size=n_hold, replace=False)
    w = np.repeat(1 / n_hold, n_hold)
    draws["unstratified"].append(metrics(Rv[:, pick] @ w))

    parts = []
    for sec, k in sec_target.items():
        cand = sec_idx.get(sec, np.array([], dtype=int))
        if len(cand) == 0:
            continue
        take = min(k, len(cand))
        parts.append(rng.choice(cand, size=take, replace=False))
    pick = np.concatenate(parts)
    w = np.repeat(1 / len(pick), len(pick))
    draws["sector_matched"].append(metrics(Rv[:, pick] @ w))

# ---------------------------------------------------------------- percentiles
KEYS = ["ann_return", "sharpe", "max_drawdown", "beta_vs_topix"]
out = {
    "layer": "L2",
    "inference": ("Percentiles against a randomisation distribution. No test statistics are reported "
                  "in this layer: the portfolio embeds 2026 hindsight by construction, so a p-value "
                  "would describe the placebo design rather than the portfolio."),
    "preregistration": ("Seed, draw count, pool definition, both drawing schemes and the "
                        "equal-weight comparison convention were recorded in V11_PROGRESS.md before "
                        "this script was run."),
    "seed": SEED, "n_draws": N_DRAWS, "n_holdings": n_hold,
    "pool_size": len(pool_codes),
    "pool_definition": ("scores.csv: investment_eligible AND price_available AND not financial AND "
                        "liquid_20m_60d AND net_income>0 AND ROE>=5% AND price history >= 756 trading "
                        "days. Non-financial matches the universe the team actually selected from."),
    "convention": ("3-year window of 756 trading days ending 2026-06-01, fixed-weight daily "
                   "rebalancing, equal weights on both sides so that weighting is not a confound. "
                   "TOPIX ETF 1306.T adjusted for the 2026-03-30 ten-for-one split."),
    "benchmark_ann_return": round(bench_ann, 4),
    "actual": actual,
    "sector_target": sec_target,
    "sector_shortfall": {k: v for k, v in shortfall.items() if v},
    "percentiles": {}, "distribution": {},
}

for scheme, vals in draws.items():
    arr = np.array(vals)                                   # (N, 4)
    out["percentiles"][scheme] = {}
    out["distribution"][scheme] = {}
    for i, k in enumerate(KEYS):
        col = arr[:, i]
        col = col[np.isfinite(col)]
        out["distribution"][scheme][k] = {
            "p1": round(float(np.percentile(col, 1)), 4), "p5": round(float(np.percentile(col, 5)), 4),
            "p25": round(float(np.percentile(col, 25)), 4), "p50": round(float(np.percentile(col, 50)), 4),
            "p75": round(float(np.percentile(col, 75)), 4), "p95": round(float(np.percentile(col, 95)), 4),
            "p99": round(float(np.percentile(col, 99)), 4),
            "mean": round(float(col.mean()), 4), "sd": round(float(col.std(ddof=1)), 4)}
        for lab in actual:
            v = actual[lab][k]
            out["percentiles"][scheme].setdefault(lab, {})[k] = round(float((col < v).mean() * 100), 1)

np.save(ED / "layer2_draws_v11.npy", np.array([draws["unstratified"], draws["sector_matched"]]))
json.dump(out, open(ED / "layer2_placebo_v11.json", "w"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- console
print("pool = %d firms; %d draws of %d holdings; seed %d" % (len(pool_codes), N_DRAWS, n_hold, SEED))
print("TOPIX 3y annualised: %.1f%%" % (bench_ann * 100))
if out["sector_shortfall"]:
    print("sector shortfall:", out["sector_shortfall"])
for scheme in draws:
    print("\n=== %s ===" % scheme)
    for k in KEYS:
        d = out["distribution"][scheme][k]
        f = (lambda x: "%.1f%%" % (x * 100)) if k in ("ann_return", "max_drawdown") else (lambda x: "%.2f" % x)
        print("  %-14s p5=%-8s p25=%-8s p50=%-8s p75=%-8s p95=%-8s" %
              (k, f(d["p5"]), f(d["p25"]), f(d["p50"]), f(d["p75"]), f(d["p95"])))
        for lab in actual:
            print("      %-18s actual=%-8s -> percentile %.1f"
                  % (lab, f(actual[lab][k]), out["percentiles"][scheme][lab][k]))
print("\nwritten -> layer2_placebo_v11.json")
