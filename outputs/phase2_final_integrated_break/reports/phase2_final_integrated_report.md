
# Phase2 Final Integrated Report

## 1. Phase2の目的

Phase2は、Phase1の先行研究式を守りながら、式の使い方を破る段階である。式の定義ではなく、重み、正規化、候補数、業種調整、欠損処理、時点外検証を最適化し、Phase3で変わるMoat・生まれるMoatを評価するための候補宇宙を構築する。

## 2. Phase1からの接続

Phase1の式はB/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、simple distress guardrail、Liquidity、Anomaly Reviewである。Phase2ではこれらの定義を変更していない。

## 3. Phase2が「破」である理由

Phase2で変えたものは、重み、候補数、正規化、欠損処理、業種調整、検証方法である。Future Moat、AIテーマ、Transformation Moat、中計テキストは導入していない。

## 4. Top1200正式採用

Formal Top1200 count: 1200。Phase1 Top5 coverage: 5/5。

Top2000は参照群であり、正式候補群ではない。Top2000 reference-only count: 800。

## 5. Financial / Distress Exclusion

金融業除外後の正式Top1200内financial count: 0。
distress hard exclude後の正式Top1200内distress count: 0。

## 6. Gross Profitability

Phase1およびPhase2正式候補群では、可能な限り売上総利益／総資産で定義されるGross Profitabilityを用いた。一方、過去年次パネルで売上総利益が直接取得できない場合は、収益性proxyを別名で扱い、原式とは区別した。

## 7. Normalization Consensus

| scope | metric | value |
| --- | --- | --- |
| formal_top1200 | normalization_core_count | 970 |
| formal_top1200 | normalization_robust_count | 1135 |
| formal_top1200 | normalization_fragile_count | 29 |
| formal_top1200 | sector_adjusted_candidate_count | 19 |

## 8. Point-in-time Panel / Fixed-weight Validation

EDINET提出日を基準にpoint-in-time panelを構築し、固定重みの時点外検証を実施した。

| availability_year | annual_top1200_count | strict_ready_count | strict_ready_rate | feature_missing_review_rate | gross_profitability_direct_rate | gross_profitability_proxy_rate | distress_flag_count | financial_count | sector_hhi | max_sector_share | phase1_top5_coverage | 252d_forward_return_eligible_count | optional_median_forward_return_252d | optional_volatility_forward_return_252d | optional_max_drawdown_proxy_252d | strict_ready_pool_count | strict_ready_top_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 1200 | 1009 | 0.8408333333333333 | 0.15916666666666668 | 0.9266666666666666 | 0.07333333333333333 | 0 | 0 | 0.06885833333333333 | 0.11916666666666667 |  | 1200 | 0.16062929680629207 | 0.4378751939330979 | -0.7855760882517475 | 2074 | 1200 |
| 2024 | 1200 | 998 | 0.8316666666666667 | 0.1675 | 0.9175 | 0.0825 | 0 | 0 | 0.06481666666666666 | 0.1075 |  | 1200 | 0.01873828784200885 | 0.38464472575611797 | -0.7613020357942815 | 2795 | 1200 |
| 2025 | 1200 | 997 | 0.8308333333333333 | 0.16833333333333333 | 0.9133333333333333 | 0.08666666666666667 | 0 | 0 | 0.06555555555555556 | 0.11416666666666667 |  | 215 | 0.2248034840684287 | 0.5680787032547954 | -0.5513413506012951 | 2803 | 1200 |

## 9. True Walk-forward Optimization

strict_true_walk_forward_completed = false。
本成果物ではpoint-in-time panelと固定重みの年度別検証を行った。完全なtrain/test型Walk-forward optimizationは、より長い過去年次パネルを構築した後に実施する。

## 10. Phase3 Handoff

Phase3ではTop100、Top300、Top1200、Top2000参照群を使い分ける。Phase3で初めてFuture Moat、changing moat、emerging moat、AI moat、business transformationを導入する。

## 11. 限界

本成果物は将来リターン最大化モデルではない。Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。point-in-time panel validationは候補群の時点外確認であり、予測力の証明ではない。
