from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


def cap_weights(raw_weights: pd.Series, max_weight: float) -> pd.Series:
    raw = raw_weights.fillna(0).clip(lower=0)
    if raw.sum() <= 0:
        raw = pd.Series(1.0, index=raw.index)
    original = raw / raw.sum()
    capped = pd.Series(0.0, index=original.index)
    remaining = set(original.index)
    remaining_weight = 1.0

    while remaining:
        base = original.loc[list(remaining)]
        base = base / base.sum()
        proposed = base * remaining_weight
        over = proposed[proposed > max_weight]
        if over.empty:
            capped.loc[proposed.index] = proposed
            break
        capped.loc[over.index] = max_weight
        remaining_weight -= max_weight * len(over)
        remaining -= set(over.index)
        if remaining_weight <= 0:
            break
    total = capped.sum()
    return capped / total if total > 0 else capped


def allocate_portfolio(
    config: AppConfig,
    capital: int | None = None,
    max_weight: float | None = None,
) -> pd.DataFrame:
    logger = setup_logger("allocate", config.logs_dir)
    capital = capital or config.total_capital
    max_weight = max_weight or config.max_weight
    candidates = pd.read_csv(config.data_processed_dir / "portfolio_candidates.csv", dtype={"code": str})
    latest = pd.read_csv(config.data_processed_dir / "latest_prices.csv")
    latest = latest[["ticker", "latest_date", "close"]].rename(columns={"close": "previous_close"})

    df = candidates.drop(columns=[c for c in ["latest_date", "previous_close"] if c in candidates.columns])
    df = df.merge(latest, on="ticker", how="left")
    df = df.dropna(subset=["previous_close"])
    df = df[df["previous_close"] > 0].copy()
    if df.empty:
        raise RuntimeError("No portfolio candidates have usable latest prices.")

    positive_scores = df["adjusted_bb_score"].clip(lower=0)
    if positive_scores.sum() <= 0:
        positive_scores = pd.Series(1.0, index=df.index)
    raw_weights = positive_scores / positive_scores.sum()
    final_weights = cap_weights(raw_weights, max_weight)

    df["target_weight"] = final_weights
    df["target_investment"] = capital * df["target_weight"]
    df["shares"] = np.floor(df["target_investment"] / df["previous_close"]).astype(int)
    df["actual_investment"] = df["shares"] * df["previous_close"]
    cash = float(capital - df["actual_investment"].sum())

    max_investment = capital * max_weight
    guard = 0
    while cash >= df["previous_close"].min() and guard < 200_000:
        guard += 1
        added = False
        order = df.sort_values("adjusted_bb_score", ascending=False).index
        for idx in order:
            price = float(df.at[idx, "previous_close"])
            if price <= cash and df.at[idx, "actual_investment"] + price <= max_investment:
                df.at[idx, "shares"] += 1
                df.at[idx, "actual_investment"] += price
                cash -= price
                added = True
                break
        if not added:
            break

    df["actual_weight"] = df["actual_investment"] / capital
    df["cash_remaining"] = cash
    df["max_weight_limit"] = max_weight
    df = df.sort_values("actual_investment", ascending=False).reset_index(drop=True)
    df.to_csv(config.data_processed_dir / "portfolio.csv", index=False)
    df.to_csv(config.reports_tables_dir / "portfolio_table.csv", index=False)
    logger.info("Allocated %.0f yen with %.0f yen cash remaining", df["actual_investment"].sum(), cash)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=int, default=None)
    parser.add_argument("--max-weight", type=float, default=None)
    args = parser.parse_args()
    allocate_portfolio(load_config(), capital=args.capital, max_weight=args.max_weight)


if __name__ == "__main__":
    main()
