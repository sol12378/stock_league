# Flag Reconciliation

`flag_audit_summary.csv` reports **825** Phase3-review rows, while direct recount of the formal review-ready CSV yields **840**. Difference: **15**. Per the design rule, all downstream decisions use the direct CSV recount.

Soft-review flags do not automatically exclude a company. Hard exclusions use formal-universe membership, distress, anomaly, liquidity below ¥30,000,000/day, negative equity, persistent losses, and excessive financial missingness. Phase1 Top5 remain fixed but retain warning flags.
