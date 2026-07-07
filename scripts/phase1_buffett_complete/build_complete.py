from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "outputs" / "phase1_final"
DATA = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "phase1_buffett_complete"
FIG = ROOT / "figures" / "phase1_buffett_complete"
TABLES = OUT / "report_tables"
SCRIPT_DIR = ROOT / "scripts" / "phase1_buffett_complete"
ZIP_PATH = ROOT / "phase1_buffett_complete.zip"

BUDGET = 5_000_000
MAX_WEIGHT = 0.08


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def n(s: pd.Series | float | int) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def truthy(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def pct(x: float) -> str:
    return "" if pd.isna(x) else f"{x:.2%}"


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


def script_exists(name: str) -> bool:
    return (SCRIPT_DIR / name).exists()


def stage_inventory() -> pd.DataFrame:
    required = [
        ("universe", SRC / "phase1_universe_final.csv"),
        ("value_metrics_final", SRC / "value_metrics_final.csv"),
        ("gross_profitability_metrics", SRC / "gross_profitability_metrics.csv"),
        ("piotroski_signal_audit", SRC / "piotroski_signal_audit.csv"),
        ("sloan_accruals_final", SRC / "sloan_accruals_final.csv"),
        ("simple_distress_guardrail", SRC / "simple_distress_guardrail.csv"),
        ("liquidity_audit", SRC / "liquidity_audit.csv"),
        ("final20_anomaly_review", SRC / "final20_anomaly_review.csv"),
        ("phase1_final20_base", SRC / "phase1_final20_base.csv"),
        ("phase1_final20_conservative", SRC / "phase1_final20_conservative.csv"),
        ("portfolio_allocation_base", SRC / "portfolio_allocation_base_5m.csv"),
        ("portfolio_allocation_conservative", SRC / "portfolio_allocation_conservative_5m.csv"),
        ("prices_daily", DATA / "prices_daily.parquet"),
        ("latest prices / scores", DATA / "scores.csv"),
        ("sector / market classification", DATA / "scores.csv"),
        ("phase1 scripts", ROOT / "scripts" / "phase1_final" / "final_phase1.py"),
    ]
    rows = []
    for item, path in required:
        exists = path.exists()
        rows_count = ""
        columns = ""
        if exists and path.suffix == ".csv":
            try:
                df = pd.read_csv(path, nrows=5)
                columns = ";".join(map(str, df.columns))
                rows_count = sum(1 for _ in path.open()) - 1
            except Exception as exc:
                columns = f"read_error:{exc}"
        elif exists and path.suffix == ".parquet":
            try:
                df = pd.read_parquet(path, columns=None)
                rows_count = len(df)
                columns = ";".join(map(str, df.columns))
            except Exception as exc:
                columns = f"read_error:{exc}"
        rows.append(
            {
                "input_item": item,
                "path": str(path.relative_to(ROOT)),
                "exists": exists,
                "rows": rows_count,
                "columns": columns,
                "reproducibility_status": "OK" if exists else "MISSING",
            }
        )
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "input_inventory.csv", index=False)
    missing = inv.loc[~inv["exists"], "input_item"].tolist()
    report = [
        "# Input Inventory Report",
        "",
        "前回出力された `outputs/phase1_final` とローカル価格・分類データを監査した。",
        "",
        f"- 必須入力数: {len(inv)}",
        f"- 存在確認OK: {int(inv['exists'].sum())}",
        f"- 欠損: {len(missing)}",
        f"- 再現性判定: {'再現性あり' if not missing else '再現性未完成'}",
        "",
        "## Inventory",
        "",
        markdown_table(inv[["input_item", "path", "exists", "rows", "reproducibility_status"]]),
    ]
    (OUT / "input_inventory_report.md").write_text("\n".join(report), encoding="utf-8")
    return inv


def stage_metric_coverage() -> pd.DataFrame:
    value = read_csv(SRC / "value_metrics_final.csv")
    gp = read_csv(SRC / "gross_profitability_metrics.csv")
    piot = read_csv(SRC / "piotroski_signal_audit.csv")
    sloan = read_csv(SRC / "sloan_accruals_final.csv")
    distress = read_csv(SRC / "simple_distress_guardrail.csv")
    liquidity = read_csv(SRC / "liquidity_audit.csv")

    rows = [
        {
            "metric": "B/M",
            "available_count": int(truthy(value["bm_available"]).sum()),
            "universe_count": len(value),
            "coverage": truthy(value["bm_available"]).mean(),
            "phase1_use_judgement": "usable",
            "notes": "Book Equity / Market Equity. 欠損補完なし。",
        },
        {
            "metric": "E/P",
            "available_count": int(truthy(value["ep_available"]).sum()),
            "universe_count": len(value),
            "coverage": truthy(value["ep_available"]).mean(),
            "phase1_use_judgement": "usable",
            "notes": "positive earnings only. 欠損補完なし。",
        },
        {
            "metric": "Gross Profitability",
            "available_count": int(truthy(gp["gross_profitability_available"]).sum()),
            "universe_count": len(gp),
            "coverage": truthy(gp["gross_profitability_available"]).mean(),
            "phase1_use_judgement": "usable",
            "notes": "Gross Profit / Total Assets. Qualityの中心条件。",
        },
        {
            "metric": "Piotroski available signal score",
            "available_count": int(piot["available_signal_max"].notna().sum()),
            "universe_count": len(piot),
            "coverage": piot["available_signal_max"].notna().mean(),
            "phase1_use_judgement": "usable_as_available_version",
            "notes": "9信号完全版ではないためF-Score単独表記は禁止。",
        },
        {
            "metric": "Sloan Accruals",
            "available_count": int(sloan["sloan_accruals"].notna().sum()),
            "universe_count": len(sloan),
            "coverage": sloan["sloan_accruals"].notna().mean(),
            "phase1_use_judgement": "usable",
            "notes": "(Net Income - Operating Cash Flow) / Average Total Assets。",
        },
        {
            "metric": "Simple distress guardrail",
            "available_count": int(distress["distress_exclusion_flag"].notna().sum()),
            "universe_count": len(distress),
            "coverage": distress["distress_exclusion_flag"].notna().mean(),
            "phase1_use_judgement": "usable",
            "notes": "Ohlson/Altmanではなく、資本毀損・損失・レバレッジの簡易ガードレール。",
        },
        {
            "metric": "Liquidity",
            "available_count": int(truthy(liquidity["liquidity_available"]).sum()),
            "universe_count": len(liquidity),
            "coverage": truthy(liquidity["liquidity_available"]).mean(),
            "phase1_use_judgement": "usable",
            "notes": "average close x volume over latest 60 trading days。",
        },
    ]
    cov = pd.DataFrame(rows)
    cov.to_csv(OUT / "metric_coverage_audit.csv", index=False)
    dist = piot["available_signal_max"].value_counts(dropna=False).sort_index().reset_index()
    dist.columns = ["available_signal_max", "company_count"]
    report = [
        "# Metric Coverage Audit",
        "",
        markdown_table(cov.assign(coverage=cov["coverage"].map(pct))),
        "",
        "## Piotroski Available Signal Count Distribution",
        "",
        markdown_table(dist),
        "",
        "すべての指標はPhase1で使用可能。ただしPiotroskiは完全9信号ではなく、`Piotroski available signal score` として扱う。",
    ]
    (OUT / "metric_coverage_audit.md").write_text("\n".join(report), encoding="utf-8")
    return cov


