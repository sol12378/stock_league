"""Part 9: 適格企業の発行済株式数を実勢値で取り直す。

なぜ必要か:
  XBRLの株式数・1株当たり数値は「提出時点」の基準。提出後に株式分割した会社は
  株価(遡って調整済み)と基準が食い違い、時価総額が分割比率のぶん過小になる。
  実測で確認した例:
     6648 かわでん   XBRL 4,192,000 → 実勢 16,015,485 (3.82倍)
     3798 ULSグループ XBRL 6,228,800 → 実勢 56,578,380 (9.08倍)
     5729 日本精鉱   XBRL 2,605,900 → 実勢  9,802,968 (3.76倍)
  この3社はいずれも修正前のPBRが0.3で、Price軸の最上位に張り付いていた。

  DATA_MISSINGNESS_AUDIT_v1 §D-3 が推奨していた「quote-metrics を全社に広げる」
  の最小実装。fast_info だけを使うので1社1秒程度で済む。

出力: work/new_4axis_screen/out/shares_live.csv
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yfinance as yf
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
WORKERS = 10
RETRIES = 2


def fetch(ticker: str) -> dict[str, object]:
    for attempt in range(RETRIES + 1):
        try:
            fi = yf.Ticker(ticker).fast_info
            return {
                "ticker": ticker,
                "shares_live": fi.get("shares"),
                "last_price": fi.get("lastPrice"),
                "market_cap_live": fi.get("marketCap"),
                "status": "ok",
            }
        except Exception as exc:
            if attempt == RETRIES:
                return {"ticker": ticker, "shares_live": None, "last_price": None,
                        "market_cap_live": None, "status": f"error:{type(exc).__name__}"}
            time.sleep(1.0 * (attempt + 1))
    return {"ticker": ticker, "status": "unreachable"}


def main() -> None:
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str},
                         low_memory=False, usecols=["code", "ticker", "investment_eligible"])
    tickers = scores.loc[
        scores["investment_eligible"].fillna(False).astype(bool), "ticker"
    ].dropna().unique().tolist()
    print(f"取得対象 {len(tickers)} 銘柄 / 並列 {WORKERS}", file=sys.stderr)

    rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch, t): t for t in tickers}
        for f in tqdm(as_completed(futs), total=len(futs), desc="fast_info"):
            rows.append(f.result())

    out = pd.DataFrame(rows).merge(scores[["code", "ticker"]], on="ticker", how="left")
    out.to_csv(OUT / "shares_live.csv", index=False)
    ok = out["shares_live"].notna()
    print()
    print("取得成功:", int(ok.sum()), "/", len(out),
          f"({ok.mean()*100:.1f}%)")
    print(out["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
