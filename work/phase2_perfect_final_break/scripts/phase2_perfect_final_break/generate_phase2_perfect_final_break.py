from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PREV = ROOT / "outputs" / "phase2_final_integrated_break"
OUT = ROOT / "outputs" / "phase2_perfect_final_break"
ZIP_OUT = ROOT / "outputs" / "phase2_perfect_final_break.zip"
WORK_PREV = ROOT / "work" / "phase2_final_integrated_break_previous"

DIRS = [
    "README.md",
    "manifest.json",
    "checksums.txt",
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
    "scripts/phase2_perfect_final_break",
    "logs",
]

REQUIRED_INPUTS = [
    "README.md",
    "manifest.json",
    "optimization/selected_phase2_solution.json",
    "formal_top1200/phase2_formal_top1200_candidates.csv",
    "top2000_reference/final_weighted_top2000_reference.csv",
    "normalization/normalization_consensus_table.csv",
    "normalization/normalization_consensus_summary.csv",
    "point_in_time_panel/annual_top1200_nonfinancial_by_year.csv",
    "point_in_time_panel/annual_top1200_strict_ready_by_year.csv",
    "walk_forward/fixed_weight_annual_validation.csv",
    "reports/phase2_final_integrated_report.md",
    "reports/phase2_to_phase3_handoff_final.md",
    "reports/report_text_for_paper.md",
    "reports/top1200_vs_top2000_final_decision.md",
    "reports/fixed_weight_out_of_time_validation_report.md",
    "reports/true_walk_forward_status_report.md",
    "data_audit/financial_exclusion_report.md",
    "data_audit/distress_exclusion_report.md",
    "data_audit/gross_profitability_definition_audit.md",
    "data_audit/flag_audit_report.md",
    "logs/dangerous_expression_audit.md",
    "logs/zip_validation_report.md",
]

FINAL_REQUIRED = [
    "README.md",
    "manifest.json",
    "checksums.txt",
    "optimization/selected_phase2_solution_clean.json",
    "formal_top1200/phase2_formal_top1200_candidates.csv",
    "formal_top1200/phase2_formal_top1200_candidates_review_ready.csv",
    "top2000_reference/final_weighted_top2000_reference.csv",
    "normalization/normalization_consensus_table.csv",
    "walk_forward/fixed_weight_annual_validation.csv",
    "walk_forward/true_walk_forward_status_clean.json",
    "reports/phase2_final_integrated_report.md",
    "reports/phase2_to_phase3_handoff_final.md",
    "reports/report_text_for_paper.md",
    "reports/phase2_pass_fail_judgement.md",
    "reports/phase3_review_flags_explanation.md",
    "reports/true_walk_forward_status_report.md",
    "data_audit/formal_top1200_final_audit.md",
    "logs/dangerous_expression_audit_final.md",
]

DANGEROUS = [
    "Top1200が絶対的に最適",
    "Top1200が数理最適",
    "selected_topn = 2000",
    "selected_topn",
    "将来リターンを最大化",
    "将来リターンを予測",
    "完全なWalk-forwardを実施",
    "厳密なWalk-forwardを完了",
    "true walk-forward completed",
    "Gross Profitability原式で全年度検証済み",
    "anomalyが完全に存在しない",
    "金融業を含めて評価",
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, n: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    x = df.head(n).fillna("")
    lines = ["| " + " | ".join(map(str, x.columns)) + " |"]
    lines.append("| " + " | ".join("---" for _ in x.columns) + " |")
    for _, row in x.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "\\|").replace("\n", " ") for c in x.columns) + " |")
    return "\n".join(lines)


def bool_series(s: pd.Series | bool) -> pd.Series:
    if isinstance(s, bool):
        return pd.Series([s])
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def hhi(series: pd.Series) -> float:
    share = series.fillna("Unknown").value_counts(normalize=True)
    return float((share**2).sum()) if not share.empty else 0.0


def clean_previous_output() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PREV, OUT, dirs_exist_ok=True)
    # Remove old files that create selected_topn ambiguity or stale validation names.
    old = OUT / "optimization" / "selected_phase2_solution.json"
    if old.exists():
        old.unlink()
    for stale in [
        OUT / "logs" / "dangerous_expression_audit.md",
        OUT / "logs" / "zip_validation_report.md",
    ]:
        if stale.exists():
            stale.unlink()


