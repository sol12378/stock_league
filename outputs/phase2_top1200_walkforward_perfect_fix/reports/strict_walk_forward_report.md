
# Strict Walk-forward Report

## 実施内容

この成果物では、単一時点スナップショットではなく、EDINET提出日ベースのpoint-in-time historical panelから年度別foldを作成しました。
各foldは、test fiscal yearより前の年度をtrain候補、当該年度をtest候補として分離しています。

## Fold Results

| fold_test_availability_year | test_availability_start | test_availability_end | train_row_count | train_ready_count | test_row_count | test_ready_count | top1200_count | top1200_ready_rate | top1200_gross_profit_direct_rate | top1200_future_return_252d_available_rate | top1200_future_return_252d_mean | top1200_future_return_252d_median | top1200_distress_flag_rate | top1200_feature_missing_review_rate | strict_train_test_separated | eligible_for_63d_validation | eligible_for_126d_validation | eligible_for_252d_validation | claim_level |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 2023-01-01 00:00:00 | 2023-12-31 23:59:59 | 1 | 1 | 2673 | 2263 | 1200 | 0.8441666666666666 | 0.8858333333333334 | 1.0 | 0.2423478198104786 | 0.1889970662760112 | 0.0016666666666666668 | 0.15583333333333332 | True | False | False | False | strict point-in-time availability-year walk-forward panel; statistical power limited by available years and target maturity |
| 2024 | 2024-01-01 00:00:00 | 2024-12-31 23:59:59 | 2674 | 2264 | 3573 | 3055 | 1200 | 0.8525 | 0.8791666666666667 | 1.0 | 0.10716172224019425 | 0.041670467045575865 | 0.0025 | 0.14666666666666667 | True | True | True | True | strict point-in-time availability-year walk-forward panel; statistical power limited by available years and target maturity |
| 2025 | 2025-01-01 00:00:00 | 2025-12-31 23:59:59 | 6247 | 5319 | 3583 | 3052 | 1200 | 0.8683333333333333 | 0.8866666666666667 | 0.1375 | 0.3261282859815095 | 0.25848700270004765 | 0.0016666666666666668 | 0.13083333333333333 | True | True | True | False | strict point-in-time availability-year walk-forward panel; statistical power limited by available years and target maturity |

## Fold Definitions

| fold_test_availability_year | train_availability_years | test_availability_year | test_availability_start | test_availability_end | train_fiscal_years_present | test_fiscal_years_present | train_available_date_max | test_available_date_min | test_available_date_max | strict_train_test_separated | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 2022 | 2023 | 2023-01-01 00:00:00 | 2023-12-31 23:59:59 | 2021 | 2022,2023 | 2022-03-30 13:43:00 | 2023-03-23 15:09:00 | 2023-12-28 16:42:00 | True | Rows are assigned by EDINET submit_date availability year, not fiscal year. No facts submitted after the test window starts are used for training. |
| 2024 | 2022,2023 | 2024 | 2024-01-01 00:00:00 | 2024-12-31 23:59:59 | 2021,2022,2023 | 2023,2024 | 2023-12-28 16:42:00 | 2024-01-04 14:15:00 | 2024-12-27 16:01:00 | True | Rows are assigned by EDINET submit_date availability year, not fiscal year. No facts submitted after the test window starts are used for training. |
| 2025 | 2022,2023,2024 | 2025 | 2025-01-01 00:00:00 | 2025-12-31 23:59:59 | 2021,2022,2023,2024 | 2024,2025 | 2024-12-27 16:01:00 | 2025-01-06 11:55:00 | 2025-12-26 16:34:00 | True | Rows are assigned by EDINET submit_date availability year, not fiscal year. No facts submitted after the test window starts are used for training. |

## 解釈

`strict_walk_forward_ready` は、財務ファクト、価格結合、主要特徴量が同時に揃った行を示します。
`future_return_252d_available_rate` は、検証ターゲットとして252営業日先リターンが観測できる割合です。
fold数や初期年度のtrain件数が限られる場合、これはモデルの将来予測力を強く主張するものではなく、look-aheadを避けた検証データ基盤の構築結果として扱います。
