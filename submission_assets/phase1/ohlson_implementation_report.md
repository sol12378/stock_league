# Ohlson O-Score Implementation Report

Ohlson O-Score is not calculated in Phase1.

Required inputs missing from the local data include GNP price-level index, working capital,
current liabilities, current assets, funds from operations, and CHIN. The implementation does
not replace GNP with log(total assets), because that would be a material departure from the original formula.