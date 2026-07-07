# Previous Result Review

- utility最大化ではTop2000が最良だった。
- Top2000 utility: 0.7872
- Top1200 utility rank: 3
- Top1200 utility: 0.7100
- Top1200はutility 3位程度ではない場合でも、Phase3候補宇宙としてdefensibleだった。
- Top1200 Phase1 Top5 coverage: 5/5
- Top1200 distress flag rate: 0.0000
- Top1200 review flag rate: 0.0000
- Top1200 anomaly flag rate: 0.0000
- Top1200 GP missing rate: 0.0000

## Top1000 / Top1200 / Top2000 comparison
| topn | topn_utility | phase1_top5_count | gross_profitability_median | sector_hhi | anomaly_flag_rate | gp_missing_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 1000.0 | 0.6905197971084692 | 5.0 | 0.2637640230120129 | 0.071408 | 0.0 | 0.0 |
| 1200.0 | 0.7099681670692758 | 5.0 | 0.2568928398457142 | 0.0706777777777777 | 0.0 | 0.0 |
| 2000.0 | 0.787241932596777 | 5.0 | 0.2619677570273768 | 0.0762259999999999 | 0.0005 | 0.0 |

## 今回の修正
- Top2000は広すぎるため、Phase3分析対象としてはレビュー負荷が大きい。
- 正式候補群はTop1200に調整する。
- Walk-forward未実施または不十分だった点を、利用可能データでLevel 2 snapshot proxyとして補強する。
- 正規化方式によって候補群が揺れていた点をnormalization consensusで補正する。
