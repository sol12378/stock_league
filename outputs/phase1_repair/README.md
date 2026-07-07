# Phase1 Repair README

## 実行順

```bash
.venv/bin/python scripts/phase1_repair/01_inventory_inputs.py
.venv/bin/python scripts/phase1_repair/02_normalize_tickers.py
.venv/bin/python scripts/phase1_repair/03_collect_or_reconstruct_market_equity.py
.venv/bin/python scripts/phase1_repair/04_compute_bm_ep.py
.venv/bin/python scripts/phase1_repair/05_audit_value_coverage.py
.venv/bin/python scripts/phase1_repair/06_rerun_phase1_screening.py
.venv/bin/python scripts/phase1_repair/07_generate_reports.py
```

## 入力ファイル
`data/processed/scores.csv`, `data/processed/fundamentals_raw.csv`, `data/raw/edinet/xbrl/*.zip`.

## カバレッジ基準
B/M・E/P両方のカバレッジが50%未満なら最終20社を確定しません。70%以上なら再構築へ進みます。

## yfinance注意
この修復版はネットワーク取得を使わず、既存ローカルデータとEDINET XBRLを優先します。