from __future__ import annotations

import numpy as np
import pandas as pd

from src.report.extra_analysis import (
    REQUIRED_ABLATION_LABELS,
    aggregate_market_sector_exposure,
    build_ablation_comparison,
    build_final_selection_template,
    build_score_correlation,
    normalize_category_return_weights,
)


def test_score_correlation_is_square_with_requested_score_labels() -> None:
    scores = pd.DataFrame(
        {
            "ticker": ["1001", "1002", "1003", "1004"],
            "quality_score": [0.2, 0.4, 0.6, 0.8],
            "growth_score": [0.9, 0.7, 0.3, 0.1],
            "value_score": [0.1, 0.3, 0.5, 0.7],
        }
    )
    score_columns = ["quality_score", "growth_score", "value_score"]

    correlation = build_score_correlation(scores, score_columns=score_columns)

    assert correlation.shape == (3, 3)
    assert correlation.index.tolist() == score_columns
    assert correlation.columns.tolist() == score_columns
    assert np.allclose(np.diag(correlation), 1.0)


def test_market_and_sector_aggregation_counts_selected_twenty() -> None:
    universe = pd.DataFrame(
        {
            "ticker": [f"{code:04d}" for code in range(1000, 1030)],
            "market": ["Prime"] * 12 + ["Standard"] * 10 + ["Growth"] * 8,
            "sector": ["Tech"] * 10 + ["Consumer"] * 8 + ["Industrial"] * 7 + ["Health"] * 5,
            "selected": [True] * 20 + [False] * 10,
        }
    )

    exposure = aggregate_market_sector_exposure(
        universe,
        market_col="market",
        sector_col="sector",
        selected_col="selected",
    )

    assert set(exposure) == {"market", "sector"}
    assert exposure["market"]["universe_total"].sum() == 30
    assert exposure["sector"]["universe_total"].sum() == 30
    assert exposure["market"]["portfolio_selected"].sum() == 20
    assert exposure["sector"]["portfolio_selected"].sum() == 20
    assert exposure["market"].loc["Prime", "portfolio_selected"] == 12
    assert exposure["sector"].loc["Industrial", "portfolio_selected"] == 2


def test_category_return_weights_are_normalized() -> None:
    raw_weights = pd.Series(
        {
            "quality": 2.0,
            "growth": 1.0,
            "value": 1.0,
            "momentum": 0.0,
        }
    )

    weights = normalize_category_return_weights(raw_weights)

    assert weights.index.tolist() == raw_weights.index.tolist()
    assert np.isclose(weights.sum(), 1.0)
    assert weights.loc["quality"] == 0.5
    assert weights.loc["momentum"] == 0.0


def test_ablation_comparison_includes_required_eight_labels() -> None:
    comparison = build_ablation_comparison(
        {
            label: pd.Series([0.01, -0.005, 0.004, 0.002])
            for label in REQUIRED_ABLATION_LABELS
        }
    )

    assert len(REQUIRED_ABLATION_LABELS) == 8
    assert set(REQUIRED_ABLATION_LABELS).issubset(set(comparison["label"]))


def test_final_selection_template_tracks_selected_count() -> None:
    candidates = pd.DataFrame(
        {
            "code": [f"{code:04d}" for code in range(1300, 1325)],
            "ticker": [f"{code:04d}" for code in range(1300, 1325)],
            "company_name": [f"Company {number}" for number in range(25)],
            "final_score": np.linspace(1.0, 0.0, 25),
            "sector": ["Tech"] * 25,
        }
    )

    template = build_final_selection_template(candidates, selected_count=20)

    assert len(template) == 25
    assert template["selected"].sum() == 20
    assert template.loc[template["code"] == "1300", "selected"].item()
    assert not template.loc[template["code"] == "1324", "selected"].item()
