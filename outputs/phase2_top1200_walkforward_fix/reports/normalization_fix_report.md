# Normalization Fix Report

## 前回の問題4
前回は正規化方式によってTopN候補群が揺れ、特にwinsorized z-scoreでTop1200 Jaccardが低かった。

## なぜ揺れるのか
会計指標には極端値、業種差、欠損、規模差があり、percentileとz-scoreでは順位の意味が変わるためである。

## 採用方針
- market_percentile: 主基準
- sector_percentile: 業種補正確認
- robust_zscore: 外れ値に強い頑健性確認
- winsorized_zscore: 外れ値感度確認

## Consensus tag
4方式中3方式以上でTop1200ならnormalization core、2方式以上ならrobust、marketのみならfragileとした。

## Summary
| metric | value |
| --- | --- |
| normalization_core_count | 1024 |
| normalization_robust_count | 1320 |
| normalization_fragile_count | 29 |
| sector_adjusted_candidate_count | 181 |
| outlier_sensitive_count | 1338 |

## Phase3での使い方
normalization core/robust候補を優先し、fragile/outlier-sensitive候補は財務原データと業種文脈を確認する。
