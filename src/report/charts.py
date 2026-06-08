from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

try:
    import japanize_matplotlib  # noqa: F401
except Exception:
    pass

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger

JAPANESE_FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"

if Path(JAPANESE_FONT_PATH).exists():
    font_manager.fontManager.addfont(JAPANESE_FONT_PATH)
    plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False


def _save_current(path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def generate_charts(config: AppConfig) -> None:
    logger = setup_logger("charts", config.logs_dir)
    figures = config.reports_figures_dir
    figures.mkdir(parents=True, exist_ok=True)

    returns_path = config.data_processed_dir / "portfolio_returns.csv"
    if returns_path.exists():
        returns = pd.read_csv(returns_path, parse_dates=["date"])
        plt.figure(figsize=(10, 5))
        if "portfolio_cumulative_return" in returns:
            plt.plot(returns["date"], returns["portfolio_cumulative_return"], label="Portfolio", linewidth=2.2)
        for col in returns.columns:
            if col.endswith("_cumulative_return") and col != "portfolio_cumulative_return":
                plt.plot(returns["date"], returns[col], label=col.replace("_cumulative_return", ""))
        plt.axhline(0, color="black", linewidth=0.8)
        plt.title("Cumulative Return Comparison")
        plt.ylabel("Cumulative return")
        plt.legend()
        _save_current(figures / "cumulative_return.png")

        cumulative = 1 + returns["portfolio_cumulative_return"].fillna(0)
        drawdown = cumulative / cumulative.cummax() - 1
        plt.figure(figsize=(10, 4))
        plt.fill_between(returns["date"], drawdown, 0, alpha=0.35)
        plt.plot(returns["date"], drawdown, linewidth=1.6)
        plt.title("Portfolio Drawdown")
        plt.ylabel("Drawdown")
        _save_current(figures / "drawdown.png")

    portfolio_path = config.data_processed_dir / "portfolio.csv"
    if portfolio_path.exists():
        portfolio = pd.read_csv(portfolio_path)
        sector = portfolio.groupby("sector_33")["actual_weight"].sum().sort_values(ascending=True)
        plt.figure(figsize=(8, max(4, len(sector) * 0.35)))
        sector.plot(kind="barh")
        plt.title("Sector Allocation")
        plt.xlabel("Weight")
        _save_current(figures / "sector_allocation.png")

        category = portfolio.groupby("category")["actual_weight"].sum().sort_values(ascending=False)
        plt.figure(figsize=(7, 4))
        category.plot(kind="bar")
        plt.title("Category Allocation")
        plt.ylabel("Weight")
        plt.xticks(rotation=20, ha="right")
        _save_current(figures / "category_allocation.png")

    scores_path = config.data_processed_dir / "scores.csv"
    if scores_path.exists():
        scores = pd.read_csv(scores_path)
        plt.figure(figsize=(8, 4))
        scores["adjusted_bb_score"].dropna().hist(bins=40)
        plt.title("Adjusted BB Score Distribution")
        plt.xlabel("Adjusted BB Score")
        plt.ylabel("Companies")
        _save_current(figures / "score_distribution.png")

    contribution_path = config.data_processed_dir / "contribution_by_stock.csv"
    if contribution_path.exists():
        contribution = pd.read_csv(contribution_path).sort_values("contribution").tail(20)
        if "company_name_ja" in contribution.columns:
            labels = contribution["company_name_ja"].fillna("").where(
                contribution["company_name_ja"].fillna("").astype(str).str.len() > 0,
                contribution["company_name"].fillna(contribution["ticker"]),
            )
        else:
            labels = contribution["company_name"].fillna(contribution["ticker"])
        plt.figure(figsize=(9, max(4, len(contribution) * 0.35)))
        plt.barh(labels, contribution["contribution"])
        plt.title("Contribution by Stock")
        plt.xlabel("Contribution")
        _save_current(figures / "contribution_by_stock.png")

    risk_path = config.data_processed_dir / "risk_return.csv"
    if risk_path.exists():
        risk = pd.read_csv(risk_path)
        plt.figure(figsize=(7, 5))
        plt.scatter(risk["annualized_volatility"], risk["annualized_return"], alpha=0.75)
        for _, row in risk.iterrows():
            if str(row["ticker"]) in {config.topix_proxy, config.nikkei}:
                plt.annotate(row["ticker"], (row["annualized_volatility"], row["annualized_return"]))
        plt.title("Risk Return Scatter")
        plt.xlabel("Annualized volatility")
        plt.ylabel("Annualized return")
        _save_current(figures / "risk_return_scatter.png")

    logger.info("Generated report figures in %s", figures)


def main() -> None:
    generate_charts(load_config())


if __name__ == "__main__":
    main()
