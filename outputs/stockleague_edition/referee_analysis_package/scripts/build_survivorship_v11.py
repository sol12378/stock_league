# -*- coding: utf-8 -*-
"""W7: survivorship in the price panel.

The JPX delisting list could not be retrieved (the listing pages returned HTTP 403 to an
automated request on 2026-07-25), so the bias is not quantified. Per the pre-registered
fallback we instead measure the panel's survivorship directly and state the direction of
the bias without claiming a magnitude.

A delisted ticker shows up in a daily panel as a series that simply stops. We count tickers
whose last observation precedes the panel's end by more than a threshold, which is an upper
bound on how many delistings the panel could contain.

Output: outputs/stockleague_edition/survivorship_v11.json
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
THRESHOLDS = [30, 60, 180]

px = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
px = px.dropna(subset=["adj_close"])
last = px.groupby("ticker")["date"].max()
first = px.groupby("ticker")["date"].min()
panel_end, panel_start = px.date.max(), px.date.min()

counts = {}
for th in THRESHOLDS:
    stopped = last[last < panel_end - pd.Timedelta(days=th)]
    counts[th] = {"n_tickers_stopped": int(len(stopped)),
                  "share_of_panel": round(float(len(stopped) / len(last)), 5),
                  "tickers": sorted(stopped.index.tolist())[:20]}

out = {
    "retrieval_attempt": ("The JPX delisted-companies listing was requested on 2026-07-25 and returned "
                          "HTTP 403 to an automated request. No delisting list is included in the "
                          "repository. The bias is therefore NOT quantified, and we do not estimate it."),
    "panel": {"start": str(panel_start.date()), "end": str(panel_end.date()),
              "n_tickers": int(len(last))},
    "stopped_series": counts,
    "direction_of_bias": ("Upward for every historical return series in this paper, including the "
                          "benchmarks and the placebo distribution. A panel assembled from currently "
                          "listed tickers omits firms that were delisted after failing, so any "
                          "portfolio drawn from it -- ours, the mechanical benchmark, and each of the "
                          "10,000 random draws -- is drawn from a universe with the worst outcomes "
                          "already removed."),
    "differential_effect": ("Because the bias inflates the placebo distribution as well as the "
                            "portfolio, the Layer 2 percentile is less exposed to it than a "
                            "raw return comparison would be. That is an argument for preferring the "
                            "randomisation framing, not an argument that the bias is small."),
    "upper_bound_reading": ("At the 30-day threshold the panel contains %d ticker(s) whose series "
                            "stops early, out of %d. The panel is, to a first approximation, a "
                            "survivors-only panel: it does not contain the delistings, so the count of "
                            "stopped series is an upper bound on what could be recovered from it and "
                            "not an estimate of how many firms actually delisted."
                            % (counts[30]["n_tickers_stopped"], len(last))),
}
json.dump(out, open(ED / "survivorship_v11.json", "w"), ensure_ascii=False, indent=1)

print("panel %s..%s, %d tickers" % (out["panel"]["start"], out["panel"]["end"], out["panel"]["n_tickers"]))
for th, c in counts.items():
    print("  series stopping >%3dd before panel end: %d (%.3f%%)"
          % (th, c["n_tickers_stopped"], c["share_of_panel"] * 100))
print("\nwritten -> survivorship_v11.json")
