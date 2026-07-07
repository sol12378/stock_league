# Phase3 Handoff From Weight Experiment

## Weighted Top100 / Top300 / Top1000の使い方
Weighted Top100は優先的に定性確認する候補群、Top300はPhase3候補母集団、Top1000は指標感度確認の参照母集団として使う。

## Phase1 Top5との整合性
| code | company_name | phase1_top5_order | weighted_rank | weighted_score | in_top20 | in_top50 | in_top100 | in_top300 | in_top500 | in_top1000 | reason_if_rank_low |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1 | 29 | 0.9381576075875258 | False | True | True | True | True | True |  |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 2 | 36 | 0.9267636322084843 | False | True | True | True | True | True |  |
| 6430 | DAIKOKU DENKI CO.,LTD. | 3 | 171 | 0.8603051401950285 | False | False | False | True | True | True |  |
| 7803 | Bushiroad Inc. | 4 | 7 | 0.9725995266891962 | True | True | True | True | True | True |  |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 5 | 51 | 0.9126433288405428 | False | False | True | True | True | True |  |

## 重み最適化で上位に来たがreviewが必要な企業
_No rows._

## 生まれるMoat・変わるMoat分析で優先すべき候補
Top100のうち、価値・品質・流動性が同時に高い企業を優先する。Phase1 Top5と重なる企業は説明可能性と感度の両面で確認する。

## Phase3で除外確認すべき企業
distress_review_flag、anomaly_flags、one_time_profit_suspected、microcap_flag、missingness_penaltyが高い企業は、事業内容と財務注記を確認してから採用可否を判断する。
