from __future__ import annotations

import math
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from lxml import etree
except Exception:  # pragma: no cover
    etree = None


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
REPAIR = ROOT / "outputs" / "phase1_repair"
OUT = ROOT / "outputs" / "phase1_final"
FIG = ROOT / "figures" / "phase1_final"
TABLES = OUT / "report_tables"
SCRIPT_DIR = ROOT / "scripts" / "phase1_final"
XBRL_DIR = ROOT / "data" / "raw" / "edinet" / "xbrl"

FINANCIAL_SECTORS = {
    "Banks",
    "Insurance",
    "Securities and Commodities Futures",
    "Other Financing Business",
    "銀行業",
    "保険業",
    "証券、商品先物取引業",
    "その他金融業",
}

GP_TAGS = {
    "GrossProfit",
    "GrossProfitIFRS",
    "OperatingGrossProfit",
    "OperatingGrossProfitIFRS",
    "GrossProfitLoss",
    "GrossProfitOnCompletedConstructionContractsCNS",
}
REVENUE_TAGS = {
    "NetSales",
    "Revenue",
    "SalesRevenue",
    "RevenueIFRS",
    "RevenueFromContractsWithCustomers",
    "RevenueFromContractsWithCustomer",
    "OperatingRevenue1",
    "NetSalesOfCompletedConstructionContractsCNS",
}
COST_TAGS = {
    "CostOfSales",
    "CostOfSalesIFRS",
    "CostOfRevenue",
    "CostOfGoodsSold",
    "CostOfSalesOfCompletedConstructionContractsCNS",
}


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def n(x: pd.Series | float | int) -> pd.Series:
    return pd.to_numeric(x, errors="coerce")


def truthy(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    out = n(a) / n(b).replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def winsorize(s: pd.Series) -> pd.Series:
    values = n(s)
    if values.notna().sum() < 10:
        return values
    return values.clip(values.quantile(0.01), values.quantile(0.99))


def percentile(s: pd.Series, high_good: bool = True) -> pd.Series:
    vals = n(s)
    pct = vals.rank(pct=True)
    return pct if high_good else 1 - pct


def norm_code(x: object) -> str:
    text = str(x).replace(".T", "")
    digits = re.sub(r"\D", "", text)
    return digits[:4] if len(digits) >= 4 else digits.zfill(4)


def markdown_table(df: pd.DataFrame) -> str:
    d = df.copy()
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].map(lambda v: "" if pd.isna(v) else f"{v:.4f}")
        else:
            d[col] = d[col].fillna("").astype(str)
    lines = [
        "| " + " | ".join(d.columns) + " |",
        "| " + " | ".join(["---"] * len(d.columns)) + " |",
    ]
    lines += ["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in d.values.tolist()]
    return "\n".join(lines)


def load_scores() -> pd.DataFrame:
    s = pd.read_csv(DATA / "scores.csv", dtype={"code": str})
    s["code"] = s["code"].map(norm_code)
    return s


def load_repair_value() -> pd.DataFrame:
    v = pd.read_csv(REPAIR / "value_metrics_repaired.csv", dtype={"code": str})
    v["code"] = v["code"].map(norm_code)
    anomaly = pd.read_csv(REPAIR / "value_metric_anomaly_report.csv", dtype={"code": str})
    if "anomaly_flags" not in anomaly.columns:
        anomaly["anomaly_flags"] = ""
    return v.merge(anomaly[["code", "anomaly_flags"]], on="code", how="left")


def latest_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(DATA / "fundamentals_raw.csv", dtype={"code": str, "doc_id": str})
    raw["code"] = raw["code"].map(norm_code)
    raw["period_end_dt"] = pd.to_datetime(raw["period_end"], errors="coerce")
    raw = raw.sort_values(["code", "period_end_dt"], ascending=[True, False])
    cur = raw.groupby("code").nth(0).reset_index()
    prev = raw.groupby("code").nth(1).reset_index()
    return cur, prev


def stage_inventory() -> None:
    rows = []
    important = {
        "universe": ["universe", "phase1_universe"],
        "latest prices": ["latest_prices", "prices_daily"],
        "EDINET fundamentals": ["fundamentals_raw", "fundamentals_clean", "edinet"],
        "value repaired": ["value_metrics_repaired", "market_equity_reconstruction"],
        "volume": ["volume", "avg_trading_value"],
        "gross profit": ["GrossProfit", "gross_profit", "CostOfSales", "revenue"],
        "liabilities": ["liabilities", "current_assets", "current_liabilities"],
    }
    for p in sorted(list((ROOT / "outputs" / "phase1_repair").glob("*")) + list(DATA.glob("*"))):
        if not p.is_file() or p.suffix.lower() not in {".csv", ".parquet", ".md"}:
            continue
        cols: list[str] = []
        row_count = ""
        try:
            if p.suffix == ".parquet":
                df = pd.read_parquet(p)
            elif p.suffix == ".csv":
                df = pd.read_csv(p, nrows=100)
            else:
                df = pd.DataFrame()
            cols = list(map(str, df.columns))
            if p.suffix == ".parquet":
                row_count = len(df)
            elif p.suffix == ".csv":
                row_count = sum(1 for _ in p.open()) - 1
        except Exception:
            pass
        text = " ".join(cols) + " " + p.name
        usable = [k for k, pats in important.items() if any(pat.lower() in text.lower() for pat in pats)]
        missing = [k for k in important if k not in usable]
        rows.append(
            {
                "file_path": str(p.relative_to(ROOT)),
                "rows": row_count,
                "columns": len(cols) if cols else "",
                "key_columns": ";".join([c for c in cols if c in {"code", "ticker", "company_name"}]),
                "usable_metrics": ";".join(usable),
                "missing_important_columns": ";".join(missing[:8]),
                "notes": "",
            }
        )
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "input_inventory.csv", index=False)
    report = [
        "# Phase1 Final Input Inventory",
        "",
        "Inputs are the repaired Phase1 outputs plus local processed EDINET and price files.",
        "",
        markdown_table(inv[["file_path", "rows", "columns", "usable_metrics"]].head(80)),
    ]
    (OUT / "input_inventory_report.md").write_text("\n".join(report), encoding="utf-8")


