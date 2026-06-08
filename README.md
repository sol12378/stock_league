# BEYOND BUFFETT Stock League Pipeline

日経STOCKリーグ向けの日本株スクリーニング、500万円ポートフォリオ構成、バックテスト、図表・レポート草案生成パイプラインです。

## Setup

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

`.env` には `EDINET_API_KEY` を設定してください。JPX上場銘柄一覧は既定で `docs/data_e.xls` を読みます。

## Run

```bash
.venv/bin/python -m src.run_all --edinet-limit 300
```

時間を短縮したい場合:

```bash
.venv/bin/python -m src.run_all --skip-edinet
.venv/bin/python -m src.run_all --skip-fetch-prices
```

主な出力:

- `data/processed/universe.csv`
- `data/processed/latest_prices.csv`
- `data/processed/fundamentals_clean.csv`
- `data/processed/scores.csv`
- `data/processed/candidates_top80.csv`
- `data/processed/portfolio.csv`
- `data/processed/portfolio_returns.csv`
- `data/processed/performance_summary.csv`
- `reports/figures/*.png`
- `reports/draft/report_draft.md`
- `reports/draft/beyond_buffett_report.docx`

## Notes

本パイプラインは公開データに基づく調査・レポート作成支援用です。yfinanceとEDINET APIの取得状況により、欠損や取得失敗が発生する可能性があります。最終提出前には、候補企業の有価証券報告書、決算説明資料、中期経営計画を手動確認してください。

## 2026-06-08 screening update

第1スクリーニングの `investment_eligible` は、従来は価格取得、価格履歴、流動性条件に近く、流動性条件通過後2,560社から2,556社へ4社しか減らない状態でした。今回、500万円の仮想ポートフォリオに組み入れる前提として、財務安全性、継続収益力、営業キャッシュフロー、レバレッジ、主要指標の異常値、財務データ欠損を確認する投資適格性フィルターへ強化しました。

初回強化後のファネルは、`universe` 3,649社、`price_available` 3,648社、`liquid_20m_60d` 2,560社、`investment_eligible` 1,917社、`scored` 1,917社でした。`scored` は投資適格性を通過したスコア算出対象企業数として定義し、レポート上は「スコア算出対象」と表記します。

## exp001 screening consistency and financial-sector handling

`exp001` では、投資適格性除外理由の4社ズレを修正しました。原因は、`liquid_20m_60d` は2,560社で集計していた一方、除外理由CSVの母集団には価格履歴500日以上の条件を先に適用していたためです。その結果、価格履歴不足の4社が `investment_eligible=False` であるにもかかわらず、除外理由CSVに出力されていませんでした。修正後は、`liquid_20m_60d=True` かつ `investment_eligible=False` の全社を除外CSVに出力し、価格履歴不足、財務データ結合失敗、主要財務データ欠損、銘柄コード不一致等は `missing_financial_data` または `other_data_quality_issue` として必ず理由付けします。

また、銀行、保険、証券などの金融業は、一般事業会社と財務構造が異なるため、自己資本比率、営業キャッシュフロー、有利子負債倍率、営業利益率などを同一基準で比較することには限界があります。そのため、本分析では、金融業については一部の財務健全性フィルターを機械的に適用せず、ROE、PBR、利益安定性、株主還元、資本効率改善などを中心に評価しました。これにより、金融業を不自然に除外することを避けつつ、Transformation MoatおよびCore Moatの観点から評価しています。

`exp001` 再計算後のファネルは、`universe` 3,649社、`price_available` 3,648社、`liquid_20m_60d` 2,560社、`investment_eligible` 1,963社、`scored` 1,963社です。金融業の機械的除外を外したため、投資適格性通過数は初回強化後の1,917社から1,963社へ変わりました。除外理由のユニーク除外数は597社で、`2,560 - 1,963 = 597` と一致します。金融業は33業種分類の `Banks`、`Insurance`、`Securities and Commodities Futures`、`Other Financing Business` および日本語相当業種を対象とし、流動性通過151社のうち144社が投資適格性を通過しました。
