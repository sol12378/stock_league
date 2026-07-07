
# BEYOND BUFFETT Phase2 Top1200 Walk-forward Perfect Fix

この成果物は、完全Walk-forwardに必要な追加データパネル構築タスクを実装したものです。
EDINET/XBRLの有価証券報告書、提出日、日次価格を使い、point-in-timeで検証可能な historical panel を作成しました。

## 何を追加したか

1. inline XBRLの `name/contextRef/scale` を読んだ拡張ファクト抽出
2. Gross Profit原式、株式数、流動資産/負債、営業CFを含む年度別パネル
3. `submit_date` の翌日以降を保守的な `decision_date` とする価格結合
4. 63/126/252営業日先の将来リターン列
5. Piotroski F-score 9要素のcomponent-level欠損監査
6. fiscal year単位のstrict train/test fold定義
7. 年度別Top1200ランキングとfold検証結果

## 重要な位置づけ

本成果物は、完全Walk-forwardを主張するために必要なデータパネルを最大限構築したものです。
ただし、利用可能なローカルデータは2021-2026のEDINET文書と2021-06以降の日次価格に限られるため、統計的に十分な長期fold数を保証するものではありません。
「look-aheadを避けたpoint-in-time panelの構築」は完了し、そのうえでfold数・欠損・将来リターン利用可能率を監査可能にしています。

## 主要ファイル

- `xbrl_facts/edinet_xbrl_extended_facts.csv`
- `data_panel/historical_point_in_time_panel.csv`
- `data_panel/walk_forward_feature_panel.csv`
- `walk_forward/fold_definitions.csv`
- `walk_forward/strict_walk_forward_results.csv`
- `walk_forward/annual_rankings_all.csv`
- `walk_forward/annual_top1200_by_year.csv`
- `reports/data_panel_construction_report.md`
- `reports/strict_walk_forward_report.md`
- `reports/walk_forward_completeness_audit.md`
- `reports/limitations.md`
- `reports/phase3_handoff_from_perfect_panel.md`

## Summary

| metric | value |
| --- | --- |
| xbrl_fact_rows | 10712 |
| xbrl_parse_error_count | 0 |
| panel_rows | 10712 |
| strict_fact_complete_rows | 9155 |
| strict_walk_forward_ready_rows | 9141 |
| future_return_252d_available_rows | 6931 |
| fold_count | 3 |
