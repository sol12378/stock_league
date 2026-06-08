from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def cumulative_returns(returns: pd.Series) -> pd.Series:
    return (1 + returns.fillna(0)).cumprod() - 1


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    cumulative = (1 + returns).prod() - 1
    return (1 + cumulative) ** (periods_per_year / len(returns)) - 1


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    returns = returns.dropna()
    return returns.std() * np.sqrt(periods_per_year) if len(returns) > 1 else np.nan


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    ann_return = annualized_return(returns)
    ann_vol = annualized_volatility(returns)
    if not np.isfinite(ann_vol) or ann_vol == 0:
        return np.nan
    return (ann_return - risk_free_rate) / ann_vol


def max_drawdown(returns: pd.Series) -> float:
    value = (1 + returns.fillna(0)).cumprod()
    drawdown = value / value.cummax() - 1
    return float(drawdown.min()) if not drawdown.empty else np.nan


def capm_alpha_beta(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> tuple[float, float]:
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]
    if len(aligned) < 30 or aligned["benchmark"].std() == 0:
        return np.nan, np.nan
    x = sm.add_constant(aligned["benchmark"])
    model = sm.OLS(aligned["portfolio"], x).fit()
    alpha_daily = float(model.params.get("const", np.nan))
    beta = float(model.params.get("benchmark", np.nan))
    return alpha_daily * 252, beta


def information_ratio(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    active = (portfolio_returns - benchmark_returns).dropna()
    if len(active) < 2 or active.std() == 0:
        return np.nan
    return active.mean() / active.std() * np.sqrt(252)


def performance_row(
    name: str,
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, float | str]:
    row: dict[str, float | str] = {
        "name": name,
        "observations": int(returns.dropna().shape[0]),
        "cumulative_return": float((1 + returns.fillna(0)).prod() - 1),
        "annualized_return": float(annualized_return(returns)),
        "annualized_volatility": float(annualized_volatility(returns)),
        "sharpe_ratio": float(sharpe_ratio(returns)),
        "max_drawdown": float(max_drawdown(returns)),
    }
    if benchmark_returns is not None:
        alpha, beta = capm_alpha_beta(returns, benchmark_returns)
        row["capm_alpha"] = alpha
        row["capm_beta"] = beta
        row["information_ratio"] = information_ratio(returns, benchmark_returns)
    else:
        row["capm_alpha"] = np.nan
        row["capm_beta"] = np.nan
        row["information_ratio"] = np.nan
    return row
