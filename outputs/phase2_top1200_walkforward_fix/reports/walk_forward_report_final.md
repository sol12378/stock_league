# Walk-forward Report Final

## 実施Level
Level 2

## 使用した年度・期間
[2023, 2024, 2025]

## train/test設計
Level 2では年度別snapshotを作り、submit_dateを利用可能日として扱った。submit_dateがない場合はfiscal_year_end + 120日proxyを使う設計である。

## look-aheadを避けるための処理
価格は利用可能日以前の直近日次価格を使った。ただし、完全な開示日ベースの再計算ではない。

## 結果
| walk_forward_level | fiscal_year | train_period | test_period | top1200_feasible | candidate_count | bm_median_vs_market | ep_median_vs_market | gross_profitability_median_vs_market | piotroski_ratio_median_vs_market | sloan_accruals_median_vs_market | adv60_median_vs_market_ratio | distress_flag_rate | review_flag_rate | anomaly_flag_rate | gp_missing_rate | sector_hhi | max_sector_share | top1200_jaccard_with_previous_fold | selected_weight_drift | normalization_consensus_retention | optional_future_return | optional_future_volatility | optional_future_max_drawdown | lookahead_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Level 2 | 2023 | previous available fiscal snapshots as proxy; no re-optimization | 2023 | True | 1200 | 0.0477970119949234 | 0.0050479873348535 | 0.0292234330629962 | 0.1666666666666666 | 0.0013879875198605 | 7.348840371069029 | 0.0 | 0.7925 | 0.0075 | 0.0158333333333333 | 0.0756291666666666 | 0.1608333333333333 |  | 0.0 |  |  |  |  | submit_date used when available; otherwise fiscal_year_end + 120 days proxy. Gross Profitability original formula unavailable in raw panel, so operating_income/total_assets proxy is used. |
| Level 2 | 2024 | previous available fiscal snapshots as proxy; no re-optimization | 2024 | True | 1200 | 0.0648928387694086 | 0.0066570112349917 | 0.0271503085835176 | 0.0 | 2.69637942018619e-06 | 9.222298346367158 | 0.0 | 0.7883333333333333 | 0.0025 | 0.0183333333333333 | 0.0684999999999999 | 0.1425 | 0.6442769019876627 | 0.0 |  |  |  |  | submit_date used when available; otherwise fiscal_year_end + 120 days proxy. Gross Profitability original formula unavailable in raw panel, so operating_income/total_assets proxy is used. |
| Level 2 | 2025 | previous available fiscal snapshots as proxy; no re-optimization | 2025 | True | 1200 | 0.099379335374557 | 0.0073182596774378 | 0.0248674499900217 | 0.0 | 0.0027926477120103 | 7.903063718204078 | 0.0 | 0.7883333333333333 | 0.005 | 0.0233333333333333 | 0.0682611111111111 | 0.1491666666666666 | 0.7209469153515065 | 0.0 |  |  |  |  | submit_date used when available; otherwise fiscal_year_end + 120 days proxy. Gross Profitability original formula unavailable in raw panel, so operating_income/total_assets proxy is used. |

## 限界
本データには複数年度のlook-ahead-safeな完全財務スナップショットが不足していたため、厳密なFull Walk-forward validationではなくLevel 2 snapshot proxyとして実施した。

将来リターン最大化や予測力は主張しない。候補群構成ルールの時間的頑健性を参考確認したものである。
