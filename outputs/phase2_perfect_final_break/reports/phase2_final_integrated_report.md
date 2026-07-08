
# Phase2 Final Integrated Report

## Phase2の正式定義

Phase2は、Phase1で採用した先行研究式の定義を変えず、式の使い方を最適化する段階である。Phase1で守ったものはB/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、simple distress guardrail、Liquidity、Anomaly Review、独自重み付き式を正式採用しない思想である。

Phase2で破ったものは、固定された閾値、固定された候補数、固定された正規化方式、単一の分位基準、単一時点だけの候補評価、式の適用方法である。Phase1式そのものの定義、バフェット型のValue x Quality x Safety思想、金融業除外、Distress hard exclude、Phase2にFuture MoatやAIテーマを入れないこと、将来リターン最大化を主目的にしないことは破っていない。

## Top1200 / Top2000

utility_selected_topn = 2000。formal_selected_topn = 1200。Top2000は幅を評価するutility上の参照群であり、正式候補群ではない。Top1200は、広さ、品質、安全性、流動性、業種分散、解釈可能性、Phase3 review burdenを総合して正式採用したbalanced universeである。

## Formal Top1200 Audit

| metric | value |
| --- | --- |
| formal_top1200_count | 1200 |
| phase1_top5_coverage | 5/5 |
| financial_count | 0 |
| distress_count | 0 |
| negative_equity_count | 0 |
| anomaly_flag_count | 0 |
| gp_proxy_or_unverified_count | 32 |
| phase2_review_required_count | 637 |
| phase3_review_required_count | 840 |
| normalization_core_count | 970 |
| normalization_robust_count | 1135 |
| normalization_fragile_count | 29 |
| outlier_sensitive_count | 622 |
| sector_hhi | 0.07067777777777777 |
| max_sector_share | 0.11583333333333333 |
| anomaly_flags_standardized | True |
| top1200_flag_all_true | True |
| top2000_reference_flag_all_true | True |

## Walk-forward Disclosure

本成果物ではpoint-in-time panelとfixed-weight out-of-time validationを実施した。true walk-forward optimizationは、十分な複数foldが不足しているため未完了である。本成果物は将来リターン予測力を主張するものではない。

## Phase3 Handoff

Phase3 review flagsは除外理由ではない。Phase3で変わるMoat・生まれるMoatを評価する際の追加確認論点である。
