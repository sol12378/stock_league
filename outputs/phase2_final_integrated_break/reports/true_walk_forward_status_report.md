# True Walk-forward Optimization Status

True walk-forward optimization requires at least two folds where train rows are sufficient and test-year 252 trading-day targets have matured.

| test_availability_year | eligible_for_true_252d_walk_forward | strict_ready_count | forward_252d_eligible_count | reason |
| --- | --- | --- | --- | --- |
| 2023 | True | 1009 | 1200 | eligible |
| 2024 | False | 998 | 1200 | insufficient strict-ready rows or 252d target maturity |
| 2025 | False | 997 | 215 | insufficient strict-ready rows or 252d target maturity |

Completed: False

Fewer than two folds have both sufficient strict-ready rows and mature 252d targets.
