from __future__ import annotations

import numpy as np
import pandas as pd


def repair_split_jumps(series: pd.Series, low_ratio: float = 0.35, high_ratio: float = 3.0) -> pd.Series:
    """Back-adjust obvious split/reverse-split jumps that Yahoo leaves in some JP series."""
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    adjusted = numeric.copy()
    values = numeric.to_numpy()
    for idx in range(1, len(values)):
        prev = values[idx - 1]
        current = values[idx]
        if not np.isfinite(prev) or not np.isfinite(current) or prev <= 0 or current <= 0:
            continue
        ratio = current / prev
        if ratio < low_ratio or ratio > high_ratio:
            adjusted.iloc[:idx] = adjusted.iloc[:idx] * ratio
    return adjusted
