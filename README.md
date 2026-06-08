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

再計算後のファネルは、`universe` 3,649社、`price_available` 3,648社、`liquid_20m_60d` 2,560社、`investment_eligible` 1,917社、`scored` 1,917社です。`scored` は投資適格性を通過したスコア算出対象企業数として定義し、レポート上は「スコア算出対象」と表記します。

除外理由のユニーク除外数は639社です。理由別には、財務データ欠損308社、自己資本比率の低さ70社、継続的な営業赤字154社、継続的な営業CF赤字282社、過大レバレッジ74社、バリュエーション異常値14社、収益性異常値70社、その他データ品質32社です。金融・保険・銀行等は自己資本比率、レバレッジ、営業CFの扱いを一般事業会社より緩和し、流動性通過157社のうち100社が投資適格性を通過しました。
