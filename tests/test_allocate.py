from __future__ import annotations

import pandas as pd

from src.portfolio.allocate import cap_weights


def test_cap_weights_sum_and_limit() -> None:
    weights = cap_weights(pd.Series([10.0, 2.0, 1.0, 1.0, 1.0]), max_weight=0.4)
    assert abs(weights.sum() - 1.0) < 1e-12
    assert weights.max() <= 0.4 + 1e-12
