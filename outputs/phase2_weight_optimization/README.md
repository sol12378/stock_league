# BEYOND BUFFETT Phase2 Weight Optimization

## この成果物の位置づけ

このZIPは、BEYOND BUFFETT Phase2の重み最適化探索実験である。  
Phase1の正式ルールを置き換えるものではない。  
Phase1では独自重み付き総合式を避けた。  
本実験は、Phase2の「破」として、各先行研究式の相対的重要度を調べるために行った。

## 参照したPhase1成果物

- outputs/phase1_buffett_complete/screening_candidates_complete.csv
- outputs/phase1_top5/phase1_buffett_core_top5.csv
- outputs/phase1_top5/phase1_top5_candidate_pool.csv
- outputs/phase1_top5/report_tables/phase1_top5_screening_funnel.csv
- outputs/phase1_top5/report_tables/phase1_top5_metrics_table.csv

Phase1成果物はコピーせず、上記パスを参照した。

## 使い方

1. ZIPを展開する
2. README.mdを読む
3. reports/weight_optimization_report.mdを確認する
4. rankings/exploratory_weighted_ranking_all.csvを見る
5. rankings/phase1_top5_rank_check.csvでPhase1 Top5の順位を確認する
6. reports/phase3_handoff_from_weight_experiment.mdをPhase3設計に使う

## 注意

Exploratory Weighted Buffett Score は正式な銘柄選定式ではない。  
将来リターン最大化モデルではない。  
Phase3での候補探索・感度分析・指標重要度確認のための補助成果物である。

## Main Files

- reports/weight_optimization_report.md
- reports/phase1_vs_weighted_experiment_report.md
- reports/limitations.md
- reports/phase3_handoff_from_weight_experiment.md
- rankings/exploratory_weighted_ranking_all.csv
- rankings/phase1_top5_rank_check.csv
- optimization/selected_weight_solution.json

## Selected Objective

- Selected trial: 0
- Objective score: 0.9616
- Stability Jaccard mean: 0.5739

