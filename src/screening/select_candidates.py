from __future__ import annotations

import argparse
import math

import pandas as pd

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


def select_candidates(config: AppConfig, portfolio_size: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    logger = setup_logger("select_candidates", config.logs_dir)
    portfolio_size = portfolio_size or config.portfolio_size
    scores = pd.read_csv(config.data_processed_dir / "scores.csv", dtype={"code": str})
    eligible = scores[scores["investment_eligible"]].copy()
    if len(eligible) < portfolio_size:
        eligible = scores[scores["close"].notna()].copy()

    top80 = eligible.sort_values("adjusted_bb_score", ascending=False).head(80).copy()
    top80.to_csv(config.data_processed_dir / "candidates_top80.csv", index=False)

    max_sector_count = max(2, math.ceil(portfolio_size * 0.25))
    max_category_count = max(4, math.ceil(portfolio_size * 0.40))
    selected_rows: list[pd.Series] = []
    sector_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}

    for _, row in top80.iterrows():
        sector = str(row.get("sector_33", "Unknown"))
        category = str(row.get("category", "Unknown"))
        if sector_counts.get(sector, 0) >= max_sector_count:
            continue
        if category_counts.get(category, 0) >= max_category_count:
            continue
        selected_rows.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
        if len(selected_rows) >= portfolio_size:
            break

    if len(selected_rows) < portfolio_size:
        selected_tickers = {row["ticker"] for row in selected_rows}
        for _, row in top80.iterrows():
            if row["ticker"] in selected_tickers:
                continue
            selected_rows.append(row)
            selected_tickers.add(row["ticker"])
            if len(selected_rows) >= portfolio_size:
                break

    portfolio = pd.DataFrame(selected_rows).head(portfolio_size).copy()
    portfolio["needs_financial_explanation"] = portfolio["is_financial"].astype(bool)
    portfolio["is_small_cap_candidate"] = portfolio["scale_category"].fillna("").str.contains(
        "Small|Growth|PRO", case=False, regex=True
    )
    portfolio.to_csv(config.data_processed_dir / "portfolio_candidates.csv", index=False)

    summary_path = config.data_processed_dir / "screening_summary.csv"
    summary = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame(columns=["stage", "count"])
    extra = pd.DataFrame(
        [
            {"stage": "candidates_top80", "count": len(top80)},
            {"stage": "portfolio_candidates", "count": len(portfolio)},
        ]
    )
    summary = pd.concat([summary[~summary["stage"].isin(extra["stage"])], extra], ignore_index=True)
    summary.to_csv(summary_path, index=False)
    logger.info("Selected %s top80 and %s portfolio candidates", len(top80), len(portfolio))
    return top80, portfolio


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-size", type=int, default=None)
    args = parser.parse_args()
    select_candidates(load_config(), portfolio_size=args.portfolio_size)


if __name__ == "__main__":
    main()
