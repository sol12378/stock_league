from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

extra_analysis = pytest.importorskip("src.report.extra_analysis")

EXPECTED_SELECTED_COUNT = 20
EXPECTED_CANDIDATE_COUNT = 80


@dataclass(frozen=True)
class SyntheticConfig:
    root_dir: Path
    jpx_listed_companies_path: Path
    edinet_api_key: str
    backtest_years: int
    total_capital: int
    portfolio_size: int
    max_weight: float
    topix_proxy: str
    nikkei: str
    edinet_limit: str
    data_raw_dir: Path
    data_processed_dir: Path
    prices_raw_dir: Path
    edinet_raw_dir: Path
    reports_figures_dir: Path
    reports_tables_dir: Path
    reports_draft_dir: Path
    logs_dir: Path

    def ensure_dirs(self) -> None:
        for path in [
            self.data_raw_dir / "jpx",
            self.prices_raw_dir,
            self.edinet_raw_dir,
            self.data_processed_dir,
            self.reports_figures_dir,
            self.reports_tables_dir,
            self.reports_draft_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def _test_config(tmp_path: Path) -> SyntheticConfig:
    return SyntheticConfig(
        root_dir=tmp_path,
        jpx_listed_companies_path=tmp_path / "docs" / "data_e.xls",
        edinet_api_key="",
        backtest_years=5,
        total_capital=5_000_000,
        portfolio_size=EXPECTED_SELECTED_COUNT,
        max_weight=0.08,
        topix_proxy="1306.T",
        nikkei="^N225",
        edinet_limit="300",
        data_raw_dir=tmp_path / "data" / "raw",
        data_processed_dir=tmp_path / "data" / "processed",
        prices_raw_dir=tmp_path / "data" / "raw" / "prices",
        edinet_raw_dir=tmp_path / "data" / "raw" / "edinet",
        reports_figures_dir=tmp_path / "reports" / "figures",
        reports_tables_dir=tmp_path / "reports" / "tables",
        reports_draft_dir=tmp_path / "reports" / "draft",
        logs_dir=tmp_path / "logs",
    )


def _write_synthetic_inputs(config: SyntheticConfig) -> None:
    config.ensure_dirs()
    tickers = [f"{1300 + index}.T" for index in range(EXPECTED_CANDIDATE_COUNT)]
    selected_tickers = set(tickers[:EXPECTED_SELECTED_COUNT])

    scores = pd.DataFrame(
        {
            "code": [str(1300 + index) for index in range(EXPECTED_CANDIDATE_COUNT)],
            "ticker": tickers,
            "company_name": [f"Company {index}" for index in range(EXPECTED_CANDIDATE_COUNT)],
            "company_name_ja": [f"日本企業{index}" for index in range(EXPECTED_CANDIDATE_COUNT)],
            "market": ["Prime"] * 35 + ["Standard"] * 30 + ["Growth"] * 15,
            "sector_33": ["Services" if index % 2 else "Foods" for index in range(EXPECTED_CANDIDATE_COUNT)],
            "close": [1000 + index for index in range(EXPECTED_CANDIDATE_COUNT)],
            "avg_trading_value_60d": [30_000_000] * EXPECTED_CANDIDATE_COUNT,
            "investment_eligible": [True] * EXPECTED_CANDIDATE_COUNT,
            "category": [
                "Core Moat" if index % 4 == 0 else "Transformation Moat" if index % 4 == 1 else
                "Future Moat" if index % 4 == 2 else "Discovery"
                for index in range(EXPECTED_CANDIDATE_COUNT)
            ],
            "moat_score": np.linspace(1.0, 0.0, EXPECTED_CANDIDATE_COUNT),
            "transformation_score": np.linspace(0.9, 0.1, EXPECTED_CANDIDATE_COUNT),
            "future_moat_score": np.linspace(0.8, 0.2, EXPECTED_CANDIDATE_COUNT),
            "valuation_score": np.linspace(0.7, 0.3, EXPECTED_CANDIDATE_COUNT),
            "bb_score": np.linspace(1.2, 0.2, EXPECTED_CANDIDATE_COUNT),
            "momentum_score": np.linspace(0.6, 0.0, EXPECTED_CANDIDATE_COUNT),
            "risk_score": np.linspace(0.0, 0.6, EXPECTED_CANDIDATE_COUNT),
            "adjusted_bb_score": np.linspace(1.5, 0.1, EXPECTED_CANDIDATE_COUNT),
            "score_rank": np.arange(1, EXPECTED_CANDIDATE_COUNT + 1),
        }
    )
    portfolio = scores[scores["ticker"].isin(selected_tickers)].copy()
    portfolio["actual_weight"] = 1 / EXPECTED_SELECTED_COUNT

    scores.to_csv(config.data_processed_dir / "scores.csv", index=False)
    scores.to_csv(config.data_processed_dir / "candidates_top80.csv", index=False)
    portfolio.to_csv(config.data_processed_dir / "portfolio.csv", index=False)

    dates = pd.bdate_range("2024-01-01", periods=90)
    price_rows = []
    needed_tickers = tickers[:25] + [config.topix_proxy, config.nikkei]
    for ticker_index, ticker in enumerate(needed_tickers):
        base = 100 + ticker_index
        for day_index, date in enumerate(dates):
            close = base * (1 + 0.001 * day_index + 0.0001 * ticker_index)
            price_rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "close": close,
                    "adj_close": close,
                }
            )
    pd.DataFrame(price_rows).to_parquet(config.data_processed_dir / "prices_daily.parquet", index=False)


def _required_tables() -> dict[str, list[str]]:
    return extra_analysis.REQUIRED_TABLE_COLUMNS


def _required_figures() -> list[str]:
    return extra_analysis.REQUIRED_FIGURES


def _read_required_outputs(config: SyntheticConfig) -> dict[str, pd.DataFrame]:
    tables = {}
    for filename, columns in _required_tables().items():
        path = config.reports_tables_dir / filename
        assert path.exists(), f"Missing required table: {path}"
        table = pd.read_csv(path)
        assert set(columns).issubset(table.columns), f"{filename} missing columns"
        tables[filename] = table

    for filename in _required_figures():
        path = config.reports_figures_dir / filename
        assert path.exists(), f"Missing required figure: {path}"
        assert path.stat().st_size > 0, f"Empty required figure: {path}"

    return tables


def test_extra_analysis_outputs_have_required_paths_and_columns(tmp_path: Path) -> None:
    config = _test_config(tmp_path)
    _write_synthetic_inputs(config)

    extra_analysis.generate_extra_analysis(config)

    _read_required_outputs(config)


def test_extra_analysis_outputs_preserve_selection_and_ablation_contract(tmp_path: Path) -> None:
    config = _test_config(tmp_path)
    _write_synthetic_inputs(config)

    extra_analysis.generate_extra_analysis(config)
    tables = _read_required_outputs(config)

    ablation = tables["ablation_performance.csv"]
    assert set(extra_analysis.REQUIRED_ABLATION_LABELS).issubset(set(ablation["label"]))

    final_selection = tables["final_selection_reason.csv"]
    assert len(final_selection) == EXPECTED_CANDIDATE_COUNT
    assert final_selection["selected"].astype(bool).sum() == EXPECTED_SELECTED_COUNT

    qualitative = tables["qualitative_edinet_summary.csv"]
    assert len(qualitative) == EXPECTED_SELECTED_COUNT