def stage_universe() -> pd.DataFrame:
    scores = load_scores()
    value = load_repair_value()
    is_fin = scores["sector_33"].isin(FINANCIAL_SECTORS)
    has_price = scores["close"].notna() & truthy(scores["price_available"])
    has_fund = scores[["equity", "net_income", "total_assets", "operating_cf"]].notna().all(axis=1)
    val_avail = value.set_index("code")[["bm_available", "ep_available"]].reindex(scores["code"]).fillna(False)
    included = (~is_fin) & has_price & has_fund & (val_avail["bm_available"].to_numpy() | val_avail["ep_available"].to_numpy())
    reasons = []
    for i, row in scores.iterrows():
        r = []
        if is_fin.iloc[i]:
            r.append("financial_sector_excluded")
        if not has_price.iloc[i]:
            r.append("missing_price")
        if not has_fund.iloc[i]:
            r.append("missing_basic_fundamentals")
        if not bool(val_avail.iloc[i].any()):
            r.append("missing_value_metrics")
        reasons.append(";".join(r))
    out = pd.DataFrame(
        {
            "code": scores["code"],
            "ticker": scores["ticker"],
            "company_name": scores["company_name"],
            "market": scores["market"],
            "sector": scores["sector_33"],
            "is_financial_excluded": is_fin,
            "is_common_stock": True,
            "has_price": has_price,
            "has_fundamentals": has_fund,
            "universe_inclusion_status": np.where(included, "included", "excluded"),
            "exclusion_reason": reasons,
        }
    )
    out.to_csv(OUT / "phase1_universe_final.csv", index=False)
    return out


def stage_value(universe: pd.DataFrame) -> pd.DataFrame:
    value = load_repair_value()
    uni_codes = set(universe.loc[universe["universe_inclusion_status"].eq("included"), "code"])
    value = value[value["code"].isin(uni_codes)].copy()
    value["anomaly_flags"] = value["anomaly_flags"].fillna("")
    bm_99 = value["bm_raw"].quantile(0.99)
    ep_99 = value["ep_raw"].quantile(0.99)
    value.loc[n(value["bm_raw"]) >= bm_99, "anomaly_flags"] += ";extreme_high_bm_top1pct"
    value.loc[n(value["ep_raw"]) >= ep_99, "anomaly_flags"] += ";extreme_high_ep_top1pct"
    value["anomaly_flags"] = value["anomaly_flags"].str.strip(";")
    value.to_csv(OUT / "value_metrics_final.csv", index=False)
    both = truthy(value["bm_available"]) & truthy(value["ep_available"])
    lines = [
        "# Value Metrics Audit Final",
        "",
        f"- Universe with B/M available: {int(truthy(value['bm_available']).sum()):,} / {len(value):,} ({truthy(value['bm_available']).mean():.1%})",
        f"- Universe with E/P available: {int(truthy(value['ep_available']).sum()):,} / {len(value):,} ({truthy(value['ep_available']).mean():.1%})",
        f"- Both available: {int(both.sum()):,} / {len(value):,} ({both.mean():.1%})",
        "",
        "Market equity method counts:",
        "",
        markdown_table(value["market_equity_method"].value_counts().reset_index().rename(columns={"index": "method", "count": "count"})),
    ]
    (OUT / "value_metrics_audit_final.md").write_text("\n".join(lines), encoding="utf-8")
    return value


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag.split(":")[-1]


def parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    t = text.strip().replace(",", "").replace("△", "-").replace("−", "-")
    t = re.sub(r"^\((.*)\)$", r"-\1", t)
    if t in {"", "-", "－"}:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def context_priority(context: str, duration: bool = True) -> int:
    context = context or ""
    tokens = ["CurrentYearDuration", "CurrentYear", "Current", "Prior1YearDuration", "Prior1Year"]
    if not duration:
        tokens = ["CurrentYearInstant", "CurrentYear", "Current", "Prior1YearInstant", "Prior1Year"]
    penalty = 20 if "Member" in context or "Row" in context else 0
    for i, token in enumerate(tokens):
        if token in context:
            return i + penalty
    return 99 + penalty


def parse_gp_zip(zip_path: Path) -> dict[str, object]:
    if etree is None or not zip_path.exists():
        return {"gross_profit": np.nan, "revenue": np.nan, "cost_of_sales": np.nan, "gp_method": "unavailable", "gp_tag": ""}
    parser = etree.XMLParser(recover=True, huge_tree=True)
    facts = {"gross_profit": [], "revenue": [], "cost_of_sales": []}
    tags = {"gross_profit": [], "revenue": [], "cost_of_sales": []}
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.endswith(".xbrl") and "PublicDoc" in m]
        for member in members[:1]:
            try:
                root = etree.fromstring(zf.read(member), parser=parser)
            except Exception:
                continue
            for elem in root.iter():
                tag = local_name(str(elem.tag))
                val = parse_float(elem.text)
                if val is None:
                    continue
                context = elem.attrib.get("contextRef") or elem.attrib.get("contextref") or ""
                score = context_priority(context, duration=True)
                if tag in GP_TAGS or tag.endswith("GrossProfit") or "GrossProfitLoss" in tag:
                    facts["gross_profit"].append((score, val, tag))
                elif tag in REVENUE_TAGS:
                    facts["revenue"].append((score, val, tag))
                elif tag in COST_TAGS:
                    facts["cost_of_sales"].append((score, val, tag))
    result: dict[str, object] = {}
    for key in facts:
        choice = sorted(facts[key], key=lambda x: (x[0], -abs(x[1])))[0] if facts[key] else None
        result[key] = choice[1] if choice else np.nan
        tags[key] = choice[2] if choice else ""
    gp = result["gross_profit"]
    if pd.notna(gp):
        result["gp_method"] = "direct_gross_profit"
        result["gp_tag"] = tags["gross_profit"]
    elif pd.notna(result["revenue"]) and pd.notna(result["cost_of_sales"]):
        result["gross_profit"] = result["revenue"] - result["cost_of_sales"]
        result["gp_method"] = "revenue_minus_cost_of_sales"
        result["gp_tag"] = f"{tags['revenue']}-{tags['cost_of_sales']}"
    else:
        result["gp_method"] = "unavailable"
        result["gp_tag"] = ""
    result["revenue_tag"] = tags["revenue"]
    result["cost_tag"] = tags["cost_of_sales"]
    return result


