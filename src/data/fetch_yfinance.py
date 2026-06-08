from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from tqdm import tqdm

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


PRICE_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def _normalize_download(data: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    if isinstance(data.columns, pd.MultiIndex):
        level0 = set(map(str, data.columns.get_level_values(0)))
        level1 = set(map(str, data.columns.get_level_values(1)))
        for ticker in tickers:
            if ticker in level0:
                sub = data[ticker].copy()
            elif ticker in level1:
                sub = data.xs(ticker, axis=1, level=1).copy()
            else:
                continue
            sub["ticker"] = ticker
            frames.append(sub)
    else:
        sub = data.copy()
        sub["ticker"] = tickers[0] if tickers else ""
        frames.append(sub)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames)
    out = out.reset_index().rename(columns={"Date": "date", "index": "date"})
    out = out.rename(columns=PRICE_COLUMNS)
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if col not in out.columns:
            out[col] = np.nan
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out = out[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]]
    return out.dropna(subset=["date", "ticker"]).dropna(subset=["close", "adj_close"], how="all")


def fetch_price_chunk(tickers: list[str], years: int, retries: int = 2) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            data = yf.download(
                tickers=tickers,
                period=f"{years}y",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=True,
            )
            return _normalize_download(data, tickers)
        except Exception as exc:  # yfinance raises varied network/parser exceptions
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    return pd.DataFrame()


def build_latest_prices(prices: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker, group in prices.sort_values("date").groupby("ticker"):
        clean = group.dropna(subset=["close", "adj_close"], how="all")
        if clean.empty:
            continue
        latest = clean.iloc[-1]
        tail = clean.tail(60).copy()
        trading_value = tail["close"].astype(float) * tail["volume"].astype(float)
        rows.append(
            {
                "ticker": ticker,
                "latest_date": latest["date"],
                "close": latest["close"],
                "adj_close": latest["adj_close"],
                "volume": latest["volume"],
                "avg_trading_value_60d": trading_value.replace([np.inf, -np.inf], np.nan).mean(),
                "history_days": len(clean),
            }
        )
    return pd.DataFrame(rows)


def fetch_quote_metrics(
    tickers: list[str],
    output_path: Path,
    limit: int | None = None,
    sleep_seconds: float = 0.05,
) -> pd.DataFrame:
    if limit is not None and limit > 0:
        tickers = tickers[:limit]
    rows: list[dict[str, object]] = []
    for ticker in tqdm(tickers, desc="quote metrics"):
        info: dict[str, object] = {}
        try:
            info = yf.Ticker(ticker).get_info()
        except Exception:
            try:
                fast = yf.Ticker(ticker).fast_info
                info = dict(fast.items()) if hasattr(fast, "items") else {}
            except Exception:
                info = {}
        rows.append(
            {
                "ticker": ticker,
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "price_to_book": info.get("priceToBook"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "ebitda": info.get("ebitda"),
                "currency": info.get("currency"),
                "quote_type": info.get("quoteType"),
            }
        )
        time.sleep(sleep_seconds)
    metrics = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_path, index=False)
    return metrics


def fetch_prices(
    config: AppConfig,
    years: int | None = None,
    chunk_size: int = 180,
    quote_metrics_limit: int = 800,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    logger = setup_logger("fetch_yfinance", config.logs_dir)
    universe = pd.read_csv(config.data_processed_dir / "universe.csv", dtype={"code": str})
    tickers = universe["ticker"].dropna().drop_duplicates().tolist()
    benchmark_tickers = [config.topix_proxy, config.nikkei]
    all_tickers = tickers + [t for t in benchmark_tickers if t not in tickers]
    years = years or config.backtest_years

    frames: list[pd.DataFrame] = []
    failed_chunks: list[dict[str, object]] = []
    for start in tqdm(range(0, len(all_tickers), chunk_size), desc="price chunks"):
        chunk = all_tickers[start : start + chunk_size]
        try:
            part = fetch_price_chunk(chunk, years=years)
            frames.append(part)
        except Exception as exc:
            failed_chunks.append({"chunk_start": start, "tickers": ",".join(chunk), "error": str(exc)})

    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if prices.empty:
        raise RuntimeError("No yfinance price data was fetched.")

    prices = prices.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"])
    prices_path = config.data_processed_dir / "prices_daily.parquet"
    latest_path = config.data_processed_dir / "latest_prices.csv"
    prices.to_parquet(prices_path, index=False)
    latest = build_latest_prices(prices)
    latest.to_csv(latest_path, index=False)

    missing = sorted(set(all_tickers) - set(latest["ticker"]))
    failed_rows = failed_chunks + [{"ticker": t, "error": "no latest price"} for t in missing]
    pd.DataFrame(failed_rows).to_csv(config.logs_dir / "failed_tickers.csv", index=False)

    liquid_tickers = (
        latest[latest["ticker"].isin(tickers)]
        .sort_values("avg_trading_value_60d", ascending=False)["ticker"]
        .tolist()
    )
    fetch_quote_metrics(
        liquid_tickers,
        config.data_processed_dir / "yfinance_metrics.csv",
        limit=quote_metrics_limit,
    )
    logger.info("Wrote %s price rows, %s latest rows", len(prices), len(latest))
    return prices, latest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=180)
    parser.add_argument("--quote-metrics-limit", type=int, default=800)
    args = parser.parse_args()
    fetch_prices(
        load_config(),
        years=args.years,
        chunk_size=args.chunk_size,
        quote_metrics_limit=args.quote_metrics_limit,
    )


if __name__ == "__main__":
    main()