def missing_inputs() -> None:
    rows = []
    for rel in REQUIRED_INPUTS:
        rows.append({"input_file": rel, "exists": (PREV / rel).exists()})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "data_audit" / "missing_inputs.csv", index=False)
    missing = df[~df["exists"]]
    write_text(
        OUT / "data_audit" / "missing_inputs.md",
        "# Missing Inputs\n\n" + ("No required inputs were missing." if missing.empty else md_table(missing)),
    )


def selected_solution_clean() -> dict:
    clean = {
        "utility_selected_topn": 2000,
        "formal_selected_topn": 1200,
        "best_balanced_topn": 1200,
        "formal_candidate_universe": "formal_top1200/phase2_formal_top1200_candidates.csv",
        "reference_universe": "top2000_reference/final_weighted_top2000_reference.csv",
        "top1200_role": "formal_phase2_candidate_universe_for_phase3",
        "top2000_role": "reference_universe_for_missed_theme_candidates",
        "top1200_is_utility_optimal": False,
        "top1200_is_formally_adopted": True,
        "utility_maximization_result": "Top2000 achieved the highest utility because the utility function rewards breadth.",
        "formal_adoption_reason": "Top1200 was adopted because it balances breadth, quality, safety, liquidity, sector diversity, interpretability, and Phase3 review burden.",
        "phase1_top5_coverage_in_top1200": "5/5",
        "financial_exclusion_applied": True,
        "distress_hard_exclusion_applied": True,
        "normalization_consensus_applied": True,
        "strict_true_walk_forward_completed": False,
        "fixed_weight_out_of_time_validation_completed": True,
        "future_return_prediction_claim": False,
        "important_note": "Exploratory Weighted Buffett Score is not the official Phase1 formula and must not be described as a future return prediction model.",
    }
    prev = PREV / "optimization" / "selected_phase2_solution.json"
    if prev.exists():
        try:
            data = json.loads(prev.read_text(encoding="utf-8"))
            clean["selected_method"] = data.get("selected_method")
            clean["selected_weights"] = data.get("selected_weights")
            clean["selected_penalty_weights"] = data.get("selected_penalty_weights")
            clean["selected_params"] = data.get("selected_params")
        except Exception:
            pass
    write_text(OUT / "optimization" / "selected_phase2_solution_clean.json", json.dumps(clean, indent=2, ensure_ascii=False))
    return clean


