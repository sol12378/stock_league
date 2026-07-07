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


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "phase2_final_integrated_break"
ZIP_OUT = ROOT / "outputs" / "phase2_final_integrated_break.zip"

PHASE2_WF = ROOT / "outputs" / "phase2_top1200_walkforward_fix"
PHASE2_PERFECT = ROOT / "outputs" / "phase2_top1200_walkforward_perfect_fix"
PHASE2_REAL = ROOT / "outputs" / "phase2_real_optimization"
PHASE2_WEIGHT = ROOT / "outputs" / "phase2_weight_optimization"
PHASE1_TOP5 = ROOT / "outputs" / "phase1_top5" / "phase1_buffett_core_top5.csv"
FUND_CLEAN = ROOT / "data" / "processed" / "fundamentals_clean.csv"

FORMAL_CANDIDATES = PHASE2_WF / "top1200_final" / "phase2_optimized_top1200_candidates.csv"
CONSENSUS = PHASE2_WF / "consensus" / "normalization_consensus_table.csv"
TOP2000 = PHASE2_WF / "rankings" / "final_weighted_top2000_reference.csv"
PANEL = PHASE2_PERFECT / "data_panel" / "walk_forward_feature_panel.csv"
WF_COMPLETENESS = PHASE2_PERFECT / "validation" / "walk_forward_completeness_audit.csv"
REAL_ALL = PHASE2_REAL / "rankings" / "final_weighted_ranking_all.csv"
TOPN_METRICS = PHASE2_REAL / "topn_selection" / "topn_metrics.csv"
SELECTED_SOLUTION = PHASE2_REAL / "optimization" / "selected_phase2_solution.json"

DIRS = [
    "data_audit",
    "configs",
    "formal_top1200",
    "top2000_reference",
    "normalization",
    "point_in_time_panel",
    "walk_forward",
    "optimization",
    "rankings",
    "validation",
    "ablation",
    "figures",
    "reports",
    "scripts/phase2_final_integrated_break",
    "logs",
]

FINANCIAL_PATTERNS = [
    "bank",
    "insurance",
    "securities",
    "commodities futures",
    "financing",
    "other financing",
]
POSITIVE_WEIGHT_DEFAULT = {
    "bm": 0.18,
    "ep": 0.18,
    "gp": 0.18,
    "piotroski": 0.16,
    "sloan": 0.12,
    "distress": 0.10,
    "liquidity": 0.08,
}
REQUIRED_FILES = [
    "formal_top1200/phase2_formal_top1200_candidates.csv",
    "top2000_reference/final_weighted_top2000_reference.csv",
    "normalization/normalization_consensus_table.csv",
    "point_in_time_panel/annual_top1200_nonfinancial_by_year.csv",
    "point_in_time_panel/annual_top1200_strict_ready_by_year.csv",
    "walk_forward/fixed_weight_annual_validation.csv",
    "reports/phase2_final_integrated_report.md",
    "reports/phase2_to_phase3_handoff_final.md",
    "reports/report_text_for_paper.md",
    "reports/top1200_vs_top2000_final_decision.md",
    "data_audit/financial_exclusion_report.md",
    "data_audit/distress_exclusion_report.md",
    "data_audit/gross_profitability_definition_audit.md",
    "data_audit/flag_audit_report.md",
    "logs/dangerous_expression_audit.md",
    "manifest.json",
    "README.md",
]


