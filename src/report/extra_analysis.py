from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

try:
    import japanize_matplotlib  # noqa: F401
except Exception:
    pass

from src.config import AppConfig, load_config
from src.portfolio.metrics import cumulative_returns, performance_row
from src.utils.logging import setup_logger
from src.utils.prices import repair_split_jumps

JAPANESE_FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"

SCORE_COLUMNS = [
    "moat_score",
    "transformation_score",
    "future_moat_score",
    "valuation_score",
    "bb_score",
    "momentum_score",
    "risk_score",
    "adjusted_bb_score",
]

REQUIRED_ABLATION_LABELS = [
    "final BEYOND BUFFETT portfolio",
    "moat_score top20",
    "transformation_score top20",
    "future_moat_score top20",
    "valuation_score top20",
    "equal_weight_final20",
    "TOPIX ETF 1306.T",
    "Nikkei 225 ^N225",
]

SCREENING_STAGE_COLUMNS = [
    "universe",
    "price_available",
    "liquid_20m_60d",
    "investment_eligible",
    "candidates_top80",
    "portfolio_selected",
]

FINAL_SELECTION_COLUMNS = [
    "code",
    "company_name",
    "score_rank",
    "selected",
    "reason",
    "risk_note",
    "qualitative_check_needed",
]

QUALITATIVE_SUMMARY_COLUMNS = [
    "code",
    "ticker",
    "company_name",
    "category",
    "business_summary",
    "issues_to_address",
    "business_risks",
    "rd_activity",
    "sustainability",
    "governance",
    "source_note",
]

REQUIRED_FIGURES = [
    "score_correlation_heatmap.png",
    "ablation_cumulative_return.png",
    "category_cumulative_return.png",
    "screening_funnel_by_market.png",
    "screening_funnel_by_sector.png",
]

REQUIRED_TABLE_COLUMNS = {
    "score_correlation.csv": ["score", *SCORE_COLUMNS],
    "screening_by_market.csv": ["market", *SCREENING_STAGE_COLUMNS],
    "screening_by_sector.csv": ["sector_33", *SCREENING_STAGE_COLUMNS],
    "category_returns.csv": [
        "category",
        "observations",
        "cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
    ],
    "ablation_performance.csv": [
        "label",
        "observations",
        "cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "capm_alpha",
        "capm_beta",
    ],
    "final_selection_reason.csv": FINAL_SELECTION_COLUMNS,
    "qualitative_edinet_summary.csv": QUALITATIVE_SUMMARY_COLUMNS,
}

if Path(JAPANESE_FONT_PATH).exists():
    font_manager.fontManager.addfont(JAPANESE_FONT_PATH)
    plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False


