# -*- coding: utf-8 -*-
"""W2 acceptance criterion: the Layer 2 placebo distribution figure (V11_PLAN.md §4).

Design decisions, so they are not mistaken for defaults:

* SMALL MULTIPLES, not two overlaid histograms. The two drawing schemes are separate
  panels, so each panel carries a single series. That removes the need to distinguish
  series by colour, which is what makes the figure safe in greyscale print and under
  colour-vision deficiency -- the paper will be printed by referees.
* ONE fill hue plus ink for the marker. No categorical palette is used, so there are no
  adjacent-hue pairs to separate.
* The actual portfolio is a direct-labelled rule, not a legend entry: identity never
  rests on colour alone.
* Recessive axes, no top/right spines, no gridlines competing with the marks.

Output: outputs/stockleague_edition/fig_layer2_v11.pdf (vector, for \\includegraphics)
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"

FILL = "#8FA8BF"        # single mid-tone fill: ~55% luminance, reads as mid-grey in print
EDGE = "#5C7891"
INK = "#1A1A1A"
MUTED = "#6B6B6B"

L2 = json.load(open(ED / "layer2_placebo_v11.json"))
draws = np.load(ED / "layer2_draws_v11.npy")          # (2, N, 4): schemes x draws x metrics
SCHEMES = [("unstratified", "Unstratified draws", 0),
           ("sector_matched", "Sector-composition matched", 1)]
ACTUAL = L2["actual"]["ours_equal"]["ann_return"]

fig, axes = plt.subplots(2, 1, figsize=(6.4, 4.4), sharex=True)
for ax, (key, title, idx) in zip(axes, SCHEMES):
    x = draws[idx][:, 0] * 100                        # annualised return, per cent
    n, _, _ = ax.hist(x, bins=60, color=FILL, edgecolor=EDGE, linewidth=0.3)
    med = float(np.median(x))
    pct = L2["percentiles"][key]["ours_equal"]["ann_return"]

    # Headroom band above the bars so the annotations never sit on top of the data.
    top = n.max()
    ax.set_ylim(0, top * 1.34)
    label_y = top * 1.12

    ax.axvline(med, color=MUTED, linewidth=1.0, linestyle=(0, (4, 3)), ymax=1 / 1.34)
    ax.annotate("median %.1f%%" % med, xy=(med, label_y),
                xytext=(-3, 0), textcoords="offset points",
                fontsize=7.5, color=MUTED, ha="right", va="center")

    ax.axvline(ACTUAL * 100, color=INK, linewidth=2.0, ymax=1 / 1.34)
    ax.annotate("portfolio %.1f%% (%.1fth pctile)" % (ACTUAL * 100, pct),
                xy=(ACTUAL * 100, label_y),
                xytext=(-5, 0), textcoords="offset points",
                fontsize=8, color=INK, ha="right", va="center")

    ax.set_title(title, fontsize=9, loc="left", color=INK, pad=4)
    ax.set_ylabel("draws", fontsize=8, color=MUTED)
    ax.tick_params(labelsize=7.5, colors=MUTED, length=3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#C8C8C8")
        ax.spines[side].set_linewidth(0.6)

axes[-1].set_xlabel("three-year annualised return (%%), %s draws of %d firms"
                    % ("{:,}".format(L2["n_draws"]), L2["n_holdings"]),
                    fontsize=8, color=MUTED)
fig.tight_layout(pad=0.6)
fig.savefig(ED / "fig_layer2_v11.pdf", bbox_inches="tight")
print("wrote fig_layer2_v11.pdf")
print("  unstratified  median %.1f%%  portfolio %.1f%% (pctile %.1f)"
      % (np.median(draws[0][:, 0]) * 100, ACTUAL * 100,
         L2["percentiles"]["unstratified"]["ours_equal"]["ann_return"]))
print("  sector-matched median %.1f%%  portfolio %.1f%% (pctile %.1f)"
      % (np.median(draws[1][:, 0]) * 100, ACTUAL * 100,
         L2["percentiles"]["sector_matched"]["ours_equal"]["ann_return"]))
