# Phase1 Buffett Complete README

## 実行順
1. `bash scripts/phase1_buffett_complete/run_all.sh`

## 必要ライブラリ
Python, pandas, numpy, matplotlib, pyarrow。

## 入力ファイル
`outputs/phase1_final/` の各CSV、`data/processed/scores.csv`、`data/processed/prices_daily.parquet`。

## 出力ファイル
`outputs/phase1_buffett_complete/`、`figures/phase1_buffett_complete/`、`phase1_buffett_complete.zip`。

## 各スクリプトの役割
| script | role |
| --- | --- |
| 01_inventory_inputs.py | 入力監査 |
| 02_metric_coverage_audit.py | 指標カバレッジ監査 |
| 03_anomaly_review.py | 異常値レビュー |
| 04_build_base_final20.py | base final20生成 |
| 05_build_conservative_final20.py | conservative final20生成 |
| 06_build_sector_adjusted_final20.py | sector-adjusted final20生成 |
| 07_allocate_5m.py | 500万円配分 |
| 08_generate_reports.py | レポート生成 |
| build_complete.py | 全工程の実体 |
| run_all.sh | 全工程実行 |

## 停止条件
必須入力CSVが欠損する、final20が20社未満、500万円投資率が95%未満、scripts実在確認が失敗する場合は完成判定を下げる。

## 再現方法
前回成果物 `outputs/phase1_final` が存在する状態で `run_all.sh` を実行する。

## scriptsの存在確認
| script | exists |
| --- | --- |
| 01_inventory_inputs.py | True |
| 02_metric_coverage_audit.py | True |
| 03_anomaly_review.py | True |
| 04_build_base_final20.py | True |
| 05_build_conservative_final20.py | True |
| 06_build_sector_adjusted_final20.py | True |
| 07_allocate_5m.py | True |
| 08_generate_reports.py | True |
| build_complete.py | True |
| run_all.sh | True |

## 既知の限界
Buffett本人の完全再現ではない。Piotroskiはavailable版。Ohlson/Altman原式は入力不足のため未実装。Gross Profitabilityは業種差がある。