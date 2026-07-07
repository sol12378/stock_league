# Phase1 Formula Implementation Audit

| indicator | paper | original_formula | implementation_status | variables_used | missing_reason | departure_from_original | report_label |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B/M | Fama-French | Book Equity / Market Equity | Implemented | equity, market_equity_final |  | none | B/M |
| E/P | Basu | Earnings / Market Equity | Implemented for positive earnings | net_income, market_equity_final | 赤字企業は欠損 | none | E/P |
| Gross Profitability | Novy-Marx | Gross Profit / Assets | Unavailable |  | gross profit/COGS absent | not implemented | 計算不能 |
| Piotroski available signal score | Piotroski | 9 binary signals | Partial | 6 available signals | gross margin/current ratio/equity issuance absent | 6/9 signals | Piotroski available signal score |
| Sloan Accruals | Sloan | (NI - CFO) / Avg Assets | Implemented | net_income, operating_cf, assets |  | none | Sloan accruals |
| Ohlson O-Score | Ohlson | Original O-score | Unavailable |  | GNP/WC/CA/CL/FFO/CHIN absent | not implemented | 計算不能 |
| Altman Z-Score | Altman | Original Z-score | Unavailable |  | working capital/retained earnings absent | not implemented | 計算不能 |