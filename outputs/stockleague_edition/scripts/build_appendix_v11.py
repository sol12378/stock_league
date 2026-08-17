# -*- coding: utf-8 -*-
"""Appendix tables required by V11_PLAN.md §6 item 8: gate-threshold robustness, cost
sensitivity, and the evidence-level / realised-revenue correspondence.

The correspondence table is the one the plan marked "if possible". It is possible, it is
tiny, and it points the wrong way for our own proposal -- level-3 firms grew revenue more
slowly than level-2 firms over the window. We report it because omitting an unfavourable
descriptive table from a paper whose argument is about honest measurement would be absurd.

Output: outputs/stockleague_edition/appendix_v11.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
P3 = ROOT / "outputs/phase3_beyond_buffett_v2"

# ---------------------------------------------------------------- gate-threshold robustness
RB = json.load(open(ED / "robustness_v7.json"))
base = RB["base_shu5"]
robustness = {
    "base_selection": base,
    "base_note": ("The five mechanically-selected holdings. Each variant perturbs exactly one "
                  "threshold in the quality gate and re-runs the selection; the overlap column counts "
                  "how many of the five survive."),
    "n_variants": int(RB["n_variants"]),
    "min_overlap": int(RB["min_overlap"]),
    "variants": [{"variant": k, "selection": v, "overlap_with_base": int(RB["overlap_with_base"][k])}
                 for k, v in RB["variants"].items()],
}

# ---------------------------------------------------------------- cost sensitivity
CO = json.load(open(ED / "costs_v11.json"))
cost_rows = []
for port, label in [("ours_equal", "Portfolio (equal weight)"),
                    ("benchmark_buf20_equal", "Mechanical benchmark")]:
    r = CO["results"][port]
    row = {"series": label,
           "annual_turnover_monthly": r["annual_turnover_monthly"],
           "annual_turnover_daily": r["annual_turnover_daily"]}
    for bp, blk in r["cost_grid_monthly"].items():
        row["monthly_" + bp] = blk["ann_return"]
    row["daily_no_cost"] = r["daily_rebalance_no_cost"]["ann_return"]
    row["daily_headline_cost"] = r["daily_rebalance_headline_cost"]["ann_return"]
    cost_rows.append(row)

# ---------------------------------------------------------------- evidence level vs realised revenue
cur = pd.read_csv(P3 / "scripts/phase3_selection/curated_evidence.csv", dtype=str)
cur["code"] = cur.code.str.zfill(4)
cur["level"] = cur.emerging_evidence_level.astype(int)

fund = pd.read_csv(ROOT / "data/processed/fundamentals_raw.csv", dtype={"code": str}, low_memory=False)
fund["code"] = fund["code"].str.zfill(4)
fund["period_end"] = pd.to_datetime(fund["period_end"])
fund["revenue"] = pd.to_numeric(fund["revenue"], errors="coerce")

rows = []
for code, lvl in zip(cur.code, cur.level):
    h = (fund[fund.code == code].drop_duplicates(subset=["period_end"], keep="last")
         .sort_values("period_end"))
    if len(h) < 2 or pd.isna(h.revenue.iloc[0]) or pd.isna(h.revenue.iloc[-1]) or h.revenue.iloc[0] <= 0:
        continue
    yrs = len(h) - 1
    rows.append({"code": code, "level": int(lvl), "periods": int(len(h)),
                 "revenue_cagr": round(float((h.revenue.iloc[-1] / h.revenue.iloc[0]) ** (1 / yrs) - 1), 4)})
corr = pd.DataFrame(rows)
by_level = {
    str(int(l)): {"n": int(len(g)),
                  "median_revenue_cagr": round(float(g.revenue_cagr.median()), 4),
                  "mean_revenue_cagr": round(float(g.revenue_cagr.mean()), 4),
                  "min": round(float(g.revenue_cagr.min()), 4),
                  "max": round(float(g.revenue_cagr.max()), 4)}
    for l, g in corr.groupby("level")
}
levels_sorted = sorted(by_level, key=int)
higher_grew_more = (by_level[levels_sorted[-1]]["median_revenue_cagr"]
                    > by_level[levels_sorted[0]]["median_revenue_cagr"])

correspondence = {
    "question": ("Do firms placed higher on the evidence ladder go on to report faster "
                 "theme-relevant revenue growth? This is the crudest possible version of the "
                 "validation described in the manuscript, on the only firms for which we have "
                 "hand-coded levels."),
    "sample": ("The %d hand-coded level-2 and level-3 firms. Revenue growth is the annualised rate "
               "across all fiscal years on file, from the same filing panel used elsewhere; it is "
               "TOTAL revenue, not theme-attributable revenue, which almost no firm discloses "
               "separately." % len(corr)),
    "by_level": by_level,
    "firms": corr.sort_values(["level", "revenue_cagr"]).to_dict("records"),
    "result": ("Level-3 firms grew revenue MORE SLOWLY than level-2 firms over this window "
               "(median %.1f%% versus %.1f%%). The ordering runs against our own proposal."
               % (by_level[levels_sorted[-1]]["median_revenue_cagr"] * 100,
                  by_level[levels_sorted[0]]["median_revenue_cagr"] * 100)),
    "higher_level_grew_faster": bool(higher_grew_more),
    "interpretation": ("This is not evidence that the ladder fails, and we would resist a reader "
                       "concluding either way from it. With %s and %s firms per cell, total rather "
                       "than theme-attributable revenue, no as-of coding, and no control for sector "
                       "or size, the table has no power to order the levels. We report it because it "
                       "is the honest state of the only correspondence we can compute, and because a "
                       "paper arguing for careful measurement should not omit the descriptive table "
                       "that happens to be unflattering."
                       % (by_level[levels_sorted[0]]["n"], by_level[levels_sorted[-1]]["n"])),
}

out = {"robustness": robustness, "cost_sensitivity": cost_rows, "evidence_correspondence": correspondence}
json.dump(out, open(ED / "appendix_v11.json", "w"), ensure_ascii=False, indent=1)

print("gate-threshold robustness: %d variants, minimum overlap %d of %d"
      % (robustness["n_variants"], robustness["min_overlap"], len(base)))
for v in robustness["variants"]:
    print("   %-22s overlap %d" % (v["variant"], v["overlap_with_base"]))
print("\nevidence level vs realised revenue growth (n=%d)" % len(corr))
for l in levels_sorted:
    b = by_level[l]
    print("   level %s: n=%d  median %+.1f%%  mean %+.1f%%  [%+.1f%%, %+.1f%%]"
          % (l, b["n"], b["median_revenue_cagr"] * 100, b["mean_revenue_cagr"] * 100,
             b["min"] * 100, b["max"] * 100))
print("   -> higher level grew faster: %s" % correspondence["higher_level_grew_faster"])
print("\nwritten -> appendix_v11.json")
