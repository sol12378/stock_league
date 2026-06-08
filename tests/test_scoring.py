from __future__ import annotations

import numpy as np
import pandas as pd

from src.screening.scoring import winsorize, zscore


def test_zscore_centers_series() -> None:
    result = zscore(pd.Series([1, 2, 3, 4, 5], dtype=float))
    assert abs(result.mean()) < 1e-12
    assert np.isclose(result.std(), 1.0)


def test_winsorize_clips_outlier() -> None:
    result = winsorize(pd.Series([1, 2, 3, 4, 1000], dtype=float), lower=0.0, upper=0.8)
    assert result.max() < 1000