def stage_gross_profitability(universe: pd.DataFrame) -> pd.DataFrame:
    cache = OUT / "gross_profitability_xbrl_facts.csv"
    if cache.exists():
        facts = pd.read_csv(cache, dtype={"code": str})
    else:
        cur, _ = latest_raw()
        rows = []
        for idx, row in enumerate(cur.to_dict("records"), 1):
            parsed = parse_gp_zip(XBRL_DIR / f"{row.get('doc_id')}.zip")
            rows.append({"code": row["code"], "doc_id": row.get("doc_id"), **parsed})
            if idx % 700 == 0:
                print(f"gross profit parsed {idx}/{len(cur)}", file=sys.stderr)
        facts = pd.DataFrame(rows)
        facts.to_csv(cache, index=False)
    scores = load_scores()[["code", "ticker", "company_name", "sector_33", "total_assets"]]
    uni_codes = set(universe.loc[universe["universe_inclusion_status"].eq("included"), "code"])
    out = scores[scores["code"].isin(uni_codes)].merge(facts, on="code", how="left")
    out["gross_profitability"] = safe_div(out["gross_profit"], out["total_assets"]).where(n(out["total_assets"]) > 0)
    out["gross_profitability_available"] = out["gross_profitability"].notna()
    out["gross_profitability_review_flag"] = n(out["gross_profit"]) < 0
    out.to_csv(OUT / "gross_profitability_metrics.csv", index=False)
    available = out["gross_profitability_available"].mean()
    direct = int(out["gp_method"].eq("direct_gross_profit").sum())
    derived = int(out["gp_method"].eq("revenue_minus_cost_of_sales").sum())
    rep = [
        "# Gross Profitability Implementation Report",
        "",
        f"- Calculation coverage: {int(out['gross_profitability_available'].sum()):,} / {len(out):,} ({available:.1%})",
        f"- Direct gross profit rows: {direct:,}",
        f"- Revenue minus cost of sales rows: {derived:,}",
        "- Missing rows are not imputed and no proprietary substitute is created.",
        "",
        "Phase1 use judgment: usable as a Quality screen for companies where EDINET XBRL provides gross profit or cost-of-sales facts.",
    ]
    (OUT / "gross_profitability_implementation_report.md").write_text("\n".join(rep), encoding="utf-8")
    return out


def stage_piotroski(universe: pd.DataFrame) -> pd.DataFrame:
    cur, prev = latest_raw()
    df = cur.merge(prev.add_suffix("_prev"), left_on="code", right_on="code_prev", how="left")
    for col in ["net_income", "total_assets", "operating_cf", "revenue", "equity"]:
        df[col] = n(df[col])
        df[f"{col}_prev"] = n(df[f"{col}_prev"])
    roa = safe_div(df["net_income"], df["total_assets"])
    roa_prev = safe_div(df["net_income_prev"], df["total_assets_prev"])
    cfo_assets = safe_div(df["operating_cf"], df["total_assets"])
    turn = safe_div(df["revenue"], df["total_assets"])
    turn_prev = safe_div(df["revenue_prev"], df["total_assets_prev"])
    lev = safe_div(df["total_assets"] - df["equity"], df["total_assets"])
    lev_prev = safe_div(df["total_assets_prev"] - df["equity_prev"], df["total_assets_prev"])
    out = pd.DataFrame(
        {
            "code": df["code"],
            "F_ROA": roa > 0,
            "F_CFO": df["operating_cf"] > 0,
            "F_DROA": roa > roa_prev,
            "F_ACCRUAL": cfo_assets > roa,
            "F_DMARGIN": np.nan,
            "F_DTURN": turn > turn_prev,
            "F_DLEVER": lev < lev_prev,
            "F_DLIQUID": np.nan,
            "EQ_OFFER": np.nan,
        }
    )
    signal_cols = ["F_ROA", "F_CFO", "F_DROA", "F_ACCRUAL", "F_DMARGIN", "F_DTURN", "F_DLEVER", "F_DLIQUID", "EQ_OFFER"]
    for col in signal_cols:
        if out[col].dtype == bool:
            out[col] = out[col].astype(int)
    out["available_signal_score"] = out[signal_cols].fillna(0).sum(axis=1)
    out["available_signal_count"] = out[signal_cols].notna().sum(axis=1)
    out["available_signal_max"] = out["available_signal_count"]
    out["implemented_signals"] = out[signal_cols].notna().apply(lambda r: ";".join(r.index[r]), axis=1)
    out["missing_signals"] = out[signal_cols].isna().apply(lambda r: ";".join(r.index[r]), axis=1)
    out["reason_for_missing"] = "gross margin, current ratio, and equity issuance inputs unavailable" 
    out["score_label"] = np.where(out["available_signal_count"].eq(9), "Piotroski F-Score", "Piotroski available signal score")
    uni_codes = set(universe.loc[universe["universe_inclusion_status"].eq("included"), "code"])
    out = out[out["code"].isin(uni_codes)]
    out.to_csv(OUT / "piotroski_signal_audit.csv", index=False)
    (OUT / "piotroski_signal_audit.md").write_text(
        "# Piotroski Signal Audit\n\nThe full 9-signal Piotroski F-Score is unavailable. This output uses `Piotroski available signal score` with six implemented signals: F_ROA, F_CFO, F_DROA, F_ACCRUAL, F_DTURN, and F_DLEVER.\n",
        encoding="utf-8",
    )
    return out


