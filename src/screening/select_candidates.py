from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


ROLE_QUOTAS = {
    "変わる堀": 6,
    "生まれる堀": 7,
    "守る堀": 5,
    "分散・橋渡し枠": 2,
}

DIRECT_FUTURE_CODES = {
    "6524",
    "6627",
    "6777",
    "6387",
    "6800",
    "6617",
    "6356",
    "6920",
    "6871",
    "6861",
    "6981",
    "6648",
    "6278",
}

SECONDARY_FUTURE_CODES = {
    "8050",
    "4971",
    "9501",
    "9513",
    "7747",
    "7725",
    "7730",
    "6960",
    "6929",
}

CORE_MOAT_CODES = {"3449", "4971", "4368", "3723", "6861", "9022", "7181"}


def _bool_value(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.number)):
        return float(value) != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = 0.0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    return out


def _add_role_selection_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = _numeric_columns(
        df,
        [
            "moat_score",
            "transformation_score",
            "future_moat_score",
            "valuation_score",
            "momentum_score",
            "risk_score",
            "adjusted_bb_score",
        ],
    )
    risk_penalty = out["risk_score"].clip(lower=0)
    code = out["code"].fillna("").astype(str)
    out["role_score_transformation"] = (
        0.45 * out["adjusted_bb_score"]
        + 0.25 * out["transformation_score"]
        + 0.20 * out["valuation_score"]
        + 0.10 * out["moat_score"]
        - 0.05 * risk_penalty
    )
    out["role_score_future"] = (
        0.45 * out["adjusted_bb_score"]
        + 0.25 * out["future_moat_score"]
        + 0.10 * out["moat_score"]
        + 0.05 * out["transformation_score"]
        - 0.04 * risk_penalty
        + code.isin(DIRECT_FUTURE_CODES).astype(float) * 0.35
        + code.isin(SECONDARY_FUTURE_CODES).astype(float) * 0.15
    )
    out["role_score_moat"] = (
        0.35 * out["adjusted_bb_score"]
        + 0.35 * out["moat_score"]
        + 0.10 * out["transformation_score"]
        + 0.05 * out["future_moat_score"]
        + 0.05 * out["valuation_score"]
        - 0.05 * risk_penalty
        + out.get("category", pd.Series("", index=out.index)).fillna("").astype(str).eq("Core Moat").astype(float) * 0.25
        + code.isin(CORE_MOAT_CODES).astype(float) * 0.15
    )
    out["role_score_bridge"] = (
        0.45 * out["adjusted_bb_score"]
        + 0.20 * out["moat_score"]
        + 0.15 * out["transformation_score"]
        + 0.10 * out["future_moat_score"]
        + 0.10 * out["valuation_score"]
        - 0.05 * risk_penalty
    )
    return out


def _secondary_role(row: pd.Series, primary_role: str) -> str:
    role_scores = {
        "守る堀": row.get("moat_score", 0),
        "変わる堀": row.get("transformation_score", 0),
        "生まれる堀": row.get("future_moat_score", 0),
    }
    ordered = sorted(role_scores.items(), key=lambda item: float(item[1] or 0), reverse=True)
    for role, score in ordered:
        if role != primary_role and pd.notna(score):
            return role
    return ""