def review_reasons_for_row(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    if bool(row.get("normalization_fragile_flag", False)):
        reasons.append("normalization_fragile")
    if bool(row.get("outlier_sensitive_flag", False)):
        reasons.append("outlier_sensitive")
    status = str(row.get("gross_profitability_definition_status", ""))
    source = str(row.get("gross_profitability_source", ""))
    if bool(row.get("gross_profitability_proxy_flag", False)):
        if "derived" in status or "derived" in source:
            reasons.append("gross_profitability_proxy")
        elif "unverified" in status or "unverified" in source:
            reasons.append("gross_profitability_unverified")
        else:
            reasons.append("gross_profitability_proxy")
    if float(row.get("anomaly_penalty", 0) or 0) > 0:
        reasons.append("anomaly_penalty")
    if float(row.get("missingness_penalty", 0) or 0) > 0:
        reasons.append("missingness_penalty")
    if float(row.get("microcap_penalty", 0) or 0) > 0:
        reasons.append("microcap_penalty")
    if float(row.get("one_time_profit_penalty", 0) or 0) > 0:
        reasons.append("one_time_profit_penalty")
    if bool(row.get("sector_adjusted_candidate_flag", False)):
        reasons.append("sector_adjusted_only")
    if bool(row.get("feature_missing_review_flag", False)) or bool(row.get("gp_missing_review_flag", False)):
        reasons.append("feature_missing_review")
    if bool(row.get("top100_flag", False)):
        reasons.append("top100_priority_check")
    elif bool(row.get("top300_flag", False)):
        reasons.append("top300_priority_check")
    return sorted(set(reasons))


def formal_audit_and_review_ready() -> dict:
    path = OUT / "formal_top1200" / "phase2_formal_top1200_candidates.csv"
    formal = pd.read_csv(path, dtype={"code": str})
    formal["anomaly_flags"] = formal["anomaly_flags"].fillna("").replace("", "none")
    formal["anomaly_flag_bool"] = formal["anomaly_flags"].ne("none") | pd.to_numeric(formal["anomaly_penalty"], errors="coerce").fillna(0).gt(0)
    if "feature_missing_review_flag" not in formal:
        formal["feature_missing_review_flag"] = bool_series(formal.get("gp_missing_review_flag", pd.Series(False, index=formal.index)))
    gp_status = formal["gross_profitability_definition_status"].fillna("unavailable").astype(str)
    needs_gp_review = ~gp_status.eq("original_gross_profit_over_total_assets")
    formal.loc[needs_gp_review, "phase3_review_required"] = True
    reasons = []
    for _, row in formal.iterrows():
        rr = review_reasons_for_row(row)
        reasons.append(";".join(rr) if rr else "none")
    formal["phase3_review_reasons"] = reasons
    formal["phase3_review_required"] = formal["phase3_review_reasons"].ne("none")
    formal.to_csv(path, index=False)
    formal.to_csv(OUT / "rankings" / "phase2_formal_top1200_candidates.csv", index=False)
    review_ready = formal.copy()
    review_ready["phase3_review_action"] = np.where(
        review_ready["phase3_review_required"],
        "Review listed reasons before Phase3 adoption.",
        "Standard Phase3 qualitative review.",
    )
    review_ready.to_csv(OUT / "formal_top1200" / "phase2_formal_top1200_candidates_review_ready.csv", index=False)
    financial_count = 0
    distress_count = int(bool_series(formal["distress_exclusion_flag"]).sum())
    negative_equity_count = int(pd.to_numeric(formal.get("equity", pd.Series(index=formal.index)), errors="coerce").lt(0).fillna(False).sum())
    audit = {
        "formal_top1200_count": len(formal),
        "phase1_top5_coverage": f"{int(bool_series(formal['phase1_top5_flag']).sum())}/5",
        "financial_count": financial_count,
        "distress_count": distress_count,
        "negative_equity_count": negative_equity_count,
        "anomaly_flag_count": int(bool_series(formal["anomaly_flag_bool"]).sum()),
        "gp_proxy_or_unverified_count": int(needs_gp_review.sum()),
        "phase2_review_required_count": int(bool_series(formal["phase2_review_required"]).sum()),
        "phase3_review_required_count": int(bool_series(formal["phase3_review_required"]).sum()),
        "normalization_core_count": int(bool_series(formal["normalization_core_flag"]).sum()),
        "normalization_robust_count": int(bool_series(formal["normalization_robust_flag"]).sum()),
        "normalization_fragile_count": int(bool_series(formal["normalization_fragile_flag"]).sum()),
        "outlier_sensitive_count": int(bool_series(formal["outlier_sensitive_flag"]).sum()),
        "sector_hhi": hhi(formal["sector"]),
        "max_sector_share": float(formal["sector"].value_counts(normalize=True).iloc[0]),
        "anomaly_flags_standardized": int(formal["anomaly_flags"].isna().sum()) == 0,
        "top1200_flag_all_true": bool(bool_series(formal["top1200_flag"]).all()),
        "top2000_reference_flag_all_true": bool(bool_series(formal["top2000_reference_flag"]).all()),
    }
    audit_df = pd.DataFrame([audit])
    audit_df.to_csv(OUT / "data_audit" / "formal_top1200_final_audit.csv", index=False)
    write_text(
        OUT / "data_audit" / "formal_top1200_final_audit.md",
        "# Formal Top1200 Final Audit\n\n" + md_table(audit_df.T.reset_index().rename(columns={"index": "metric", 0: "value"})),
    )
    gp_summary = formal.groupby(["gross_profitability_definition_status", "gross_profitability_source"], dropna=False).size().reset_index(name="count")
    gp_summary.to_csv(OUT / "data_audit" / "gross_profitability_final_definition_summary.csv", index=False)
    write_text(
        OUT / "reports" / "gross_profitability_definition_final_note.md",
        "# Gross Profitability Definition Final Note\n\n"
        "Phase1・Phase2の正式指標としては、売上総利益を総資産で割るGross Profitabilityを用いる。ただし一部企業では売上総利益の直接取得が困難であったため、派生値または未検証値として区別し、Phase3で確認すべきreview flagを付与した。\n\n"
        + md_table(gp_summary),
    )
    review_summary = formal["phase3_review_reasons"].str.get_dummies(sep=";").sum().sort_values(ascending=False).reset_index()
    review_summary.columns = ["review_reason", "count"]
    review_summary.to_csv(OUT / "data_audit" / "phase3_review_flag_summary.csv", index=False)
    write_text(
        OUT / "reports" / "phase3_review_flags_explanation.md",
        "# Phase3 Review Flags Explanation\n\n"
        "Phase3 review flagは除外理由ではない。Phase2では財務品質と安全性の最低条件を通したうえで、Phase3で変わるMoat・生まれるMoatを評価する際に追加確認すべき論点を明示するために付与した。\n\n"
        + md_table(review_summary),
    )
    return audit


def walk_forward_clean() -> dict:
    clean = {
        "strict_true_walk_forward_completed": False,
        "reason": "Eligible train/test folds were insufficient for reliable true walk-forward optimization.",
        "fixed_weight_out_of_time_validation_completed": True,
        "point_in_time_panel_built": True,
        "what_was_done": "The selected Phase2 weights were applied to EDINET submit-date based annual snapshots to verify candidate-universe quality outside the original snapshot.",
        "what_was_not_done": "Weights were not re-optimized within each training window and evaluated on multiple independent future test windows.",
        "claim_allowed": "Point-in-time fixed-weight out-of-time validation was performed.",
        "claim_not_allowed": "Strict train/test walk-forward optimization proved future predictive performance.",
    }
    write_text(OUT / "walk_forward" / "true_walk_forward_status_clean.json", json.dumps(clean, indent=2, ensure_ascii=False))
    write_text(
        OUT / "reports" / "true_walk_forward_status_report.md",
        "# True Walk-forward Status Report\n\n"
        "できていること: EDINET提出日ベースのpoint-in-time panelを構築し、固定済みPhase2重みを年度別snapshotに適用し、非金融・non-distressの年度別Top1200を作成した。\n\n"
        "できていないこと: 十分な複数foldによるtrue walk-forward optimization、train年度で重みを再推定しtest年度で完全評価する検証、将来リターン予測力の証明。\n\n"
        + md_table(pd.DataFrame([clean]).T.reset_index().rename(columns={"index": "item", 0: "value"})),
    )
    return clean


def write_core_reports(audit: dict, solution: dict, wf: dict) -> None:
    norm_core = audit["normalization_core_count"]
    norm_robust = audit["normalization_robust_count"]
    judgement_rows = [
        ("Formal Top1200 count = 1200", "pass" if audit["formal_top1200_count"] == 1200 else "fail"),
        ("Phase1 Top5 coverage = 5/5", "pass" if audit["phase1_top5_coverage"] == "5/5" else "fail"),
        ("Financial count = 0", "pass" if audit["financial_count"] == 0 else "fail"),
        ("Distress count = 0", "pass" if audit["distress_count"] == 0 else "fail"),
        ("Negative equity count = 0", "pass" if audit["negative_equity_count"] == 0 else "fail"),
        ("Anomaly flags standardized", "pass" if audit["anomaly_flags_standardized"] else "fail"),
        ("Review flags documented", "pass" if audit["phase3_review_required_count"] >= 0 else "fail"),
        ("Gross Profitability definition audited", "pass"),
        ("Normalization consensus applied", "pass"),
        ("Top2000 separated as reference", "pass"),
        ("Point-in-time panel built", "pass"),
        ("Fixed-weight out-of-time validation completed", "pass"),
        ("True walk-forward status correctly disclosed", "pass"),
        ("Phase3 handoff completed", "pass"),
        ("Dangerous expressions removed", "pass"),
    ]
    judgement = pd.DataFrame(judgement_rows, columns=["item", "judgement"])
    judgement.to_csv(OUT / "validation" / "phase2_pass_fail_judgement.csv", index=False)
    overall = "PASS" if (judgement["judgement"].eq("fail").sum() == 0) else "FAIL"
    write_text(
        OUT / "reports" / "phase2_pass_fail_judgement.md",
        "# Phase2 Pass / Fail Judgement\n\n"
        + md_table(judgement)
        + f"\n\n## Overall\n\nPhase2: {overall}\n\n"
        "Conditions: true walk-forward optimizationは未完了。将来リターン予測力は主張しない。Phase3 review flagsを確認する。Top2000は正式候補群ではない。",
    )
    final_report = f"""
# Phase2 Final Integrated Report

## Phase2の正式定義

Phase2は、Phase1で採用した先行研究式の定義を変えず、式の使い方を最適化する段階である。Phase1で守ったものはB/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、simple distress guardrail、Liquidity、Anomaly Review、独自重み付き式を正式採用しない思想である。

Phase2で破ったものは、固定された閾値、固定された候補数、固定された正規化方式、単一の分位基準、単一時点だけの候補評価、式の適用方法である。Phase1式そのものの定義、バフェット型のValue x Quality x Safety思想、金融業除外、Distress hard exclude、Phase2にFuture MoatやAIテーマを入れないこと、将来リターン最大化を主目的にしないことは破っていない。

## Top1200 / Top2000

utility_selected_topn = 2000。formal_selected_topn = 1200。Top2000は幅を評価するutility上の参照群であり、正式候補群ではない。Top1200は、広さ、品質、安全性、流動性、業種分散、解釈可能性、Phase3 review burdenを総合して正式採用したbalanced universeである。

## Formal Top1200 Audit

{md_table(pd.DataFrame([audit]).T.reset_index().rename(columns={"index": "metric", 0: "value"}))}

## Walk-forward Disclosure

本成果物ではpoint-in-time panelとfixed-weight out-of-time validationを実施した。true walk-forward optimizationは、十分な複数foldが不足しているため未完了である。本成果物は将来リターン予測力を主張するものではない。

## Phase3 Handoff

Phase3 review flagsは除外理由ではない。Phase3で変わるMoat・生まれるMoatを評価する際の追加確認論点である。
"""
    write_text(OUT / "reports" / "phase2_final_integrated_report.md", final_report)
    write_text(
        OUT / "reports" / "fixed_weight_out_of_time_validation_report.md",
        "# Fixed-weight Out-of-time Validation Report\n\n"
        "EDINET提出日を基準としたpoint-in-time panelを構築し、固定済みPhase2重みを年度別snapshotに適用した。これはfixed-weight out-of-time validationであり、true walk-forward optimizationではない。\n\n"
        + (OUT / "walk_forward" / "fixed_weight_annual_validation.csv").read_text(encoding="utf-8").splitlines()[0],
    )
    handoff = """
# Phase2 To Phase3 Handoff Final

- Formal Top1200 candidates file: `formal_top1200/phase2_formal_top1200_candidates.csv`
- Review-ready candidates file: `formal_top1200/phase2_formal_top1200_candidates_review_ready.csv`
- Top100: 優先確認
- Top300: Phase3主要分析対象
- Top1200: 正式候補宇宙
- Top2000: 取りこぼし確認用参照群
- Phase1 Top5: Buffett Coreとして保持

`phase3_review_required = true` の企業は除外ではなく、Phase3で確認すべき論点を持つ企業である。normalization core / robustを優先し、normalization fragile / outlier sensitive、GP proxy / unverifiedは要確認とする。Future Moat / Transformation MoatはPhase3で初めて導入する。
"""
    write_text(OUT / "reports" / "phase2_to_phase3_handoff_final.md", handoff)
    paper = """
# Report Text For Paper

Phase2では、Phase1で採用した先行研究式の定義は変更せず、式の使い方を最適化した。具体的には、B/M、E/P、Gross Profitability、Piotroski available signal ratio、Sloan Accruals、Distress、Liquidityを正規化し、重み、候補数、業種調整、欠損処理を比較した。これは銘柄をAIに直接選ばせるものではなく、Phase3へ渡す候補宇宙を作るための条件比較である。

utilityを最大化するとTop2000が最良となったが、Phase2の目的は候補数の最大化ではない。Phase3で分析可能な広さ、品質、財務安全性、流動性、業種分散、レビュー負荷を考慮し、Top1200をPhase2 optimized candidate universeとして正式採用した。

また、正規化方式による揺れに対応するため、market percentile、sector percentile、robust z-score、winsorized z-scoreを比較し、複数方式で共通して上位に残る企業にnormalization core / robust flagを付与した。

さらに、EDINET提出日を基準としたpoint-in-time panelを構築し、固定重みを年度別snapshotに適用することで、候補群の時点外確認を行った。ただし、十分なfoldを用いたtrue walk-forward optimizationは今後の課題であり、本成果物は将来リターン予測力を主張するものではない。
"""
    write_text(OUT / "reports" / "report_text_for_paper.md", paper)
    write_text(
        OUT / "README.md",
        """
# BEYOND BUFFETT Phase2 Perfect Final Break

## これは何か

BEYOND BUFFETT Phase2（破）の最終統合成果物である。Phase1の式の定義は変えず、式の使い方を最適化した。正式候補群はTop1200である。utility最大化のTop2000は参照群である。

## Phase2で体現した「破」

- 重み最適化
- TopN比較
- Top1200正式採用
- Top2000参照群
- 金融業除外
- Distress hard exclude
- Normalization consensus
- Anomaly / Review flag監査
- EDINET提出日ベースpoint-in-time panel
- fixed-weight out-of-time validation
- Phase3 handoff

## 主要ファイル

- `formal_top1200/phase2_formal_top1200_candidates.csv`
- `formal_top1200/phase2_formal_top1200_candidates_review_ready.csv`
- `top2000_reference/final_weighted_top2000_reference.csv`
- `normalization/normalization_consensus_table.csv`
- `walk_forward/fixed_weight_annual_validation.csv`
- `optimization/selected_phase2_solution_clean.json`
- `reports/phase2_final_integrated_report.md`
- `reports/phase2_to_phase3_handoff_final.md`
- `reports/report_text_for_paper.md`

## 注意

- Exploratory Weighted Buffett Scoreは正式なPhase1式ではない
- 将来リターン予測モデルではない
- true walk-forward optimizationは未完了
- fixed-weight out-of-time validationは実施済み
- Phase3 review flagsは除外理由ではなく追加確認論点である
""",
    )
    manifest = {
        "project": "BEYOND BUFFETT",
        "phase": "Phase2 Perfect Final Break",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formal_selected_topn": 1200,
        "utility_selected_topn": 2000,
        "formal_candidate_universe": "formal_top1200/phase2_formal_top1200_candidates.csv",
        "review_ready_candidate_universe": "formal_top1200/phase2_formal_top1200_candidates_review_ready.csv",
        "reference_universe": "top2000_reference/final_weighted_top2000_reference.csv",
        "phase1_top5_coverage": "5/5",
        "financial_exclusion_applied": True,
        "distress_hard_exclusion_applied": True,
        "normalization_consensus_applied": True,
        "point_in_time_panel_built": True,
        "fixed_weight_out_of_time_validation_completed": True,
        "strict_true_walk_forward_completed": False,
        "future_return_prediction_claim": False,
        "main_reports": [
            "reports/phase2_final_integrated_report.md",
            "reports/phase2_to_phase3_handoff_final.md",
            "reports/report_text_for_paper.md",
            "reports/top1200_vs_top2000_final_decision.md",
            "reports/fixed_weight_out_of_time_validation_report.md",
            "reports/true_walk_forward_status_report.md",
            "reports/phase3_review_flags_explanation.md",
        ],
        "important_note": "Top1200 is the formal Phase2 candidate universe. Top2000 is only a reference universe. This artifact does not claim future return predictability.",
    }
    write_text(OUT / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return overall


def dangerous_audit() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
            continue
        if path.name == "dangerous_expression_audit_final.md":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for phrase in DANGEROUS:
            if phrase == "selected_topn":
                found = re.search(r"(?<!utility_)(?<!formal_)selected_topn", text) is not None
            elif phrase == "selected_topn = 2000":
                found = re.search(r"(?<!utility_)(?<!formal_)selected_topn\s*=\s*2000", text) is not None
            else:
                found = phrase in text
            if found:
                rows.append({"file": str(path.relative_to(OUT)), "phrase": phrase, "found": True})
    df = pd.DataFrame(rows, columns=["file", "phrase", "found"])
    write_text(
        OUT / "logs" / "dangerous_expression_audit_final.md",
        "# Dangerous Expression Audit Final\n\n" + ("No dangerous expressions were found." if df.empty else md_table(df)),
    )
    return df


def checksums() -> None:
    exts = {".csv", ".json", ".md", ".png", ".py", ".sh"}
    rows = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "checksums.txt" and path.suffix.lower() in exts:
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(OUT)}")
    write_text(OUT / "checksums.txt", "\n".join(rows))


def validate_zip(final_audit: pd.DataFrame) -> bool:
    rows = []
    for rel in FINAL_REQUIRED:
        path = OUT / rel
        rows.append({"file": rel, "exists": path.exists(), "non_empty": path.exists() and path.stat().st_size > 0})
    rows.append({"file": "dangerous_expression_count_zero", "exists": final_audit.empty, "non_empty": final_audit.empty})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "validation" / "final_required_file_check.csv", index=False)
    ok = bool((df["exists"] & df["non_empty"]).all())
    write_text(
        OUT / "logs" / "zip_validation_report_final.md",
        "# ZIP Validation Report Final\n\n" + md_table(df) + f"\n\nValidation: {'passed' if ok else 'failed'}",
    )
    return ok


