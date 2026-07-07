# Phase2 Real Optimization Report

## 1. Phase2の目的
Phase1で使った先行研究式の定義を変えず、式の使い方、重み、候補群サイズ、欠損処理、業種調整を検証する。

## 2. Phase1との違い
Phase1は「守」であり、独自重み付き総合式なしの段階スクリーニングだった。Phase2は「破」として、式そのものではなく適用条件を比較した。

## 3. Phase2が「破」である理由
既存式を尊重しながら、Optuna TPEとNSGA-IIで条件空間を探索し、TopNや欠損処理の妥当性を反証可能な形で調べた。

## 4. 式そのものは変えていない
B/M、E/P、Gross Profitability、Piotroski、Sloan、distress safety proxy、liquidityというPhase1由来の式・指標を用いた。

## 5. 変えたもの
重み、適用条件、候補群サイズ、欠損処理、業種調整、GP欠損ペナルティ、concentration penalty。

## 6. AIは銘柄を直接選んでいない
AI/Optunaは式の使い方を比較・検証した。銘柄の最終採用判断はPhase3の定性確認に残す。

## 7. Optuna TPE
`optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)` で 5000 trialsを実行した。

## 8. NSGA-II
`optuna.samplers.NSGAIISampler(seed=43, population_size=100)` で 3000 trialsを実行した。

## 9. Top1200検証結果
top1200_is_optimal=False, top1200_is_defensible=True, selected_topn=2000。

## 10. Phase1 Top5との整合性
| code | company_name | phase1_top5_order | weighted_rank | weighted_score | in_top100 | in_top300 | in_top1000 | in_top1200 | in_selected_topn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1 | 46 | 0.9545126937979272 | True | True | True | True | True |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 2 | 355 | 0.9085700636774872 | False | False | True | True | True |
| 6430 | DAIKOKU DENKI CO.,LTD. | 3 | 72 | 0.9463890451018464 | True | True | True | True | True |
| 7803 | Bushiroad Inc. | 4 | 75 | 0.9461874584572638 | True | True | True | True | True |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 5 | 136 | 0.932935039428618 | False | True | True | True | True |

## 11. Phase3への接続
Top100は優先定性確認、Top300は候補深掘り、Top1200はPhase2 candidate universe、Top1500は感度参照として使う。

## 12. 限界
walk-forwardは単一スナップショット制約により未実施。将来リターン最大化モデルではない。

## 13. 採用推奨
Exploratory Weighted Buffett ScoreはPhase3候補探索・review flag管理・TopN根拠作りに限定して採用する。

## 14. レポート本文に貼れる要約
本実験では、Phase1の先行研究式を変更せず、Optuna TPEとNSGA-IIにより重み・欠損処理・業種調整・候補群サイズを探索した。得られたスコアは正式なBuffett Scoreではなく、Phase3の候補探索を支援するExploratory Weighted Buffett Scoreである。

## Selected weights
| metric | weight |
| --- | --- |
| bm | 0.18445915574257452 |
| distress | 0.2506101343460851 |
| ep | 0.05724894173929047 |
| gp | 0.14717910156895553 |
| liquidity | 0.33011280681347804 |
| piotroski | 0.009821470657685773 |
| sloan | 0.020568389131930525 |

## Selected penalties
| penalty | weight |
| --- | --- |
| anomaly | 0.29713500327930653 |
| microcap | 0.19871292956780232 |
| missing | 0.25850377194395013 |
| onetime | 0.1949619853730527 |