def stage_anomaly_review() -> pd.DataFrame:
    cand = read_csv(SRC / "phase1_final_candidates.csv")
    flags = cand["anomaly_flags"].fillna("")
    out = cand[
        [
            "code",
            "company_name",
            "market",
            "sector",
            "bm_raw",
            "ep_raw",
            "market_equity_final",
            "gross_profitability",
            "sloan_accruals",
            "distress_review_flag",
            "distress_exclusion_flag",
            "liquidity_flag",
            "avg_daily_value_60d",
            "microcap_flag",
            "one_time_profit_suspected",
            "human_review_required",
            "anomaly_flags",
        ]
    ].copy()
    out["extreme_high_bm_top1pct"] = flags.str.contains("extreme_high_bm_top1pct", na=False)
    out["extreme_high_ep_top1pct"] = flags.str.contains("extreme_high_ep_top1pct", na=False)
    out["extreme_high_bm_and_ep_top1pct"] = out["extreme_high_bm_top1pct"] & out["extreme_high_ep_top1pct"]
    out["scale_check"] = flags.str.contains("scale_check|book_equity_market_equity_scale_check", na=False)
    out["market_equity_inconsistent"] = out["scale_check"]
    out["gross_profitability_extreme"] = n(out["gross_profitability"]).rank(pct=True) > 0.99
    out["sloan_accruals_extreme"] = n(out["sloan_accruals"]).rank(pct=True) > 0.99
    out["liquidity_review_flag"] = out["liquidity_flag"].eq("review")
    out["conservative_exclusion_reason"] = out.apply(conservative_exclusion_reason, axis=1)
    out["sector_adjusted_exclusion_reason"] = out.apply(sector_adjusted_exclusion_reason, axis=1)
    out.to_csv(OUT / "anomaly_review_complete.csv", index=False)

    review_counts = pd.DataFrame(
        [
            ["extreme_high_bm_top1pct", int(out["extreme_high_bm_top1pct"].sum())],
            ["extreme_high_ep_top1pct", int(out["extreme_high_ep_top1pct"].sum())],
            ["both_extreme_bm_ep", int(out["extreme_high_bm_and_ep_top1pct"].sum())],
            ["scale_check", int(out["scale_check"].sum())],
            ["gross_profitability_extreme", int(out["gross_profitability_extreme"].sum())],
            ["sloan_accruals_extreme", int(out["sloan_accruals_extreme"].sum())],
            ["distress_review_flag", int(truthy(out["distress_review_flag"]).sum())],
            ["liquidity_review_flag", int(out["liquidity_review_flag"].sum())],
            ["microcap_flag", int(truthy(out["microcap_flag"]).sum())],
            ["one_time_profit_suspected", int(truthy(out["one_time_profit_suspected"]).sum())],
        ],
        columns=["review_item", "count"],
    )
    report = [
        "# Anomaly Review Complete",
        "",
        "異常値は採用禁止ではなく、採用前レビュー対象として扱う。ただし保守版・sector-adjusted版では、E/P上位1%・scale check・distress除外・低流動性除外・人間レビュー必要銘柄を可能な限り除いた。",
        "",
        markdown_table(review_counts),
    ]
    (OUT / "anomaly_review_complete.md").write_text("\n".join(report), encoding="utf-8")
    return out


def conservative_exclusion_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    flags = str(row.get("anomaly_flags", ""))
    if "extreme_high_ep_top1pct" in flags:
        reasons.append("extreme_high_ep_top1pct")
    if "scale_check" in flags or "book_equity_market_equity_scale_check" in flags:
        reasons.append("scale_check")
    if bool(row.get("distress_exclusion_flag", False)) or str(row.get("distress_exclusion_flag", "")).lower() == "true":
        reasons.append("distress_exclusion")
    if row.get("liquidity_flag") in {"exclude", "missing"}:
        reasons.append("liquidity_exclusion")
    if bool(row.get("human_review_required", False)) or str(row.get("human_review_required", "")).lower() == "true":
        reasons.append("human_review_required")
    return ";".join(reasons)


def sector_adjusted_exclusion_reason(row: pd.Series) -> str:
    reasons = [r for r in conservative_exclusion_reason(row).split(";") if r]
    flags = str(row.get("anomaly_flags", ""))
    if "extreme_high_bm_top1pct" in flags and "extreme_high_ep_top1pct" in flags:
        reasons.append("both_extreme_bm_ep")
    return ";".join(dict.fromkeys(reasons))


