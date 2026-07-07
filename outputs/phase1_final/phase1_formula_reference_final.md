# Phase1 Formula Reference Final

| formula | paper | authors | year | journal | original_formula | what_it_measures | implementation_status | departure | report_label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B/M | Fama-French | Fama and French | 1993 | JFE | Book Equity / Market Equity | Value | Implemented | none | B/M |
| E/P | Basu | Basu | 1977/1983 | JF/JFE | Earnings / Market Equity | Earnings yield | Implemented | positive earnings only | E/P |
| Gross Profitability | Other Side of Value | Novy-Marx | 2013 | JFE | Gross Profit / Assets | Profitability | Implemented where XBRL tags available | missing tags not imputed | Gross Profitability |
| Piotroski | Value Investing | Piotroski | 2000 | JAR | 9 binary signals | Financial strength | Partial | 6 available signals | Piotroski available signal score |
| Sloan Accruals | Accruals and Cash Flows | Sloan | 1996 | Accounting Review | (NI-CFO)/Avg Assets | Earnings quality | Implemented | CFO form | Sloan accruals |
| Ohlson O-Score | Bankruptcy prediction | Ohlson | 1980 | JAR | O-score | Distress | Unavailable | missing inputs | Not implemented |
| Altman Z | Bankruptcy prediction | Altman | 1968 | JF | Z-score | Distress | Unavailable | missing inputs | Not implemented |
| Simple distress guardrail | Implementation guardrail | N/A | N/A | N/A | negative equity/loss/leverage flags | Low distress | Implemented | not Ohlson/Altman | Simple distress guardrail |
| Liquidity filter | Implementation guardrail | N/A | N/A | N/A | avg close*volume 60d | Tradability | Implemented | not selection alpha | Liquidity filter |