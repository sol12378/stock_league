from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.metrics import capm_alpha_beta, max_drawdown


def test_drawdown_negative() -> None:
    returns = pd.Series([0.1, -0.2, 0.05])
    assert np.isclose(max_drawdown(returns), -0.2)


def test_capm_runs() -> None:
    benchmark = pd.Series(np.linspace(-0.01, 0.01, 80))
    portfolio = benchmark * 1.2 + 0.0001
    alpha, beta = capm_alpha_beta(portfolio, benchmark)
    assert np.isfinite(alpha)
    assert np.isclose(beta, 1.2)
