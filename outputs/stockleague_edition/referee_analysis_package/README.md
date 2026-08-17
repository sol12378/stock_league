# Replication package — *When Keyword Measures of Thematic Exposure Break Down* (v11)

Every number in the manuscript is produced by a script in `scripts/` and written to a JSON file in
`outputs/`. The manuscript reads those JSON files through a generator
(`build_wp_tables_v11.py`) that emits `tables_v11.tex` and `numbers_v11.tex`; no number is typed by
hand into the LaTeX source. A machine check (`check_gates_v11.py`) enforces this along with the
paper's other self-imposed constraints, and fails the build if any is violated.

**Random seed: 20260725.** It appears in `build_layer2_placebo_v11.py` and in the manuscript text.
Re-running the randomisation reproduces the reported percentiles exactly.

## What you need

- Python 3.11+ with `pandas`, `numpy`, `scipy`, `pyarrow`, `matplotlib`
- LaTeX with XeTeX (we use [Tectonic](https://tectonic-typesetting.github.io/) 0.16)
- The two data panels described below

## Data we do not redistribute

The price panel is vendor data and is not included. It is a Parquet file at
`data/processed/prices_daily.parquet` with columns `date`, `ticker`, `adj_close`, covering
2021-06-01 to 2026-06-01 for 3,650 Tokyo-listed tickers (`NNNN.T` form) plus `^N225`. Daily adjusted
closes from any vendor with Japanese coverage will substitute; we obtained ours via `yfinance`.

Two files derived from public EDINET filings are likewise expected at
`data/processed/fundamentals_raw.csv` (10,712 annual securities reports, 3,559 firms, with a
`submit_date` submission timestamp per filing — this column is what makes the point-in-time analysis
possible) and `data/processed/scores.csv` (the contest edition's scored cross-section, which supplies
sector codes and the thematic-exposure score audited in Section 2).

Paths are absolute constants at the top of each script (`ROOT = ...`); change `ROOT` to your checkout.

## Reproducing each table

Run in this order — later scripts read earlier outputs.

| Table / section | Command | Output |
|---|---|---|
| Layer 1 out-of-sample table + appendix funnel/$t$ table | `python scripts/build_layer1_pit_v11.py` | `layer1_pit_v11.json` |
| Layer 2 randomisation table | `python scripts/build_layer2_placebo_v11.py` | `layer2_placebo_v11.json` |
| Factor attribution table | `python scripts/build_factors_v11.py` | `factors_v11.json` |
| Cost / deflated-Sharpe table, the MDE figures, the specification count | `python scripts/build_costs_v11.py` | `costs_v11.json` |
| Saturation and evidence-ladder tables, own-portfolio audit | `python scripts/build_saturation_v11.py` | `saturation_v11.json` |
| §6 survivorship | `python scripts/build_survivorship_v11.py` | `survivorship_v11.json` |
| Appendix: robustness, cost sensitivity, evidence-level correspondence | `python scripts/build_appendix_v11.py` | `appendix_v11.json` |
| Layer 2 distribution figure | `python scripts/build_fig_layer2_v11.py` | `fig_layer2_v11.pdf` |
| Benchmark degrees-of-freedom table | — | reads `control_comparison_v10.json` from the contest edition |
| All LaTeX tables and in-text numbers | `python scripts/build_wp_tables_v11.py` | `tables_v11.tex`, `numbers_v11.tex` |
| Gate checks | `python scripts/check_gates_v11.py` | `gates_v11.json`, exit 1 on failure |
| The paper | `tectonic -X compile referee_wp_v11.tex --outdir .` | `referee_wp_v11.pdf` |

Table numbers are not stable across drafts because floats are emitted per section and renumber when
text moves; the table is keyed by content instead. `build_wp_tables_v11.py` writes one file per
section (`tables_l1_v11.tex`, `tables_sat_v11.tex`, and so on) plus a `tables_v11.tex` manifest.

`build_costs_v11.py` reads `layer1_pit_v11.json` and `layer2_placebo_v11.json`; the trial variance
used to deflate the Sharpe ratio is the empirical standard deviation of Sharpe ratios across the
Layer 2 placebo draws, so the placebo script must run first.

## What the gate checks enforce

`check_gates_v11.py` reports twelve gates. The ones a referee may want to verify independently:

- **G2** — no hand-typed decimal percentage appears in the LaTeX prose; the paper must read its
  numbers from the generated files.
- **G3** — no test statistic and no use of the word "significant" anywhere in the Layer 2 or Layer 3
  sections. Only Layer 1 admits testing.
- **G4** — the ordering disclosure (that the main benchmark weighting was changed *after* seeing what
  the alternative implied) is present in the Limitations.
- **G5** — no claim to have beaten a Buffett-style benchmark survives as a conclusion.
- **G6** — the statement that the fifteen discretionary holdings are not point-in-time reproducible
  appears *before* the Layer 1 table.
- **G10** — every bibliography entry is cited; no padding.

## Known deviations and what they cost

These are stated in the paper and repeated here so a replicator is not surprised:

1. **The Layer 1 ranking is not the contest ranking.** The contest ranks on
   `rank(ROE) + rank(earnings yield)`. Earnings yield needs a share count; no point-in-time share
   counts exist in the data, and the 2026 snapshot covers 300 of 3,649 firms — a set selected by the
   2026 pipeline, so screening on it would inject look-ahead. Layer 1 ranks on ROE alone, with
   `rank(ROE) + rank(operating margin)` as a robustness check. Layer 1 therefore validates the quality
   gate and quality ranking, not the valuation leg. The discarded earnings-yield branch is counted in
   the specification total because we ran it.
2. **The loss-free gate is translated.** The contest requires three consecutive loss-free years; at
   the earliest as-of date only two are on file for most firms, so the gate becomes "loss-free over
   the periods available at the as-of date". Available-period counts are reported per as-of date.
3. **No value factor.** Same root cause as (1).
4. **Survivorship is not quantified.** The JPX delisting list returned HTTP 403 to an automated
   request on 2026-07-25. Direction is stated; magnitude is not estimated.
5. **Two "Sharpe ratios" appear.** Performance tables report the geometric Sharpe (annualised
   compound return / annualised volatility). The deflated Sharpe calculation requires the arithmetic
   Sharpe (mean/sd of daily returns, annualised), which is lower. Both are labelled where they appear.

## Contact

Questions, and especially disagreements with the level-2 and level-3 evidence assignments — each of
which carries a source URL and quoted passage so that it can be disputed — are welcome.