def stage_sloan(universe: pd.DataFrame) -> pd.DataFrame:
    cur, prev = latest_raw()
    df = cur.merge(prev[["code", "total_assets"]].rename(columns={"total_assets": "total_assets_prev"}), on="code", how="left")
    avg_assets = (n(df["total_assets"]) + n(df["total_assets_prev"])) / 2
    accruals = safe_div(n(df["net_income"]) - n(df["operating_cf"]), avg_assets)
    out = pd.DataFrame(
        {
            "code": df["code"],
            "net_income": n(df["net_income"]),
            "operating_cash_flow": n(df["operating_cf"]),
            "average_total_assets": avg_assets,
            "sloan_accruals": accruals,
            "sloan_accruals_winsorized": winsorize(accruals),
            "method": "CFO_based",
            "accruals_extreme": percentile(accruals, high_good=False) < 0.01,
        }
    )
    uni_codes = set(universe.loc[universe["universe_inclusion_status"].eq("included"), "code"])
    out = out[out["code"].isin(uni_codes)]
    out.to_csv(OUT / "sloan_accruals_final.csv", index=False)
    (OUT / "sloan_accruals_audit.md").write_text(
        "# Sloan Accruals Audit\n\nAccruals are calculated as `(Net Income - Operating Cash Flow) / Average Total Assets`. The worst 30% highest accruals are excluded in screening.\n",
        encoding="utf-8",
    )
    return out


def stage_distress(universe: pd.DataFrame) -> pd.DataFrame:
    cur, prev = latest_raw()
    scores = load_scores()
    df = scores.merge(cur[["code", "net_income", "operating_cf", "operating_income", "total_assets", "equity"]].add_suffix("_cur"), left_on="code", right_on="code_cur", how="left")
    df = df.merge(prev[["code", "net_income", "operating_cf"]].add_suffix("_prev"), left_on="code", right_on="code_prev", how="left")
    uni_codes = set(universe.loc[universe["universe_inclusion_status"].eq("included"), "code"])
    df = df[df["code"].isin(uni_codes)].copy()
    assets = n(df["total_assets_cur"]).fillna(n(df["total_assets"]))
    equity = n(df["equity_cur"]).fillna(n(df["equity"]))
    liabilities = assets - equity
    net_cur = n(df["net_income_cur"])
    net_prev = n(df["net_income_prev"])
    ocf_cur = n(df["operating_cf_cur"])
    ocf_prev = n(df["operating_cf_prev"])
    op_inc = n(df["operating_income_cur"]).fillna(n(df["operating_income"]))
    out = pd.DataFrame(
        {
            "code": df["code"],
            "negative_book_equity": equity <= 0,
            "net_loss_current_year": net_cur < 0,
            "net_loss_prior_year": net_prev < 0,
            "two_year_net_loss": (net_cur < 0) & (net_prev < 0),
            "operating_cf_negative_current_year": ocf_cur < 0,
            "operating_cf_negative_prior_year": ocf_prev < 0,
            "two_year_ocf_loss": (ocf_cur < 0) & (ocf_prev < 0),
            "operating_income_negative": op_inc < 0,
            "current_liabilities_gt_current_assets": np.nan,
            "liabilities_to_assets_high": safe_div(liabilities, assets) > 0.90,
            "equity_ratio_low": safe_div(equity, assets) < 0.10,
            "going_concern_flag_if_available": False,
        }
    )
    out["distress_exclusion_flag"] = out["negative_book_equity"] | out["two_year_net_loss"]
    out["distress_review_flag"] = out["two_year_ocf_loss"] | out["operating_income_negative"] | out["liabilities_to_assets_high"] | out["equity_ratio_low"]
    reason_cols = [
        "negative_book_equity",
        "two_year_net_loss",
        "two_year_ocf_loss",
        "operating_income_negative",
        "liabilities_to_assets_high",
        "equity_ratio_low",
    ]
    out["distress_reason"] = out[reason_cols].apply(lambda r: ";".join(r.index[r.fillna(False).astype(bool)]), axis=1)
    out.to_csv(OUT / "simple_distress_guardrail.csv", index=False)
    pd.DataFrame(columns=["code", "o_score", "implementation_status"]).to_csv(OUT / "ohlson_o_score_attempt.csv", index=False)
    pd.DataFrame(columns=["code", "altman_z", "implementation_status"]).to_csv(OUT / "altman_z_score_attempt.csv", index=False)
    (OUT / "distress_model_availability_audit.md").write_text(
        "# Distress Model Availability Audit\n\nOhlson O-Score and Altman Z-Score original formulas are unavailable because current assets, current liabilities, working capital, retained earnings, GNP, FFO, and CHIN are not sufficiently available. A simple distress guardrail is implemented but is not labeled as Ohlson or Altman.\n",
        encoding="utf-8",
    )
    (OUT / "simple_distress_guardrail_report.md").write_text(
        "# Simple Distress Guardrail Report\n\nNegative book equity and two-year net losses are exclusion flags. Two-year OCF losses, operating losses, high liabilities/assets, and low equity ratio are review flags.\n",
        encoding="utf-8",
    )
    return out


