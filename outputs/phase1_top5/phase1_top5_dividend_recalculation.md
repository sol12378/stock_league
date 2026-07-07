# Phase1 Top5 Dividend Recalculation

Top5のローカル配当利回りは欠損していたため、Yahoo Finance via yfinanceから年間DPSと株価を取得し、`年間DPS / 株価` で再計算した。

| code | company_name | price_used | chosen_annual_dps | recalculated_dividend_yield | trailing_annual_dps | trailing_dividend_yield_recalculated |
| --- | --- | --- | --- | --- | --- | --- |
| 3539 | JM HOLDINGS CO.,LTD. | 1,268.00 | 24.00 | 1.89% | 24.00 | 1.89% |
| 4350 | MEDICAL SYSTEM NETWORK Co.,Ltd. | 480.00 | 12.00 | 2.50% | 12.00 | 2.50% |
| 6430 | DAIKOKU DENKI CO.,LTD. | 2,351.00 | 100.00 | 4.25% | 0.00 | 0.00% |
| 7803 | Bushiroad Inc. | 323.00 | 5.00 | 1.55% | 2.25 | 0.70% |
| 9470 | GAKKEN HOLDINGS CO.,LTD. | 1,030.00 | 29.00 | 2.82% | 27.50 | 2.67% |

- Top5を最終20社内で各4%保有した場合の配当利回り寄与: 0.52%
- Top5を最終20社内で各5%保有した場合の配当利回り寄与: 0.65%
- 500万円ポートフォリオ換算の年間配当額目安（各4%）: 26,020円
- 500万円ポートフォリオ換算の年間配当額目安（各5%）: 32,524円

注意: これは最新取得時点のDPS・株価に基づく概算であり、配当予想の変更、記念配当、無配転落、株価変動で変わる。