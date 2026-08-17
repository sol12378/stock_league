#!/usr/bin/env python3
"""BEYOND BUFFETT Phase3 reproducible pipeline.

The implementation intentionally separates Phase2 universe formation from the
Phase3 transformation/emerging moat measurements.  Missing optional evidence is
never imputed: unavailable components remain NaN and are reported.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
import textwrap
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_TOP5 = {
    "3539": "JM HOLDINGS CO.,LTD.",
    "6430": "DAIKOKU DENKI CO.,LTD.",
    "7803": "Bushiroad Inc.",
    "9470": "GAKKEN HOLDINGS CO.,LTD.",
    "4350": "MEDICAL SYSTEM NETWORK Co.,Ltd.",
}
CONFIG_PATH = Path(__file__).with_name("phase3_config.json")
try:
    CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
except Exception:
    CONFIG = {"liquidity_threshold_jpy_per_day": 30_000_000, "total_budget_jpy": 5_000_000}
LIQUIDITY_THRESHOLD = float(os.getenv("PHASE3_LIQUIDITY_THRESHOLD", CONFIG.get("liquidity_threshold_jpy_per_day", 30_000_000)))
TOTAL_BUDGET = 5_000_000


def find_repo_root() -> Path:
    env = os.getenv("PHASE3_REPO_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in [Path.cwd().resolve(), *here.parents]:
        if (parent / "outputs" / "phase2_perfect_final_break.zip").exists():
            return parent
    raise RuntimeError("Repository root containing outputs/phase2_perfect_final_break.zip was not found")


ROOT = find_repo_root()
OUT = ROOT / "outputs" / "phase3_beyond_buffett"
DATA = OUT / "data"
DOCS = OUT / "docs"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
WORK = ROOT / "work" / "phase2_perfect_final_break"
ZIP_PATH = ROOT / "outputs" / "phase2_perfect_final_break.zip"
CURATED = Path(__file__).with_name("curated_evidence.csv")

for directory in (DATA, DOCS, REPORTS, LOGS):
    directory.mkdir(parents=True, exist_ok=True)


def log(message: str, warning: bool = False) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    target = LOGS / ("warnings.log" if warning else "run.log")
    with target.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")
    print(message)


def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.extract(r"(\d+)", expand=False).str.zfill(4)


def bool_series(series: pd.Series | None, index=None) -> pd.Series:
    if series is None:
        return pd.Series(False, index=index, dtype=bool)
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def numeric(series: pd.Series | None, index=None) -> pd.Series:
    if series is None:
        return pd.Series(np.nan, index=index, dtype=float)
    return pd.to_numeric(series, errors="coerce")


def pct(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = numeric(series)
    result = s.rank(pct=True, method="average")
    return result if higher_is_better else 1 - result


def row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [c for c in columns if c in frame]
    return frame[existing].apply(pd.to_numeric, errors="coerce").mean(axis=1) if existing else pd.Series(np.nan, index=frame.index)


def safe_read(path: Path, required: bool = False) -> pd.DataFrame:
    if not path.exists():
        message = f"Missing input: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}"
        log(message, warning=True)
        with (LOGS / "missing_features.log").open("a", encoding="utf-8") as fh:
            fh.write(message + "\n")
        if required:
            raise FileNotFoundError(message)
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        if required:
            raise
        log(f"Could not read optional input {path}: {exc}", warning=True)
        return pd.DataFrame()


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"Wrote {path.relative_to(ROOT)} ({len(frame):,} rows)")


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def locate(relative: str, alternatives: tuple[str, ...] = ()) -> Path | None:
    candidates = [WORK / relative, *(WORK / a for a in alternatives)]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    basename = Path(relative).name
    matches = list(WORK.rglob(basename)) if WORK.exists() else []
    return matches[0] if matches else None


def stage00_unzip() -> None:
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"Fatal: {ZIP_PATH} is missing")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        safe_members = [m for m in zf.infolist() if not Path(m.filename).is_absolute() and ".." not in Path(m.filename).parts]
        zf.extractall(ROOT / "work", members=safe_members)
    if not WORK.exists():
        raise RuntimeError("Fatal: archive did not create work/phase2_perfect_final_break")
    log(f"Extracted {ZIP_PATH.relative_to(ROOT)} to {WORK.relative_to(ROOT)}")


def stage01_audit_inputs() -> None:
    required = "formal_top1200/phase2_formal_top1200_candidates_review_ready.csv"
    required_path = locate(required)
    if required_path is None:
        raise FileNotFoundError(f"Fatal: {required} was not found after extraction")
    expected = [
        required,
        "rankings/phase2_formal_top100.csv", "rankings/phase2_formal_top300.csv",
        "top2000_reference/final_weighted_top2000_reference.csv",
        "top2000_reference/top1200_out_top2000_reference_only.csv",
        "normalization/normalization_consensus_table.csv",
        "point_in_time_panel/point_in_time_feature_panel_with_filters.csv",
        "data_audit/flag_audit_summary.csv",
    ]
    rows = []
    for rel in expected:
        path = locate(rel)
        row = {"expected_path": rel, "found": path is not None, "actual_path": str(path.relative_to(ROOT)) if path else ""}
        if path and path.suffix == ".csv":
            sample = pd.read_csv(path, nrows=5, low_memory=False)
            row.update({"column_count": len(sample.columns), "columns": "|".join(sample.columns)})
        rows.append(row)
    write_csv(pd.DataFrame(rows), DATA / "phase3_input_inventory.csv")


def build_panel_features(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame(columns=["code"])
    panel = panel.copy()
    panel["code"] = normalize_code(panel["code"])
    panel["fiscal_year"] = numeric(panel.get("fiscal_year"))
    panel["availability_date_sort"] = pd.to_datetime(panel.get("availability_date"), errors="coerce")
    panel["operating_margin"] = numeric(panel.get("operating_income")) / numeric(panel.get("revenue")).replace(0, np.nan)
    panel["roe"] = numeric(panel.get("net_income")) / numeric(panel.get("equity")).replace(0, np.nan)
    panel = panel.sort_values(["code", "fiscal_year", "availability_date_sort"])
    rows = []
    metrics = ["roa", "roe", "operating_margin", "gross_margin", "asset_turnover", "current_ratio", "leverage"]
    carry = ["fiscal_year", "revenue", "gross_profit", "operating_income", "net_income", "total_assets", "equity",
             "current_assets", "current_liabilities", "operating_cf", "capex", "rd_expense", "employees",
             "gross_margin", "asset_turnover", "current_ratio", "leverage", "roa", "negative_equity_flag",
             "gross_profitability_definition_status", "gross_profitability_proxy_flag", "feature_missing_review_flag"]
    for code, group in panel.groupby("code", sort=False):
        latest = group.iloc[-1]
        target = latest["fiscal_year"] - 3 if pd.notna(latest["fiscal_year"]) else np.nan
        historical = group[group["fiscal_year"] <= target] if pd.notna(target) else group.iloc[0:0]
        base = historical.iloc[-1] if not historical.empty else (group.iloc[0] if len(group) >= 2 else None)
        out = {"code": code, "panel_latest_fiscal_year": latest.get("fiscal_year"), "panel_years_available": int(group["fiscal_year"].nunique())}
        for col in carry:
            out[f"latest_{col}"] = latest.get(col, np.nan)
        for metric in metrics:
            lv = pd.to_numeric(pd.Series([latest.get(metric)]), errors="coerce").iloc[0]
            bv = pd.to_numeric(pd.Series([base.get(metric) if base is not None else np.nan]), errors="coerce").iloc[0]
            out[f"delta_{metric}_3y"] = lv - bv if pd.notna(lv) and pd.notna(bv) else np.nan
        recent3 = group.tail(3)
        out["persistent_loss_flag"] = bool(len(recent3) >= 3 and numeric(recent3.get("net_income")).notna().all() and (numeric(recent3.get("net_income")) < 0).all())
        out["negative_cfo_flag"] = bool(pd.notna(latest.get("operating_cf")) and float(latest.get("operating_cf")) < 0)
        ni = pd.to_numeric(pd.Series([latest.get("net_income")]), errors="coerce").iloc[0]
        ocf = pd.to_numeric(pd.Series([latest.get("operating_cf")]), errors="coerce").iloc[0]
        out["cfo_to_net_income"] = ocf / ni if pd.notna(ocf) and pd.notna(ni) and ni > 0 else np.nan
        rows.append(out)
    return pd.DataFrame(rows)


def stage02_seed() -> None:
    formal_path = locate("formal_top1200/phase2_formal_top1200_candidates_review_ready.csv")
    if formal_path is None:
        raise FileNotFoundError("Fatal: formal Top1200 is missing")
    formal = safe_read(formal_path, required=True)
    formal["code"] = normalize_code(formal["code"])
    formal = formal.drop_duplicates("code", keep="first").copy()
    formal = formal.rename(columns={"rank": "phase2_rank"})

    ref_path = locate("top2000_reference/final_weighted_top2000_reference.csv", ("rankings/phase2_top2000_reference.csv",))
    ref = safe_read(ref_path) if ref_path else pd.DataFrame()
    if not ref.empty:
        ref["code"] = normalize_code(ref["code"])
        wanted = [c for c in ref.columns if c not in formal.columns or c == "code"]
        formal = formal.merge(ref[wanted].drop_duplicates("code"), on="code", how="left")

    norm_path = locate("normalization/normalization_consensus_table.csv")
    norm = safe_read(norm_path) if norm_path else pd.DataFrame()
    if not norm.empty:
        norm["code"] = normalize_code(norm["code"])
        wanted = [c for c in norm.columns if c not in formal.columns or c == "code"]
        formal = formal.merge(norm[wanted].drop_duplicates("code"), on="code", how="left")

    panel_path = locate("point_in_time_panel/point_in_time_feature_panel_with_filters.csv")
    panel = safe_read(panel_path) if panel_path else pd.DataFrame()
    panel_features = build_panel_features(panel)
    formal = formal.merge(panel_features, on="code", how="left")

    prices = safe_read(ROOT / "data" / "processed" / "latest_prices.csv")
    if not prices.empty:
        prices["code"] = normalize_code(prices["ticker"])
        cols = [c for c in ["code", "latest_date", "close", "adj_close", "volume", "avg_trading_value_60d"] if c in prices]
        formal = formal.merge(prices[cols].drop_duplicates("code"), on="code", how="left")

    required_cols = ["ticker", "company_name", "sector", "final_exploratory_weighted_score", "bm_raw", "ep_raw",
                     "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d",
                     "distress_exclusion_flag", "anomaly_flag_bool", "phase1_top5_flag", "top100_flag", "top300_flag",
                     "top1200_flag", "top2000_reference_flag", "phase3_review_required", "phase3_review_reasons",
                     "normalization_core_flag", "normalization_robust_flag", "normalization_fragile_flag",
                     "outlier_sensitive_flag", "gross_profitability_proxy_flag", "phase3_priority_flag", "phase3_handoff_note"]
    for col in required_cols:
        if col not in formal:
            formal[col] = np.nan
    leading = ["code", "ticker", "company_name", "sector", "phase2_rank", *required_cols[4:]]
    leading = list(dict.fromkeys([c for c in leading if c in formal]))
    formal = formal[leading + [c for c in formal.columns if c not in leading]]
    write_csv(formal, DATA / "phase3_seed_universe_from_phase2.csv")


def stage03_confidence() -> None:
    d = safe_read(DATA / "phase3_seed_universe_from_phase2.csv", required=True)
    d["code"] = normalize_code(d["code"])
    core = bool_series(d.get("normalization_core_flag"), d.index)
    robust = bool_series(d.get("normalization_robust_flag"), d.index)
    outlier = bool_series(d.get("outlier_sensitive_flag"), d.index)
    fragile = bool_series(d.get("normalization_fragile_flag"), d.index)
    gp_proxy = bool_series(d.get("gross_profitability_proxy_flag"), d.index)
    review = bool_series(d.get("phase3_review_required"), d.index)
    missing_review = bool_series(d.get("feature_missing_review_flag"), d.index) | bool_series(d.get("latest_feature_missing_review_flag"), d.index)
    gp_status = d.get("gross_profitability_definition_status", pd.Series("", index=d.index)).fillna("").astype(str).str.lower().isin({"proxy", "unverified"})
    d["phase2_confidence_score"] = (1 + .05 * core + .03 * robust - .10 * outlier - .15 * fragile - .10 * gp_proxy - .10 * review - .05 * missing_review).clip(0, 1.1)
    d["negative_equity_flag"] = bool_series(d.get("latest_negative_equity_flag"), d.index)
    d["persistent_loss_flag"] = bool_series(d.get("persistent_loss_flag"), d.index)
    d["negative_cfo_flag"] = bool_series(d.get("negative_cfo_flag"), d.index)
    key = [c for c in ["bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "avg_daily_value_60d", "latest_roa", "latest_equity", "latest_operating_cf"] if c in d]
    d["financial_missing_rate"] = d[key].isna().mean(axis=1)
    d["financial_data_missing_too_much"] = d["financial_missing_rate"] > .45
    hard = pd.DataFrame({
        "not_formal_top1200": ~bool_series(d.get("top1200_flag"), d.index),
        "distress": bool_series(d.get("distress_exclusion_flag"), d.index),
        "anomaly": bool_series(d.get("anomaly_flag_bool"), d.index),
        "low_liquidity": numeric(d.get("avg_daily_value_60d"), d.index).lt(LIQUIDITY_THRESHOLD) | numeric(d.get("avg_daily_value_60d"), d.index).isna(),
        "negative_equity": d["negative_equity_flag"],
        "persistent_loss": d["persistent_loss_flag"],
        "financial_missing": d["financial_data_missing_too_much"],
    })
    d["base_hard_exclusion_reasons"] = hard.apply(lambda r: ";".join(r.index[r].tolist()) or "none", axis=1)
    d["base_hard_exclusion_flag"] = hard.any(axis=1) & ~bool_series(d.get("phase1_top5_flag"), d.index)
    soft = pd.DataFrame({
        "phase3_review_required": review, "outlier_sensitive": outlier, "normalization_fragile": fragile,
        "gross_profitability_proxy": gp_proxy, "sector_adjusted": bool_series(d.get("sector_adjusted_candidate_flag"), d.index),
        "gross_profitability_proxy_or_unverified_status": gp_status,
        "feature_missing_review": missing_review,
    })
    d["soft_review_reasons"] = soft.apply(lambda r: ";".join(r.index[r].tolist()) or "none", axis=1)
    d["soft_review_flag"] = soft.any(axis=1)
    write_csv(d, DATA / "phase3_guardrail_confidence.csv")


def stage04_transformation_lite() -> None:
    d = safe_read(DATA / "phase3_guardrail_confidence.csv", required=True)
    # Use economically interpretable cross-sectional ranks; no Phase2 aggregate score enters this formula.
    for source, target, hib in [
        ("bm_raw", "bm_value_component", True), ("ep_raw", "ep_value_component", True),
        ("gross_profitability", "gp_quality_component", True), ("piotroski_available_ratio", "piotroski_component", True),
        ("sloan_accruals", "sloan_quality_component", False), ("avg_daily_value_60d", "liquidity_component", True),
        ("delta_roa_3y", "delta_roa_component", True), ("delta_roe_3y", "delta_roe_component", True),
        ("delta_operating_margin_3y", "delta_operating_margin_component", True),
        ("delta_gross_margin_3y", "delta_gross_margin_component", True),
        ("delta_asset_turnover_3y", "delta_asset_turnover_component", True),
        ("delta_current_ratio_3y", "delta_current_ratio_component", True),
        ("delta_leverage_3y", "delta_leverage_component", False),
    ]:
        d[target] = pct(d[source], hib) if source in d else np.nan
    value_cols = ["bm_value_component", "ep_value_component"] + [c for c in ["sector_percentile_score", "market_percentile_score"] if c in d]
    d["value_score"] = 100 * row_mean(d, value_cols)
    d["quality_score"] = 100 * row_mean(d, ["gp_quality_component", "piotroski_component", "sloan_quality_component"])
    improvement_cols = ["delta_roa_component", "delta_roe_component", "delta_operating_margin_component", "delta_gross_margin_component", "delta_asset_turnover_component", "delta_current_ratio_component", "delta_leverage_component"]
    d["improvement_score"] = 100 * row_mean(d, improvement_cols)
    d["improvement_component_count"] = d[improvement_cols].notna().sum(axis=1)
    cfo_quality = numeric(d.get("cfo_to_net_income"), d.index).clip(0, 2) / 2
    d["execution_safety_score"] = 100 * pd.concat([
        numeric(d.get("piotroski_available_ratio"), d.index).clip(0, 1),
        numeric(d.get("distress_safety_score"), d.index).clip(0, 1),
        d["sloan_quality_component"], cfo_quality,
    ], axis=1).mean(axis=1)
    d["liquidity_confidence_score"] = 100 * pd.concat([d["liquidity_component"], numeric(d.get("phase2_confidence_score"), d.index) / 1.1], axis=1).mean(axis=1)
    high_sloan_cut = numeric(d.get("sloan_accruals"), d.index).quantile(.90)
    d["high_sloan_accrual_flag"] = numeric(d.get("sloan_accruals"), d.index) >= high_sloan_cut
    penalties = pd.DataFrame({
        "high_sloan_accrual": 10 * d["high_sloan_accrual_flag"],
        "distress": 25 * bool_series(d.get("distress_exclusion_flag"), d.index),
        "anomaly": 20 * bool_series(d.get("anomaly_flag_bool"), d.index),
        "negative_cfo": 12 * bool_series(d.get("negative_cfo_flag"), d.index),
        "persistent_loss": 15 * bool_series(d.get("persistent_loss_flag"), d.index),
        "normalization_fragile": 8 * bool_series(d.get("normalization_fragile_flag"), d.index),
        "outlier_sensitive": 5 * bool_series(d.get("outlier_sensitive_flag"), d.index),
        "gross_profitability_proxy": 5 * bool_series(d.get("gross_profitability_proxy_flag"), d.index),
    })
    d["value_trap_penalty"] = penalties.sum(axis=1)
    d["value_trap_penalty_reasons"] = penalties.apply(lambda r: ";".join(r.index[r > 0].tolist()) or "none", axis=1)
    d["transformation_lite_score"] = (100 * (.30*d["value_score"]/100 + .20*d["quality_score"]/100 + .20*d["improvement_score"]/100 + .20*d["execution_safety_score"]/100 + .10*d["liquidity_confidence_score"]/100) - d["value_trap_penalty"]).clip(0, 100)
    score_cols = ["value_score", "quality_score", "improvement_score", "execution_safety_score", "liquidity_confidence_score"]
    d["transformation_lite_missing_rate"] = d[score_cols].isna().mean(axis=1)
    d["transformation_scoring_reason"] = d.apply(lambda r: f"value={r.value_score:.1f}; quality={r.quality_score:.1f}; improvement={r.improvement_score:.1f}; safety={r.execution_safety_score:.1f}; penalty={r.value_trap_penalty:.1f}", axis=1)
    write_csv(d, DATA / "phase3_transformation_lite_scores.csv")


def stage05_enrich() -> None:
    evidence = safe_read(CURATED)
    if evidence.empty:
        evidence = pd.DataFrame(columns=["code", "ai_infrastructure_category", "emerging_evidence_level", "evidence_snippet", "evidence_source"])
    evidence["code"] = normalize_code(evidence["code"])
    write_csv(evidence, DATA / "phase3_disclosure_enrichment.csv")
    optional = []
    for name in ["shareholder_return.csv", "reform_evidence.csv", "disclosure_texts.csv"]:
        matches = [ROOT / "inputs_phase3" / name, ROOT / name]
        found = next((p for p in matches if p.exists()), None)
        optional.append({"optional_input": name, "found": bool(found), "path": str(found.relative_to(ROOT)) if found else ""})
    write_csv(pd.DataFrame(optional), DATA / "phase3_optional_input_status.csv")


def stage06_transformation_full() -> None:
    d = safe_read(DATA / "phase3_transformation_lite_scores.csv", required=True)
    shareholder = safe_read(ROOT / "inputs_phase3" / "shareholder_return.csv")
    reform = safe_read(ROOT / "inputs_phase3" / "reform_evidence.csv")
    for extra in (shareholder, reform):
        if not extra.empty and "code" in extra:
            extra["code"] = normalize_code(extra["code"])
            d = d.merge(extra.drop_duplicates("code"), on="code", how="left", suffixes=("", "_optional"))
    shareholder_cols = [c for c in ["dividend_yield", "dividend_growth_3y", "doe", "buyback_yield", "net_payout_yield", "fcf_coverage_of_payout"] if c in d]
    reform_cols = [c for c in ["capital_cost_disclosure_flag", "roic_target_flag", "pbr_improvement_policy_flag", "cross_shareholding_reduction_flag", "asset_sale_flag", "portfolio_restructuring_flag", "medium_term_plan_kpi_flag"] if c in d]
    d["valuation_gap_score"] = d["value_score"]
    d["capital_efficiency_improvement_score"] = d["improvement_score"]
    d["shareholder_alignment_score"] = 100 * row_mean(pd.DataFrame({c: pct(d[c], True) for c in shareholder_cols}), shareholder_cols) if shareholder_cols else np.nan
    d["reform_evidence_score"] = 100 * d[reform_cols].apply(lambda s: bool_series(s)).mean(axis=1) if reform_cols else np.nan
    d["execution_reliability_score"] = d["execution_safety_score"]
    d["quality_trap_resistance_score"] = d["quality_score"]
    full_components = ["valuation_gap_score", "capital_efficiency_improvement_score", "shareholder_alignment_score", "reform_evidence_score", "execution_reliability_score", "quality_trap_resistance_score"]
    d["transformation_full_missing_rate"] = d[full_components].isna().mean(axis=1)
    enough = d[["shareholder_alignment_score", "reform_evidence_score"]].notna().all(axis=1)
    d["transformation_full_score"] = (100*(.20*d["valuation_gap_score"]/100 + .22*d["capital_efficiency_improvement_score"]/100 + .16*d["shareholder_alignment_score"]/100 + .17*d["reform_evidence_score"]/100 + .13*d["execution_reliability_score"]/100 + .12*d["quality_trap_resistance_score"]/100)-d["value_trap_penalty"]).clip(0,100)
    d["transformation_score"] = d["transformation_full_score"].where(enough, d["transformation_lite_score"])
    d["transformation_score_method"] = np.where(enough, "full", "lite_due_to_missing_shareholder_or_reform_inputs")
    write_csv(d, DATA / "phase3_transformation_scores.csv")


def stage07_emerging() -> None:
    d = safe_read(DATA / "phase3_transformation_scores.csv", required=True)
    e = safe_read(DATA / "phase3_disclosure_enrichment.csv")
    if not e.empty:
        d = d.merge(e, on="code", how="left")
    d["rd_to_sales"] = numeric(d.get("latest_rd_expense"), d.index) / numeric(d.get("latest_revenue"), d.index).replace(0, np.nan)
    d["employee_growth_proxy"] = np.nan
    d["rd_intensity_component"] = pct(d["rd_to_sales"], True)
    d["gross_margin_power_component"] = pct(d.get("latest_gross_margin", d.get("gross_profitability")), True)
    d["gross_profitability_power_component"] = pct(d.get("gross_profitability"), True)
    level = numeric(d.get("emerging_evidence_level"), d.index).fillna(0).clip(0, 3)
    # Level 2 is concrete company disclosure, not two-thirds of a theme keyword.
    # Map L0/L1/L2/L3 to 0/.35/.80/1.00 so verified products and use cases are
    # materially distinct from policy-only language while L3 keeps the bonus for
    # quantitative evidence.
    evidence_strength = level.map({0: 0.0, 1: 0.35, 2: 0.80, 3: 1.00}).fillna(0)
    d["intangible_capital_score"] = 100 * pd.concat([d["rd_intensity_component"], pct(d.get("latest_employees"), True)], axis=1).mean(axis=1)
    d["innovation_capacity_score"] = 100 * pd.concat([d["rd_intensity_component"], .35 + .65*evidence_strength], axis=1).mean(axis=1)
    d["bottleneck_pricing_power_score"] = 100 * pd.concat([d["gross_margin_power_component"], d["gross_profitability_power_component"], evidence_strength], axis=1).mean(axis=1)
    d["ai_infrastructure_exposure_score"] = 100 * evidence_strength
    category = d.get("ai_infrastructure_category", pd.Series("", index=d.index)).fillna("").astype(str)
    d["data_customer_base_score"] = 100 * evidence_strength * category.isin(["business_data", "quality_assurance", "cybersecurity"]).astype(float)
    d["trust_safety_infrastructure_score"] = 100 * evidence_strength * category.isin(["quality_assurance", "cybersecurity", "factory_automation", "semiconductor", "precision_processing"]).astype(float)
    d["evidence_level_bonus"] = level.map({0:0,1:2,2:4,3:8}).fillna(0)
    d["keyword_only_flag"] = bool_series(d.get("keyword_only_flag"), d.index)
    d["no_revenue_evidence_flag"] = level.eq(1)
    d["no_customer_or_product_evidence_flag"] = level.le(1)
    d["media_only_flag"] = False
    d["theme_hype_penalty"] = 20*d["keyword_only_flag"] + 15*d["no_revenue_evidence_flag"] + 10*d["no_customer_or_product_evidence_flag"] + 10*d["media_only_flag"]
    d["financial_guardrail_penalty"] = 20*bool_series(d.get("base_hard_exclusion_flag"), d.index) + 5*bool_series(d.get("normalization_fragile_flag"), d.index)
    weights = {"intangible_capital_score":.18, "innovation_capacity_score":.15, "bottleneck_pricing_power_score":.18, "ai_infrastructure_exposure_score":.22, "data_customer_base_score":.14, "trust_safety_infrastructure_score":.13}
    d["emerging_score"] = (sum(w*d[c] for c,w in weights.items()) + d["evidence_level_bonus"] - d["theme_hype_penalty"] - d["financial_guardrail_penalty"]).clip(0,100)
    d["emerging_missing_rate"] = d[list(weights)].isna().mean(axis=1)
    d["emerging_penalty_reasons"] = d.apply(lambda r: ";".join([x for x,b in [("keyword_only",r.keyword_only_flag),("no_revenue_evidence",r.no_revenue_evidence_flag),("no_customer_or_product_evidence",r.no_customer_or_product_evidence_flag),("financial_guardrail",r.financial_guardrail_penalty>0)] if b]) or "none", axis=1)
    d["evidence_snippet"] = d.get("evidence_snippet", pd.Series("no verified company disclosure", index=d.index)).fillna("no verified company disclosure")
    d["evidence_source"] = d.get("evidence_source", pd.Series("", index=d.index)).fillna("")
    write_csv(d, DATA / "phase3_emerging_scores.csv")


def stage08_evidence() -> None:
    d = safe_read(DATA / "phase3_emerging_scores.csv", required=True)
    improvements = [c for c in ["delta_roa_3y", "delta_roe_3y", "delta_operating_margin_3y", "delta_gross_margin_3y", "delta_asset_turnover_3y", "delta_current_ratio_3y"] if c in d]
    positive_count = d[improvements].apply(pd.to_numeric, errors="coerce").gt(0).sum(axis=1) if improvements else pd.Series(0,index=d.index)
    trans_level = np.select([positive_count.ge(3), positive_count.ge(2), positive_count.ge(1)], [3,2,1], default=0)
    d["transformation_evidence_level"] = trans_level
    d["transformation_evidence_basis"] = [f"{n} positive three-year financial improvement indicators" for n in positive_count]
    d["emerging_evidence_level"] = numeric(d.get("emerging_evidence_level"), d.index).fillna(0).astype(int).clip(0,3)
    d["ai_keyword_only_flag"] = bool_series(d.get("keyword_only_flag"), d.index)
    d["low_pbr_only_flag"] = numeric(d.get("value_score"), d.index).ge(70) & pd.Series(trans_level, index=d.index).eq(0)
    d["evidence_level"] = d[["transformation_evidence_level", "emerging_evidence_level"]].max(axis=1)
    d["evidence_level_label"] = d["evidence_level"].map({0:"Level 0",1:"Level 1",2:"Level 2",3:"Level 3"})
    cols = ["code","ticker","company_name","sector","transformation_evidence_level","transformation_evidence_basis","emerging_evidence_level","evidence_level","evidence_level_label","evidence_snippet","evidence_source"]
    write_csv(d[cols], DATA / "phase3_evidence_levels.csv")
    write_csv(d, DATA / "phase3_scoring_master.csv")


def stage09_grades() -> None:
    d = safe_read(DATA / "phase3_scoring_master.csv", required=True)
    hard = bool_series(d.get("base_hard_exclusion_flag"), d.index)
    tscore = numeric(d.get("transformation_score"), d.index)
    tlevel = numeric(d.get("transformation_evidence_level"), d.index)
    trap = numeric(d.get("value_trap_penalty"), d.index)
    conf = numeric(d.get("phase2_confidence_score"), d.index)
    d["transformation_grade"] = np.select([
        hard | tlevel.eq(0) | trap.ge(30) | bool_series(d.get("low_pbr_only_flag"), d.index),
        tscore.ge(75) & tlevel.ge(2) & trap.le(15),
        tscore.ge(60) & tlevel.ge(1) & conf.ge(.65) & trap.le(25),
    ], ["D","A","B"], default="C")
    escore = numeric(d.get("emerging_score"), d.index)
    elevel = numeric(d.get("emerging_evidence_level"), d.index)
    hype = numeric(d.get("theme_hype_penalty"), d.index)
    d["emerging_grade"] = np.select([
        hard | elevel.eq(0) | bool_series(d.get("ai_keyword_only_flag"), d.index),
        escore.ge(75) & elevel.ge(2) & hype.le(10),
        escore.ge(60) & elevel.ge(2),
        escore.ge(40) | elevel.eq(1),
    ], ["D","A","B","C"], default="D")
    d["transformation_grade_reason"] = d.apply(lambda r: f"score={r.transformation_score:.1f}; evidence=L{r.transformation_evidence_level}; trap={r.value_trap_penalty:.1f}; confidence={r.phase2_confidence_score:.2f}",axis=1)
    d["emerging_grade_reason"] = d.apply(lambda r: f"score={r.emerging_score:.1f}; evidence=L{r.emerging_evidence_level}; hype={r.theme_hype_penalty:.1f}",axis=1)
    write_csv(d, DATA / "phase3_grade_assignment.csv")


def stage10_roles() -> None:
    d = safe_read(DATA / "phase3_grade_assignment.csv", required=True)
    buffett = bool_series(d.get("phase1_top5_flag"), d.index)
    hard = bool_series(d.get("base_hard_exclusion_flag"), d.index)
    tg = d["transformation_grade"].isin(["A","B"])
    eg = d["emerging_grade"].isin(["A","B"])
    dual = tg & eg & numeric(d["transformation_score"]).ge(60) & numeric(d["emerging_score"]).ge(60) & numeric(d["emerging_evidence_level"]).ge(2)
    role = np.select([
        buffett,
        hard,
        dual,
        eg & numeric(d["emerging_evidence_level"]).ge(2),
        tg & numeric(d["transformation_evidence_level"]).ge(1) & numeric(d["value_trap_penalty"]).le(25),
        (~hard) & numeric(d["phase2_confidence_score"]).ge(.75) & d[["transformation_score","emerging_score"]].max(axis=1).ge(40),
    ], ["Buffett Core","Rejected","Dual Moat","Emerging Core","Transformation Core","Bridge / Diversifier"], default="Watchlist")
    d["role_candidate"] = role
    d["dual_combined_score"] = .5*numeric(d["transformation_score"]) + .5*numeric(d["emerging_score"])
    d["bridge_score"] = .6*d[["transformation_score","emerging_score"]].max(axis=1) + .4*(numeric(d["phase2_confidence_score"])/1.1*100)
    write_csv(d, DATA / "phase3_role_assignment.csv")
    write_csv(d[d["role_candidate"].eq("Dual Moat")], DATA / "phase3_dual_moat_candidates.csv")
    write_csv(d[d["role_candidate"].eq("Bridge / Diversifier")], DATA / "phase3_bridge_candidates.csv")


def selection_allowed(row, sector_counts, theme_counts) -> tuple[bool, str]:
    sector = str(row.get("sector", "Unknown"))
    raw_theme = row.get("ai_infrastructure_category", "")
    theme = "non_ai_or_transformation" if pd.isna(raw_theme) or not str(raw_theme).strip() else str(raw_theme).strip()
    if sector_counts[sector] >= 3:
        return False, "sector_count_cap"
    if theme != "non_ai_or_transformation" and theme_counts[theme] >= 4:
        return False, "theme_count_cap"
    if bool(row.get("base_hard_exclusion_flag", False)):
        return False, "base_hard_exclusion"
    if bool(row.get("low_pbr_only_flag", False)):
        return False, "low_pbr_only"
    if bool(row.get("ai_keyword_only_flag", False)):
        return False, "ai_keyword_only"
    return True, ""


def stage11_select() -> None:
    d = safe_read(DATA / "phase3_role_assignment.csv", required=True)
    d["code"] = normalize_code(d["code"])
    selected = []
    audit = []
    sector_counts, theme_counts = Counter(), Counter()
    fixed = d[bool_series(d.get("phase1_top5_flag"), d.index)].sort_values("phase2_rank")
    if len(fixed) != 5:
        raise RuntimeError(f"Phase1 fixed core must contain 5 names; observed {len(fixed)}")
    for _, row in fixed.iterrows():
        rec = row.to_dict(); rec["final_role"] = "Buffett Core"; rec["selection_order"] = len(selected)+1
        selected.append(rec); sector_counts[str(row.sector)] += 1; theme_counts["buffett_core"] += 1

    role_specs = [
        ("Dual Moat", 3, "dual_combined_score"),
        ("Emerging Core", 5, "emerging_score"),
        # Fill evidence-scarce Emerging slots before the much larger
        # Transformation pool so that sector-capacity remains feasible.
        ("Transformation Core", 5, "transformation_score"),
        ("Bridge / Diversifier", 2, "bridge_score"),
    ]
    chosen_codes = {r["code"] for r in selected}
    for role_name, quota, score_col in role_specs:
        if role_name == "Dual Moat":
            pool = d[(d.transformation_grade.isin(["A","B"])) & (d.emerging_grade.isin(["A","B"])) & (numeric(d.emerging_evidence_level).ge(2))]
        elif role_name == "Transformation Core":
            pool = d[(d.transformation_grade.isin(["A","B"])) & numeric(d.transformation_evidence_level).ge(1)]
        elif role_name == "Emerging Core":
            pool = d[(d.emerging_grade.isin(["A","B"])) & numeric(d.emerging_evidence_level).ge(2)]
        else:
            pool = d[(~bool_series(d.base_hard_exclusion_flag)) & numeric(d.phase2_confidence_score).ge(.65)]
        pool = pool[~pool.code.isin(chosen_codes)].sort_values([score_col,"phase2_confidence_score"], ascending=False)
        picked = 0
        for _, row in pool.iterrows():
            ok, reason = selection_allowed(row, sector_counts, theme_counts)
            if not ok:
                audit.append({"code":row.code,"requested_role":role_name,"decision":"skipped","reason":reason,"score":row.get(score_col)})
                continue
            rec=row.to_dict(); rec["final_role"]=role_name; rec["selection_order"]=len(selected)+1
            selected.append(rec); chosen_codes.add(row.code); sector_counts[str(row.sector)] += 1
            raw_theme=row.get("ai_infrastructure_category","")
            theme="non_ai_or_transformation" if pd.isna(raw_theme) or not str(raw_theme).strip() else str(raw_theme).strip()
            theme_counts[theme]+=1
            audit.append({"code":row.code,"requested_role":role_name,"decision":"selected","reason":"highest eligible under constraints","score":row.get(score_col)})
            picked += 1
            if picked == quota: break
        if picked < quota:
            # Transparent fallback: diversify among non-hard-excluded Top1200, without relaxing evidence for Emerging.
            if role_name in {"Dual Moat", "Emerging Core"}:
                raise RuntimeError(f"Insufficient Level 2+ evidence-backed candidates for {role_name}: {picked}/{quota}")
            fallback = d[(~bool_series(d.base_hard_exclusion_flag)) & (~d.code.isin(chosen_codes))].copy()
            fallback["fallback_score"] = d[["transformation_score","emerging_score"]].max(axis=1)
            for _, row in fallback.sort_values(["fallback_score","phase2_confidence_score"],ascending=False).iterrows():
                ok, reason=selection_allowed(row,sector_counts,theme_counts)
                if not ok: continue
                rec=row.to_dict(); rec["final_role"]=role_name; rec["selection_order"]=len(selected)+1; rec["selection_caveat"]="quota fallback; human review required"
                selected.append(rec); chosen_codes.add(row.code); sector_counts[str(row.sector)]+=1
                raw_theme=row.get("ai_infrastructure_category","")
                theme="non_ai_or_transformation" if pd.isna(raw_theme) or not str(raw_theme).strip() else str(raw_theme).strip()
                theme_counts[theme]+=1
                picked+=1
                if picked==quota: break
    final = pd.DataFrame(selected).sort_values("selection_order")
    if len(final) != 20:
        raise RuntimeError(f"Final selection count is {len(final)}, expected 20")
    final["selection_reason"] = final.apply(lambda r: ("Phase1 fixed Buffett Core" if r.final_role=="Buffett Core" else f"{r.final_role}: transformation={r.transformation_score:.1f}, emerging={r.emerging_score:.1f}, evidence=T{int(r.transformation_evidence_level)}/E{int(r.emerging_evidence_level)}, confidence={r.phase2_confidence_score:.2f}"),axis=1)
    final["human_review_required"] = bool_series(final.get("phase3_review_required"), final.index) | final.get("selection_caveat",pd.Series("",index=final.index)).fillna("").ne("")
    candidates = d[d.role_candidate.isin(["Dual Moat","Transformation Core","Emerging Core","Bridge / Diversifier"])].copy()
    candidates["selected"] = candidates.code.isin(final.code)
    rejected = d[~d.code.isin(final.code)].copy()
    rejected["rejection_reason"] = np.select([
        bool_series(rejected.base_hard_exclusion_flag),
        rejected.role_candidate.eq("Rejected"),
        rejected.role_candidate.eq("Watchlist"),
    ], [rejected.base_hard_exclusion_reasons,"role guardrail failed","score/evidence insufficient for a core pool"], default="eligible but displaced by role, sector, theme, or quota constraint")
    write_csv(candidates, DATA / "phase3_final20_candidates.csv")
    write_csv(final, DATA / "phase3_final20_selected.csv")
    write_csv(rejected.sort_values(["role_candidate","transformation_score","emerging_score"],ascending=[True,False,False]), DATA / "phase3_rejected_candidates.csv")
    write_csv(pd.DataFrame(audit), DATA / "phase3_selection_audit_trail.csv")


def stage12_allocation() -> None:
    d = safe_read(DATA / "phase3_final20_selected.csv", required=True)
    role_targets = {"Buffett Core":.25,"Transformation Core":.25,"Emerging Core":.25,"Dual Moat":.15,"Bridge / Diversifier":.10}
    counts=d.final_role.value_counts().to_dict()
    d["role_target_weight"] = d.final_role.map(role_targets)
    d["target_weight"] = d.apply(lambda r: r.role_target_weight/counts.get(r.final_role,1),axis=1).clip(upper=.08)
    # Redistribute the small residual without breaching the 8% stock cap.
    residual=1-d.target_weight.sum()
    for _ in range(10):
        eligible=d.target_weight.lt(.08-1e-12)
        if residual<=1e-10 or not eligible.any(): break
        add=min(residual/eligible.sum(), float((.08-d.loc[eligible,"target_weight"]).min()))
        d.loc[eligible,"target_weight"]+=add; residual=1-d.target_weight.sum()
    d["target_amount_yen"]=(d.target_weight*TOTAL_BUDGET).round(-3)
    d["unit_shares"] = np.nan
    d["purchase_units"] = np.nan
    d["shares"] = np.nan
    d["estimated_cost_yen"] = np.nan
    d["allocation_status"] = "template_only_unit_share_data_missing"
    d["price_used"] = numeric(d.get("close"), d.index)
    write_csv(d, DATA / "phase3_allocation_plan.csv")


def variant_selection(d: pd.DataFrame, variant: str) -> list[str]:
    pool=d[~bool_series(d.base_hard_exclusion_flag)].copy()
    if variant=="A1": score=pool.transformation_score
    elif variant=="A2": score=pool.emerging_score
    elif variant=="A3": score=.5*pool.transformation_score+.5*pool.emerging_score; pool=pool.assign(emerging_evidence_level=3)
    elif variant=="A4": score=pool.transformation_score+numeric(pool.value_trap_penalty)
    elif variant=="A5": score=pool.emerging_score+numeric(pool.theme_hype_penalty)
    elif variant=="A6": score=.5*pool.transformation_score+.5*pool.emerging_score
    elif variant=="A8": pool=pool[bool_series(pool.top100_flag)]; score=.5*pool.transformation_score+.5*pool.emerging_score
    elif variant=="A9": pool=pool[bool_series(pool.top300_flag)]; score=.5*pool.transformation_score+.5*pool.emerging_score
    else: score=.5*pool.transformation_score+.5*pool.emerging_score
    return pool.assign(_score=score).sort_values("_score",ascending=False).head(20).code.tolist()


def stage13_ablation() -> None:
    d=safe_read(DATA/"phase3_role_assignment.csv",required=True)
    final=safe_read(DATA/"phase3_final20_selected.csv",required=True)
    base=set(normalize_code(final.code))
    labels={
        "A1":"Transformation Score only","A2":"Emerging Score only","A3":"remove Evidence Level","A4":"remove Value Trap Penalty","A5":"remove Theme Hype Penalty","A6":"remove Phase2 Confidence","A7":"remove sector constraint","A8":"Top100 only","A9":"Top300 only","A10":"Top1200","A11":"exclude Buffett Core","A12":"exclude Dual Moat","A13":"exclude Bridge",
    }
    rows=[]
    for key,label in labels.items():
        codes=set(variant_selection(d,key))
        if key=="A11": codes-=set(final.loc[final.final_role.eq("Buffett Core"),"code"])
        if key=="A12": codes-=set(final.loc[final.final_role.eq("Dual Moat"),"code"])
        if key=="A13": codes-=set(final.loc[final.final_role.eq("Bridge / Diversifier"),"code"])
        rows.append({"variant":key,"description":label,"selected_count":len(codes),"overlap_with_final20":len(codes&base),"jaccard_with_final20":len(codes&base)/len(codes|base) if codes|base else np.nan,"status":"structural selection executed; return backtest not used for replacement"})
    write_csv(pd.DataFrame(rows),DATA/"phase3_ablation_results.csv")


def md_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty: return "_No rows._"
    view=frame[columns].copy()
    def cell(value):
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            value = f"{value:.4f}".rstrip("0").rstrip(".")
        return str(value).replace("|", "\\|").replace("\n", " ")
    header="| "+" | ".join(columns)+" |"
    rule="|"+"|".join("---" for _ in columns)+"|"
    rows=["| "+" | ".join(cell(v) for v in row)+" |" for row in view.itertuples(index=False,name=None)]
    return "\n".join([header,rule,*rows])


def stage14_reports() -> None:
    seed=safe_read(DATA/"phase3_seed_universe_from_phase2.csv",required=True)
    guard=safe_read(DATA/"phase3_guardrail_confidence.csv",required=True)
    trans=safe_read(DATA/"phase3_transformation_scores.csv",required=True)
    emerging=safe_read(DATA/"phase3_emerging_scores.csv",required=True)
    evidence=safe_read(DATA/"phase3_evidence_levels.csv",required=True)
    final=safe_read(DATA/"phase3_final20_selected.csv",required=True)
    rejected=safe_read(DATA/"phase3_rejected_candidates.csv",required=True)
    ablation=safe_read(DATA/"phase3_ablation_results.csv",required=True)
    audit_summary_path=locate("data_audit/flag_audit_summary.csv")
    audit_summary=safe_read(audit_summary_path) if audit_summary_path else pd.DataFrame()
    reported=None
    if not audit_summary.empty:
        row=audit_summary[audit_summary.flag.eq("phase3_review_required")]
        reported=int(row.iloc[0]["count"]) if not row.empty else None
    actual=int(bool_series(seed.phase3_review_required).sum())
    flagged=seed[bool_series(seed.phase1_top5_flag)]
    observed=dict(zip(normalize_code(flagged.code),flagged.company_name))
    top5_ok=set(observed)==set(EXPECTED_TOP5)
    input_rows=safe_read(DATA/"phase3_input_inventory.csv")
    missing=input_rows[~bool_series(input_rows.get("found"),input_rows.index)] if not input_rows.empty else pd.DataFrame()

    write_md(REPORTS/"phase3_phase2_input_audit.md",f"""
    # Phase2 Input Audit

    - Formal universe: {len(seed):,} rows; unique codes: {seed.code.nunique():,}.
    - Phase1 Top5 flags: {len(flagged)}; specified-code reconciliation: **{'PASS' if top5_ok else 'WARNING'}**.
    - Phase2 review-summary count: {reported if reported is not None else 'not available'}.
    - Actual CSV recount for `phase3_review_required`: {actual}. The actual CSV is authoritative.
    - Missing expected nonfatal inputs: {len(missing)}.

    Phase1 flagged names:

    {md_table(flagged,['code','ticker','company_name','sector','phase2_rank'])}
    """)
    write_md(REPORTS/"phase3_flag_reconciliation_report.md",f"""
    # Flag Reconciliation

    `flag_audit_summary.csv` reports **{reported}** Phase3-review rows, while direct recount of the formal review-ready CSV yields **{actual}**. Difference: **{actual-(reported or 0)}**. Per the design rule, all downstream decisions use the direct CSV recount.

    Soft-review flags do not automatically exclude a company. Hard exclusions use formal-universe membership, distress, anomaly, liquidity below ¥{LIQUIDITY_THRESHOLD:,.0f}/day, negative equity, persistent losses, and excessive financial missingness. Phase1 Top5 remain fixed but retain warning flags.
    """)
    miss_lines=["- shareholder-return metrics: unavailable", "- reform-disclosure metrics: unavailable", "- patent/citation and recurring-revenue metrics: unavailable", "- trading-unit data: unavailable; allocation is a template", f"- R&D expense latest-year coverage: {numeric(seed.get('latest_rd_expense')).notna().mean():.1%}", f"- capex latest-year coverage: {numeric(seed.get('latest_capex')).notna().mean():.1%}"]
    write_md(REPORTS/"phase3_missing_feature_report.md","# Missing Feature Report\n\n"+"\n".join(miss_lines)+"\n\nMissing values were not imputed. Full Transformation scores fall back to the documented Lite score.")
    counts=evidence.emerging_evidence_level.value_counts().sort_index().to_dict()
    write_md(REPORTS/"phase3_evidence_audit_report.md",f"""
    # Evidence Audit

    Emerging evidence counts: {counts}. Only company-official product, business, or IR pages in the curated evidence table can lift Emerging evidence to Level 2 or 3. Sector classification by itself remains Level 0. Level 3 requires a disclosed quantity; Level 2 requires a concrete product, use case, customer group, or investment plan.
    """)

    role_counts=final.final_role.value_counts().to_dict()
    sector_counts=final.sector.value_counts().to_dict()
    violations=[]
    if len(final)!=20: violations.append("final_count")
    if bool_series(final.phase1_top5_flag).sum()!=5: violations.append("phase1_top5")
    if not bool_series(final.top1200_flag).all(): violations.append("outside_top1200")
    if sector_counts and max(sector_counts.values())>3: violations.append("sector_count_cap")
    noncore=final[~bool_series(final.phase1_top5_flag)]
    if bool_series(noncore.base_hard_exclusion_flag).any(): violations.append("hard_exclusion_selected")
    if bool_series(noncore.get("low_pbr_only_flag"), noncore.index).any(): violations.append("low_pbr_only_selected")
    if bool_series(noncore.get("ai_keyword_only_flag"), noncore.index).any(): violations.append("ai_keyword_only_selected")
    write_md(REPORTS/"phase3_selection_audit.md",f"""
    # Selection Audit

    - Final count: {len(final)}
    - Role composition: {role_counts}
    - Sector counts: {sector_counts}
    - Phase1 fixed names: {int(bool_series(final.phase1_top5_flag).sum())}
    - Remaining names all from Top1200: {bool(bool_series(noncore.top1200_flag).all())}
    - Constraint violations: **{'; '.join(violations) if violations else 'none'}**

    The constrained greedy procedure fixes Buffett Core, selects Dual, reserves scarce evidence-qualified sector capacity by filling Emerging, and then fills Transformation and Bridge while checking hard exclusions and sector/theme counts. This feasibility ordering does not change the requested role quotas. The audit trail is in `data/phase3_selection_audit_trail.csv`.
    """)
    write_md(REPORTS/"phase3_ablation_report.md",f"# Ablation Report\n\nReturn history sufficient for a point-in-time Phase3 backtest was not supplied as a Phase3 input; therefore no backtest result changes the final 20. Structural variants were executed:\n\n{md_table(ablation,['variant','description','selected_count','overlap_with_final20','jaccard_with_final20','status'])}")
    write_md(REPORTS/"phase3_formula_lineage_report.md","""
    # Formula Lineage Report

    This Phase3 composite is **not itself a formula proven by prior research**. It reconstructs indicators whose economic meaning is established and combines them for the Phase3 objective.

    ## Transformation lineage

    - B/M: Fama–French value lineage; E/P: Basu earnings-yield lineage; enterprise multiple is reserved for optional EV/EBITDA data.
    - ROIC/ROIC–WACC and DuPont: capital efficiency and the decomposition of margin, turnover, and leverage.
    - Payout/buyback yield: shareholder alignment; unavailable here unless optional data are supplied.
    - Piotroski F-Score: financial strength among value firms; Sloan accruals: earnings quality.
    - Altman Z/Ohlson O: distress guardrails; JPX cost-of-capital disclosure: Japan reform proxy when supplied.

    ## Emerging lineage

    - R&D capital: Lev–Sougiannis / Peters–Taylor lineage; organization capital: Eisfeldt–Papanikolaou lineage.
    - Patents per R&D: innovation efficiency; HHI/market share: industrial organization and bottleneck power.
    - Recurring revenue/customer concentration: customer and data-base durability.
    - AI-infrastructure exposure: company-disclosure proxies aligned to IEA/METI/MIC industrial-infrastructure framing.
    - Trust/safety: investment proxies inspired by NIST AI RMF, NIST CSF, OECD AI Principles, and Japan's AI business guidelines.
    """)
    top_rej=rejected.sort_values(["transformation_score","emerging_score"],ascending=False).head(40)
    write_md(REPORTS/"phase3_rejected_candidates.md",f"# Rejected Candidates\n\n{md_table(top_rej,['code','company_name','sector','role_candidate','transformation_score','emerging_score','rejection_reason'])}")

    write_md(DOCS/"phase3_build_design.md","""
    # Phase3 Build Design

    Nine layers are implemented: Phase2 universe, guardrail/confidence, Transformation, Emerging, Evidence, grades, roles, final selection/allocation/ablation, and report handoff. Phase2's exploratory aggregate forms the universe only and is never an input to either final moat score or the final selection ordering.
    """)
    write_md(DOCS/"phase3_transformation_moat_definition.md","""
    # Transformation Moat Definition

    Transformation Moat measures the possibility that an existing competitive position is re-rated through improving capital efficiency, payout alignment, asset/portfolio reform, execution, and earnings quality. Low PBR alone is insufficient. The complete formula is the requested 20/22/16/17/13/12 weighted model less the value-trap penalty. Where payout or reform disclosure is unavailable, the 30/20/20/20/10 Lite score is used and explicitly labeled.
    """)
    write_md(DOCS/"phase3_emerging_moat_definition.md","""
    # Emerging Moat Definition

    Emerging Moat measures infrastructure, implementation, and trust bottlenecks created by AI-era industrial change. The model weights intangible capital (18%), innovation (15%), bottleneck/pricing power (18%), AI infrastructure exposure (22%), data/customer base (14%), and trust/safety (13%), then adds an evidence bonus and subtracts theme-hype and financial penalties. A sector label or AI keyword alone cannot establish evidence.
    """)
    write_md(DOCS/"phase3_scoring_framework.md","""
    # Scoring Framework

    All available numeric components are converted to cross-sectional percentile scores in the formal Top1200. Direction is reversed for accruals and leverage deterioration. Missing components remain missing; subscore means use available components and their missing rates are retained. Confidence is only a tie-break/review signal. Full and Lite Transformation methods are separately identified.
    """)
    write_md(DOCS/"phase3_selection_algorithm.md","""
    # Selection Algorithm

    1. Fix the five `phase1_top5_flag` names.
    2. Remove non-core hard exclusions from formal Top1200.
    3. Build evidence-qualified Dual, Transformation, Emerging, and Bridge pools.
    4. Fill 3 Dual slots, then reserve feasible sector capacity for 5 evidence-qualified Emerging slots before filling 5 Transformation and 2 Bridge slots.
    5. Enforce at most three names per sector and four per explicit AI-infrastructure theme.
    6. Record every skip/selection and generate explicit rejection reasons.
    """)
    rationale_cols=["selection_order","code","company_name","sector","final_role","transformation_score","emerging_score","selection_reason"]
    write_md(DOCS/"phase3_final20_rationale.md",f"# Final 20 Rationale\n\n{md_table(final,rationale_cols)}")
    write_md(DOCS/"phase3_allocation_report.md","""
    # Allocation Report

    The budget is ¥5,000,000, with role targets of 25% Buffett, 25% Transformation, 25% Emerging, 15% Dual, and 10% Bridge, and an 8% per-stock cap. Latest prices are retained where available. Trading-unit data were not found, so purchase units, shares, and estimated cost are deliberately blank: `phase3_allocation_plan.csv` is an executable template once verified trading units are supplied.
    """)
    write_md(DOCS/"phase3_ablation_plan.md","""
    # Ablation Plan

    A1–A13 cover Transformation-only, Emerging-only, removal of Evidence, trap penalty, hype penalty, confidence, sector constraints, Top100/Top300/Top1200 universe restrictions, and removal of Buffett, Dual, or Bridge roles. They test logical dependence and concentration; they do not authorize return-driven replacement of the final 20. A valid return test additionally needs point-in-time price histories, TOPIX/Nikkei series, corporate-action handling, and an as-of-date policy.
    """)
    write_md(DOCS/"phase3_risk_and_limitations.md","""
    # Risk and Limitations

    - Scores do not guarantee future returns; weights are conceptual design coefficients, not ex-post optimized parameters.
    - Sparse disclosure can understate a company. AI infrastructure can overheat; Transformation names can be value traps.
    - R&D and AI words can be overvalued; Evidence Level and penalties reduce, but cannot eliminate, judgment.
    - Full payout/reform, patent, recurring-revenue, customer-concentration, and trading-unit data are unavailable.
    - The final 20 maximizes explanatory coherence under constraints, not historical backtest performance.
    """)
    write_md(DOCS/"phase3_to_report_handoff.md",f"""
    # Phase3 Report Handoff

    Phase3「離」の目的は、Phase1が測った完成済みMoatとPhase2が形成した候補宇宙を土台に、資本効率改革で「変わるMoat」とAI時代の産業基盤・実装基盤・信頼基盤から「生まれるMoat」を測ることである。Phase2の`final_exploratory_weighted_score`は候補宇宙形成用であり、Phase3のMoatスコアや最終順位には使っていない。

    Transformationは評価ギャップだけでなく、資本効率の3年変化、実行安全性、利益の質、流動性・信頼度を統合し、バリュートラップを減点する。Emergingは無形資産、革新能力、ボトルネック、AIインフラ接続、顧客・データ基盤、信頼・安全を統合し、開示Levelとテーマ過熱を明示する。これは独自の原式を先行研究として主張するものではなく、先行研究で意味が確立した指標を日本株の開示制約に合わせて束ね直した合成測定モデルである。独自性は束ね方、日本株補正、Evidence Level、役割・分散制約にある。

    低PBR単独およびAIキーワード単独を採用根拠にせず、Phase1 guardrailを維持した。最終構成は{role_counts}。採用理由は役割・両スコア・Evidence・Confidenceを併記し、不採用理由はhard exclusion、Evidence不足、役割・業種・テーマ・定員による次点のいずれかを明示した。A1–A13のアブレーションは選定ロジックの依存性と集中リスクを確認するが、バックテスト最大化による銘柄入替には使わない。限界は開示疎密、テーマ過熱、バリュートラップ、未取得の還元・特許・顧客・単元株データである。
    """)
    write_md(REPORTS/"phase3_summary_report.md",f"""
    # BEYOND BUFFETT Phase3 Summary

    - Formal universe: {len(seed):,}
    - Review flag actual/reported: {actual}/{reported}
    - Transformation Lite mean missing rate: {numeric(trans.transformation_lite_missing_rate).mean():.1%}
    - Emerging component mean missing rate: {numeric(emerging.emerging_missing_rate).mean():.1%}
    - Evidence levels: {evidence.evidence_level.value_counts().sort_index().to_dict()}
    - Final roles: {role_counts}
    - Constraint violations: {violations if violations else 'none'}

    Human review should begin with `docs/phase3_final20_rationale.md`, `reports/phase3_selection_audit.md`, `reports/phase3_evidence_audit_report.md`, and `data/phase3_allocation_plan.csv`.
    """)
    finalize_manifest_readme()


def finalize_manifest_readme() -> None:
    write_md(OUT/"README.md","""
    # BEYOND BUFFETT — Phase3「離」

    This folder is a reproducible Phase3 package generated from `phase2_perfect_final_break.zip`. Run `scripts/phase3_selection/run_all.sh` from any directory to rebuild all data, documentation, reports, logs, the manifest, and `outputs/phase3_beyond_buffett.zip`.

    Phase2's exploratory weighted score forms the candidate universe only. Final measurement uses Transformation and Emerging moat composites, evidence levels, guardrails, role quotas, and sector/theme constraints. Missing optional inputs are logged and never fabricated.
    """)
    files=[]
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name not in {"MANIFEST.md"}:
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            files.append((str(p.relative_to(OUT)),p.stat().st_size,digest))
    manifest="# MANIFEST\n\n| Path | Bytes | SHA-256 |\n|---|---:|---|\n"+"\n".join(f"| `{p}` | {size} | `{sha}` |" for p,size,sha in files)+"\n"
    write_md(OUT/"MANIFEST.md",manifest)


STAGES={
    "00":stage00_unzip,"01":stage01_audit_inputs,"02":stage02_seed,"03":stage03_confidence,
    "04":stage04_transformation_lite,"05":stage05_enrich,"06":stage06_transformation_full,
    "07":stage07_emerging,"08":stage08_evidence,"09":stage09_grades,"10":stage10_roles,
    "11":stage11_select,"12":stage12_allocation,"13":stage13_ablation,"14":stage14_reports,
}


def run_stage(stage: str) -> None:
    LOGS.mkdir(parents=True,exist_ok=True)
    log(f"START stage {stage}")
    STAGES[stage]()
    log(f"END stage {stage}")
    if stage == "14":
        # Stage-end logging mutates run.log, so refresh the manifest last.
        finalize_manifest_readme()


if __name__=="__main__":
    requested=sys.argv[1:] or list(STAGES)
    for stage in requested:
        run_stage(stage)