def ensure_dirs() -> None:
    for rel in DIRS:
        (OUT / rel).mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def md_table(df: pd.DataFrame, n: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    x = df.head(n).fillna("")
    headers = [str(c) for c in x.columns]
    lines = ["| " + " | ".join(h.replace("|", "\\|") for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for _, row in x.iterrows():
        vals = [str(row[c]).replace("|", "\\|").replace("\n", " ") for c in x.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def is_financial_frame(df: pd.DataFrame) -> pd.Series:
    result = pd.Series(False, index=df.index)
    if "is_financial" in df:
        result |= bool_series(df["is_financial"])
    for col in ["sector", "sector_33", "sector_17"]:
        if col in df:
            text = df[col].fillna("").astype(str).str.lower()
            for pattern in FINANCIAL_PATTERNS:
                result |= text.str.contains(pattern, regex=False)
    return result.fillna(False)


def hhi(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    share = series.fillna("Unknown").value_counts(normalize=True)
    return float((share**2).sum())


def pct_rank(s: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    y = x.rank(pct=True, method="average")
    if not higher:
        y = 1 - y
    return y.fillna(0.5)


def load_selected_weights() -> dict[str, float]:
    if SELECTED_SOLUTION.exists():
        try:
            data = json.loads(SELECTED_SOLUTION.read_text(encoding="utf-8"))
            return data.get("selected_weights", POSITIVE_WEIGHT_DEFAULT)
        except Exception:
            return POSITIVE_WEIGHT_DEFAULT
    return POSITIVE_WEIGHT_DEFAULT


def load_inputs() -> dict[str, pd.DataFrame]:
    missing = []
    paths = {
        "formal_candidates": FORMAL_CANDIDATES,
        "consensus": CONSENSUS,
        "top2000": TOP2000,
        "panel": PANEL,
        "phase1_top5": PHASE1_TOP5,
        "fundamentals_clean": FUND_CLEAN,
        "topn_metrics": TOPN_METRICS,
        "wf_completeness": WF_COMPLETENESS,
    }
    for name, path in paths.items():
        if not path.exists():
            missing.append({"input": name, "path": rel(path), "status": "missing"})
    write_text(
        OUT / "data_audit" / "missing_inputs.md",
        "# Missing Inputs\n\n" + (md_table(pd.DataFrame(missing)) if missing else "No required priority inputs were missing."),
    )
    out: dict[str, pd.DataFrame] = {}
    out["formal"] = pd.read_csv(FORMAL_CANDIDATES, dtype={"code": str})
    out["consensus"] = pd.read_csv(CONSENSUS, dtype={"code": str})
    out["top2000"] = pd.read_csv(TOP2000, dtype={"code": str})
    out["panel"] = pd.read_csv(PANEL, dtype={"code": str, "ticker": str}, low_memory=False)
    out["phase1_top5"] = pd.read_csv(PHASE1_TOP5, dtype={"code": str}) if PHASE1_TOP5.exists() else pd.DataFrame(columns=["code"])
    out["fund_clean"] = pd.read_csv(FUND_CLEAN, dtype={"code": str}) if FUND_CLEAN.exists() else pd.DataFrame(columns=["code"])
    out["topn"] = pd.read_csv(TOPN_METRICS) if TOPN_METRICS.exists() else pd.DataFrame()
    out["wf_completeness"] = pd.read_csv(WF_COMPLETENESS) if WF_COMPLETENESS.exists() else pd.DataFrame()
    return out


def merge_metadata(df: pd.DataFrame, fund_clean: pd.DataFrame) -> pd.DataFrame:
    if fund_clean.empty:
        return df
    cols = [c for c in ["code", "company_name", "company_name_ja", "market", "sector_33", "sector_17", "is_financial", "equity"] if c in fund_clean.columns]
    meta = fund_clean[cols].drop_duplicates("code")
    return df.merge(meta, on="code", how="left", suffixes=("", "_meta"))


def financial_distress_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    financial = is_financial_frame(df)
    distress = pd.Series(False, index=df.index)
    for col in ["distress_exclusion_flag", "distress_flag_pti"]:
        if col in df:
            distress |= bool_series(df[col])
    negative_equity = pd.Series(False, index=df.index)
    for col in ["equity", "book_equity"]:
        if col in df:
            negative_equity |= pd.to_numeric(df[col], errors="coerce").lt(0).fillna(False)
    if "negative_equity" in df:
        negative_equity |= bool_series(df["negative_equity"])
    return financial, distress, negative_equity


def latest_panel_gp(panel: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "code",
        "availability_date",
        "gross_profit_source",
        "gross_profit",
        "cost_of_sales",
        "operating_profitability_proxy",
        "gross_profitability",
        "strict_fact_complete",
    ]
    use = panel[[c for c in cols if c in panel.columns]].copy()
    use["availability_date"] = pd.to_datetime(use["availability_date"], errors="coerce")
    return use.sort_values(["code", "availability_date"]).drop_duplicates("code", keep="last")


def add_gp_definition(df: pd.DataFrame, latest_gp: pd.DataFrame) -> pd.DataFrame:
    out = df.merge(latest_gp.add_prefix("panel_"), left_on="code", right_on="panel_code", how="left")
    source = out.get("panel_gross_profit_source", pd.Series(index=out.index, dtype=object)).fillna("")
    has_gp = pd.to_numeric(out.get("gross_profitability", pd.Series(index=out.index)), errors="coerce").notna()
    out["gross_profitability_source"] = np.select(
        [
            source.eq("direct_xbrl_gross_profit"),
            source.eq("derived_revenue_minus_cost_of_sales"),
            has_gp,
        ],
        [
            "direct_xbrl_gross_profit_panel_confirmed",
            "derived_revenue_minus_cost_of_sales_panel_confirmed",
            "phase2_snapshot_metric_source_unverified",
        ],
        default="unavailable",
    )
    out["gross_profitability_definition_status"] = np.select(
        [
            source.eq("direct_xbrl_gross_profit"),
            source.eq("derived_revenue_minus_cost_of_sales"),
            has_gp,
        ],
        [
            "original_gross_profit_over_total_assets",
            "gross_profit_over_total_assets_derived_from_revenue_minus_cost",
            "phase2_snapshot_metric_source_unverified",
        ],
        default="unavailable",
    )
    out["gross_profitability_proxy_flag"] = ~out["gross_profitability_definition_status"].eq("original_gross_profit_over_total_assets")
    out["gross_profitability_proxy_note"] = np.select(
        [
            source.eq("direct_xbrl_gross_profit"),
            source.eq("derived_revenue_minus_cost_of_sales"),
            has_gp,
        ],
        [
            "Gross Profit / Total Assets was confirmed from direct XBRL gross profit in the point-in-time panel.",
            "Gross profit was reconstructed as revenue minus cost of sales in the point-in-time panel.",
            "Phase2 snapshot contains a gross_profitability value, but direct historical XBRL source was not confirmed for this row.",
        ],
        default="Gross Profitability was unavailable and must be reviewed before Phase3 adoption.",
    )
    return out.drop(columns=[c for c in out.columns if c.startswith("panel_") and c != "panel_gross_profit_source"], errors="ignore")


def prepare_formal_top1200(inputs: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    consensus = inputs["consensus"].copy()
    phase1_codes = set(inputs["phase1_top5"]["code"].astype(str))
    consensus = merge_metadata(consensus, inputs["fund_clean"])
    consensus["code"] = consensus["code"].astype(str)
    if "rank" not in consensus:
        consensus["rank"] = np.arange(1, len(consensus) + 1)
    financial, distress, negative_equity = financial_distress_masks(consensus)
    consensus["financial_exclusion_flag"] = financial
    consensus["distress_hard_exclusion_flag"] = distress
    consensus["negative_equity_flag"] = negative_equity
    eligible = consensus[~financial & ~distress & ~negative_equity].copy()
    selected = eligible.sort_values("rank").head(1200).copy()
    missing_phase1 = sorted(code for code in phase1_codes if code not in set(selected["code"]) and code in set(eligible["code"]))
    if missing_phase1:
        force = eligible[eligible["code"].isin(missing_phase1)].copy()
        selected = pd.concat([selected, force], ignore_index=True).drop_duplicates("code", keep="last")
        selected = selected.sort_values(["rank"]).head(1200).copy()
        still_missing = sorted(code for code in missing_phase1 if code not in set(selected["code"]))
        if still_missing:
            replace = eligible[eligible["code"].isin(still_missing)].copy()
            base = selected[~selected["code"].isin(phase1_codes)].sort_values("rank").head(max(0, 1200 - len(replace)))
            selected = pd.concat([base, selected[selected["code"].isin(phase1_codes)], replace], ignore_index=True)
            selected = selected.drop_duplicates("code", keep="last").sort_values("rank").head(1200)
    selected = selected.sort_values("rank").reset_index(drop=True)
    selected["rank"] = np.arange(1, len(selected) + 1)
    selected["top100_flag"] = selected["rank"] <= 100
    selected["top300_flag"] = selected["rank"] <= 300
    selected["top1200_flag"] = True
    selected["top2000_reference_flag"] = selected["code"].isin(set(inputs["top2000"]["code"].astype(str)))
    selected["phase1_top5_flag"] = selected["code"].isin(phase1_codes)
    selected["anomaly_flags"] = selected.get("anomaly_flags", pd.Series(index=selected.index, dtype=object)).fillna("").replace("", "none")
    selected["anomaly_penalty"] = pd.to_numeric(selected.get("anomaly_penalty", 0), errors="coerce").fillna(0)
    selected.loc[selected["anomaly_penalty"].gt(0) & selected["anomaly_flags"].eq("none"), "anomaly_flags"] = "derived_anomaly_penalty_positive"
    selected["anomaly_flag_bool"] = ~selected["anomaly_flags"].eq("none") | selected["anomaly_penalty"].gt(0)
    for col in ["distress_review_flag", "gp_missing_review_flag", "normalization_fragile_flag", "outlier_sensitive_flag"]:
        if col not in selected:
            selected[col] = False
        selected[col] = bool_series(selected[col])
    selected["feature_missing_review_flag"] = bool_series(selected.get("gp_missing_review_flag", False))
    reasons = []
    for _, row in selected.iterrows():
        r = []
        if bool(row.get("distress_review_flag", False)):
            r.append("distress_review")
        if bool(row.get("gp_missing_review_flag", False)):
            r.append("gp_missing_or_proxy_review")
        if bool(row.get("normalization_fragile_flag", False)):
            r.append("normalization_fragile")
        if bool(row.get("outlier_sensitive_flag", False)):
            r.append("outlier_sensitive")
        if bool(row.get("anomaly_flag_bool", False)):
            r.append("anomaly_review")
        reasons.append(";".join(r) if r else "none")
    selected["phase2_review_reasons"] = reasons
    selected["phase2_review_required"] = ~selected["phase2_review_reasons"].eq("none")
    selected["phase3_review_reasons"] = np.where(
        selected["phase2_review_required"],
        selected["phase2_review_reasons"] + ";phase3_due_diligence",
        np.where(selected["rank"].le(300), "top300_priority_due_diligence", "standard_phase3_due_diligence"),
    )
    selected["phase3_review_required"] = selected["phase3_review_reasons"].ne("standard_phase3_due_diligence")
    selected["phase3_priority_flag"] = np.select(
        [
            selected["rank"].le(100) & bool_series(selected.get("normalization_core_flag", False)),
            selected["rank"].le(300) & bool_series(selected.get("normalization_robust_flag", False)),
            selected["phase2_review_required"],
        ],
        ["high", "medium_high", "review"],
        default="standard",
    )
    selected["phase3_handoff_note"] = np.select(
        [
            selected["phase3_priority_flag"].eq("high"),
            selected["phase3_priority_flag"].eq("medium_high"),
            selected["phase3_priority_flag"].eq("review"),
        ],
        [
            "Top100 and normalization core. Prioritize Phase3 moat review.",
            "Top300 and normalization robust. Review after high priority group.",
            "Requires Phase3 due diligence before adoption.",
        ],
        default="Formal Top1200 member for Phase3 candidate universe.",
    )
    selected = add_gp_definition(selected, latest_panel_gp(inputs["panel"]))
    required_cols = [
        "rank",
        "code",
        "ticker",
        "company_name",
        "sector",
        "final_exploratory_weighted_score",
        "bm_raw",
        "ep_raw",
        "gross_profitability",
        "gross_profitability_definition_status",
        "gross_profitability_source",
        "gross_profitability_proxy_flag",
        "gross_profitability_proxy_note",
        "piotroski_available_ratio",
        "sloan_accruals",
        "avg_daily_value_60d",
        "distress_exclusion_flag",
        "distress_review_flag",
        "anomaly_flags",
        "anomaly_flag_bool",
        "anomaly_penalty",
        "gp_missing_review_flag",
        "normalization_top1200_count",
        "normalization_core_flag",
        "normalization_robust_flag",
        "normalization_fragile_flag",
        "sector_adjusted_candidate_flag",
        "outlier_sensitive_flag",
        "phase2_review_required",
        "phase2_review_reasons",
        "phase3_review_required",
        "phase3_review_reasons",
        "phase1_top5_flag",
        "top100_flag",
        "top300_flag",
        "top1200_flag",
        "top2000_reference_flag",
        "phase3_priority_flag",
        "phase3_handoff_note",
    ]
    for col in required_cols:
        if col not in selected:
            selected[col] = np.nan
    selected[required_cols].to_csv(OUT / "formal_top1200" / "phase2_formal_top1200_candidates.csv", index=False)
    excluded = pd.DataFrame(
        [
            {"reason": "financial", "excluded_count": int(financial.sum())},
            {"reason": "distress_hard_exclude", "excluded_count": int(distress.sum())},
            {"reason": "negative_equity", "excluded_count": int(negative_equity.sum())},
        ]
    )
    financial_report = consensus.loc[financial, ["code", "ticker", "company_name", "sector", "market"] if "market" in consensus else ["code", "ticker", "company_name", "sector"]].copy()
    financial_report.to_csv(OUT / "data_audit" / "financial_exclusion_report.csv", index=False)
    distress_report = consensus.loc[distress | negative_equity, [c for c in ["code", "ticker", "company_name", "sector", "distress_exclusion_flag", "equity", "negative_equity_flag"] if c in consensus.columns]].copy()
    distress_report.to_csv(OUT / "data_audit" / "distress_exclusion_report.csv", index=False)
    write_text(
        OUT / "data_audit" / "financial_exclusion_report.md",
        "# Financial Exclusion Report\n\nFinancial companies were excluded from the formal Phase2 Top1200 and annual point-in-time Top1200 universes.\n\n"
        + md_table(excluded[excluded["reason"].eq("financial")])
        + f"\n\nFinancial rows detected in candidate universe: {int(financial.sum())}\n",
    )
    write_text(
        OUT / "data_audit" / "distress_exclusion_report.md",
        "# Distress Exclusion Report\n\nDistress hard excludes and negative equity rows were removed before formal and annual Top1200 selection.\n\n"
        + md_table(excluded[excluded["reason"].ne("financial")]),
    )
    stats = {
        "formal_count": len(selected),
        "phase1_top5_coverage": int(selected["phase1_top5_flag"].sum()),
        "financial_after_fix": int(is_financial_frame(selected).sum()),
        "distress_after_fix": int(bool_series(selected.get("distress_exclusion_flag", False)).sum()),
        "negative_equity_after_fix": int(pd.to_numeric(selected.get("equity", pd.Series(index=selected.index)), errors="coerce").lt(0).fillna(False).sum()),
    }
    return selected[required_cols], financial_report, distress_report, stats


def build_top2000_reference(inputs: dict[str, pd.DataFrame], formal: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    top2000 = inputs["top2000"].copy()
    top2000["code"] = top2000["code"].astype(str)
    top2000["anomaly_flags"] = top2000.get("anomaly_flags", pd.Series(index=top2000.index, dtype=object)).fillna("none").replace("", "none")
    top2000.to_csv(OUT / "top2000_reference" / "final_weighted_top2000_reference.csv", index=False)
    only = top2000[~top2000["code"].isin(set(formal["code"]))].copy()
    only.to_csv(OUT / "top2000_reference" / "top1200_out_top2000_reference_only.csv", index=False)
    return top2000, only


def build_normalization(inputs: dict[str, pd.DataFrame], formal: pd.DataFrame) -> pd.DataFrame:
    consensus = inputs["consensus"].copy()
    consensus["code"] = consensus["code"].astype(str)
    consensus.to_csv(OUT / "normalization" / "normalization_consensus_table.csv", index=False)
    summary = pd.DataFrame(
        [
            {"scope": "all_universe", "metric": "normalization_core_count", "value": int(bool_series(consensus["normalization_core_flag"]).sum())},
            {"scope": "all_universe", "metric": "normalization_robust_count", "value": int(bool_series(consensus["normalization_robust_flag"]).sum())},
            {"scope": "all_universe", "metric": "normalization_fragile_count", "value": int(bool_series(consensus["normalization_fragile_flag"]).sum())},
            {"scope": "all_universe", "metric": "sector_adjusted_candidate_count", "value": int(bool_series(consensus["sector_adjusted_candidate_flag"]).sum())},
        ]
    )
    summary.to_csv(OUT / "normalization" / "normalization_consensus_summary.csv", index=False)
    formal_codes = set(formal["code"])
    top = consensus[consensus["code"].isin(formal_codes)]
    summary_top = pd.DataFrame(
        [
            {"scope": "formal_top1200", "metric": "normalization_core_count", "value": int(bool_series(top["normalization_core_flag"]).sum())},
            {"scope": "formal_top1200", "metric": "normalization_robust_count", "value": int(bool_series(top["normalization_robust_flag"]).sum())},
            {"scope": "formal_top1200", "metric": "normalization_fragile_count", "value": int(bool_series(top["normalization_fragile_flag"]).sum())},
            {"scope": "formal_top1200", "metric": "sector_adjusted_candidate_count", "value": int(bool_series(top["sector_adjusted_candidate_flag"]).sum())},
        ]
    )
    summary_top.to_csv(OUT / "normalization" / "normalization_consensus_summary_top1200.csv", index=False)
    write_text(
        OUT / "reports" / "normalization_consensus_report.md",
        "# Normalization Consensus Report\n\n"
        "Market percentile, sector percentile, robust z-score, and winsorized z-score memberships were integrated from the Phase2 normalization consensus artifact.\n\n"
        "## All Universe\n\n"
        + md_table(summary)
        + "\n\n## Formal Top1200\n\n"
        + md_table(summary_top),
    )
    return consensus


def score_annual(sub: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    out = sub.copy()
    score_map = [
        ("bm_score", "book_to_market", True),
        ("ep_score", "earnings_to_price", True),
        ("gp_score", "gross_profitability", True),
        ("piotroski_score", "piotroski_f_score_ratio", True),
        ("sloan_quality_score", "sloan_accruals", False),
        ("liquidity_score", "decision_adv60", True),
    ]
    for out_col, source, higher in score_map:
        out[out_col] = pct_rank(out[source], higher) if source in out else 0.5
    out["distress_safety_score"] = 1 - bool_series(out.get("distress_flag_pti", False)).astype(float)
    out["fixed_weight_score"] = (
        weights.get("bm", 0) * out["bm_score"]
        + weights.get("ep", 0) * out["ep_score"]
        + weights.get("gp", 0) * out["gp_score"]
        + weights.get("piotroski", 0) * out["piotroski_score"]
        + weights.get("sloan", 0) * out["sloan_quality_score"]
        + weights.get("distress", 0) * out["distress_safety_score"]
        + weights.get("liquidity", 0) * out["liquidity_score"]
    )
    out = out.sort_values("fixed_weight_score", ascending=False).reset_index(drop=True)
    out["annual_rank"] = np.arange(1, len(out) + 1)
    return out


def annual_top1200(inputs: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = inputs["panel"].copy()
    panel["availability_date"] = pd.to_datetime(panel["availability_date"], errors="coerce")
    panel["availability_year"] = panel["availability_date"].dt.year
    panel["financial_exclusion_flag"] = is_financial_frame(panel)
    _, distress, negative_equity = financial_distress_masks(panel)
    panel["distress_hard_exclusion_flag"] = distress
    panel["negative_equity_flag"] = negative_equity
    panel["gross_profitability_definition_status"] = np.select(
        [
            panel["gross_profit_source"].eq("direct_xbrl_gross_profit"),
            panel["gross_profit_source"].eq("derived_revenue_minus_cost_of_sales"),
            panel["operating_profitability_proxy"].notna() & panel["gross_profitability"].isna(),
        ],
        [
            "original_gross_profit_over_total_assets",
            "gross_profit_over_total_assets_derived_from_revenue_minus_cost",
            "operating_profitability_proxy",
        ],
        default="unavailable",
    )
    panel["gross_profitability_source"] = panel["gross_profit_source"].fillna("unavailable")
    panel["gross_profitability_proxy_flag"] = ~panel["gross_profitability_definition_status"].eq("original_gross_profit_over_total_assets")
    panel["feature_missing_review_flag"] = ~bool_series(panel.get("strict_walk_forward_feature_complete", False))
    panel["point_in_time_review_reasons"] = np.where(panel["feature_missing_review_flag"], "feature_missing", "none")
    eligible = panel[~panel["financial_exclusion_flag"] & ~panel["distress_hard_exclusion_flag"] & ~panel["negative_equity_flag"]].copy()
    weights = load_selected_weights()
    nonfinancial_rows = []
    strict_rows = []
    review_rows = []
    summary_rows = []
    for year in sorted(y for y in eligible["availability_year"].dropna().unique() if 2023 <= int(y) <= 2025):
        sub = eligible[eligible["availability_year"].eq(year)].copy()
        ranked = score_annual(sub, weights)
        top = ranked.head(min(1200, len(ranked))).copy()
        top["top1200_variant"] = "nonfinancial_non_distress"
        nonfinancial_rows.append(top)
        strict_pool = sub[bool_series(sub.get("strict_walk_forward_ready", False))].copy()
        strict_ranked = score_annual(strict_pool, weights)
        strict_top = strict_ranked.head(min(1200, len(strict_ranked))).copy()
        strict_top["top1200_variant"] = "strict_ready"
        strict_rows.append(strict_top)
        review_rows.append(
            top[
                [
                    "availability_year",
                    "code",
                    "ticker",
                    "company_name",
                    "sector",
                    "annual_rank",
                    "feature_missing_review_flag",
                    "gross_profitability_definition_status",
                    "gross_profitability_proxy_flag",
                    "point_in_time_review_reasons",
                ]
            ].copy()
        )
        summary_rows.append(
            {
                "availability_year": int(year),
                "annual_top1200_count": len(top),
                "strict_ready_count": int(bool_series(top.get("strict_walk_forward_ready", False)).sum()),
                "strict_ready_rate": float(bool_series(top.get("strict_walk_forward_ready", False)).mean()) if len(top) else 0.0,
                "feature_missing_review_rate": float(top["feature_missing_review_flag"].mean()) if len(top) else 0.0,
                "gross_profitability_direct_rate": float(top["gross_profit_source"].eq("direct_xbrl_gross_profit").mean()) if len(top) else 0.0,
                "gross_profitability_proxy_rate": float(top["gross_profitability_proxy_flag"].mean()) if len(top) else 0.0,
                "distress_flag_count": int(bool_series(top.get("distress_flag_pti", False)).sum()) if len(top) else 0,
                "financial_count": int(is_financial_frame(top).sum()) if len(top) else 0,
                "sector_hhi": hhi(top["sector"]) if "sector" in top else 0.0,
                "max_sector_share": float(top["sector"].value_counts(normalize=True).iloc[0]) if len(top) and "sector" in top else 0.0,
                "phase1_top5_coverage": np.nan,
                "252d_forward_return_eligible_count": int(top["future_return_252d"].notna().sum()) if "future_return_252d" in top else 0,
                "optional_median_forward_return_252d": float(top["future_return_252d"].median(skipna=True)) if "future_return_252d" in top else np.nan,
                "optional_volatility_forward_return_252d": float(top["future_return_252d"].std(skipna=True)) if "future_return_252d" in top else np.nan,
                "optional_max_drawdown_proxy_252d": float(top["future_return_252d"].min(skipna=True)) if "future_return_252d" in top else np.nan,
                "strict_ready_pool_count": len(strict_pool),
                "strict_ready_top_count": len(strict_top),
            }
        )
    nonfinancial = pd.concat(nonfinancial_rows, ignore_index=True) if nonfinancial_rows else pd.DataFrame()
    strict = pd.concat(strict_rows, ignore_index=True) if strict_rows else pd.DataFrame()
    reviews = pd.concat(review_rows, ignore_index=True) if review_rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    nonfinancial.to_csv(OUT / "point_in_time_panel" / "annual_top1200_nonfinancial_by_year.csv", index=False)
    strict.to_csv(OUT / "point_in_time_panel" / "annual_top1200_strict_ready_by_year.csv", index=False)
    reviews.to_csv(OUT / "point_in_time_panel" / "annual_top1200_review_flags_by_year.csv", index=False)
    summary.to_csv(OUT / "point_in_time_panel" / "annual_top1200_summary_by_year.csv", index=False)
    panel.to_csv(OUT / "point_in_time_panel" / "point_in_time_feature_panel_with_filters.csv", index=False)
    return nonfinancial, strict, reviews, summary


def fixed_weight_validation(nonfinancial: pd.DataFrame, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    validation = summary.copy()
    validation.to_csv(OUT / "walk_forward" / "fixed_weight_annual_validation.csv", index=False)
    rows = []
    years = sorted(nonfinancial["availability_year"].dropna().unique()) if not nonfinancial.empty else []
    prev: set[str] | None = None
    for year in years:
        cur = set(nonfinancial[nonfinancial["availability_year"].eq(year)]["code"].astype(str))
        rows.append(
            {
                "availability_year": int(year),
                "top1200_count": len(cur),
                "jaccard_with_previous_year": np.nan if prev is None else len(cur & prev) / len(cur | prev),
            }
        )
        prev = cur
    overlap = pd.DataFrame(rows)
    overlap.to_csv(OUT / "walk_forward" / "fixed_weight_annual_top1200_overlap.csv", index=False)
    summary_json = {
        "fixed_weight_out_of_time_validation_completed": True,
        "years": [int(y) for y in years],
        "mean_strict_ready_rate": None if validation.empty else float(validation["strict_ready_rate"].mean()),
        "mean_feature_missing_review_rate": None if validation.empty else float(validation["feature_missing_review_rate"].mean()),
    }
    write_text(OUT / "walk_forward" / "fixed_weight_annual_summary.json", json.dumps(summary_json, indent=2, ensure_ascii=False))
    return validation, overlap


def true_walk_forward_status(inputs: dict[str, pd.DataFrame], fixed_validation: pd.DataFrame) -> bool:
    rows = []
    eligible = 0
    for _, row in fixed_validation.iterrows():
        ok = bool(row["strict_ready_count"] >= 1000 and row["252d_forward_return_eligible_count"] >= 960)
        eligible += int(ok)
        rows.append(
            {
                "test_availability_year": int(row["availability_year"]),
                "eligible_for_true_252d_walk_forward": ok,
                "strict_ready_count": int(row["strict_ready_count"]),
                "forward_252d_eligible_count": int(row["252d_forward_return_eligible_count"]),
                "reason": "eligible" if ok else "insufficient strict-ready rows or 252d target maturity",
            }
        )
    completed = eligible >= 2
    attempt = pd.DataFrame(rows)
    attempt.to_csv(OUT / "walk_forward" / "true_walk_forward_attempt.csv", index=False)
    status = {
        "strict_true_walk_forward_completed": completed,
        "eligible_fold_count": eligible,
        "minimum_required_eligible_folds": 2,
        "reason": "eligible folds >= 2" if completed else "Fewer than two folds have both sufficient strict-ready rows and mature 252d targets.",
        "note": "No forced train/test optimization is claimed when the panel cannot support it.",
    }
    write_text(OUT / "walk_forward" / "true_walk_forward_status.json", json.dumps(status, indent=2, ensure_ascii=False))
    write_text(
        OUT / "reports" / "true_walk_forward_status_report.md",
        "# True Walk-forward Optimization Status\n\n"
        "True walk-forward optimization requires at least two folds where train rows are sufficient and test-year 252 trading-day targets have matured.\n\n"
        + md_table(attempt)
        + "\n\n"
        + f"Completed: {completed}\n\n"
        + status["reason"],
    )
    return completed


def audits(formal: pd.DataFrame, annual: pd.DataFrame) -> None:
    gp = pd.DataFrame(
        [
            {"scope": "formal_top1200", "metric": "direct_original_rate", "value": float((~formal["gross_profitability_proxy_flag"]).mean())},
            {"scope": "formal_top1200", "metric": "proxy_or_unverified_rate", "value": float(formal["gross_profitability_proxy_flag"].mean())},
        ]
    )
    if not annual.empty:
        by_year = annual.groupby("availability_year").agg(
            direct_original_rate=("gross_profitability_proxy_flag", lambda x: float((~x).mean())),
            proxy_or_unverified_rate=("gross_profitability_proxy_flag", "mean"),
        ).reset_index()
        for _, r in by_year.iterrows():
            gp = pd.concat(
                [
                    gp,
                    pd.DataFrame(
                        [
                            {"scope": f"annual_{int(r['availability_year'])}", "metric": "direct_original_rate", "value": r["direct_original_rate"]},
                            {"scope": f"annual_{int(r['availability_year'])}", "metric": "proxy_or_unverified_rate", "value": r["proxy_or_unverified_rate"]},
                        ]
                    ),
                ],
                ignore_index=True,
            )
    gp.to_csv(OUT / "data_audit" / "gross_profitability_definition_audit.csv", index=False)
    write_text(
        OUT / "data_audit" / "gross_profitability_definition_audit.md",
        "# Gross Profitability Definition Audit\n\n"
        "Phase1 and the Phase2 formal candidate universe use Gross Profit / Total Assets where direct or reconstructable gross profit is available. "
        "Historical panel rows that cannot confirm direct gross profit are marked separately and must not be described as fully original GP/A validation.\n\n"
        + md_table(gp),
    )
    flag_summary = pd.DataFrame(
        [
            {"flag": "phase2_review_required", "count": int(bool_series(formal["phase2_review_required"]).sum())},
            {"flag": "phase3_review_required", "count": int(bool_series(formal["phase3_review_required"]).sum())},
            {"flag": "anomaly_flag_bool", "count": int(bool_series(formal["anomaly_flag_bool"]).sum())},
            {"flag": "gp_missing_review_flag", "count": int(bool_series(formal["gp_missing_review_flag"]).sum())},
            {"flag": "normalization_fragile_flag", "count": int(bool_series(formal["normalization_fragile_flag"]).sum())},
            {"flag": "outlier_sensitive_flag", "count": int(bool_series(formal["outlier_sensitive_flag"]).sum())},
        ]
    )
    flag_summary.to_csv(OUT / "data_audit" / "flag_audit_summary.csv", index=False)
    write_text(
        OUT / "data_audit" / "flag_audit_report.md",
        "# Flag Audit Report\n\nAnomaly, review, normalization fragility, and Phase3 due-diligence flags were consolidated into the formal Top1200 file.\n\n"
        + md_table(flag_summary),
    )


def create_figures(formal: pd.DataFrame, top2000: pd.DataFrame, normalization: pd.DataFrame, annual_summary: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axis("off")
    ax.text(
        0.02,
        0.6,
        "Phase1 formulas\n(B/M, E/P, GP/A, Piotroski, Sloan, Distress, Liquidity)\n→ Phase2 break\n(weights, normalization, TopN, missingness, point-in-time checks)\n→ Phase3 moat evaluation",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "phase2_flow_from_phase1_to_phase3.png", dpi=150)
    plt.close(fig)

    comp = pd.DataFrame(
        [
            {
                "group": "Top1200",
                "gp_median": formal["gross_profitability"].median(skipna=True),
                "piotroski_median": formal["piotroski_available_ratio"].median(skipna=True),
                "sector_hhi": hhi(formal["sector"]),
            },
            {
                "group": "Top2000",
                "gp_median": top2000["gross_profitability"].median(skipna=True),
                "piotroski_median": top2000["piotroski_available_ratio"].median(skipna=True),
                "sector_hhi": hhi(top2000["sector"]),
            },
        ]
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    comp.set_index("group").plot(kind="bar", ax=ax)
    ax.set_title("Top1200 vs Top2000 Metrics")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "top1200_vs_top2000_metrics.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    formal["sector"].value_counts().head(20).plot(kind="bar", ax=ax)
    ax.set_title("Formal Top1200 Sector Distribution")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "formal_top1200_sector_distribution.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    formal[["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio"]].median().plot(kind="bar", ax=ax)
    ax.set_title("Formal Top1200 Metric Medians")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "formal_top1200_metric_vs_market.png", dpi=150)
    plt.close(fig)

    method_cols = [c for c in normalization.columns if c.startswith("in_") and c.endswith("_top1200")]
    if method_cols:
        mat = pd.DataFrame(index=method_cols, columns=method_cols, dtype=float)
        for a in method_cols:
            sa = set(normalization[bool_series(normalization[a])]["code"].astype(str))
            for b in method_cols:
                sb = set(normalization[bool_series(normalization[b])]["code"].astype(str))
                mat.loc[a, b] = len(sa & sb) / len(sa | sb) if sa | sb else np.nan
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(mat.astype(float), vmin=0, vmax=1)
        ax.set_xticks(range(len(method_cols)), labels=[m.replace("in_", "").replace("_top1200", "") for m in method_cols], rotation=45, ha="right")
        ax.set_yticks(range(len(method_cols)), labels=[m.replace("in_", "").replace("_top1200", "") for m in method_cols])
        fig.colorbar(im, ax=ax)
        ax.set_title("Normalization Jaccard Matrix")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "normalization_jaccard_matrix.png", dpi=150)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    formal["normalization_top1200_count"].value_counts().sort_index().plot(kind="bar", ax=ax)
    ax.set_title("Normalization Consensus Counts in Formal Top1200")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "normalization_consensus_counts.png", dpi=150)
    plt.close(fig)

    if not annual_summary.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        annual_summary.set_index("availability_year")["strict_ready_rate"].plot(kind="bar", ax=ax)
        ax.set_ylim(0, 1)
        ax.set_title("Annual Top1200 Strict-ready Rate")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "annual_top1200_ready_rate.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5))
        annual_summary.set_index("availability_year")["sector_hhi"].plot(marker="o", ax=ax)
        ax.set_title("Annual Top1200 Sector HHI")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "annual_top1200_sector_hhi.png", dpi=150)
        plt.close(fig)

    cov_path = PHASE2_PERFECT / "data_audit" / "strict_panel_column_coverage.csv"
    if cov_path.exists():
        cov = pd.read_csv(cov_path)
        fig, ax = plt.subplots(figsize=(10, 5))
        cov.set_index("column")["coverage"].plot(kind="bar", ax=ax)
        ax.set_ylim(0, 1)
        ax.set_title("Point-in-time Panel Coverage")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "point_in_time_panel_coverage.png", dpi=150)
        plt.close(fig)


def write_reports(
    formal: pd.DataFrame,
    top2000: pd.DataFrame,
    top2000_only: pd.DataFrame,
    norm_summary_top: pd.DataFrame,
    annual_summary: pd.DataFrame,
    fixed_validation: pd.DataFrame,
    true_completed: bool,
    stats: dict[str, int],
) -> None:
    write_text(
        OUT / "reports" / "top1200_vs_top2000_final_decision.md",
        """
# Top1200 vs Top2000 Final Decision

utility最大化ではTop2000が最良であった。しかし、Phase2の目的は候補数の最大化ではなく、Phase3で分析可能な候補宇宙を作ることである。
したがって、Top2000は取りこぼし確認用の参照群とし、Top1200をPhase2正式候補群として採用した。

Top2000 reference-only rows are stored in `top2000_reference/top1200_out_top2000_reference_only.csv`.
""",
    )
    write_text(
        OUT / "reports" / "fixed_weight_out_of_time_validation_report.md",
        "# Fixed-weight Out-of-time Validation Report\n\n"
        "Phase2 selected weights were fixed and applied to annual point-in-time snapshots after financial and distress hard exclusions.\n\n"
        + md_table(fixed_validation),
    )
    write_text(
        OUT / "reports" / "phase2_to_phase3_handoff_final.md",
        """
# Phase2 To Phase3 Handoff Final

Phase2 formal candidate universe: `formal_top1200/phase2_formal_top1200_candidates.csv`.

Top100 are the first qualitative-review priority. Top300 are the second review block. Top1200 is the formal Phase3 candidate universe. Top2000 is a reference universe for omission checks only.

Phase1 Top5 retention is recorded in `phase1_top5_flag`; all five must remain unless a hard exclusion is documented.

Phase3 review rules:
- normalization core / robust candidates should be prioritized.
- normalization fragile and outlier-sensitive candidates require raw data review.
- GP proxy or unverified rows require Gross Profit / Total Assets confirmation.
- anomaly flags require evidence review; `none` does not prove anomalies are impossible.
- Top2000 reference-only candidates can be revived only with explicit Phase3 moat evidence and financial-data confirmation.

Phase3 placeholder columns to add:
- changing_moat_score placeholder
- emerging_moat_score placeholder
- ai_moat_placeholder
- capital_efficiency_change_placeholder
- shareholder_return_placeholder
- business_transformation_placeholder

Future Moat is introduced in Phase3, not Phase2.
""",
    )
    paper = """
# Report Text For Paper

Phase2では、Phase1で用いた先行研究式の定義は変更せず、式の適用方法を最適化した。具体的には、B/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、Distress、Liquidityを百分位順位などに正規化し、重み、欠損処理、業種調整、候補数を探索した。これは銘柄をAIに直接選ばせるものではなく、Phase3へ渡す候補宇宙を作るための条件比較である。

utility最大化ではTop2000が最良であったが、Phase2の目的は候補数最大化ではない。Phase3で実際に分析可能な広さ、品質、財務安全性、流動性、業種分散、レビュー負荷を考慮し、Top1200をPhase2 optimized candidate universeとして採用した。

また、正規化方式による揺れを確認するため、market percentile、sector percentile、robust z-score、winsorized z-scoreを比較し、複数方式で共通して上位に残る企業にnormalization core / robust flagを付与した。

さらに、EDINET提出日を基準にしたpoint-in-time panelを構築し、固定重みを年度別snapshotに適用することで、単一時点だけでなく時点外での候補群品質も確認した。ただし、十分なfoldを用いた完全なWalk-forward optimizationは今後の課題であり、本結果は将来リターン予測力を示すものではない。
"""
    write_text(OUT / "reports" / "report_text_for_paper.md", paper)
    report = f"""
# Phase2 Final Integrated Report

## 1. Phase2の目的

Phase2は、Phase1の先行研究式を守りながら、式の使い方を破る段階である。式の定義ではなく、重み、正規化、候補数、業種調整、欠損処理、時点外検証を最適化し、Phase3で変わるMoat・生まれるMoatを評価するための候補宇宙を構築する。

## 2. Phase1からの接続

Phase1の式はB/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、simple distress guardrail、Liquidity、Anomaly Reviewである。Phase2ではこれらの定義を変更していない。

## 3. Phase2が「破」である理由

Phase2で変えたものは、重み、候補数、正規化、欠損処理、業種調整、検証方法である。Future Moat、AIテーマ、Transformation Moat、中計テキストは導入していない。

## 4. Top1200正式採用

Formal Top1200 count: {len(formal)}。Phase1 Top5 coverage: {stats['phase1_top5_coverage']}/5。

Top2000は参照群であり、正式候補群ではない。Top2000 reference-only count: {len(top2000_only)}。

## 5. Financial / Distress Exclusion

金融業除外後の正式Top1200内financial count: {stats['financial_after_fix']}。
distress hard exclude後の正式Top1200内distress count: {stats['distress_after_fix']}。

## 6. Gross Profitability

Phase1およびPhase2正式候補群では、可能な限り売上総利益／総資産で定義されるGross Profitabilityを用いた。一方、過去年次パネルで売上総利益が直接取得できない場合は、収益性proxyを別名で扱い、原式とは区別した。

## 7. Normalization Consensus

{md_table(norm_summary_top)}

## 8. Point-in-time Panel / Fixed-weight Validation

EDINET提出日を基準にpoint-in-time panelを構築し、固定重みの時点外検証を実施した。

{md_table(fixed_validation)}

## 9. True Walk-forward Optimization

strict_true_walk_forward_completed = {str(true_completed).lower()}。
本成果物ではpoint-in-time panelと固定重みの年度別検証を行った。完全なtrain/test型Walk-forward optimizationは、より長い過去年次パネルを構築した後に実施する。

## 10. Phase3 Handoff

Phase3ではTop100、Top300、Top1200、Top2000参照群を使い分ける。Phase3で初めてFuture Moat、changing moat、emerging moat、AI moat、business transformationを導入する。

## 11. 限界

本成果物は将来リターン最大化モデルではない。Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。point-in-time panel validationは候補群の時点外確認であり、予測力の証明ではない。
"""
    write_text(OUT / "reports" / "phase2_final_integrated_report.md", report)
    write_text(
        OUT / "README.md",
        """
# BEYOND BUFFETT Phase2 Final Integrated Break

## これは何か

BEYOND BUFFETT Phase2（破）の最終統合成果物である。Phase1の式の定義は変えず、式の使い方を最適化した。正式候補群はTop1200である。Top2000は参照群である。

## 主な成果物

- `formal_top1200/phase2_formal_top1200_candidates.csv`
- `top2000_reference/final_weighted_top2000_reference.csv`
- `normalization/normalization_consensus_table.csv`
- `point_in_time_panel/annual_top1200_nonfinancial_by_year.csv`
- `point_in_time_panel/annual_top1200_strict_ready_by_year.csv`
- `walk_forward/fixed_weight_annual_validation.csv`
- `reports/phase2_final_integrated_report.md`
- `reports/phase2_to_phase3_handoff_final.md`
- `reports/report_text_for_paper.md`

## 注意

- Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。
- 将来リターン最大化モデルではない。
- 完全なWalk-forward optimizationが未実施の場合は、その旨を明記する。
- point-in-time panel validationは候補群の時点外確認であり、予測力の証明ではない。
""",
    )


def dangerous_expression_audit() -> None:
    dangerous = [
        "Top1200が絶対的に最適",
        "将来リターンを最大化",
        "厳密なWalk-forwardを完全実施",
        "金融業を含めて評価",
        "Gross Profitability原式で全年度検証済み",
        "anomalyが完全に存在しない",
    ]
    rows = []
    for path in sorted(OUT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for phrase in dangerous:
            rows.append({"file": str(path.relative_to(OUT)), "phrase": phrase, "found": phrase in text})
    audit = pd.DataFrame(rows)
    found = audit[audit["found"]]
    write_text(
        OUT / "logs" / "dangerous_expression_audit.md",
        "# Dangerous Expression Audit\n\n"
        + ("No dangerous expressions were found." if found.empty else md_table(found)),
    )


def validation_and_manifest(stats: dict[str, int], true_completed: bool, fixed_completed: bool, annual_summary: pd.DataFrame) -> bool:
    manifest = {
        "project": "BEYOND BUFFETT",
        "phase": "Phase2 Final Integrated Break",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formal_candidate_universe": "formal_top1200/phase2_formal_top1200_candidates.csv",
        "formal_topn": 1200,
        "utility_max_topn": 2000,
        "top2000_role": "reference_universe",
        "financial_exclusion_applied": stats["financial_after_fix"] == 0,
        "distress_hard_exclusion_applied": stats["distress_after_fix"] == 0,
        "normalization_consensus_applied": True,
        "point_in_time_panel_built": True,
        "strict_true_walk_forward_completed": true_completed,
        "fixed_weight_out_of_time_validation_completed": fixed_completed,
        "phase1_top5_coverage": int(stats["phase1_top5_coverage"]),
        "annual_top1200_financial_count_after_fix": int(annual_summary["financial_count"].sum()) if not annual_summary.empty else 0,
        "annual_top1200_distress_count_after_fix": int(annual_summary["distress_flag_count"].sum()) if not annual_summary.empty else 0,
        "important_note": "This artifact constructs a Phase3 candidate universe. It does not claim future return predictability.",
    }
    write_text(OUT / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    checks = []
    for req in REQUIRED_FILES:
        path = OUT / req
        checks.append({"file": req, "exists": path.exists(), "non_empty": path.exists() and path.stat().st_size > 0})
    formal = pd.read_csv(OUT / "formal_top1200" / "phase2_formal_top1200_candidates.csv", dtype={"code": str})
    checks.extend(
        [
            {"file": "formal_top1200_count_1200", "exists": len(formal) == 1200, "non_empty": len(formal) == 1200},
            {"file": "phase1_top5_coverage_5", "exists": int(bool_series(formal["phase1_top5_flag"]).sum()) == 5, "non_empty": int(bool_series(formal["phase1_top5_flag"]).sum()) == 5},
            {"file": "formal_financial_count_zero", "exists": stats["financial_after_fix"] == 0, "non_empty": stats["financial_after_fix"] == 0},
            {"file": "formal_distress_count_zero", "exists": stats["distress_after_fix"] == 0, "non_empty": stats["distress_after_fix"] == 0},
        ]
    )
    validation = pd.DataFrame(checks)
    validation.to_csv(OUT / "validation" / "final_validation_check.csv", index=False)
    passed = bool((validation["exists"] & validation["non_empty"]).all())
    write_text(
        OUT / "logs" / "final_validation_errors.md",
        "# Final Validation Errors\n\n" + ("No validation errors." if passed else md_table(validation[~(validation["exists"] & validation["non_empty"])])),
    )
    return passed


def checksums() -> None:
    exts = {".csv", ".json", ".md", ".png", ".py", ".sh", ".yaml"}
    rows = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "checksums.txt" and path.suffix.lower() in exts:
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(OUT)}")
    write_text(OUT / "checksums.txt", "\n".join(rows))


def zip_artifact() -> None:
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(OUT.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(OUT)
            parts = set(rel_path.parts)
            if parts & {"__pycache__", ".git", ".venv", "venv", "node_modules"}:
                continue
            if path.name == ".DS_Store" or path.suffix in {".tmp", ".log"}:
                continue
            zf.write(path, Path("phase2_final_integrated_break") / rel_path)


def zip_validation() -> bool:
    required = [str(Path("phase2_final_integrated_break") / r) for r in REQUIRED_FILES + ["checksums.txt"]]
    rows = []
    with zipfile.ZipFile(ZIP_OUT) as zf:
        names = set(zf.namelist())
        for req in required:
            rows.append({"zip_path": req, "present": req in names})
    ok = all(r["present"] for r in rows)
    lines = [
        "# ZIP Validation Report",
        "",
        f"- ZIP exists: {ZIP_OUT.exists()}",
        f"- ZIP size MB: {ZIP_OUT.stat().st_size / 1024 / 1024:.3f}",
        f"- Required files present: {ok}",
        "",
        md_table(pd.DataFrame(rows)),
    ]
    write_text(OUT / "logs" / "zip_validation_report.md", "\n".join(lines))
    return ok


def copy_script_and_config() -> None:
    shutil.copy2(Path(__file__), OUT / "scripts" / "phase2_final_integrated_break" / "generate_phase2_final_integrated_break.py")
    run_all = OUT / "scripts" / "phase2_final_integrated_break" / "run_all.sh"
    write_text(
        run_all,
        "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/../../../..\"\n.venv/bin/python scripts/phase2_final_integrated_break/generate_phase2_final_integrated_break.py",
    )
    run_all.chmod(0o755)
    write_text(
        OUT / "configs" / "phase2_final_integrated_break_config.yaml",
        "\n".join(
            [
                "output: outputs/phase2_final_integrated_break/",
                "formal_topn: 1200",
                "utility_max_topn: 2000",
                "financial_exclusion: true",
                "distress_hard_exclusion: true",
                "walk_forward_policy: point_in_time_panel_and_fixed_weight_out_of_time_validation",
                "true_walk_forward_policy: execute_only_when_at_least_two_252d_mature_folds_exist",
            ]
        ),
    )


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    ensure_dirs()
    inputs = load_inputs()
    formal, _, _, stats = prepare_formal_top1200(inputs)
    top2000, top2000_only = build_top2000_reference(inputs, formal)
    normalization = build_normalization(inputs, formal)
    norm_summary_top = pd.read_csv(OUT / "normalization" / "normalization_consensus_summary_top1200.csv")
    annual_nonfinancial, annual_strict, annual_reviews, annual_summary = annual_top1200(inputs)
    fixed_validation, overlap = fixed_weight_validation(annual_nonfinancial, annual_summary)
    true_completed = true_walk_forward_status(inputs, fixed_validation)
    audits(formal, annual_nonfinancial)
    # Mirror key optimization/ablation inputs when available.
    if SELECTED_SOLUTION.exists():
        shutil.copy2(SELECTED_SOLUTION, OUT / "optimization" / "selected_phase2_solution.json")
    if (PHASE2_REAL / "ablation" / "ablation_results_real.csv").exists():
        shutil.copy2(PHASE2_REAL / "ablation" / "ablation_results_real.csv", OUT / "ablation" / "ablation_results_real.csv")
    create_figures(formal, top2000, normalization, annual_summary, inputs)
    write_reports(formal, top2000, top2000_only, norm_summary_top, annual_summary, fixed_validation, true_completed, stats)
    copy_script_and_config()
    dangerous_expression_audit()
    checksums()
    validation_passed = validation_and_manifest(stats, true_completed, True, annual_summary)
    checksums()
    zip_artifact()
    zip_ok = zip_validation()
    checksums()
    zip_artifact()
    summary = {
        "formal_topn": 1200,
        "utility_max_topn": 2000,
        "financial_exclusion_applied": stats["financial_after_fix"] == 0,
        "distress_hard_exclusion_applied": stats["distress_after_fix"] == 0,
        "phase1_top5_coverage": stats["phase1_top5_coverage"],
        "normalization_core_in_top1200": int(bool_series(formal["normalization_core_flag"]).sum()),
        "normalization_robust_in_top1200": int(bool_series(formal["normalization_robust_flag"]).sum()),
        "strict_true_walk_forward_completed": true_completed,
        "fixed_weight_out_of_time_validation_completed": True,
        "annual_top1200_financial_count_after_fix": int(annual_summary["financial_count"].sum()) if not annual_summary.empty else 0,
        "annual_top1200_distress_count_after_fix": int(annual_summary["distress_flag_count"].sum()) if not annual_summary.empty else 0,
        "zip_validation": "passed" if zip_ok and validation_passed else "failed",
    }
    write_text(OUT / "logs" / "summary.log", json.dumps(summary, indent=2, ensure_ascii=False))
    print("Phase2 Final Integrated Break completed.")
    print("")
    print("Output directory:")
    print("outputs/phase2_final_integrated_break/")
    print("")
    print("ZIP:")
    print("outputs/phase2_final_integrated_break.zip")
    print("")
    print("Formal Phase2 candidate universe:")
    print("formal_top1200/phase2_formal_top1200_candidates.csv")
    print("")
    print("Reference universe:")
    print("top2000_reference/final_weighted_top2000_reference.csv")
    print("")
    print("Key reports:")
    print("- reports/phase2_final_integrated_report.md")
    print("- reports/phase2_to_phase3_handoff_final.md")
    print("- reports/report_text_for_paper.md")
    print("- reports/top1200_vs_top2000_final_decision.md")
    print("- reports/fixed_weight_out_of_time_validation_report.md")
    print("")
    print("Summary:")
    for key, value in summary.items():
        print(f"- {key} = {value}")


if __name__ == "__main__":
    main()
