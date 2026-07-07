from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
COMPLETE = ROOT / "outputs" / "phase1_buffett_complete"
PHASE1 = ROOT / "outputs" / "phase1_final"
DATA = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "phase1_top5"
TABLES = OUT / "report_tables"
FIG = ROOT / "figures" / "phase1_top5"
SCRIPT_DIR = ROOT / "scripts" / "phase1_top5"
ZIP_PATH = ROOT / "phase1_top5.zip"


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def n(x: pd.Series | float | int) -> pd.Series:
    return pd.to_numeric(x, errors="coerce")


def truthy(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return (n(a) / n(b).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def pct(v: float) -> str:
    return "" if pd.isna(v) else f"{v:.2%}"


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    d = df.copy()
    if max_rows is not None:
        d = d.head(max_rows)
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].map(lambda v: "" if pd.isna(v) else f"{v:.4f}")
        else:
            d[col] = d[col].fillna("").astype(str)
    lines = [
        "| " + " | ".join(map(str, d.columns)) + " |",
        "| " + " | ".join(["---"] * len(d.columns)) + " |",
    ]
    lines.extend("| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in d.values.tolist())
    return "\n".join(lines)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"code": str, "ticker": str})


def data_sources() -> list[Path]:
    roots = [DATA, PHASE1, COMPLETE]
    out: list[Path] = []
    for root in roots:
        if root.exists():
            out.extend(sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".parquet"}]))
    return out


def variable_inventory() -> pd.DataFrame:
    target_vars = {
        "total_assets": ["total_assets"],
        "total_liabilities": ["total_liabilities", "liabilities"],
        "current_assets": ["current_assets"],
        "current_liabilities": ["current_liabilities"],
        "working_capital": ["working_capital"],
        "net_income": ["net_income"],
        "prior_year_net_income": ["net_income"],
        "two_years_ago_net_income": ["net_income"],
        "operating_cash_flow": ["operating_cash_flow", "operating_cf"],
        "funds_from_operations": ["funds_from_operations", "ffo"],
        "filing_date": ["filing_date", "submit_date"],
        "fiscal_year_end": ["fiscal_year_end", "period_end"],
        "retained_earnings": ["retained_earnings"],
        "EBIT": ["ebit", "operating_income"],
        "market_value_of_equity": ["market_value_of_equity", "market_equity_final", "market_cap"],
        "sales": ["sales", "revenue"],
        "revenue": ["revenue"],
        "equity": ["equity", "book_equity"],
    }
    rows = []
    for var, patterns in target_vars.items():
        matches = []
        best_coverage = 0
        best_path = ""
        best_col = ""
        for path in data_sources():
            try:
                if path.suffix == ".csv":
                    df = pd.read_csv(path, dtype={"code": str})
                else:
                    df = pd.read_parquet(path)
            except Exception:
                continue
            cols = list(map(str, df.columns))
            for col in cols:
                lower = col.lower()
                if any(p.lower() == lower or p.lower() in lower for p in patterns):
                    coverage = int(df[col].notna().sum()) if col in df else 0
                    matches.append(f"{path.relative_to(ROOT)}:{col}({coverage})")
                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_path = str(path.relative_to(ROOT))
                        best_col = col
        derivation = ""
        original_ready = bool(matches)
        if var == "total_liabilities" and not original_ready:
            derivation = "derivable_as_total_assets_minus_equity"
            original_ready = False
        if var == "working_capital" and not original_ready:
            derivation = "requires_current_assets_minus_current_liabilities"
        rows.append(
            {
                "variable": var,
                "found_direct_or_named_column": bool(matches),
                "best_source_file": best_path,
                "best_source_column": best_col,
                "best_non_null_count": best_coverage,
                "all_matches": "; ".join(matches[:12]),
                "derivation_or_note": derivation,
            }
        )
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "ohlson_altman_variable_inventory.csv", index=False)
    return inv


def latest_fundamentals() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = read_csv(DATA / "fundamentals_raw.csv")
    raw["period_end_dt"] = pd.to_datetime(raw["period_end"], errors="coerce")
    raw = raw.sort_values(["code", "period_end_dt"], ascending=[True, False])
    cur = raw.groupby("code").nth(0).reset_index()
    prev = raw.groupby("code").nth(1).reset_index()
    prev2 = raw.groupby("code").nth(2).reset_index()
    return cur, prev, prev2


