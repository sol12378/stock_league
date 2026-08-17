# -*- coding: utf-8 -*-
"""W4: implementation realism and statistical housekeeping.

Four things, all of which cut against the paper's own numbers:

1. MONTHLY REBALANCING WITH COSTS. The contest measurement convention rebalanced to fixed
   weights daily, which is not implementable. The headline convention here is monthly
   rebalancing with a one-way cost of 25 bp plus an odd-lot spread assumption, applied to
   traded notional; the daily convention moves to the appendix. Cost sensitivity is reported
   over a grid so a reader can substitute their own assumption.

2. DEFLATED SHARPE RATIO (Bailey & Lopez de Prado 2014). The observed Sharpe ratio is
   discounted for the number of specifications we traversed and for the non-normality of
   the return series. The trial variance is estimated from the Layer 2 placebo distribution
   of Sharpe ratios -- an empirical distribution of what a random portfolio from this pool
   achieves -- rather than assumed.

3. MINIMUM DETECTABLE EFFECT. What excess return the Layer 1 design could have detected at
   conventional power, computed per as-of date, so that the null result in Table 1 can be
   read against what the test was capable of finding.

4. SPECIFICATION COUNT. An explicit enumeration of every specification traversed across
   this paper and the contest edition that preceded it.

Output: outputs/stockleague_edition/costs_v11.json
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
WORK = ROOT / "work/pure_buffett_benchmark"

ANN = 252
W3Y = 756
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
ONE_WAY_BP = 25.0            # headline one-way transaction cost
ODD_LOT_BP = 15.0            # additional spread assumed for sub-unit (odd-lot) share trading
COST_GRID_BP = [0.0, 10.0, 25.0, 50.0, 100.0]
EULER = 0.5772156649015329

# ---------------------------------------------------------------- inputs
L1 = json.load(open(ED / "layer1_pit_v11.json"))
L2 = json.load(open(ED / "layer2_placebo_v11.json"))
CC = json.load(open(ED / "control_comparison_v10.json"))
pf = json.load(open(WORK / "portfolio_v7.json"))
w_actual = pf["weights_v7"]
codes_actual = [t.replace(".T", "") for t in w_actual]
buf20 = CC["buf_pool"]["buf20"]

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
need = set(w_actual) | {c + ".T" for c in buf20} | {"1306.T"}
wide = px[px.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns:
        wide.loc[wide.index >= d0, t] *= f

win = wide.tail(W3Y).ffill()
rets = win.pct_change(fill_method=None).iloc[1:]
month_end = rets.groupby([rets.index.year, rets.index.month]).apply(lambda g: g.index[-1])
REBAL_DAYS = set(pd.DatetimeIndex(sorted(month_end.values)))


# ---------------------------------------------------------------- portfolio simulators
def simulate(weights, cost_bp, rebalance="monthly", odd_lot_bp=0.0):
    """Return the net daily return series. Costs are charged on traded notional.

    Total cost rate per unit of traded notional = (cost_bp + odd_lot_bp) / 10000.
    Turnover at a rebalance = sum_i |w_target_i - w_drifted_i| (buys plus sells).
    An entry cost is charged on the full notional at inception.
    """
    tks = [t for t in weights if t in rets.columns]
    w_t = np.array([weights[t] for t in tks], dtype=float)
    w_t = w_t / w_t.sum()
    R = rets[tks].fillna(0.0).values
    rate = (cost_bp + odd_lot_bp) / 10_000.0

    w = w_t.copy()
    out = np.empty(len(R))
    entry = rate * 1.0                      # buy the whole portfolio on day one
    for i in range(len(R)):
        gross = float(w @ R[i])
        # drift the weights with the day's returns
        w = w * (1.0 + R[i])
        w = w / w.sum()
        cost = 0.0
        if rebalance == "daily" or (rebalance == "monthly" and rets.index[i] in REBAL_DAYS):
            cost = rate * float(np.abs(w_t - w).sum())
            w = w_t.copy()
        out[i] = gross - cost - (entry if i == 0 else 0.0)
    return pd.Series(out, index=rets.index)


def block(r, rb):
    rb = rb.reindex(r.index).fillna(0.0)
    ar = lambda x: float((1 + x).prod() ** (ANN / len(x)) - 1)
    nav = (1 + r).cumprod()
    vol = float(r.std() * np.sqrt(ANN))
    a = ar(r)
    return {"ann_return": round(a, 4), "volatility": round(vol, 4),
            "sharpe": round(a / vol, 3) if vol > 0 else None,
            "max_drawdown": round(float((nav / nav.cummax() - 1).min()), 4),
            "excess_vs_topix": round(a - ar(rb), 4),
            "beta_vs_topix": round(float(r.cov(rb) / rb.var()), 3)}


def turnover_of(weights, rebalance="monthly"):
    tks = [t for t in weights if t in rets.columns]
    w_t = np.array([weights[t] for t in tks], dtype=float)
    w_t /= w_t.sum()
    R = rets[tks].fillna(0.0).values
    w, tot = w_t.copy(), 0.0
    for i in range(len(R)):
        w = w * (1.0 + R[i])
        w = w / w.sum()
        if rebalance == "daily" or (rebalance == "monthly" and rets.index[i] in REBAL_DAYS):
            tot += float(np.abs(w_t - w).sum())
            w = w_t.copy()
    return tot / (len(R) / ANN)          # annualised traded notional (buys + sells)


rb = rets["1306.T"]
SERIES = {
    "ours_role_budget": w_actual,
    "ours_equal": {c + ".T": 1 / len(codes_actual) for c in codes_actual},
    "benchmark_buf20_equal": {c + ".T": 1 / len(buf20) for c in buf20},
}

results = {}
for name, w in SERIES.items():
    results[name] = {
        "daily_rebalance_no_cost": block(simulate(w, 0.0, "daily"), rb),
        "monthly_rebalance_no_cost": block(simulate(w, 0.0, "monthly"), rb),
        "monthly_headline": block(simulate(w, ONE_WAY_BP, "monthly", ODD_LOT_BP), rb),
        "daily_rebalance_headline_cost": block(simulate(w, ONE_WAY_BP, "daily", ODD_LOT_BP), rb),
        "annual_turnover_monthly": round(turnover_of(w, "monthly"), 3),
        "annual_turnover_daily": round(turnover_of(w, "daily"), 3),
        "cost_grid_monthly": {("%dbp" % int(c)): block(simulate(w, c, "monthly", ODD_LOT_BP), rb)
                              for c in COST_GRID_BP},
    }

# ---------------------------------------------------------------- specification count
SPEC_TABLE = [
    ("Layer 1 as-of validation", "3 as-of dates x (3 series x 2 ranking formulas + 3 discarded "
                                 "earnings-yield series)", 27),
    ("Layer 2 randomisation", "2 drawing schemes x 2 portfolio weightings", 4),
    ("Factor attribution", "3 test portfolios x 3 factor models", 9),
    ("Benchmark construction (contribution B)", "3 holding counts x 3 weighting rules", 9),
    ("Quality-gate threshold robustness (contest edition)", "8 single-threshold variants", 8),
    ("Market-phase splits (contest edition)", "4 phases", 4),
    ("Allocation rules (contest edition)", "equal, role budget, minimum variance", 3),
    ("Measurement windows (contest edition)", "3-year and 1-year", 2),
    ("Benchmark comparison pairs (contest edition)", "4 pairwise comparisons", 4),
    ("Volatility-matched leverage variant (contest edition)", "1", 1),
    ("Graham-style control (contest edition)", "1", 1),
    ("Cost conventions (this paper)", "5-point cost grid x 2 rebalancing frequencies", 10),
]
N_SPECS = sum(n for _, _, n in SPEC_TABLE)

# ---------------------------------------------------------------- deflated Sharpe ratio
def deflated_sharpe(r, n_trials, sr_trial_sd_annual):
    """Bailey & Lopez de Prado (2014). r = daily return series of the selected strategy."""
    x = r.dropna().values
    T = len(x)
    sr = float(x.mean() / x.std(ddof=1))                 # per-observation Sharpe
    g3 = float(stats.skew(x))
    g4 = float(stats.kurtosis(x, fisher=False))          # non-excess kurtosis
    v = (sr_trial_sd_annual / math.sqrt(ANN)) ** 2        # variance of per-obs trial Sharpes
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    sr0 = math.sqrt(v) * ((1 - EULER) * z1 + EULER * z2)
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2))
    dsr = float(stats.norm.cdf((sr - sr0) * math.sqrt(T - 1) / denom))
    return {"observed_sharpe_annualised": round(sr * math.sqrt(ANN), 3),
            "sharpe_definition": ("Arithmetic: mean/sd of daily net returns, annualised by sqrt(252). "
                                  "This is the quantity the Bailey-Lopez de Prado formula is defined "
                                  "on and is NOT the same as the geometric Sharpe reported in the "
                                  "performance tables (annualised compound return / annualised vol), "
                                  "which is higher for these series."),
            "threshold_sharpe_annualised": round(sr0 * math.sqrt(ANN), 3),
            "deflated_sharpe_probability": round(dsr, 4),
            "n_trials": n_trials, "n_observations": T,
            "skewness": round(g3, 3), "kurtosis": round(g4, 3),
            "trial_sharpe_sd_annualised": round(sr_trial_sd_annual, 3),
            "survives_at_95": bool(dsr >= 0.95)}


# trial variance from the placebo Sharpe distribution (empirical, not assumed)
sr_sd = L2["distribution"]["sector_matched"]["sharpe"]["sd"]
sr_sd_unstrat = L2["distribution"]["unstratified"]["sharpe"]["sd"]

dsr = {}
for name, w in SERIES.items():
    net = simulate(w, ONE_WAY_BP, "monthly", ODD_LOT_BP)
    dsr[name] = {
        "sector_matched_trial_sd": deflated_sharpe(net, N_SPECS, sr_sd),
        "unstratified_trial_sd": deflated_sharpe(net, N_SPECS, sr_sd_unstrat),
    }

# ---------------------------------------------------------------- minimum detectable effect
Z_A, Z_B = stats.norm.ppf(0.975), stats.norm.ppf(0.80)
mde = {}
for as_of in L1["as_of_dates"]:
    r = L1["results"][as_of]["pool_eq"]
    n = r["days"]
    # daily excess sd implied by the reported information ratio and tracking error
    te_ann = abs(r["mean_excess_ann"] / r["information_ratio"]) if r["information_ratio"] else None
    if te_ann is None:
        continue
    sd_daily = te_ann / math.sqrt(ANN)
    mde_daily = (Z_A + Z_B) * sd_daily / math.sqrt(n)
    mde[as_of] = {"n_days": n, "tracking_error_annualised": round(te_ann, 4),
                  "mde_annualised": round(mde_daily * ANN, 4),
                  "observed_excess_annualised": r["excess_ann"],
                  "detectable": bool(abs(r["excess_ann"]) >= mde_daily * ANN)}

# ---------------------------------------------------------------- assemble
out = {
    "conventions": {
        "headline": ("Monthly rebalancing to fixed target weights, one-way cost of %.0f bp plus an "
                     "assumed odd-lot spread of %.0f bp, charged on traded notional (buys plus sells), "
                     "with an entry cost on the full notional. The contest edition's daily "
                     "fixed-weight rebalancing is reported alongside as the appendix convention."
                     % (ONE_WAY_BP, ODD_LOT_BP)),
        "one_way_bp": ONE_WAY_BP, "odd_lot_bp": ODD_LOT_BP, "cost_grid_bp": COST_GRID_BP,
        "window": "756 trading days ending 2026-06-01",
    },
    "results": results,
    "specification_count": {
        "total": N_SPECS,
        "note": ("A lower bound. It counts specifications we can enumerate from the artefacts; "
                 "informal variants explored and discarded before the artefacts were written are not "
                 "recoverable and are therefore not counted."),
        "table": [{"category": c, "detail": d, "n": n} for c, d, n in SPEC_TABLE],
    },
    "deflated_sharpe": dsr,
    "deflated_sharpe_note": ("Trial variance is the standard deviation of Sharpe ratios across the "
                             "Layer 2 placebo draws, which measures how much Sharpe dispersion this "
                             "pool generates by chance at this holding count. Reported under both "
                             "the sector-matched and unstratified placebo distributions."),
    "mde": mde,
    "mde_note": ("Minimum detectable annualised excess return, two-sided at the 5%% level with 80%% "
                 "power, using the realised tracking error of the equal-weighted gate-passing pool "
                 "at each as-of date. Stated so that the Layer 1 null can be read against the "
                 "sensitivity of the test."),
}
json.dump(out, open(ED / "costs_v11.json", "w"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- console
print("specification count: %d\n" % N_SPECS)
for name in SERIES:
    r = results[name]
    print("=== %s (annual turnover: monthly %.2f / daily %.2f) ===" %
          (name, r["annual_turnover_monthly"], r["annual_turnover_daily"]))
    for k in ["daily_rebalance_no_cost", "monthly_rebalance_no_cost", "monthly_headline",
              "daily_rebalance_headline_cost"]:
        b = r[k]
        print("  %-30s ann=%6.1f%% sh=%5.2f mdd=%6.1f%%" %
              (k, b["ann_return"] * 100, b["sharpe"], b["max_drawdown"] * 100))
    print("  cost grid (monthly): " + "  ".join(
        "%s->%.1f%%" % (c, r["cost_grid_monthly"][c]["ann_return"] * 100) for c in r["cost_grid_monthly"]))
    d = dsr[name]["sector_matched_trial_sd"]
    print("  DSR: observed SR %.2f vs threshold %.2f -> p=%.3f (survives 95%%: %s)"
          % (d["observed_sharpe_annualised"], d["threshold_sharpe_annualised"],
             d["deflated_sharpe_probability"], d["survives_at_95"]))
print("\n=== minimum detectable effect (Layer 1, equal-weighted pool) ===")
for a, m in mde.items():
    print("  %s: n=%d days, TE=%.1f%%, MDE=%+.1fp, observed=%+.1fp -> %s"
          % (a, m["n_days"], m["tracking_error_annualised"] * 100, m["mde_annualised"] * 100,
             m["observed_excess_annualised"] * 100,
             "detectable" if m["detectable"] else "BELOW detection threshold"))
print("\nwritten -> costs_v11.json")
