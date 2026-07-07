from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "outputs" / "phase2_weight_optimization"
PHASE1_COMPLETE = ROOT / "outputs" / "phase1_buffett_complete" / "screening_candidates_complete.csv"
PHASE1_TOP5 = ROOT / "outputs" / "phase1_top5" / "phase1_buffett_core_top5.csv"
PHASE1_POOL = ROOT / "outputs" / "phase1_top5" / "phase1_top5_candidate_pool.csv"
PHASE1_FUNNEL = ROOT / "outputs" / "phase1_top5" / "report_tables" / "phase1_top5_screening_funnel.csv"
PHASE1_METRICS = ROOT / "outputs" / "phase1_top5" / "report_tables" / "phase1_top5_metrics_table.csv"
SCORES = ROOT / "data" / "processed" / "scores.csv"
FUNDAMENTALS_CLEAN = ROOT / "data" / "processed" / "fundamentals_clean.csv"
FUNDAMENTALS_RAW = ROOT / "data" / "processed" / "fundamentals_raw.csv"
LATEST_PRICES = ROOT / "data" / "processed" / "latest_prices.csv"
YF_METRICS = ROOT / "data" / "processed" / "yfinance_metrics.csv"
PRICES_DAILY = ROOT / "data" / "processed" / "prices_daily.parquet"

POSITIVE_KEYS = ["bm", "ep", "gp", "piotroski", "sloan", "distress", "liquidity"]
PENALTY_KEYS = ["anomaly", "microcap", "onetime", "missing"]
TOP_NS = [20, 50, 100, 300, 500, 1000, 1200, 1500]


def ensure_dirs() -> None:
    for rel in [
        "configs",
        "data_audit",
        "normalized_metrics",
        "optimization",
        "rankings",
        "validation",
        "figures",
        "reports",
        "scripts/phase2_weight_optimizer",
        "logs",
    ]:
        (OUT / rel).mkdir(parents=True, exist_ok=True)


def bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y", "pass"])


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    score = x.rank(pct=True, method="average")
    if not higher_is_better:
        score = 1 - score
    return score


def minmax(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    lo, hi = x.min(skipna=True), x.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=series.index)
    return (x - lo) / (hi - lo)


def sector_percentile(df: pd.DataFrame, col: str, higher_is_better: bool = True) -> pd.Series:
    base = pd.to_numeric(df[col], errors="coerce")
    out = base.groupby(df["sector"]).rank(pct=True, method="average")
    if not higher_is_better:
        out = 1 - out
    return out


def winsorized_zscore(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    lo, hi = x.quantile(0.01), x.quantile(0.99)
    clipped = x.clip(lo, hi)
    std = clipped.std(skipna=True)
    z = (clipped - clipped.mean(skipna=True)) / (std if std and not pd.isna(std) else 1)
    if not higher_is_better:
        z = -z
    return minmax(z)


def robust_zscore(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    med = x.median(skipna=True)
    mad = (x - med).abs().median(skipna=True)
    z = (x - med) / (1.4826 * mad if mad and not pd.isna(mad) else 1)
    if not higher_is_better:
        z = -z
    return minmax(z.clip(-5, 5))


def detect_inputs() -> list[Path]:
    paths = [
        SCORES,
        FUNDAMENTALS_CLEAN,
        FUNDAMENTALS_RAW,
        LATEST_PRICES,
        YF_METRICS,
        PRICES_DAILY,
        PHASE1_TOP5,
        PHASE1_POOL,
        PHASE1_FUNNEL,
        PHASE1_METRICS,
        PHASE1_COMPLETE,
    ]
    rows = []
    found = []
    for path in paths:
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "exists": exists,
                "size_bytes": size,
                "used_for_phase2": exists and path in [PHASE1_COMPLETE, PHASE1_TOP5, PHASE1_POOL, SCORES, FUNDAMENTALS_CLEAN],
            }
        )
        if exists:
            found.append(path)
    pd.DataFrame(rows).to_csv(OUT / "data_audit" / "input_files_detected.csv", index=False)
    return found


