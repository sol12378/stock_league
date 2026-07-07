# Phase1 Final Input Inventory

Inputs are the repaired Phase1 outputs plus local processed EDINET and price files.

| file_path | rows | columns | usable_metrics |
| --- | --- | --- | --- |
| data/processed/ablation_performance.csv | 8 | 10 |  |
| data/processed/candidates_top80.csv | 80 | 126 | volume;gross profit |
| data/processed/category_returns.csv | 4 | 10 |  |
| data/processed/contribution_by_stock.csv | 20 | 6 |  |
| data/processed/edinet_documents.csv | 10712 | 11 | EDINET fundamentals |
| data/processed/final_selection_reason.csv | 80 | 7 |  |
| data/processed/financial_sector_exclusion_check.csv | 151 | 24 | volume |
| data/processed/financial_sector_handling_summary.csv | 7 | 2 |  |
| data/processed/financial_sector_score_components.csv | 167 | 30 |  |
| data/processed/fundamentals_clean.csv | 3649 | 38 | EDINET fundamentals;gross profit |
| data/processed/fundamentals_raw.csv | 10712 | 19 | EDINET fundamentals;gross profit |
| data/processed/investment_eligibility_exclusion_summary.csv | 11 | 3 |  |
| data/processed/investment_eligibility_exclusions.csv | 597 | 19 |  |
| data/processed/latest_prices.csv | 3650 | 7 | latest prices;volume |
| data/processed/performance_summary.csv | 3 | 10 |  |
| data/processed/portfolio.csv | 20 | 138 | volume;gross profit |
| data/processed/portfolio_before_v12.csv | 20 | 101 | volume;gross profit |
| data/processed/portfolio_candidates.csv | 20 | 130 | volume;gross profit |
| data/processed/portfolio_returns.csv | 1222 | 7 |  |
| data/processed/prices_daily.parquet | 4349347 | 8 | latest prices;volume |
| data/processed/qualitative_edinet_summary.csv | 20 | 11 | EDINET fundamentals |
| data/processed/risk_return.csv | 22 | 3 |  |
| data/processed/score_correlation.csv | 8 | 9 |  |
| data/processed/scores.csv | 3649 | 122 | volume;gross profit |
| data/processed/screening_by_market.csv | 4 | 7 | universe |
| data/processed/screening_by_sector.csv | 33 | 7 | universe |
| data/processed/screening_summary.csv | 7 | 2 |  |
| data/processed/universe.csv | 3649 | 12 | universe |
| data/processed/yfinance_metrics.csv | 300 | 12 |  |
| outputs/phase1_repair/README.md |  |  |  |
| outputs/phase1_repair/edinet_share_facts.csv | 3579 | 11 | EDINET fundamentals |
| outputs/phase1_repair/final_checklist.md |  |  |  |
| outputs/phase1_repair/input_file_inventory.csv | 1480 | 9 |  |
| outputs/phase1_repair/input_file_inventory_report.md |  |  |  |
| outputs/phase1_repair/market_equity_reconstruction.csv | 3169 | 23 | value repaired |
| outputs/phase1_repair/phase1_formula_implementation_audit.md |  |  |  |
| outputs/phase1_repair/phase1_revised_candidates.csv | 3169 | 38 |  |
| outputs/phase1_repair/phase1_revised_final20_base.csv | 20 | 47 |  |
| outputs/phase1_repair/phase1_revised_final20_report.md |  |  |  |
| outputs/phase1_repair/phase1_revised_final20_sector_adjusted.csv | 20 | 47 |  |
| outputs/phase1_repair/phase1_revised_screening_funnel.csv | 5 | 6 |  |
| outputs/phase1_repair/phase1_value_data_repair_report.md |  |  |  |
| outputs/phase1_repair/ticker_mapping.csv | 3649 | 8 |  |
| outputs/phase1_repair/value_coverage_audit.csv | 70 | 3 |  |
| outputs/phase1_repair/value_coverage_audit.md |  |  |  |
| outputs/phase1_repair/value_metric_anomaly_report.csv | 129 | 7 |  |
| outputs/phase1_repair/value_metric_anomaly_report.md |  |  |  |
| outputs/phase1_repair/value_metrics_repaired.csv | 3169 | 19 | value repaired |