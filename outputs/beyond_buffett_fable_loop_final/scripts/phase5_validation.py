#!/usr/bin/env python
"""Phase5 validation: risk characterization of the final portfolio (plan C)
vs TOPIX proxy (1306.T) and Nikkei (^N225).

IMPORTANT FRAMING: the portfolio is built from data available as of 2026-06,
so any historical simulation is in-sample by construction. All numbers are
RISK CHARACTERISTICS (vol, drawdown, beta, concentration), not performance
claims. This is stated in every output.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
P5 = OUT / "phase5_verification_and_ablation"
FIG = OUT / "figures"
TAB = OUT / "tables"
P5.mkdir(exist_ok=True)

alloc = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
f20 = pd.read_csv(OUT / "phase3_moat_construction/final20_selected.csv")
f20["code_n"] = f20["code"].astype(str).str.replace(".T", "", regex=False).str.replace("﻿", "", regex=False).str.split(".").str[0].str.zfill(4)
alloc["code_n"] = alloc["code_n"].astype(str).str.zfill(4)
alloc = alloc.merge(f20[["code_n", "bm_raw"]], on="code_n", how="left")
alloc["ticker"] = alloc["code_n"] + ".T"
w = alloc.set_index("ticker")["target_weight_final"]

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                     columns=["date", "ticker", "adj_close"])
need = set(w.index) | {"1306.T", "^N225"}
px = px[px["ticker"].isin(need)]
wide = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()

# Data repair: 1306.T has an UNADJUSTED 1:10 split on 2026-03-30 in the source
# parquet (adj_close drops -90.2% in one day). Multiply post-split prices by 10
# so returns are continuous. Verified: no other ticker in the portfolio set has
# a split-like cliff (only 2112.T +32.9% on 2024-01-25, kept as a genuine
# small-cap move).
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
for t, (d0, factor) in SPLIT_FIXES.items():
    wide.loc[wide.index >= d0, t] = wide.loc[wide.index >= d0, t] * factor
    print(f"[data repair] {t}: x{factor} applied on/after {d0.date()}")

ret = wide.pct_change()

WINDOWS = {"3y": 756, "1y": 252}
ANN = 252

def stats_for(window):
    r = ret.tail(window).copy()
    rp = (r[w.index] * w.values).sum(axis=1)          # daily-rebalanced fixed weights
    rb = r["1306.T"]                                   # TOPIX proxy
    rn = r["^N225"]
    def ann_ret(x):
        return float((1 + x).prod() ** (ANN / len(x)) - 1)
    def mdd_of(x):
        c = (1 + x).cumprod()
        return float((c / c.cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN))
    dn = rp[rp < 0]
    sortino = float(rp.mean() * ANN / (dn.std() * np.sqrt(ANN))) if len(dn) else np.nan
    beta = float(rp.cov(rb) / rb.var())
    alpha = float((rp.mean() - beta * rb.mean()) * ANN)
    te = float((rp - rb).std() * np.sqrt(ANN))
    ir = float((rp - rb).mean() * ANN / te) if te > 0 else np.nan
    return {
        "port_ann_return": round(ann_ret(rp), 4),
        "topix_ann_return": round(ann_ret(rb), 4),
        "nikkei_ann_return": round(ann_ret(rn), 4),
        "volatility": round(vol, 4),
        "sharpe": round(ann_ret(rp) / vol, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(mdd_of(rp), 4),
        "topix_max_drawdown": round(mdd_of(rb), 4),
        "beta_vs_topix": round(beta, 3),
        "jensens_alpha_ann": round(alpha, 4),
        "tracking_error": round(te, 4),
        "information_ratio": round(ir, 3),
    }, rp, rb, rn

res3, rp3, rb3, rn3 = stats_for(WINDOWS["3y"])
res1, rp1, rb1, rn1 = stats_for(WINDOWS["1y"])
print("3y:", json.dumps(res3))
print("1y:", json.dumps(res1))

# contributions over 3y window
r3 = ret.tail(WINDOWS["3y"])
cumret = (1 + r3[w.index]).prod() - 1
contrib = (w * cumret).rename("contribution")
alloc2 = alloc.set_index("ticker").join(contrib)
role_contrib = alloc2.groupby("final_role")["contribution"].sum().sort_values(ascending=False)
theme_contrib = alloc2.groupby("theme")["contribution"].sum().sort_values(ascending=False)
sector_contrib = alloc2.groupby("sector")["contribution"].sum().sort_values(ascending=False)
print("role contribution:\n", role_contrib)

# concentration
hhi_stock = float((w ** 2).sum())
hhi_sector = float((alloc.groupby("sector")["target_weight_final"].sum() ** 2).sum())
hhi_theme = float((alloc.groupby("theme")["target_weight_final"].sum() ** 2).sum())

# leave-one-out on vol/MDD (3y)
loo_rows = []
for t in w.index:
    w2 = w.drop(t)
    w2 = w2 / w2.sum()
    rp2 = (r3[w2.index] * w2.values).sum(axis=1)
    c = (1 + rp2).cumprod()
    loo_rows.append({"ticker": t, "company": alloc2.loc[t, "company_name"],
                     "vol_wo": round(float(rp2.std() * np.sqrt(ANN)), 4),
                     "mdd_wo": round(float((c / c.cummax() - 1).min()), 4),
                     "contribution": round(float(contrib[t]), 4)})
loo = pd.DataFrame(loo_rows)
loo["vol_delta"] = loo["vol_wo"] - res3["volatility"]
loo.to_csv(P5 / "leave_one_out.csv", index=False)

# exclusion variants (3y stats without a group)
def excl_stats(mask, name):
    w2 = w[~w.index.isin(alloc.loc[mask, "ticker"])]
    if len(w2) == len(w):
        return None
    w2 = w2 / w2.sum()
    rp2 = (r3[w2.index] * w2.values).sum(axis=1)
    c = (1 + rp2).cumprod()
    return {"variant": name, "n": len(w2),
            "ann_return": round(float((1 + rp2).prod() ** (ANN / len(rp2)) - 1), 4),
            "volatility": round(float(rp2.std() * np.sqrt(ANN)), 4),
            "max_drawdown": round(float((c / c.cummax() - 1).min()), 4)}

top_contrib_ticker = contrib.idxmax()
variants = [
    excl_stats(alloc["ticker"] == top_contrib_ticker, f"top contributor excluded ({top_contrib_ticker})"),
    excl_stats(alloc["theme"] != "non_ai", "AI infrastructure themes excluded"),
    excl_stats(alloc["bm_raw"] >= 1.0, "low-PBR (PBR<=1) names excluded"),
]
variants = [v for v in variants if v]
pd.DataFrame(variants).to_csv(P5 / "exclusion_variants.csv", index=False)
print(pd.DataFrame(variants).to_string(index=False))

# figures ------------------------------------------------------------------
cum_p = (1 + rp3).cumprod()
cum_b = (1 + rb3).cumprod()
cum_n = (1 + rn3).cumprod()
dd_p = cum_p / cum_p.cummax() - 1
dd_b = cum_b / cum_b.cummax() - 1
fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True,
                         gridspec_kw={"height_ratios": [2, 1]})
axes[0].plot(cum_p.index, cum_p.values, color="black", label="Final20 (plan C)")
axes[0].plot(cum_b.index, cum_b.values, color="0.5", linestyle="--", label="TOPIX proxy (1306.T)")
axes[0].plot(cum_n.index, cum_n.values, color="0.7", linestyle=":", label="Nikkei 225")
axes[0].set_ylabel("cumulative (3y)")
axes[0].legend(fontsize=8)
axes[0].set_title("In-sample risk characterization (NOT a performance claim)")
axes[1].fill_between(dd_p.index, dd_p.values, 0, color="0.3", label="Final20 drawdown")
axes[1].plot(dd_b.index, dd_b.values, color="0.6", linestyle="--", label="TOPIX proxy")
axes[1].set_ylabel("drawdown")
axes[1].legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "drawdown_chart.png", dpi=200)
plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 4))
rc = role_contrib
bars = ax.bar(range(len(rc)), rc.values * 100, color="0.55", edgecolor="black")
for b, h in zip(bars, ["", "//", "..", "xx", "\\\\"]):
    b.set_hatch(h)
ax.set_xticks(range(len(rc)))
ax.set_xticklabels([x.replace(" ", "\n") for x in rc.index], fontsize=8)
ax.set_ylabel("contribution to 3y cumulative return (%pt)")
ax.set_title("Role contribution (in-sample, risk characterization)")
fig.tight_layout()
fig.savefig(FIG / "role_contribution.png", dpi=200)
plt.close(fig)

# risk summary table
risk_summary = pd.DataFrame([
    {"metric": "volatility (3y, ann.)", "portfolio": res3["volatility"], "topix_proxy": round(float(rb3.std()*np.sqrt(ANN)),4)},
    {"metric": "max drawdown (3y)", "portfolio": res3["max_drawdown"], "topix_proxy": res3["topix_max_drawdown"]},
    {"metric": "beta vs TOPIX (3y)", "portfolio": res3["beta_vs_topix"], "topix_proxy": 1.0},
    {"metric": "tracking error (3y)", "portfolio": res3["tracking_error"], "topix_proxy": 0.0},
    {"metric": "HHI stock", "portfolio": round(hhi_stock, 4), "topix_proxy": None},
    {"metric": "HHI sector", "portfolio": round(hhi_sector, 4), "topix_proxy": None},
    {"metric": "HHI theme", "portfolio": round(hhi_theme, 4), "topix_proxy": None},
])
risk_summary.to_csv(TAB / "risk_summary_table.csv", index=False)

json.dump({"framing": "in-sample risk characterization; NOT performance prediction",
           "data_repairs": {"1306.T": "unadjusted 1:10 split on 2026-03-30 corrected (x10 after)"},
           "window_3y": res3, "window_1y": res1,
           "hhi": {"stock": round(hhi_stock, 4), "sector": round(hhi_sector, 4), "theme": round(hhi_theme, 4)},
           "role_contribution_3y": {k: round(float(v), 4) for k, v in role_contrib.items()},
           "theme_contribution_3y": {k: round(float(v), 4) for k, v in theme_contrib.items()},
           "sector_contribution_top3": {k: round(float(v), 4) for k, v in sector_contrib.head(3).items()},
           "top_contributor": str(top_contrib_ticker),
           "loo_vol_range": [float(loo.vol_wo.min()), float(loo.vol_wo.max())],
           "exclusion_variants": variants,
           }, open(P5 / "phase5_validation_summary.json", "w"), ensure_ascii=False, indent=2)
print("\nwritten", P5)
