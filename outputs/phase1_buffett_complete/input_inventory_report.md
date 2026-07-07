# Input Inventory Report

前回出力された `outputs/phase1_final` とローカル価格・分類データを監査した。

- 必須入力数: 16
- 存在確認OK: 16
- 欠損: 0
- 再現性判定: 再現性あり

## Inventory

| input_item | path | exists | rows | reproducibility_status |
| --- | --- | --- | --- | --- |
| universe | outputs/phase1_final/phase1_universe_final.csv | True | 3649 | OK |
| value_metrics_final | outputs/phase1_final/value_metrics_final.csv | True | 3099 | OK |
| gross_profitability_metrics | outputs/phase1_final/gross_profitability_metrics.csv | True | 3099 | OK |
| piotroski_signal_audit | outputs/phase1_final/piotroski_signal_audit.csv | True | 3099 | OK |
| sloan_accruals_final | outputs/phase1_final/sloan_accruals_final.csv | True | 3099 | OK |
| simple_distress_guardrail | outputs/phase1_final/simple_distress_guardrail.csv | True | 3099 | OK |
| liquidity_audit | outputs/phase1_final/liquidity_audit.csv | True | 3099 | OK |
| final20_anomaly_review | outputs/phase1_final/final20_anomaly_review.csv | True | 3099 | OK |
| phase1_final20_base | outputs/phase1_final/phase1_final20_base.csv | True | 20 | OK |
| phase1_final20_conservative | outputs/phase1_final/phase1_final20_conservative.csv | True | 20 | OK |
| portfolio_allocation_base | outputs/phase1_final/portfolio_allocation_base_5m.csv | True | 20 | OK |
| portfolio_allocation_conservative | outputs/phase1_final/portfolio_allocation_conservative_5m.csv | True | 20 | OK |
| prices_daily | data/processed/prices_daily.parquet | True | 4349347 | OK |
| latest prices / scores | data/processed/scores.csv | True | 3649 | OK |
| sector / market classification | data/processed/scores.csv | True | 3649 | OK |
| phase1 scripts | scripts/phase1_final/final_phase1.py | True |  | OK |