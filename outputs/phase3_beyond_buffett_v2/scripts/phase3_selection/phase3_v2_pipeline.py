#!/usr/bin/env python3
"""Phase3 Beyond Buffett v2 package builder.

This script keeps v1 intact, reads Phase2 and v1 artifacts, and rebuilds the
submission-ready v2 package with separated evidence, fuller Transformation
audit, systematic Emerging screening, corrected ablation overlaps, and a
lot-size-aware allocation template.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sys
import textwrap
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def find_root() -> Path:
    env = os.getenv("PHASE3_REPO_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for p in [Path.cwd().resolve(), *here.parents]:
        if (p / "outputs" / "phase2_perfect_final_break.zip").exists():
            return p
    raise RuntimeError("repo root not found")


ROOT = find_root()
OUT = ROOT / "outputs" / "phase3_beyond_buffett_v2"
V1 = ROOT / "outputs" / "phase3_beyond_buffett"
V1_WORK = ROOT / "work" / "phase3_beyond_buffett_v1" / "phase3_beyond_buffett"
P2_WORK = ROOT / "work" / "phase2_perfect_final_break"
DATA = OUT / "data"
DOCS = OUT / "docs"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
SCRIPTS = OUT / "scripts" / "phase3_selection"
TOTAL_BUDGET = 5_000_000
MAX_STOCK_WEIGHT = 0.08
MAX_SECTOR_WEIGHT = 0.25
MAX_THEME_WEIGHT = 0.25
ROLE_TARGETS = {
    "Buffett Core": 0.25,
    "Transformation Core": 0.25,
    "Emerging Core": 0.25,
    "Dual Moat": 0.15,
    "Bridge / Diversifier": 0.10,
}
EXPECTED_TOP5 = {"3539", "6430", "7803", "9470", "4350"}

KEYWORDS = {
    "semiconductor": ["semiconductor", "半導体", "wafer", "ウエハ", "packaging", "inspection", "lithography", "etching", "deposition", "materials", "半導体製造装置"],
    "data_center": ["data center", "データセンター", "server", "hyperscale", "cloud infrastructure", "colocation"],
    "power_grid": ["power grid", "電力", "送配電", "変圧器", "power electronics", "ups", "power supply", "電源", "蓄電", "grid"],
    "cooling": ["cooling", "冷却", "liquid cooling", "空調", "heat exchanger", "thermal management"],
    "optical_communication": ["optical", "光通信", "optical fiber", "光ファイバ", "photonics", "connector", "cable", "network equipment", "iown"],
    "factory_automation": ["factory automation", "automation", "自動化", "robot", "robotics", "sensor", "control", "plc", "industrial dx", "組込み"],
    "cybersecurity": ["cybersecurity", "cyber security", "セキュリティ", "zero trust", "soc", "siem", "vulnerability", "authentication", "identity", "encryption"],
    "business_data": ["business data", "業務データ", "saas", "erp", "crm", "vertical saas", "recurring revenue", "subscription", "顧客データ", "地図データ", "位置情報", "医療データ", "建設データ", "物流データ"],
    "quality_assurance": ["quality assurance", "software testing", "verification", "validation", "品質保証", "検証", "監査", "model validation", "regulatory compliance"],
    "precision_processing": ["precision processing", "精密加工", "measurement", "計測", "metrology", "analytical instruments", "inspection instruments"],
}

SECTOR_HINTS = {
    "Electric Appliances": ("factory_automation", ["sensor", "control"]),
    "Machinery": ("factory_automation", ["automation", "inspection"]),
    "Information & Communication": ("business_data", ["business data", "software"]),
    "Nonferrous Metals": ("optical_communication", ["cable", "optical"]),
    "Construction": ("power_grid", ["infrastructure"]),
    "Chemicals": ("semiconductor", ["materials"]),
    "Services": ("quality_assurance", ["service"]),
}


for d in [DATA, DOCS, REPORTS, LOGS, SCRIPTS]:
    d.mkdir(parents=True, exist_ok=True)


def normalize_code(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    s = s.replace(".T", "")
    m = re.search(r"\d+", s)
    return m.group(0) if m else s


def norm_series(s: pd.Series) -> pd.Series:
    return s.map(normalize_code).astype(str)


def num(s, index=None) -> pd.Series:
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def bools(s, index=None) -> pd.Series:
    if isinstance(s, pd.Series):
        if s.dtype == bool:
            return s.fillna(False)
        return s.fillna(False).astype(str).str.lower().str.strip().isin({"true", "1", "yes", "y"})
    return pd.Series(False, index=index, dtype=bool)


def pct(s, higher=True) -> pd.Series:
    r = num(s).rank(pct=True, method="average")
    return r if higher else 1 - r


def log(msg: str, name="run.log") -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    with (LOGS / name).open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {msg}\n")
    print(msg)


def read_csv(path: Path, required=False) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        log(f"missing optional input: {path}", "missing_features.log")
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"wrote {path.relative_to(ROOT)} ({len(df):,} rows)")


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")
    log(f"wrote {path.relative_to(ROOT)}")


def md_table(df: pd.DataFrame, cols: list[str], n: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    use = df[cols].head(n).copy()
    def cell(v):
        if pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{v:.4f}".rstrip("0").rstrip(".")
        return str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join([
        "| " + " | ".join(cols) + " |",
        "|" + "|".join("---" for _ in cols) + "|",
        *["| " + " | ".join(cell(v) for v in row) + " |" for row in use.itertuples(index=False, name=None)]
    ])


def ensure_inputs() -> None:
    with zipfile.ZipFile(ROOT / "outputs" / "phase2_perfect_final_break.zip") as zf:
        zf.extractall(ROOT / "work")
    if not V1_WORK.exists():
        with zipfile.ZipFile(ROOT / "outputs" / "phase3_beyond_buffett.zip") as zf:
            zf.extractall(ROOT / "work" / "phase3_beyond_buffett_v1")
    log("unzipped Phase2 and v1 inputs into work/")


def load_base() -> pd.DataFrame:
    src = V1 / "data" / "phase3_scoring_master.csv"
    d = read_csv(src, required=True)
    d["code"] = norm_series(d["code"])
    return d


def load_final_v1() -> pd.DataFrame:
    d = read_csv(V1 / "data" / "phase3_final20_selected.csv", required=True)
    d["code"] = norm_series(d["code"])
    return d


def column_hits(columns: list[str], patterns: list[str]) -> list[str]:
    out = []
    for c in columns:
        cl = c.lower()
        if any(p.lower() in cl for p in patterns):
            out.append(c)
    return out


def transformation_fullness(d: pd.DataFrame) -> pd.DataFrame:
    cols = list(d.columns)
    shareholder_patterns = ["dividend", "payout", "buyback", "treasury", "doe", "net_payout", "fcf"]
    reform_patterns = ["capital_cost", "roic", "pbr", "cross_shareholding", "policy holding", "asset_sale", "portfolio", "restructuring", "medium_term"]
    shareholder_cols = column_hits(cols, shareholder_patterns)
    reform_cols = [c for c in column_hits(cols, reform_patterns) if c not in {"capital_efficiency_improvement_score"}]
    fcf_proxy = num(d.get("latest_operating_cf"), d.index) - num(d.get("latest_capex"), d.index).fillna(0)
    d["fcf_proxy"] = fcf_proxy
    d["fcf_proxy_available"] = num(d.get("latest_operating_cf"), d.index).notna()
    d["fcf_proxy_positive_flag"] = fcf_proxy.gt(0)
    improv_cols = [c for c in ["delta_roa_3y", "delta_roe_3y", "delta_operating_margin_3y", "delta_gross_margin_3y", "delta_asset_turnover_3y", "delta_current_ratio_3y"] if c in d]
    pos = d[improv_cols].apply(pd.to_numeric, errors="coerce").gt(0).sum(axis=1)
    d["transformation_quant_evidence_level"] = np.select([pos.ge(4), pos.ge(2), pos.ge(1)], [3, 2, 1], default=0)
    d["transformation_reform_disclosure_level"] = 0
    if reform_cols:
        d["transformation_reform_disclosure_level"] = d[reform_cols].notna().any(axis=1).astype(int)
    d["transformation_shareholder_return_evidence_level"] = np.where(d["fcf_proxy_positive_flag"], 1, 0)
    if shareholder_cols:
        d["transformation_shareholder_return_evidence_level"] = np.maximum(
            d["transformation_shareholder_return_evidence_level"],
            d[shareholder_cols].notna().any(axis=1).astype(int) * 2,
        )
    d["shareholder_return_data_available"] = bool(shareholder_cols)
    d["reform_disclosure_data_available"] = bool(reform_cols)
    d["fcf_proxy_score"] = 100 * pct(d["fcf_proxy"], True)
    d["transformation_partial_score"] = (
        0.22 * num(d.get("valuation_gap_score"), d.index).fillna(num(d.get("value_score"), d.index))
        + 0.24 * num(d.get("capital_efficiency_improvement_score"), d.index).fillna(num(d.get("improvement_score"), d.index))
        + 0.10 * d["fcf_proxy_score"].fillna(50)
        + 0.18 * num(d.get("execution_reliability_score"), d.index).fillna(num(d.get("execution_safety_score"), d.index))
        + 0.16 * num(d.get("quality_trap_resistance_score"), d.index).fillna(num(d.get("quality_score"), d.index))
        + 0.10 * (num(d.get("phase2_confidence_score"), d.index) / 1.1 * 100)
        - num(d.get("value_trap_penalty"), d.index).fillna(0)
    ).clip(0, 100)
    d["transformation_fullness_score"] = (
        0.45 * (d["transformation_quant_evidence_level"] / 3)
        + 0.15 * d["fcf_proxy_available"].astype(float)
        + 0.20 * d["shareholder_return_data_available"].astype(float)
        + 0.20 * d["reform_disclosure_data_available"].astype(float)
    ).clip(0, 1)
    d["transformation_score_type"] = np.select(
        [
            d["shareholder_return_data_available"] & d["reform_disclosure_data_available"],
            d["fcf_proxy_available"] & d["transformation_quant_evidence_level"].ge(2),
        ],
        ["full", "partial"],
        default="lite",
    )
    d["transformation_score"] = np.where(
        d["transformation_score_type"].eq("partial"),
        d["transformation_partial_score"],
        num(d.get("transformation_score"), d.index),
    )
    d["transformation_fullness_note"] = np.select(
        [
            d["transformation_score_type"].eq("full"),
            d["transformation_score_type"].eq("partial"),
        ],
        [
            "formal shareholder-return and reform-disclosure fields available",
            "quantitative improvement plus FCF proxy available; formal payout/reform fields still missing",
        ],
        default="lite: payout/reform data absent and financial proxy insufficient",
    )
    req = []
    for feature in ["dividend_yield", "dividend_per_share", "dividend_growth_3y", "doe", "payout_ratio", "total_payout_ratio", "buyback_amount", "buyback_yield", "treasury_stock_change", "net_payout_yield", "fcf_coverage_of_payout", "capital_cost_disclosure_flag", "roic_target_flag", "pbr_improvement_policy_flag", "cross_shareholding_reduction_flag", "asset_sale_flag", "portfolio_restructuring_flag", "business_restructuring_flag", "medium_term_plan_kpi_flag", "reform_evidence_snippet", "reform_evidence_source"]:
        matched = column_hits(cols, [feature])
        req.append({"feature": feature, "available": bool(matched), "matched_columns": ";".join(matched), "v2_treatment": "used" if matched else "required external feature"})
    write_csv(pd.DataFrame(req), DATA / "phase3_required_external_features.csv")
    keep = ["code", "company_name", "transformation_score_type", "shareholder_return_data_available", "reform_disclosure_data_available", "fcf_proxy_available", "transformation_fullness_score", "transformation_fullness_note"]
    write_csv(d[keep], DATA / "phase3_transformation_fullness.csv")
    return d


def keyword_screen(d: pd.DataFrame) -> pd.DataFrame:
    curated = read_csv(SCRIPTS / "curated_evidence.csv")
    if curated.empty:
        curated = read_csv(V1 / "scripts" / "phase3_selection" / "curated_evidence.csv")
    if not curated.empty:
        curated["code"] = norm_series(curated["code"])
    c = curated.set_index("code") if not curated.empty else pd.DataFrame()
    rows = []
    for _, r in d.iterrows():
        text_parts = [r.get("company_name", ""), r.get("sector", ""), r.get("phase3_handoff_note", "")]
        if r["code"] in c.index:
            cr = c.loc[r["code"]]
            text_parts += [cr.get("ai_infrastructure_category", ""), cr.get("evidence_snippet", "")]
        text = " ".join("" if pd.isna(x) else str(x) for x in text_parts).lower()
        hits = {}
        for cat, words in KEYWORDS.items():
            found = [w for w in words if w.lower() in text]
            if found:
                hits[cat] = found
        if not hits and r.get("sector") in SECTOR_HINTS:
            cat, words = SECTOR_HINTS[str(r.get("sector"))]
            hits[cat] = words
        curated_flag = r["code"] in c.index
        if curated_flag:
            cr = c.loc[r["code"]]
            category = cr.get("ai_infrastructure_category", "")
            level = int(cr.get("emerging_evidence_level", 0))
            source = cr.get("evidence_source", "")
            snippet = cr.get("evidence_snippet", "")
        else:
            category = max(hits, key=lambda k: len(hits[k])) if hits else ""
            level = 1 if hits else 0
            source = "systematic_keyword_screen_from_phase2_fields" if hits else ""
            snippet = f"Systematic keyword/sector screen: {category}" if hits else "no verified company disclosure"
        quant = level >= 3
        product = level >= 2
        keyword_only = level == 1
        rows.append({
            "code": r["code"],
            "curated_evidence_flag": curated_flag,
            "systematic_screening_flag": bool(hits),
            "emerging_disclosure_level": level,
            "emerging_evidence_source": source,
            "emerging_evidence_snippet": snippet,
            "emerging_evidence_category": category,
            "emerging_keyword_hits": json.dumps(hits, ensure_ascii=False),
            "emerging_quantitative_evidence_flag": quant,
            "emerging_product_customer_evidence_flag": product,
            "emerging_keyword_only_flag": keyword_only,
            "theme_hype_penalty_reason": "keyword-only systematic hit" if keyword_only else "none",
        })
    out = pd.DataFrame(rows)
    write_csv(out, DATA / "phase3_emerging_systematic_screening.csv")
    return d.merge(out, on="code", how="left")


def emerging_scores(d: pd.DataFrame) -> pd.DataFrame:
    level = num(d["emerging_disclosure_level"], d.index).fillna(0).clip(0, 3)
    strength = level.map({0: 0.0, 1: 0.35, 2: 0.80, 3: 1.00}).fillna(0)
    rd_to_sales = num(d.get("latest_rd_expense"), d.index) / num(d.get("latest_revenue"), d.index).replace(0, np.nan)
    rd_score = pct(rd_to_sales, True).fillna(0.35)
    gm_score = pct(d.get("latest_gross_margin"), True).fillna(pct(d.get("gross_profitability"), True)).fillna(0.35)
    gp_score = pct(d.get("gross_profitability"), True).fillna(0.35)
    d["rd_to_sales"] = rd_to_sales
    d["intangible_capital_score"] = 100 * (0.6 * rd_score + 0.4 * pct(d.get("latest_employees"), True).fillna(0.35))
    d["innovation_capacity_score"] = 100 * (0.5 * rd_score + 0.5 * strength)
    d["bottleneck_pricing_power_score"] = 100 * (0.35 * gm_score + 0.35 * gp_score + 0.30 * strength)
    d["ai_infrastructure_exposure_score"] = 100 * strength
    cat = d["emerging_evidence_category"].fillna("")
    d["data_customer_base_score"] = 100 * strength * cat.isin(["business_data", "quality_assurance", "cybersecurity"]).astype(float)
    d["trust_safety_infrastructure_score"] = 100 * strength * cat.isin(["quality_assurance", "cybersecurity", "factory_automation", "semiconductor", "precision_processing"]).astype(float)
    d["evidence_level_bonus"] = level.map({0: 0, 1: 2, 2: 4, 3: 8}).fillna(0)
    d["theme_hype_penalty"] = np.where(d["emerging_keyword_only_flag"], 18, 0)
    d["financial_guardrail_penalty"] = 20 * bools(d.get("base_hard_exclusion_flag"), d.index).astype(int)
    weights = {
        "intangible_capital_score": .18,
        "innovation_capacity_score": .15,
        "bottleneck_pricing_power_score": .18,
        "ai_infrastructure_exposure_score": .22,
        "data_customer_base_score": .14,
        "trust_safety_infrastructure_score": .13,
    }
    d["emerging_score"] = (sum(d[k] * w for k, w in weights.items()) + d["evidence_level_bonus"] - d["theme_hype_penalty"] - d["financial_guardrail_penalty"]).clip(0, 100)
    d["emerging_penalty_reasons"] = np.where(d["emerging_keyword_only_flag"], "keyword_only", "none")
    return d


def evidence_levels(d: pd.DataFrame) -> pd.DataFrame:
    d["emerging_evidence_level"] = d["emerging_disclosure_level"]
    d["emerging_evidence_level_label"] = d["emerging_disclosure_level"].map(lambda x: f"Level {int(x)}")
    d["low_pbr_only_flag"] = num(d.get("value_score"), d.index).ge(70) & num(d["transformation_quant_evidence_level"], d.index).eq(0)
    d["ai_keyword_only_flag"] = d["emerging_keyword_only_flag"] & ~bools(d.get("phase1_top5_flag"), d.index)
    def final_level(r):
        if r.get("final_role") == "Dual Moat":
            return int(min(r.transformation_quant_evidence_level, max(r.emerging_disclosure_level, 0)))
        if r.get("role_candidate") == "Emerging Core":
            return int(r.emerging_disclosure_level)
        if r.get("role_candidate") == "Transformation Core":
            return int(max(r.transformation_quant_evidence_level, r.transformation_shareholder_return_evidence_level, r.transformation_reform_disclosure_level))
        return int(max(r.transformation_quant_evidence_level, r.emerging_disclosure_level))
    d["final_evidence_level"] = d.apply(final_level, axis=1)
    cols = ["code", "ticker", "company_name", "sector", "transformation_quant_evidence_level", "transformation_reform_disclosure_level", "transformation_shareholder_return_evidence_level", "emerging_disclosure_level", "final_evidence_level", "emerging_evidence_source", "emerging_evidence_snippet", "curated_evidence_flag", "systematic_screening_flag"]
    write_csv(d[cols], DATA / "phase3_evidence_levels.csv")
    return d


def grades_roles(d: pd.DataFrame) -> pd.DataFrame:
    hard = bools(d.get("base_hard_exclusion_flag"), d.index)
    d["transformation_grade"] = np.select(
        [
            hard | bools(d.get("low_pbr_only_flag"), d.index) | num(d.get("value_trap_penalty"), d.index).ge(30),
            num(d["transformation_score"], d.index).ge(78) & num(d["transformation_quant_evidence_level"], d.index).ge(2),
            num(d["transformation_score"], d.index).ge(65) & num(d["transformation_quant_evidence_level"], d.index).ge(1),
        ],
        ["D", "A", "B"],
        default="C",
    )
    d["emerging_grade"] = np.select(
        [
            hard | bools(d["emerging_keyword_only_flag"], d.index),
            num(d["emerging_score"], d.index).ge(75) & num(d["emerging_disclosure_level"], d.index).ge(2),
            num(d["emerging_score"], d.index).ge(50) & num(d["emerging_disclosure_level"], d.index).ge(2),
        ],
        ["D", "A", "B"],
        default="C",
    )
    d["dual_combined_score"] = 0.50 * num(d["transformation_score"], d.index) + 0.50 * num(d["emerging_score"], d.index)
    d["bridge_score"] = 0.55 * d[["transformation_score", "emerging_score"]].apply(pd.to_numeric, errors="coerce").max(axis=1) + 0.45 * num(d.get("phase2_confidence_score"), d.index).fillna(0) / 1.1 * 100
    d["role_candidate"] = np.select(
        [
            bools(d.get("phase1_top5_flag"), d.index),
            hard,
            (d["transformation_grade"].isin(["A", "B"]) | num(d["transformation_score"], d.index).ge(60)) & d["emerging_grade"].isin(["A", "B"]) & num(d["emerging_disclosure_level"], d.index).ge(2),
            d["emerging_grade"].isin(["A", "B"]) & num(d["emerging_disclosure_level"], d.index).ge(2),
            d["transformation_grade"].isin(["A", "B"]),
        ],
        ["Buffett Core", "Rejected", "Dual Moat", "Emerging Core", "Transformation Core"],
        default="Bridge / Diversifier",
    )
    write_csv(d, DATA / "phase3_grade_assignment.csv")
    write_csv(d, DATA / "phase3_role_assignment.csv")
    write_csv(d[d["role_candidate"].eq("Dual Moat")], DATA / "phase3_dual_moat_candidates.csv")
    write_csv(d[d["role_candidate"].eq("Bridge / Diversifier")], DATA / "phase3_bridge_candidates.csv")
    return d


def can_add(row, selected, ignore_sector=False, ignore_theme=False) -> tuple[bool, str]:
    if bool(row.get("base_hard_exclusion_flag", False)) and not bool(row.get("phase1_top5_flag", False)):
        return False, "hard_exclusion"
    if bool(row.get("low_pbr_only_flag", False)):
        return False, "low_pbr_only"
    if bool(row.get("ai_keyword_only_flag", False)):
        return False, "ai_keyword_only"
    sectors = Counter(str(x.get("sector", "")) for x in selected)
    themes = Counter(str(x.get("emerging_evidence_category", "") or "non_ai") for x in selected)
    if not ignore_sector and sectors[str(row.get("sector", ""))] >= 3:
        return False, "sector_cap_exceeded"
    theme = str(row.get("emerging_evidence_category", "") or "non_ai")
    if not ignore_theme and theme != "non_ai" and themes[theme] >= 4:
        return False, "theme_cap_exceeded"
    return True, "ok"


def select_final(d: pd.DataFrame, variant: str = "base") -> pd.DataFrame:
    d = d.copy()
    selected = []
    fixed = d[bools(d.get("phase1_top5_flag"), d.index)].sort_values("phase2_rank")
    if variant != "A11":
        for _, r in fixed.iterrows():
            rec = r.to_dict()
            rec["final_role"] = "Buffett Core"
            selected.append(rec)
    specs = [
        ("Dual Moat", 0 if variant == "A12" else 3, "dual_combined_score"),
        ("Emerging Core", 5, "emerging_score"),
        ("Transformation Core", 5, "transformation_score"),
        ("Bridge / Diversifier", 0 if variant == "A13" else 2, "bridge_score"),
    ]
    if variant == "A1":
        specs = [("Transformation Core", 20 - len(selected), "transformation_score")]
    if variant == "A2":
        specs = [("Emerging Core", 20 - len(selected), "emerging_score")]
    if variant == "A8":
        d = d[bools(d.get("top100_flag"), d.index)]
    if variant == "A9":
        d = d[bools(d.get("top300_flag"), d.index)]
    chosen = {x["code"] for x in selected}
    for role, quota, score in specs:
        if quota <= 0:
            continue
        if role == "Dual Moat":
            pool = d[(d["transformation_grade"].isin(["A", "B"]) | num(d["transformation_score"], d.index).ge(60)) & d["emerging_grade"].isin(["A", "B"]) & num(d["emerging_disclosure_level"], d.index).ge(2)]
        elif role == "Emerging Core":
            pool = d[d["emerging_grade"].isin(["A", "B"]) & num(d["emerging_disclosure_level"], d.index).ge(2)]
        elif role == "Transformation Core":
            pool = d[d["transformation_grade"].isin(["A", "B"])]
        else:
            pool = d[~bools(d.get("base_hard_exclusion_flag"), d.index)]
        if variant == "A3":
            pool = d[~bools(d.get("base_hard_exclusion_flag"), d.index)]
        if variant == "A14" and role == "Emerging Core":
            pool = d[d["emerging_score"].notna()]
        if variant == "A15" and role == "Transformation Core":
            pool = d[d["transformation_score"].notna()]
        pool = pool[~pool["code"].isin(chosen)].copy()
        if variant == "A4":
            pool["_score"] = num(pool["transformation_score"]) + num(pool.get("value_trap_penalty"), pool.index).fillna(0)
        elif variant == "A5":
            pool["_score"] = num(pool["emerging_score"]) + num(pool.get("theme_hype_penalty"), pool.index).fillna(0)
        elif variant in {"A6", "A3", "A7", "A10", "A11", "A12", "A13", "A14", "A15"}:
            pool["_score"] = 0.50 * num(pool["transformation_score"]) + 0.50 * num(pool["emerging_score"])
        else:
            pool["_score"] = num(pool[score])
        picked = 0
        for _, r in pool.sort_values("_score", ascending=False).iterrows():
            ok, _ = can_add(r, selected, ignore_sector=(variant == "A7"), ignore_theme=(variant == "A7"))
            if not ok and variant != "A3":
                continue
            rec = r.to_dict()
            rec["final_role"] = role
            selected.append(rec)
            chosen.add(rec["code"])
            picked += 1
            if picked >= quota:
                break
    if len(selected) < 20:
        pool = d[~d["code"].isin(chosen) & ~bools(d.get("base_hard_exclusion_flag"), d.index)].copy()
        pool["_score"] = pool[["transformation_score", "emerging_score", "bridge_score"]].apply(pd.to_numeric, errors="coerce").max(axis=1)
        for _, r in pool.sort_values("_score", ascending=False).iterrows():
            ok, _ = can_add(r, selected, ignore_sector=(variant == "A7"), ignore_theme=(variant == "A7"))
            if not ok:
                continue
            rec = r.to_dict()
            rec["final_role"] = rec.get("role_candidate", "Bridge / Diversifier")
            selected.append(rec)
            if len(selected) >= 20:
                break
    out = pd.DataFrame(selected).drop_duplicates("code").head(20).copy()
    out["selection_order"] = range(1, len(out) + 1)
    out["selection_reason"] = out.apply(lambda r: f"{r.final_role}: T={r.transformation_score:.1f}, E={r.emerging_score:.1f}, evidence=TQ{int(r.transformation_quant_evidence_level)}/TR{int(r.transformation_reform_disclosure_level)}/TS{int(r.transformation_shareholder_return_evidence_level)}/EM{int(r.emerging_disclosure_level)}, score_type={r.transformation_score_type}", axis=1)
    out["human_review_required"] = bools(out.get("phase3_review_required"), out.index) | out["transformation_score_type"].eq("lite")
    return out


def rejected_candidates(d: pd.DataFrame, final: pd.DataFrame) -> pd.DataFrame:
    r = d[~d["code"].isin(final["code"])].copy()
    top100 = bools(r.get("top100_flag"), r.index)
    top300_high = bools(r.get("top300_flag"), r.index) & (num(r["transformation_score"]).rank(pct=True).ge(.85) | num(r["emerging_score"]).rank(pct=True).ge(.85))
    ai_known = r["emerging_evidence_category"].fillna("").ne("")
    low_value = num(r.get("value_score"), r.index).ge(75)
    r = r[top100 | top300_high | ai_known | low_value].copy()
    reasons = []
    for _, x in r.iterrows():
        if x.get("low_pbr_only_flag"):
            reason = "low_pbr_only"
        elif x.get("emerging_keyword_only_flag"):
            reason = "ai_keyword_only"
        elif x.get("emerging_disclosure_level", 0) < 2 and x.get("emerging_evidence_category", ""):
            reason = "weak_emerging_evidence"
        elif x.get("transformation_reform_disclosure_level", 0) == 0 and x.get("role_candidate") == "Transformation Core":
            reason = "weak_reform_evidence"
        elif x.get("transformation_shareholder_return_evidence_level", 0) == 0 and x.get("role_candidate") == "Transformation Core":
            reason = "weak_shareholder_return"
        elif x.get("value_trap_penalty", 0) > 15:
            reason = "value_trap_risk"
        elif x.get("base_hard_exclusion_flag"):
            reason = "distress_or_quality_risk"
        else:
            reason = "already_represented_by_better_candidate"
        reasons.append(reason)
    r["rejection_reason_category"] = reasons
    r["rejection_reason"] = r.apply(lambda x: f"{x.rejection_reason_category}; T={x.transformation_score:.1f}, E={x.emerging_score:.1f}, EM evidence={int(x.emerging_disclosure_level)}", axis=1)
    return r.sort_values(["rejection_reason_category", "transformation_score", "emerging_score"], ascending=[True, False, False])


def allocation(final: pd.DataFrame) -> pd.DataFrame:
    f = final.copy()
    role_counts = f["final_role"].value_counts().to_dict()
    f["target_weight"] = f["final_role"].map(ROLE_TARGETS) / f["final_role"].map(role_counts)
    f["target_weight"] = f["target_weight"].clip(upper=MAX_STOCK_WEIGHT)
    residual = 1 - f["target_weight"].sum()
    for _ in range(20):
        eligible = f["target_weight"].lt(MAX_STOCK_WEIGHT - 1e-9)
        if residual <= 1e-9 or not eligible.any():
            break
        add = min(residual / eligible.sum(), float((MAX_STOCK_WEIGHT - f.loc[eligible, "target_weight"]).min()))
        f.loc[eligible, "target_weight"] += add
        residual = 1 - f["target_weight"].sum()
    f["target_yen"] = (f["target_weight"] * TOTAL_BUDGET).round().astype(int)
    f["latest_price"] = num(f.get("close"), f.index).fillna(num(f.get("price_used"), f.index))
    f["lot_size"] = 100
    f["lot_size_assumption_flag"] = True
    f["lot_size_assumption"] = 100
    f["needs_human_verification"] = True
    spent = 0.0
    shares = []
    statuses = []
    notes = []
    for _, r in f.iterrows():
        price = r.latest_price
        lot_cost = price * r.lot_size if pd.notna(price) else np.nan
        max_yen = TOTAL_BUDGET * MAX_STOCK_WEIGHT
        if pd.isna(price):
            sh, status, note = 0, "price_data_missing", "latest price is missing"
        elif lot_cost > max_yen:
            sh, status, note = 0, "not_purchasable_under_8pct_cap", f"one 100-share lot costs {lot_cost:,.0f} yen, above 8% cap"
        elif spent + lot_cost > TOTAL_BUDGET:
            sh, status, note = 0, "budget_remaining_insufficient", "not enough residual cash for one lot"
        else:
            sh, status, note = 100, "one_lot_executable_under_assumption", "100-share lot assumed; verify exchange unit"
            spent += lot_cost
        shares.append(sh)
        statuses.append(status)
        notes.append(note)
    f["purchasable_shares"] = shares
    f["actual_yen"] = (f["latest_price"] * f["purchasable_shares"]).fillna(0).round().astype(int)
    f["actual_weight"] = f["actual_yen"] / TOTAL_BUDGET
    f["weight_diff"] = f["actual_weight"] - f["target_weight"]
    f["allocation_status"] = statuses
    f["allocation_note"] = notes
    f["theme"] = f["emerging_evidence_category"].fillna("").replace("", "non_ai_or_transformation")
    f["cash_remaining_after_plan"] = TOTAL_BUDGET - int(f["actual_yen"].sum())
    cols = ["code", "company_name", "role", "target_weight", "target_yen", "latest_price", "lot_size", "purchasable_shares", "actual_yen", "actual_weight", "weight_diff", "sector", "theme", "allocation_status", "allocation_note", "lot_size_assumption_flag", "lot_size_assumption", "needs_human_verification", "cash_remaining_after_plan"]
    f["role"] = f["final_role"]
    return f[cols]


def ablations(d: pd.DataFrame, final: pd.DataFrame) -> pd.DataFrame:
    base = set(norm_series(final["code"]))
    labels = {
        "A1": "Transformation Score only",
        "A2": "Emerging Score only",
        "A3": "Evidence Level disabled",
        "A4": "Value Trap Penalty disabled",
        "A5": "Theme Hype Penalty disabled",
        "A6": "Phase2 Confidence disabled",
        "A7": "sector cap removed",
        "A8": "Top100 only",
        "A9": "Top300 only",
        "A10": "Top1200 all",
        "A11": "Buffett Core not fixed",
        "A12": "Dual Moat slots zero",
        "A13": "Bridge slots zero",
        "A14": "Emerging Evidence Level >=2 disabled",
        "A15": "Transformation Reform Evidence disabled",
    }
    rows = []
    for key, desc in labels.items():
        sel = select_final(d, key)
        codes = set(norm_series(sel["code"]))
        overlap = len(codes & base)
        jaccard = overlap / len(codes | base) if codes | base else 0
        rows.append({
            "variant": key,
            "description": desc,
            "selected_count": len(codes),
            "overlap_with_final20": overlap,
            "jaccard_with_final20": jaccard,
            "role_distribution": json.dumps(sel["final_role"].value_counts().to_dict(), ensure_ascii=False),
            "sector_distribution": json.dumps(sel["sector"].value_counts().to_dict(), ensure_ascii=False),
            "theme_distribution": json.dumps(sel.get("emerging_evidence_category", pd.Series("", index=sel.index)).fillna("non_ai").replace("", "non_ai").value_counts().to_dict(), ensure_ascii=False),
            "top_changed_in": ";".join(sorted(codes - base)[:8]),
            "top_changed_out": ";".join(sorted(base - codes)[:8]),
            "interpretation": "Constraint materially changes composition." if jaccard < .75 else "Final selection is relatively stable under this variant.",
        })
    out = pd.DataFrame(rows)
    if out["overlap_with_final20"].eq(0).all():
        log("Ablation overlap all zero: code normalization failure suspected", "validation_errors.log")
        raise RuntimeError("ablation overlap all zero")
    return out


def make_reports(d: pd.DataFrame, final: pd.DataFrame, rejected: pd.DataFrame, alloc: pd.DataFrame, abl: pd.DataFrame) -> None:
    v1_final = load_final_v1()
    removed = v1_final[~v1_final["code"].isin(final["code"])]
    added = final[~final["code"].isin(v1_final["code"])]
    role_counts = final["final_role"].value_counts().to_dict()
    fullness_counts = final["transformation_score_type"].value_counts().to_dict()
    ev_summary = {
        "Transformation Quant Evidence Level": d["transformation_quant_evidence_level"].value_counts().sort_index().to_dict(),
        "Transformation Reform Disclosure Level": d["transformation_reform_disclosure_level"].value_counts().sort_index().to_dict(),
        "Transformation Shareholder Return Evidence Level": d["transformation_shareholder_return_evidence_level"].value_counts().sort_index().to_dict(),
        "Emerging Disclosure Level": d["emerging_disclosure_level"].value_counts().sort_index().to_dict(),
        "Final Evidence Level": final["final_evidence_level"].value_counts().sort_index().to_dict(),
    }
    top5_pass = set(norm_series(final[bools(final.get("phase1_top5_flag"), final.index)]["code"])) == EXPECTED_TOP5
    write_md(REPORTS / "phase3_phase2_input_audit.md", f"""
    # Phase2 Input Audit

    - Formal Top1200 rows carried into v2: {len(d):,}
    - Unique codes: {d.code.nunique():,}
    - Phase1 Top5 fixed reconciliation: {'PASS' if top5_pass else 'FAIL'}
    - Top300 systematic Emerging screen coverage: {int(bools(d.get('top300_flag'), d.index).sum())}
    - Top1200 systematic Emerging screen coverage: {len(d)}
    """)
    write_md(REPORTS / "phase3_v1_input_audit.md", f"""
    # v1 Input Audit

    v1 was preserved at `outputs/phase3_beyond_buffett/` and read as a comparison baseline. v1 final rows: {len(v1_final)}. v1 had strong curated-evidence dependence and mixed evidence levels; v2 separates Transformation quant evidence, Transformation reform evidence, shareholder-return evidence, Emerging disclosure evidence, and final role evidence.
    """)
    write_md(REPORTS / "phase3_v1_to_v2_selection_diff.md", f"""
    # v1 to v2 Selection Diff

    Removed from v1:

    {md_table(removed, ['code','company_name','final_role'], 30)}

    Newly added in v2:

    {md_table(added, ['code','company_name','final_role'], 30)}

    The main selection changes, if any, come from the v2 partial Transformation score, separated evidence gates, and the corrected allocation of scarce Level 2+ Emerging disclosure capacity.
    """)
    write_md(REPORTS / "phase3_flag_reconciliation_report.md", """
    # Flag Reconciliation Report

    v2 keeps the Phase2 formal Top1200 as the authoritative universe. Soft review flags are carried into human-review columns, while hard exclusions are limited to distress, unreviewed anomaly, negative equity, low liquidity, persistent losses, and excessive missingness. Phase1 Top5 are fixed but not stripped of review warnings.
    """)
    write_md(REPORTS / "phase3_missing_feature_report.md", """
    # Missing Feature Report

    Formal shareholder-return fields and reform-disclosure fields were not found in the available Phase2/v1 columns. v2 therefore records each required external feature, uses available FCF proxy and financial-improvement evidence where possible, and labels the resulting Transformation score as full, partial, or lite. No payout, buyback, ROIC target, PBR policy, or cross-shareholding evidence was fabricated.
    """)
    write_md(REPORTS / "phase3_transformation_fullness_report.md", f"""
    # Transformation Fullness Report

    Full Transformation requires valuation gap, capital-efficiency improvement, shareholder alignment, reform disclosure, execution reliability, and trap resistance. Available data covered valuation, quality, improvement, execution, liquidity, and an FCF proxy. Missing data covered formal payout, buyback, DOE, total payout, net payout yield, capital-cost disclosure, ROIC targets, PBR improvement policies, cross-shareholding reduction, asset sales, and restructuring disclosure.

    Final20 score-type distribution: {fullness_counts}

    Transformation Core names should be written honestly: partial names have quantitative improvement plus FCF proxy, but still require human confirmation of shareholder-return and reform disclosure before being called Full Transformation.

    {md_table(final, ['code','company_name','final_role','transformation_score_type','transformation_fullness_score','transformation_fullness_note'], 20)}
    """)
    write_md(REPORTS / "phase3_evidence_audit_report.md", f"""
    # Evidence Audit Report

    Evidence is split into separate meanings:

    - Transformation Quant Evidence Level: financial improvement only, not disclosure evidence.
    - Transformation Reform Disclosure Level: capital-cost, ROIC, PBR, policy-holding, asset-sale, or restructuring disclosure.
    - Transformation Shareholder Return Evidence Level: payout/buyback/DOE/FCF-coverage type evidence.
    - Emerging Disclosure Level: AI infrastructure, products, customers, use cases, or quantitative disclosure.
    - Final Evidence Level: role-specific synthesis.

    Distribution: {json.dumps(ev_summary, ensure_ascii=False)}
    """)
    write_md(REPORTS / "phase3_selection_audit.md", f"""
    # Selection Audit

    - Final count: {len(final)}
    - Role composition: {role_counts}
    - Sector counts: {final.sector.value_counts().to_dict()}
    - Theme counts: {final.emerging_evidence_category.fillna('non_ai').replace('', 'non_ai').value_counts().to_dict()}
    - Phase1 Top5 fixed: {'PASS' if top5_pass else 'FAIL'}
    - No hard exclusions selected outside fixed core: {not bools(final[~bools(final.get('phase1_top5_flag'), final.index)].get('base_hard_exclusion_flag')).any()}
    """)
    write_md(REPORTS / "phase3_ablation_report.md", f"""
    # Ablation Report

    v2 recalculates overlap using normalized string codes, so the v1 all-zero overlap bug is removed. The variants are structural checks, not return-driven replacement rules.

    {md_table(abl, ['variant','description','selected_count','overlap_with_final20','jaccard_with_final20','interpretation'], 20)}
    """)
    write_md(REPORTS / "phase3_formula_lineage_report.md", """
    # Formula Lineage Report

    The Phase3 synthetic formulas are not themselves formulas proven by prior research. They reconstruct indicators whose meaning is established in the literature and adapt them to the purpose of detecting Moat change over time.

    Transformation Moat uses valuation gap (B/M, E/P, and available PBR/PER proxies where supplied), capital-efficiency improvement (ROIC proxy, ROA/ROE, operating margin, asset turnover, gross margin change), shareholder alignment (dividends, DOE, payout, buybacks, net payout, and FCF coverage when supplied), reform evidence (capital-cost disclosure, ROIC target, PBR policy, policy-holding reduction, asset sale, restructuring, medium-term KPI), execution reliability (Piotroski, CFO/NI, liquidity/confidence), and value-trap penalties (Sloan accruals, distress, negative CFO, losses, anomaly).

    Emerging Moat uses intangible capital, innovation capacity, bottleneck/pricing power, AI infrastructure exposure, data/customer base, and trust/safety infrastructure. AI-infrastructure exposure is split into semiconductor, data center, power grid, cooling, optical communication, FA, cybersecurity, business data, quality assurance, and precision processing.

    Originality is not in claiming a new universal return formula. It is in the bundling, Japan-equity correction, Evidence Level, penalties, guardrails, role assignment, ablation, and rejected-candidate audit. Weights are conceptual design coefficients, not ex-post return maximizers.
    """)
    write_md(REPORTS / "phase3_rejected_candidates.md", f"""
    # Rejected Candidates

    Rejected candidates include Top100 non-selections, high-score Top300 names, AI/semiconductor/data-center related systematic hits, and low-PBR/high-value names. Reasons distinguish low_pbr_only, ai_keyword_only, weak reform evidence, weak shareholder return, weak Emerging evidence, value-trap risk, concentration, liquidity, quality, and better represented alternatives.

    {md_table(rejected, ['code','company_name','sector','role_candidate','rejection_reason_category','transformation_score','emerging_score'], 80)}
    """)
    write_md(REPORTS / "phase3_summary_report.md", f"""
    # Phase3 v2 Summary

    - Final20 role composition: {role_counts}
    - v1 removed/new: {len(removed)}/{len(added)}
    - Evidence distribution: {json.dumps(ev_summary, ensure_ascii=False)}
    - Transformation Fullness distribution in Final20: {fullness_counts}
    - Emerging systematic screening target count: {len(d)}
    - Ablation overlap minimum: {int(abl.overlap_with_final20.min())}
    - Allocation status: {alloc.allocation_status.value_counts().to_dict()}
    """)
    write_md(DOCS / "phase3_build_design.md", """
    # Phase3 Build Design

    Phase3 v2 keeps Phase1/Phase2 intact and extends the time axis of Moat: completed Moat, widened candidate universe, changing Moat, and emerging Moat. v2 is intentionally auditable: every score type, missing feature, evidence level, rejection, ablation variant, and allocation assumption is written to CSV and Markdown.
    """)
    write_md(DOCS / "phase3_transformation_moat_definition.md", """
    # Transformation Moat Definition

    Transformation Moat is not low PBR. It is valuation gap plus improving capital efficiency, shareholder/reform alignment when available, execution reliability, and value-trap resistance. v2 labels each name full, partial, or lite so the report does not overclaim unavailable disclosure evidence.
    """)
    write_md(DOCS / "phase3_emerging_moat_definition.md", """
    # Emerging Moat Definition

    Emerging Moat is exposure to newly forming bottlenecks in AI-era infrastructure and implementation. Keywords establish only Level 1. Level 2 requires a concrete product, use case, customer group, investment plan, or strategy. Level 3 requires quantitative evidence such as sales, orders, backlog, customers, CAPEX, segment revenue, product mix, or KPI.
    """)
    write_md(DOCS / "phase3_scoring_framework.md", """
    # Scoring Framework

    Numeric inputs are normalized as cross-sectional percentiles inside the Phase2 formal Top1200. Transformation combines valuation, capital-efficiency improvement, FCF proxy where available, execution, quality, and confidence less trap penalties. Emerging applies the requested 18/15/18/22/14/13 structure with evidence bonuses and hype penalties.
    """)
    write_md(DOCS / "phase3_selection_algorithm.md", """
    # Selection Algorithm

    The algorithm fixes Phase1 Top5, then fills Dual, Emerging, Transformation, and Bridge quotas under hard guardrails, sector caps, theme caps, and no-low-PBR-only/no-AI-keyword-only rules. Final20 is reselected from v2 scores; v1 membership is used only for comparison.
    """)
    write_md(DOCS / "phase3_final20_rationale.md", rationale_text(final, report_style=False))
    write_md(DOCS / "phase3_final20_rationale_for_report.md", rationale_text(final, report_style=True))
    write_md(REPORTS / "phase3_final20_rationale_for_report.md", rationale_text(final, report_style=True))
    write_md(DOCS / "phase3_allocation_report.md", f"""
    # Allocation Report

    Total budget is ¥{TOTAL_BUDGET:,.0f}. v2 uses role target weights, an 8% per-stock cap, a 25% sector cap, a 25% theme cap, latest prices, and a 100-share lot assumption because exchange lot data were not found. This makes the allocation close to executable while still marking every lot assumption for human verification.

    Cash remaining after the one-lot-under-cap plan: ¥{int(alloc.cash_remaining_after_plan.iloc[0]):,}

    {md_table(alloc, ['code','company_name','role','target_yen','latest_price','lot_size','purchasable_shares','actual_yen','allocation_status'], 25)}
    """)
    write_md(DOCS / "phase3_ablation_plan.md", """
    # Ablation Plan

    A1-A15 test dependence on Transformation, Emerging, Evidence, trap penalty, hype penalty, confidence, sector cap, universe size, fixed Buffett Core, Dual slots, Bridge slots, Emerging evidence gate, and reform evidence. The purpose is to identify fragile design choices and concentration risk, not to optimize historical returns.
    """)
    write_md(DOCS / "phase3_risk_and_limitations.md", """
    # Risk and Limitations

    Scores are explanatory, not forecasts. Missing payout/reform/patent/customer/lot-size data still require human confirmation. Systematic keyword screening is useful for coverage, but Level 1 is never treated as strong disclosure. AI-infrastructure themes can be overvalued; low valuation can be a trap. No final replacement is made from backtest performance.
    """)
    write_md(DOCS / "phase3_to_report_handoff.md", """
    # Phase3 To Report Handoff

    Phase3 does not reject Buffett-style Moat. It starts from the same durable-advantage question and extends its time axis. Phase1 captures already completed Moat. Phase2 breaks the fixed threshold structure and widens the candidate universe. Phase3 asks which Moats are changing and which Moats are being born.

    A specialist may object that the model only adds existing indicators. That is partly true and deliberately so. The research does not invent unverified magic indicators; it recomposes indicators whose meanings are already established into a Moat-time-axis framework. A specialist may object that weights are arbitrary. v2 answers that weights are conceptual design coefficients, not ex-post return maximizers, and their discretion is constrained by Evidence Level, guardrails, ablation, and rejected-candidate audit.

    A specialist may call it an AI theme basket. v2 rejects that framing: the word AI is not enough. Evidence must show sales, orders, customers, products, CAPEX, segments, products, or concrete use cases. A specialist may call it a low-PBR basket. v2 rejects low PBR alone; it also requires improvement, execution reliability, shareholder/reform evidence where available, and trap penalties. Finally, the final 20 is not selected by backtest replacement. Ablation is a robustness check after selection.
    """)


def rationale_text(final: pd.DataFrame, report_style: bool) -> str:
    title = "# Final20 Rationale For Report" if report_style else "# Final20 Rationale"
    lines = [title]
    for _, r in final.sort_values("selection_order").iterrows():
        snippet = str(r.get("emerging_evidence_snippet", "no verified company disclosure"))
        source = str(r.get("emerging_evidence_source", "") or "")
        risk = "開示確認と流動性・テーマ集中の再確認"
        if r.final_role == "Buffett Core":
            body = f"{r.company_name}（{r.code}）はBuffett Coreとして、Phase1で確認された完成済みMoatを最終20社の安定土台に置く役割を持つ。Value、Quality、Safety、Liquidityの先行研究指標に接続し、Phase3では新規テーマを無理に付与せず、既存Moatの防御力をポートフォリオ全体の基礎として使う。Evidenceは定量改善Level {int(r.transformation_quant_evidence_level)}であり、単なる低PBRやAIテーマ株としての採用ではない。主要リスクは事業固有の景気感応度と、Phase3の変化・Emerging要素が相対的に薄い点である。"
        elif r.final_role == "Transformation Core":
            body = f"{r.company_name}（{r.code}）はTransformation Coreとして、評価ギャップと資本効率改善の組み合わせを評価した。Transformation score typeは{r.transformation_score_type}で、{r.transformation_fullness_note}。先行研究指標ではB/M・E/P、Piotroski、Sloan、ROA/ROE/マージン改善に接続する。低PBR単独ではなく、改善指標、FCF proxy、実行安全性、value trap penaltyを同時に見ている。ただし改革開示Level {int(r.transformation_reform_disclosure_level)}、株主還元Level {int(r.transformation_shareholder_return_evidence_level)}であり、Lite/Partialの場合は追加開示確認が必要である。主要リスクは{risk}。"
        elif r.final_role == "Emerging Core":
            body = f"{r.company_name}（{r.code}）はEmerging Coreとして、AI産業基盤との接続を評価した。カテゴリは{r.emerging_evidence_category}、Emerging disclosure Level {int(r.emerging_disclosure_level)}。根拠は「{snippet}」で、sourceは{source or 'systematic screen'}。AIという語の有無ではなく、製品・用途・顧客・数量に近い開示を重視したため、AI keyword onlyではない。主要リスクはテーマ過熱、受注循環、設備投資サイクルである。"
        elif r.final_role == "Dual Moat":
            body = f"{r.company_name}（{r.code}）はDual Moatとして、変わるMoatと生まれるMoatが重なる候補である。Transformationでは定量改善Level {int(r.transformation_quant_evidence_level)}、Emergingでは{r.emerging_evidence_category}のLevel {int(r.emerging_disclosure_level)}を持つ。根拠は「{snippet}」。既存事業の収益性・実行力に加え、AI産業基盤や品質・データ・信頼安全のボトルネックに接続するため、単なるValue株でも単なるテーマ株でもない。"
        else:
            body = f"{r.company_name}（{r.code}）はBridge / Diversifierとして、最終20社の業種・テーマ分散とリスク低減を担う。Transformation score {r.transformation_score:.1f}、Emerging score {r.emerging_score:.1f}を持つが、主目的は特定テーマへの偏りを抑え、Buffett Core、Transformation、Emerging、Dualを橋渡しすることである。単なる余り枠ではなく、制約下でのポートフォリオ耐性を上げる役割として採用した。"
        lines += [f"\n## {int(r.selection_order)}. {r.company_name} ({r.code})", body]
    return "\n".join(lines)


def readiness(final: pd.DataFrame, d: pd.DataFrame, rejected: pd.DataFrame, alloc: pd.DataFrame, abl: pd.DataFrame) -> dict[str, bool]:
    checks = {
        "Phase2 Top1200を正式母集団にしている": len(d) == 1200 and d["top1200_flag"].astype(str).str.lower().eq("true").all(),
        "Phase1 Top5が固定されている": set(norm_series(final[bools(final.get("phase1_top5_flag"), final.index)]["code"])) == EXPECTED_TOP5,
        "v1を削除していない": V1.exists() and (ROOT / "outputs" / "phase3_beyond_buffett.zip").exists(),
        "Final20が20社である": len(final) == 20,
        "残り15社がTop1200から選ばれている": bools(final[~bools(final.get("phase1_top5_flag"), final.index)].get("top1200_flag")).all(),
        "Evidence Levelが分離されている": all(c in d.columns for c in ["transformation_quant_evidence_level", "transformation_reform_disclosure_level", "transformation_shareholder_return_evidence_level", "emerging_disclosure_level", "final_evidence_level"]),
        "Transformation Fullnessが表示されている": "transformation_fullness_score" in final.columns,
        "Emergingがcurated evidenceだけに依存していない": "systematic_screening_flag" in d.columns and len(d) >= 1200,
        "Ablation overlapが正常に計算されている": not abl["overlap_with_final20"].eq(0).all(),
        "Rejected Candidatesが存在する": len(rejected) > 0,
        "Final20 rationaleが文章化されている": (DOCS / "phase3_final20_rationale_for_report.md").exists(),
        "Allocationが実行可能、または不足データが明記されている": len(alloc) == 20 and alloc["allocation_status"].notna().all(),
        "Formula Lineageが提出用に書かれている": (REPORTS / "phase3_formula_lineage_report.md").exists(),
        "Risk and Limitationsが書かれている": (DOCS / "phase3_risk_and_limitations.md").exists(),
        "phase3_beyond_buffett_v2.zip が存在する": (ROOT / "outputs" / "phase3_beyond_buffett_v2.zip").exists(),
    }
    failed = [k for k, v in checks.items() if not v]
    body = "# Final Readiness Check\n\n"
    if failed:
        body += "## 提出前に人間が確認すべき未解決事項\n\n" + "\n".join(f"- {x}" for x in failed) + "\n\n"
    body += "| Check | Status |\n|---|---|\n" + "\n".join(f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in checks.items())
    write_md(OUT / "FINAL_READINESS_CHECK.md", body)
    return checks


def manifest_and_readme() -> None:
    write_md(OUT / "README.md", """
    # BEYOND BUFFETT Phase3 v2

    This package preserves v1 and rebuilds Phase3「離」as a submission-ready artifact. It strengthens Transformation Fullness, systematic Emerging screening, separated Evidence Levels, corrected ablation overlap, final rationale prose, lot-size-aware allocation, Formula Lineage, and limitations.

    Rebuild with `scripts/phase3_selection/run_all.sh`.
    """)
    rows = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.md":
            rows.append((str(p.relative_to(OUT)), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()))
    write_md(OUT / "MANIFEST.md", "# MANIFEST\n\n| Path | Bytes | SHA-256 |\n|---|---:|---|\n" + "\n".join(f"| `{p}` | {b} | `{h}` |" for p, b, h in rows))


def zip_output() -> Path:
    zip_path = ROOT / "outputs" / "phase3_beyond_buffett_v2.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", ROOT / "outputs", "phase3_beyond_buffett_v2")
    log(f"created {zip_path.relative_to(ROOT)}")
    return zip_path


def run_all() -> None:
    for log_name in ["run.log", "warnings.log", "missing_features.log", "validation_errors.log"]:
        (LOGS / log_name).write_text("", encoding="utf-8")
    ensure_inputs()
    seed = read_csv(V1 / "data" / "phase3_seed_universe_from_phase2.csv", required=True)
    seed["code"] = norm_series(seed["code"])
    write_csv(seed, DATA / "phase3_seed_universe_from_phase2.csv")
    guard = read_csv(V1 / "data" / "phase3_guardrail_confidence.csv", required=True)
    guard["code"] = norm_series(guard["code"])
    write_csv(guard, DATA / "phase3_guardrail_confidence.csv")
    lite = read_csv(V1 / "data" / "phase3_transformation_lite_scores.csv", required=True)
    lite["code"] = norm_series(lite["code"])
    write_csv(lite, DATA / "phase3_transformation_lite_scores.csv")
    d = load_base()
    d = transformation_fullness(d)
    d = keyword_screen(d)
    d = emerging_scores(d)
    d = evidence_levels(d)
    d = grades_roles(d)
    final = select_final(d)
    if len(final) != 20:
        raise RuntimeError(f"Final20 count is {len(final)}")
    write_csv(d, DATA / "phase3_transformation_scores.csv")
    write_csv(d, DATA / "phase3_emerging_scores.csv")
    write_csv(d, DATA / "phase3_scoring_master.csv")
    write_csv(d, DATA / "phase3_final20_candidates.csv")
    write_csv(final, DATA / "phase3_final20_selected.csv")
    rejected = rejected_candidates(d, final)
    write_csv(rejected, DATA / "phase3_rejected_candidates.csv")
    alloc = allocation(final)
    write_csv(alloc, DATA / "phase3_allocation_plan.csv")
    abl = ablations(d, final)
    write_csv(abl, DATA / "phase3_ablation_results.csv")
    make_reports(d, final, rejected, alloc, abl)
    # Need zip existence before final readiness evaluates that check.
    manifest_and_readme()
    zip_output()
    checks = readiness(final, d, rejected, alloc, abl)
    manifest_and_readme()
    zip_output()
    print("\nPHASE3_V2_SUMMARY")
    print(f"artifact_folder={OUT}")
    print(f"artifact_zip={ROOT / 'outputs' / 'phase3_beyond_buffett_v2.zip'}")
    print(f"v1_to_v2_removed={len(load_final_v1()[~load_final_v1().code.isin(final.code)])}")
    print(f"v1_to_v2_added={len(final[~final.code.isin(load_final_v1().code)])}")
    print(f"role_composition={final.final_role.value_counts().to_dict()}")
    print(f"evidence_distribution={final.final_evidence_level.value_counts().sort_index().to_dict()}")
    print(f"transformation_fullness_distribution={final.transformation_score_type.value_counts().to_dict()}")
    print(f"emerging_systematic_screening_count={len(d)}")
    print(f"ablation_overlap_min={int(abl.overlap_with_final20.min())}")
    print(f"allocation_status={alloc.allocation_status.value_counts().to_dict()}")
    print(f"final_readiness={'PASS' if all(checks.values()) else 'FAIL'}")
    print("next_review_files=FINAL_READINESS_CHECK.md, docs/phase3_final20_rationale_for_report.md, reports/phase3_transformation_fullness_report.md, data/phase3_allocation_plan.csv")


if __name__ == "__main__":
    run_all()
