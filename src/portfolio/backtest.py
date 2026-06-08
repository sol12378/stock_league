from __future__ import annotations

import pandas as pd

from src.config import AppConfig, load_config
from src.portfolio.metrics import cumulative_returns, performance_row
from src.utils.logging import setup_logger
from src.utils.prices import repair_split_jumps


def run_backtest(config: AppConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    logger = setup_logger("backtest", config.logs_dir)
    portfolio = pd.read_csv(config.data_processed_dir / "portfolio.csv", dtype={"code": str})
    prices = pd.read_parquet(config.data_processed_dir / "prices_daily.parquet")
    prices["price_for_return"] = prices["adj_close"].fillna(prices["close"])

    tickers = portfolio["ticker"].tolist()
    benchmarks = [config.topix_proxy, config.nikkei]
    needed = tickers + [b for b in benchmarks if b not in tickers]
    pivot = (
        prices[prices["ticker"].isin(needed)]
        .pivot(index="date", columns="ticker", values="price_for_return")
        .sort_index()
    )
    pivot = pivot.apply(repair_split_jumps, axis=0)
    returns = pivot.pct_change().replace([float("inf"), float("-inf")], pd.NA)
    weights = portfolio.set_index("ticker")["actual_weight"].reindex(tickers).fillna(0)
    portfolio_returns = returns[tickers].mul(weights, axis=1).sum(axis=1, min_count=1).fillna(0)

    out = pd.DataFrame({"date": returns.index, "portfolio_return": portfolio_returns.values})
    out["portfolio_cumulative_return"] = cumulative_returns(portfolio_returns).values
    for benchmark in benchmarks:
        if benchmark in returns.columns:
            out[f"{benchmark}_return"] = returns[benchmark].fillna(0).values
            out[f"{benchmark}_cumulative_return"] = cumulative_returns(returns[benchmark]).values
    out.to_csv(config.data_processed_dir / "portfolio_returns.csv", index=False)

    topix_returns = returns[config.topix_proxy].dropna() if config.topix_proxy in returns.columns else None
    summary_rows = [performance_row("Portfolio", portfolio_returns, topix_returns)]
    for benchmark in benchmarks:
        if benchmark in returns.columns:
            summary_rows.append(performance_row(benchmark, returns[benchmark]))
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(config.data_processed_dir / "performance_summary.csv", index=False)
    summary.to_csv(config.reports_tables_dir / "performance_summary.csv", index=False)

    contribution_rows: list[dict[str, object]] = []
    for ticker, weight in weights.items():
        if ticker not in pivot.columns:
            continue
        series = pivot[ticker].dropna()
        if len(series) < 2:
            continue
        stock_return = series.iloc[-1] / series.iloc[0] - 1
        row = portfolio[portfolio["ticker"] == ticker].iloc[0].to_dict()
        contribution_rows.append(
            {
                "ticker": ticker,
                "company_name": row.get("company_name"),
                "company_name_ja": row.get("company_name_ja"),
                "actual_weight": weight,
                "stock_cumulative_return": stock_return,
                "contribution": weight * stock_return,
            }
        )
    pd.DataFrame(contribution_rows).sort_values("contribution", ascending=False).to_csv(
        config.data_processed_dir / "contribution_by_stock.csv", index=False
    )

    risk_rows: list[dict[str, object]] = []
    for ticker in needed:
        if ticker not in returns.columns:
            continue
        ticker_returns = returns[ticker].dropna()
        if len(ticker_returns) < 30:
            continue
        risk_rows.append(
            {
                "ticker": ticker,
                "annualized_return": (1 + ticker_returns).prod() ** (252 / len(ticker_returns)) - 1,
                "annualized_volatility": ticker_returns.std() * (252**0.5),
            }
        )
    pd.DataFrame(risk_rows).to_csv(config.data_processed_dir / "risk_return.csv", index=False)
    logger.info("Wrote portfolio_returns.csv and performance_summary.csv")
    return out, summary


def main() -> None:
    run_backtest(load_config())


if __name__ == "__main__":
    main()
