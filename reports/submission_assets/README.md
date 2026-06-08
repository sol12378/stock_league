# BEYOND BUFFETT 提出レポート素材パッケージ

提出用レポート作成に必要な図表、数値、テーブルを集約したフォルダです。

## ディレクトリ

- `tables/`: CSV形式の表・数値
- `figures/`: PNG形式の図表
- `docs/`: 草案PDF/DOCX/Markdownと元分析PDF

## 最優先で使う素材

- `tables/screening_summary.csv` と `figures/screening_funnel.png`
- `tables/investment_eligibility_exclusion_summary.csv` と `tables/investment_eligibility_exclusions.csv`
- `tables/financial_sector_handling_summary.csv`、`tables/financial_sector_exclusion_check.csv`、`tables/financial_sector_score_components.csv`
- `tables/score_formula_table.csv`
- `tables/scores_top20.csv`
- `tables/portfolio_table.csv` と `tables/portfolio_policy_summary.csv`
- `figures/category_allocation.png` と `figures/sector_allocation.png`
- `tables/selection_reason_table.csv`
- `tables/performance_summary.csv`
- `figures/cumulative_return.png`、`figures/drawdown.png`、`figures/contribution_by_stock.png`
- `tables/ablation_performance.csv`、`tables/category_returns.csv`、`tables/santec_exclusion_analysis.csv`
- `tables/future_moat_classification.csv`、`tables/edinet_qualitative_summary.csv`、`tables/limitations_table.csv`

## 注意

投資適格性フィルターでは、500万円の仮想ポートフォリオに組み入れる前提として、流動性に加え、財務安全性、継続的な収益力、キャッシュ創出力、主要指標の異常値を確認しました。財務的な持続可能性を欠く企業や、データの信頼性が著しく低い企業は長期投資の対象として不適切であるため除外しています。

EDINET定性要約は提出前の確認用ドラフトです。EDINET XBRL取得済みの定量情報と既存分類をもとに作成していますが、最終提出前には有価証券報告書本文・IR資料で文言を確認してください。
