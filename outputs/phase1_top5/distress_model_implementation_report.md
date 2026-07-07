# Distress Model Implementation Report

Ohlson O-Score原式は実装しない。必要なGNP price-level index、current assets、current liabilities、funds from operationsが十分に揃わないためである。operating cash flow / total liabilitiesはFFO/TLの補助候補として算出できるが、原式からの逸脱になるためTop5選定の主条件には使わない。

Altman Z-Score原式も実装しない。working capitalとretained earningsが欠け、EBITもoperating income proxyに留まるためである。Altman原式は製造業向けであり、日本株非金融全体に絶対閾値をそのまま適用しない。

今回のTop5選定では、Ohlson/Altmanは補助レビューに留め、Low Distress条件はsimple distress guardrailで担保する。

## Missing Variables

| model | missing_variables |
| --- | --- |
| Ohlson | GNP price-level index; current_assets; current_liabilities; funds_from_operations |
| Altman | working_capital; retained_earnings; strict_EBIT |

## Variable Inventory Summary

| variable | found_direct_or_named_column | best_source_file | best_source_column | derivation_or_note |
| --- | --- | --- | --- | --- |
| total_assets | True | data/processed/fundamentals_raw.csv | total_assets |  |
| total_liabilities | True | outputs/phase1_final/simple_distress_guardrail.csv | liabilities_to_assets_high |  |
| current_assets | True |  |  |  |
| current_liabilities | True |  |  |  |
| working_capital | False |  |  | requires_current_assets_minus_current_liabilities |
| net_income | True | data/processed/fundamentals_raw.csv | net_income |  |
| prior_year_net_income | True | data/processed/fundamentals_raw.csv | net_income |  |
| two_years_ago_net_income | True | data/processed/fundamentals_raw.csv | net_income |  |
| operating_cash_flow | True | data/processed/fundamentals_raw.csv | operating_cf |  |
| funds_from_operations | False |  |  |  |
| filing_date | True | data/processed/edinet_documents.csv | submit_date |  |
| fiscal_year_end | True | data/processed/edinet_documents.csv | period_end |  |
| retained_earnings | False |  |  |  |
| EBIT | True | data/processed/fundamentals_raw.csv | operating_income |  |
| market_value_of_equity | True | outputs/phase1_final/final20_anomaly_review.csv | market_equity_final |  |
| sales | True | data/processed/fundamentals_raw.csv | revenue |  |
| revenue | True | data/processed/fundamentals_raw.csv | revenue |  |
| equity | True | data/processed/fundamentals_raw.csv | equity |  |