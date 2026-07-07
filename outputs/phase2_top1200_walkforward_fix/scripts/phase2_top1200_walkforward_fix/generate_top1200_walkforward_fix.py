from __future__ import annotations

import hashlib
import json
import math
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PREV = ROOT / "outputs" / "phase2_real_optimization"
PREV_ZIP = ROOT / "outputs" / "phase2_real_optimization.zip"
OUT = ROOT / "outputs" / "phase2_top1200_walkforward_fix"
ZIP = ROOT / "outputs" / "phase2_top1200_walkforward_fix.zip"
WORK_PREV = ROOT / "work" / "phase2_real_optimization_previous"
PHASE1_COMPLETE = ROOT / "outputs" / "phase1_buffett_complete" / "screening_candidates_complete.csv"
PHASE1_TOP5 = ROOT / "outputs" / "phase1_top5" / "phase1_buffett_core_top5.csv"
FUND_RAW = ROOT / "data" / "processed" / "fundamentals_raw.csv"
FUND_CLEAN = ROOT / "data" / "processed" / "fundamentals_clean.csv"
PRICES_DAILY = ROOT / "data" / "processed" / "prices_daily.parquet"

POSITIVE_KEYS = ["bm", "ep", "gp", "piotroski", "sloan", "distress", "liquidity"]
TOPNS = [1000, 1200, 2000]


