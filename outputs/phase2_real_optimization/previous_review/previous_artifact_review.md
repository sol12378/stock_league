# Previous Artifact Review

- Previous source: `work/previous_phase2_weight_optimization/phase2_weight_optimization`
- Previous trial count: 906

## Previous algorithm breakdown
| algorithm | count |
| --- | --- |
| random_search | 495 |
| optuna_tpe_proxy | 270 |
| nsga2_proxy | 135 |
| baseline | 6 |

## Previous selected weights
```json
{
  "bm": 0.14285714285714285,
  "distress": 0.14285714285714285,
  "ep": 0.14285714285714285,
  "gp": 0.14285714285714285,
  "liquidity": 0.14285714285714285,
  "piotroski": 0.14285714285714285,
  "sloan": 0.14285714285714285
}
```

## Previous Top20
| rank | code | company_name | sector | exploratory_weighted_score |
| --- | --- | --- | --- | --- |
| 1 | 1909 | Nippon Dry-Chemical CO.,LTD. | Machinery | 1.0 |
| 2 | 6745 | HOCHIKI CORPORATION | Electric Appliances | 0.9930546992801544 |
| 3 | 9507 | Shikoku Electric Power Company,Incorporated | Electric Power and Gas | 0.9907385986691828 |
| 4 | 6676 | BUFFALO INC. | Electric Appliances | 0.989631150909353 |
| 5 | 9505 | Hokuriku Electric Power Company | Electric Power and Gas | 0.9808686862174972 |
| 6 | 4022 | Rasa Industries,Ltd. | Chemicals | 0.9759891355407208 |
| 7 | 7803 | Bushiroad Inc. | Other Products | 0.9725995266891962 |
| 8 | 9533 | TOHO GAS CO.,LTD. | Electric Power and Gas | 0.9722015287354908 |
| 9 | 6440 | JUKI CORPORATION | Machinery | 0.9708271397604272 |
| 10 | 9024 | SEIBU HOLDINGS INC. | Land Transportation | 0.9673455494073137 |
| 11 | 6039 | Japan Animal Referral Medical Center Co.,Ltd. | Services | 0.962584402768053 |
| 12 | 6454 | MAX CO.,LTD. | Machinery | 0.9559816690684728 |
| 13 | 6418 | JAPAN CASH MACHINE CO.,LTD. | Machinery | 0.9543066002969866 |
| 14 | 8037 | KAMEI CORPORATION | Wholesale Trade | 0.9536002039457776 |
| 15 | 1333 | Umios Corporation | Fishery, Agriculture and Forestry | 0.9522056035347018 |
| 16 | 7211 | MITSUBISHI MOTORS CORPORATION | Transportation Equipment | 0.9518360579845132 |
| 17 | 3089 | Techno Alpha Co.,Ltd. | Wholesale Trade | 0.9512402383809788 |
| 18 | 7419 | Nojima Co.,Ltd. | Retail Trade | 0.9499852418669448 |
| 19 | 2220 | KAMEDA SEIKA CO.,LTD. | Foods | 0.9491678406580084 |
| 20 | 9993 | YAMAZAWA CO.,LTD. | Retail Trade | 0.9488343882792512 |

## Phase1 Top5 weighted rank
| code | company_name | phase1_top5_order | weighted_rank | weighted_score | in_top20 | in_top50 | in_top100 | in_top300 | in_top500 | in_top1000 | reason_if_rank_low |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1 | 29 | 0.9381576075875258 | False | True | True | True | True | True |  |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 2 | 36 | 0.9267636322084843 | False | True | True | True | True | True |  |
| 6430 | DAIKOKU DENKI CO.,LTD. | 3 | 171 | 0.8603051401950285 | False | False | False | True | True | True |  |
| 7803 | Bushiroad Inc. | 4 | 7 | 0.9725995266891962 | True | True | True | True | True | True |  |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 5 | 51 | 0.9126433288405428 | False | False | True | True | True | True |  |

## Previous Top1000 / Top1200 metrics
| n | phase1_top5_count | phase1_rank_score | bm_median | ep_median | gp_median | piotroski_median | sloan_median | adv60_median | distress_flag_rate | anomaly_flag_rate | review_flag_rate | missingness_mean | sector_hhi | max_sector_share | market_bm_median | market_ep_median | market_gp_median | market_piotroski_median | market_sloan_median | market_adv60_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1000.0 | 5.0 | 0.9813428018076178 | 1.0493248226897331 | 0.096450026656984 | 0.3061734928746401 | 0.8333333333333334 | -0.0397902214670448 | 133824941.66666666 | 0.0 | 0.002 | 0.0 | 0.008 | 0.0753779999999999 | 0.137 | 0.876644137710109 | 0.0734587712370457 | 0.2568928398457142 | 0.6666666666666666 | -0.0191435874904972 | 70807621.66666667 |
| 1200.0 | 5.0 | 0.9813428018076178 | 1.0288056577268805 | 0.0937574298652524 | 0.2985567662023741 | 0.8333333333333334 | -0.0379292088942671 | 127077573.33333334 | 0.0 | 0.0016666666666666 | 0.0 | 0.0084722222222222 | 0.0744694444444444 | 0.1275 | 0.876644137710109 | 0.0734587712370457 | 0.2568928398457142 | 0.6666666666666666 | -0.0191435874904972 | 70807621.66666667 |

## Previous stability Jaccard

- Mean Top300 Jaccard: 0.5739095747534582

## Previous problems
- Optuna TPE / NSGA-II proxy疑惑
- trial数不足
- single snapshotのみ
- Top1200の検証不足
- Gross Profitability欠損上位銘柄のreview不足
- stabilityが強固ではない
- equal weightの解釈注意

## Fixes in this run
- 実際に `optuna.samplers.TPESampler` を使って5,000 trialsを実行する。
- 実際に `optuna.samplers.NSGAIISampler` を使って3,000 trialsを実行する。
- TopN候補群サイズを制約付きutilityで比較する。
- GP欠損review flagとGP欠損ペナルティを明示的に入れる。
- stability、normalization sensitivity、missing handling sensitivityを拡張する。
