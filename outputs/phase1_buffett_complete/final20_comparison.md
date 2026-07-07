# Final20 Comparison

| portfolio | company_count | overlap_with_base | overlap_with_conservative | overlap_with_sector_adjusted | sector_count | market_count | average_bm | average_ep | average_gross_profitability | average_piotroski_available_ratio | average_sloan_accruals | human_review_required_count | liquidity_review_count | distress_review_count | extreme_value_count | retail_trade_count | retail_trade_ratio | adoption_judgement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | 20 | 20 | 8 | 5 | 7 | 2 | 1.5927 | 0.1916 | 0.6797 | 0.8417 | -0.0368 | 12 | 10 | 0 | 1 | 13 | 65.00% | comparison_reference |
| conservative | 20 | 8 | 20 | 11 | 7 | 3 | 1.5301 | 0.1409 | 0.4628 | 0.8750 | -0.0228 | 0 | 0 | 0 | 0 | 13 | 65.00% | comparison_reference |
| sector_adjusted | 20 | 5 | 11 | 20 | 11 | 3 | 1.5055 | 0.1495 | 0.4128 | 0.8750 | -0.0308 | 0 | 0 | 0 | 0 | 4 | 20.00% | formal_phase1_recommended |

正式採用候補は `sector_adjusted final20` とする。理由は、ValueとQuality条件を維持しつつ、human review・流動性reviewを抑え、Retail Trade偏重を5社以下に制約しているため。