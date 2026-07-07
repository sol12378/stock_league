# Phase1 Buffett Complete Report

## 1. Phase1の目的
Phase1は、公開データと先行研究ベースの式だけで、割安・高品質・安全・利益の質が高く、現実に売買可能な日本株20社を選ぶ「守」のポートフォリオを作る。

## 2. Buffett Proxy Portfolioの定義
Buffett本人の判断を完全再現するものではなく、良い会社を高すぎない価格で長期保有するという思想を、B/M、E/P、Gross Profitability、Piotroski available signal score、Sloan Accruals、distress guardrail、liquidity filterに落とし込んだ代理ポートフォリオである。

## 3. 独自式を避ける理由
Phase1ではMOAT係数式や独自重み付き総合スコアを使わない。レポート提出時に説明可能で、再現可能で、先行研究との対応が明確な式だけを使うためである。

## 4. 使用した先行研究式
ValueはFama-French型のB/MとBasu型のE/P、QualityはNovy-Marx型Gross Profitability、Financial StrengthはPiotroski available signal score、Earnings QualityはSloan Accrualsを使った。Ohlson/Altmanは原式入力不足のため未実装と明記し、代わりにsimple distress guardrailを使った。

## 5. 前回までの問題点
前回版はValueとQualityの実装は進んだが、提出用としてはbase/conservative/sector-adjustedの明確な3分類、業種集中の抑制、human review削減、READMEとscriptsの整合性確認が不足していた。

## 6. 今回の修正内容
入力監査、指標カバレッジ監査、異常値レビュー、3種類のfinal20、500万円配分、企業別採用理由、式リファレンス、限界、最終判定、zip化を追加した。

## 7. B/M・E/Pカバレッジ
B/Mカバレッジは 99.68%、E/Pカバレッジは 88.74% で、70%基準を満たす。欠損を平均値・中央値で補完していない。

## 8. Gross Profitability実装
Gross Profitabilityカバレッジは 98.16% で、Quality条件の中心として使った。小売に有利に出やすい可能性があるため、sector-adjusted版では業種制約を入れた。

## 9. Piotroski available signal score
9信号完全版ではないため、`Piotroski F-Score` ではなく `Piotroski available signal score` と表記する。available signal ratio >= 0.65 を基準にした。

## 10. Sloan Accruals
Sloan Accrualsは `(Net Income - Operating Cash Flow) / Average Total Assets` で計算し、悪い側上位30%を除外候補にした。

## 11. Distress guardrail
negative book equity、two-year net loss、OCF損失、営業赤字、高負債比率、低自己資本比率などを確認し、資本毀損リスクを抑えた。

## 12. Liquidity filter
60日平均売買代金を使い、300万円未満は除外、300万円以上1000万円未満はreview、1000万円以上をpassとした。正式採用候補ではpass銘柄を優先した。

## 13. Anomaly review
extreme_high_bm、extreme_high_ep、scale_check、market equity不整合、Gross Profitability極端値、Sloan極端値、distress、liquidity、microcap、一過性利益疑いを確認した。

## 14. Base / Conservative / Sector-adjusted の比較
| portfolio | company_count | overlap_with_base | overlap_with_conservative | overlap_with_sector_adjusted | sector_count | market_count | average_bm | average_ep | average_gross_profitability | average_piotroski_available_ratio | average_sloan_accruals | human_review_required_count | liquidity_review_count | distress_review_count | extreme_value_count | retail_trade_count | retail_trade_ratio | adoption_judgement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | 20 | 20 | 8 | 5 | 7 | 2 | 1.5927 | 0.1916 | 0.6797 | 0.8417 | -0.0368 | 12 | 10 | 0 | 1 | 13 | 65.00% | comparison_reference |
| conservative | 20 | 8 | 20 | 11 | 7 | 3 | 1.5301 | 0.1409 | 0.4628 | 0.8750 | -0.0228 | 0 | 0 | 0 | 0 | 13 | 65.00% | comparison_reference |
| sector_adjusted | 20 | 5 | 11 | 20 | 11 | 3 | 1.5055 | 0.1495 | 0.4128 | 0.8750 | -0.0308 | 0 | 0 | 0 | 0 | 4 | 20.00% | formal_phase1_recommended |