def select_candidates(config: AppConfig, portfolio_size: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    logger = setup_logger("select_candidates", config.logs_dir)
    portfolio_size = portfolio_size or config.portfolio_size
    scores = pd.read_csv(config.data_processed_dir / "scores.csv", dtype={"code": str})
    eligible = scores[scores["investment_eligible"]].copy()
    if len(eligible) < portfolio_size:
        eligible = scores[scores["close"].notna()].copy()

    top80 = eligible.sort_values("adjusted_bb_score", ascending=False).head(80).copy()
    top80 = _add_role_selection_scores(top80)
    top80.to_csv(config.data_processed_dir / "candidates_top80.csv", index=False)

    max_sector_count = max(2, math.ceil(portfolio_size * 0.25))
    max_financial_count = max(3, math.floor(portfolio_size * 0.15))
    max_power_count = max(2, math.floor(portfolio_size * 0.15))
    selected_rows: list[tuple[pd.Series, str]] = []
    selected_codes: set[str] = set()
    sector_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    financial_count = 0
    power_count = 0

    def can_add(row: pd.Series) -> bool:
        code = str(row.get("code", ""))
        if code in selected_codes:
            return False
        sector = str(row.get("sector_33", "Unknown"))
        if sector_counts.get(sector, 0) >= max_sector_count:
            return False
        if _bool_value(row.get("is_financial_like", row.get("is_financial", False))) and financial_count >= max_financial_count:
            return False
        if sector == "Electric Power and Gas" and power_count >= max_power_count:
            return False
        return True

    def add_row(row: pd.Series, role: str) -> None:
        nonlocal financial_count, power_count
        selected_rows.append((row, role))
        selected_codes.add(str(row.get("code", "")))
        sector = str(row.get("sector_33", "Unknown"))
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
        if _bool_value(row.get("is_financial_like", row.get("is_financial", False))):
            financial_count += 1
        if sector == "Electric Power and Gas":
            power_count += 1

    role_plan = [
        ("変わる堀", ROLE_QUOTAS["変わる堀"], "role_score_transformation"),
        ("生まれる堀", ROLE_QUOTAS["生まれる堀"], "role_score_future"),
        ("守る堀", ROLE_QUOTAS["守る堀"], "role_score_moat"),
        ("分散・橋渡し枠", ROLE_QUOTAS["分散・橋渡し枠"], "role_score_bridge"),
    ]

    for role, target_count, score_column in role_plan:
        for _, row in top80.sort_values([score_column, "adjusted_bb_score"], ascending=False).iterrows():
            if role_counts.get(role, 0) >= target_count:
                break
            if role == "変わる堀" and float(row.get("transformation_score", 0) or 0) < 0.50:
                continue
            if role == "生まれる堀":
                code = str(row.get("code", ""))
                if float(row.get("future_moat_score", 0) or 0) < 0.75 and code not in DIRECT_FUTURE_CODES | SECONDARY_FUTURE_CODES:
                    continue
            if role == "守る堀" and float(row.get("moat_score", 0) or 0) < 0.25 and row.get("category") != "Core Moat":
                continue
            if can_add(row):
                add_row(row, role)

    if len(selected_rows) < portfolio_size:
        for _, row in top80.iterrows():
            if len(selected_rows) >= portfolio_size:
                break
            if not can_add(row):
                continue
            add_row(row, "分散・橋渡し枠")

    portfolio = pd.DataFrame([row for row, _ in selected_rows]).head(portfolio_size).copy()
    roles = [role for _, role in selected_rows][:portfolio_size]
    portfolio["primary_role"] = roles
    portfolio["secondary_role"] = [
        _secondary_role(row, role) for (_, row), role in zip(portfolio.iterrows(), roles, strict=False)
    ]
    portfolio["needs_financial_explanation"] = portfolio["is_financial"].astype(bool)
    portfolio["is_small_cap_candidate"] = portfolio["scale_category"].fillna("").str.contains(
        "Small|Growth|PRO", case=False, regex=True
    )
    portfolio.to_csv(config.data_processed_dir / "portfolio_candidates.csv", index=False)

    summary_path = config.data_processed_dir / "screening_summary.csv"
    summary = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame(columns=["stage", "count"])
    extra = pd.DataFrame(
        [
            {"stage": "candidates_top80", "count": len(top80)},
            {"stage": "portfolio_candidates", "count": len(portfolio)},
        ]
    )
    summary = pd.concat([summary[~summary["stage"].isin(extra["stage"])], extra], ignore_index=True)
    summary.to_csv(summary_path, index=False)
    logger.info("Selected %s top80 and %s portfolio candidates", len(top80), len(portfolio))
    return top80, portfolio


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-size", type=int, default=None)
    args = parser.parse_args()
    select_candidates(load_config(), portfolio_size=args.portfolio_size)


if __name__ == "__main__":
    main()
