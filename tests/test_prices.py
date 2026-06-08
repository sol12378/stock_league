from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.prices import repair_split_jumps


def test_repair_split_jumps_back_adjusts_prior_prices() -> None:
    repaired = repair_split_jumps(pd.Series([1000.0, 1010.0, 102.0, 103.0]))
    assert np.isclose(repaired.iloc[1], repaired.iloc[2])
    assert repaired.iloc[-1] / repaired.iloc[0] - 1 < 0.03
