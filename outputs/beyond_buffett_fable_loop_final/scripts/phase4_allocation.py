#!/usr/bin/env python
"""Phase4: theoretical portfolio allocation for the Final20.

Plans:
  A equal weight (5% x 20)
  B role budget (25/25/25/15/10 split equally within role)
  C risk-adjusted role allocation (inverse-vol x liquidity x evidence x confidence within role)
  D constrained minimum-variance overlay (role budgets fixed, per-stock bounds) - reference
Final = C (explainability first), with unit-share execution at L=1 (project convention,
Nikkei STOCK League virtual portfolio) and L=100 sensitivity.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import minimize

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
P4 = OUT / "phase4_portfolio_allocation"
FIG = OUT / "figures"
TAB = OUT / "tables"
for p in (P4, FIG, TAB):
    p.mkdir(parents=True, exist_ok=True)

BUDGET = 5_000_000
CAP = 0.08
ROLE_BUDGET = {"Buffett Core": 0.25, "Transformation Core": 0.25,
               "Emerging Core": 0.25, "Dual Moat": 0.15, "Bridge / Diversifier": 0.10}

f20 = pd.read_csv(OUT / "phase3_moat_construction/final20_selected.csv")
f20["code_n"] = f20["code"].astype(str).str.replace(".T", "", regex=False).str.replace("﻿", "", regex=False).str.split(".").str[0].str.zfill(4)
f20["ticker"] = f20["code_n"] + ".T"
cols = ["code_n", "ticker", "company_name", "sector", "final_role", "final_evidence_level",
        "phase2_confidence_score", "avg_trading_value_60d", "ai_infrastructure_category"]
f = f20[cols].copy()
f["theme"] = f["ai_infrastructure_category"].fillna("non_ai").replace("", "non_ai")
f.loc[f["theme"].isna() | (f["theme"] == "nan"), "theme"] = "non_ai"

# ---- prices / risk stats -----------------------------------------------------
px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                     columns=["date", "ticker", "adj_close", "close"])
px = px[px["ticker"].isin(set(f["ticker"]))]
wide = px.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
last_close = px.sort_values("date").groupby("ticker")["close"].last()

ret = wide.pct_change().dropna(how="all")
ret1y = ret.tail(252)
vol_1y = ret1y.std() * np.sqrt(252)
# max drawdown over last 1y
w1y = wide.tail(253)
mdd = ((w1y / w1y.cummax()) - 1).min()

f = f.merge(vol_1y.rename("vol_1y"), left_on="ticker", right_index=True, how="left")
f = f.merge(mdd.rename("mdd_1y"), left_on="ticker", right_index=True, how="left")
f = f.merge(last_close.rename("price"), left_on="ticker", right_index=True, how="left")
assert f["price"].notna().all(), "missing price for some final20"
print("price coverage OK; vol range:", round(f.vol_1y.min(), 3), "-", round(f.vol_1y.max(), 3))

# ---- Plan A: equal ------------------------------------------------------------
f["w_equal"] = 1 / len(f)

# ---- Plan B: role budget, equal within role -----------------------------------
f["w_role_budget"] = f.apply(lambda r: ROLE_BUDGET[r.final_role] / (f.final_role == r.final_role).sum(), axis=1)

# ---- Plan C: risk-adjusted within role ----------------------------------------
liq = f["avg_trading_value_60d"].fillna(0)
liq_factor = np.where(liq >= 50e6, 1.0, np.where(liq >= 30e6, 0.85, 0.70))
ev_factor = 1 + 0.05 * (f["final_evidence_level"].fillna(1) - 2)   # L3:1.05 L2:1.0 L1:0.95
conf_factor = 0.5 + 0.5 * f["phase2_confidence_score"].fillna(0.9)
inv_vol = 1 / f["vol_1y"].clip(lower=0.10)
raw = inv_vol * liq_factor * ev_factor * conf_factor
f["w_risk"] = 0.0
for role, b in ROLE_BUDGET.items():
    idx = f.final_role == role
    f.loc[idx, "w_risk"] = b * raw[idx] / raw[idx].sum()
# cap 8% and redistribute within role
for _ in range(5):
    over = f["w_risk"] > CAP
    if not over.any():
        break
    excess = (f.loc[over, "w_risk"] - CAP).sum()
    f.loc[over, "w_risk"] = CAP
    for role in ROLE_BUDGET:
        idx = (f.final_role == role) & (~over)
        role_excess = excess * (f.loc[f.final_role == role, "w_risk"].sum() /
                                f.loc[~over, "w_risk"].sum()) if f.loc[~over].shape[0] else 0
    # simpler: renormalize non-capped within each role to keep role budgets
    for role, b in ROLE_BUDGET.items():
        idx = f.final_role == role
        capped = idx & (f["w_risk"] >= CAP - 1e-12)
        free = idx & ~capped
        rem = b - f.loc[capped, "w_risk"].sum()
        if free.any() and rem > 0:
            f.loc[free, "w_risk"] = rem * f.loc[free, "w_risk"] / f.loc[free, "w_risk"].sum()

# ---- Plan D: constrained min-variance (reference) -----------------------------
tickers = f["ticker"].tolist()
Rm = ret1y[tickers].fillna(0)
S = Rm.cov().values * 252
n = len(tickers)
role_arr = f["final_role"].values

def pvar(w):
    return float(w @ S @ w)

cons = [{"type": "eq", "fun": lambda w, r=role, b=b: w[role_arr == r].sum() - b}
        for role, b in ROLE_BUDGET.items()]
bounds = [(0.02, CAP)] * n
w0 = f["w_role_budget"].values
res = minimize(pvar, w0, bounds=bounds, constraints=cons, method="SLSQP",
               options={"maxiter": 500})
f["w_minvar"] = res.x if res.success else w0
print("minvar success:", res.success, "vol_D:", round(np.sqrt(pvar(f['w_minvar'].values)), 4))

# ---- portfolio-level stats ----------------------------------------------------
def port_stats(wcol):
    w = f[wcol].values
    vol = float(np.sqrt(w @ S @ w))
    hhi_stock = float((w ** 2).sum())
    sec = f.groupby("sector")[wcol].sum()
    thm = f.groupby("theme")[wcol].sum()
    return {"vol": round(vol, 4), "hhi_stock": round(hhi_stock, 4),
            "max_stock": round(float(w.max()), 4),
            "max_sector": round(float(sec.max()), 4), "max_sector_name": sec.idxmax(),
            "max_theme_ex_nonai": round(float(thm.drop("non_ai", errors="ignore").max()), 4)}

stats = {p: port_stats(c) for p, c in
         [("A_equal", "w_equal"), ("B_role_budget", "w_role_budget"),
          ("C_risk_adjusted", "w_risk"), ("D_minvar", "w_minvar")]}
print(json.dumps(stats, indent=1))

# ---- unit-share execution for final plan (C) ----------------------------------
def execute(wcol, lot):
    w = f[wcol]
    q = (np.floor(BUDGET * w / (f["price"] * lot)) * lot).astype(int)
    amt = q * f["price"]
    return q, amt

for lot, tag in ((1, "L1"), (100, "L100")):
    q, amt = execute("w_risk", lot)
    f[f"qty_{tag}"] = q
    f[f"amount_{tag}"] = amt
f["actual_w_L1"] = f["amount_L1"] / BUDGET
f["actual_w_L100"] = f["amount_L100"] / BUDGET
cash_L1 = BUDGET - f["amount_L1"].sum()
cash_L100 = BUDGET - f["amount_L100"].sum()
print("L=1: invested", int(f.amount_L1.sum()), "cash", int(cash_L1),
      "| L=100: invested", int(f.amount_L100.sum()), "cash", int(cash_L100),
      "unbuyable", int((f.qty_L100 == 0).sum()))

# ---- write CSVs ---------------------------------------------------------------
base_cols = ["code_n", "company_name", "sector", "theme", "final_role",
             "final_evidence_level", "price", "vol_1y", "mdd_1y", "avg_trading_value_60d"]
f[base_cols + ["w_equal"]].to_csv(P4 / "allocation_equal_weight.csv", index=False)
f[base_cols + ["w_role_budget"]].to_csv(P4 / "allocation_role_budget.csv", index=False)
f[base_cols + ["w_risk"]].to_csv(P4 / "allocation_risk_adjusted.csv", index=False)
f[base_cols + ["w_minvar"]].to_csv(P4 / "allocation_minvar_reference.csv", index=False)
fin = f[base_cols + ["w_equal", "w_role_budget", "w_risk", "w_minvar",
                     "qty_L1", "amount_L1", "actual_w_L1", "qty_L100", "amount_L100", "actual_w_L100"]].copy()
fin = fin.rename(columns={"w_risk": "target_weight_final"})
fin.to_csv(P4 / "allocation_final.csv", index=False)
fin.to_csv(TAB / "allocation_table_for_report.csv", index=False)

json.dump({"plan_stats": stats,
           "final_plan": "C_risk_adjusted",
           "execution_L1": {"invested": int(f.amount_L1.sum()), "cash": int(cash_L1),
                            "deploy_rate": round(float(f.amount_L1.sum() / BUDGET), 4),
                            "max_abs_dev_from_target": round(float((f.actual_w_L1 - f.w_risk).abs().max()), 4)},
           "execution_L100": {"invested": int(f.amount_L100.sum()), "cash": int(cash_L100),
                              "deploy_rate": round(float(f.amount_L100.sum() / BUDGET), 4),
                              "unbuyable": int((f.qty_L100 == 0).sum()),
                              "unbuyable_names": f.loc[f.qty_L100 == 0, "company_name"].tolist()},
           "role_totals_final": {k: round(float(v), 4) for k, v in f.groupby("final_role")["w_risk"].sum().items()},
           }, open(P4 / "phase4_summary.json", "w"), ensure_ascii=False, indent=2)

# ---- figures (monochrome-friendly) --------------------------------------------
plt.rcParams["font.family"] = ["Hiragino Sans", "Arial Unicode MS", "sans-serif"]
grays = ["0.2", "0.4", "0.55", "0.7", "0.85"]
hatches = ["", "//", "..", "xx", "\\\\", "++", "oo", "--", "**", "OO", "||"]

role_order = list(ROLE_BUDGET)
rw = f.groupby("final_role")["w_risk"].sum().reindex(role_order)
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(range(len(rw)), rw.values * 100, color=grays)
for b, h in zip(bars, hatches):
    b.set_hatch(h)
    b.set_edgecolor("black")
ax.set_xticks(range(len(rw)))
ax.set_xticklabels(["Buffett\nCore", "Transformation\nCore", "Emerging\nCore", "Dual\nMoat", "Bridge/\nDiversifier"], fontsize=9)
ax.set_ylabel("weight (%)")
ax.set_title("Portfolio role weights (final plan C)")
for i, v in enumerate(rw.values):
    ax.text(i, v * 100 + 0.3, f"{v*100:.1f}%", ha="center", fontsize=9)
fig.tight_layout()
fig.savefig(FIG / "portfolio_role_weights.png", dpi=200)
plt.close(fig)

sw = f.groupby("sector")["w_risk"].sum().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(7, 4.5))
bars = ax.barh(range(len(sw)), sw.values * 100, color="0.6", edgecolor="black")
for b, h in zip(bars, hatches * 2):
    b.set_hatch(h)
ax.set_yticks(range(len(sw)))
ax.set_yticklabels(sw.index, fontsize=8)
ax.axvline(25, color="black", linestyle="--", linewidth=1)
ax.text(25.2, 0.2, "sector cap 25%", fontsize=8)
ax.set_xlabel("weight (%)")
ax.set_title("Portfolio sector weights (final plan C)")
fig.tight_layout()
fig.savefig(FIG / "portfolio_sector_weights.png", dpi=200)
plt.close(fig)

tw_ = f.groupby("theme")["w_risk"].sum().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(7, 3.8))
bars = ax.barh(range(len(tw_)), tw_.values * 100, color="0.6", edgecolor="black")
for b, h in zip(bars, hatches * 2):
    b.set_hatch(h)
ax.set_yticks(range(len(tw_)))
ax.set_yticklabels(tw_.index, fontsize=9)
ax.axvline(25, color="black", linestyle="--", linewidth=1)
ax.text(25.2, 0.2, "theme cap 25%", fontsize=8)
ax.set_xlabel("weight (%)")
ax.set_title("Portfolio theme weights (final plan C)")
fig.tight_layout()
fig.savefig(FIG / "portfolio_theme_weights.png", dpi=200)
plt.close(fig)

print("\nfinal plan C weights:")
print(f[["code_n", "company_name", "final_role", "w_risk", "qty_L1", "amount_L1"]]
      .sort_values(["final_role", "w_risk"], ascending=[True, False]).to_string(index=False))
print("\nwritten", P4)
