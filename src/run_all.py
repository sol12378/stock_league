from __future__ import annotations

import argparse
import time
from collections.abc import Callable

from src.config import AppConfig, load_config
from src.data.build_fundamentals import build_fundamentals
from src.data.fetch_edinet import fetch_edinet_for_codes, select_edinet_codes
from src.data.fetch_yfinance import fetch_prices
from src.data.load_jpx import build_universe
from src.data.parse_edinet_xbrl import parse_all_edinet
from src.portfolio.allocate import allocate_portfolio
from src.portfolio.backtest import run_backtest
from src.report.charts import generate_charts
from src.report.extra_analysis import generate_extra_analysis
from src.report.generate_markdown import generate_docx, generate_markdown
from src.report.generate_pdf import generate_pdf
from src.screening.scoring import score_universe
from src.screening.select_candidates import select_candidates
from src.utils.logging import setup_logger


def _run_step(name: str, fn: Callable[[], object], logger) -> object:
    logger.info("START %s", name)
    start = time.time()
    try:
        result = fn()
    except Exception:
        logger.exception("FAILED %s", name)
        raise
    logger.info("END %s (%.1fs)", name, time.time() - start)
    return result


def run_pipeline(config: AppConfig, args: argparse.Namespace) -> None:
    logger = setup_logger("run_all", config.logs_dir)
    _run_step(
        "load_jpx",
        lambda: build_universe(
            config.jpx_listed_companies_path,
            config.data_processed_dir / "universe.csv",
        ),
        logger,
    )

    if not args.skip_fetch_prices:
        _run_step(
            "fetch_yfinance",
            lambda: fetch_prices(
                config,
                years=args.years,
                chunk_size=args.price_chunk_size,
                quote_metrics_limit=args.quote_metrics_limit,
            ),
            logger,
        )

    _run_step("build_fundamentals_initial", lambda: build_fundamentals(config), logger)
    initial_scores = _run_step(
        "scoring_preliminary",
        lambda: score_universe(config, preliminary=True),
        logger,
    )

    if not args.skip_edinet:
        source = initial_scores.sort_values("adjusted_bb_score", ascending=False)
        codes = select_edinet_codes(source, args.edinet_limit)
        _run_step(
            "fetch_edinet",
            lambda: fetch_edinet_for_codes(
                config,
                codes=codes,
                lookback_days=args.edinet_lookback_days,
                docs_per_company=args.edinet_docs_per_company,
            ),
            logger,
        )
        _run_step("parse_edinet_xbrl", lambda: parse_all_edinet(config), logger)
        _run_step("build_fundamentals_final", lambda: build_fundamentals(config), logger)

    _run_step("scoring_final", lambda: score_universe(config, preliminary=False), logger)
    _run_step("select_candidates", lambda: select_candidates(config, args.portfolio_size), logger)
    _run_step(
        "allocate",
        lambda: allocate_portfolio(config, capital=args.capital, max_weight=args.max_weight),
        logger,
    )
    _run_step("backtest", lambda: run_backtest(config), logger)
    _run_step("charts", lambda: generate_charts(config), logger)
    if args.extra_analysis:
        _run_step("extra_analysis", lambda: generate_extra_analysis(config), logger)
    _run_step("generate_markdown", lambda: generate_markdown(config), logger)
    _run_step("generate_docx", lambda: generate_docx(config), logger)
    _run_step("generate_pdf", lambda: generate_pdf(config), logger)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-edinet", action="store_true")
    parser.add_argument("--skip-fetch-prices", action="store_true")
    parser.add_argument("--years", type=int, default=None)
    parser.add_argument("--portfolio-size", type=int, default=None)
    parser.add_argument("--capital", type=int, default=None)
    parser.add_argument("--max-weight", type=float, default=None)
    parser.add_argument("--edinet-limit", default=None)
    parser.add_argument("--edinet-lookback-days", type=int, default=1300)
    parser.add_argument("--edinet-docs-per-company", type=int, default=3)
    parser.add_argument("--quote-metrics-limit", type=int, default=800)
    parser.add_argument("--price-chunk-size", type=int, default=180)
    parser.add_argument("--extra-analysis", action="store_true")
    args = parser.parse_args()
    config = load_config()
    if args.years is None:
        args.years = config.backtest_years
    if args.portfolio_size is None:
        args.portfolio_size = config.portfolio_size
    if args.capital is None:
        args.capital = config.total_capital
    if args.max_weight is None:
        args.max_weight = config.max_weight
    if args.edinet_limit is None:
        args.edinet_limit = config.edinet_limit
    return args


def main() -> None:
    config = load_config()
    args = parse_args()
    run_pipeline(config, args)


if __name__ == "__main__":
    main()