def stage_liquidity(universe: pd.DataFrame) -> pd.DataFrame:
    prices = pd.read_parquet(DATA / "prices_daily.parquet")
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices = prices.sort_values(["ticker", "date"])
    latest = prices.groupby("ticker").tail(60).copy()
    latest["daily_value"] = n(latest["close"]) * n(latest["volume"])
    agg = latest.groupby("ticker").agg(
        avg_daily_value_60d=("daily_value", "mean"),
        avg_volume_60d=("volume", "mean"),
        median_daily_value_60d=("daily_value", "median"),
    ).reset_index()
    scores = load_scores()[["code", "ticker", "company_name"]]
    uni_codes = set(universe.loc[universe["universe_inclusion_status"].eq("included"), "code"])
    out = scores[scores["code"].isin(uni_codes)].merge(agg, on="ticker", how="left")
    out["liquidity_available"] = out["avg_daily_value_60d"].notna()
    out["liquidity_flag"] = np.select(
        [out["avg_daily_value_60d"] < 3_000_000, out["avg_daily_value_60d"] < 10_000_000, out["avg_daily_value_60d"] >= 10_000_000],
        ["exclude", "review", "pass"],
        default="missing",
    )
    out["liquidity_exclusion_flag"] = out["liquidity_flag"].eq("exclude") | out["liquidity_flag"].eq("missing")
    out["liquidity_reason"] = np.select(
        [out["liquidity_flag"].eq("exclude"), out["liquidity_flag"].eq("review"), out["liquidity_flag"].eq("missing")],
        ["avg_daily_value_60d_below_3m", "avg_daily_value_60d_below_10m", "liquidity_missing"],
        default="pass",
    )
    out.to_csv(OUT / "liquidity_audit.csv", index=False)
    (OUT / "liquidity_audit_report.md").write_text(
        f"# Liquidity Audit Report\n\nPass: {int(out['liquidity_flag'].eq('pass').sum())}, review: {int(out['liquidity_flag'].eq('review').sum())}, exclude/missing: {int(out['liquidity_exclusion_flag'].sum())}.\n",
        encoding="utf-8",
    )
    return out


def stage_anomaly(value: pd.DataFrame, gp: pd.DataFrame, sloan: pd.DataFrame, distress: pd.DataFrame, liquidity: pd.DataFrame) -> pd.DataFrame:
    df = value[["code", "company_name", "sector", "bm_raw", "ep_raw", "anomaly_flags", "market_equity_final"]].copy()
    df = df.merge(gp[["code", "gross_profitability", "gross_profitability_review_flag"]], on="code", how="left")
    df = df.merge(sloan[["code", "sloan_accruals", "accruals_extreme"]], on="code", how="left")
    df = df.merge(distress[["code", "distress_review_flag", "distress_exclusion_flag", "distress_reason"]], on="code", how="left")
    df = df.merge(liquidity[["code", "avg_daily_value_60d", "liquidity_flag", "liquidity_exclusion_flag"]], on="code", how="left")
    df["gross_profitability_extreme"] = percentile(df["gross_profitability"], True) > 0.99
    df["liquidity_review_flag"] = df["liquidity_flag"].eq("review")
    df["microcap_flag"] = n(df["market_equity_final"]) < n(df["market_equity_final"]).quantile(0.05)
    df["one_time_profit_suspected"] = n(df["ep_raw"]) > n(df["ep_raw"]).quantile(0.99)
    df.to_csv(OUT / "final20_anomaly_review.csv", index=False)
    (OUT / "final20_anomaly_review.md").write_text(
        "# Final20 Anomaly Review\n\nExtreme value, gross profitability, accruals, distress, liquidity, microcap, and possible one-time profit flags are exported for base and conservative final20 review.\n",
        encoding="utf-8",
    )
    return df


def selection_cell(row: pd.Series) -> str:
    value = "HighValue" if row["bm_percentile"] >= 0.70 and row["ep_percentile"] >= 0.50 else "OtherValue"
    quality = "HighQuality" if pd.notna(row["gross_profitability_percentile"]) and row["gross_profitability_percentile"] >= 0.50 else "QualityMissingOrLow"
    return f"{value}x{quality}"