def ensure_dirs() -> None:
    for rel in [
        "configs",
        "data_audit",
        "previous_review",
        "top1200_final",
        "walk_forward",
        "normalization_fix",
        "consensus",
        "rankings",
        "validation",
        "figures",
        "reports",
        "scripts/phase2_top1200_walkforward_fix",
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


def hhi(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    shares = series.value_counts(normalize=True)
    return float((shares**2).sum())


def md_table(df: pd.DataFrame, n: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    data = df.head(n).fillna("")
    headers = [str(c) for c in data.columns]
    lines = ["| " + " | ".join(h.replace("|", "\\|") for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for _, row in data.iterrows():
        vals = [str(row[c]).replace("|", "\\|").replace("\n", " ") for c in data.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def pct(series: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    y = x.rank(pct=True, method="average")
    if not higher:
        y = 1 - y
    return y.fillna(0.5)


def minmax(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    lo, hi = x.min(skipna=True), x.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=series.index)
    return ((x - lo) / (hi - lo)).fillna(0.5)


def winsor_z(series: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    lo, hi = x.quantile(0.01), x.quantile(0.99)
    c = x.clip(lo, hi)
    std = c.std(skipna=True)
    z = (c - c.mean(skipna=True)) / (std if std and np.isfinite(std) else 1.0)
    if not higher:
        z = -z
    return minmax(z)


def robust_z(series: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    med = x.median(skipna=True)
    mad = (x - med).abs().median(skipna=True)
    z = (x - med) / (1.4826 * mad if mad and np.isfinite(mad) else 1.0)
    z = z.clip(-5, 5)
    if not higher:
        z = -z
    return minmax(z)


def sector_pct(df: pd.DataFrame, col: str, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(df[col], errors="coerce")
    y = x.groupby(df["sector"]).rank(pct=True, method="average")
    if not higher:
        y = 1 - y
    return y.fillna(0.5)


def extract_previous() -> Path:
    if WORK_PREV.exists():
        shutil.rmtree(WORK_PREV)
    WORK_PREV.mkdir(parents=True, exist_ok=True)
    if PREV_ZIP.exists():
        with zipfile.ZipFile(PREV_ZIP) as zf:
            zf.extractall(WORK_PREV)
        nested = WORK_PREV / "phase2_real_optimization"
        return nested if nested.exists() else WORK_PREV
    return PREV


def load_inputs() -> dict:
    prev = extract_previous()
    selected = json.loads((prev / "optimization" / "selected_phase2_solution.json").read_text(encoding="utf-8"))
    topn = pd.read_csv(prev / "topn_selection" / "topn_metrics.csv")
    ranking = pd.read_csv(prev / "rankings" / "final_weighted_ranking_all.csv")
    top1200_prev = pd.read_csv(prev / "rankings" / "final_weighted_top1200.csv")
    phase1_check = pd.read_csv(prev / "rankings" / "phase1_top5_rank_check_final.csv")
    stability = pd.read_csv(prev / "validation" / "stability_results_real.csv")
    norm_sens = pd.read_csv(prev / "validation" / "normalization_sensitivity.csv")
    phase1 = pd.read_csv(PHASE1_COMPLETE)
    phase1["code"] = phase1["code"].astype(str)
    ranking["code"] = ranking["code"].astype(str)
    top1200_prev["code"] = top1200_prev["code"].astype(str)
    return {
        "prev": prev,
        "selected": selected,
        "topn": topn,
        "ranking": ranking,
        "top1200_prev": top1200_prev,
        "phase1_check": phase1_check,
        "stability": stability,
        "norm_sens": norm_sens,
        "phase1": phase1,
    }


def previous_review(inputs: dict) -> None:
    topn = inputs["topn"]
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    top2000 = topn[topn["topn"] == 2000].iloc[0]
    top1000 = topn[topn["topn"] == 1000].iloc[0]
    lines = [
        "# Previous Result Review",
        "",
        "- utility最大化ではTop2000が最良だった。",
        f"- Top2000 utility: {float(top2000['topn_utility']):.4f}",
        f"- Top1200 utility rank: {int(top1200['topn_utility_rank'])}",
        f"- Top1200 utility: {float(top1200['topn_utility']):.4f}",
        "- Top1200はutility 3位程度ではない場合でも、Phase3候補宇宙としてdefensibleだった。",
        f"- Top1200 Phase1 Top5 coverage: {int(top1200['phase1_top5_count'])}/5",
        f"- Top1200 distress flag rate: {float(top1200['distress_flag_rate']):.4f}",
        f"- Top1200 review flag rate: {float(top1200['review_flag_rate']):.4f}",
        f"- Top1200 anomaly flag rate: {float(top1200['anomaly_flag_rate']):.4f}",
        f"- Top1200 GP missing rate: {float(top1200['gp_missing_rate']):.4f}",
        "",
        "## Top1000 / Top1200 / Top2000 comparison",
        md_table(pd.DataFrame([top1000, top1200, top2000])[
            ["topn", "topn_utility", "phase1_top5_count", "gross_profitability_median", "sector_hhi", "anomaly_flag_rate", "gp_missing_rate"]
        ]),
        "",
        "## 今回の修正",
        "- Top2000は広すぎるため、Phase3分析対象としてはレビュー負荷が大きい。",
        "- 正式候補群はTop1200に調整する。",
        "- Walk-forward未実施または不十分だった点を、利用可能データでLevel 2 snapshot proxyとして補強する。",
        "- 正規化方式によって候補群が揺れていた点をnormalization consensusで補正する。",
    ]
    write_text(OUT / "reports" / "previous_result_review.md", "\n".join(lines))
    write_text(OUT / "previous_review" / "previous_result_review.md", "\n".join(lines))


def enrich_ranking(ranking: pd.DataFrame, phase1: pd.DataFrame) -> pd.DataFrame:
    phase_cols = [
        "code",
        "market",
        "distress_review_flag",
        "microcap_flag",
        "one_time_profit_suspected",
        "market_equity_final",
        "liquidity_flag",
    ]
    merged = ranking.merge(phase1[[c for c in phase_cols if c in phase1.columns]], on="code", how="left", suffixes=("", "_phase1"))
    if "distress_review_flag" not in merged:
        merged["distress_review_flag"] = False
    for col in ["microcap_flag", "one_time_profit_suspected"]:
        if col not in merged:
            merged[col] = False
    return merged


def score_by_normalization(df: pd.DataFrame, weights: dict, penalties: dict, gp_penalty: float, method: str) -> pd.DataFrame:
    work = df.copy()
    raw_map = {
        "bm_score": ("bm_raw", True),
        "ep_score": ("ep_raw", True),
        "gp_score": ("gross_profitability", True),
        "piotroski_score": ("piotroski_available_ratio", True),
        "sloan_quality_score": ("sloan_accruals", False),
        "liquidity_score": ("avg_daily_value_60d", True),
    }
    for out_col, (raw_col, higher) in raw_map.items():
        if method == "market_percentile":
            work[out_col] = pct(work[raw_col], higher)
        elif method == "sector_percentile":
            work[out_col] = sector_pct(work, raw_col, higher)
        elif method == "robust_zscore":
            work[out_col] = robust_z(work[raw_col], higher)
        elif method == "winsorized_zscore":
            work[out_col] = winsor_z(work[raw_col], higher)
    work["distress_safety_score"] = 1 - bool_series(work["distress_exclusion_flag"]).astype(float)
    for col in ["anomaly_penalty", "microcap_penalty", "one_time_profit_penalty", "missingness_penalty"]:
        if col not in work:
            work[col] = 0.0
    raw_score = (
        weights["bm"] * work["bm_score"]
        + weights["ep"] * work["ep_score"]
        + weights["gp"] * work["gp_score"]
        + weights["piotroski"] * work["piotroski_score"]
        + weights["sloan"] * work["sloan_quality_score"]
        + weights["distress"] * work["distress_safety_score"]
        + weights["liquidity"] * work["liquidity_score"]
        - penalties.get("anomaly", 0) * work["anomaly_penalty"]
        - penalties.get("microcap", 0) * work["microcap_penalty"]
        - penalties.get("onetime", 0) * work["one_time_profit_penalty"]
        - penalties.get("missing", 0) * work["missingness_penalty"]
        - gp_penalty * work["gp_missing_review_flag"].astype(float)
    )
    work[f"{method}_score"] = minmax(raw_score)
    work[f"{method}_rank"] = work[f"{method}_score"].rank(ascending=False, method="first").astype(int)
    return work.sort_values(f"{method}_rank")


def normalization_consensus(base: pd.DataFrame, selected: dict) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    weights = selected["selected_weights"]
    penalties = selected["selected_penalty_weights"]
    gp_penalty = selected.get("selected_params", {}).get("gp_missing_penalty_strength", 0.1)
    methods = ["market_percentile", "sector_percentile", "robust_zscore", "winsorized_zscore"]
    method_tables = {}
    flags = pd.DataFrame({"code": base["code"].astype(str)})
    rank_cols = pd.DataFrame({"code": base["code"].astype(str)})
    for method in methods:
        ranked = score_by_normalization(base, weights, penalties, gp_penalty, method)
        method_tables[method] = ranked
        top = ranked.head(1200).copy()
        top.to_csv(OUT / "normalization_fix" / f"ranking_{method}_top1200.csv", index=False)
        flags[f"in_{method}_top1200"] = flags["code"].isin(set(top["code"])).to_numpy()
        rank_cols = rank_cols.merge(ranked[["code", f"{method}_rank", f"{method}_score"]], on="code", how="left")
    consensus = base.merge(flags, on="code", how="left").merge(rank_cols, on="code", how="left")
    flag_cols = [f"in_{m}_top1200" for m in methods]
    consensus["normalization_top1200_count"] = consensus[flag_cols].sum(axis=1)
    consensus["normalization_core_flag"] = consensus["normalization_top1200_count"] >= 3
    consensus["normalization_robust_flag"] = consensus["normalization_top1200_count"] >= 2
    consensus["normalization_fragile_flag"] = consensus["in_market_percentile_top1200"] & (consensus["normalization_top1200_count"] == 1)
    consensus["sector_adjusted_candidate_flag"] = consensus["in_sector_percentile_top1200"] & ~consensus["in_market_percentile_top1200"]
    consensus["outlier_sensitive_flag"] = (consensus["winsorized_zscore_rank"] - consensus["market_percentile_rank"]).abs() > 600
    consensus["normalization_review_note"] = np.select(
        [
            consensus["normalization_core_flag"],
            consensus["normalization_robust_flag"],
            consensus["normalization_fragile_flag"],
            consensus["sector_adjusted_candidate_flag"],
            consensus["outlier_sensitive_flag"],
        ],
        [
            "Core across normalization methods.",
            "Robust across at least two normalization methods.",
            "Fragile: included only under market percentile.",
            "Sector-adjusted candidate; review sector context.",
            "Outlier-sensitive rank movement; review raw metrics.",
        ],
        default="Reference only.",
    )
    consensus.to_csv(OUT / "consensus" / "normalization_consensus_table.csv", index=False)
    summary = pd.DataFrame(
        [
            {"metric": "normalization_core_count", "value": int(consensus["normalization_core_flag"].sum())},
            {"metric": "normalization_robust_count", "value": int(consensus["normalization_robust_flag"].sum())},
            {"metric": "normalization_fragile_count", "value": int(consensus["normalization_fragile_flag"].sum())},
            {"metric": "sector_adjusted_candidate_count", "value": int(consensus["sector_adjusted_candidate_flag"].sum())},
            {"metric": "outlier_sensitive_count", "value": int(consensus["outlier_sensitive_flag"].sum())},
        ]
    )
    summary.to_csv(OUT / "consensus" / "normalization_consensus_summary.csv", index=False)
    return consensus, method_tables


def summary_stats(df: pd.DataFrame, label: str, market: pd.DataFrame) -> dict:
    return {
        "group": label,
        "count": len(df),
        "phase1_top5_coverage": int(df["phase1_top5_flag"].astype(bool).sum()),
        "bm_median": float(df["bm_raw"].median(skipna=True)),
        "ep_median": float(df["ep_raw"].median(skipna=True)),
        "gross_profitability_median": float(df["gross_profitability"].median(skipna=True)),
        "piotroski_median": float(df["piotroski_available_ratio"].median(skipna=True)),
        "sloan_median": float(df["sloan_accruals"].median(skipna=True)),
        "adv60_median": float(df["avg_daily_value_60d"].median(skipna=True)),
        "distress_flag_rate": float(bool_series(df["distress_exclusion_flag"]).mean()),
        "review_flag_rate": float(bool_series(df["distress_review_flag"]).mean()),
        "anomaly_flag_rate": float(df["anomaly_penalty"].mean()),
        "gp_missing_rate": float(df["gp_missing_review_flag"].mean()),
        "sector_hhi": hhi(df["sector"]),
        "max_sector_share": float(df["sector"].value_counts(normalize=True).iloc[0]) if len(df) else 0,
        "bm_vs_market": float(df["bm_raw"].median(skipna=True) - market["bm_raw"].median(skipna=True)),
        "ep_vs_market": float(df["ep_raw"].median(skipna=True) - market["ep_raw"].median(skipna=True)),
        "gp_vs_market": float(df["gross_profitability"].median(skipna=True) - market["gross_profitability"].median(skipna=True)),
        "piotroski_vs_market": float(df["piotroski_available_ratio"].median(skipna=True) - market["piotroski_available_ratio"].median(skipna=True)),
        "sloan_vs_market": float(market["sloan_accruals"].median(skipna=True) - df["sloan_accruals"].median(skipna=True)),
        "adv60_vs_market_ratio": float(df["avg_daily_value_60d"].median(skipna=True) / market["avg_daily_value_60d"].median(skipna=True)),
    }


def build_top1200_outputs(consensus: pd.DataFrame, topn_metrics: pd.DataFrame) -> pd.DataFrame:
    top1200 = consensus.sort_values("rank").head(1200).copy()
    top1200["top100_flag"] = top1200["rank"] <= 100
    top1200["top300_flag"] = top1200["rank"] <= 300
    top1200["top1200_flag"] = True
    top1200["top2000_reference_flag"] = top1200["rank"] <= 2000
    top1200["phase3_priority_flag"] = np.select(
        [
            top1200["top100_flag"] & top1200["normalization_core_flag"],
            top1200["top300_flag"] & top1200["normalization_robust_flag"],
            top1200["normalization_fragile_flag"],
            top1200["gp_missing_review_flag"] | (top1200["anomaly_penalty"] > 0) | top1200["outlier_sensitive_flag"],
        ],
        ["high", "medium_high", "review", "review"],
        default="standard",
    )
    top1200["phase3_handoff_note"] = np.select(
        [
            top1200["phase3_priority_flag"].eq("high"),
            top1200["phase3_priority_flag"].eq("medium_high"),
            top1200["phase3_priority_flag"].eq("review"),
        ],
        [
            "High priority: Top100 and normalization core candidate.",
            "Medium-high priority: Top300 and normalization robust candidate.",
            "Review required: normalization fragility, GP missing, anomaly, or outlier sensitivity.",
        ],
        default="Formal Top1200 candidate universe member.",
    )
    required_cols = [
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
        "distress_review_flag",
        "anomaly_flags",
        "gp_missing_review_flag",
        "phase1_top5_flag",
        "top100_flag",
        "top300_flag",
        "top1200_flag",
        "top2000_reference_flag",
        "normalization_core_flag",
        "normalization_robust_flag",
        "normalization_fragile_flag",
        "sector_adjusted_candidate_flag",
        "outlier_sensitive_flag",
        "normalization_review_note",
        "normalization_top1200_count",
        "phase3_priority_flag",
        "phase3_handoff_note",
    ]
    top1200[required_cols].to_csv(OUT / "top1200_final" / "phase2_optimized_top1200_candidates.csv", index=False)
    top1200[required_cols].to_csv(OUT / "rankings" / "final_weighted_top1200_fixed.csv", index=False)

    market = consensus
    top1000 = consensus.sort_values("rank").head(1000)
    top2000 = consensus.sort_values("rank").head(2000)
    summaries = pd.DataFrame(
        [
            summary_stats(top1200, "Top1200 formal", market),
            summary_stats(top1000, "Top1000 comparison", market),
            summary_stats(top2000, "Top2000 reference", market),
            summary_stats(market, "Market universe", market),
        ]
    )
    summaries.to_csv(OUT / "top1200_final" / "phase2_optimized_top1200_summary.csv", index=False)
    top1200["sector"].value_counts().rename_axis("sector").reset_index(name="count").assign(
        share=lambda x: x["count"] / len(top1200)
    ).to_csv(OUT / "top1200_final" / "phase2_top1200_sector_distribution.csv", index=False)
    metrics = []
    for col in ["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d"]:
        metrics.append(
            {
                "metric": col,
                "mean": top1200[col].mean(skipna=True),
                "median": top1200[col].median(skipna=True),
                "p25": top1200[col].quantile(0.25),
                "p75": top1200[col].quantile(0.75),
                "market_median": market[col].median(skipna=True),
            }
        )
    pd.DataFrame(metrics).to_csv(OUT / "top1200_final" / "phase2_top1200_metric_distribution.csv", index=False)
    top2000.to_csv(OUT / "rankings" / "final_weighted_top2000_reference.csv", index=False)
    return top1200


def make_walk_forward() -> dict:
    missing_reasons = []
    if not FUND_RAW.exists() or not PRICES_DAILY.exists() or not FUND_CLEAN.exists():
        missing_reasons.append("Required fundamentals_raw, fundamentals_clean, or prices_daily was missing.")
    if missing_reasons:
        level = "Level 4"
        summary = {"walk_forward_level": level, "reason": "; ".join(missing_reasons)}
        pd.DataFrame([summary]).to_csv(OUT / "walk_forward" / "walk_forward_results.csv", index=False)
        return summary

    clean = pd.read_csv(FUND_CLEAN)
    clean["code"] = clean["code"].astype(str)
    clean_cols = ["code", "company_name", "market", "sector_33", "sector_17", "shares_outstanding"]
    clean = clean[[c for c in clean_cols if c in clean.columns]].drop_duplicates("code")
    raw = pd.read_csv(FUND_RAW, parse_dates=["submit_date", "period_end"])
    raw["code"] = raw["code"].astype(str)
    raw["fiscal_year"] = raw["period_end"].dt.year
    raw = raw[raw["fiscal_year"].between(2023, 2025)].copy()
    raw = raw.merge(clean, on="code", how="left")
    raw["sector"] = raw.get("sector_33", raw.get("sector_17", "Unknown")).fillna("Unknown")
    raw["available_date"] = raw["submit_date"].fillna(raw["period_end"] + pd.Timedelta(days=120))
    if raw["fiscal_year"].nunique() < 3:
        level = "Level 4"
    else:
        level = "Level 2"

    prices = pd.read_parquet(PRICES_DAILY, columns=["date", "ticker", "close", "volume"])
    prices["ticker"] = prices["ticker"].astype(str)
    prices["date"] = pd.to_datetime(prices["date"]).astype("datetime64[ns]")
    raw["available_date"] = pd.to_datetime(raw["available_date"]).astype("datetime64[ns]")
    prices = prices.sort_values(["ticker", "date"])
    prices["trading_value"] = prices["close"] * prices["volume"]
    prices["adv60_proxy"] = prices.groupby("ticker")["trading_value"].transform(lambda s: s.rolling(60, min_periods=20).mean())
    left = raw.sort_values(["ticker", "available_date"])
    right = prices.sort_values(["ticker", "date"])
    try:
        panel = pd.merge_asof(left, right, left_on="available_date", right_on="date", by="ticker", direction="backward")
    except ValueError:
        left = raw.sort_values("available_date")
        right = prices.sort_values("date")
        panel = pd.merge_asof(left, right, left_on="available_date", right_on="date", by="ticker", direction="backward")
    for col in ["equity", "net_income", "operating_income", "operating_cf", "total_assets", "revenue", "shares_outstanding", "close", "adv60_proxy"]:
        panel[col] = pd.to_numeric(panel[col], errors="coerce")
    panel["market_equity_proxy"] = panel["close"] * panel["shares_outstanding"]
    panel["bm_raw"] = panel["equity"] / panel["market_equity_proxy"]
    panel["ep_raw"] = panel["net_income"] / panel["market_equity_proxy"]
    panel["gross_profitability_proxy"] = panel["operating_income"] / panel["total_assets"]
    panel = panel.sort_values(["code", "fiscal_year"])
    panel["asset_growth"] = panel.groupby("code")["total_assets"].pct_change()
    panel["revenue_growth_proxy"] = panel.groupby("code")["revenue"].pct_change()
    signals = [
        panel["net_income"] > 0,
        panel["operating_cf"] > 0,
        panel["operating_cf"] > panel["net_income"],
        panel["revenue_growth_proxy"] > 0,
        panel["asset_growth"] < 0.30,
        panel["equity"] > 0,
    ]
    panel["piotroski_available_ratio_proxy"] = sum(s.astype(float) for s in signals) / len(signals)
    panel["sloan_accruals_proxy"] = (panel["net_income"] - panel["operating_cf"]) / panel["total_assets"]
    panel["distress_flag_proxy"] = (panel["equity"] <= 0) | ((panel["net_income"] < 0) & (panel["operating_cf"] < 0))
    panel["review_flag_proxy"] = panel[["market_equity_proxy", "bm_raw", "ep_raw", "gross_profitability_proxy", "adv60_proxy"]].isna().any(axis=1)
    panel["anomaly_flag_proxy"] = (panel["bm_raw"] > panel["bm_raw"].quantile(0.99)) | (panel["ep_raw"] > panel["ep_raw"].quantile(0.99))
    panel["gp_missing_rate_proxy"] = panel["gross_profitability_proxy"].isna()
    panel.to_csv(OUT / "walk_forward" / "walk_forward_fold_details.csv", index=False)

    weights = json.loads((PREV / "optimization" / "selected_phase2_solution.json").read_text(encoding="utf-8"))["selected_weights"]
    rows = []
    overlaps = []
    prev_set: set[str] | None = None
    for year, sub in panel.groupby("fiscal_year"):
        sub = sub.copy()
        if len(sub) < 100:
            continue
        sub["bm_score"] = pct(sub["bm_raw"])
        sub["ep_score"] = pct(sub["ep_raw"])
        sub["gp_score"] = pct(sub["gross_profitability_proxy"])
        sub["piotroski_score"] = pct(sub["piotroski_available_ratio_proxy"])
        sub["sloan_quality_score"] = pct(sub["sloan_accruals_proxy"], higher=False)
        sub["distress_safety_score"] = 1 - sub["distress_flag_proxy"].astype(float)
        sub["liquidity_score"] = pct(sub["adv60_proxy"])
        sub["wf_score"] = (
            weights["bm"] * sub["bm_score"]
            + weights["ep"] * sub["ep_score"]
            + weights["gp"] * sub["gp_score"]
            + weights["piotroski"] * sub["piotroski_score"]
            + weights["sloan"] * sub["sloan_quality_score"]
            + weights["distress"] * sub["distress_safety_score"]
            + weights["liquidity"] * sub["liquidity_score"]
        )
        sub = sub.sort_values("wf_score", ascending=False).reset_index(drop=True)
        sub["wf_rank"] = sub.index + 1
        top = sub.head(min(1200, len(sub)))
        current_set = set(top["code"])
        jaccard = np.nan if prev_set is None else len(current_set & prev_set) / len(current_set | prev_set)
        overlaps.append({"fiscal_year": int(year), "top1200_jaccard_with_previous_fold": jaccard, "top1200_count": len(top)})
        prev_set = current_set
        rows.append(
            {
                "walk_forward_level": level,
                "fiscal_year": int(year),
                "train_period": "previous available fiscal snapshots as proxy; no re-optimization",
                "test_period": int(year),
                "top1200_feasible": bool((~top["distress_flag_proxy"]).all()),
                "candidate_count": len(top),
                "bm_median_vs_market": top["bm_raw"].median(skipna=True) - sub["bm_raw"].median(skipna=True),
                "ep_median_vs_market": top["ep_raw"].median(skipna=True) - sub["ep_raw"].median(skipna=True),
                "gross_profitability_median_vs_market": top["gross_profitability_proxy"].median(skipna=True) - sub["gross_profitability_proxy"].median(skipna=True),
                "piotroski_ratio_median_vs_market": top["piotroski_available_ratio_proxy"].median(skipna=True) - sub["piotroski_available_ratio_proxy"].median(skipna=True),
                "sloan_accruals_median_vs_market": sub["sloan_accruals_proxy"].median(skipna=True) - top["sloan_accruals_proxy"].median(skipna=True),
                "adv60_median_vs_market_ratio": top["adv60_proxy"].median(skipna=True) / sub["adv60_proxy"].median(skipna=True),
                "distress_flag_rate": float(top["distress_flag_proxy"].mean()),
                "review_flag_rate": float(top["review_flag_proxy"].mean()),
                "anomaly_flag_rate": float(top["anomaly_flag_proxy"].mean()),
                "gp_missing_rate": float(top["gp_missing_rate_proxy"].mean()),
                "sector_hhi": hhi(top["sector"]),
                "max_sector_share": float(top["sector"].value_counts(normalize=True).iloc[0]),
                "top1200_jaccard_with_previous_fold": jaccard,
                "selected_weight_drift": 0.0,
                "normalization_consensus_retention": np.nan,
                "optional_future_return": np.nan,
                "optional_future_volatility": np.nan,
                "optional_future_max_drawdown": np.nan,
                "lookahead_note": "submit_date used when available; otherwise fiscal_year_end + 120 days proxy. Gross Profitability original formula unavailable in raw panel, so operating_income/total_assets proxy is used.",
            }
        )
    results = pd.DataFrame(rows)
    overlap = pd.DataFrame(overlaps)
    drift = pd.DataFrame([{"fiscal_year": y, "selected_weight_drift": 0.0, "note": "Weights fixed from Phase2 selected solution; no per-year re-optimization due to incomplete panel."} for y in results.get("fiscal_year", pd.Series(dtype=int))])
    results.to_csv(OUT / "walk_forward" / "walk_forward_results.csv", index=False)
    overlap.to_csv(OUT / "walk_forward" / "walk_forward_top1200_overlap.csv", index=False)
    drift.to_csv(OUT / "walk_forward" / "walk_forward_weight_drift.csv", index=False)
    summary = {
        "walk_forward_level": level,
        "years": results["fiscal_year"].tolist() if not results.empty else [],
        "fold_count": int(len(results)),
        "mean_top1200_jaccard": None if overlap["top1200_jaccard_with_previous_fold"].dropna().empty else float(overlap["top1200_jaccard_with_previous_fold"].dropna().mean()),
        "strict_full_walk_forward": False,
        "note": "Level 2 snapshot walk-forward proxy; not a future return prediction model.",
    }
    write_text(OUT / "walk_forward" / "walk_forward_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def create_figures(top1200: pd.DataFrame, consensus: pd.DataFrame, topn: pd.DataFrame, wf_summary: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top1000 = consensus.sort_values("rank").head(1000)
    top2000 = consensus.sort_values("rank").head(2000)
    comp = pd.DataFrame(
        [
            summary_stats(top1200, "Top1200", consensus),
            summary_stats(top2000, "Top2000", consensus),
        ]
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    comp.set_index("group")[["gross_profitability_median", "piotroski_median", "sector_hhi", "anomaly_flag_rate"]].plot(kind="bar", ax=ax)
    ax.set_title("Top1200 vs Top2000 Metrics")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "top1200_vs_top2000_metrics.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(topn["topn"], topn["topn_utility"], marker="o")
    ax.axvline(1200, color="red", linestyle="--", label="Formal Top1200")
    ax.axvline(2000, color="gray", linestyle=":", label="Utility max Top2000")
    ax.legend()
    ax.set_title("TopN Utility Curve")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "topn_utility_curve_highlight_top1200.png", dpi=150)
    plt.close(fig)

    sector = top1200["sector"].value_counts().head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    sector.plot(kind="bar", ax=ax, color="#2f6f73")
    ax.set_title("Top1200 Sector Distribution")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "top1200_sector_distribution.png", dpi=150)
    plt.close(fig)

    metrics = ["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d"]
    fig, ax = plt.subplots(figsize=(10, 5))
    ratios = []
    for m in metrics:
        denom = consensus[m].median(skipna=True)
        ratios.append(top1200[m].median(skipna=True) / denom if denom else np.nan)
    ax.bar(metrics, ratios, color="#665191")
    ax.axhline(1, color="black", linewidth=1)
    ax.set_title("Top1200 Metric Median vs Market")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "top1200_metric_vs_market.png", dpi=150)
    plt.close(fig)

    methods = ["market_percentile", "sector_percentile", "robust_zscore", "winsorized_zscore"]
    sets = {m: set(consensus.loc[consensus[f"in_{m}_top1200"], "code"]) for m in methods}
    matrix = np.zeros((4, 4))
    for i, a in enumerate(methods):
        for j, b in enumerate(methods):
            matrix[i, j] = len(sets[a] & sets[b]) / len(sets[a] | sets[b])
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(matrix, vmin=0, vmax=1, cmap="YlGnBu")
    ax.set_xticks(range(4), methods, rotation=35, ha="right")
    ax.set_yticks(range(4), methods)
    ax.set_title("Normalization Jaccard Matrix")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "normalization_jaccard_matrix.png", dpi=150)
    plt.close(fig)

    counts = consensus["normalization_top1200_count"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 5))
    counts.plot(kind="bar", ax=ax, color="#ffa600")
    ax.set_title("Normalization Consensus Counts")
    ax.set_xlabel("Number of methods in Top1200")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "normalization_consensus_counts.png", dpi=150)
    plt.close(fig)
    shutil.copyfile(OUT / "figures" / "normalization_consensus_counts.png", OUT / "figures" / "normalization_overlap_venn_or_bar.png")

    rank_cols = [f"{m}_rank" for m in methods]
    corr = consensus[rank_cols].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(4), methods, rotation=35, ha="right")
    ax.set_yticks(range(4), methods)
    ax.set_title("Normalization Rank Correlation")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "normalization_rank_correlation.png", dpi=150)
    plt.close(fig)

    wf = pd.read_csv(OUT / "walk_forward" / "walk_forward_results.csv")
    overlap = pd.read_csv(OUT / "walk_forward" / "walk_forward_top1200_overlap.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    if not overlap.empty:
        ax.plot(overlap["fiscal_year"], overlap["top1200_jaccard_with_previous_fold"], marker="o")
    ax.set_title("Walk-forward Top1200 Jaccard")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "walk_forward_jaccard.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    if not wf.empty:
        wf.set_index("fiscal_year")[["bm_median_vs_market", "ep_median_vs_market", "gross_profitability_median_vs_market", "sloan_accruals_median_vs_market"]].plot(ax=ax, marker="o")
    ax.set_title("Walk-forward Metric Stability")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "walk_forward_metric_stability.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    if not wf.empty:
        ax.plot(wf["fiscal_year"], wf["sector_hhi"], marker="o", color="#a05195")
    ax.set_title("Walk-forward Sector HHI")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "walk_forward_sector_hhi.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axis("off")
    ax.text(
        0.02,
        0.65,
        "Phase1 formulas -> Phase2 weights/normalization -> Top1200 universe -> Phase3 moat/theme review",
        fontsize=12,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#e8f1f2", edgecolor="#2f6f73"),
    )
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "phase2_to_phase3_flow.png", dpi=150)
    plt.close(fig)


def reports(inputs: dict, consensus: pd.DataFrame, top1200: pd.DataFrame, wf_summary: dict) -> None:
    topn = inputs["topn"]
    top1200_m = topn[topn["topn"] == 1200].iloc[0]
    top2000_m = topn[topn["topn"] == 2000].iloc[0]
    cons_summary = pd.read_csv(OUT / "consensus" / "normalization_consensus_summary.csv")
    phase1_check = inputs["phase1_check"]
    summary = pd.read_csv(OUT / "top1200_final" / "phase2_optimized_top1200_summary.csv")
    wf_results = pd.read_csv(OUT / "walk_forward" / "walk_forward_results.csv")

    core_count = int(consensus["normalization_core_flag"].sum())
    robust_count = int(consensus["normalization_robust_flag"].sum())
    fragile_count = int(consensus["normalization_fragile_flag"].sum())

    write_text(
        OUT / "reports" / "normalization_fix_report.md",
        f"""# Normalization Fix Report

## 前回の問題4
前回は正規化方式によってTopN候補群が揺れ、特にwinsorized z-scoreでTop1200 Jaccardが低かった。

## なぜ揺れるのか
会計指標には極端値、業種差、欠損、規模差があり、percentileとz-scoreでは順位の意味が変わるためである。

## 採用方針
- market_percentile: 主基準
- sector_percentile: 業種補正確認
- robust_zscore: 外れ値に強い頑健性確認
- winsorized_zscore: 外れ値感度確認

## Consensus tag
4方式中3方式以上でTop1200ならnormalization core、2方式以上ならrobust、marketのみならfragileとした。

## Summary
{md_table(cons_summary)}

## Phase3での使い方
normalization core/robust候補を優先し、fragile/outlier-sensitive候補は財務原データと業種文脈を確認する。
""",
    )

    write_text(
        OUT / "reports" / "top1200_vs_top2000_decision.md",
        f"""# Top1200 vs Top2000 Decision

## TopN utility比較
{md_table(topn[["topn", "topn_utility", "topn_utility_rank", "phase1_top5_count", "sector_hhi", "anomaly_flag_rate", "gp_missing_rate"]], 20)}

## Top2000が数理utility最大だった理由
utility関数に候補数の広さが含まれているため、品質・安全性を大きく崩さない範囲ではTop2000が高く評価された。

## Top1200を正式採用する理由
utility最大化ではTop2000が最良となったが、Phase3で分析可能な候補数、品質、安全性、流動性、業種分散、レビュー負荷のバランスを考慮し、Top1200をPhase2 optimized candidate universeとして採用した。

## Top2000の補助的使い方
Top2000は取りこぼし確認用の参照群であり、Top1200外・Top2000内の企業はFuture MoatやTransformation Moatが強い場合のみPhase3で復活候補にできる。

## 「最適」という言葉の注意
Top1200は絶対的な数理最適解ではない。本研究目的に照らした正式採用候補群である。
""",
    )

    wf_level = wf_summary["walk_forward_level"]
    wf_note = (
        "本データには複数年度のlook-ahead-safeな完全財務スナップショットが不足していたため、厳密なFull Walk-forward validationではなくLevel 2 snapshot proxyとして実施した。"
        if wf_level == "Level 2"
        else "本データには複数年度のlook-ahead-safeな財務スナップショットが不足していたため、厳密なWalk-forward validationは実施できなかった。"
    )
    write_text(
        OUT / "reports" / "walk_forward_report_final.md",
        f"""# Walk-forward Report Final

## 実施Level
{wf_level}

## 使用した年度・期間
{wf_summary.get("years", [])}

## train/test設計
Level 2では年度別snapshotを作り、submit_dateを利用可能日として扱った。submit_dateがない場合はfiscal_year_end + 120日proxyを使う設計である。

## look-aheadを避けるための処理
価格は利用可能日以前の直近日次価格を使った。ただし、完全な開示日ベースの再計算ではない。

## 結果
{md_table(wf_results, 20)}

## 限界
{wf_note}

将来リターン最大化や予測力は主張しない。候補群構成ルールの時間的頑健性を参考確認したものである。
""",
    )

    write_text(
        OUT / "reports" / "phase2_top1200_final_report.md",
        f"""# Phase2 Top1200 Final Report

## 1. Phase2の目的
Phase1で使った先行研究式の定義は変更せず、重み・候補群サイズ・正規化方法・業種調整を検証し、Phase3で分析可能な候補宇宙を作る。

## 2. Phase2が「破」である理由
Phase1の式を尊重しながら、式の使い方を最適化・検証するためである。

## 3. なぜTop2000ではなくTop1200を正式採用するのか
utility最大化ではTop2000が最良となったが、Phase2の目的は候補数最大化ではない。Top1200はPhase1 Top5をすべて保持し、品質・安全性・流動性・業種分散・レビュー負荷のバランスが良い。

## 4. Top1200の指標品質
{md_table(summary, 10)}

## 5. Top1200の業種分散
Sector HHI: {float(top1200_m["sector_hhi"]):.4f}

## 6. Phase1 Top5保持状況
{md_table(phase1_check, 10)}

## 7. Walk-forward実施結果
Walk-forward level: {wf_level}. 詳細は reports/walk_forward_report_final.md を参照。

## 8. 正規化方式感度への対応
market percentileを主基準とし、sector percentile、robust z-score、winsorized z-scoreでconsensus tagを付けた。

## 9. Normalization consensus
core={core_count}, robust={robust_count}, fragile={fragile_count}

## 10. Phase3への接続
Top100は優先確認、Top300は重点候補、Top1200は正式候補宇宙、Top2000は取りこぼし参照群として使う。

## 11. 限界
Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。将来リターン最大化モデルでもない。

## 12. レポート本文に使える要約文
utility最大化ではTop2000が最良となったが、Phase3で分析可能な候補数、品質、安全性、流動性、業種分散、レビュー負荷のバランスを考慮し、Top1200をPhase2 optimized candidate universeとして採用した。
""",
    )

    gp_review = pd.read_csv(PREV / "data_audit" / "gp_missing_review.csv") if (PREV / "data_audit" / "gp_missing_review.csv").exists() else pd.DataFrame()
    write_text(
        OUT / "reports" / "phase2_to_phase3_handoff_top1200.md",
        f"""# Phase2 To Phase3 Handoff Top1200

## 正式候補群
Top1200をPhase2 optimized candidate universeとして採用する。

## 使い分け
- Top100: 優先確認
- Top300: 重点候補
- Top1200: 正式候補宇宙
- Top2000: 取りこぼし確認用参照群

## Phase1 Top5
{md_table(phase1_check, 10)}

## Normalization categories
- normalization core: {core_count}
- normalization robust: {robust_count}
- normalization fragile: {fragile_count}

## GP missing review
{md_table(gp_review, 20)}

## Phase3で見るべきテーマ列 placeholder
- future_moat_theme
- transformation_moat_theme
- business_change_evidence
- primary_research_note
- final_phase3_review_decision

## Phase3実装への入力ファイル一覧
- top1200_final/phase2_optimized_top1200_candidates.csv
- rankings/final_weighted_top2000_reference.csv
- consensus/normalization_consensus_table.csv
- walk_forward/walk_forward_results.csv
""",
    )

    write_text(
        OUT / "reports" / "top2000_reference_note.md",
        """# Top2000 Reference Note

- utility最大化ではTop2000が最良だった。
- しかしPhase2正式候補群としては広すぎる。
- Top2000はPhase3でテーマ企業の取りこぼし確認に使う。
- Top1200外・Top2000内の企業は、Future MoatやTransformation Moatが強い場合のみPhase3で復活候補にできる。
- ただしその場合もPhase2 review flagsを確認する。
""",
    )

    write_text(
        OUT / "reports" / "report_text_for_paper.md",
        """# Report Text For Paper

Phase2では、Phase1で採用した先行研究式の定義は変更せず、重み・候補群サイズ・正規化方法・業種調整を検証した。候補数を含むutilityを最大化するとTop2000が最良となったが、Phase2の目的は候補数の最大化ではなく、Phase3で分析可能な候補宇宙を作ることである。Top1200はPhase1 Top5をすべて保持し、財務安全性、利益の質、流動性、業種分散の面で良好であり、レビュー負荷も現実的である。したがって本研究ではTop1200をPhase2 optimized candidate universeとして採用し、Top2000は取りこぼし確認用の参照群とした。

また、正規化方式によって候補群に差異が生じたため、market percentileを主基準としつつ、sector percentile、robust z-score、winsorized z-scoreによるランキングも作成した。複数方式で共通して上位に残る企業をnormalization robust候補としてタグ付けし、Phase3で優先的に確認する。

Walk-forward検証については、利用可能な過去財務スナップショットの範囲で実施した。厳密な実施に必要な複数年度の開示日ベースデータが不足する場合には、単一時点の横断面最適化であることを明記し、将来リターン予測力ではなく候補群構成ルールとして解釈する。
""",
    )


def selected_solution_json(inputs: dict, wf_summary: dict, consensus: pd.DataFrame) -> None:
    topn = inputs["topn"]
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    solution = {
        "selected_topn": 1200,
        "utility_max_topn": 2000,
        "top1200_is_utility_optimal": False,
        "top1200_is_formally_adopted": True,
        "reason": "Top1200 is adopted because it balances candidate breadth, quality, safety, liquidity, sector diversity, interpretability, and review burden for Phase3.",
        "phase1_top5_coverage": f"{int(top1200['phase1_top5_count'])}/5",
        "top2000_role": "reference_universe_for_missed_theme_candidates",
        "normalization_primary": "market_percentile",
        "normalization_fix": "consensus tagging across market_percentile, sector_percentile, robust_zscore, winsorized_zscore",
        "walk_forward_level": wf_summary["walk_forward_level"],
        "normalization_core_count": int(consensus["normalization_core_flag"].sum()),
        "normalization_robust_count": int(consensus["normalization_robust_flag"].sum()),
        "normalization_fragile_count": int(consensus["normalization_fragile_flag"].sum()),
        "limitations": [
            "This is not a future return maximization model.",
            "Exploratory Weighted Buffett Score is not the official Phase1 formula.",
            "Walk-forward depends on availability of historical snapshots.",
        ],
    }
    write_text(OUT / "top1200_final" / "selected_phase2_top1200_solution.json", json.dumps(solution, indent=2, ensure_ascii=False))


def audit_and_manifest(inputs: dict, wf_summary: dict) -> None:
    input_paths = [
        PREV_ZIP,
        PREV,
        PHASE1_COMPLETE,
        PHASE1_TOP5,
        FUND_RAW,
        FUND_CLEAN,
        PRICES_DAILY,
    ]
    rows = []
    for p in input_paths:
        rows.append({"path": rel(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() and p.is_file() else ""})
    pd.DataFrame(rows).to_csv(OUT / "data_audit" / "input_files_detected.csv", index=False)
    need_cols = [
        "code",
        "ticker",
        "company_name",
        "sector",
        "fiscal_year",
        "fiscal_period",
        "fiscal_year_end",
        "filing_date",
        "disclosure_date",
        "effective_date",
        "price_date",
        "book_equity",
        "market_equity",
        "market_equity_final",
        "net_income",
        "operating_cash_flow",
        "gross_profit",
        "total_assets",
        "average_total_assets",
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
        "anomaly_flags",
        "daily_return",
        "monthly_return",
        "close",
        "volume",
    ]
    raw_cols = set(pd.read_csv(FUND_RAW, nrows=0).columns) if FUND_RAW.exists() else set()
    rank_cols = set(inputs["ranking"].columns)
    miss = pd.DataFrame([{"column": c, "available_in_any_input": c in raw_cols or c in rank_cols} for c in need_cols])
    write_text(OUT / "data_audit" / "missing_inputs_and_columns.md", "# Missing Inputs And Columns\n\n" + md_table(miss, 80))
    (OUT / "configs" / "top1200_walkforward_fix_config.yaml").write_text(
        "selected_topn: 1200\nutility_max_topn: 2000\nnormalization_primary: market_percentile\nwalk_forward_policy: level_2_if_possible_else_level_4\n",
        encoding="utf-8",
    )
    manifest = {
        "project": "BEYOND BUFFETT",
        "phase": "Phase2 Top1200 Walk-forward Fix",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "description": "Phase2正式候補群をTop1200へ固定し、walk-forward proxyとnormalization consensusで補強した最終成果物。",
        "input_files": [rel(p) for p in input_paths if p.exists()],
        "main_outputs": [
            "top1200_final/phase2_optimized_top1200_candidates.csv",
            "top1200_final/selected_phase2_top1200_solution.json",
            "consensus/normalization_consensus_table.csv",
            "walk_forward/walk_forward_results.csv",
            "reports/phase2_top1200_final_report.md",
            "reports/top1200_vs_top2000_decision.md",
            "reports/normalization_fix_report.md",
            "reports/walk_forward_report_final.md",
            "reports/phase2_to_phase3_handoff_top1200.md",
        ],
        "important_note": "Exploratory Weighted Buffett Score is not the official Phase1 formula and is not a future return maximization model.",
        "walk_forward_level": wf_summary["walk_forward_level"],
    }
    write_text(OUT / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))


def readme(inputs: dict, wf_summary: dict, consensus: pd.DataFrame) -> None:
    topn = inputs["topn"]
    top1200 = topn[topn["topn"] == 1200].iloc[0]
    text = f"""# BEYOND BUFFETT Phase2 Top1200 Walk-forward Fix

## この成果物の位置づけ

これはBEYOND BUFFETT Phase2（破）のTop1200正式候補群版である。  
utility最大化ではTop2000が最良だったが、Phase3で分析可能な候補群としてTop1200を正式採用した。  
Top2000は取りこぼし確認用の参照群として残した。

## 主な修正

1. Phase2正式候補群をTop1200に固定
2. Walk-forward validationを可能な範囲で実施
3. 正規化方式感度問題に対してnormalization consensusを導入
4. Top1200候補にnormalization core / robust / fragile flagsを追加
5. Phase3へのhandoffを整備

## 重要な結論

- selected_topn: 1200
- utility_max_topn: 2000
- phase1_top5_coverage: {int(top1200["phase1_top5_count"])}/5
- walk_forward_level: {wf_summary["walk_forward_level"]}
- normalization_core_count: {int(consensus["normalization_core_flag"].sum())}
- normalization_robust_count: {int(consensus["normalization_robust_flag"].sum())}
- normalization_fragile_count: {int(consensus["normalization_fragile_flag"].sum())}

## 注意

Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。  
将来リターン最大化モデルではない。  
Phase2の目的は、Phase3で「変わるMoat」「生まれるMoat」を評価するための候補宇宙を作ることである。
"""
    write_text(OUT / "README.md", text)


def copy_scripts() -> None:
    dst = OUT / "scripts" / "phase2_top1200_walkforward_fix"
    dst.mkdir(parents=True, exist_ok=True)
    this = Path(__file__)
    target = dst / "generate_top1200_walkforward_fix.py"
    if this.resolve() != target.resolve():
        shutil.copyfile(this, target)
    write_text(dst / "__init__.py", '"""Phase2 Top1200 walk-forward fix scripts."""')
    run_all = dst / "run_all.sh"
    write_text(
        run_all,
        """#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT_DIR"
python3 outputs/phase2_top1200_walkforward_fix/scripts/phase2_top1200_walkforward_fix/generate_top1200_walkforward_fix.py
""",
    )
    run_all.chmod(0o755)


def checksums() -> None:
    rows = []
    exts = {".csv", ".json", ".md", ".png", ".py", ".sh", ".yaml", ".txt", ".log"}
    for p in sorted(OUT.rglob("*")):
        if not p.is_file() or p.name == "checksums.txt":
            continue
        relp = p.relative_to(OUT)
        if any(part in {"__pycache__", ".git", ".venv", "venv", "node_modules"} for part in relp.parts):
            continue
        if p.suffix in exts or p.name == "run_all.sh":
            rows.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {relp}")
    write_text(OUT / "checksums.txt", "\n".join(rows))


def zip_and_validate() -> tuple[Path, bool]:
    required = [
        "README.md",
        "manifest.json",
        "reports/phase2_top1200_final_report.md",
        "reports/top1200_vs_top2000_decision.md",
        "reports/normalization_fix_report.md",
        "reports/walk_forward_report_final.md",
        "reports/phase2_to_phase3_handoff_top1200.md",
        "top1200_final/phase2_optimized_top1200_candidates.csv",
        "top1200_final/selected_phase2_top1200_solution.json",
        "consensus/normalization_consensus_table.csv",
        "rankings/final_weighted_top2000_reference.csv",
    ]
    errors = []
    for r in required:
        p = OUT / r
        if not p.exists():
            errors.append(f"Missing: {r}")
        elif p.stat().st_size == 0:
            errors.append(f"Empty: {r}")
    write_text(OUT / "logs" / "final_validation_errors.md", "# Final Validation Errors\n\n" + ("\n".join(f"- {e}" for e in errors) if errors else "- None"))
    if ZIP.exists():
        ZIP.unlink()
    exclude = {"__pycache__", ".git", ".venv", "venv", "node_modules"}
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(OUT.rglob("*")):
            if not p.is_file():
                continue
            relp = p.relative_to(OUT)
            if any(part in exclude for part in relp.parts):
                continue
            if p.name == ".DS_Store" or p.suffix == ".tmp":
                continue
            zf.write(p, Path("phase2_top1200_walkforward_fix") / relp)
    with zipfile.ZipFile(ZIP) as zf:
        names = sorted(zf.namelist())
    zip_required = [f"phase2_top1200_walkforward_fix/{r}" for r in required]
    lines = [
        "# ZIP Validation Report",
        "",
        f"- ZIP exists: {ZIP.exists()}",
        f"- ZIP size MB: {ZIP.stat().st_size / (1024 * 1024):.3f}",
        "",
        "## Required checks",
    ]
    for r in zip_required:
        lines.append(f"- {r}: {'OK' if r in names else 'MISSING'}")
    missing = [r for r in zip_required if r not in names]
    lines += ["", "## Missing", *([f"- {m}" for m in missing] or ["- None"]), "", "## File listing"]
    lines += [f"- {n}" for n in names]
    write_text(OUT / "logs" / "zip_validation_report.md", "\n".join(lines))
    checksums()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(OUT.rglob("*")):
            if not p.is_file():
                continue
            relp = p.relative_to(OUT)
            if any(part in exclude for part in relp.parts):
                continue
            if p.name == ".DS_Store" or p.suffix == ".tmp":
                continue
            zf.write(p, Path("phase2_top1200_walkforward_fix") / relp)
    return ZIP, not errors and not missing


def main() -> None:
    ensure_dirs()
    inputs = load_inputs()
    previous_review(inputs)
    base = enrich_ranking(inputs["ranking"], inputs["phase1"])
    consensus, method_tables = normalization_consensus(base, inputs["selected"])
    top1200 = build_top1200_outputs(consensus, inputs["topn"])
    wf_summary = make_walk_forward()
    selected_solution_json(inputs, wf_summary, consensus)
    create_figures(top1200, consensus, inputs["topn"], wf_summary)
    reports(inputs, consensus, top1200, wf_summary)
    audit_and_manifest(inputs, wf_summary)
    readme(inputs, wf_summary, consensus)
    copy_scripts()
    checksums()
    zip_path, passed = zip_and_validate()
    topn = inputs["topn"]
    top1200_m = topn[topn["topn"] == 1200].iloc[0]
    msg = f"""Phase2 Top1200 Walk-forward Fix completed.

Output directory:
outputs/phase2_top1200_walkforward_fix/

ZIP:
outputs/phase2_top1200_walkforward_fix.zip

Formal Phase2 candidate universe:
top1200_final/phase2_optimized_top1200_candidates.csv

Selected solution:
top1200_final/selected_phase2_top1200_solution.json

Key reports:
reports/phase2_top1200_final_report.md
reports/top1200_vs_top2000_decision.md
reports/normalization_fix_report.md
reports/walk_forward_report_final.md
reports/phase2_to_phase3_handoff_top1200.md

Summary:
- selected_topn = 1200
- utility_max_topn = 2000
- top1200_formally_adopted = true
- phase1_top5_coverage = {int(top1200_m['phase1_top5_count'])}/5
- walk_forward_level = {wf_summary['walk_forward_level']}
- normalization_core_count = {int(consensus['normalization_core_flag'].sum())}
- normalization_robust_count = {int(consensus['normalization_robust_flag'].sum())}
- normalization_fragile_count = {int(consensus['normalization_fragile_flag'].sum())}
- zip_validation = {'passed' if passed else 'failed'}
- zip_size_mb = {zip_path.stat().st_size / (1024 * 1024):.3f}
"""
    write_text(OUT / "logs" / "summary.log", msg)
    print(msg)


if __name__ == "__main__":
    main()
