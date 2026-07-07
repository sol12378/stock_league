# Phase2 Top1200 Final Report

## 1. Phase2の目的
Phase1で使った先行研究式の定義は変更せず、重み・候補群サイズ・正規化方法・業種調整を検証し、Phase3で分析可能な候補宇宙を作る。

## 2. Phase2が「破」である理由
Phase1の式を尊重しながら、式の使い方を最適化・検証するためである。

## 3. なぜTop2000ではなくTop1200を正式採用するのか
utility最大化ではTop2000が最良となったが、Phase2の目的は候補数最大化ではない。Top1200はPhase1 Top5をすべて保持し、品質・安全性・流動性・業種分散・レビュー負荷のバランスが良い。

## 4. Top1200の指標品質
| group | count | phase1_top5_coverage | bm_median | ep_median | gross_profitability_median | piotroski_median | sloan_median | adv60_median | distress_flag_rate | review_flag_rate | anomaly_flag_rate | gp_missing_rate | sector_hhi | max_sector_share | bm_vs_market | ep_vs_market | gp_vs_market | piotroski_vs_market | sloan_vs_market | adv60_vs_market_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Top1200 formal | 1200 | 5 | 0.9045357199503644 | 0.0755058109581445 | 0.2568928398457142 | 0.8333333333333334 | -0.0231891727365511 | 346844199.1666667 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0706777777777777 | 0.1158333333333333 | 0.0278915822402554 | 0.0020470397210988 | 0.0 | 0.1666666666666667 | 0.0040455852460539 | 4.898402050551385 |
| Top1000 comparison | 1000 | 5 | 0.913457024485372 | 0.0763055071156095 | 0.2637640230120129 | 0.8333333333333334 | -0.024455499001728 | 403915315.8333334 | 0.0 | 0.0 | 0.0 | 0.0 | 0.071408 | 0.127 | 0.0368128867752631 | 0.0028467358785638 | 0.0068711831662987 | 0.1666666666666667 | 0.0053119115112308 | 5.704404502311934 |
| Top2000 reference | 2000 | 5 | 0.8930095162465346 | 0.0764263385225859 | 0.2619677570273768 | 0.8333333333333334 | -0.0193089041834703 | 141704676.66666666 | 0.0 | 0.0 | 0.0005 | 0.0 | 0.0762259999999999 | 0.13 | 0.0163653785364256 | 0.0029675672855402 | 0.0050749171816626 | 0.1666666666666667 | 0.0001653166929731 | 2.0012630467063888 |
| Market universe | 3099 | 5 | 0.876644137710109 | 0.0734587712370457 | 0.2568928398457142 | 0.6666666666666666 | -0.0191435874904972 | 70807621.66666667 | 0.0593739916101968 | 0.1181026137463698 | 0.143272023233301 | 0.0183930300096805 | 0.0825559588333827 | 0.1610196837689577 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |

## 5. Top1200の業種分散
Sector HHI: 0.0707

## 6. Phase1 Top5保持状況
| code | company_name | phase1_top5_order | weighted_rank | weighted_score | in_top100 | in_top300 | in_top1000 | in_top1200 | in_selected_topn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1 | 46 | 0.9545126937979272 | True | True | True | True | True |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 2 | 355 | 0.9085700636774872 | False | False | True | True | True |
| 6430 | DAIKOKU DENKI CO.,LTD. | 3 | 72 | 0.9463890451018464 | True | True | True | True | True |
| 7803 | Bushiroad Inc. | 4 | 75 | 0.9461874584572638 | True | True | True | True | True |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 5 | 136 | 0.932935039428618 | False | True | True | True | True |

## 7. Walk-forward実施結果
Walk-forward level: Level 2. 詳細は reports/walk_forward_report_final.md を参照。

## 8. 正規化方式感度への対応
market percentileを主基準とし、sector percentile、robust z-score、winsorized z-scoreでconsensus tagを付けた。

## 9. Normalization consensus
core=1024, robust=1320, fragile=29

## 10. Phase3への接続
Top100は優先確認、Top300は重点候補、Top1200は正式候補宇宙、Top2000は取りこぼし参照群として使う。

## 11. 限界
Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。将来リターン最大化モデルでもない。

## 12. レポート本文に使える要約文
utility最大化ではTop2000が最良となったが、Phase3で分析可能な候補数、品質、安全性、流動性、業種分散、レビュー負荷のバランスを考慮し、Top1200をPhase2 optimized candidate universeとして採用した。