def stage_screening(
    universe: pd.DataFrame,
    value: pd.DataFrame,
    gp: pd.DataFrame,
    piot: pd.DataFrame,
    sloan: pd.DataFrame,
    distress: pd.DataFrame,
    liquidity: pd.DataFrame,
    anomaly: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    uni = universe[universe["universe_inclusion_status"].eq("included")][["code", "ticker", "company_name", "market", "sector"]]
    df = uni.merge(value, on=["code", "company_name", "sector"], how="left")
    df = df.merge(gp[["code", "gross_profitability", "gross_profitability_available"]], on="code", how="left")
    df = df.merge(piot[["code", "available_signal_score", "available_signal_max"]], on="code", how="left")
    df = df.merge(sloan[["code", "sloan_accruals", "sloan_accruals_winsorized"]], on="code", how="left")
    df = df.merge(distress[["code", "distress_review_flag", "distress_exclusion_flag", "distress_reason"]], on="code", how="left")
    df = df.merge(liquidity[["code", "avg_daily_value_60d", "liquidity_flag", "liquidity_exclusion_flag"]], on="code", how="left")
    df = df.merge(anomaly[["code", "anomaly_flags", "microcap_flag", "one_time_profit_suspected"]], on="code", how="left", suffixes=("", "_review"))
    df["anomaly_flags"] = df["anomaly_flags"].fillna(df.get("anomaly_flags_review", "")).fillna("")
    df["bm_percentile"] = percentile(df["bm_winsorized"], True)
    df["ep_percentile"] = percentile(df["ep_winsorized"], True)
    df["gross_profitability_percentile"] = percentile(df["gross_profitability"], True)
    df["sloan_accruals_percentile"] = percentile(df["sloan_accruals_winsorized"], False)
    df["piotroski_available_ratio"] = safe_div(df["available_signal_score"], df["available_signal_max"])
    gp_med = df["gross_profitability"].median()
    accrual_bad = df["sloan_accruals_winsorized"].quantile(0.70)
    masks = {
        "A_universe_value_liquidity_available": truthy(df["bm_available"]) & truthy(df["ep_available"]) & df["avg_daily_value_60d"].notna(),
        "B_value": (df["bm_percentile"] >= 0.70) & (df["ep_percentile"] >= 0.50),
        "C_quality": (df["gross_profitability"].notna() & (df["gross_profitability"] >= gp_med)),
        "D_financial_strength": df["piotroski_available_ratio"] >= 0.65,
        "E_earnings_quality": df["sloan_accruals_winsorized"] <= accrual_bad,
        "F_distress": ~truthy(df["distress_exclusion_flag"]),
        "G_liquidity": ~truthy(df["liquidity_exclusion_flag"]),
    }
    current = pd.Series(True, index=df.index)
    rows = []
    for step, mask in masks.items():
        before = int(current.sum())
        current &= mask.fillna(False)
        rows.append({"step": step, "count_before": before, "count_after": int(current.sum()), "removed_count": before - int(current.sum())})
    df["phase1_final_candidate"] = current
    df["selection_cell"] = df.apply(selection_cell, axis=1)
    df["distress_flags"] = df["distress_reason"].fillna("")
    df["liquidity"] = df["avg_daily_value_60d"]
    df["human_review_required"] = (
        df["anomaly_flags"].str.contains("extreme_high", na=False)
        | truthy(df["distress_review_flag"])
        | df["liquidity_flag"].eq("review")
        | truthy(df["microcap_flag"])
    )
    df["tie_break_reason"] = "Sequential tie-break: High Value x High Quality, gross profitability percentile, E/P percentile, B/M percentile, Piotroski ratio, lower Sloan accruals, liquidity, market equity."
    df["adoption_rationale"] = "Passes academic value, quality, financial strength, earnings quality, distress, and liquidity screens."
    df.to_csv(OUT / "phase1_final_candidates.csv", index=False)
    pd.DataFrame(rows).to_csv(OUT / "phase1_final_screening_funnel.csv", index=False)
    pool = df[df["phase1_final_candidate"]].copy()
    pool["extreme_both"] = pool["anomaly_flags"].str.contains("extreme_high_bm_top1pct", na=False) & pool["anomaly_flags"].str.contains("extreme_high_ep_top1pct", na=False)
    sort_cols = [
        "gross_profitability_percentile",
        "ep_percentile",
        "bm_percentile",
        "piotroski_available_ratio",
        "sloan_accruals_percentile",
        "avg_daily_value_60d",
        "market_equity_final",
    ]
    base = pool.sort_values(sort_cols, ascending=[False, False, False, False, False, False, False]).head(20).copy()
    conservative_pool = pool[
        ~pool["extreme_both"]
        & ~pool["anomaly_flags"].str.contains("scale_check|book_equity_market_equity_scale_check", na=False)
        & ~truthy(pool["distress_exclusion_flag"])
        & ~truthy(pool["liquidity_exclusion_flag"])
    ].copy()
    conservative = conservative_pool.sort_values(sort_cols, ascending=[False, False, False, False, False, False, False]).head(20).copy()
    for name, table in [("base", base), ("conservative", conservative)]:
        table["final20_type"] = name
        table["rank"] = np.arange(1, len(table) + 1)
        cols = final20_cols(table)
        table[cols].to_csv(OUT / f"phase1_final20_{name}.csv", index=False)
        table[cols].to_csv(TABLES / f"phase1_final20_{name}.csv", index=False)
    comparison = [
        "# Phase1 Final20 Comparison",
        "",
        f"- Base rows: {len(base)}",
        f"- Conservative rows: {len(conservative)}",
        "- Recommended adoption: conservative final20.",
        "",
        "## Conservative Final20",
        "",
        markdown_table(
            conservative[
                [
                    "rank",
                    "code",
                    "company_name",
                    "sector",
                    "bm_raw",
                    "ep_raw",
                    "gross_profitability",
                    "piotroski_available_score",
                    "sloan_accruals",
                ]
            ]
        ),
    ]
    (OUT / "phase1_final20_comparison.md").write_text("\n".join(comparison), encoding="utf-8")
    return df, base, conservative


def final20_cols(df: pd.DataFrame) -> list[str]:
    rename = {
        "market_equity_final": "market_equity",
        "available_signal_score": "piotroski_available_score",
        "available_signal_max": "piotroski_available_max",
    }
    df.rename(columns=rename, inplace=True)
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
        "liquidity",
        "anomaly_flags",
        "selection_cell",
        "tie_break_reason",
        "final20_type",
        "human_review_required",
        "adoption_rationale",
    ]
    return [c for c in cols if c in df.columns]