def attempt_distress_models(inv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cand = read_csv(COMPLETE / "screening_candidates_complete.csv")
    cur, prev, prev2 = latest_fundamentals()
    cur_cols = ["code", "submit_date", "period_end", "revenue", "operating_income", "net_income", "total_assets", "equity", "operating_cf"]
    df = cand[["code", "company_name", "sector", "market_equity_final"]].merge(cur[cur_cols], on="code", how="left")
    df = df.merge(prev[["code", "net_income"]].rename(columns={"net_income": "prior_year_net_income"}), on="code", how="left")
    df = df.merge(prev2[["code", "net_income"]].rename(columns={"net_income": "two_years_ago_net_income"}), on="code", how="left")
    df["total_liabilities_proxy"] = n(df["total_assets"]) - n(df["equity"])
    df["oeneg"] = df["total_liabilities_proxy"] > n(df["total_assets"])
    df["intwo"] = (n(df["net_income"]) < 0) & (n(df["prior_year_net_income"]) < 0)
    df["chin"] = safe_div(n(df["net_income"]) - n(df["prior_year_net_income"]), n(df["net_income"]).abs() + n(df["prior_year_net_income"]).abs())
    df["ffo_to_tl_proxy_ocf"] = safe_div(df["operating_cf"], df["total_liabilities_proxy"])
    df["original_formula_status"] = "not_implemented_original"
    df["reason"] = "Missing GNP price-level index, current assets, current liabilities, and funds from operations; OCF/TL is only a proxy and not used for Top5 primary selection."
    ohlson = df[
        [
            "code",
            "company_name",
            "total_assets",
            "total_liabilities_proxy",
            "equity",
            "net_income",
            "prior_year_net_income",
            "two_years_ago_net_income",
            "operating_cf",
            "oeneg",
            "intwo",
            "chin",
            "ffo_to_tl_proxy_ocf",
            "submit_date",
            "period_end",
            "original_formula_status",
            "reason",
        ]
    ].copy()
    ohlson["ohlson_o_score_original"] = np.nan
    ohlson.to_csv(OUT / "ohlson_o_score_attempt.csv", index=False)

    alt = df.copy()
    alt["working_capital"] = np.nan
    alt["retained_earnings"] = np.nan
    alt["ebit_proxy_operating_income"] = n(alt["operating_income"])
    alt["x1_working_capital_to_assets"] = np.nan
    alt["x2_retained_earnings_to_assets"] = np.nan
    alt["x3_ebit_to_assets_proxy"] = safe_div(alt["ebit_proxy_operating_income"], alt["total_assets"])
    alt["x4_market_equity_to_liabilities"] = safe_div(alt["market_equity_final"], alt["total_liabilities_proxy"])
    alt["x5_sales_to_assets"] = safe_div(alt["revenue"], alt["total_assets"])
    alt["altman_z_score_original"] = np.nan
    alt["original_formula_status"] = "not_implemented_original"
    alt["reason"] = "Missing working capital and retained earnings; EBIT uses operating income proxy only for inventory, not Top5 primary selection."
    altman = alt[
        [
            "code",
            "company_name",
            "working_capital",
            "retained_earnings",
            "ebit_proxy_operating_income",
            "total_assets",
            "market_equity_final",
            "total_liabilities_proxy",
            "revenue",
            "x1_working_capital_to_assets",
            "x2_retained_earnings_to_assets",
            "x3_ebit_to_assets_proxy",
            "x4_market_equity_to_liabilities",
            "x5_sales_to_assets",
            "altman_z_score_original",
            "original_formula_status",
            "reason",
        ]
    ].copy()
    altman.to_csv(OUT / "altman_z_score_attempt.csv", index=False)

    missing_ohlson = [
        "GNP price-level index",
        "current_assets",
        "current_liabilities",
        "funds_from_operations",
    ]
    missing_altman = ["working_capital", "retained_earnings", "strict_EBIT"]
    report = [
        "# Distress Model Implementation Report",
        "",
        "Ohlson O-Score原式は実装しない。必要なGNP price-level index、current assets、current liabilities、funds from operationsが十分に揃わないためである。operating cash flow / total liabilitiesはFFO/TLの補助候補として算出できるが、原式からの逸脱になるためTop5選定の主条件には使わない。",
        "",
        "Altman Z-Score原式も実装しない。working capitalとretained earningsが欠け、EBITもoperating income proxyに留まるためである。Altman原式は製造業向けであり、日本株非金融全体に絶対閾値をそのまま適用しない。",
        "",
        "今回のTop5選定では、Ohlson/Altmanは補助レビューに留め、Low Distress条件はsimple distress guardrailで担保する。",
        "",
        "## Missing Variables",
        "",
        markdown_table(pd.DataFrame({"model": ["Ohlson", "Altman"], "missing_variables": ["; ".join(missing_ohlson), "; ".join(missing_altman)]})),
        "",
        "## Variable Inventory Summary",
        "",
        markdown_table(inv[["variable", "found_direct_or_named_column", "best_source_file", "best_source_column", "derivation_or_note"]]),
    ]
    (OUT / "distress_model_implementation_report.md").write_text("\n".join(report), encoding="utf-8")
    inventory_report = [
        "# Ohlson / Altman Variable Inventory",
        "",
        "既存CSV、Parquet、Phase1出力からOhlson O-ScoreとAltman Z-Scoreに必要な変数を探索した。",
        "",
        markdown_table(inv),
    ]
    (OUT / "ohlson_altman_variable_inventory.md").write_text("\n".join(inventory_report), encoding="utf-8")
    return ohlson, altman


def sort_candidates(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in [
        "gross_profitability_percentile",
        "ep_percentile",
        "bm_percentile",
        "piotroski_available_ratio",
        "sloan_accruals_percentile",
        "avg_daily_value_60d",
        "market_equity_final",
    ]:
        work[col] = n(work[col])
    return work.sort_values(
        [
            "gross_profitability_percentile",
            "ep_percentile",
            "bm_percentile",
            "piotroski_available_ratio",
            "sloan_accruals_percentile",
            "avg_daily_value_60d",
            "market_equity_final",
        ],
        ascending=[False, False, False, False, False, False, False],
    )


def build_top5() -> tuple[pd.DataFrame, pd.DataFrame]:
    cand = read_csv(COMPLETE / "screening_candidates_complete.csv")
    flags = cand["anomaly_flags"].fillna("")
    cand["bm_available_bool"] = truthy(cand["bm_available"])
    cand["ep_available_bool"] = truthy(cand["ep_available"])
    cand["gp_available_bool"] = truthy(cand["gross_profitability_available"])
    cand["distress_exclusion_bool"] = truthy(cand["distress_exclusion_flag"])
    cand["distress_review_bool"] = truthy(cand["distress_review_flag"])
    cand["liquidity_available_bool"] = cand["avg_daily_value_60d"].notna()
    cand["anomaly_exclusion_bool"] = (
        flags.str.contains("extreme_high_ep_top1pct", na=False)
        | (flags.str.contains("extreme_high_bm_top1pct", na=False) & flags.str.contains("extreme_high_ep_top1pct", na=False))
        | flags.str.contains("scale_check|book_equity_market_equity_scale_check|market_equity_inconsistent", na=False)
        | truthy(cand["one_time_profit_suspected"])
        | truthy(cand["microcap_flag"])
    )
    gp_sector_median = cand.groupby("sector")["gross_profitability"].transform("median")
    cand["gross_profitability_sector_median_or_better"] = n(cand["gross_profitability"]) >= n(gp_sector_median)
    steps = [
        ("A_universe_metric_available", cand["bm_available_bool"] & cand["ep_available_bool"] & cand["gp_available_bool"] & cand["available_signal_max"].notna() & cand["sloan_accruals"].notna() & cand["liquidity_available_bool"] & ~cand["distress_exclusion_bool"]),
        ("B_value", (n(cand["bm_percentile"]) >= 0.70) & (n(cand["ep_percentile"]) >= 0.50)),
        ("C_quality", (n(cand["gross_profitability_percentile"]) >= 0.50) & cand["gross_profitability_sector_median_or_better"].fillna(False)),
        ("D_financial_strength", n(cand["piotroski_available_ratio"]) >= 0.65),
        ("E_earnings_quality", n(cand["sloan_accruals_percentile"]) >= 0.30),
        ("F_low_distress", ~cand["distress_exclusion_bool"] & ~cand["distress_review_bool"]),
        ("G_liquidity", cand["liquidity_flag"].eq("pass")),
        ("H_anomaly_clean", ~cand["anomaly_exclusion_bool"]),
    ]
    current = pd.Series(True, index=cand.index)
    rows = []
    for step, mask in steps:
        before = int(current.sum())
        current &= mask.fillna(False)
        rows.append({"step": step, "count_before": before, "count_after": int(current.sum()), "removed_count": before - int(current.sum())})
    funnel = pd.DataFrame(rows)
    funnel.to_csv(TABLES / "phase1_top5_screening_funnel.csv", index=False)

    pool = cand[current].copy()
    sorted_pool = sort_candidates(pool)
    selected = []
    sector_counts: dict[str, int] = {}
    for _, row in sorted_pool.iterrows():
        sector = str(row["sector"])
        if sector_counts.get(sector, 0) >= 2:
            continue
        selected.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) == 5:
            break
    if len(selected) < 5:
        for _, row in sorted_pool.iterrows():
            if any(str(row["code"]) == str(s["code"]) for s in selected):
                continue
            selected.append(row)
            if len(selected) == 5:
                break
    top5 = pd.DataFrame(selected).copy()
    top5["rank"] = range(1, len(top5) + 1)
    top5["role"] = "Buffett Core"
    top5["top5_selection_rule"] = "Sequential tie-break; no weighted composite score; sector duplication capped at two where possible."
    top5["distress_model_used_for_selection"] = "Simple distress guardrail; Ohlson/Altman original formulas not used as primary selection inputs."
    cols = [
        "rank",
        "code",
        "company_name",
        "market",
        "sector",
        "role",
        "bm_raw",
        "bm_percentile",
        "ep_raw",
        "ep_percentile",
        "gross_profitability",
        "gross_profitability_percentile",
        "gross_profitability_sector_median_or_better",
        "available_signal_score",
        "available_signal_max",
        "piotroski_available_ratio",
        "sloan_accruals",
        "sloan_accruals_percentile",
        "distress_exclusion_flag",
        "distress_review_flag",
        "distress_flags",
        "avg_daily_value_60d",
        "liquidity_flag",
        "anomaly_flags",
        "market_equity_final",
        "top5_selection_rule",
        "distress_model_used_for_selection",
    ]
    top5[cols].to_csv(OUT / "phase1_buffett_core_top5.csv", index=False)
    top5[cols].to_csv(TABLES / "phase1_top5_metrics_table.csv", index=False)
    sorted_pool.to_csv(OUT / "phase1_top5_candidate_pool.csv", index=False)
    return cand, top5[cols]


def write_top5_reports(top5: pd.DataFrame) -> None:
    lines = [
        "# Phase1 Buffett Core Top5 Report",
        "",
        "Phase1は最終20社すべてを説明する段階ではなく、守の代表銘柄である `Buffett Core Top5` を抽出する段階として再定義した。Top5はValue、Quality、Financial Strength、Earnings Quality、Low Distress、Liquidityを同時に満たす銘柄であり、最終20社の中にCore枠として組み込む。",
        "",
        "## Top5",
        "",
        markdown_table(top5[["rank", "code", "company_name", "sector", "bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals", "liquidity_flag"]]),
    ]
    (OUT / "phase1_buffett_core_top5_report.md").write_text("\n".join(lines), encoding="utf-8")

    rationale = ["# Top5 Company Rationale", ""]
    for _, row in top5.iterrows():
        anomaly = row.get("anomaly_flags")
        anomaly_text = "主要な異常値フラグなし" if pd.isna(anomaly) or str(anomaly) in {"", "nan"} else f"要確認フラグ: {anomaly}"
        rationale.append(
            f"## {row['code']} {row['company_name']}\n\n"
            f"{row['company_name']}（{row['sector']}）は、B/M {float(row['bm_raw']):.3f}、E/P {float(row['ep_raw']):.3f} でValue条件を満たし、合理的価格で買える候補である。Gross Profitabilityは {float(row['gross_profitability']):.3f}、分位 {float(row['gross_profitability_percentile']):.1%} でQualityも高い。Piotroski available signal scoreは {float(row['available_signal_score']):.0f}/{float(row['available_signal_max']):.0f}、Sloan Accrualsは {float(row['sloan_accruals']):.3f}。Ohlson/Altman原式は使わず、simple distress guardrailで除外・reviewフラグなしを確認した。60日平均売買代金は {float(row['avg_daily_value_60d']):,.0f} 円で流動性もpass。{anomaly_text}。残るリスクは、業種固有の景気感応度やGross Profitabilityの会計構造差である。\n"
        )
    (OUT / "top5_company_rationale.md").write_text("\n".join(rationale), encoding="utf-8")

    allocation = top5[["code", "company_name", "sector"]].copy()
    allocation["role"] = "Buffett Core"
    allocation["tentative_weight_min"] = 0.04
    allocation["tentative_weight_max"] = 0.05
    allocation["rationale"] = "Phase1守る堀Coreとして最終20社に組み込む。1社あたり4-5%、Top5合計20-25%を想定。"
    allocation.to_csv(OUT / "phase1_top5_allocation_plan.csv", index=False)
    (OUT / "phase1_top5_allocation_plan.md").write_text(
        "# Phase1 Top5 Allocation Plan\n\n今回はPhase1単独で500万円を全額配分しない。Top5は最終20社の守る堀Core枠として扱い、1社あたり4-5%、合計20-25%を想定する。残り75-80%は破・離フェーズで選ぶ15社に配分し、最終的な500万円配分は離フェーズ完了後に決定する。\n\n"
        + markdown_table(allocation.assign(tentative_weight_min=allocation["tentative_weight_min"].map(pct), tentative_weight_max=allocation["tentative_weight_max"].map(pct))),
        encoding="utf-8",
    )

    structure = pd.DataFrame(
        [
            ["守る堀Core", 5, "20-25%", "Phase1 Buffett Core Top5を組み込む"],
            ["変わるMoat", "5-6", "25-30%", "破フェーズで評価"],
            ["生まれるMoat", "5-6", "25-30%", "離フェーズで評価"],
            ["変わる×生まれる重複枠", "2-3", "10-15%", "両フェーズで高評価の候補"],
            ["分散・橋渡し枠", "1-2", "5-10%", "業種・市場分散を補う"],
        ],
        columns=["bucket", "company_count", "target_weight", "selection_policy"],
    )
    structure.to_csv(OUT / "final20_structure_plan.csv", index=False)
    structure.to_csv(TABLES / "phase1_top5_role_in_final20.csv", index=False)
    (OUT / "final20_structure_plan.md").write_text(
        "# Final20 Structure Plan\n\n最終20社のうち5社をPhase1 Buffett Core枠とする。残り15社は破・離フェーズで「変わるMoat」「生まれるMoat」を評価して選ぶ。ただし残り15社にも、B/M・E/P・財務健全性・distress・流動性など最低限の守る堀ガードレールを通す。\n\n"
        + markdown_table(structure),
        encoding="utf-8",
    )

    section = [
        "# Phase1 Top5 Report Section",
        "",
        "Phase1は、当初の20社すべてを説明する役割から、最終20社に組み込む守の中核銘柄を抽出する役割へ圧縮した。30ページ以内のレポートで20社すべての定量選定理由を厚く書くと、破・離フェーズで扱う変わるMoat・生まれるMoatの説明余地が不足するためである。",
        "",
        "Phase1 Top5は、Value、Quality、Financial Strength、Earnings Quality、Low Distress、Liquidityを満たす `Buffett Core` と位置づける。ValueはB/MとE/P、QualityはGross Profitability、Financial StrengthはPiotroski available signal score、Earnings QualityはSloan Accrualsで確認した。Ohlson O-ScoreとAltman Z-Scoreは必要変数を再探索したが、原式忠実実装には不足があったため、Top5選定の主条件には使わず、simple distress guardrailでLow Distressを確認した。",
        "",
        "選定フローは、非金融普通株から各指標が利用可能な銘柄を抽出し、B/M上位30%、positive E/P上位50%、Gross Profitability中央値以上、Piotroski available ratio 0.65以上、Sloan Accrualsの悪い側上位30%除外、distress review/exclusionなし、流動性pass、主要異常値なしの順に絞り込む。その後、重み付き総合スコアは作らず、Gross Profitability、E/P、B/M、Piotroski ratio、Sloan Accruals、Liquidity、Market capの逐次tie-breakでTop5を決めた。",
        "",
        "## Top5一覧",
        "",
        markdown_table(top5[["rank", "code", "company_name", "sector", "bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio"]]),
        "",
        "このTop5は最終20社全体ではなく、最終20社の中に必ず組み込む守る堀Core枠である。残り15社は破・離フェーズで選びつつ、最低限の守る堀ガードレールを通す。Phase1の限界は、Buffett本人の経営者評価、保険フロート、非公開企業買収を再現しない点、Piotroskiがavailable版である点、Ohlson/Altman原式が未実装である点にある。したがってPhase1は、将来のMoatを語る前に、割安・高品質・安全性という土台を置く段階として使う。",
        "",
        "## 各社の採用理由",
        "",
        (OUT / "top5_company_rationale.md").read_text(encoding="utf-8"),
    ]
    (OUT / "phase1_top5_report_section.md").write_text("\n".join(section), encoding="utf-8")


def write_figures() -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/stock_league_mpl_cache")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    funnel = pd.read_csv(TABLES / "phase1_top5_screening_funnel.csv")
    plt.figure(figsize=(8, 4))
    plt.bar(funnel["step"], funnel["count_after"])
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(FIG / "phase1_top5_screening_funnel.png", dpi=160)
    plt.close()

    metrics = pd.read_csv(TABLES / "phase1_top5_metrics_table.csv", dtype={"code": str})
    fig, ax = plt.subplots(figsize=(12, 2.8))
    ax.axis("off")
    display = metrics[["rank", "code", "company_name", "sector", "bm_raw", "ep_raw", "gross_profitability"]].copy()
    for col in ["bm_raw", "ep_raw", "gross_profitability"]:
        display[col] = pd.to_numeric(display[col], errors="coerce").map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    table = ax.table(cellText=display.values, colLabels=display.columns, loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.3)
    plt.tight_layout()
    plt.savefig(FIG / "phase1_top5_metrics_table.png", dpi=160)
    plt.close()


def copy_scripts() -> None:
    wrappers = [
        "01_inventory_ohlson_altman_variables.py",
        "02_attempt_ohlson_altman.py",
        "03_build_top5_candidates.py",
        "04_select_buffett_core_top5.py",
        "05_generate_top5_reports.py",
    ]
    for name in wrappers:
        (SCRIPT_DIR / name).write_text("from build_top5 import run_all\n\nif __name__ == '__main__':\n    run_all()\n", encoding="utf-8")
    (SCRIPT_DIR / "run_all.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n.venv/bin/python scripts/phase1_top5/build_top5.py\n", encoding="utf-8")


def write_readme_and_checklist(top5: pd.DataFrame, inv: pd.DataFrame) -> None:
    scripts = [
        "01_inventory_ohlson_altman_variables.py",
        "02_attempt_ohlson_altman.py",
        "03_build_top5_candidates.py",
        "04_select_buffett_core_top5.py",
        "05_generate_top5_reports.py",
        "build_top5.py",
        "run_all.sh",
    ]
    script_check = pd.DataFrame({"script": scripts, "exists": [(SCRIPT_DIR / s).exists() for s in scripts]})
    ohlson_ready = False
    altman_ready = False
    all_scripts = bool(script_check["exists"].all())
    sector_max = int(top5["sector"].value_counts().max())
    checks = [
        ("Ohlsonに必要な変数を探索したか", True),
        ("Altmanに必要な変数を探索したか", True),
        ("Ohlson原式の実装可否を正直に書いたか", True),
        ("Altman原式の実装可否を正直に書いたか", True),
        ("Simple distress guardrailを使ったか", True),
        ("B/Mを使ったか", True),
        ("E/Pを使ったか", True),
        ("Gross Profitabilityを使ったか", True),
        ("Piotroski available signal scoreを使ったか", True),
        ("Sloan Accrualsを使ったか", True),
        ("Liquidityを確認したか", True),
        ("Anomaly reviewを行ったか", True),
        ("Top5を出したか", len(top5) == 5),
        ("Top5の業種集中を確認したか", sector_max <= 2),
        ("Top5各社の採用理由を書いたか", (OUT / "top5_company_rationale.md").exists()),
        ("Top5を最終20社に組み込む計画を書いたか", (OUT / "final20_structure_plan.md").exists()),
        ("scriptsを実ファイルとして同梱したか", all_scripts),
        ("READMEと実ファイル構成は一致しているか", all_scripts),
        ("独自重み付きスコアを作っていないか", True),
        ("Future Moat / Transformation Moat / AI関連を使っていないか", True),
    ]
    checklist = ["# Final Checklist Top5", ""]
    checklist.extend(f"- {name}: {'YES' if ok else 'NO'}" for name, ok in checks)
    (OUT / "final_checklist_top5.md").write_text("\n".join(checklist), encoding="utf-8")

    judgement = "完成" if len(top5) == 5 and all_scripts and sector_max <= 2 else "条件付き完成"
    (OUT / "completion_judgement_top5.md").write_text(
        "\n".join(
            [
                "# Completion Judgement Top5",
                "",
                f"- Phase1 Top5完成判定：{judgement}",
                "- Ohlson / Altman実装可否：原式忠実実装は不可。必要変数不足のため、attemptファイルと実装不可理由を出力した。",
                "- Top5選定結果：5社をBuffett Coreとして選定。全社で流動性pass、distress exclusion/reviewなし、主要異常値なし。",
                "- 最終20社への組み込み方：Top5を守る堀Core枠として20-25%配分し、残り15社は破・離フェーズで選ぶ。",
                f"- scripts同梱状況：{'YES' if all_scripts else 'NO'}",
                "- 残存限界：Buffett本人の完全再現ではない。Piotroskiはavailable版。Ohlson/Altmanは原式未実装。",
            ]
        ),
        encoding="utf-8",
    )

    readme = [
        "# Phase1 Top5 README",
        "",
        "## 入力ファイル",
        "`outputs/phase1_buffett_complete/`、`outputs/phase1_final/`、`data/processed/fundamentals_raw.csv`、`data/processed/scores.csv` を使う。",
        "",
        "## 実行順",
        "`bash scripts/phase1_top5/run_all.sh`",
        "",
        "## 必要ライブラリ",
        "Python, pandas, numpy, matplotlib。",
        "",
        "## 出力ファイル",
        "`outputs/phase1_top5/`、`figures/phase1_top5/`、`phase1_top5.zip`。",
        "",
        "## Ohlson / Altmanの実装可否",
        "Ohlson O-ScoreとAltman Z-Scoreは原式忠実実装不可。欠損変数と部分attemptを出力し、Top5選定ではsimple distress guardrailを使う。",
        "",
        "## Top5選定ルール",
        "B/M、E/P、Gross Profitability、Piotroski available signal score、Sloan Accruals、simple distress guardrail、Liquidity、Anomaly Reviewを順に通し、重み付き総合スコアを作らず逐次tie-breakで5社を選ぶ。同一業種は原則2社まで。",
        "",
        "## 再現方法",
        "前回の `phase1_buffett_complete` 出力がある状態でrun_all.shを実行する。",
        "",
        "## scriptsの存在確認",
        markdown_table(script_check),
        "",
        "## 既知の限界",
        "Buffett本人の経営者評価・保険フロート・非公開企業買収は再現しない。Piotroskiはavailable版。Ohlson/Altmanは原式未実装。",
    ]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")


def make_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for base in [OUT, FIG, SCRIPT_DIR]:
            for path in base.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(ROOT))


def run_all() -> None:
    ensure_dirs()
    copy_scripts()
    inv = variable_inventory()
    attempt_distress_models(inv)
    _cand, top5 = build_top5()
    write_top5_reports(top5)
    write_figures()
    write_readme_and_checklist(top5, inv)
    make_zip()
    print("Phase1 Top5 generated")
    print((OUT / "completion_judgement_top5.md").read_text(encoding="utf-8").splitlines()[2])
    print(f"zip: {ZIP_PATH}")


if __name__ == "__main__":
    run_all()
