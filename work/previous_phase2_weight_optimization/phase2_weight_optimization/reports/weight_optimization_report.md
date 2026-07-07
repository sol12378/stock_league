# BEYOND BUFFETT Phase2 Weight Optimization Experiment

## 1. 実験の目的
Phase1で使った先行研究式・会計ファイナンス指標を、探索目的の **Exploratory Weighted Buffett Score** として一度だけ重み付けし、Phase3候補探索に使える感度情報を作る。

## 2. Phase1正式ルールとの違い
Phase1は独自の重み付き総合式を避け、段階的スクリーニングと逐次タイブレークでBuffett Core Top5を選んだ。本実験はその置き換えではなく、相対的重要度の確認である。

## 3. なぜ重み付き式を正式採用しないのか
重み付き式は欠損処理、正規化、探索目的の設計に結果が左右される。説明責任の観点ではPhase1の段階ルールより弱く、過去データやPhase1 Top5に過剰適合するリスクがある。

## 4. 重み最適化を行う理由
Phase3で見るべき候補範囲、感度の高い指標、Phase1 Top5の頑健性、業種偏りを検査するためである。

## 5. 使用指標
B/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、simple distress safety proxy、60日平均売買代金、anomaly/microcap/one-time profit/missingness penalties。

## 6. 正規化方法
主実験は market_percentile。補助表として sector_percentile を保存した。Sloan Accrualsは低いほど良いので反転し、欠損は中央値補完とmissingness_penaltyで扱った。

## 7. 重み探索方法
baseline 6種類と、Dirichlet/一様乱数による軽量な deterministic proxy search を実行した。仕様上のRandom Search 5,000、Optuna 3,000、NSGA-II 2,000のフル実行ではなく、監査可能な成果物生成を優先した軽量版である。

## 8. 最適化目的
Phase1 Top5 retention、quality preservation、value discipline、distress control、liquidity adequacy、sector diversity、stability、interpretabilityを合成したメタ目的関数を使った。将来リターン最大化は目的にしていない。

## 9. 最良重み
| metric | weight |
| --- | --- |
| bm | 0.14285714285714285 |
| distress | 0.14285714285714285 |
| ep | 0.14285714285714285 |
| gp | 0.14285714285714285 |
| liquidity | 0.14285714285714285 |
| piotroski | 0.14285714285714285 |
| sloan | 0.14285714285714285 |
| penalty_anomaly | 0.12 |
| penalty_microcap | 0.1 |
| penalty_missing | 0.08 |
| penalty_onetime | 0.1 |

Selected objective score: 0.9616

## 10. 重みの解釈
選ばれた重みはPhase2の探索条件下で、価値・品質・安全性・流動性のバランスを取ったものとして読む。これは正式な銘柄選定式ではない。

## 11. TopN特徴
| n | phase1_top5_count | bm_median | ep_median | gp_median | piotroski_median | sloan_median | adv60_median | sector_hhi | distress_flag_rate | anomaly_flag_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20.0 | 1.0 | 1.5466706390985356 | 0.2023942087260601 | 0.3007354667715296 | 1.0 | -0.0549501782283989 | 622245021.7585245 | 0.11 | 0.0 | 0.0 |
| 50.0 | 3.0 | 1.440916090202303 | 0.1774698838194121 | 0.3090120438363092 | 1.0 | -0.0571293978759983 | 352741780.0 | 0.092 | 0.0 | 0.0 |
| 100.0 | 4.0 | 1.427323545646951 | 0.1492082270801946 | 0.3183233608648727 | 1.0 | -0.055730496056813 | 221121963.33333337 | 0.0786 | 0.0 | 0.0 |
| 300.0 | 5.0 | 1.2562121064190146 | 0.117724934757094 | 0.333054301827232 | 0.8333333333333334 | -0.0485606349420886 | 192389017.5 | 0.0854222222222222 | 0.0 | 0.0 |
| 500.0 | 5.0 | 1.172216237346897 | 0.1063640503014939 | 0.3148975860557507 | 0.8333333333333334 | -0.0447279152403076 | 185677559.1666667 | 0.0774639999999999 | 0.0 | 0.002 |
| 1000.0 | 5.0 | 1.0493248226897331 | 0.096450026656984 | 0.3061734928746401 | 0.8333333333333334 | -0.0397902214670448 | 133824941.66666666 | 0.0753779999999999 | 0.0 | 0.002 |
| 1200.0 | 5.0 | 1.0288056577268805 | 0.0937574298652524 | 0.2985567662023741 | 0.8333333333333334 | -0.0379292088942671 | 127077573.33333334 | 0.0744694444444444 | 0.0 | 0.0016666666666666 |
| 1500.0 | 5.0 | 1.004455773715585 | 0.0900216065893063 | 0.286756856393045 | 0.8333333333333334 | -0.0345615120448774 | 122016252.5 | 0.0756195555555555 | 0.0 | 0.004 |

