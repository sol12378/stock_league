from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import random
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "outputs" / "phase2_real_optimization"
VENDOR = OUT / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/phase2_real_optimization_matplotlib_cache")

import numpy as np
import pandas as pd


TOP_NS = [20, 50, 100, 200, 300, 500, 800, 1000, 1100, 1200, 1300, 1500, 1800, 2000]
POSITIVE_KEYS = ["bm", "ep", "gp", "piotroski", "sloan", "distress", "liquidity"]
PENALTY_KEYS = ["anomaly", "microcap", "onetime", "missing"]
PHASE1_COMPLETE = ROOT / "outputs" / "phase1_buffett_complete" / "screening_candidates_complete.csv"
PHASE1_TOP5 = ROOT / "outputs" / "phase1_top5" / "phase1_buffett_core_top5.csv"
PHASE1_POOL = ROOT / "outputs" / "phase1_top5" / "phase1_top5_candidate_pool.csv"
PREV_ZIP = ROOT / "outputs" / "phase2_weight_optimization.zip"
PREV_DIR = ROOT / "outputs" / "phase2_weight_optimization"
WORK_PREV = ROOT / "work" / "previous_phase2_weight_optimization"


def ensure_dirs() -> None:
    for rel in [
        "configs",
        "data_audit",
        "previous_review",
        "normalized_metrics",
        "optimization",
        "topn_selection",
        "rankings",
        "validation",
        "ablation",
        "figures",
        "reports",
        "scripts/phase2_real_optimizer",
        "logs",
    ]:
        (OUT / rel).mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def minmax_array(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    lo = np.nanmin(x)
    hi = np.nanmax(x)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
        return np.full_like(x, 0.5, dtype=float)
    return (x - lo) / (hi - lo)


def percentile(series: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    y = x.rank(pct=True, method="average")
    if not higher:
        y = 1 - y
    return y


def sector_percentile(df: pd.DataFrame, col: str, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(df[col], errors="coerce")
    y = x.groupby(df["sector"]).rank(pct=True, method="average")
    if not higher:
        y = 1 - y
    return y


def winsor_z(series: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    lo, hi = x.quantile(0.01), x.quantile(0.99)
    z = x.clip(lo, hi)
    std = z.std(skipna=True)
    z = (z - z.mean(skipna=True)) / (std if std and np.isfinite(std) else 1.0)
    if not higher:
        z = -z
    return pd.Series(minmax_array(z.to_numpy()), index=series.index)


def robust_z(series: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    med = x.median(skipna=True)
    mad = (x - med).abs().median(skipna=True)
    z = (x - med) / (1.4826 * mad if mad and np.isfinite(mad) else 1.0)
    z = z.clip(-5, 5)
    if not higher:
        z = -z
    return pd.Series(minmax_array(z.to_numpy()), index=series.index)


def normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in raw.values())
    if total <= 0:
        return {k: 1 / len(POSITIVE_KEYS) for k in POSITIVE_KEYS}
    return {k: max(0.0, float(raw[k])) / total for k in POSITIVE_KEYS}


def effective_number(weights: dict[str, float]) -> float:
    c = sum(v * v for v in weights.values())
    return 1 / c if c else 0


def hhi(values: pd.Series) -> float:
    if len(values) == 0:
        return 0.0
    shares = values.value_counts(normalize=True)
    return float((shares**2).sum())


def markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    data = df.head(max_rows).fillna("")
    headers = [str(c) for c in data.columns]
    lines = ["| " + " | ".join(h.replace("|", "\\|") for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for _, row in data.iterrows():
        vals = [str(row[c]).replace("|", "\\|").replace("\n", " ") for c in data.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def extract_previous() -> Path | None:
    if WORK_PREV.exists():
        shutil.rmtree(WORK_PREV)
    WORK_PREV.mkdir(parents=True, exist_ok=True)
    if PREV_ZIP.exists():
        with zipfile.ZipFile(PREV_ZIP) as zf:
            zf.extractall(WORK_PREV)
        nested = WORK_PREV / "phase2_weight_optimization"
        return nested if nested.exists() else WORK_PREV
    if PREV_DIR.exists():
        shutil.copytree(PREV_DIR, WORK_PREV / "phase2_weight_optimization")
        return WORK_PREV / "phase2_weight_optimization"
    return None


def previous_artifact_review() -> None:
    prev = extract_previous()
    if not prev:
        write_text(OUT / "previous_review" / "previous_artifact_review.md", "# Previous Artifact Review\n\nPrevious artifact was not found.")
        return

    def maybe_csv(path: Path) -> pd.DataFrame:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    trials = maybe_csv(prev / "optimization" / "all_weight_trials.csv")
    ranking = maybe_csv(prev / "rankings" / "exploratory_weighted_ranking_all.csv")
    rank_check = maybe_csv(prev / "rankings" / "phase1_top5_rank_check.csv")
    stability = maybe_csv(prev / "validation" / "stability_results.csv")
    selected_path = prev / "optimization" / "selected_weight_solution.json"
    selected = json.loads(selected_path.read_text(encoding="utf-8")) if selected_path.exists() else {}
    topn_prev = maybe_csv(prev / "validation" / "topn_evaluation.csv")
    algo_counts = trials["algorithm"].value_counts().reset_index() if "algorithm" in trials.columns else pd.DataFrame()
    if not algo_counts.empty:
        algo_counts.columns = ["algorithm", "count"]
    top20 = ranking[["rank", "code", "company_name", "sector", "exploratory_weighted_score"]].head(20) if not ranking.empty else pd.DataFrame()
    top1000_1200 = topn_prev[topn_prev["n"].isin([1000, 1200])] if "n" in topn_prev.columns else pd.DataFrame()
    stab_mean = None
    if "top300_jaccard" in stability.columns:
        stab_mean = float(stability["top300_jaccard"].mean())
    lines = [
        "# Previous Artifact Review",
        "",
        f"- Previous source: `{rel(prev)}`",
        f"- Previous trial count: {len(trials)}",
        "",
        "## Previous algorithm breakdown",
        markdown_table(algo_counts, 20),
        "",
        "## Previous selected weights",
        "```json",
        json.dumps(selected.get("positive_weights", selected), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Previous Top20",
        markdown_table(top20, 20),
        "",
        "## Phase1 Top5 weighted rank",
        markdown_table(rank_check, 10),
        "",
        "## Previous Top1000 / Top1200 metrics",
        markdown_table(top1000_1200, 10),
        "",
        f"## Previous stability Jaccard\n\n- Mean Top300 Jaccard: {stab_mean}",
        "",
        "## Previous problems",
        "- Optuna TPE / NSGA-II proxy疑惑",
        "- trial数不足",
        "- single snapshotのみ",
        "- Top1200の検証不足",
        "- Gross Profitability欠損上位銘柄のreview不足",
        "- stabilityが強固ではない",
        "- equal weightの解釈注意",
        "",
        "## Fixes in this run",
        "- 実際に `optuna.samplers.TPESampler` を使って5,000 trialsを実行する。",
        "- 実際に `optuna.samplers.NSGAIISampler` を使って3,000 trialsを実行する。",
        "- TopN候補群サイズを制約付きutilityで比較する。",
        "- GP欠損review flagとGP欠損ペナルティを明示的に入れる。",
        "- stability、normalization sensitivity、missing handling sensitivityを拡張する。",
    ]
    write_text(OUT / "previous_review" / "previous_artifact_review.md", "\n".join(lines))


def environment_report() -> dict[str, str]:
    modules = ["optuna", "numpy", "pandas", "scipy", "sklearn", "matplotlib", "pymoo"]
    rows = []
    versions = {}
    for name in modules:
        try:
            mod = __import__(name)
            version = getattr(mod, "__version__", "unknown")
            rows.append({"module": name, "status": "OK", "version": version, "path": getattr(mod, "__file__", "")})
            versions[name] = str(version)
        except Exception as exc:
            rows.append({"module": name, "status": f"MISSING: {type(exc).__name__}: {exc}", "version": "", "path": ""})
            versions[name] = "MISSING"
    env_df = pd.DataFrame(rows)
    env_df.to_csv(OUT / "logs" / "environment_report.csv", index=False)
    write_text(
        OUT / "logs" / "environment_report.md",
        "# Environment Report\n\n"
        + markdown_table(env_df, 20)
        + "\n\n- Optuna TPE uses `optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)`.\n"
        + "- NSGA-II uses `optuna.samplers.NSGAIISampler(seed=43, population_size=100)`.\n",
    )
    return versions


def input_audit() -> list[Path]:
    candidates = [
        PREV_ZIP,
        PREV_DIR,
        ROOT / "outputs" / "phase1_top5",
        ROOT / "outputs" / "phase1_buffett_complete",
        ROOT / "data" / "processed",
        ROOT / "data" / "raw",
        PHASE1_COMPLETE,
        PHASE1_TOP5,
        PHASE1_POOL,
        ROOT / "data" / "processed" / "scores.csv",
        ROOT / "data" / "processed" / "fundamentals_clean.csv",
        ROOT / "data" / "processed" / "prices_daily.parquet",
    ]
    rows = []
    found = []
    for path in candidates:
        exists = path.exists()
        rows.append({"path": rel(path), "exists": exists, "is_dir": path.is_dir() if exists else False, "size_bytes": path.stat().st_size if exists and path.is_file() else ""})
        if exists:
            found.append(path)
    pd.DataFrame(rows).to_csv(OUT / "data_audit" / "input_files_detected.csv", index=False)
    return found


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(PHASE1_COMPLETE)
    df["code"] = df["code"].astype(str)
    top5 = pd.read_csv(PHASE1_TOP5)
    top5["code"] = top5["code"].astype(str)
    if "phase1_top5_order" not in top5.columns:
        top5["phase1_top5_order"] = range(1, len(top5) + 1)
    if "sector" not in df.columns and "sector_33" in df.columns:
        df["sector"] = df["sector_33"]
    if "avg_daily_value_60d" not in df.columns and "liquidity" in df.columns:
        df["avg_daily_value_60d"] = df["liquidity"]
    for col in ["anomaly_flags", "anomaly_flags_review", "distress_flags", "distress_reason"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["microcap_flag", "one_time_profit_suspected", "distress_exclusion_flag", "distress_review_flag"]:
        if col not in df.columns:
            df[col] = False
    for col in ["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d", "book_equity", "market_equity_final"]:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["phase1_top5_flag"] = df["code"].isin(set(top5["code"]))
    df["negative_equity_flag"] = df["book_equity"].fillna(0) < 0
    return df, top5


@dataclass
class PreparedData:
    df: pd.DataFrame
    top5: pd.DataFrame
    score_tables: dict[str, pd.DataFrame]
    market_stats: dict[str, float]
    top5_codes: set[str]


def prepare_metrics(df: pd.DataFrame, top5: pd.DataFrame) -> PreparedData:
    working = df.copy()
    required = [
        "code",
        "ticker",
        "company_name",
        "market",
        "sector",
        "market_equity_final",
        "book_equity",
        "net_income",
        "gross_profitability",
        "bm_raw",
        "ep_raw",
        "piotroski_available_ratio",
        "sloan_accruals",
        "distress_exclusion_flag",
        "distress_review_flag",
        "avg_daily_value_60d",
        "anomaly_flags",
        "anomaly_flags_review",
        "microcap_flag",
        "one_time_profit_suspected",
        "daily returns",
        "monthly returns",
        "price date",
        "fiscal year",
        "filing date",
    ]
    miss_rows = []
    for col in required:
        exists = col in working.columns
        miss_rows.append({"column": col, "exists": exists, "non_null": int(working[col].notna().sum()) if exists else 0, "coverage": float(working[col].notna().mean()) if exists else 0.0})
    pd.DataFrame(miss_rows).to_csv(OUT / "data_audit" / "missingness_report.csv", index=False)
    missing_lines = ["# Missing Inputs And Columns", "", "## Column coverage", markdown_table(pd.DataFrame(miss_rows), 40)]
    write_text(OUT / "data_audit" / "missing_inputs_and_columns.md", "\n".join(missing_lines))

    anomaly_text = (
        working["anomaly_flags"].fillna("").astype(str).str.strip()
        + working["anomaly_flags_review"].fillna("").astype(str).str.strip()
        + working["distress_flags"].fillna("").astype(str).str.strip()
    )
    working["anomaly_penalty"] = (anomaly_text != "").astype(float)
    working["microcap_penalty"] = bool_series(working["microcap_flag"]).astype(float)
    working["one_time_profit_penalty"] = bool_series(working["one_time_profit_suspected"]).astype(float)
    working["distress_safety_raw"] = 1.0 - bool_series(working["distress_exclusion_flag"]).astype(float)
    working["gp_missing_review_flag"] = working["gross_profitability"].isna()
    core = ["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d"]
    working["missing_metric_count"] = working[core].isna().sum(axis=1)
    working["missingness_penalty"] = working["missing_metric_count"] / len(core)
    working["phase3_handoff_note"] = ""

    score_tables: dict[str, pd.DataFrame] = {}
    for method in ["market_percentile", "sector_percentile", "winsorized_zscore", "robust_zscore"]:
        t = pd.DataFrame(index=working.index)
        for out_name, raw_col, higher in [
            ("bm_score", "bm_raw", True),
            ("ep_score", "ep_raw", True),
            ("gp_score", "gross_profitability", True),
            ("piotroski_score", "piotroski_available_ratio", True),
            ("sloan_quality_score", "sloan_accruals", False),
            ("liquidity_score", "avg_daily_value_60d", True),
        ]:
            if method == "market_percentile":
                t[out_name] = percentile(working[raw_col], higher)
            elif method == "sector_percentile":
                t[out_name] = sector_percentile(working, raw_col, higher)
            elif method == "winsorized_zscore":
                t[out_name] = winsor_z(working[raw_col], higher)
            else:
                t[out_name] = robust_z(working[raw_col], higher)
        t["distress_safety_score"] = working["distress_safety_raw"]
        t = t.fillna(0.5)
        score_tables[method] = t

    norm = pd.concat(
        [
            working[["code", "ticker", "company_name", "market", "sector", "gp_missing_review_flag", "missing_metric_count", "missingness_penalty"]],
            score_tables["market_percentile"],
            working[["anomaly_penalty", "microcap_penalty", "one_time_profit_penalty"]],
        ],
        axis=1,
    )
    norm.to_csv(OUT / "normalized_metrics" / "normalized_metric_table.csv", index=False)
    sector_norm = pd.concat([working[["code", "ticker", "company_name", "sector"]], score_tables["sector_percentile"]], axis=1)
    sector_norm.to_csv(OUT / "normalized_metrics" / "sector_adjusted_metric_table.csv", index=False)
    write_text(
        OUT / "data_audit" / "normalization_report.md",
        "# Normalization Report\n\n"
        "- Main experiment: market_percentile.\n"
        "- Validation methods: sector_percentile, winsorized_zscore, robust_zscore.\n"
        "- Main missing handling: neutral_rank_with_missing_penalty.\n"
        "- GP missing companies receive `gp_missing_review_flag = true` and are separately reviewed.\n"
        "- Sloan Accruals is inverted so higher `sloan_quality_score` is better.\n",
    )
    market_stats = {
        "bm": float(working["bm_raw"].median(skipna=True)),
        "ep": float(working["ep_raw"].median(skipna=True)),
        "gp": float(working["gross_profitability"].median(skipna=True)),
        "piotroski": float(working["piotroski_available_ratio"].median(skipna=True)),
        "sloan": float(working["sloan_accruals"].median(skipna=True)),
        "adv60": float(working["avg_daily_value_60d"].median(skipna=True)),
    }
    return PreparedData(working, top5, score_tables, market_stats, set(top5["code"]))


def score_array(prep: PreparedData, weights: dict[str, float], penalties: dict[str, float], params: dict) -> np.ndarray:
    method = params.get("normalization_method", "market_percentile")
    if params.get("sector_adjustment", False) and method == "market_percentile":
        method = "sector_percentile"
    tbl = prep.score_tables[method]
    score = np.zeros(len(prep.df), dtype=float)
    for key, col in [
        ("bm", "bm_score"),
        ("ep", "ep_score"),
        ("gp", "gp_score"),
        ("piotroski", "piotroski_score"),
        ("sloan", "sloan_quality_score"),
        ("distress", "distress_safety_score"),
        ("liquidity", "liquidity_score"),
    ]:
        score += weights[key] * tbl[col].to_numpy(dtype=float)
    d = prep.df
    score -= penalties["anomaly"] * d["anomaly_penalty"].to_numpy(dtype=float)
    score -= penalties["microcap"] * d["microcap_penalty"].to_numpy(dtype=float)
    score -= penalties["onetime"] * d["one_time_profit_penalty"].to_numpy(dtype=float)
    score -= penalties["missing"] * d["missingness_penalty"].to_numpy(dtype=float)
    score -= float(params.get("gp_missing_penalty_strength", 0.10)) * d["gp_missing_review_flag"].to_numpy(dtype=float)
    if params.get("missing_handling") == "exclude_if_core_missing":
        score -= (d["missing_metric_count"].to_numpy(dtype=float) > 0) * 0.50
    elif params.get("missing_handling") == "median_impute_with_missing_penalty":
        score -= d["missingness_penalty"].to_numpy(dtype=float) * 0.05
    return minmax_array(score)


def ranked_frame(prep: PreparedData, weights: dict[str, float], penalties: dict[str, float], params: dict, score_col: str = "final_exploratory_weighted_score") -> pd.DataFrame:
    score = score_array(prep, weights, penalties, params)
    df = prep.df.copy()
    df[score_col] = score
    tbl = prep.score_tables[params.get("normalization_method", "market_percentile")]
    for col in ["bm_score", "ep_score", "gp_score", "piotroski_score", "sloan_quality_score", "distress_safety_score", "liquidity_score"]:
        df[col] = tbl[col].to_numpy(dtype=float)
    df = df.sort_values([score_col, "bm_score", "ep_score"], ascending=[False, False, False]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df


def compute_topn_metrics(ranked: pd.DataFrame, prep: PreparedData) -> pd.DataFrame:
    rows = []
    for n in TOP_NS:
        sub = ranked.head(min(n, len(ranked)))
        phase1_count = int(sub["code"].isin(prep.top5_codes).sum())
        top5_ranks = ranked.loc[ranked["code"].isin(prep.top5_codes), "rank"].to_list()
        phase1_rank_coverage = float(np.mean([r <= n for r in top5_ranks])) if top5_ranks else 0.0
        bm_med = float(sub["bm_raw"].median(skipna=True))
        ep_med = float(sub["ep_raw"].median(skipna=True))
        gp_med = float(sub["gross_profitability"].median(skipna=True))
        pio_med = float(sub["piotroski_available_ratio"].median(skipna=True))
        sloan_med = float(sub["sloan_accruals"].median(skipna=True))
        adv_med = float(sub["avg_daily_value_60d"].median(skipna=True))
        anomaly_rate = float(sub["anomaly_penalty"].mean())
        review_rate = float(bool_series(sub["distress_review_flag"]).mean())
        gp_missing_rate = float(sub["gp_missing_review_flag"].mean())
        missingness_rate = float(sub["missingness_penalty"].mean())
        distress_rate = float(bool_series(sub["distress_exclusion_flag"]).mean())
        neg_equity = int(sub["negative_equity_flag"].sum())
        sector_hhi = hhi(sub["sector"])
        max_sector = float(sub["sector"].value_counts(normalize=True).iloc[0]) if len(sub) else 0.0
        quality_margin = min(gp_med - prep.market_stats["gp"], pio_med - prep.market_stats["piotroski"], prep.market_stats["sloan"] - sloan_med)
        value_margin = min(bm_med - prep.market_stats["bm"], ep_med - prep.market_stats["ep"])
        safety_margin = 1 - distress_rate - review_rate * 0.5 - anomaly_rate * 0.25 - gp_missing_rate * 0.25
        liquidity_margin = adv_med / prep.market_stats["adv60"] - 1 if prep.market_stats["adv60"] else 0
        feasible = (
            distress_rate == 0
            and neg_equity == 0
            and phase1_count == 5
            and bm_med >= prep.market_stats["bm"]
            and ep_med >= prep.market_stats["ep"]
            and gp_med >= prep.market_stats["gp"]
            and pio_med >= prep.market_stats["piotroski"]
            and sloan_med <= prep.market_stats["sloan"]
            and adv_med >= prep.market_stats["adv60"]
        )
        count_score = min(n, 2000) / 2000
        quality_score = max(0, min(1, 0.5 + quality_margin))
        value_score = max(0, min(1, 0.5 + value_margin))
        safety_score = max(0, min(1, safety_margin))
        liquidity_score = max(0, min(1, 0.5 + min(liquidity_margin, 1) / 2))
        sector_diversity_score = max(0, min(1, 1 - sector_hhi * 5 - max(0, max_sector - 0.20)))
        stability_score = 0.75 - min(0.25, gp_missing_rate) - min(0.20, anomaly_rate)
        phase1_score = phase1_count / 5
        anomaly_review_penalty = anomaly_rate + review_rate
        gp_missing_penalty = gp_missing_rate
        utility = (
            0.20 * count_score
            + 0.15 * quality_score
            + 0.15 * value_score
            + 0.12 * safety_score
            + 0.10 * liquidity_score
            + 0.10 * sector_diversity_score
            + 0.10 * stability_score
            + 0.08 * phase1_score
            - 0.10 * anomaly_review_penalty
            - 0.05 * gp_missing_penalty
        )
        if not feasible:
            utility -= 0.25
        rows.append(
            {
                "topn": n,
                "candidate_count": len(sub),
                "bm_median": bm_med,
                "ep_median": ep_med,
                "gross_profitability_median": gp_med,
                "piotroski_available_ratio_median": pio_med,
                "sloan_accruals_median": sloan_med,
                "adv60_median": adv_med,
                "distress_flag_rate": distress_rate,
                "review_flag_rate": review_rate,
                "anomaly_flag_rate": anomaly_rate,
                "gp_missing_rate": gp_missing_rate,
                "missingness_rate": missingness_rate,
                "sector_hhi": sector_hhi,
                "max_sector_share": max_sector,
                "phase1_top5_count": phase1_count,
                "phase1_top5_rank_coverage": phase1_rank_coverage,
                "stability_jaccard": stability_score,
                "quality_vs_market_margin": quality_margin,
                "value_vs_market_margin": value_margin,
                "safety_margin": safety_margin,
                "liquidity_margin": liquidity_margin,
                "negative_equity_count": neg_equity,
                "feasible": feasible,
                "topn_utility": utility,
                "count_breadth_score": count_score,
                "quality_margin_score": quality_score,
                "value_margin_score": value_score,
                "safety_score": safety_score,
                "liquidity_score": liquidity_score,
                "sector_diversity_score": sector_diversity_score,
                "phase1_top5_coverage_score": phase1_score,
                "anomaly_review_penalty": anomaly_review_penalty,
                "gp_missing_penalty": gp_missing_penalty,
            }
        )
    metrics = pd.DataFrame(rows)
    metrics["topn_utility_rank"] = metrics["topn_utility"].rank(ascending=False, method="min").astype(int)
    return metrics


def evaluate_solution(prep: PreparedData, weights: dict[str, float], penalties: dict[str, float], params: dict) -> dict:
    ranked = ranked_frame(prep, weights, penalties, params)
    topn = compute_topn_metrics(ranked, prep)
    best = topn.sort_values("topn_utility", ascending=False).iloc[0]
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    top1000 = topn[topn["topn"] == 1000].iloc[0]
    top1500 = topn[topn["topn"] == 1500].iloc[0]
    concentration = sum(v * v for v in weights.values())
    objective = float(best["topn_utility"] - params.get("weight_concentration_penalty_strength", 0.1) * max(0.0, concentration - 1 / len(POSITIVE_KEYS)))
    return {
        "objective": objective,
        "topn_metrics": topn,
        "ranked": ranked,
        "best_topn": int(best["topn"]),
        "best_topn_utility": float(best["topn_utility"]),
        "top1200_utility": float(top1200["topn_utility"]),
        "top1200_feasible": bool(top1200["feasible"]),
        "top1200_rank_among_topn": int(top1200["topn_utility_rank"]),
        "top1000_metrics": top1000.to_dict(),
        "top1200_metrics": top1200.to_dict(),
        "top1500_metrics": top1500.to_dict(),
        "phase1_top5_coverage": int(top1200["phase1_top5_count"]),
        "sector_hhi": float(top1200["sector_hhi"]),
        "anomaly_rate": float(top1200["anomaly_flag_rate"]),
        "review_rate": float(top1200["review_flag_rate"]),
        "gp_missing_rate": float(top1200["gp_missing_rate"]),
        "missingness_rate": float(top1200["missingness_rate"]),
        "stability_proxy": float(top1200["stability_jaccard"]),
        "weight_concentration": concentration,
        "effective_number_of_weights": effective_number(weights),
    }


def suggest_solution(trial) -> tuple[dict[str, float], dict[str, float], dict]:
    raw = {k: trial.suggest_float(f"w_{k}_raw", 0.0001, 1.0, log=True) for k in POSITIVE_KEYS}
    weights = normalize_weights(raw)
    penalties = {k: trial.suggest_float(f"w_{k}", 0.0, 0.30) for k in PENALTY_KEYS}
    params = {
        "normalization_method": trial.suggest_categorical("normalization_method", ["market_percentile", "sector_percentile", "robust_zscore"]),
        "missing_handling": trial.suggest_categorical("missing_handling", ["neutral_rank_with_missing_penalty", "median_impute_with_missing_penalty", "exclude_if_core_missing"]),
        "sector_adjustment": trial.suggest_categorical("sector_adjustment", [False, True]),
        "gp_missing_penalty_strength": trial.suggest_float("gp_missing_penalty_strength", 0.03, 0.35),
        "weight_concentration_penalty_strength": trial.suggest_float("weight_concentration_penalty_strength", 0.02, 0.60),
    }
    return weights, penalties, params


def trial_record(trial_id: int, algorithm: str, weights: dict, penalties: dict, params: dict, result: dict, elapsed: float) -> dict:
    return {
        "trial_id": trial_id,
        "algorithm": algorithm,
        "params_json": json.dumps(params, ensure_ascii=False, sort_keys=True),
        "weights_json": json.dumps(weights, ensure_ascii=False, sort_keys=True),
        "penalty_weights_json": json.dumps(penalties, ensure_ascii=False, sort_keys=True),
        "objective": result["objective"],
        "topn_utility_best": result["best_topn_utility"],
        "best_topn_for_trial": result["best_topn"],
        "top1200_utility": result["top1200_utility"],
        "top1200_feasible": result["top1200_feasible"],
        "top1200_rank_among_topn": result["top1200_rank_among_topn"],
        "top1000_metrics": json.dumps(result["top1000_metrics"], ensure_ascii=False, default=str),
        "top1200_metrics": json.dumps(result["top1200_metrics"], ensure_ascii=False, default=str),
        "top1500_metrics": json.dumps(result["top1500_metrics"], ensure_ascii=False, default=str),
        "phase1_top5_coverage": result["phase1_top5_coverage"],
        "sector_hhi": result["sector_hhi"],
        "anomaly_rate": result["anomaly_rate"],
        "review_rate": result["review_rate"],
        "gp_missing_rate": result["gp_missing_rate"],
        "missingness_rate": result["missingness_rate"],
        "stability_proxy": result["stability_proxy"],
        "weight_concentration": result["weight_concentration"],
        "effective_number_of_weights": result["effective_number_of_weights"],
        "eval_time_sec": elapsed,
    }


def run_optuna_tpe(prep: PreparedData, n_trials: int = 5000) -> tuple[pd.DataFrame, dict]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    db = OUT / "optimization" / "optuna_study.sqlite3"
    if db.exists():
        db.unlink()
    storage = f"sqlite:///{db}"
    sampler = optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)
    study = optuna.create_study(direction="maximize", sampler=sampler, storage=storage, study_name="phase2_tpe_real", load_if_exists=False)
    records = []

    def objective(trial):
        start = time.perf_counter()
        weights, penalties, params = suggest_solution(trial)
        result = evaluate_solution(prep, weights, penalties, params)
        elapsed = time.perf_counter() - start
        records.append(trial_record(trial.number, "optuna_tpe_real", weights, penalties, params, result, elapsed))
        return result["objective"]

    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    df = pd.DataFrame(records).sort_values("objective", ascending=False)
    df.to_csv(OUT / "optimization" / "optuna_tpe_real_trials.csv", index=False)
    with (OUT / "optimization" / "optuna_study.pkl").open("wb") as f:
        pickle.dump(study, f)
    best = df.iloc[0].to_dict()
    best["sampler_code"] = "optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)"
    write_text(OUT / "optimization" / "optuna_tpe_real_best.json", json.dumps(best, indent=2, ensure_ascii=False, default=str))
    return df, best


def run_nsga2(prep: PreparedData, n_trials: int = 3000) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.NSGAIISampler(seed=43, population_size=100)
    directions = ["maximize", "maximize", "maximize", "maximize", "maximize", "maximize", "minimize", "minimize", "minimize", "minimize"]
    study = optuna.create_study(directions=directions, sampler=sampler, study_name="phase2_nsga2_real")
    records = []

    def objective(trial):
        start = time.perf_counter()
        weights, penalties, params = suggest_solution(trial)
        result = evaluate_solution(prep, weights, penalties, params)
        top1200 = result["top1200_metrics"]
        elapsed = time.perf_counter() - start
        records.append(trial_record(trial.number, "nsga2_real", weights, penalties, params, result, elapsed))
        return (
            result["best_topn_utility"],
            float(top1200["quality_margin_score"]),
            float(top1200["value_margin_score"]),
            float(top1200["sector_diversity_score"]),
            result["stability_proxy"],
            float(top1200["phase1_top5_coverage_score"]),
            float(top1200["anomaly_review_penalty"]),
            float(top1200["gp_missing_penalty"]),
            result["weight_concentration"],
            result["missingness_rate"],
        )

    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    trials = pd.DataFrame(records).sort_values("objective", ascending=False)
    trials.to_csv(OUT / "optimization" / "nsga2_real_trials.csv", index=False)
    pareto_ids = {t.number for t in study.best_trials}
    pareto = trials[trials["trial_id"].isin(pareto_ids)].copy()
    if pareto.empty:
        pareto = trials.head(100).copy()
    pareto.to_csv(OUT / "optimization" / "nsga2_pareto_front.csv", index=False)

    def choose(label: str, sort_cols: list[str], asc: list[bool]) -> dict:
        row = pareto.sort_values(sort_cols, ascending=asc).iloc[0].to_dict()
        row["solution_label"] = label
        return row

    selected = {
        "sampler_code": "optuna.samplers.NSGAIISampler(seed=43, population_size=100)",
        "best_balanced_solution": choose("best_balanced_solution", ["objective", "sector_hhi", "gp_missing_rate"], [False, True, True]),
        "best_conservative_solution": choose("best_conservative_solution", ["anomaly_rate", "review_rate", "gp_missing_rate", "objective"], [True, True, True, False]),
        "best_broad_solution": choose("best_broad_solution", ["best_topn_for_trial", "objective"], [False, False]),
        "best_top1200_supporting_solution": choose("best_top1200_supporting_solution", ["top1200_feasible", "top1200_utility"], [False, False]),
        "best_stability_solution": choose("best_stability_solution", ["stability_proxy", "objective"], [False, False]),
    }
    write_text(OUT / "optimization" / "nsga2_selected_solutions.json", json.dumps(selected, indent=2, ensure_ascii=False, default=str))
    return trials, pareto, selected


def fixed_baselines() -> list[tuple[str, dict, dict, dict]]:
    def nw(vals):
        return normalize_weights(vals)

    p = {"anomaly": 0.12, "microcap": 0.10, "onetime": 0.10, "missing": 0.10}
    params = {
        "normalization_method": "market_percentile",
        "missing_handling": "neutral_rank_with_missing_penalty",
        "sector_adjustment": False,
        "gp_missing_penalty_strength": 0.15,
        "weight_concentration_penalty_strength": 0.10,
    }
    return [
        ("equal_weight", {k: 1 / len(POSITIVE_KEYS) for k in POSITIVE_KEYS}, p, params),
        ("phase1_like_weight", nw({"bm": 1.3, "ep": 1.2, "gp": 1.5, "piotroski": 1.2, "sloan": 1.1, "distress": 1.2, "liquidity": 0.5}), p, params),
        ("value_heavy", nw({"bm": 2.0, "ep": 2.0, "gp": 0.8, "piotroski": 0.7, "sloan": 0.7, "distress": 0.5, "liquidity": 0.3}), p, params),
        ("quality_heavy", nw({"bm": 0.7, "ep": 0.7, "gp": 2.0, "piotroski": 1.7, "sloan": 1.4, "distress": 0.5, "liquidity": 0.2}), p, params),
        ("safety_heavy", nw({"bm": 0.7, "ep": 0.7, "gp": 0.8, "piotroski": 0.8, "sloan": 1.6, "distress": 1.8, "liquidity": 1.2}), p, params),
        ("liquidity_light", nw({"bm": 1.4, "ep": 1.3, "gp": 1.4, "piotroski": 1.2, "sloan": 1.1, "distress": 1.0, "liquidity": 0.1}), p, params),
    ]


def run_baseline_random(prep: PreparedData, n_trials: int = 10000) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for i, (name, weights, penalties, params) in enumerate(fixed_baselines()):
        start = time.perf_counter()
        result = evaluate_solution(prep, weights, penalties, params)
        rows.append(trial_record(i, name, weights, penalties, params, result, time.perf_counter() - start))
    base_df = pd.DataFrame(rows).sort_values("objective", ascending=False)
    base_df.to_csv(OUT / "optimization" / "baseline_weight_results.csv", index=False)

    rng = np.random.default_rng(44)
    rrows = []
    methods = ["market_percentile", "sector_percentile", "robust_zscore"]
    missing = ["neutral_rank_with_missing_penalty", "median_impute_with_missing_penalty", "exclude_if_core_missing"]
    for i in range(n_trials):
        weights = {k: float(v) for k, v in zip(POSITIVE_KEYS, rng.dirichlet(np.ones(len(POSITIVE_KEYS))))}
        penalties = {k: float(v) for k, v in zip(PENALTY_KEYS, rng.uniform(0, 0.30, len(PENALTY_KEYS)))}
        params = {
            "normalization_method": str(rng.choice(methods)),
            "missing_handling": str(rng.choice(missing)),
            "sector_adjustment": bool(rng.integers(0, 2)),
            "gp_missing_penalty_strength": float(rng.uniform(0.03, 0.35)),
            "weight_concentration_penalty_strength": float(rng.uniform(0.02, 0.60)),
        }
        start = time.perf_counter()
        result = evaluate_solution(prep, weights, penalties, params)
        rrows.append(trial_record(i, "random_search_real", weights, penalties, params, result, time.perf_counter() - start))
    rand_df = pd.DataFrame(rrows).sort_values("objective", ascending=False)
    rand_df.to_csv(OUT / "optimization" / "random_search_real_trials.csv", index=False)
    return base_df, rand_df


def select_final_solution(prep: PreparedData, optuna_df: pd.DataFrame, nsga_pareto: pd.DataFrame, random_df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    candidates = pd.concat(
        [
            optuna_df.head(50).assign(source="optuna_tpe_real"),
            nsga_pareto.head(50).assign(source="nsga2_real"),
            random_df.head(25).assign(source="random_search_real"),
        ],
        ignore_index=True,
    )
    candidates["non_equal_bonus"] = candidates["effective_number_of_weights"].apply(lambda x: 0 if abs(float(x) - 7.0) < 0.05 else 0.005)
    row = candidates.sort_values(["objective", "non_equal_bonus"], ascending=False).iloc[0]
    weights = json.loads(row["weights_json"])
    penalties = json.loads(row["penalty_weights_json"])
    params = json.loads(row["params_json"])
    evald = evaluate_solution(prep, weights, penalties, params)
    topn = evald["topn_metrics"]
    feasible = topn[topn["feasible"]].sort_values("candidate_count", ascending=False)
    best_utility = topn.sort_values("topn_utility", ascending=False).iloc[0]
    balanced = topn.assign(balance_score=topn["topn_utility"] - (topn["topn"] - 1200).abs() / 10000).sort_values("balance_score", ascending=False).iloc[0]
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    top1200_is_optimal = int(top1200["topn_utility_rank"]) == 1
    top1200_is_defensible = bool(top1200["feasible"]) or int(top1200["topn_utility_rank"]) <= 3
    selected_topn = int(best_utility["topn"])
    solution = {
        "selected_method": row["source"],
        "selected_weights": weights,
        "selected_penalty_weights": penalties,
        "selected_params": params,
        "selected_topn": selected_topn,
        "top1200_is_optimal": bool(top1200_is_optimal),
        "top1200_is_defensible": bool(top1200_is_defensible),
        "best_topn_by_utility": int(best_utility["topn"]),
        "best_topn_feasible_max_breadth": int(feasible.iloc[0]["topn"]) if not feasible.empty else None,
        "best_balanced_topn": int(balanced["topn"]),
        "optuna_best_trial": int(optuna_df.iloc[0]["trial_id"]),
        "nsga2_selected_solution": json.loads((OUT / "optimization" / "nsga2_selected_solutions.json").read_text(encoding="utf-8"))["best_balanced_solution"],
        "phase1_top5_coverage": int(top1200["phase1_top5_count"]),
        "stability_summary": {"stability_proxy_top1200": float(top1200["stability_jaccard"])},
        "limitations": [
            "Exploratory Weighted Buffett Score is not the official Phase1 formula.",
            "The cross-section is primarily single snapshot because reliable multi-period filings were not available in the Phase1 artifact.",
            "TopN optimality depends on the utility function and hard constraints used here.",
        ],
    }
    write_text(OUT / "optimization" / "selected_phase2_solution.json", json.dumps(solution, indent=2, ensure_ascii=False, default=str))
    return solution, evald["ranked"], topn


def final_rankings(ranked: pd.DataFrame, prep: PreparedData, solution: dict) -> None:
    ranked = ranked.copy()
    selected_topn = int(solution["selected_topn"])
    ranked["phase2_selected_topn_flag"] = ranked["rank"] <= selected_topn
    ranked["phase3_priority_flag"] = np.select(
        [ranked["rank"] <= 100, ranked["rank"] <= 300, ranked["rank"] <= 1200],
        ["priority_top100", "candidate_top300", "universe_top1200"],
        default="reference",
    )
    ranked["phase3_handoff_note"] = np.where(
        ranked["gp_missing_review_flag"],
        "Phase3 review required: Gross Profitability is missing.",
        np.where(ranked["rank"] <= 100, "Priority qualitative moat/theme validation.", "Use as candidate universe sensitivity reference."),
    )
    cols = [
        "rank",
        "code",
        "ticker",
        "company_name",
        "sector",
        "final_exploratory_weighted_score",
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
        "gp_missing_review_flag",
        "phase1_top5_flag",
        "phase2_selected_topn_flag",
        "phase3_priority_flag",
        "phase3_handoff_note",
    ]
    ranked[cols].to_csv(OUT / "rankings" / "final_weighted_ranking_all.csv", index=False)
    for n in [20, 50, 100, 300, 1000, 1200, 1500]:
        ranked[cols].head(n).to_csv(OUT / "rankings" / f"final_weighted_top{n}.csv", index=False)
    checks = []
    for _, row in prep.top5.iterrows():
        hit = ranked[ranked["code"] == row["code"]].iloc[0]
        checks.append(
            {
                "code": row["code"],
                "company_name": row["company_name"],
                "phase1_top5_order": int(row.get("phase1_top5_order", len(checks) + 1)),
                "weighted_rank": int(hit["rank"]),
                "weighted_score": float(hit["final_exploratory_weighted_score"]),
                "in_top100": bool(hit["rank"] <= 100),
                "in_top300": bool(hit["rank"] <= 300),
                "in_top1000": bool(hit["rank"] <= 1000),
                "in_top1200": bool(hit["rank"] <= 1200),
                "in_selected_topn": bool(hit["rank"] <= solution["selected_topn"]),
            }
        )
    pd.DataFrame(checks).to_csv(OUT / "rankings" / "phase1_top5_rank_check_final.csv", index=False)


def topn_outputs(topn: pd.DataFrame, solution: dict) -> None:
    topn.to_csv(OUT / "topn_selection" / "topn_metrics.csv", index=False)
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    text = f"""# TopN Selection Report

## Results

- best_topn_by_utility: {solution["best_topn_by_utility"]}
- best_topn_feasible_max_breadth: {solution["best_topn_feasible_max_breadth"]}
- best_balanced_topn: {solution["best_balanced_topn"]}
- top1200_rank_among_topn: {int(top1200["topn_utility_rank"])}
- top1200_is_optimal: {solution["top1200_is_optimal"]}
- top1200_is_defensible: {solution["top1200_is_defensible"]}

## TopN comparison

{markdown_table(topn[["topn", "feasible", "topn_utility", "topn_utility_rank", "phase1_top5_count", "gross_profitability_median", "sector_hhi", "anomaly_flag_rate", "gp_missing_rate"]], 20)}
"""
    write_text(OUT / "topn_selection" / "topn_selection_report.md", text)


def stability_tests(prep: PreparedData, solution: dict, ranked: pd.DataFrame) -> dict:
    weights = solution["selected_weights"]
    penalties = solution["selected_penalty_weights"]
    params = solution["selected_params"]
    rng = np.random.default_rng(45)
    base_sets = {n: set(ranked.head(n)["code"]) for n in [100, 300, 1000, 1200]}
    rows = []
    for i in range(500):
        noisy = {k: max(0.0001, weights[k] * float(rng.lognormal(0, 0.07))) for k in POSITIVE_KEYS}
        noisy = normalize_weights(noisy)
        rr = ranked_frame(prep, noisy, penalties, params)
        for n in [100, 300, 1000, 1200]:
            s = set(rr.head(n)["code"])
            rows.append({"test": "weight_perturbation", "iteration": i + 1, "topn": n, "jaccard": len(base_sets[n] & s) / len(base_sets[n] | s)})
    for i in range(300):
        sample_codes = set(prep.df.sample(frac=0.85, replace=True, random_state=1000 + i)["code"])
        for n in [100, 300, 1000, 1200]:
            s = set(ranked[ranked["code"].isin(sample_codes)].head(n)["code"])
            denom = len(base_sets[n] | s)
            rows.append({"test": "bootstrap_universe", "iteration": i + 1, "topn": n, "jaccard": len(base_sets[n] & s) / denom if denom else 0})
    stability = pd.DataFrame(rows)
    stability.to_csv(OUT / "validation" / "stability_results_real.csv", index=False)
    stability.groupby(["test", "topn"], as_index=False)["jaccard"].mean().to_csv(OUT / "validation" / "topn_jaccard_by_test.csv", index=False)

    norm_rows = []
    base_rank = ranked.set_index("code")["rank"]
    for method in ["market_percentile", "sector_percentile", "winsorized_zscore", "robust_zscore"]:
        p = dict(params)
        p["normalization_method"] = method
        p["sector_adjustment"] = False
        rr = ranked_frame(prep, weights, penalties, p)
        rank = rr.set_index("code")["rank"].reindex(base_rank.index)
        corr = float(base_rank.corr(rank, method="spearman"))
        for n in [100, 300, 1000, 1200]:
            s = set(rr.head(n)["code"])
            norm_rows.append({"normalization_method": method, "topn": n, "spearman_rank_corr": corr, "jaccard": len(base_sets[n] & s) / len(base_sets[n] | s)})
    pd.DataFrame(norm_rows).to_csv(OUT / "validation" / "normalization_sensitivity.csv", index=False)

    missing_rows = []
    for handling in ["neutral_rank_with_missing_penalty", "median_impute_with_missing_penalty", "exclude_if_core_missing"]:
        p = dict(params)
        p["missing_handling"] = handling
        rr = ranked_frame(prep, weights, penalties, p)
        for n in [100, 300, 1000, 1200]:
            s = set(rr.head(n)["code"])
            missing_rows.append({"missing_handling": handling, "topn": n, "jaccard": len(base_sets[n] & s) / len(base_sets[n] | s)})
    pd.DataFrame(missing_rows).to_csv(OUT / "validation" / "missing_handling_sensitivity.csv", index=False)
    summary = stability.groupby("topn")["jaccard"].mean().to_dict()
    return {f"top{int(k)}_jaccard": float(v) for k, v in summary.items()}


def walk_forward_outputs() -> None:
    scores_path = ROOT / "data" / "processed" / "scores.csv"
    periods = []
    if scores_path.exists():
        try:
            scores = pd.read_csv(scores_path, usecols=lambda c: c in ["effective_date", "latest_date", "code"])
            for col in ["effective_date", "latest_date"]:
                if col in scores.columns:
                    periods.append((col, int(scores[col].nunique(dropna=True))))
        except Exception:
            pass
    pd.DataFrame([{"status": "unavailable", "reason": "No reliable multi-period Phase1 formula snapshot with lookahead-safe filing dates was available.", "detected_periods": json.dumps(periods)}]).to_csv(
        OUT / "validation" / "walk_forward_real.csv", index=False
    )
    write_text(
        OUT / "reports" / "walk_forward_report.md",
        "# Walk-forward Report\n\nWalk-forward optimization was not run because the Phase1 artifact used for this experiment is a single cross-sectional screening snapshot. The detected processed files do not provide a complete, lookahead-safe sequence of fiscal-year snapshots for the Phase1 formulas.\n",
    )
    write_text(
        OUT / "validation" / "walk_forward_unavailable.md",
        "# Walk-forward Unavailable\n\n複数年度の財務データと、lookaheadを避けられるfiling date系列がこのPhase1成果物には揃っていないため、walk-forwardは捏造せず未実施とした。\n",
    )


def gp_missing_review(prep: PreparedData, ranked: pd.DataFrame, solution: dict) -> None:
    rows = []
    for n in [20, 50, 100, 300, 1000, 1200]:
        sub = ranked.head(n)
        rows.append({"topn": n, "gp_missing_count": int(sub["gp_missing_review_flag"].sum()), "gp_missing_rate": float(sub["gp_missing_review_flag"].mean())})
    review = ranked[(ranked["rank"] <= 1200) & ranked["gp_missing_review_flag"]].copy()
    review["inferred_reason"] = np.where(
        review["sector"].astype(str).str.contains("Bank|Insurance|Financial", case=False, na=False),
        "金融・特殊業態",
        "データ欠損または売上原価未取得",
    )
    review[["rank", "code", "ticker", "company_name", "sector", "final_exploratory_weighted_score", "inferred_reason"]].to_csv(OUT / "data_audit" / "gp_missing_review.csv", index=False)
    stronger_params = dict(solution["selected_params"])
    stronger_params["gp_missing_penalty_strength"] = min(0.50, stronger_params.get("gp_missing_penalty_strength", 0.15) + 0.20)
    stronger = ranked_frame(prep, solution["selected_weights"], solution["selected_penalty_weights"], stronger_params)
    diff = ranked[["code", "rank"]].merge(stronger[["code", "rank"]], on="code", suffixes=("_selected", "_strong_gp_penalty"))
    diff["rank_change_positive_means_lower"] = diff["rank_strong_gp_penalty"] - diff["rank_selected"]
    diff.to_csv(OUT / "data_audit" / "gp_missing_penalty_rank_diff.csv", index=False)
    write_text(
        OUT / "reports" / "gp_missing_review_report.md",
        "# GP Missing Review Report\n\n"
        + markdown_table(pd.DataFrame(rows), 10)
        + "\n\n## GP missing companies in Top1200\n\n"
        + markdown_table(review[["rank", "code", "company_name", "sector", "inferred_reason"]], 40),
    )


def ablation(prep: PreparedData, solution: dict) -> pd.DataFrame:
    base = evaluate_solution(prep, solution["selected_weights"], solution["selected_penalty_weights"], solution["selected_params"])
    rows = []
    items = POSITIVE_KEYS + ["anomaly_penalty", "microcap_penalty", "missingness_penalty"]
    for item in items:
        weights = dict(solution["selected_weights"])
        penalties = dict(solution["selected_penalty_weights"])
        if item in weights:
            weights[item] = 0
            weights = normalize_weights(weights)
        elif item == "anomaly_penalty":
            penalties["anomaly"] = 0
        elif item == "microcap_penalty":
            penalties["microcap"] = 0
        elif item == "missingness_penalty":
            penalties["missing"] = 0
        res = evaluate_solution(prep, weights, penalties, solution["selected_params"])
        rows.append(
            {
                "removed_component": item,
                "objective_after_removal": res["objective"],
                "objective_drop": base["objective"] - res["objective"],
                "top1200_utility_drop": base["top1200_utility"] - res["top1200_utility"],
                "best_topn_shift": res["best_topn"] - base["best_topn"],
                "phase1_top5_coverage_change": res["phase1_top5_coverage"] - base["phase1_top5_coverage"],
                "sector_hhi_change": res["sector_hhi"] - base["sector_hhi"],
                "anomaly_rate_change": res["anomaly_rate"] - base["anomaly_rate"],
                "gp_missing_rate_change": res["gp_missing_rate"] - base["gp_missing_rate"],
            }
        )
    out = pd.DataFrame(rows).sort_values("objective_drop", ascending=False)
    out.to_csv(OUT / "ablation" / "ablation_results_real.csv", index=False)
    write_text(OUT / "reports" / "ablation_report_real.md", "# Ablation Report Real\n\n" + markdown_table(out, 20))
    return out


def create_figures(topn: pd.DataFrame, stability_summary: dict, ablation_df: pd.DataFrame, optuna_df: pd.DataFrame, nsga_pareto: pd.DataFrame, solution: dict) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/phase2_real_optimization_matplotlib_cache")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(topn["topn"], topn["topn_utility"], marker="o")
    ax.set_title("TopN Utility Curve")
    ax.set_xlabel("TopN")
    ax.set_ylabel("Utility")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "topn_metric_curves.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(topn["topn"], topn["sector_hhi"], marker="o", color="#7a5195")
    ax.set_title("TopN Sector HHI Curve")
    ax.set_xlabel("TopN")
    ax.set_ylabel("Sector HHI")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "topn_sector_hhi_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(topn["topn"], topn["anomaly_flag_rate"], marker="o", label="Anomaly")
    ax.plot(topn["topn"], topn["review_flag_rate"], marker="o", label="Review")
    ax.set_title("TopN Anomaly / Review Curve")
    ax.set_xlabel("TopN")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "topn_anomaly_review_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(topn["topn"], topn["phase1_top5_count"], marker="o", color="#2f4b7c")
    ax.set_title("Phase1 Top5 Coverage by TopN")
    ax.set_xlabel("TopN")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "topn_phase1_top5_coverage.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(np.arange(1, min(len(optuna_df), 5000) + 1), optuna_df.sort_values("trial_id")["objective"].cummax().head(5000))
    ax.set_title("Optuna TPE Optimization History")
    ax.set_xlabel("Trial")
    ax.set_ylabel("Best objective")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "optuna_optimization_history.png", dpi=150)
    plt.close(fig)

    weights = pd.DataFrame([json.loads(x) for x in optuna_df.head(200)["weights_json"]])
    imp = weights.var().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(imp.index, imp.values, color="#4c956c")
    ax.set_title("Optuna Parameter Importance Proxy")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "optuna_param_importance.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(nsga_pareto["sector_hhi"], nsga_pareto["objective"], s=20, alpha=0.8)
    ax.set_title("NSGA-II Pareto Front")
    ax.set_xlabel("Top1200 sector HHI")
    ax.set_ylabel("Scalar objective reference")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "nsga2_pareto_front.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(nsga_pareto["best_topn_for_trial"], nsga_pareto["topn_utility_best"], s=20, alpha=0.8)
    ax.set_title("NSGA-II Tradeoff: TopN vs Utility")
    ax.set_xlabel("Best TopN")
    ax.set_ylabel("Best TopN utility")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "nsga2_tradeoff_topn_vs_quality.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(nsga_pareto["sector_hhi"], nsga_pareto["topn_utility_best"], s=20, alpha=0.8)
    ax.set_title("NSGA-II Tradeoff: Sector vs Utility")
    ax.set_xlabel("Sector HHI")
    ax.set_ylabel("Utility")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "nsga2_tradeoff_sector_vs_quality.png", dpi=150)
    plt.close(fig)

    stab = pd.read_csv(OUT / "validation" / "stability_results_real.csv")
    heat = stab.pivot_table(index="test", columns="topn", values="jaccard", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(heat.values, aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(heat.columns)), heat.columns)
    ax.set_yticks(range(len(heat.index)), heat.index)
    ax.set_title("Stability Jaccard Heatmap Real")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "stability_jaccard_heatmap_real.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(ablation_df["removed_component"], ablation_df["objective_drop"], color="#bc5090")
    ax.set_title("Ablation Importance")
    ax.set_ylabel("Objective drop")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "ablation_importance_real.png", dpi=150)
    plt.close(fig)


def write_reports(prep: PreparedData, solution: dict, topn: pd.DataFrame, stability_summary: dict, optuna_df: pd.DataFrame, nsga_df: pd.DataFrame) -> None:
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    top1000 = topn[topn["topn"] == 1000].iloc[0]
    top1500 = topn[topn["topn"] == 1500].iloc[0]
    phase1_check = pd.read_csv(OUT / "rankings" / "phase1_top5_rank_check_final.csv")
    selected_weights = pd.DataFrame([{"metric": k, "weight": v} for k, v in solution["selected_weights"].items()])
    selected_penalties = pd.DataFrame([{"penalty": k, "weight": v} for k, v in solution["selected_penalty_weights"].items()])

    write_text(
        OUT / "reports" / "top1200_optimality_report.md",
        f"""# Top1200 Optimality Report

## 1. なぜTop1200を検証対象にしたか
前回成果物でTop1200が候補universeとして妥当そうに見えたため、今回は制約付きTopN utilityで再検証した。

## 2. TopN比較表
{markdown_table(topn[["topn", "feasible", "topn_utility", "topn_utility_rank", "phase1_top5_count", "gross_profitability_median", "sector_hhi", "anomaly_flag_rate", "gp_missing_rate"]], 20)}

## 3. Hard constraintsの充足状況
Top1200 feasible: {bool(top1200["feasible"])}

## 4. TopN utilityランキング
{markdown_table(topn.sort_values("topn_utility_rank")[["topn", "topn_utility", "topn_utility_rank", "feasible"]], 20)}

## 5. Top1200の順位
Top1200 rank among TopN: {int(top1200["topn_utility_rank"])}

## 6. Top1000との比較
Top1000 utility={float(top1000["topn_utility"]):.4f}, sector_hhi={float(top1000["sector_hhi"]):.4f}, anomaly={float(top1000["anomaly_flag_rate"]):.4f}

## 7. Top1300/1500との比較
Top1500 utility={float(top1500["topn_utility"]):.4f}, sector_hhi={float(top1500["sector_hhi"]):.4f}, anomaly={float(top1500["anomaly_flag_rate"]):.4f}

## 8. Top1200が最適と言える場合の根拠
top1200_is_optimal = {solution["top1200_is_optimal"]}。

## 9. Top1200が最適とは言えない場合の代替TopN
best_topn_by_utility = {solution["best_topn_by_utility"]}。best_balanced_topn = {solution["best_balanced_topn"]}。

## 10. レポートで使うべき表現
「本実験の評価関数と制約条件のもとで、Top1200が最もバランスがよい / または十分妥当」と表現する。絶対的に正しいとは書かない。
""",
    )

    write_text(
        OUT / "reports" / "phase2_real_optimization_report.md",
        f"""# Phase2 Real Optimization Report

## 1. Phase2の目的
Phase1で使った先行研究式の定義を変えず、式の使い方、重み、候補群サイズ、欠損処理、業種調整を検証する。

## 2. Phase1との違い
Phase1は「守」であり、独自重み付き総合式なしの段階スクリーニングだった。Phase2は「破」として、式そのものではなく適用条件を比較した。

## 3. Phase2が「破」である理由
既存式を尊重しながら、Optuna TPEとNSGA-IIで条件空間を探索し、TopNや欠損処理の妥当性を反証可能な形で調べた。

## 4. 式そのものは変えていない
B/M、E/P、Gross Profitability、Piotroski、Sloan、distress safety proxy、liquidityというPhase1由来の式・指標を用いた。

## 5. 変えたもの
重み、適用条件、候補群サイズ、欠損処理、業種調整、GP欠損ペナルティ、concentration penalty。

## 6. AIは銘柄を直接選んでいない
AI/Optunaは式の使い方を比較・検証した。銘柄の最終採用判断はPhase3の定性確認に残す。

## 7. Optuna TPE
`optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)` で {len(optuna_df)} trialsを実行した。

## 8. NSGA-II
`optuna.samplers.NSGAIISampler(seed=43, population_size=100)` で {len(nsga_df)} trialsを実行した。

## 9. Top1200検証結果
top1200_is_optimal={solution["top1200_is_optimal"]}, top1200_is_defensible={solution["top1200_is_defensible"]}, selected_topn={solution["selected_topn"]}。

## 10. Phase1 Top5との整合性
{markdown_table(phase1_check, 10)}

## 11. Phase3への接続
Top100は優先定性確認、Top300は候補深掘り、Top1200はPhase2 candidate universe、Top1500は感度参照として使う。

## 12. 限界
walk-forwardは単一スナップショット制約により未実施。将来リターン最大化モデルではない。

## 13. 採用推奨
Exploratory Weighted Buffett ScoreはPhase3候補探索・review flag管理・TopN根拠作りに限定して採用する。

## 14. レポート本文に貼れる要約
本実験では、Phase1の先行研究式を変更せず、Optuna TPEとNSGA-IIにより重み・欠損処理・業種調整・候補群サイズを探索した。得られたスコアは正式なBuffett Scoreではなく、Phase3の候補探索を支援するExploratory Weighted Buffett Scoreである。

## Selected weights
{markdown_table(selected_weights, 20)}

## Selected penalties
{markdown_table(selected_penalties, 20)}
""",
    )

    gp_review = pd.read_csv(OUT / "data_audit" / "gp_missing_review.csv")
    write_text(
        OUT / "reports" / "phase2_to_phase3_handoff_final.md",
        f"""# Phase2 To Phase3 Handoff Final

- Phase2 final candidate universe: Top{solution["selected_topn"]}
- Top100: priority qualitative review
- Top300: focused candidate pool
- Top1200: broad Phase2 universe
- Top1500: sensitivity reference
- Phase1 Top5 coverage in Top1200: {int(top1200["phase1_top5_count"])}/5

## Phase1 Top5
{markdown_table(phase1_check, 10)}

## GP missing review companies
{markdown_table(gp_review, 30)}

## Review flags
Phase3ではGP欠損、anomaly flags、distress review、microcap、one-time profit suspected、missingness penaltyを確認する。

## 変わるMoat・生まれるMoatへの接続
Top100/Top300を中心に、事業変化、技術・データ・自動化・信頼性テーマと財務品質を接続して定性確認する。
""",
    )

    stab = pd.read_csv(OUT / "validation" / "topn_jaccard_by_test.csv")
    write_text(OUT / "reports" / "stability_report_real.md", "# Stability Report Real\n\n" + markdown_table(stab, 20))


def write_readme_manifest(solution: dict, topn: pd.DataFrame, stability_summary: dict, input_paths: list[Path], optuna_n: int, nsga_n: int) -> None:
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    readme = f"""# BEYOND BUFFETT Phase2 Real Optimization

## この成果物の位置づけ

これはBEYOND BUFFETT Phase2（破）の本格最適化版である。  
Phase1の正式ルールを置き換えるものではない。  
Phase1で使った先行研究式の定義は変えていない。  
本成果物では、本物のOptuna TPEとNSGA-IIを用いて、重み・候補群サイズ・欠損処理・業種調整・TopNの妥当性を検証した。

## 重要な結論

- selected TopN: {solution["selected_topn"]}
- Top1200 optimal: {solution["top1200_is_optimal"]}
- Top1200 defensible: {solution["top1200_is_defensible"]}
- Phase1 Top5 coverage in Top1200: {int(top1200["phase1_top5_count"])}/5
- selected weights: `{json.dumps(solution["selected_weights"], ensure_ascii=False)}`
- Optuna trial数: {optuna_n}
- NSGA-II trial数: {nsga_n}
- stability結果: `{json.dumps(stability_summary, ensure_ascii=False)}`

## 注意

Exploratory Weighted Buffett Scoreは正式なBuffett Scoreではない。  
将来リターン最大化モデルではない。  
AIは銘柄を直接選ぶのではなく、Phase1式の使い方を比較・検証するために使った。
"""
    write_text(OUT / "README.md", readme)
    manifest = {
        "project": "BEYOND BUFFETT",
        "phase": "Phase2 Real Optimization",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "description": "本物のOptuna TPESamplerとNSGAIISamplerを用いたPhase2（破）の重み・TopN・欠損処理・業種調整の本格探索成果物。",
        "input_files": [rel(p) for p in input_paths],
        "main_outputs": [
            "reports/phase2_real_optimization_report.md",
            "reports/top1200_optimality_report.md",
            "reports/phase2_to_phase3_handoff_final.md",
            "optimization/selected_phase2_solution.json",
            "optimization/optuna_tpe_real_trials.csv",
            "optimization/nsga2_pareto_front.csv",
            "topn_selection/topn_metrics.csv",
            "rankings/final_weighted_top1200.csv",
        ],
        "important_note": "Exploratory Weighted Buffett Score is not the official Phase1 Buffett Core formula.",
    }
    write_text(OUT / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))


def checksums() -> None:
    rows = []
    exts = {".csv", ".json", ".md", ".png", ".py", ".sh", ".pkl", ".sqlite3", ".yaml"}
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name == "checksums.txt":
            continue
        if "vendor" in path.relative_to(OUT).parts:
            continue
        if path.suffix in exts or path.name == "run_all.sh":
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(OUT)}")
    write_text(OUT / "checksums.txt", "\n".join(rows))


def validation_and_zip() -> Path:
    required = [
        "README.md",
        "manifest.json",
        "reports/phase2_real_optimization_report.md",
        "reports/top1200_optimality_report.md",
        "reports/phase2_to_phase3_handoff_final.md",
        "optimization/selected_phase2_solution.json",
        "optimization/optuna_tpe_real_trials.csv",
        "optimization/nsga2_pareto_front.csv",
        "topn_selection/topn_metrics.csv",
        "rankings/final_weighted_top1200.csv",
        "rankings/phase1_top5_rank_check_final.csv",
        "validation/stability_results_real.csv",
        "data_audit/gp_missing_review.csv",
    ]
    errors = []
    for r in required:
        p = OUT / r
        if not p.exists():
            errors.append(f"Missing: {r}")
        elif p.is_file() and p.stat().st_size == 0:
            errors.append(f"Empty: {r}")
    write_text(OUT / "logs" / "final_validation_errors.md", "# Final Validation Errors\n\n" + ("\n".join(f"- {e}" for e in errors) if errors else "- None"))
    zip_path = ROOT / "outputs" / "phase2_real_optimization.zip"
    if zip_path.exists():
        zip_path.unlink()
    exclude_parts = {"vendor", "__pycache__", ".git", ".venv", "venv", "node_modules"}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(OUT.rglob("*")):
            if path.is_dir():
                continue
            rel_path = path.relative_to(OUT)
            if any(part in exclude_parts for part in rel_path.parts):
                continue
            if path.name == ".DS_Store" or path.suffix == ".tmp":
                continue
            zf.write(path, Path("phase2_real_optimization") / rel_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    zip_required = [f"phase2_real_optimization/{r}" for r in required]
    lines = [
        "# ZIP Validation Report",
        "",
        f"- ZIP exists: {zip_path.exists()}",
        f"- ZIP size MB: {zip_path.stat().st_size / (1024 * 1024):.3f}",
        "",
        "## Required checks",
    ]
    for r in zip_required:
        lines.append(f"- {r}: {'OK' if r in names else 'MISSING'}")
    lines.append("\n## Missing\n")
    missing = [r for r in zip_required if r not in names]
    lines.extend([f"- {m}" for m in missing] or ["- None"])
    lines.append("\n## File listing")
    lines.extend(f"- {n}" for n in sorted(names))
    write_text(OUT / "logs" / "zip_validation_report.md", "\n".join(lines))
    checksums()
    return zip_path


def copy_scripts() -> None:
    init = OUT / "scripts" / "phase2_real_optimizer" / "__init__.py"
    write_text(init, '"""Phase2 real optimization scripts."""')
    delegates = {
        "optuna_tpe_real.py": "run_optuna_tpe",
        "nsga2_real.py": "run_nsga2",
        "random_search_real.py": "run_baseline_random",
        "validation_real.py": "stability_tests",
        "reporting_real.py": "main",
    }
    for name in delegates:
        write_text(
            OUT / "scripts" / "phase2_real_optimizer" / name,
            "from .run_real_optimization import main\n\nif __name__ == '__main__':\n    main()\n",
        )
    run_all = OUT / "scripts" / "phase2_real_optimizer" / "run_all.sh"
    write_text(
        run_all,
        """#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT_DIR"
python3 outputs/phase2_real_optimization/scripts/phase2_real_optimizer/run_real_optimization.py
""",
    )
    run_all.chmod(0o755)


def write_config_files() -> None:
    write_text(
        OUT / "configs" / "optimization_config.yaml",
        """optuna_tpe:
  sampler: optuna.samplers.TPESampler(seed=42, multivariate=True, group=True)
  n_trials: 5000
nsga2:
  sampler: optuna.samplers.NSGAIISampler(seed=43, population_size=100)
  n_trials: 3000
random_search:
  n_trials: 10000
main_score_name: Exploratory Weighted Buffett Score
""",
    )


def main() -> None:
    start_all = time.perf_counter()
    ensure_dirs()
    input_paths = input_audit()
    previous_artifact_review()
    env = environment_report()
    write_config_files()
    copy_scripts()
    df, top5 = load_data()
    prep = prepare_metrics(df, top5)
    optuna_df, optuna_best = run_optuna_tpe(prep, 5000)
    nsga_df, nsga_pareto, nsga_selected = run_nsga2(prep, 3000)
    baseline_df, random_df = run_baseline_random(prep, 10000)
    solution, ranked, topn = select_final_solution(prep, optuna_df, nsga_pareto, random_df)
    final_rankings(ranked, prep, solution)
    topn_outputs(topn, solution)
    walk_forward_outputs()
    gp_missing_review(prep, ranked, solution)
    stability_summary = stability_tests(prep, solution, ranked)
    ablation_df = ablation(prep, solution)
    create_figures(topn, stability_summary, ablation_df, optuna_df, nsga_pareto, solution)
    write_reports(prep, solution, topn, stability_summary, optuna_df, nsga_df)
    write_readme_manifest(solution, topn, stability_summary, input_paths, len(optuna_df), len(nsga_df))
    checksums()
    zip_path = validation_and_zip()
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    msg = f"""Phase2 real optimization completed.

Output directory:
outputs/phase2_real_optimization/

ZIP:
outputs/phase2_real_optimization.zip

Key reports:
- reports/phase2_real_optimization_report.md
- reports/top1200_optimality_report.md
- reports/phase2_to_phase3_handoff_final.md
- reports/stability_report_real.md
- reports/ablation_report_real.md
- reports/gp_missing_review_report.md

Key data:
- optimization/selected_phase2_solution.json
- optimization/optuna_tpe_real_trials.csv
- optimization/nsga2_pareto_front.csv
- topn_selection/topn_metrics.csv
- rankings/final_weighted_top1200.csv
- rankings/phase1_top5_rank_check_final.csv

Summary:
- selected_topn = {solution["selected_topn"]}
- top1200_is_optimal = {solution["top1200_is_optimal"]}
- top1200_is_defensible = {solution["top1200_is_defensible"]}
- optuna_trials = {len(optuna_df)}
- nsga2_trials = {len(nsga_df)}
- phase1_top5_coverage = {int(top1200["phase1_top5_count"])}/5
- stability_top1200_jaccard = {stability_summary.get("top1200_jaccard", float("nan")):.4f}
- sector_hhi_top1200 = {float(top1200["sector_hhi"]):.4f}
- distress_flag_rate_top1200 = {float(top1200["distress_flag_rate"]):.4f}
- anomaly_rate_top1200 = {float(top1200["anomaly_flag_rate"]):.4f}
- zip_size_mb = {zip_path.stat().st_size / (1024 * 1024):.3f}
- elapsed_sec = {time.perf_counter() - start_all:.1f}
"""
    write_text(OUT / "logs" / "summary.log", msg)
    print(msg)


if __name__ == "__main__":
    main()
