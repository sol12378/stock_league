# Phase2 To Phase3 Handoff Top1200

## 正式候補群
Top1200をPhase2 optimized candidate universeとして採用する。

## 使い分け
- Top100: 優先確認
- Top300: 重点候補
- Top1200: 正式候補宇宙
- Top2000: 取りこぼし確認用参照群

## Phase1 Top5
| code | company_name | phase1_top5_order | weighted_rank | weighted_score | in_top100 | in_top300 | in_top1000 | in_top1200 | in_selected_topn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1 | 46 | 0.9545126937979272 | True | True | True | True | True |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 2 | 355 | 0.9085700636774872 | False | False | True | True | True |
| 6430 | DAIKOKU DENKI CO.,LTD. | 3 | 72 | 0.9463890451018464 | True | True | True | True | True |
| 7803 | Bushiroad Inc. | 4 | 75 | 0.9461874584572638 | True | True | True | True | True |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 5 | 136 | 0.932935039428618 | False | True | True | True | True |

## Normalization categories
- normalization core: 1024
- normalization robust: 1320
- normalization fragile: 29

## GP missing review
_No rows._

## Phase3で見るべきテーマ列 placeholder
- future_moat_theme
- transformation_moat_theme
- business_change_evidence
- primary_research_note
- final_phase3_review_decision

## Phase3実装への入力ファイル一覧
- top1200_final/phase2_optimized_top1200_candidates.csv
- rankings/final_weighted_top2000_reference.csv
- consensus/normalization_consensus_table.csv
- walk_forward/walk_forward_results.csv
