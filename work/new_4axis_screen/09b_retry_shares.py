"""Part 9b: 09_fetch_shares.py の取りこぼしを埋める。

初回は並列10でレート制限に当たり 906/1,963 しか取れなかった。
未取得ぶんだけを低並列＋指数バックオフで再取得し、shares_live.csv を更新する。
途中で落ちても進捗が残るよう、1巡ごとに書き出す。
"""
from __future__ import annotations

import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
CSV = OUT / "shares_live.csv"

WORKERS = 3
PASSES = 8
BASE_SLEEP = 0.7


def fetch(ticker: str, pause: float) -> dict[str, object]:
    time.sleep(pause * random.uniform(0.6, 1.4))
    try:
        fi = yf.Ticker(ticker).fast_info
        return {"ticker": ticker, "shares_live": fi.get("shares"),
                "last_price": fi.get("lastPrice"), "market_cap_live": fi.get("marketCap"),
                "status": "ok"}
    except Exception as exc:
        return {"ticker": ticker, "shares_live": None, "last_price": None,
                "market_cap_live": None, "status": f"error:{type(exc).__name__}"}


def main() -> None:
    df = pd.read_csv(CSV, dtype={"code": str})
    for p in range(1, PASSES + 1):
        todo = df.loc[df["shares_live"].isna(), "ticker"].dropna().tolist()
        if not todo:
            print("すべて取得済み")
            break
        pause = BASE_SLEEP * (1.6 ** (p - 1))
        print(f"[pass {p}] 未取得 {len(todo)} 件 / 並列{WORKERS} / 待機{pause:.1f}s", file=sys.stderr)
        got = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(fetch, t, pause) for t in todo]
            for f in as_completed(futs):
                r = f.result()
                if r["shares_live"] is not None:
                    m = df["ticker"] == r["ticker"]
                    for k in ["shares_live", "last_price", "market_cap_live", "status"]:
                        df.loc[m, k] = r[k]
                    got += 1
        df.to_csv(CSV, index=False)
        rate = df["shares_live"].notna().mean() * 100
        print(f"[pass {p}] 追加 {got} 件 → 累計 {int(df['shares_live'].notna().sum())}/{len(df)} "
              f"({rate:.1f}%)", file=sys.stderr)
        if got == 0:
            print("このパスで1件も取れなかったので待機を延ばして継続", file=sys.stderr)
            time.sleep(30)

    ok = df["shares_live"].notna()
    print(f"最終: {int(ok.sum())}/{len(df)} ({ok.mean()*100:.1f}%)")


if __name__ == "__main__":
    main()