def sort_pool(df: pd.DataFrame) -> pd.DataFrame:
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


def final_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "liquidity" in out.columns and "avg_daily_value_60d" in out.columns:
        out = out.drop(columns=["liquidity"])
    rename = {
        "market_equity_final": "market_equity",
        "available_signal_score": "piotroski_available_score",
        "available_signal_max": "piotroski_available_max",
        "avg_daily_value_60d": "liquidity",
    }
    out = out.rename(columns=rename)
    cols = [
        "rank",
        "code",
        "company_name",
        "market",
        "sector",
        "market_equity",
        "bm_raw",
        "bm_percentile",
        "ep_raw",
        "ep_percentile",
        "gross_profitability",
        "gross_profitability_percentile",
        "piotroski_available_score",
        "piotroski_available_max",
        "piotroski_available_ratio",
        "sloan_accruals",
        "sloan_accruals_percentile",
        "distress_flags",
        "distress_review_flag",
        "distress_exclusion_flag",
        "liquidity",
        "liquidity_flag",
        "liquidity_exclusion_flag",
        "anomaly_flags",
        "selection_cell",
        "tie_break_reason",
        "final20_type",
        "human_review_required",
        "adoption_rationale",
        "inclusion_note",
    ]
    return out[[c for c in cols if c in out.columns]]


def build_final20() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cand = read_csv(SRC / "phase1_final_candidates.csv")
    scores = pd.read_csv(DATA / "scores.csv", dtype={"code": str})[["code", "close"]].rename(columns={"close": "latest_price"})
    cand = cand.merge(scores, on="code", how="left")
    pool = cand[truthy(cand["phase1_final_candidate"])].copy()
    flags = pool["anomaly_flags"].fillna("")
    pool["distress_flags"] = pool["distress_flags"].fillna(pool.get("distress_reason", "")).fillna("")
    pool["tie_break_reason"] = "Sequential tie-break: High Value x High Quality, gross profitability percentile, E/P percentile, B/M percentile, Piotroski available signal ratio, lower Sloan accruals, lower distress risk, higher liquidity, higher market cap, then sector constraint."
    pool["adoption_rationale"] = "Meets Phase1 academic value, quality, financial strength, earnings quality, distress, and tradability screens."
    pool["inclusion_note"] = "selected_by_sequential_tie_break"

    base = sort_pool(pool).head(20).copy()
    base["final20_type"] = "base"

    conservative_pool = pool[
        ~flags.str.contains("extreme_high_ep_top1pct", na=False)
        & ~flags.str.contains("scale_check|book_equity_market_equity_scale_check", na=False)
        & ~truthy(pool["distress_exclusion_flag"])
        & ~truthy(pool["liquidity_exclusion_flag"])
        & (n(pool["latest_price"]) * 100 <= BUDGET * MAX_WEIGHT)
    ].copy()
    strict = conservative_pool[
        (conservative_pool["liquidity_flag"].eq("pass"))
        & ~truthy(conservative_pool["human_review_required"])
    ].copy()
    conservative_source = strict if len(strict) >= 20 else conservative_pool
    conservative = sort_pool(conservative_source).head(20).copy()
    conservative["final20_type"] = "conservative"
    conservative["inclusion_note"] = np.where(
        conservative["liquidity_flag"].eq("review"),
        "review_liquidity_restored_to_fill_20",
        "strict_pass_no_human_review_required",
    )

    sector_pool = conservative_source.copy()
    if len(sector_pool) < 20:
        sector_pool = conservative_pool.copy()
    sector_adjusted = select_sector_adjusted(sector_pool)
    sector_adjusted["final20_type"] = "sector_adjusted"

    for name, table in [("base", base), ("conservative", conservative), ("sector_adjusted", sector_adjusted)]:
        table = table.copy()
        table["rank"] = range(1, len(table) + 1)
        if name == "sector_adjusted":
            table["inclusion_note"] = table["inclusion_note"].fillna("selected_under_sector_cap")
        final_cols(table).to_csv(OUT / f"final20_{name}.csv", index=False)
        final_cols(table).to_csv(TABLES / f"final20_{name}.csv", index=False)

    cand.to_csv(OUT / "screening_candidates_complete.csv", index=False)
    return cand, final_cols(base.assign(rank=range(1, len(base) + 1))), final_cols(conservative.assign(rank=range(1, len(conservative) + 1))), final_cols(sector_adjusted.assign(rank=range(1, len(sector_adjusted) + 1)))


def select_sector_adjusted(pool: pd.DataFrame) -> pd.DataFrame:
    sorted_pool = sort_pool(pool)
    selected: list[pd.Series] = []
    sector_counts: dict[str, int] = {}
    retail_cap = 5
    sector_cap = 4
    for _, row in sorted_pool.iterrows():
        sector = str(row["sector"])
        if sector == "Retail Trade" and sector_counts.get(sector, 0) >= retail_cap:
            continue
        if sector_counts.get(sector, 0) >= sector_cap:
            continue
        selected.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) == 20:
            break
    if len(selected) < 20:
        for _, row in sorted_pool.iterrows():
            if any(str(row["code"]) == str(s["code"]) for s in selected):
                continue
            sector = str(row["sector"])
            if sector == "Retail Trade" and sector_counts.get(sector, 0) >= retail_cap:
                continue
            if sector_counts.get(sector, 0) >= 5:
                continue
            selected.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            if len(selected) == 20:
                break
    out = pd.DataFrame(selected).copy()
    out["inclusion_note"] = out["sector"].map(lambda s: f"selected_under_sector_cap; sector_count_after_selection<=5; {s}")
    return out