def _save_current(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def _write_table(df: pd.DataFrame, config: AppConfig, filename: str) -> None:
    config.data_processed_dir.mkdir(parents=True, exist_ok=True)
    config.reports_tables_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.data_processed_dir / filename, index=False)
    df.to_csv(config.reports_tables_dir / filename, index=False)


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _truthy(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float) != 0
    return series.fillna("").astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _clean_code(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def _company_name_ja_first(df: pd.DataFrame) -> pd.Series:
    fallback = pd.Series("", index=df.index, dtype=object)
    if "company_name" in df.columns:
        fallback = df["company_name"].fillna("").astype(str)
    elif "ticker" in df.columns:
        fallback = df["ticker"].fillna("").astype(str)
    elif "code" in df.columns:
        fallback = _clean_code(df["code"])

    if "company_name_ja" not in df.columns:
        return fallback

    japanese = df["company_name_ja"].fillna("").astype(str).str.strip()
    return japanese.where(japanese.str.len() > 0, fallback)


def build_score_correlation(
    scores: pd.DataFrame,
    score_columns: list[str] | tuple[str, ...] = SCORE_COLUMNS,
) -> pd.DataFrame:
    numeric_scores = pd.DataFrame(index=scores.index)
    for column in score_columns:
        if column in scores.columns:
            numeric_scores[column] = pd.to_numeric(scores[column], errors="coerce")
        else:
            numeric_scores[column] = np.nan
    return numeric_scores.corr().reindex(index=score_columns, columns=score_columns)


def _stage_masks(scores: pd.DataFrame) -> dict[str, pd.Series]:
    index = scores.index
    if "close" in scores.columns:
        close = pd.to_numeric(scores["close"], errors="coerce")
        price_available = close.notna() & (close > 0)
    elif "adj_close" in scores.columns:
        adj_close = pd.to_numeric(scores["adj_close"], errors="coerce")
        price_available = adj_close.notna() & (adj_close > 0)
    elif "price_available" in scores.columns:
        price_available = _truthy(scores["price_available"])
    else:
        price_available = pd.Series(True, index=index)

    if "liquid_20m_60d" in scores.columns:
        liquid_20m_60d = _truthy(scores["liquid_20m_60d"])
    elif "avg_trading_value_60d" in scores.columns:
        trading_value = pd.to_numeric(scores["avg_trading_value_60d"], errors="coerce").fillna(0)
        liquid_20m_60d = trading_value >= 20_000_000
    else:
        liquid_20m_60d = pd.Series(True, index=index)

    if "investment_eligible" in scores.columns:
        investment_eligible = _truthy(scores["investment_eligible"])
    else:
        investment_eligible = price_available & liquid_20m_60d

    return {
        "universe": pd.Series(True, index=index),
        "price_available": price_available,
        "liquid_20m_60d": liquid_20m_60d,
        "investment_eligible": investment_eligible,
    }


def _group_count(frame: pd.DataFrame, group_col: str) -> pd.Series:
    if frame.empty or group_col not in frame.columns:
        return pd.Series(dtype=int)
    groups = frame[group_col].fillna("Unknown").astype(str)
    return groups.value_counts(sort=False)


def _aggregate_exposure(
    scores: pd.DataFrame,
    group_col: str,
    top80: pd.DataFrame | None = None,
    portfolio: pd.DataFrame | None = None,
    selected_col: str | None = None,
) -> pd.DataFrame:
    if scores.empty or group_col not in scores.columns:
        return pd.DataFrame(
            columns=[
                "universe_total",
                "price_available",
                "liquid_20m_60d",
                "investment_eligible",
                "candidates_top80",
                "portfolio_selected",
            ]
        )

    grouped = scores[group_col].fillna("Unknown").astype(str)
    values = sorted(grouped.unique())
    masks = _stage_masks(scores)
    table = pd.DataFrame(index=pd.Index(values, name=group_col))
    table["universe_total"] = grouped.value_counts(sort=False).reindex(values, fill_value=0)
    for stage, mask in masks.items():
        if stage == "universe":
            continue
        table[stage] = grouped[mask].value_counts(sort=False).reindex(values, fill_value=0)

    if top80 is not None and not top80.empty and group_col in top80.columns:
        table["candidates_top80"] = _group_count(top80, group_col).reindex(values, fill_value=0)
    else:
        table["candidates_top80"] = 0

    if portfolio is not None and not portfolio.empty and group_col in portfolio.columns:
        table["portfolio_selected"] = _group_count(portfolio, group_col).reindex(values, fill_value=0)
    elif selected_col and selected_col in scores.columns:
        table["portfolio_selected"] = (
            grouped[_truthy(scores[selected_col])].value_counts(sort=False).reindex(values, fill_value=0)
        )
    else:
        table["portfolio_selected"] = 0

    numeric_columns = [
        "universe_total",
        "price_available",
        "liquid_20m_60d",
        "investment_eligible",
        "candidates_top80",
        "portfolio_selected",
    ]
    table[numeric_columns] = table[numeric_columns].fillna(0).astype(int)
    return table.sort_values(
        ["portfolio_selected", "candidates_top80", "investment_eligible", "universe_total"],
        ascending=False,
    )


def aggregate_market_sector_exposure(
    scores: pd.DataFrame,
    market_col: str = "market",
    sector_col: str = "sector_33",
    selected_col: str | None = None,
    top80: pd.DataFrame | None = None,
    portfolio: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    return {
        "market": _aggregate_exposure(scores, market_col, top80, portfolio, selected_col),
        "sector": _aggregate_exposure(scores, sector_col, top80, portfolio, selected_col),
    }


def normalize_category_return_weights(weights: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(weights, errors="coerce").fillna(0).clip(lower=0)
    total = numeric.sum()
    if total > 0:
        return numeric / total
    if len(numeric) == 0:
        return numeric
    return pd.Series(1 / len(numeric), index=numeric.index, dtype=float)


def _load_repaired_returns(config: AppConfig, tickers: list[str] | None = None) -> pd.DataFrame:
    prices_path = config.data_processed_dir / "prices_daily.parquet"
    if not prices_path.exists():
        return pd.DataFrame()

    prices = pd.read_parquet(prices_path)
    if prices.empty or "ticker" not in prices.columns or "date" not in prices.columns:
        return pd.DataFrame()

    prices = prices.copy()
    if "adj_close" in prices.columns and "close" in prices.columns:
        prices["price_for_return"] = prices["adj_close"].fillna(prices["close"])
    elif "adj_close" in prices.columns:
        prices["price_for_return"] = prices["adj_close"]
    elif "close" in prices.columns:
        prices["price_for_return"] = prices["close"]
    else:
        return pd.DataFrame()

    needed = set(tickers or prices["ticker"].dropna().astype(str).unique().tolist())
    prices["ticker"] = prices["ticker"].astype(str)
    pivot = (
        prices[prices["ticker"].isin(needed)]
        .pivot_table(index="date", columns="ticker", values="price_for_return", aggfunc="last")
        .sort_index()
    )
    if pivot.empty:
        return pd.DataFrame()

    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.apply(repair_split_jumps, axis=0)
    returns = pivot.pct_change().replace([np.inf, -np.inf], np.nan)
    return returns


def _weighted_returns(
    returns: pd.DataFrame,
    tickers: list[str],
    weights: pd.Series | None = None,
) -> pd.Series:
    available = [ticker for ticker in tickers if ticker in returns.columns]
    if returns.empty or not available:
        return pd.Series(dtype=float)

    if weights is None:
        normalized = pd.Series(1 / len(available), index=available, dtype=float)
    else:
        normalized = normalize_category_return_weights(weights.reindex(available).fillna(0))

    return returns[available].mul(normalized, axis=1).sum(axis=1, min_count=1).fillna(0)


def _performance_with_label(
    label: str,
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, float | str]:
    row = performance_row(label, returns, benchmark_returns)
    row["label"] = row.pop("name")
    return row


def build_ablation_comparison(
    return_series_by_label: dict[str, pd.Series],
    benchmark_returns: pd.Series | None = None,
) -> pd.DataFrame:
    rows = [
        _performance_with_label(label, series, benchmark_returns)
        for label, series in return_series_by_label.items()
    ]
    if not rows:
        return pd.DataFrame(columns=REQUIRED_TABLE_COLUMNS["ablation_performance.csv"])
    table = pd.DataFrame(rows)
    ordered = [
        "label",
        "observations",
        "cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "capm_alpha",
        "capm_beta",
        "information_ratio",
    ]
    return table[[column for column in ordered if column in table.columns]]


def build_final_selection_template(
    candidates: pd.DataFrame,
    portfolio: pd.DataFrame | None = None,
    selected_count: int | None = None,
) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(columns=FINAL_SELECTION_COLUMNS)

    table = candidates.copy()
    if "code" in table.columns:
        table["code"] = _clean_code(table["code"])
    elif "ticker" in table.columns:
        table["code"] = table["ticker"].fillna("").astype(str).str.replace(r"\.T$", "", regex=True)
    else:
        table["code"] = ""
    table["company_name"] = _company_name_ja_first(table)
    if "score_rank" not in table.columns:
        table["score_rank"] = np.arange(1, len(table) + 1)

    if portfolio is not None and not portfolio.empty:
        selected_codes = set(_clean_code(portfolio["code"])) if "code" in portfolio.columns else set()
        selected_tickers = (
            set(portfolio["ticker"].fillna("").astype(str)) if "ticker" in portfolio.columns else set()
        )
        table["selected"] = table.apply(
            lambda row: row.get("code", "") in selected_codes
            or str(row.get("ticker", "")) in selected_tickers,
            axis=1,
        )
    else:
        selected_n = selected_count if selected_count is not None else 0
        table["selected"] = False
        table.loc[table.index[:selected_n], "selected"] = True

    table["reason"] = ""
    table["risk_note"] = ""
    table["qualitative_check_needed"] = True
    return table[FINAL_SELECTION_COLUMNS]


def _score_correlation(scores: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    corr = build_score_correlation(scores)
    _write_table(corr.reset_index(names="score"), config, "score_correlation.csv")

    plt.figure(figsize=(9, 7))
    image = plt.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    plt.colorbar(image, fraction=0.046, pad=0.04)
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
    plt.yticks(range(len(corr.index)), corr.index)
    plt.title("Score Correlation")
    for row_index, score_name in enumerate(corr.index):
        for col_index, column_name in enumerate(corr.columns):
            value = corr.loc[score_name, column_name]
            if np.isfinite(value):
                plt.text(col_index, row_index, f"{value:.2f}", ha="center", va="center", fontsize=7)
    _save_current(config.reports_figures_dir / "score_correlation_heatmap.png")
    return corr


def _screening_breakdowns(
    scores: pd.DataFrame,
    top80: pd.DataFrame,
    portfolio: pd.DataFrame,
    config: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exposure = aggregate_market_sector_exposure(scores, top80=top80, portfolio=portfolio)
    market = exposure["market"].reset_index().rename(columns={"universe_total": "universe"})
    sector = exposure["sector"].reset_index().rename(columns={"universe_total": "universe"})
    market = market[REQUIRED_TABLE_COLUMNS["screening_by_market.csv"]]
    sector = sector[REQUIRED_TABLE_COLUMNS["screening_by_sector.csv"]]
    _write_table(market, config, "screening_by_market.csv")
    _write_table(sector, config, "screening_by_sector.csv")
    return market, sector


def _plot_market_funnel(table: pd.DataFrame, path: Path) -> None:
    plot = table.set_index("market")[SCREENING_STAGE_COLUMNS] if not table.empty else pd.DataFrame()
    plt.figure(figsize=(10, 5))
    if plot.empty:
        plt.text(0.5, 0.5, "No screening data", ha="center", va="center")
        plt.axis("off")
    else:
        plot.plot(kind="bar", ax=plt.gca())
        plt.yscale("log")
        plt.title("Screening Funnel by Market")
        plt.ylabel("Companies (log scale)")
        plt.xlabel("")
        plt.xticks(rotation=20, ha="right")
        plt.legend(fontsize=8, ncol=2)
    _save_current(path)


def _plot_sector_funnel(table: pd.DataFrame, path: Path) -> None:
    if not table.empty:
        plot = (
            table.sort_values(["portfolio_selected", "candidates_top80", "investment_eligible"])
            .tail(15)
            .set_index("sector_33")[["investment_eligible", "candidates_top80", "portfolio_selected"]]
        )
    else:
        plot = pd.DataFrame()

    plt.figure(figsize=(10, max(4, len(plot) * 0.4)))
    if plot.empty:
        plt.text(0.5, 0.5, "No screening data", ha="center", va="center")
        plt.axis("off")
    else:
        plot.plot(kind="barh", ax=plt.gca())
        plt.title("Screening Funnel by Sector")
        plt.xlabel("Companies")
        plt.ylabel("")
        plt.legend(fontsize=8)
    _save_current(path)


def _category_return_series(portfolio: pd.DataFrame, returns: pd.DataFrame) -> dict[str, pd.Series]:
    if portfolio.empty or returns.empty or "category" not in portfolio.columns or "ticker" not in portfolio.columns:
        return {}

    series_by_category: dict[str, pd.Series] = {}
    for category, rows in portfolio.groupby(portfolio["category"].fillna("Unknown").astype(str)):
        tickers = rows["ticker"].fillna("").astype(str).tolist()
        if "actual_weight" in rows.columns:
            weights = rows.set_index("ticker")["actual_weight"]
        else:
            weights = pd.Series(1, index=tickers, dtype=float)
        category_returns = _weighted_returns(returns, tickers, weights)
        if not category_returns.empty:
            series_by_category[str(category)] = category_returns
    return series_by_category


def _category_returns(portfolio: pd.DataFrame, returns: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    category_series = _category_return_series(portfolio, returns)
    benchmark = returns[config.topix_proxy].dropna() if config.topix_proxy in returns.columns else None

    rows = []
    for category, series in category_series.items():
        row = performance_row(category, series, benchmark)
        row["category"] = row.pop("name")
        rows.append(row)

    if rows:
        table = pd.DataFrame(rows).sort_values("cumulative_return", ascending=False)
        ordered = [
            "category",
            "observations",
            "cumulative_return",
            "annualized_return",
            "annualized_volatility",
            "sharpe_ratio",
            "max_drawdown",
            "capm_alpha",
            "capm_beta",
            "information_ratio",
        ]
        table = table[[column for column in ordered if column in table.columns]]
    else:
        table = pd.DataFrame(columns=REQUIRED_TABLE_COLUMNS["category_returns.csv"])
    _write_table(table, config, "category_returns.csv")

    cumulative = pd.DataFrame({name: cumulative_returns(series) for name, series in category_series.items()})
    plt.figure(figsize=(10, 5))
    if cumulative.empty:
        plt.text(0.5, 0.5, "No category return data", ha="center", va="center")
        plt.axis("off")
    else:
        cumulative.index = pd.to_datetime(cumulative.index)
        for column in cumulative.columns:
            plt.plot(cumulative.index, cumulative[column], label=column, linewidth=1.8)
        plt.axhline(0, color="black", linewidth=0.8)
        plt.title("Category Cumulative Return")
        plt.ylabel("Cumulative return")
        plt.legend()
    _save_current(config.reports_figures_dir / "category_cumulative_return.png")
    return table


def _top_score_tickers(scores: pd.DataFrame, score_column: str, portfolio_size: int) -> list[str]:
    if score_column not in scores.columns or "ticker" not in scores.columns:
        return []
    source = scores.copy()
    if "investment_eligible" in source.columns:
        eligible = source[_truthy(source["investment_eligible"])]
        source = eligible if len(eligible) >= portfolio_size else source
    source["_sort_score"] = pd.to_numeric(source[score_column], errors="coerce")
    return source.sort_values("_sort_score", ascending=False)["ticker"].dropna().astype(str).head(
        portfolio_size
    ).tolist()


def _ablation_return_series(
    scores: pd.DataFrame,
    portfolio: pd.DataFrame,
    returns: pd.DataFrame,
    config: AppConfig,
) -> dict[str, pd.Series]:
    series_by_label: dict[str, pd.Series] = {}

    final_tickers = portfolio["ticker"].dropna().astype(str).tolist() if "ticker" in portfolio.columns else []
    final_weights = (
        portfolio.set_index("ticker")["actual_weight"] if "actual_weight" in portfolio.columns else None
    )
    series_by_label["final BEYOND BUFFETT portfolio"] = _weighted_returns(
        returns,
        final_tickers,
        final_weights,
    )

    for score_column in [
        "moat_score",
        "transformation_score",
        "future_moat_score",
        "valuation_score",
    ]:
        label = f"{score_column} top20"
        tickers = _top_score_tickers(scores, score_column, config.portfolio_size)
        series_by_label[label] = _weighted_returns(returns, tickers)

    series_by_label["equal_weight_final20"] = _weighted_returns(returns, final_tickers)
    series_by_label["TOPIX ETF 1306.T"] = (
        returns[config.topix_proxy].fillna(0) if config.topix_proxy in returns.columns else pd.Series(dtype=float)
    )
    series_by_label["Nikkei 225 ^N225"] = (
        returns[config.nikkei].fillna(0) if config.nikkei in returns.columns else pd.Series(dtype=float)
    )
    return {label: series_by_label.get(label, pd.Series(dtype=float)) for label in REQUIRED_ABLATION_LABELS}


def _ablation_performance(
    scores: pd.DataFrame,
    portfolio: pd.DataFrame,
    returns: pd.DataFrame,
    config: AppConfig,
) -> pd.DataFrame:
    series_by_label = _ablation_return_series(scores, portfolio, returns, config)
    benchmark = returns[config.topix_proxy].dropna() if config.topix_proxy in returns.columns else None
    table = build_ablation_comparison(series_by_label, benchmark)
    _write_table(table, config, "ablation_performance.csv")

    cumulative = pd.DataFrame(
        {
            label: cumulative_returns(series)
            for label, series in series_by_label.items()
            if not series.empty
        }
    )
    plt.figure(figsize=(10, 5))
    if cumulative.empty:
        plt.text(0.5, 0.5, "No ablation return data", ha="center", va="center")
        plt.axis("off")
    else:
        cumulative.index = pd.to_datetime(cumulative.index)
        for column in cumulative.columns:
            plt.plot(cumulative.index, cumulative[column], label=column, linewidth=1.6)
        plt.axhline(0, color="black", linewidth=0.8)
        plt.title("Ablation Cumulative Return")
        plt.ylabel("Cumulative return")
        plt.legend(fontsize=8)
    _save_current(config.reports_figures_dir / "ablation_cumulative_return.png")
    return table


def _final_selection_reason(
    candidates: pd.DataFrame,
    portfolio: pd.DataFrame,
    config: AppConfig,
) -> pd.DataFrame:
    template = build_final_selection_template(candidates, portfolio)
    _write_table(template, config, "final_selection_reason.csv")
    return template


def _qualitative_edinet_summary(portfolio: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    if portfolio.empty:
        table = pd.DataFrame(columns=QUALITATIVE_SUMMARY_COLUMNS)
    else:
        table = pd.DataFrame(
            {
                "code": _clean_code(portfolio["code"]) if "code" in portfolio.columns else "",
                "ticker": portfolio["ticker"].fillna("").astype(str)
                if "ticker" in portfolio.columns
                else "",
                "company_name": _company_name_ja_first(portfolio),
                "category": portfolio["category"].fillna("").astype(str)
                if "category" in portfolio.columns
                else "",
                "business_summary": "",
                "issues_to_address": "",
                "business_risks": "",
                "rd_activity": "",
                "sustainability": "",
                "governance": "",
                "source_note": "EDINET XBRL/annual report narrative requires manual confirmation.",
            }
        )
        table = table[QUALITATIVE_SUMMARY_COLUMNS]
    _write_table(table, config, "qualitative_edinet_summary.csv")
    return table


def _tickers_for_returns(
    scores: pd.DataFrame,
    portfolio: pd.DataFrame,
    config: AppConfig,
) -> list[str]:
    tickers: set[str] = {config.topix_proxy, config.nikkei}
    if "ticker" in scores.columns:
        tickers.update(scores["ticker"].dropna().astype(str).tolist())
    if "ticker" in portfolio.columns:
        tickers.update(portfolio["ticker"].dropna().astype(str).tolist())
    return sorted(tickers)


def validate_extra_analysis_outputs(config: AppConfig) -> None:
    for filename, required_columns in REQUIRED_TABLE_COLUMNS.items():
        table_path = config.reports_tables_dir / filename
        processed_path = config.data_processed_dir / filename
        if not table_path.exists():
            raise FileNotFoundError(f"Missing extra analysis table: {table_path}")
        if not processed_path.exists():
            raise FileNotFoundError(f"Missing processed extra analysis table: {processed_path}")
        table = pd.read_csv(table_path)
        missing = set(required_columns) - set(table.columns)
        if missing:
            raise ValueError(f"{filename} missing columns: {sorted(missing)}")

    ablation = pd.read_csv(config.reports_tables_dir / "ablation_performance.csv")
    missing_labels = set(REQUIRED_ABLATION_LABELS) - set(ablation["label"])
    if missing_labels:
        raise ValueError(f"ablation_performance.csv missing labels: {sorted(missing_labels)}")

    final_selection = pd.read_csv(config.reports_tables_dir / "final_selection_reason.csv")
    candidates = _read_csv(config.data_processed_dir / "candidates_top80.csv", dtype={"code": str})
    portfolio = _read_csv(config.data_processed_dir / "portfolio.csv", dtype={"code": str})
    expected_candidates = len(candidates) if not candidates.empty else len(final_selection)
    if len(final_selection) != expected_candidates:
        raise ValueError(
            "final_selection_reason.csv row count mismatch: "
            f"expected {expected_candidates}, got {len(final_selection)}"
        )
    expected_selected = len(portfolio) if not portfolio.empty else config.portfolio_size
    selected_count = int(_truthy(final_selection["selected"]).sum())
    if selected_count != expected_selected:
        raise ValueError(
            "final_selection_reason.csv selected count mismatch: "
            f"expected {expected_selected}, got {selected_count}"
        )

    qualitative = pd.read_csv(config.reports_tables_dir / "qualitative_edinet_summary.csv")
    expected_qualitative = len(portfolio) if not portfolio.empty else config.portfolio_size
    if len(qualitative) != expected_qualitative:
        raise ValueError(
            "qualitative_edinet_summary.csv row count mismatch: "
            f"expected {expected_qualitative}, got {len(qualitative)}"
        )

    for filename in REQUIRED_FIGURES:
        path = config.reports_figures_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing extra analysis figure: {path}")
        if path.stat().st_size <= 0:
            raise ValueError(f"Extra analysis figure is empty: {path}")


def generate_extra_analysis(config: AppConfig) -> None:
    logger = setup_logger("extra_analysis", config.logs_dir)
    config.ensure_dirs()
    scores = _read_csv(config.data_processed_dir / "scores.csv", dtype={"code": str})
    candidates = _read_csv(config.data_processed_dir / "candidates_top80.csv", dtype={"code": str})
    portfolio = _read_csv(config.data_processed_dir / "portfolio.csv", dtype={"code": str})

    _score_correlation(scores, config)
    by_market, by_sector = _screening_breakdowns(scores, candidates, portfolio, config)
    _plot_market_funnel(by_market, config.reports_figures_dir / "screening_funnel_by_market.png")
    _plot_sector_funnel(by_sector, config.reports_figures_dir / "screening_funnel_by_sector.png")

    returns = _load_repaired_returns(config, _tickers_for_returns(scores, portfolio, config))
    _category_returns(portfolio, returns, config)
    _ablation_performance(scores, portfolio, returns, config)
    _final_selection_reason(candidates, portfolio, config)
    _qualitative_edinet_summary(portfolio, config)
    validate_extra_analysis_outputs(config)
    logger.info("Generated and validated extra analysis tables and figures")


def main() -> None:
    generate_extra_analysis(load_config())


if __name__ == "__main__":
    main()
