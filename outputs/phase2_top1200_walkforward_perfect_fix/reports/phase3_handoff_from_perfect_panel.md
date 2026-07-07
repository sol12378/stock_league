
# Phase3 Handoff From Perfect Panel

Phase3では `data_panel/walk_forward_feature_panel.csv` を基礎データとして使う。

優先確認:
- `strict_walk_forward_ready == true` の企業を優先する。
- `gross_profit_source == direct_xbrl_gross_profit` の企業はGP/A原式の信頼度が高い。
- `gross_profit_source == derived_revenue_minus_cost_of_sales` の企業は売上総利益の直接タグを再確認する。
- `shares_outstanding_source == xbrl_issued_minus_treasury` を優先し、`xbrl_issued_shares` のみの企業は自己株式控除不足を確認する。
- `piotroski_f_score_available_components < 9` の企業はF-score欠損要素を個別確認する。
- `future_return_252d` は検証用であり、銘柄選定時の説明変数として使わない。