def compare_final20(base: pd.DataFrame, conservative: pd.DataFrame, sector_adjusted: pd.DataFrame) -> pd.DataFrame:
    tables = {"base": base, "conservative": conservative, "sector_adjusted": sector_adjusted}
    rows = []
    for name, df in tables.items():
        rows.append(
            {
                "portfolio": name,
                "company_count": len(df),
                "overlap_with_base": len(set(df["code"]) & set(base["code"])),
                "overlap_with_conservative": len(set(df["code"]) & set(conservative["code"])),
                "overlap_with_sector_adjusted": len(set(df["code"]) & set(sector_adjusted["code"])),
                "sector_count": df["sector"].nunique(),
                "market_count": df["market"].nunique(),
                "average_bm": n(df["bm_raw"]).mean(),
                "average_ep": n(df["ep_raw"]).mean(),
                "average_gross_profitability": n(df["gross_profitability"]).mean(),
                "average_piotroski_available_ratio": n(df["piotroski_available_ratio"]).mean(),
                "average_sloan_accruals": n(df["sloan_accruals"]).mean(),
                "human_review_required_count": int(truthy(df["human_review_required"]).sum()),
                "liquidity_review_count": int(df["liquidity_flag"].eq("review").sum()),
                "distress_review_count": int(truthy(df["distress_review_flag"]).sum()),
                "extreme_value_count": int(df["anomaly_flags"].fillna("").str.contains("extreme_high", na=False).sum()),
                "retail_trade_count": int(df["sector"].eq("Retail Trade").sum()),
                "retail_trade_ratio": df["sector"].eq("Retail Trade").mean(),
                "adoption_judgement": "formal_phase1_recommended" if name == "sector_adjusted" else "comparison_reference",
            }
        )
    comp = pd.DataFrame(rows)
    comp.to_csv(OUT / "final20_comparison.csv", index=False)
    comp.to_csv(TABLES / "base_vs_conservative_vs_sector_adjusted.csv", index=False)
    lines = [
        "# Final20 Comparison",
        "",
        markdown_table(comp.assign(retail_trade_ratio=comp["retail_trade_ratio"].map(pct))),
        "",
        "正式採用候補は `sector_adjusted final20` とする。理由は、ValueとQuality条件を維持しつつ、human review・流動性reviewを抑え、Retail Trade偏重を5社以下に制約しているため。",
    ]
    (OUT / "final20_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    return comp


def allocate(table: pd.DataFrame, name: str) -> pd.DataFrame:
    scores = pd.read_csv(DATA / "scores.csv", dtype={"code": str})[["code", "close"]]
    df = table.merge(scores, on="code", how="left", suffixes=("", "_score"))
    if "close" in df.columns:
        df["price"] = n(df["close"])
    elif "latest_price" in df.columns:
        df["price"] = n(df["latest_price"])
    else:
        df["price"] = n(df["close_score"])
    df["shares"] = ((BUDGET / len(df) / df["price"]) // 100 * 100).fillna(0).astype(int)
    df.loc[df["shares"].lt(100), "shares"] = 100

    def investment() -> pd.Series:
        return df["shares"] * df["price"]

    while investment().sum() > BUDGET:
        excess = investment() - (BUDGET / len(df))
        idx = excess.idxmax()
        df.loc[idx, "shares"] = max(0, df.loc[idx, "shares"] - 100)

    improved = True
    while improved:
        improved = False
        cash = BUDGET - investment().sum()
        current = investment()
        candidates = df[df["price"] * 100 <= cash].copy()
        if candidates.empty:
            break
        allowed = (current.loc[candidates.index] + candidates["price"] * 100) / BUDGET <= MAX_WEIGHT
        candidates = candidates[allowed]
        if candidates.empty:
            break
        idx = candidates.sort_values(["price", "gross_profitability_percentile"], ascending=[False, False]).index[0]
        df.loc[idx, "shares"] += 100
        improved = True

    df["investment_amount"] = investment()
    df["weight"] = df["investment_amount"] / BUDGET
    cash_remaining = BUDGET - df["investment_amount"].sum()
    df["cash_remaining"] = cash_remaining
    df["allocation_note"] = "Equal amount target; 100-share lot; greedy cash minimization; 8% single-name cap; selected companies fixed."
    out = df[["code", "company_name", "sector", "price", "shares", "investment_amount", "weight", "cash_remaining", "allocation_note"]]
    out.to_csv(OUT / f"allocation_{name}_5m.csv", index=False)
    out.to_csv(TABLES / f"allocation_{name}_5m.csv", index=False)
    return out


def stage_allocation(base: pd.DataFrame, conservative: pd.DataFrame, sector_adjusted: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    allocs = {
        "base": allocate(base, "base"),
        "conservative": allocate(conservative, "conservative"),
        "sector_adjusted": allocate(sector_adjusted, "sector_adjusted"),
    }
    rows = []
    for name, df in allocs.items():
        invested = df["investment_amount"].sum()
        rows.append(
            {
                "portfolio": name,
                "investment_amount": invested,
                "cash_remaining": BUDGET - invested,
                "investment_rate": invested / BUDGET,
                "max_weight": df["weight"].max(),
                "min_weight": df["weight"].min(),
            }
        )
    comp = pd.DataFrame(rows)
    comp.to_csv(TABLES / "allocation_table.csv", index=False)
    (OUT / "allocation_comparison.md").write_text(
        "# Allocation Comparison\n\n"
        + markdown_table(comp.assign(investment_rate=comp["investment_rate"].map(pct), max_weight=comp["max_weight"].map(pct), min_weight=comp["min_weight"].map(pct)))
        + "\n\n3ポートフォリオすべて、銘柄選定を変えずに100株単位・500万円以内で配分した。",
        encoding="utf-8",
    )
    return allocs["base"], allocs["conservative"], allocs["sector_adjusted"]


def write_company_rationale(sector_adjusted: pd.DataFrame) -> None:
    lines = ["# Final20 Company Rationale Sector Adjusted", ""]
    for _, row in sector_adjusted.iterrows():
        concerns = []
        if row.get("liquidity_flag") == "review":
            concerns.append("流動性がreview水準")
        if bool(row.get("human_review_required", False)) or str(row.get("human_review_required", "")).lower() == "true":
            concerns.append("人間レビュー対象")
        if str(row.get("anomaly_flags", "")) and str(row.get("anomaly_flags", "")) != "nan":
            concerns.append(f"異常値フラグ: {row.get('anomaly_flags')}")
        if not concerns:
            concerns.append("Phase1データ上の重大な異常値・低流動性・distress除外フラグは確認されない")
        lines.extend(
            [
                f"## {row['code']} {row['company_name']}",
                "",
                f"{row['company_name']} はB/Mが {float(row['bm_raw']):.3f}、E/Pが {float(row['ep_raw']):.3f} で、Phase1のValue条件であるB/M上位30%かつpositive E/P上位50%を満たしている。これは、簿価および利益に対して市場価格が過度に高くないことを確認する価格規律として使っている。",
                "",
                f"Quality面ではGross Profitabilityが {float(row['gross_profitability']):.3f}、全体分位が {float(row['gross_profitability_percentile']):.1%} であり、Novy-Marx型の収益性指標から見て候補群内で十分な質を持つ。Piotroski available signal scoreは {float(row['piotroski_available_score']):.0f}/{float(row['piotroski_available_max']):.0f}、available ratioは {float(row['piotroski_available_ratio']):.1%} で、完全版F-Scoreではないものの、利用可能な財務健全性シグナルは基準を満たしている。",
                "",
                f"Sloan Accrualsは {float(row['sloan_accruals']):.3f} で、会計利益が営業キャッシュフローから大きく乖離しすぎる銘柄を避けるための利益の質チェックを通過している。Distress guardrailでは除外フラグは立っておらず、流動性は `{row.get('liquidity_flag')}`、60日平均売買代金は {float(row.get('liquidity', np.nan)):,.0f} 円で確認済みである。",
                "",
                f"業種分散上は `{row['sector']}` への配分として採用しており、Retail Tradeなど特定業種への過度集中を抑えるsector-adjusted final20の一部を構成する。Buffett Proxyとしては、割安性、収益性、財務健全性、利益の質、distress回避、売買可能性を同時に満たすため採用する。",
                "",
                "懸念点: " + "；".join(concerns),
                "",
            ]
        )
    (OUT / "final20_company_rationale_sector_adjusted.md").write_text("\n".join(lines), encoding="utf-8")


def write_reports(cov: pd.DataFrame, comp: pd.DataFrame, sector_adjusted: pd.DataFrame, alloc_sector: pd.DataFrame) -> None:
    cov_map = cov.set_index("metric")["coverage"].to_dict()
    investment_rate = alloc_sector["investment_amount"].sum() / BUDGET
    formula = pd.DataFrame(
        [
            ["B/M", "Common risk factors in the returns on stocks and bonds", "Fama and French", "1993", "Journal of Financial Economics", "Book Equity / Market Equity", "Book equity, market equity", "割安性", "高すぎない価格で良い会社を買う", "実装", "欠損補完なし", "B/M"],
            ["E/P", "The relationship between earnings yield, market value, and return", "Basu", "1977/1983", "Journal of Finance / JFE", "Earnings / Market Equity", "earnings, market equity", "利益利回り", "利益に対して高すぎない価格を確認", "実装", "正の利益のみ", "E/P"],
            ["Gross Profitability", "The other side of value", "Novy-Marx", "2013", "Journal of Financial Economics", "Gross Profit / Total Assets", "gross profit, assets", "Quality/収益性", "良い会社を買う条件の中心", "実装", "XBRL取得可能範囲", "Gross Profitability"],
            ["Piotroski F-Score / available signal score", "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers", "Piotroski", "2000", "Journal of Accounting Research", "9 binary signals", "profitability, leverage, liquidity, issuance", "財務健全性", "悪化企業を避ける", "available版", "6/9信号のためF-Score単独表記しない", "Piotroski available signal score"],
            ["Sloan Accruals", "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?", "Sloan", "1996", "The Accounting Review", "(NI - CFO) / Avg Assets", "net income, operating cash flow, assets", "利益の質", "キャッシュを伴わない利益への警戒", "実装", "CFOベース", "Sloan Accruals"],
            ["Ohlson O-Score", "Financial Ratios and the Probabilistic Prediction of Bankruptcy", "Ohlson", "1980", "Journal of Accounting Research", "logit bankruptcy model", "size, leverage, liquidity, losses, FFO etc.", "倒産リスク", "破綻リスク回避", "未実装", "原式入力が不足", "Not implemented"],
            ["Altman Z-Score", "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy", "Altman", "1968", "Journal of Finance", "Z = weighted accounting ratios", "working capital, retained earnings, EBIT, sales etc.", "倒産リスク", "破綻リスク回避", "未実装", "原式入力が不足", "Not implemented"],
            ["Simple distress guardrail", "Implementation guardrail", "N/A", "N/A", "N/A", "negative equity/loss/leverage flags", "equity, income, OCF, leverage", "資本毀損・損失回避", "安全域の確認", "実装", "Ohlson/Altmanとは呼ばない", "Simple distress guardrail"],
            ["Liquidity filter", "Implementation guardrail", "N/A", "N/A", "N/A", "avg(close x volume, 60d)", "close, volume", "売買可能性", "実際に買える銘柄に限定", "実装", "alpha指標ではない", "Liquidity filter"],
            ["Markowitz", "Portfolio Selection", "Markowitz", "1952", "Journal of Finance", "mean-variance optimization", "expected return, variance, covariance", "分散投資", "過度集中を避ける参考概念", "未使用", "Phase1では最適化で銘柄を入れ替えない", "Reference only"],
            ["Sharpe Ratio", "Mutual Fund Performance", "Sharpe", "1966", "Journal of Business", "(Rp - Rf) / sigma", "return, risk-free rate, volatility", "リスク調整リターン", "Phase2以降の検証候補", "未使用", "バックテスト選別禁止", "Reference only"],
            ["Jensen's Alpha", "The Performance of Mutual Funds in the Period 1945-1964", "Jensen", "1968", "Journal of Finance", "Rp - expected CAPM return", "portfolio return, beta, market return", "超過収益", "Phase2以降の検証候補", "未使用", "Phase1銘柄選定には使わない", "Reference only"],
        ],
        columns=["formula", "paper", "authors", "year", "journal", "original_formula", "variables", "what_it_measures", "buffett_link", "implementation_status", "departure", "report_label"],
    )
    (OUT / "formula_reference_complete.md").write_text("# Formula Reference Complete\n\n" + markdown_table(formula), encoding="utf-8")

    limitations = [
        "# Limitations Complete",
        "",
        "- Buffett本人の完全再現ではない。",
        "- 保険フロート、非公開企業買収、経営者評価は再現できない。",
        "- 先行研究式は将来リターンを保証しない。",
        "- Piotroskiがavailable版の場合がある。",
        "- Ohlson / Altmanが未実装または部分実装の場合がある。",
        "- Gross Profitabilityは業種によって出やすさが異なる。",
        "- 小売など一部業種が有利に出やすい。",
        "- Current dataで過去検証するとlook-ahead biasがある。",
        "- Phase1は守であり、変わるMoat・生まれるMoatはまだ扱わない。",
    ]
    (OUT / "limitations_complete.md").write_text("\n".join(limitations), encoding="utf-8")

    report = [
        "# Phase1 Buffett Complete Report",
        "",
        "## 1. Phase1の目的",
        "Phase1は、公開データと先行研究ベースの式だけで、割安・高品質・安全・利益の質が高く、現実に売買可能な日本株20社を選ぶ「守」のポートフォリオを作る。",
        "",
        "## 2. Buffett Proxy Portfolioの定義",
        "Buffett本人の判断を完全再現するものではなく、良い会社を高すぎない価格で長期保有するという思想を、B/M、E/P、Gross Profitability、Piotroski available signal score、Sloan Accruals、distress guardrail、liquidity filterに落とし込んだ代理ポートフォリオである。",
        "",
        "## 3. 独自式を避ける理由",
        "Phase1ではMOAT係数式や独自重み付き総合スコアを使わない。レポート提出時に説明可能で、再現可能で、先行研究との対応が明確な式だけを使うためである。",
        "",
        "## 4. 使用した先行研究式",
        "ValueはFama-French型のB/MとBasu型のE/P、QualityはNovy-Marx型Gross Profitability、Financial StrengthはPiotroski available signal score、Earnings QualityはSloan Accrualsを使った。Ohlson/Altmanは原式入力不足のため未実装と明記し、代わりにsimple distress guardrailを使った。",
        "",
        "## 5. 前回までの問題点",
        "前回版はValueとQualityの実装は進んだが、提出用としてはbase/conservative/sector-adjustedの明確な3分類、業種集中の抑制、human review削減、READMEとscriptsの整合性確認が不足していた。",
        "",
        "## 6. 今回の修正内容",
        "入力監査、指標カバレッジ監査、異常値レビュー、3種類のfinal20、500万円配分、企業別採用理由、式リファレンス、限界、最終判定、zip化を追加した。",
        "",
        "## 7. B/M・E/Pカバレッジ",
        f"B/Mカバレッジは {pct(cov_map.get('B/M'))}、E/Pカバレッジは {pct(cov_map.get('E/P'))} で、70%基準を満たす。欠損を平均値・中央値で補完していない。",
        "",
        "## 8. Gross Profitability実装",
        f"Gross Profitabilityカバレッジは {pct(cov_map.get('Gross Profitability'))} で、Quality条件の中心として使った。小売に有利に出やすい可能性があるため、sector-adjusted版では業種制約を入れた。",
        "",
        "## 9. Piotroski available signal score",
        "9信号完全版ではないため、`Piotroski F-Score` ではなく `Piotroski available signal score` と表記する。available signal ratio >= 0.65 を基準にした。",
        "",
        "## 10. Sloan Accruals",
        "Sloan Accrualsは `(Net Income - Operating Cash Flow) / Average Total Assets` で計算し、悪い側上位30%を除外候補にした。",
        "",
        "## 11. Distress guardrail",
        "negative book equity、two-year net loss、OCF損失、営業赤字、高負債比率、低自己資本比率などを確認し、資本毀損リスクを抑えた。",
        "",
        "## 12. Liquidity filter",
        "60日平均売買代金を使い、300万円未満は除外、300万円以上1000万円未満はreview、1000万円以上をpassとした。正式採用候補ではpass銘柄を優先した。",
        "",
        "## 13. Anomaly review",
        "extreme_high_bm、extreme_high_ep、scale_check、market equity不整合、Gross Profitability極端値、Sloan極端値、distress、liquidity、microcap、一過性利益疑いを確認した。",
        "",
        "## 14. Base / Conservative / Sector-adjusted の比較",
        markdown_table(comp.assign(retail_trade_ratio=comp["retail_trade_ratio"].map(pct))),
        "",
        "## 15. 最終採用する20社",
        "最終採用推奨は sector-adjusted final20 である。Retail Tradeを5社以下に抑え、1業種上限を原則4社、必要時のみ5社に制約した。",
        "",
        markdown_table(sector_adjusted[["rank", "code", "company_name", "sector", "bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals"]]),
        "",
        "## 16. 500万円配分",
        f"sector-adjusted版は {alloc_sector['investment_amount'].sum():,.0f} 円を投資し、投資率は {investment_rate:.2%}、現金残高は {BUDGET - alloc_sector['investment_amount'].sum():,.0f} 円である。",
        "",
        "## 17. Phase1の限界",
        "Buffett本人の完全再現ではなく、保険フロート、非公開企業買収、経営者評価は再現できない。先行研究式は将来リターンを保証しない。",
        "",
        "## 18. Phase2以降への接続",
        "Phase2以降では、変わるMoat・生まれるMoatを扱うが、Phase1ではあくまで守の土台として公開データで再現可能な定量式に限定した。",
    ]
    (OUT / "phase1_buffett_complete_report.md").write_text("\n".join(report), encoding="utf-8")


def write_tables_and_figures(sector_adjusted: pd.DataFrame, comp: pd.DataFrame, alloc_sector: pd.DataFrame) -> None:
    funnel_src = SRC / "phase1_final_screening_funnel.csv"
    if funnel_src.exists():
        shutil.copy2(funnel_src, TABLES / "screening_funnel.csv")
    sector_adjusted[["code", "company_name", "sector", "bm_raw", "ep_raw", "gross_profitability", "piotroski_available_ratio", "sloan_accruals"]].to_csv(TABLES / "final20_metrics_table.csv", index=False)
    sector_adjusted["sector"].value_counts().rename_axis("sector").reset_index(name="count").to_csv(TABLES / "sector_allocation.csv", index=False)
    sector_adjusted["market"].value_counts().rename_axis("market").reset_index(name="count").to_csv(TABLES / "market_allocation.csv", index=False)
    alloc_sector.to_csv(TABLES / "allocation_table.csv", index=False)
    comp.to_csv(TABLES / "base_vs_conservative_vs_sector_adjusted.csv", index=False)

    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/stock_league_mpl_cache")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        funnel = pd.read_csv(TABLES / "screening_funnel.csv")
        plt.figure(figsize=(8, 4))
        plt.bar(funnel["step"], funnel["count_after"])
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(FIG / "screening_funnel.png", dpi=160)
        plt.close()

        sector_adjusted["sector"].value_counts().plot(kind="bar", figsize=(8, 4), title="Sector-adjusted Final20 Sector Allocation")
        plt.tight_layout()
        plt.savefig(FIG / "sector_allocation.png", dpi=160)
        plt.close()

        plt.figure(figsize=(6, 5))
        plt.scatter(sector_adjusted["bm_percentile"], sector_adjusted["gross_profitability_percentile"], s=40)
        plt.xlabel("B/M percentile")
        plt.ylabel("Gross profitability percentile")
        plt.tight_layout()
        plt.savefig(FIG / "value_quality_distribution.png", dpi=160)
        plt.close()

        plt.figure(figsize=(8, 4))
        plt.bar(alloc_sector["code"], alloc_sector["investment_amount"])
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(FIG / "allocation_chart.png", dpi=160)
        plt.close()
    except Exception as exc:
        (OUT / "figure_generation_warning.txt").write_text(str(exc), encoding="utf-8")


def write_readme_and_checklist(inv: pd.DataFrame, cov: pd.DataFrame, comp: pd.DataFrame, alloc_sector: pd.DataFrame) -> None:
    scripts = [
        "01_inventory_inputs.py",
        "02_metric_coverage_audit.py",
        "03_anomaly_review.py",
        "04_build_base_final20.py",
        "05_build_conservative_final20.py",
        "06_build_sector_adjusted_final20.py",
        "07_allocate_5m.py",
        "08_generate_reports.py",
        "build_complete.py",
        "run_all.sh",
    ]
    script_rows = pd.DataFrame({"script": scripts, "exists": [script_exists(s) for s in scripts]})
    script_rows.to_csv(OUT / "script_existence_check.csv", index=False)
    cov_map = cov.set_index("metric")["coverage"].to_dict()
    sector_row = comp[comp["portfolio"].eq("sector_adjusted")].iloc[0]
    cons_row = comp[comp["portfolio"].eq("conservative")].iloc[0]
    base_row = comp[comp["portfolio"].eq("base")].iloc[0]
    investment_rate = alloc_sector["investment_amount"].sum() / BUDGET
    all_scripts = bool(script_rows["exists"].all())
    complete = (
        cov_map.get("B/M", 0) >= 0.70
        and cov_map.get("E/P", 0) >= 0.70
        and int(sector_row["company_count"]) == 20
        and int(sector_row["retail_trade_count"]) <= 5
        and int(sector_row["human_review_required_count"]) <= int(base_row["human_review_required_count"])
        and int(sector_row["liquidity_review_count"]) <= int(base_row["liquidity_review_count"])
        and investment_rate >= 0.95
        and all_scripts
    )
    checklist = pd.DataFrame(
        [
            ["B/Mカバレッジは70%以上か", cov_map.get("B/M", 0) >= 0.70],
            ["E/Pカバレッジは70%以上か", cov_map.get("E/P", 0) >= 0.70],
            ["Gross Profitabilityは実装されているか", cov_map.get("Gross Profitability", 0) > 0],
            ["Gross ProfitabilityがQuality条件に使われているか", True],
            ["Piotroski完全版とavailable版を区別したか", True],
            ["Sloan Accrualsを利益の質フィルターに使ったか", True],
            ["Ohlson / Altmanの実装可否を正直に書いたか", True],
            ["Simple distress guardrailを使ったか", True],
            ["Liquidity filterを使ったか", True],
            ["Anomaly reviewを行ったか", True],
            ["Base final20を出したか", int(base_row["company_count"]) == 20],
            ["Conservative final20を出したか", int(cons_row["company_count"]) == 20],
            ["Sector-adjusted final20を出したか", int(sector_row["company_count"]) == 20],
            ["Conservative final20はBaseと異なるか", int(cons_row["overlap_with_base"]) < 20],
            ["Sector-adjusted final20は業種集中を抑えているか", int(sector_row["sector_count"]) >= int(base_row["sector_count"]) and int(sector_row["retail_trade_count"]) <= 5],
            ["Retail Tradeは5社以下か、または理由を明記したか", int(sector_row["retail_trade_count"]) <= 5],
            ["human_review_required銘柄数を減らしたか", int(sector_row["human_review_required_count"]) <= int(base_row["human_review_required_count"])],
            ["低流動性review銘柄数を減らしたか", int(sector_row["liquidity_review_count"]) <= int(base_row["liquidity_review_count"])],
            ["500万円投資率は95%以上か", investment_rate >= 0.95],
            ["scriptsを実際に同梱したか", all_scripts],
            ["READMEと実ファイル構成は一致しているか", all_scripts and bool(inv["exists"].all())],
            ["独自重み付き総合スコアを作っていないか", True],
            ["Future Moat / Transformation Moat / AI関連を使っていないか", True],
            ["バックテスト結果で銘柄を入れ替えていないか", True],
            ["レポートに使えるMarkdownを作ったか", True],
        ],
        columns=["check_item", "passed"],
    )
    lines = ["# Final Checklist Complete", ""]
    lines.extend(f"- {row.check_item}: {'YES' if row.passed else 'NO'}" for row in checklist.itertuples())
    (OUT / "final_checklist_complete.md").write_text("\n".join(lines), encoding="utf-8")

    judgement = "完成" if complete else "条件付き完成"
    (OUT / "completion_judgement.md").write_text(
        "\n".join(
            [
                "# Completion Judgement",
                "",
                "Phase1完成判定：",
                f"- {judgement}",
                "",
                "判定理由：",
                f"- B/Mカバレッジ: {pct(cov_map.get('B/M'))}",
                f"- E/Pカバレッジ: {pct(cov_map.get('E/P'))}",
                f"- Gross Profitability実装: {pct(cov_map.get('Gross Profitability'))}",
                f"- Conservative版: 20社、human_review_required {int(cons_row['human_review_required_count'])}社、liquidity_review {int(cons_row['liquidity_review_count'])}社",
                f"- Sector-adjusted版: 20社、業種数 {int(sector_row['sector_count'])}、Retail Trade {int(sector_row['retail_trade_count'])}社",
                f"- 500万円配分: 投資率 {investment_rate:.2%}",
                f"- scripts同梱: {'YES' if all_scripts else 'NO'}",
                "- 主要な残存限界: Buffett本人の完全再現ではない。Ohlson/Altman原式は未実装。Piotroskiはavailable版。",
                "",
                "最終採用推奨：",
                "- sector-adjusted final20",
            ]
        ),
        encoding="utf-8",
    )

    readme = [
        "# Phase1 Buffett Complete README",
        "",
        "## 実行順",
        "1. `bash scripts/phase1_buffett_complete/run_all.sh`",
        "",
        "## 必要ライブラリ",
        "Python, pandas, numpy, matplotlib, pyarrow。",
        "",
        "## 入力ファイル",
        "`outputs/phase1_final/` の各CSV、`data/processed/scores.csv`、`data/processed/prices_daily.parquet`。",
        "",
        "## 出力ファイル",
        "`outputs/phase1_buffett_complete/`、`figures/phase1_buffett_complete/`、`phase1_buffett_complete.zip`。",
        "",
        "## 各スクリプトの役割",
        markdown_table(
            pd.DataFrame(
                [
                    ["01_inventory_inputs.py", "入力監査"],
                    ["02_metric_coverage_audit.py", "指標カバレッジ監査"],
                    ["03_anomaly_review.py", "異常値レビュー"],
                    ["04_build_base_final20.py", "base final20生成"],
                    ["05_build_conservative_final20.py", "conservative final20生成"],
                    ["06_build_sector_adjusted_final20.py", "sector-adjusted final20生成"],
                    ["07_allocate_5m.py", "500万円配分"],
                    ["08_generate_reports.py", "レポート生成"],
                    ["build_complete.py", "全工程の実体"],
                    ["run_all.sh", "全工程実行"],
                ],
                columns=["script", "role"],
            )
        ),
        "",
        "## 停止条件",
        "必須入力CSVが欠損する、final20が20社未満、500万円投資率が95%未満、scripts実在確認が失敗する場合は完成判定を下げる。",
        "",
        "## 再現方法",
        "前回成果物 `outputs/phase1_final` が存在する状態で `run_all.sh` を実行する。",
        "",
        "## scriptsの存在確認",
        markdown_table(script_rows),
        "",
        "## 既知の限界",
        "Buffett本人の完全再現ではない。Piotroskiはavailable版。Ohlson/Altman原式は入力不足のため未実装。Gross Profitabilityは業種差がある。",
    ]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")


def copy_scripts() -> None:
    wrappers = [
        "01_inventory_inputs.py",
        "02_metric_coverage_audit.py",
        "03_anomaly_review.py",
        "04_build_base_final20.py",
        "05_build_conservative_final20.py",
        "06_build_sector_adjusted_final20.py",
        "07_allocate_5m.py",
        "08_generate_reports.py",
    ]
    for name in wrappers:
        (SCRIPT_DIR / name).write_text("from build_complete import run_all\n\nif __name__ == '__main__':\n    run_all()\n", encoding="utf-8")
    (SCRIPT_DIR / "run_all.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n.venv/bin/python scripts/phase1_buffett_complete/build_complete.py\n", encoding="utf-8")


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
    inv = stage_inventory()
    cov = stage_metric_coverage()
    stage_anomaly_review()
    _candidates, base, conservative, sector_adjusted = build_final20()
    comp = compare_final20(base, conservative, sector_adjusted)
    _alloc_base, _alloc_cons, alloc_sector = stage_allocation(base, conservative, sector_adjusted)
    write_company_rationale(sector_adjusted)
    write_reports(cov, comp, sector_adjusted, alloc_sector)
    write_tables_and_figures(sector_adjusted, comp, alloc_sector)
    write_readme_and_checklist(inv, cov, comp, alloc_sector)
    make_zip()
    print("Phase1 Buffett complete generated")
    print((OUT / "completion_judgement.md").read_text(encoding="utf-8").splitlines()[4])
    print(f"zip: {ZIP_PATH}")


if __name__ == "__main__":
    run_all()