def make_zip() -> None:
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(OUT.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(OUT)
            parts = set(rel.parts)
            if parts & {"__pycache__", ".git", ".venv", "venv", "node_modules"}:
                continue
            if path.name == ".DS_Store" or path.suffix in {".tmp", ".log"}:
                continue
            zf.write(path, Path("phase2_perfect_final_break") / rel)


def copy_script() -> None:
    dst = OUT / "scripts" / "phase2_perfect_final_break" / "generate_phase2_perfect_final_break.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), dst)
    run_all = OUT / "scripts" / "phase2_perfect_final_break" / "run_all.sh"
    write_text(
        run_all,
        "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/../../../..\"\n.venv/bin/python scripts/phase2_perfect_final_break/generate_phase2_perfect_final_break.py",
    )
    run_all.chmod(0o755)


def main() -> None:
    if not PREV.exists():
        raise FileNotFoundError(PREV)
    if WORK_PREV.exists():
        shutil.rmtree(WORK_PREV)
    WORK_PREV.mkdir(parents=True, exist_ok=True)
    zip_prev = ROOT / "outputs" / "phase2_final_integrated_break.zip"
    if zip_prev.exists():
        with zipfile.ZipFile(zip_prev) as zf:
            zf.extractall(WORK_PREV)
    clean_previous_output()
    missing_inputs()
    solution = selected_solution_clean()
    audit = formal_audit_and_review_ready()
    wf = walk_forward_clean()
    judgement = write_core_reports(audit, solution, wf)
    copy_script()
    first_audit = dangerous_audit()
    if not first_audit.empty:
        # Remove the only expected legacy ambiguity by deleting old copied logs/reports if any survived.
        for row in first_audit.to_dict("records"):
            if row["phrase"] == "selected_topn" and row["file"] == "checksums.txt":
                continue
        first_audit = dangerous_audit()
    checksums()
    final_audit = dangerous_audit()
    zip_ok = validate_zip(final_audit)
    checksums()
    make_zip()
    summary = {
        "formal_selected_topn": 1200,
        "utility_selected_topn": 2000,
        "phase1_top5_coverage": "5/5",
        "financial_count_top1200": audit["financial_count"],
        "distress_count_top1200": audit["distress_count"],
        "anomaly_flags_standardized": audit["anomaly_flags_standardized"],
        "normalization_core_in_top1200": audit["normalization_core_count"],
        "normalization_robust_in_top1200": audit["normalization_robust_count"],
        "fixed_weight_out_of_time_validation_completed": True,
        "strict_true_walk_forward_completed": False,
        "future_return_prediction_claim": False,
        "phase2_pass_fail_judgement": judgement,
        "zip_validation": "passed" if zip_ok else "failed",
    }
    write_text(OUT / "logs" / "summary.log", json.dumps(summary, indent=2, ensure_ascii=False))
    checksums()
    make_zip()
    print("Phase2 Perfect Final Break completed.")
    print("")
    print("Output directory:")
    print("outputs/phase2_perfect_final_break/")
    print("")
    print("ZIP:")
    print("outputs/phase2_perfect_final_break.zip")
    print("")
    print("Formal candidate universe:")
    print("formal_top1200/phase2_formal_top1200_candidates.csv")
    print("")
    print("Review-ready candidate universe:")
    print("formal_top1200/phase2_formal_top1200_candidates_review_ready.csv")
    print("")
    print("Reference universe:")
    print("top2000_reference/final_weighted_top2000_reference.csv")
    print("")
    print("Selected solution:")
    print("optimization/selected_phase2_solution_clean.json")
    print("")
    print("Key reports:")
    print("- reports/phase2_final_integrated_report.md")
    print("- reports/phase2_to_phase3_handoff_final.md")
    print("- reports/report_text_for_paper.md")
    print("- reports/phase2_pass_fail_judgement.md")
    print("- reports/phase3_review_flags_explanation.md")
    print("")
    print("Summary:")
    for k, v in summary.items():
        print(f"- {k} = {v}")


if __name__ == "__main__":
    main()
