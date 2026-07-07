# Normalization Report

- Main experiment: market percentile ranks.
- Sector-adjusted comparison: per-sector percentile ranks saved separately.
- Winsorized and robust z-score variants are implemented in the generation script for sensitivity checks.
- Missing core metrics are imputed by the metric median and penalized through missingness_penalty.
- Sloan Accruals is inverted so that higher sloan_quality_score means better accrual quality.
- Distress is treated as a simple safety proxy; Ohlson/Altman original formulas are not claimed here.