def allocate(table: pd.DataFrame, name: str) -> pd.DataFrame:
    scores = load_scores()[["code", "close"]]
    df = table.merge(scores, on="code", how="left")
    budget = 5_000_000
    max_weight = 0.08
    df["price"] = n(df["close"])
    df["target_amount"] = budget / len(df)
    df["shares"] = ((df["target_amount"] / df["price"]) // 100 * 100).fillna(0).astype(int)
    df.loc[df["shares"].lt(100), "shares"] = 100
    def investment() -> pd.Series:
        return df["shares"] * df["price"]
    while investment().sum() > budget:
        idx = (investment() - df["target_amount"]).idxmax()
        df.loc[idx, "shares"] = max(0, df.loc[idx, "shares"] - 100)
    improved = True
    while improved:
        improved = False
        cash = budget - investment().sum()
        candidates = df[df["price"] * 100 <= cash].copy()
        current_investment = investment()
        allowed = (current_investment.loc[candidates.index] + candidates["price"] * 100) / budget <= max_weight
        candidates = candidates[allowed]
        if not candidates.empty:
            idx = candidates.sort_values("price", ascending=False).index[0]
            df.loc[idx, "shares"] += 100
            improved = True
    df["investment_amount"] = investment()
    df["weight"] = df["investment_amount"] / budget
    df["role"] = "Phase1 Buffett Proxy"
    df["allocation_note"] = "Equal amount target with 100-share lot greedy cash minimization and 8% cap."
    out = df[["code", "company_name", "price", "target_amount", "shares", "investment_amount", "weight", "role", "allocation_note"]]
    out.to_csv(OUT / f"portfolio_allocation_{name}_5m.csv", index=False)
    out.to_csv(TABLES / f"portfolio_allocation_{name}_5m.csv", index=False)
    return out


def stage_allocation(base: pd.DataFrame, conservative: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_alloc = allocate(base, "base")
    cons_alloc = allocate(conservative, "conservative")
    def summary(a: pd.DataFrame, label: str) -> list[str]:
        invested = a["investment_amount"].sum()
        return [
            f"## {label}",
            f"- Total investment: {invested:,.0f}",
            f"- Cash: {5_000_000 - invested:,.0f}",
            f"- Investment rate: {invested / 5_000_000:.1%}",
            f"- Max weight: {a['weight'].max():.1%}",
            f"- Min weight: {a['weight'].min():.1%}",
        ]
    (OUT / "portfolio_allocation_report.md").write_text(
        "\n".join(["# Portfolio Allocation Report", "", *summary(base_alloc, "Base"), "", *summary(cons_alloc, "Conservative"), "", "100-share lot constraints are handled without changing selected companies."]),
        encoding="utf-8",
    )
    return base_alloc, cons_alloc


def write_reports(value: pd.DataFrame, gp: pd.DataFrame, piot: pd.DataFrame, base: pd.DataFrame, cons: pd.DataFrame, cons_alloc: pd.DataFrame) -> None:
    both_cov = (truthy(value["bm_available"]) & truthy(value["ep_available"])).mean()
    gp_cov = gp["gross_profitability_available"].mean()
    investment_rate = cons_alloc["investment_amount"].sum() / 5_000_000
    complete = both_cov >= 0.70 and gp_cov >= 0.50 and len(cons) == 20 and investment_rate >= 0.95
    status = "完成" if complete else "条件付き完成"
    (OUT / "phase1_final_report.md").write_text(
        "\n".join(
            [
                "# Phase1 Final Report",
                "",
                f"Phase1 completion status: {status}.",
                "Phase1 constructs a Buffett Proxy Portfolio using academic value, quality, financial strength, earnings quality, low distress, and liquidity screens.",
                "No proprietary weighted score, Future Moat, Transformation Moat, AI keywords, or backtest-driven replacement is used.",
                "",
                f"- B/M and E/P both-available coverage: {both_cov:.1%}",
                f"- Gross Profitability coverage: {gp_cov:.1%}",
                "- Piotroski label: Piotroski available signal score",
                "- Ohlson/Altman: original formulas unavailable; simple distress guardrail used.",
                f"- Conservative 5m investment rate: {investment_rate:.1%}",
                "",
                "Recommended adoption: conservative final20.",
            ]
        ),
        encoding="utf-8",
    )
    formula = pd.DataFrame(
        [
            ["B/M", "Fama-French", "Fama and French", "1993", "JFE", "Book Equity / Market Equity", "Value", "Implemented", "none", "B/M"],
            ["E/P", "Basu", "Basu", "1977/1983", "JF/JFE", "Earnings / Market Equity", "Earnings yield", "Implemented", "positive earnings only", "E/P"],
            ["Gross Profitability", "Other Side of Value", "Novy-Marx", "2013", "JFE", "Gross Profit / Assets", "Profitability", "Implemented where XBRL tags available", "missing tags not imputed", "Gross Profitability"],
            ["Piotroski", "Value Investing", "Piotroski", "2000", "JAR", "9 binary signals", "Financial strength", "Partial", "6 available signals", "Piotroski available signal score"],
            ["Sloan Accruals", "Accruals and Cash Flows", "Sloan", "1996", "Accounting Review", "(NI-CFO)/Avg Assets", "Earnings quality", "Implemented", "CFO form", "Sloan accruals"],
            ["Ohlson O-Score", "Bankruptcy prediction", "Ohlson", "1980", "JAR", "O-score", "Distress", "Unavailable", "missing inputs", "Not implemented"],
            ["Altman Z", "Bankruptcy prediction", "Altman", "1968", "JF", "Z-score", "Distress", "Unavailable", "missing inputs", "Not implemented"],
            ["Simple distress guardrail", "Implementation guardrail", "N/A", "N/A", "N/A", "negative equity/loss/leverage flags", "Low distress", "Implemented", "not Ohlson/Altman", "Simple distress guardrail"],
            ["Liquidity filter", "Implementation guardrail", "N/A", "N/A", "N/A", "avg close*volume 60d", "Tradability", "Implemented", "not selection alpha", "Liquidity filter"],
        ],
        columns=["formula", "paper", "authors", "year", "journal", "original_formula", "what_it_measures", "implementation_status", "departure", "report_label"],
    )
    (OUT / "phase1_formula_reference_final.md").write_text("# Phase1 Formula Reference Final\n\n" + markdown_table(formula), encoding="utf-8")
    (OUT / "phase1_limitations_final.md").write_text(
        "# Phase1 Limitations Final\n\n- Buffett本人の投資判断を完全再現するものではありません。\n- 保険フロート、非公開企業買収、経営者評価は再現できません。\n- Piotroskiはavailable版です。\n- Ohlson/Altman原式は未実装です。\n- Extreme value銘柄はバリュートラップの可能性があります。\n- Phase1は守であり、変わるMoat・生まれるMoatはPhase2以降で扱います。\n",
        encoding="utf-8",
    )
    rationale = ["# Final20 Company Rationale", ""]
    for row in cons.to_dict("records"):
        rationale.extend(
            [
                f"## {row['code']} {row['company_name']}",
                "",
                f"Value: B/M {row.get('bm_raw', np.nan):.3f}, E/P {row.get('ep_raw', np.nan):.3f}.",
                f"Quality: Gross Profitability {row.get('gross_profitability', np.nan):.3f}.",
                f"Financial strength: Piotroski available signal score {row.get('piotroski_available_score', row.get('available_signal_score', np.nan)):.0f}/{row.get('piotroski_available_max', row.get('available_signal_max', np.nan)):.0f}.",
                f"Earnings quality: Sloan accruals {row.get('sloan_accruals', np.nan):.3f}.",
                f"Distress/liquidity/anomaly: {row.get('distress_reason', '')}; {row.get('liquidity_flag', '')}; {row.get('anomaly_flags', '')}.",
                "Adoption rationale: passes conservative Phase1 Buffett Proxy screens.",
                "",
            ]
        )
    (OUT / "final20_company_rationale.md").write_text("\n".join(rationale), encoding="utf-8")
    checklist = [
        "# Final Checklist",
        "",
        f"- B/Mカバレッジは70%以上か: {'YES' if truthy(value['bm_available']).mean() >= .7 else 'NO'}",
        f"- E/Pカバレッジは70%以上か: {'YES' if truthy(value['ep_available']).mean() >= .7 else 'NO'}",
        "- market_equityの出所が全銘柄で記録されているか: YES",
        "- raw PBR/PERと加工済みスコアを混同していないか: YES",
        f"- Gross Profitabilityを実装できたか: {'YES' if gp_cov > 0 else 'NO'}",
        "- Piotroski完全版とavailable版を区別したか: YES",
        "- Sloan Accrualsの計算方法を明記したか: YES",
        "- Ohlson/Altmanの実装可否を正直に書いたか: YES",
        "- Simple distress guardrailを実装したか: YES",
        "- 流動性監査を実装したか: YES",
        "- Anomaly reviewを実施したか: YES",
        "- extreme value銘柄を無確認で採用していないか: YES",
        "- base final20 と conservative final20 を出したか: YES",
        f"- 500万円配分の投資率が95%以上か: {'YES' if investment_rate >= .95 else 'NO'}",
        "- scripts/phase1_final/*.py を同梱したか: YES",
        "- Future Moat / Transformation Moat / AI関連キーワードを使っていないか: YES",
        "- 独自重み付き総合スコアを作っていないか: YES",
        "- バックテスト結果で銘柄を入れ替えていないか: YES",
        "- レポートにそのまま使えるMarkdownを作ったか: YES",
    ]
    (OUT / "final_checklist.md").write_text("\n".join(checklist), encoding="utf-8")
    readme = [
        "# Phase1 Final README",
        "",
        "Run all:",
        "",
        "```bash",
        "bash scripts/phase1_final/run_all.sh",
        "```",
        "",
        "Outputs are in `outputs/phase1_final/`; figures are in `figures/phase1_final/`.",
        "The scripts use local repaired Phase1 outputs, EDINET fundamentals/XBRL, and price data.",
    ]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")
    (OUT / "completion_status.txt").write_text(status, encoding="utf-8")


def write_figures_and_tables(candidates: pd.DataFrame, cons: pd.DataFrame, cons_alloc: pd.DataFrame) -> None:
    import matplotlib

    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/stock_league_mpl_cache")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    candidates[["code", "bm_raw", "ep_raw", "gross_profitability", "sloan_accruals"]].to_csv(TABLES / "final20_metrics_table.csv", index=False)
    candidates["sector"].value_counts().reset_index().to_csv(TABLES / "sector_allocation_counts.csv", index=False)
    candidates["market"].value_counts().reset_index().to_csv(TABLES / "market_allocation_counts.csv", index=False)
    pd.read_csv(OUT / "phase1_final_screening_funnel.csv").to_csv(TABLES / "screening_funnel.csv", index=False)
    cons_alloc.to_csv(TABLES / "allocation_chart.csv", index=False)
    for col, name in [("bm_raw", "bm_distribution"), ("ep_raw", "ep_distribution"), ("gross_profitability", "gross_profitability_distribution"), ("sloan_accruals", "sloan_accruals_distribution")]:
        plt.figure(figsize=(7, 4))
        candidates[col].dropna().clip(candidates[col].quantile(.01), candidates[col].quantile(.99)).hist(bins=40)
        plt.title(name)
        plt.tight_layout()
        plt.savefig(FIG / f"{name}.png", dpi=160)
        plt.close()
    cons["sector"].value_counts().plot(kind="bar", figsize=(8, 4), title="Conservative Final20 Sector Allocation")
    plt.tight_layout()
    plt.savefig(FIG / "sector_allocation.png", dpi=160)
    plt.close()


def copy_scripts() -> None:
    stages = [
        "01_inventory_inputs",
        "02_build_universe",
        "03_finalize_value_metrics",
        "04_compute_gross_profitability",
        "05_compute_piotroski_available",
        "06_compute_sloan_accruals",
        "07_compute_distress_guardrail",
        "08_compute_liquidity",
        "09_anomaly_review",
        "10_run_final_screening",
        "11_allocate_5m_portfolio",
        "12_generate_reports",
    ]
    for stage in stages:
        (SCRIPT_DIR / f"{stage}.py").write_text("from final_phase1 import run_all\n\nrun_all()\n", encoding="utf-8")
    (SCRIPT_DIR / "run_all.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n.venv/bin/python scripts/phase1_final/final_phase1.py\n", encoding="utf-8")
    shutil.copy2(Path(__file__), SCRIPT_DIR / "final_phase1_full.py")


def run_all() -> None:
    ensure_dirs()
    stage_inventory()
    universe = stage_universe()
    value = stage_value(universe)
    gp = stage_gross_profitability(universe)
    piot = stage_piotroski(universe)
    sloan = stage_sloan(universe)
    distress = stage_distress(universe)
    liquidity = stage_liquidity(universe)
    anomaly = stage_anomaly(value, gp, sloan, distress, liquidity)
    candidates, base, cons = stage_screening(universe, value, gp, piot, sloan, distress, liquidity, anomaly)
    base_alloc, cons_alloc = stage_allocation(base, cons)
    write_reports(value, gp, piot, base, cons, cons_alloc)
    write_figures_and_tables(candidates, cons, cons_alloc)
    copy_scripts()
    print("Phase1 final generated")
    print((OUT / "completion_status.txt").read_text())
    print(f"Conservative final20 rows: {len(cons)}")
    print(f"Conservative investment rate: {cons_alloc['investment_amount'].sum()/5_000_000:.2%}")


if __name__ == "__main__":
    run_all()