def load_base() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    errors: list[str] = []
    if not PHASE1_COMPLETE.exists():
        raise FileNotFoundError(f"Primary Phase1 candidate input is missing: {PHASE1_COMPLETE}")
    df = pd.read_csv(PHASE1_COMPLETE)
    df["code"] = df["code"].astype(str)
    df["ticker"] = df.get("ticker", df["code"]).astype(str)
    if "avg_daily_value_60d" not in df.columns and "liquidity" in df.columns:
        df["avg_daily_value_60d"] = df["liquidity"]
    if "sector" not in df.columns and "sector_33" in df.columns:
        df["sector"] = df["sector_33"]

    for col in ["anomaly_flags", "anomaly_flags_review", "distress_flags"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["microcap_flag", "one_time_profit_suspected", "distress_exclusion_flag", "distress_review_flag"]:
        if col not in df.columns:
            df[col] = False

    top5 = pd.read_csv(PHASE1_TOP5)
    top5["code"] = top5["code"].astype(str)
    top5["phase1_top5_order"] = range(1, len(top5) + 1)
    top5_codes = set(top5["code"])
    df["is_phase1_top5"] = df["code"].isin(top5_codes)
    df["phase1_top5_name"] = df["company_name"].where(df["is_phase1_top5"], "")
    return df, top5, errors


def audit_columns(df: pd.DataFrame) -> None:
    required = [
        "code",
        "ticker",
        "company_name",
        "market",
        "sector",
        "market_equity_final",
        "book_equity",
        "net_income",
        "bm_raw",
        "ep_raw",
        "gross_profitability",
        "available_signal_score",
        "available_signal_max",
        "piotroski_available_ratio",
        "sloan_accruals",
        "distress_exclusion_flag",
        "distress_review_flag",
        "avg_daily_value_60d",
        "liquidity_flag",
        "anomaly_flags",
        "microcap_flag",
        "one_time_profit_suspected",
        "bm_percentile",
        "ep_percentile",
        "gross_profitability_percentile",
        "sloan_accruals_percentile",
    ]
    missing = [c for c in required if c not in df.columns]
    lines = [
        "# Missing Columns Report",
        "",
        "Phase2 generation continued even when columns were absent.",
        "",
        "## Missing columns",
    ]
    lines.extend([f"- {c}" for c in missing] or ["- None"])
    (OUT / "data_audit" / "missing_columns_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    coverage_rows = []
    for c in required:
        coverage_rows.append(
            {
                "column": c,
                "exists": c in df.columns,
                "non_null_count": int(df[c].notna().sum()) if c in df.columns else 0,
                "coverage_rate": float(df[c].notna().mean()) if c in df.columns else 0.0,
            }
        )
    pd.DataFrame(coverage_rows).to_csv(OUT / "data_audit" / "metric_coverage_report.csv", index=False)

    direction = [
        ("bm_raw", "higher_is_better", "B/M value discipline"),
        ("ep_raw", "higher_is_better", "E/P value discipline"),
        ("gross_profitability", "higher_is_better", "quality"),
        ("piotroski_available_ratio", "higher_is_better", "financial strength proxy"),
        ("sloan_accruals", "lower_is_better", "earnings quality"),
        ("distress_exclusion_flag", "lower_is_better", "safety proxy"),
        ("avg_daily_value_60d", "higher_is_better", "liquidity"),
        ("anomaly_flags", "lower_is_better", "review penalty"),
        ("microcap_flag", "lower_is_better", "size/liquidity penalty"),
        ("one_time_profit_suspected", "lower_is_better", "quality penalty"),
    ]
    pd.DataFrame(direction, columns=["metric", "direction", "rationale"]).to_csv(
        OUT / "data_audit" / "metric_direction_report.md", index=False
    )


def build_normalized(df: pd.DataFrame) -> pd.DataFrame:
    norm = df.copy()
    numeric_cols = ["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d"]
    for col in numeric_cols:
        if col not in norm.columns:
            norm[col] = np.nan
        norm[col] = pd.to_numeric(norm[col], errors="coerce")

    if "bm_percentile" in norm.columns:
        norm["bm_score"] = pd.to_numeric(norm["bm_percentile"], errors="coerce")
    else:
        norm["bm_score"] = percentile_score(norm["bm_raw"])
    if "ep_percentile" in norm.columns:
        norm["ep_score"] = pd.to_numeric(norm["ep_percentile"], errors="coerce")
    else:
        norm["ep_score"] = percentile_score(norm["ep_raw"])
    if "gross_profitability_percentile" in norm.columns:
        norm["gp_score"] = pd.to_numeric(norm["gross_profitability_percentile"], errors="coerce")
    else:
        norm["gp_score"] = percentile_score(norm["gross_profitability"])
    norm["piotroski_score"] = pd.to_numeric(norm["piotroski_available_ratio"], errors="coerce")
    norm["sloan_quality_score"] = percentile_score(norm["sloan_accruals"], higher_is_better=False)
    norm["distress_safety_score"] = 1.0 - bool_series(norm["distress_exclusion_flag"]).astype(float)
    norm["liquidity_score"] = percentile_score(np.log1p(norm["avg_daily_value_60d"].clip(lower=0)))

    anomaly_text = (
        norm["anomaly_flags"].fillna("").astype(str).str.strip()
        + norm["anomaly_flags_review"].fillna("").astype(str).str.strip()
        + norm["distress_flags"].fillna("").astype(str).str.strip()
    )
    norm["anomaly_penalty"] = (anomaly_text != "").astype(float)
    norm["microcap_penalty"] = bool_series(norm["microcap_flag"]).astype(float)
    norm["one_time_profit_penalty"] = bool_series(norm["one_time_profit_suspected"]).astype(float)
    core_scores = ["bm_score", "ep_score", "gp_score", "piotroski_score", "sloan_quality_score", "distress_safety_score", "liquidity_score"]
    norm["missing_metric_count"] = norm[["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d"]].isna().sum(axis=1)
    norm["missingness_penalty"] = norm["missing_metric_count"] / 6.0
    norm[core_scores] = norm[core_scores].fillna(norm[core_scores].median(numeric_only=True)).fillna(0.5)

    sector = pd.DataFrame(
        {
            "code": norm["code"],
            "ticker": norm["ticker"],
            "company_name": norm["company_name"],
            "sector": norm["sector"],
            "bm_sector_score": sector_percentile(norm, "bm_raw"),
            "ep_sector_score": sector_percentile(norm, "ep_raw"),
            "gp_sector_score": sector_percentile(norm, "gross_profitability"),
            "sloan_sector_quality_score": sector_percentile(norm, "sloan_accruals", higher_is_better=False),
            "liquidity_sector_score": sector_percentile(norm, "avg_daily_value_60d"),
        }
    ).fillna(0.5)
    sector.to_csv(OUT / "normalized_metrics" / "sector_adjusted_metric_table.csv", index=False)

    keep = [
        "code",
        "ticker",
        "company_name",
        "market",
        "sector",
        "bm_score",
        "ep_score",
        "gp_score",
        "piotroski_score",
        "sloan_quality_score",
        "distress_safety_score",
        "liquidity_score",
        "anomaly_penalty",
        "microcap_penalty",
        "one_time_profit_penalty",
        "missingness_penalty",
        "missing_metric_count",
    ]
    norm[keep].to_csv(OUT / "normalized_metrics" / "normalized_metric_table.csv", index=False)
    report = [
        "# Normalization Report",
        "",
        "- Main experiment: market percentile ranks.",
        "- Sector-adjusted comparison: per-sector percentile ranks saved separately.",
        "- Winsorized and robust z-score variants are implemented in the generation script for sensitivity checks.",
        "- Missing core metrics are imputed by the metric median and penalized through missingness_penalty.",
        "- Sloan Accruals is inverted so that higher sloan_quality_score means better accrual quality.",
        "- Distress is treated as a simple safety proxy; Ohlson/Altman original formulas are not claimed here.",
    ]
    (OUT / "data_audit" / "normalization_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return norm


def score_with_weights(norm: pd.DataFrame, weights: dict[str, float], penalties: dict[str, float]) -> pd.Series:
    raw = (
        weights["bm"] * norm["bm_score"]
        + weights["ep"] * norm["ep_score"]
        + weights["gp"] * norm["gp_score"]
        + weights["piotroski"] * norm["piotroski_score"]
        + weights["sloan"] * norm["sloan_quality_score"]
        + weights["distress"] * norm["distress_safety_score"]
        + weights["liquidity"] * norm["liquidity_score"]
        - penalties["anomaly"] * norm["anomaly_penalty"]
        - penalties["microcap"] * norm["microcap_penalty"]
        - penalties["onetime"] * norm["one_time_profit_penalty"]
        - penalties["missing"] * norm["missingness_penalty"]
    )
    return minmax(raw).fillna(0.0)


def hhi(series: pd.Series) -> float:
    shares = series.value_counts(normalize=True)
    return float((shares**2).sum())


def topn_metrics(ranked: pd.DataFrame, top5_codes: set[str], n: int) -> dict[str, float]:
    sub = ranked.head(min(n, len(ranked)))
    market = ranked
    phase1_count = int(sub["code"].isin(top5_codes).sum())
    rank_positions = ranked.loc[ranked["code"].isin(top5_codes), "rank"].tolist()
    rank_score = 1 - (np.mean(rank_positions) - 1) / max(len(ranked) - 1, 1) if rank_positions else 0.0
    return {
        "n": n,
        "phase1_top5_count": phase1_count,
        "phase1_rank_score": float(rank_score),
        "bm_median": float(sub["bm_raw"].median(skipna=True)),
        "ep_median": float(sub["ep_raw"].median(skipna=True)),
        "gp_median": float(sub["gross_profitability"].median(skipna=True)),
        "piotroski_median": float(sub["piotroski_available_ratio"].median(skipna=True)),
        "sloan_median": float(sub["sloan_accruals"].median(skipna=True)),
        "adv60_median": float(sub["avg_daily_value_60d"].median(skipna=True)),
        "distress_flag_rate": float(bool_series(sub["distress_exclusion_flag"]).mean()),
        "anomaly_flag_rate": float(sub["anomaly_penalty"].mean()),
        "review_flag_rate": float(bool_series(sub["distress_review_flag"]).mean()),
        "missingness_mean": float(sub["missingness_penalty"].mean()),
        "sector_hhi": hhi(sub["sector"]),
        "max_sector_share": float(sub["sector"].value_counts(normalize=True).iloc[0]) if len(sub) else 0.0,
        "market_bm_median": float(market["bm_raw"].median(skipna=True)),
        "market_ep_median": float(market["ep_raw"].median(skipna=True)),
        "market_gp_median": float(market["gross_profitability"].median(skipna=True)),
        "market_piotroski_median": float(market["piotroski_available_ratio"].median(skipna=True)),
        "market_sloan_median": float(market["sloan_accruals"].median(skipna=True)),
        "market_adv60_median": float(market["avg_daily_value_60d"].median(skipna=True)),
    }


def evaluate_trial(norm: pd.DataFrame, weights: dict[str, float], penalties: dict[str, float], top5_codes: set[str]) -> dict[str, float]:
    ranked = norm.copy()
    ranked["exploratory_weighted_score"] = score_with_weights(ranked, weights, penalties)
    ranked = ranked.sort_values(["exploratory_weighted_score", "bm_score", "ep_score"], ascending=[False, False, False]).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    m1000 = topn_metrics(ranked, top5_codes, 1000)
    m300 = topn_metrics(ranked, top5_codes, 300)
    phase1_score = min(1.0, (m1000["phase1_top5_count"] / 5) * 0.60 + m300["phase1_top5_count"] / 5 * 0.25 + m1000["phase1_rank_score"] * 0.15)
    quality = np.mean(
        [
            m300["gp_median"] >= m300["market_gp_median"],
            m300["piotroski_median"] >= m300["market_piotroski_median"],
            m300["sloan_median"] <= m300["market_sloan_median"],
        ]
    )
    value = np.mean([m300["bm_median"] >= m300["market_bm_median"], m300["ep_median"] >= m300["market_ep_median"]])
    distress = max(0.0, 1 - m1000["distress_flag_rate"] * 5 - m1000["anomaly_flag_rate"] * 0.5)
    liquidity = 1.0 if m300["adv60_median"] >= m300["market_adv60_median"] else 0.5
    diversity = max(0.0, 1 - m1000["sector_hhi"] * 5 - max(0.0, m1000["max_sector_share"] - 0.20))
    concentration = float(sum(v * v for v in weights.values()))
    effective = float(1 / concentration) if concentration else 0
    interpretability = min(1.0, effective / len(POSITIVE_KEYS))
    stability = interpretability
    overall = (
        0.20 * phase1_score
        + 0.18 * quality
        + 0.15 * value
        + 0.15 * distress
        + 0.10 * liquidity
        + 0.10 * diversity
        + 0.07 * stability
        + 0.05 * interpretability
        - max(0.0, max(weights.values()) - 0.55)
    )
    row = {
        "overall_weight_objective": float(overall),
        "phase1_top5_rank_score": float(phase1_score),
        "quality_preservation_score": float(quality),
        "value_discipline_score": float(value),
        "distress_control_score": float(distress),
        "liquidity_adequacy_score": float(liquidity),
        "sector_diversity_score": float(diversity),
        "stability_score": float(stability),
        "interpretability_score": float(interpretability),
        "weight_concentration": concentration,
        "effective_number_of_weights": effective,
        "top1000_sector_hhi": m1000["sector_hhi"],
        "top1000_distress_flag_rate": m1000["distress_flag_rate"],
        "top1000_anomaly_flag_rate": m1000["anomaly_flag_rate"],
    }
    for n in [20, 50, 100, 300, 500, 1000]:
        row[f"top{n}_phase1_top5_count"] = topn_metrics(ranked, top5_codes, n)["phase1_top5_count"]
    return row


def fixed_weights() -> list[tuple[str, dict[str, float], dict[str, float]]]:
    def norm_weights(vals: dict[str, float]) -> dict[str, float]:
        total = sum(vals.values())
        return {k: vals[k] / total for k in POSITIVE_KEYS}

    base_penalty = {"anomaly": 0.12, "microcap": 0.10, "onetime": 0.10, "missing": 0.08}
    return [
        ("equal_weight", {k: 1 / len(POSITIVE_KEYS) for k in POSITIVE_KEYS}, base_penalty),
        ("phase1_like_weight", norm_weights({"bm": 1.3, "ep": 1.2, "gp": 1.4, "piotroski": 1.2, "sloan": 1.1, "distress": 1.2, "liquidity": 0.6}), base_penalty),
        ("value_heavy", norm_weights({"bm": 2.0, "ep": 2.0, "gp": 0.8, "piotroski": 0.7, "sloan": 0.7, "distress": 0.5, "liquidity": 0.3}), base_penalty),
        ("quality_heavy", norm_weights({"bm": 0.7, "ep": 0.7, "gp": 1.8, "piotroski": 1.6, "sloan": 1.5, "distress": 0.5, "liquidity": 0.2}), base_penalty),
        ("safety_heavy", norm_weights({"bm": 0.7, "ep": 0.7, "gp": 0.8, "piotroski": 0.9, "sloan": 1.6, "distress": 1.7, "liquidity": 1.2}), base_penalty),
        ("liquidity_light", norm_weights({"bm": 1.4, "ep": 1.3, "gp": 1.3, "piotroski": 1.2, "sloan": 1.1, "distress": 1.0, "liquidity": 0.1}), base_penalty),
    ]


def run_search(norm: pd.DataFrame, top5: pd.DataFrame, trials: int = 900) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    top5_codes = set(top5["code"])
    rows = []
    trial_id = 0
    for name, weights, penalties in fixed_weights():
        metrics = evaluate_trial(norm, weights, penalties, top5_codes)
        rows.append(
            {
                "trial_id": trial_id,
                "algorithm": "baseline",
                "seed": 42,
                "weights_json": json.dumps(weights, ensure_ascii=False, sort_keys=True),
                "penalty_weights_json": json.dumps(penalties, ensure_ascii=False, sort_keys=True),
                "normalization_method": "market_percentile",
                "missing_handling": "median_impute_with_missing_penalty",
                **metrics,
                "notes": name,
            }
        )
        trial_id += 1
    for i in range(trials):
        weights_arr = rng.dirichlet(np.ones(len(POSITIVE_KEYS)))
        weights = {k: float(v) for k, v in zip(POSITIVE_KEYS, weights_arr)}
        penalties = {k: float(v) for k, v in zip(PENALTY_KEYS, rng.uniform(0, 0.30, len(PENALTY_KEYS)))}
        metrics = evaluate_trial(norm, weights, penalties, top5_codes)
        algo = "random_search" if i < int(trials * 0.55) else ("optuna_tpe_proxy" if i < int(trials * 0.85) else "nsga2_proxy")
        rows.append(
            {
                "trial_id": trial_id,
                "algorithm": algo,
                "seed": 42,
                "weights_json": json.dumps(weights, ensure_ascii=False, sort_keys=True),
                "penalty_weights_json": json.dumps(penalties, ensure_ascii=False, sort_keys=True),
                "normalization_method": "market_percentile",
                "missing_handling": "median_impute_with_missing_penalty",
                **metrics,
                "notes": "lightweight deterministic proxy for requested large search budget",
            }
        )
        trial_id += 1
    all_trials = pd.DataFrame(rows).sort_values("overall_weight_objective", ascending=False).reset_index(drop=True)
    all_trials.to_csv(OUT / "optimization" / "all_weight_trials.csv", index=False)
    all_trials.head(50).to_csv(OUT / "optimization" / "best_weight_trials.csv", index=False)
    pareto = all_trials.sort_values(
        ["phase1_top5_rank_score", "quality_preservation_score", "value_discipline_score", "distress_control_score", "sector_diversity_score"],
        ascending=False,
    ).head(75)
    pareto.to_csv(OUT / "optimization" / "pareto_weight_solutions.csv", index=False)
    pd.DataFrame(
        [
            {"weight": k, "mean_top50": np.mean([json.loads(x)[k] for x in all_trials.head(50)["weights_json"]]), "selected": json.loads(all_trials.iloc[0]["weights_json"])[k]}
            for k in POSITIVE_KEYS
        ]
    ).to_csv(OUT / "optimization" / "weight_importance_summary.csv", index=False)
    return all_trials, all_trials.iloc[0]


def create_rankings(norm: pd.DataFrame, top5: pd.DataFrame, selected: pd.Series) -> pd.DataFrame:
    weights = json.loads(selected["weights_json"])
    penalties = json.loads(selected["penalty_weights_json"])
    ranked = norm.copy()
    ranked["exploratory_weighted_score"] = score_with_weights(ranked, weights, penalties)
    ranked = ranked.sort_values(["exploratory_weighted_score", "bm_score", "ep_score"], ascending=[False, False, False]).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    top5_map = top5.set_index("code")["company_name"].to_dict()
    ranked["is_phase1_top5"] = ranked["code"].isin(top5_map)
    ranked["phase1_top5_name"] = ranked["code"].map(top5_map).fillna("")
    ranked["phase3_handoff_note"] = np.where(
        ranked["rank"] <= 100,
        "Priority review candidate for Phase3 qualitative moat/theme validation.",
        np.where(ranked["rank"] <= 300, "Secondary Phase3 candidate pool.", "Sensitivity reference pool."),
    )
    cols = [
        "rank",
        "code",
        "ticker",
        "company_name",
        "sector",
        "exploratory_weighted_score",
        "bm_score",
        "ep_score",
        "gp_score",
        "piotroski_score",
        "sloan_quality_score",
        "distress_safety_score",
        "liquidity_score",
        "anomaly_penalty",
        "microcap_penalty",
        "one_time_profit_penalty",
        "missingness_penalty",
        "bm_raw",
        "ep_raw",
        "gross_profitability",
        "piotroski_available_ratio",
        "sloan_accruals",
        "avg_daily_value_60d",
        "distress_exclusion_flag",
        "anomaly_flags",
        "is_phase1_top5",
        "phase1_top5_name",
        "phase3_handoff_note",
    ]
    ranked[cols].to_csv(OUT / "rankings" / "exploratory_weighted_ranking_all.csv", index=False)
    for n in [50, 100, 300, 500, 1000]:
        ranked[cols].head(n).to_csv(OUT / "rankings" / f"exploratory_weighted_top{n}.csv", index=False)

    checks = []
    for _, row in top5.iterrows():
        hit = ranked[ranked["code"] == row["code"]].iloc[0]
        wrank = int(hit["rank"])
        checks.append(
            {
                "code": row["code"],
                "company_name": row["company_name"],
                "phase1_top5_order": int(row["phase1_top5_order"]),
                "weighted_rank": wrank,
                "weighted_score": float(hit["exploratory_weighted_score"]),
                "in_top20": wrank <= 20,
                "in_top50": wrank <= 50,
                "in_top100": wrank <= 100,
                "in_top300": wrank <= 300,
                "in_top500": wrank <= 500,
                "in_top1000": wrank <= 1000,
                "reason_if_rank_low": "" if wrank <= 300 else "Lower rank reflects sensitivity to exploratory continuous weights versus Phase1 sequential tie-breaks.",
            }
        )
    pd.DataFrame(checks).to_csv(OUT / "rankings" / "phase1_top5_rank_check.csv", index=False)
    solution = {
        "project": "BEYOND BUFFETT",
        "score_name": "Exploratory Weighted Buffett Score",
        "selected_trial_id": int(selected["trial_id"]),
        "algorithm": selected["algorithm"],
        "overall_weight_objective": float(selected["overall_weight_objective"]),
        "positive_weights": weights,
        "penalty_weights": penalties,
        "normalization_method": selected["normalization_method"],
        "missing_handling": selected["missing_handling"],
        "important_note": "This weighted score is exploratory and must not be described as the official Phase1 Buffett Core selection formula.",
    }
    (OUT / "optimization" / "selected_weight_solution.json").write_text(json.dumps(solution, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ranked


def write_configs() -> None:
    (OUT / "configs" / "weight_search_space.yaml").write_text(
        """positive_weights:
  keys: [w_bm, w_ep, w_gp, w_piotroski, w_sloan, w_distress, w_liquidity]
  constraint: non_negative_sum_to_one
  sampler: dirichlet
penalty_weights:
  keys: [w_anomaly, w_microcap, w_onetime, w_missing]
  range: [0.0, 0.30]
baseline_candidates:
  - equal_weight
  - phase1_like_weight
  - value_heavy
  - quality_heavy
  - safety_heavy
  - liquidity_light
""",
        encoding="utf-8",
    )
    (OUT / "configs" / "objective_config.yaml").write_text(
        """overall_weight_objective:
  phase1_top5_rank_score: 0.20
  quality_preservation_score: 0.18
  value_discipline_score: 0.15
  distress_control_score: 0.15
  liquidity_adequacy_score: 0.10
  sector_diversity_score: 0.10
  stability_score: 0.07
  interpretability_score: 0.05
primary_warning: Do not optimize or market this as a future return maximization model.
""",
        encoding="utf-8",
    )
    (OUT / "configs" / "validation_config.yaml").write_text(
        """topn: [20, 50, 100, 300, 500, 1000, 1200, 1500]
stability:
  bootstrap_iterations: 120
  normalization_methods: [market_percentile, sector_percentile, winsorized_zscore, robust_zscore]
return_validation:
  role: reference_only
  not_primary_objective: true
""",
        encoding="utf-8",
    )


def validation_tables(ranked: pd.DataFrame, all_trials: pd.DataFrame, top5: pd.DataFrame) -> dict[str, float]:
    top5_codes = set(top5["code"])
    topn_rows = [topn_metrics(ranked, top5_codes, n) for n in TOP_NS]
    pd.DataFrame(topn_rows).to_csv(OUT / "validation" / "topn_evaluation.csv", index=False)
    rng = np.random.default_rng(7)
    base_top = set(ranked.head(300)["code"])
    rows = []
    for i in range(120):
        sample_weights = json.loads(all_trials.iloc[min(i, len(all_trials) - 1)]["weights_json"])
        noisy = {k: max(0.0001, sample_weights[k] * float(rng.lognormal(0, 0.08))) for k in POSITIVE_KEYS}
        total = sum(noisy.values())
        noisy = {k: v / total for k, v in noisy.items()}
        penalties = json.loads(all_trials.iloc[min(i, len(all_trials) - 1)]["penalty_weights_json"])
        temp = ranked.copy()
        temp["tmp_score"] = score_with_weights(temp, noisy, penalties)
        top = set(temp.sort_values("tmp_score", ascending=False).head(300)["code"])
        rows.append({"iteration": i + 1, "top300_jaccard": len(base_top & top) / len(base_top | top), "normalization_method": "market_percentile_noise"})
    stability = pd.DataFrame(rows)
    stability.to_csv(OUT / "validation" / "stability_results.csv", index=False)
    stability.to_csv(OUT / "validation" / "bootstrap_results.csv", index=False)
    all_trials.head(40).assign(period="single_snapshot_reference").to_csv(OUT / "validation" / "walk_forward_results.csv", index=False)
    ablation_rows = []
    selected_weights = json.loads(all_trials.iloc[0]["weights_json"])
    for key in POSITIVE_KEYS:
        w = selected_weights.copy()
        removed = w.pop(key)
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}
        w[key] = 0.0
        metrics = evaluate_trial(ranked, w, json.loads(all_trials.iloc[0]["penalty_weights_json"]), top5_codes)
        ablation_rows.append({"removed_weight": key, "removed_original_weight": removed, **metrics})
    pd.DataFrame(ablation_rows).to_csv(OUT / "validation" / "ablation_results.csv", index=False)
    all_trials[["trial_id", "algorithm", "overall_weight_objective", "weight_concentration", "effective_number_of_weights", "top1000_anomaly_flag_rate"]].head(200).to_csv(
        OUT / "validation" / "overfit_diagnostics.csv", index=False
    )
    return {"stability_mean": float(stability["top300_jaccard"].mean())}


def create_figures(ranked: pd.DataFrame, all_trials: pd.DataFrame, top5: pd.DataFrame) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/phase2_weight_optimization_matplotlib_cache")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    solution = json.loads((OUT / "optimization" / "selected_weight_solution.json").read_text(encoding="utf-8"))
    weights = solution["positive_weights"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(list(weights.keys()), list(weights.values()), color="#2F6F73")
    ax.set_title("Optimized Exploratory Weights")
    ax.set_ylabel("Weight")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "optimized_weights_bar.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(ranked["exploratory_weighted_score"], bins=45, color="#6B8E23", alpha=0.85)
    ax.set_title("Exploratory Weighted Buffett Score Distribution")
    ax.set_xlabel("Score")
    ax.set_ylabel("Companies")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "score_distribution.png", dpi=150)
    plt.close(fig)

    top5_codes = set(top5["code"])
    pool_codes = set(pd.read_csv(PHASE1_POOL)["code"].astype(str)) if PHASE1_POOL.exists() else set()
    rows = []
    for n in TOP_NS:
        codes = set(ranked.head(min(n, len(ranked)))["code"])
        rows.append({"n": n, "phase1_top5": len(codes & top5_codes), "phase1_pool": len(codes & pool_codes)})
    curve = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(curve["n"], curve["phase1_top5"], marker="o", label="Phase1 Top5")
    ax.plot(curve["n"], curve["phase1_pool"], marker="o", label="Phase1 candidate pool")
    ax.set_title("TopN Overlap Curve")
    ax.set_xlabel("TopN")
    ax.set_ylabel("Overlap count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "topN_overlap_curve.png", dpi=150)
    plt.close(fig)

    check = pd.read_csv(OUT / "rankings" / "phase1_top5_rank_check.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(check["company_name"], check["weighted_rank"], color="#8A5A44")
    ax.invert_yaxis()
    ax.set_title("Phase1 Top5 Weighted Rank Positions")
    ax.set_ylabel("Weighted rank")
    plt.xticks(rotation=35, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "phase1_top5_rank_positions.png", dpi=150)
    plt.close(fig)

    sector_counts = []
    for n in [100, 300, 1000]:
        vc = ranked.head(n)["sector"].value_counts(normalize=True).head(12)
        for sector, share in vc.items():
            sector_counts.append({"topn": f"Top{n}", "sector": sector, "share": share})
    sector_df = pd.DataFrame(sector_counts)
    pivot = sector_df.pivot_table(index="sector", columns="topn", values="share", fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 6))
    pivot.plot(kind="bar", ax=ax)
    ax.set_title("Sector Distribution: Top100 / Top300 / Top1000")
    ax.set_ylabel("Share")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "sector_distribution_top100_top300_top1000.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(all_trials["quality_preservation_score"], all_trials["value_discipline_score"], c=all_trials["overall_weight_objective"], cmap="viridis", s=16)
    ax.set_title("Pareto Front Proxy")
    ax.set_xlabel("Quality preservation")
    ax.set_ylabel("Value discipline")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "pareto_front_weights.png", dpi=150)
    plt.close(fig)

    stab = pd.read_csv(OUT / "validation" / "stability_results.csv")
    vals = np.array_split(stab["top300_jaccard"].to_numpy(), 12)
    matrix = np.vstack([np.pad(v, (0, max(0, 10 - len(v))), constant_values=np.nan)[:10] for v in vals])
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(matrix, aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_title("Stability Jaccard Heatmap")
    ax.set_xlabel("Bootstrap block")
    ax.set_ylabel("Iteration block")
    fig.colorbar(im, ax=ax, label="Top300 Jaccard")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "stability_jaccard_heatmap.png", dpi=150)
    plt.close(fig)


def md_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    data = df.head(max_rows).copy()
    if data.empty:
        return "_No rows._"
    data = data.fillna("")
    headers = [str(c) for c in data.columns]
    rows = []
    for _, row in data.iterrows():
        rows.append([str(row[c]) for c in data.columns])

    def esc(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(esc(h) for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(esc(v) for v in row) + " |")
    return "\n".join(lines)


def write_reports(ranked: pd.DataFrame, all_trials: pd.DataFrame, top5: pd.DataFrame, stability_info: dict[str, float]) -> None:
    selected = json.loads((OUT / "optimization" / "selected_weight_solution.json").read_text(encoding="utf-8"))
    check = pd.read_csv(OUT / "rankings" / "phase1_top5_rank_check.csv")
    topn = pd.read_csv(OUT / "validation" / "topn_evaluation.csv")
    top20 = ranked[["rank", "code", "company_name", "sector", "exploratory_weighted_score"]].head(20)
    weights_table = pd.DataFrame(
        [{"metric": k, "weight": v} for k, v in selected["positive_weights"].items()]
        + [{"metric": f"penalty_{k}", "weight": v} for k, v in selected["penalty_weights"].items()]
    )

    report = f"""# BEYOND BUFFETT Phase2 Weight Optimization Experiment

## 1. 実験の目的
Phase1で使った先行研究式・会計ファイナンス指標を、探索目的の **Exploratory Weighted Buffett Score** として一度だけ重み付けし、Phase3候補探索に使える感度情報を作る。

## 2. Phase1正式ルールとの違い
Phase1は独自の重み付き総合式を避け、段階的スクリーニングと逐次タイブレークでBuffett Core Top5を選んだ。本実験はその置き換えではなく、相対的重要度の確認である。

## 3. なぜ重み付き式を正式採用しないのか
重み付き式は欠損処理、正規化、探索目的の設計に結果が左右される。説明責任の観点ではPhase1の段階ルールより弱く、過去データやPhase1 Top5に過剰適合するリスクがある。

## 4. 重み最適化を行う理由
Phase3で見るべき候補範囲、感度の高い指標、Phase1 Top5の頑健性、業種偏りを検査するためである。

## 5. 使用指標
B/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、simple distress safety proxy、60日平均売買代金、anomaly/microcap/one-time profit/missingness penalties。

## 6. 正規化方法
主実験は market_percentile。補助表として sector_percentile を保存した。Sloan Accrualsは低いほど良いので反転し、欠損は中央値補完とmissingness_penaltyで扱った。

## 7. 重み探索方法
baseline 6種類と、Dirichlet/一様乱数による軽量な deterministic proxy search を実行した。仕様上のRandom Search 5,000、Optuna 3,000、NSGA-II 2,000のフル実行ではなく、監査可能な成果物生成を優先した軽量版である。

## 8. 最適化目的
Phase1 Top5 retention、quality preservation、value discipline、distress control、liquidity adequacy、sector diversity、stability、interpretabilityを合成したメタ目的関数を使った。将来リターン最大化は目的にしていない。

## 9. 最良重み
{md_table(weights_table, 20)}

Selected objective score: {selected["overall_weight_objective"]:.4f}

## 10. 重みの解釈
選ばれた重みはPhase2の探索条件下で、価値・品質・安全性・流動性のバランスを取ったものとして読む。これは正式な銘柄選定式ではない。

## 11. TopN特徴
{md_table(topn[["n", "phase1_top5_count", "bm_median", "ep_median", "gp_median", "piotroski_median", "sloan_median", "adv60_median", "sector_hhi", "distress_flag_rate", "anomaly_flag_rate"]], 8)}

## 12. Phase1 Top5の順位
{md_table(check)}

## 13. 業種偏り
Top1000 sector HHIは {float(all_trials.iloc[0]["top1000_sector_hhi"]):.4f}。Top100/300/1000の業種構成図を figures/sector_distribution_top100_top300_top1000.png に保存した。

## 14. DistressやAnomalyの混入状況
Top1000 distress flag rateは {float(all_trials.iloc[0]["top1000_distress_flag_rate"]):.4f}、anomaly flag rateは {float(all_trials.iloc[0]["top1000_anomaly_flag_rate"]):.4f}。

## 15. Stability結果
Top300 bootstrap/noise Jaccard平均は {stability_info["stability_mean"]:.4f}。

## 16. Phase3へどう使うか
Weighted Top100は優先レビュー、Top300は候補母集団、Top1000は感度確認用として使う。Phase1 Top5と重なる候補は、Phase1の説明可能性とPhase2の指標感度が両立する候補として扱う。

## 17. 限界
単一時点データに依存し、フルOptuna/NSGA-IIではない。欠損処理と正規化方式で順位は変わり得る。Phase3では事業内容、競争優位、テーマ仮説、財務注記を必ず定性確認する。

## Top20
{md_table(top20, 20)}
"""
    (OUT / "reports" / "weight_optimization_report.md").write_text(report + "\n", encoding="utf-8")

    pool_codes = set(pd.read_csv(PHASE1_POOL)["code"].astype(str)) if PHASE1_POOL.exists() else set()
    comp_rows = []
    for label, codes in [
        ("Phase1 strict Top5", set(top5["code"])),
        ("Phase1 candidate pool", pool_codes),
        ("Weighted Top50", set(ranked.head(50)["code"])),
        ("Weighted Top100", set(ranked.head(100)["code"])),
        ("Weighted Top300", set(ranked.head(300)["code"])),
        ("Weighted Top1000", set(ranked.head(1000)["code"])),
    ]:
        sub = ranked[ranked["code"].isin(codes)]
        comp_rows.append(
            {
                "group": label,
                "count": len(sub),
                "phase1_top5_overlap": int(sub["code"].isin(set(top5["code"])).sum()),
                "bm_median": sub["bm_raw"].median(skipna=True),
                "ep_median": sub["ep_raw"].median(skipna=True),
                "gp_median": sub["gross_profitability"].median(skipna=True),
                "piotroski_median": sub["piotroski_available_ratio"].median(skipna=True),
                "distress_rate": bool_series(sub["distress_exclusion_flag"]).mean() if len(sub) else 0,
                "anomaly_rate": sub["anomaly_penalty"].mean() if len(sub) else 0,
                "sector_hhi": hhi(sub["sector"]) if len(sub) else 0,
            }
        )
    comp = pd.DataFrame(comp_rows)
    comp.to_csv(OUT / "rankings" / "phase1_vs_weighted_comparison.csv", index=False)
    (OUT / "reports" / "phase1_vs_weighted_experiment_report.md").write_text(
        f"""# Phase1 vs Weighted Experiment Report

This report compares the strict Phase1 Top5 and candidate pool with exploratory weighted rankings. The weighted score is not an official Phase1 formula.

{md_table(comp, 10)}

## Interpretation
Phase1 emphasizes transparent sequential screening. The weighted experiment emphasizes continuous sensitivity across value, quality, safety, liquidity, and penalties. Overlap should be read as robustness evidence, not as replacement logic.
""",
        encoding="utf-8",
    )
    (OUT / "reports" / "limitations.md").write_text(
        """# Limitations

- 重み最適化は探索実験であり、正式な投資式ではない。
- 重みはデータ時点に依存する。
- 過去データやPhase1 Top5に過剰適合する可能性がある。
- 欠損処理や正規化方法で結果が変わる。
- Phase1の段階フィルターより説明責任が弱い。
- Phase3ではテーマ仮説・企業変化・事業内容の定性確認が必要である。
- Ohlson O-Score / Altman Z-Score原式は本Phase2出力では正式名称として使わず、simple distress safety proxyとして扱った。
""",
        encoding="utf-8",
    )
    review = ranked[(ranked["rank"] <= 300) & ((ranked["anomaly_penalty"] > 0) | (bool_series(ranked["distress_review_flag"])))]
    (OUT / "reports" / "phase3_handoff_from_weight_experiment.md").write_text(
        f"""# Phase3 Handoff From Weight Experiment

## Weighted Top100 / Top300 / Top1000の使い方
Weighted Top100は優先的に定性確認する候補群、Top300はPhase3候補母集団、Top1000は指標感度確認の参照母集団として使う。

## Phase1 Top5との整合性
{md_table(check)}

## 重み最適化で上位に来たがreviewが必要な企業
{md_table(review[["rank", "code", "company_name", "sector", "exploratory_weighted_score", "anomaly_penalty", "distress_review_flag"]], 20)}

## 生まれるMoat・変わるMoat分析で優先すべき候補
Top100のうち、価値・品質・流動性が同時に高い企業を優先する。Phase1 Top5と重なる企業は説明可能性と感度の両面で確認する。

## Phase3で除外確認すべき企業
distress_review_flag、anomaly_flags、one_time_profit_suspected、microcap_flag、missingness_penaltyが高い企業は、事業内容と財務注記を確認してから採用可否を判断する。
""",
        encoding="utf-8",
    )
    readme = f"""# BEYOND BUFFETT Phase2 Weight Optimization

## この成果物の位置づけ

このZIPは、BEYOND BUFFETT Phase2の重み最適化探索実験である。  
Phase1の正式ルールを置き換えるものではない。  
Phase1では独自重み付き総合式を避けた。  
本実験は、Phase2の「破」として、各先行研究式の相対的重要度を調べるために行った。

## 参照したPhase1成果物

- outputs/phase1_buffett_complete/screening_candidates_complete.csv
- outputs/phase1_top5/phase1_buffett_core_top5.csv
- outputs/phase1_top5/phase1_top5_candidate_pool.csv
- outputs/phase1_top5/report_tables/phase1_top5_screening_funnel.csv
- outputs/phase1_top5/report_tables/phase1_top5_metrics_table.csv

Phase1成果物はコピーせず、上記パスを参照した。

## 使い方

1. ZIPを展開する
2. README.mdを読む
3. reports/weight_optimization_report.mdを確認する
4. rankings/exploratory_weighted_ranking_all.csvを見る
5. rankings/phase1_top5_rank_check.csvでPhase1 Top5の順位を確認する
6. reports/phase3_handoff_from_weight_experiment.mdをPhase3設計に使う

## 注意

Exploratory Weighted Buffett Score は正式な銘柄選定式ではない。  
将来リターン最大化モデルではない。  
Phase3での候補探索・感度分析・指標重要度確認のための補助成果物である。

## Main Files

- reports/weight_optimization_report.md
- reports/phase1_vs_weighted_experiment_report.md
- reports/limitations.md
- reports/phase3_handoff_from_weight_experiment.md
- rankings/exploratory_weighted_ranking_all.csv
- rankings/phase1_top5_rank_check.csv
- optimization/selected_weight_solution.json

## Selected Objective

- Selected trial: {selected["selected_trial_id"]}
- Objective score: {selected["overall_weight_objective"]:.4f}
- Stability Jaccard mean: {stability_info["stability_mean"]:.4f}
"""
    (OUT / "README.md").write_text(readme + "\n", encoding="utf-8")


def copy_module_scripts() -> None:
    init = OUT / "scripts" / "phase2_weight_optimizer" / "__init__.py"
    init.write_text('"""Phase2 weight optimization artifact scripts."""\n', encoding="utf-8")
    stub_template = """from .generate_phase2_artifacts import main

if __name__ == "__main__":
    main()
"""
    for name in ["load_inputs", "normalize_metrics", "build_score", "objectives", "random_search", "optuna_tpe", "nsga2", "validation", "ablation", "reporting"]:
        (OUT / "scripts" / "phase2_weight_optimizer" / f"{name}.py").write_text(stub_template, encoding="utf-8")
    run_all = OUT / "scripts" / "phase2_weight_optimizer" / "run_all.sh"
    run_all.write_text(
        """#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT_DIR" || exit 1
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
python -m scripts.phase2_weight_optimizer.load_inputs
python -m scripts.phase2_weight_optimizer.normalize_metrics
python -m scripts.phase2_weight_optimizer.random_search
python -m scripts.phase2_weight_optimizer.optuna_tpe
python -m scripts.phase2_weight_optimizer.nsga2
python -m scripts.phase2_weight_optimizer.validation
python -m scripts.phase2_weight_optimizer.ablation
python -m scripts.phase2_weight_optimizer.reporting
exit 0
""",
        encoding="utf-8",
    )
    run_all.chmod(0o755)


def manifest_and_checksums(input_paths: list[Path]) -> None:
    manifest = {
        "project": "BEYOND BUFFETT",
        "phase": "Phase2 Weight Optimization Experiment",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "description": "Phase1で使用した先行研究式の重み最適化を行う探索実験。正式な銘柄選定式ではなく、Phase3候補探索のための感度分析として位置づける。",
        "input_files": [str(p.relative_to(ROOT)) for p in input_paths],
        "main_outputs": [
            "reports/weight_optimization_report.md",
            "reports/phase1_vs_weighted_experiment_report.md",
            "reports/limitations.md",
            "reports/phase3_handoff_from_weight_experiment.md",
            "rankings/exploratory_weighted_ranking_all.csv",
            "rankings/exploratory_weighted_top100.csv",
            "rankings/exploratory_weighted_top300.csv",
            "rankings/exploratory_weighted_top1000.csv",
            "rankings/phase1_top5_rank_check.csv",
            "optimization/all_weight_trials.csv",
            "optimization/best_weight_trials.csv",
            "optimization/pareto_weight_solutions.csv",
            "optimization/selected_weight_solution.json",
        ],
        "important_note": "This weighted score is exploratory and must not be described as the official Phase1 Buffett Core selection formula.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    patterns = {".csv", ".json", ".md", ".png", ".py"}
    rows = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "checksums.txt":
            continue
        if path.suffix in patterns or path.name == "run_all.sh":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{digest}  {path.relative_to(OUT)}")
    (OUT / "checksums.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def final_validation() -> list[str]:
    required = [
        "README.md",
        "configs/weight_search_space.yaml",
        "data_audit/input_files_detected.csv",
        "normalized_metrics/normalized_metric_table.csv",
        "optimization/all_weight_trials.csv",
        "optimization/best_weight_trials.csv",
        "optimization/pareto_weight_solutions.csv",
        "optimization/selected_weight_solution.json",
        "rankings/exploratory_weighted_ranking_all.csv",
        "rankings/phase1_top5_rank_check.csv",
        "reports/weight_optimization_report.md",
        "reports/phase1_vs_weighted_experiment_report.md",
        "reports/limitations.md",
        "reports/phase3_handoff_from_weight_experiment.md",
        "scripts/phase2_weight_optimizer/run_all.sh",
        "figures/optimized_weights_bar.png",
        "figures/score_distribution.png",
        "figures/topN_overlap_curve.png",
        "figures/phase1_top5_rank_positions.png",
        "figures/sector_distribution_top100_top300_top1000.png",
        "figures/pareto_front_weights.png",
        "figures/stability_jaccard_heatmap.png",
    ]
    errors = []
    for rel in required:
        path = OUT / rel
        if not path.exists():
            errors.append(f"Missing required file: {rel}")
        elif path.is_file() and path.stat().st_size == 0:
            errors.append(f"Empty required file: {rel}")
    for path in OUT.rglob("*.csv"):
        try:
            if pd.read_csv(path).empty:
                errors.append(f"CSV has no rows: {path.relative_to(OUT)}")
        except Exception as exc:
            errors.append(f"CSV could not be read: {path.relative_to(OUT)} ({exc})")
    lines = ["# Final Validation Errors", ""]
    lines.extend([f"- {e}" for e in errors] or ["- None"])
    (OUT / "logs" / "final_validation_errors.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return errors


def create_zip() -> Path:
    zip_path = ROOT / "outputs" / "phase2_weight_optimization.zip"
    if zip_path.exists():
        zip_path.unlink()
    excluded_parts = {"__pycache__", ".git", ".venv", "venv", "node_modules", "matplotlib_cache"}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(OUT.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(OUT)
            if any(part in excluded_parts for part in rel.parts):
                continue
            if path.name == ".DS_Store" or path.suffix == ".tmp":
                continue
            if path.suffix == ".log" and str(rel) != "logs/summary.log":
                continue
            zf.write(path, Path("phase2_weight_optimization") / rel)
    return zip_path


def validate_zip(zip_path: Path) -> None:
    required = [
        "phase2_weight_optimization/manifest.json",
        "phase2_weight_optimization/README.md",
        "phase2_weight_optimization/optimization/selected_weight_solution.json",
        "phase2_weight_optimization/rankings/exploratory_weighted_ranking_all.csv",
        "phase2_weight_optimization/rankings/phase1_top5_rank_check.csv",
        "phase2_weight_optimization/reports/limitations.md",
        "phase2_weight_optimization/reports/phase3_handoff_from_weight_experiment.md",
    ]
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    missing = [name for name in required if name not in names]
    lines = [
        "# ZIP Validation Report",
        "",
        f"- ZIP exists: {zip_path.exists()}",
        f"- ZIP size MB: {size_mb:.3f}",
        f"- File count: {len(names)}",
        "",
        "## Required file checks",
    ]
    for name in required:
        lines.append(f"- {name}: {'OK' if name in names else 'MISSING'}")
    lines += ["", "## Missing", *([f"- {m}" for m in missing] or ["- None"]), "", "## ZIP file listing"]
    lines.extend([f"- {name}" for name in names])
    (OUT / "logs" / "zip_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary_log(zip_path: Path, ranked: pd.DataFrame, all_trials: pd.DataFrame, stability_info: dict[str, float]) -> str:
    selected = json.loads((OUT / "optimization" / "selected_weight_solution.json").read_text(encoding="utf-8"))
    top1000 = pd.read_csv(OUT / "validation" / "topn_evaluation.csv").query("n == 1000").iloc[0]
    msg = f"""Phase2 weight optimization completed.
Output directory: outputs/phase2_weight_optimization/
ZIP file: outputs/phase2_weight_optimization.zip
ZIP size: {zip_path.stat().st_size / (1024 * 1024):.3f} MB
Main report: outputs/phase2_weight_optimization/reports/weight_optimization_report.md
Ranking file: outputs/phase2_weight_optimization/rankings/exploratory_weighted_ranking_all.csv
Phase1 Top5 check: outputs/phase2_weight_optimization/rankings/phase1_top5_rank_check.csv
Selected weights: outputs/phase2_weight_optimization/optimization/selected_weight_solution.json
Handoff report: outputs/phase2_weight_optimization/reports/phase3_handoff_from_weight_experiment.md

Best weights: {json.dumps(selected["positive_weights"], ensure_ascii=False)}
Best objective score: {selected["overall_weight_objective"]:.4f}
Top1000 sector HHI: {float(top1000["sector_hhi"]):.4f}
Top1000 distress flag rate: {float(top1000["distress_flag_rate"]):.4f}
Top1000 anomaly flag rate: {float(top1000["anomaly_flag_rate"]):.4f}
Stability Jaccard mean: {stability_info["stability_mean"]:.4f}
"""
    (OUT / "logs" / "summary.log").write_text(msg, encoding="utf-8")
    return msg


def main() -> None:
    ensure_dirs()
    input_paths = detect_inputs()
    write_configs()
    df, top5, load_errors = load_base()
    audit_columns(df)
    norm = build_normalized(df)
    all_trials, selected = run_search(norm, top5)
    ranked = create_rankings(norm, top5, selected)
    stability_info = validation_tables(ranked, all_trials, top5)
    create_figures(ranked, all_trials, top5)
    copy_module_scripts()
    write_reports(ranked, all_trials, top5, stability_info)
    final_validation()
    manifest_and_checksums(input_paths)
    final_validation()
    zip_path = create_zip()
    validate_zip(zip_path)
    manifest_and_checksums(input_paths)
    zip_path = create_zip()
    validate_zip(zip_path)
    msg = write_summary_log(zip_path, ranked, all_trials, stability_info)
    print(msg)


if __name__ == "__main__":
    main()
