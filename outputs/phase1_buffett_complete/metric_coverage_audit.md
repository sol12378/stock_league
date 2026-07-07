# Metric Coverage Audit

| metric | available_count | universe_count | coverage | phase1_use_judgement | notes |
| --- | --- | --- | --- | --- | --- |
| B/M | 3089 | 3099 | 99.68% | usable | Book Equity / Market Equity. 欠損補完なし。 |
| E/P | 2750 | 3099 | 88.74% | usable | positive earnings only. 欠損補完なし。 |
| Gross Profitability | 3042 | 3099 | 98.16% | usable | Gross Profit / Total Assets. Qualityの中心条件。 |
| Piotroski available signal score | 3099 | 3099 | 100.00% | usable_as_available_version | 9信号完全版ではないためF-Score単独表記は禁止。 |
| Sloan Accruals | 3070 | 3099 | 99.06% | usable | (Net Income - Operating Cash Flow) / Average Total Assets。 |
| Simple distress guardrail | 3099 | 3099 | 100.00% | usable | Ohlson/Altmanではなく、資本毀損・損失・レバレッジの簡易ガードレール。 |
| Liquidity | 3099 | 3099 | 100.00% | usable | average close x volume over latest 60 trading days。 |

## Piotroski Available Signal Count Distribution

| available_signal_max | company_count |
| --- | --- |
| 6 | 3099 |

すべての指標はPhase1で使用可能。ただしPiotroskiは完全9信号ではなく、`Piotroski available signal score` として扱う。