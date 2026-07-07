# Normalization Report

- Main experiment: market_percentile.
- Validation methods: sector_percentile, winsorized_zscore, robust_zscore.
- Main missing handling: neutral_rank_with_missing_penalty.
- GP missing companies receive `gp_missing_review_flag = true` and are separately reviewed.
- Sloan Accruals is inverted so higher `sloan_quality_score` is better.
