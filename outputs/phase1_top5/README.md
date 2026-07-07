# Phase1 Top5 README

## 入力ファイル
`outputs/phase1_buffett_complete/`、`outputs/phase1_final/`、`data/processed/fundamentals_raw.csv`、`data/processed/scores.csv` を使う。

## 実行順
`bash scripts/phase1_top5/run_all.sh`

## 必要ライブラリ
Python, pandas, numpy, matplotlib。

## 出力ファイル
`outputs/phase1_top5/`、`figures/phase1_top5/`、`phase1_top5.zip`。

## Ohlson / Altmanの実装可否
Ohlson O-ScoreとAltman Z-Scoreは原式忠実実装不可。欠損変数と部分attemptを出力し、Top5選定ではsimple distress guardrailを使う。

## Top5選定ルール
B/M、E/P、Gross Profitability、Piotroski available signal score、Sloan Accruals、simple distress guardrail、Liquidity、Anomaly Reviewを順に通し、重み付き総合スコアを作らず逐次tie-breakで5社を選ぶ。同一業種は原則2社まで。

## 再現方法
前回の `phase1_buffett_complete` 出力がある状態でrun_all.shを実行する。

## scriptsの存在確認
| script | exists |
| --- | --- |
| 01_inventory_ohlson_altman_variables.py | True |
| 02_attempt_ohlson_altman.py | True |
| 03_build_top5_candidates.py | True |
| 04_select_buffett_core_top5.py | True |
| 05_generate_top5_reports.py | True |
| build_top5.py | True |
| run_all.sh | True |

## 既知の限界
Buffett本人の経営者評価・保険フロート・非公開企業買収は再現しない。Piotroskiはavailable版。Ohlson/Altmanは原式未実装。