## 15. 最終採用する20社
最終採用推奨は sector-adjusted final20 である。Retail Tradeを5社以下に抑え、1業種上限を原則4社、必要時のみ5社に制約した。

| rank | code | company_name | sector | bm_raw | ep_raw | gross_profitability | piotroski_available_ratio | sloan_accruals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3539 | JM HOLDINGS CO.,LTD. | Retail Trade | 1.4261 | 0.2041 | 0.7349 | 1.0000 | -0.0021 |
| 2 | 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | Retail Trade | 1.4402 | 0.1743 | 0.7188 | 1.0000 | -0.0258 |
| 3 | 9990 | SAC'S BAR HOLDINGS INC. | Retail Trade | 1.4280 | 0.1230 | 0.6445 | 0.6667 | -0.0146 |
| 4 | 8278 | FUJI CO.,LTD. | Retail Trade | 1.3580 | 0.0976 | 0.6015 | 0.8333 | -0.0518 |
| 5 | 6430 | DAIKOKU DENKI CO.,LTD. | Machinery | 1.4680 | 0.2505 | 0.4661 | 0.6667 | 0.0010 |
| 6 | 7803 | Bushiroad Inc. | Other Products | 1.4416 | 0.2051 | 0.4014 | 1.0000 | -0.0443 |
| 7 | 9470 | GAKKEN HOLDINGS CO.,LTD. | Information & Communication | 1.5260 | 0.1215 | 0.3948 | 1.0000 | -0.0228 |
| 8 | 9274 | KPP GROUP HOLDINGS CO.,LTD. | Wholesale Trade | 1.3191 | 0.1223 | 0.3668 | 0.8333 | -0.0091 |
| 9 | 9507 | Shikoku Electric Power Company,Incorporated | Electric Power and Gas | 1.5211 | 0.2364 | 0.3593 | 1.0000 | -0.0284 |
| 10 | 6454 | MAX CO.,LTD. | Machinery | 1.4067 | 0.1490 | 0.3523 | 1.0000 | -0.0273 |
| 11 | 1873 | NIHON HOUSE HOLDINGS CO.,LTD. | Construction | 1.9059 | 0.1151 | 0.3468 | 1.0000 | -0.0495 |
| 12 | 2918 | WARABEYA NICHIYO HOLDINGS CO.,LTD. | Foods | 1.3484 | 0.1218 | 0.3336 | 0.6667 | -0.0898 |
| 13 | 6257 | FUJISHOJI CO.,LTD. | Machinery | 2.2487 | 0.1415 | 0.3322 | 0.6667 | -0.0319 |
| 14 | 4093 | Toho Acetylene Co.,Ltd. | Chemicals | 1.5268 | 0.1062 | 0.3262 | 0.6667 | -0.0242 |
| 15 | 6286 | SEIKO CORPORATION | Machinery | 1.7029 | 0.1116 | 0.3183 | 1.0000 | -0.0739 |
| 16 | 6718 | AIPHONE CO.,LTD. | Electric Appliances | 1.5210 | 0.0824 | 0.3172 | 0.8333 | -0.0240 |
| 17 | 4433 | HITO-Communications Holdings,Inc. | Services | 1.2767 | 0.0762 | 0.3163 | 0.8333 | -0.0563 |
| 18 | 2915 | KENKO Mayonnaise Co.,Ltd. | Foods | 1.3862 | 0.1215 | 0.3105 | 1.0000 | -0.0160 |
| 19 | 2733 | ARATA CORPORATION | Wholesale Trade | 1.3949 | 0.1241 | 0.3087 | 0.8333 | 0.0019 |
| 20 | 6658 | Shirai Electronics Industrial Co.,Ltd. | Electric Appliances | 1.4644 | 0.3056 | 0.3054 | 1.0000 | -0.0262 |

## 16. 500万円配分
sector-adjusted版は 4,992,700 円を投資し、投資率は 99.85%、現金残高は 7,300 円である。

## 17. Phase1の限界
Buffett本人の完全再現ではなく、保険フロート、非公開企業買収、経営者評価は再現できない。先行研究式は将来リターンを保証しない。

## 18. Phase2以降への接続
Phase2以降では、変わるMoat・生まれるMoatを扱うが、Phase1ではあくまで守の土台として公開データで再現可能な定量式に限定した。