## 12. Phase1 Top5の順位
| code | company_name | phase1_top5_order | weighted_rank | weighted_score | in_top20 | in_top50 | in_top100 | in_top300 | in_top500 | in_top1000 | reason_if_rank_low |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1 | 29 | 0.9381576075875258 | False | True | True | True | True | True |  |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 2 | 36 | 0.9267636322084843 | False | True | True | True | True | True |  |
| 6430 | DAIKOKU DENKI CO.,LTD. | 3 | 171 | 0.8603051401950285 | False | False | False | True | True | True |  |
| 7803 | Bushiroad Inc. | 4 | 7 | 0.9725995266891962 | True | True | True | True | True | True |  |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 5 | 51 | 0.9126433288405428 | False | False | True | True | True | True |  |

## 13. 業種偏り
Top1000 sector HHIは 0.0754。Top100/300/1000の業種構成図を figures/sector_distribution_top100_top300_top1000.png に保存した。

## 14. DistressやAnomalyの混入状況
Top1000 distress flag rateは 0.0000、anomaly flag rateは 0.0020。

## 15. Stability結果
Top300 bootstrap/noise Jaccard平均は 0.5739。

## 16. Phase3へどう使うか
Weighted Top100は優先レビュー、Top300は候補母集団、Top1000は感度確認用として使う。Phase1 Top5と重なる候補は、Phase1の説明可能性とPhase2の指標感度が両立する候補として扱う。

## 17. 限界
単一時点データに依存し、フルOptuna/NSGA-IIではない。欠損処理と正規化方式で順位は変わり得る。Phase3では事業内容、競争優位、テーマ仮説、財務注記を必ず定性確認する。

## Top20
| rank | code | company_name | sector | exploratory_weighted_score |
| --- | --- | --- | --- | --- |
| 1 | 1909 | Nippon Dry-Chemical CO.,LTD. | Machinery | 1.0 |
| 2 | 6745 | HOCHIKI CORPORATION | Electric Appliances | 0.9930546992801543 |
| 3 | 9507 | Shikoku Electric Power Company,Incorporated | Electric Power and Gas | 0.9907385986691828 |
| 4 | 6676 | BUFFALO INC. | Electric Appliances | 0.989631150909353 |
| 5 | 9505 | Hokuriku Electric Power Company | Electric Power and Gas | 0.9808686862174971 |
| 6 | 4022 | Rasa Industries,Ltd. | Chemicals | 0.9759891355407208 |
| 7 | 7803 | Bushiroad Inc. | Other Products | 0.9725995266891962 |
| 8 | 9533 | TOHO GAS CO.,LTD. | Electric Power and Gas | 0.9722015287354908 |
| 9 | 6440 | JUKI CORPORATION | Machinery | 0.9708271397604273 |
| 10 | 9024 | SEIBU HOLDINGS INC. | Land Transportation | 0.9673455494073137 |
| 11 | 6039 | Japan Animal Referral Medical Center Co.,Ltd. | Services | 0.962584402768053 |
| 12 | 6454 | MAX CO.,LTD. | Machinery | 0.9559816690684729 |
| 13 | 6418 | JAPAN CASH MACHINE CO.,LTD. | Machinery | 0.9543066002969866 |
| 14 | 8037 | KAMEI CORPORATION | Wholesale Trade | 0.9536002039457776 |
| 15 | 1333 | Umios Corporation | Fishery, Agriculture and Forestry | 0.9522056035347018 |
| 16 | 7211 | MITSUBISHI MOTORS CORPORATION | Transportation Equipment | 0.9518360579845133 |
| 17 | 3089 | Techno Alpha Co.,Ltd. | Wholesale Trade | 0.9512402383809789 |
| 18 | 7419 | Nojima Co.,Ltd. | Retail Trade | 0.9499852418669448 |
| 19 | 2220 | KAMEDA SEIKA CO.,LTD. | Foods | 0.9491678406580083 |
| 20 | 9993 | YAMAZAWA CO.,LTD. | Retail Trade | 0.9488343882792512 |

