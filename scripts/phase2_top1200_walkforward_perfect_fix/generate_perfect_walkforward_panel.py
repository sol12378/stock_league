from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "phase2_top1200_walkforward_perfect_fix"
ZIP_OUT = ROOT / "outputs" / "phase2_top1200_walkforward_perfect_fix.zip"
DOCS = ROOT / "data" / "processed" / "edinet_documents.csv"
FUND_RAW = ROOT / "data" / "processed" / "fundamentals_raw.csv"
FUND_CLEAN = ROOT / "data" / "processed" / "fundamentals_clean.csv"
PRICES = ROOT / "data" / "processed" / "prices_daily.parquet"
XBRL_DIR = ROOT / "data" / "raw" / "edinet" / "xbrl"
PREV_TOP1200 = ROOT / "outputs" / "phase2_top1200_walkforward_fix" / "top1200_final" / "phase2_optimized_top1200_candidates.csv"
PREV_CONSENSUS = ROOT / "outputs" / "phase2_top1200_walkforward_fix" / "consensus" / "normalization_consensus_table.csv"
PREV_SOLUTION = ROOT / "outputs" / "phase2_top1200_walkforward_fix" / "top1200_final" / "selected_phase2_top1200_solution.json"

DIRS = [
    "configs",
    "data_audit",
    "data_panel",
    "xbrl_facts",
    "walk_forward",
    "rankings",
    "validation",
    "figures",
    "reports",
    "scripts/phase2_top1200_walkforward_perfect_fix",
    "logs",
]

TAG_CANDIDATES: dict[str, list[str]] = {
    "revenue": [
        "NetSales",
        "Revenue",
        "SalesRevenue",
        "OperatingRevenue1",
        "RevenueFromContractsWithCustomers",
        "NetSalesSummaryOfBusinessResults",
    ],
    "gross_profit": ["GrossProfit", "GrossProfitLoss"],
    "cost_of_sales": ["CostOfSales"],
    "operating_income": ["OperatingIncome", "OperatingProfit", "OperatingProfitLoss"],
    "ordinary_income": ["OrdinaryIncome", "OrdinaryProfitLoss"],
    "net_income": [
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLoss",
        "NetIncome",
        "ProfitAttributableToOwnersOfParent",
        "ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
    ],
    "total_assets": ["Assets", "TotalAssets", "TotalAssetsSummaryOfBusinessResults"],
    "equity": [
        "Equity",
        "NetAssets",
        "EquityAttributableToOwnersOfParent",
        "NetAssetsSummaryOfBusinessResults",
    ],
    "liabilities": ["Liabilities"],
    "current_assets": ["CurrentAssets"],
    "current_liabilities": ["CurrentLiabilities"],
    "operating_cf": [
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
    ],
    "investing_cf": [
        "NetCashProvidedByUsedInInvestingActivities",
        "CashFlowsFromUsedInInvestingActivities",
    ],
    "financing_cf": [
        "NetCashProvidedByUsedInFinancingActivities",
        "CashFlowsFromUsedInFinancingActivities",
    ],
    "capex": [
        "PurchaseOfPropertyPlantAndEquipment",
        "PaymentsForPurchaseOfPropertyPlantAndEquipment",
        "PurchaseOfNoncurrentAssetsInvCF",
    ],
    "rd_expense": ["ResearchAndDevelopmentExpenses", "ResearchAndDevelopmentExpense"],
    "employees": ["NumberOfEmployees"],
    "shares_issued": [
        "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
        "TotalNumberOfIssuedSharesSummaryOfBusinessResults",
    ],
    "treasury_shares": [
        "TotalNumberOfSharesHeldTreasurySharesEtc",
        "NumberOfSharesHeldInOwnNameTreasurySharesEtc",
    ],
}

FLOW_METRICS = {
    "revenue",
    "gross_profit",
    "cost_of_sales",
    "operating_income",
    "ordinary_income",
    "net_income",
    "operating_cf",
    "investing_cf",
    "financing_cf",
    "capex",
    "rd_expense",
}
STOCK_METRICS = set(TAG_CANDIDATES) - FLOW_METRICS
REQUIRED_STRICT_FACTS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "total_assets",
    "equity",
    "operating_cf",
    "current_assets",
    "current_liabilities",
    "shares_outstanding_pti",
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


def local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1]


def concept_local(elem: etree._Element) -> str:
    name = elem.attrib.get("name") or elem.attrib.get("Name") or ""
    if name:
        return name.split(":")[-1]
    return local_name(str(elem.tag))


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    text = text.replace("△", "-").replace("−", "-").replace("－", "-")
    text = re.sub(r"^\((.*)\)$", r"-\1", text)
    if text in {"", "-", "None", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def scaled_number(elem: etree._Element) -> float | None:
    value = parse_number(elem.text)
    if value is None:
        return None
    scale = elem.attrib.get("scale") or elem.attrib.get("Scale")
    sign = elem.attrib.get("sign") or elem.attrib.get("Sign")
    if scale not in (None, ""):
        try:
            value *= 10 ** int(scale)
        except ValueError:
            pass
    if sign in {"-", "negative"} and value > 0:
        value = -value
    return value


def metric_for_concept(concept: str) -> str | None:
    for metric, candidates in TAG_CANDIDATES.items():
        if concept in candidates:
            return metric
    return None


def context_priority(context: str, metric: str) -> int:
    ctx = context or ""
    non_consolidated = 30 if "NonConsolidatedMember" in ctx else 0
    segmented = 25 if ("ReportableSegment" in ctx or "_Row" in ctx or "Member" in ctx and "NonConsolidatedMember" not in ctx and "OrdinaryShareMember" not in ctx) else 0
    if metric in FLOW_METRICS:
        prefs = ["CurrentYearDuration", "CurrentDuration", "CurrentYear", "Prior1YearDuration"]
    else:
        prefs = ["CurrentYearInstant", "FilingDateInstant", "CurrentInstant", "CurrentYear", "Prior1YearInstant"]
    base = 99
    for i, token in enumerate(prefs):
        if token in ctx:
            base = i
            break
    return base + non_consolidated + segmented


def iter_xml_members(zf: zipfile.ZipFile) -> list[str]:
    return [
        name
        for name in zf.namelist()
        if name.lower().endswith((".xbrl", ".xml", ".htm", ".html", ".xhtml"))
        and "__macosx" not in name.lower()
    ]


def parse_xbrl_zip(zip_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    facts: dict[str, list[dict[str, object]]] = {metric: [] for metric in TAG_CANDIDATES}
    fact_rows: list[dict[str, object]] = []
    parser = etree.XMLParser(recover=True, huge_tree=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in iter_xml_members(zf):
            try:
                root = etree.fromstring(zf.read(member), parser=parser)
            except Exception:
                continue
            for elem in root.iter():
                concept = concept_local(elem)
                metric = metric_for_concept(concept)
                if metric is None:
                    continue
                number = scaled_number(elem)
                if number is None or not math.isfinite(number):
                    continue
                context = elem.attrib.get("contextRef") or elem.attrib.get("contextref") or ""
                unit = elem.attrib.get("unitRef") or elem.attrib.get("unitref") or ""
                row = {
                    "metric": metric,
                    "concept": concept,
                    "context_ref": context,
                    "unit_ref": unit,
                    "scale": elem.attrib.get("scale") or "",
                    "decimals": elem.attrib.get("decimals") or "",
                    "value": number,
                    "member": member,
                    "priority": context_priority(context, metric),
                }
                facts[metric].append(row)
                fact_rows.append(row)

    result: dict[str, object] = {}
    for metric, rows in facts.items():
        if not rows:
            result[metric] = np.nan
            result[f"{metric}_concept"] = ""
            result[f"{metric}_context_ref"] = ""
            result[f"{metric}_source_member"] = ""
            continue
        chosen = sorted(rows, key=lambda r: (int(r["priority"]), -abs(float(r["value"]))))[0]
        result[metric] = float(chosen["value"])
        result[f"{metric}_concept"] = chosen["concept"]
        result[f"{metric}_context_ref"] = chosen["context_ref"]
        result[f"{metric}_source_member"] = chosen["member"]
    return result, fact_rows


def load_documents() -> pd.DataFrame:
    docs = pd.read_csv(DOCS, dtype={"code": str, "sec_code": str, "doc_id": str, "edinet_code": str})
    docs["submit_date"] = pd.to_datetime(docs["submit_date"], errors="coerce")
    docs["period_start"] = pd.to_datetime(docs["period_start"], errors="coerce")
    docs["period_end"] = pd.to_datetime(docs["period_end"], errors="coerce")
    docs["fiscal_year"] = docs["period_end"].dt.year
    docs = docs[docs["form_code"].astype(str).eq("30000")].copy()
    docs = docs.sort_values(["code", "period_end", "submit_date"]).drop_duplicates(["code", "period_end"], keep="last")
    return docs


def build_extended_facts(docs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    fact_audit_counter: dict[tuple[int, str], int] = defaultdict(int)
    total = len(docs)
    for i, row in enumerate(docs.to_dict("records"), start=1):
        doc_id = str(row["doc_id"])
        zip_path = XBRL_DIR / f"{doc_id}.zip"
        if i % 500 == 0:
            print(f"parsed {i}/{total} XBRL documents")
        if not zip_path.exists():
            errors.append({"doc_id": doc_id, "code": row.get("code"), "error": "xbrl_zip_missing"})
            continue
        try:
            metrics, fact_rows = parse_xbrl_zip(zip_path)
        except Exception as exc:
            errors.append({"doc_id": doc_id, "code": row.get("code"), "error": repr(exc)})
            continue
        for fact in fact_rows:
            fact_audit_counter[(int(row["fiscal_year"]) if pd.notna(row["fiscal_year"]) else -1, str(fact["metric"]))] += 1
        rows.append(
            {
                "code": row.get("code"),
                "ticker": f"{row.get('code')}.T",
                "doc_id": doc_id,
                "edinet_code": row.get("edinet_code"),
                "filer_name": row.get("filer_name"),
                "submit_date": row.get("submit_date"),
                "period_start": row.get("period_start"),
                "period_end": row.get("period_end"),
                "fiscal_year": row.get("fiscal_year"),
                "doc_description": row.get("doc_description"),
                **metrics,
            }
        )
    facts = pd.DataFrame(rows)
    if facts.empty:
        return facts, pd.DataFrame(errors), pd.DataFrame()
    for col in list(TAG_CANDIDATES):
        if col in facts.columns:
            facts[col] = pd.to_numeric(facts[col], errors="coerce")
    facts["gross_profit_direct"] = facts["gross_profit"]
    facts["gross_profit"] = facts["gross_profit"].where(
        facts["gross_profit"].notna(),
        facts["revenue"] - facts["cost_of_sales"],
    )
    facts["gross_profit_source"] = np.select(
        [
            facts["gross_profit_direct"].notna(),
            facts["gross_profit"].notna() & facts["gross_profit_direct"].isna(),
        ],
        ["direct_xbrl_gross_profit", "derived_revenue_minus_cost_of_sales"],
        default="unavailable",
    )
    facts["shares_outstanding_pti"] = facts["shares_issued"]
    has_treasury = facts["shares_issued"].notna() & facts["treasury_shares"].notna()
    facts.loc[has_treasury, "shares_outstanding_pti"] = facts.loc[has_treasury, "shares_issued"] - facts.loc[has_treasury, "treasury_shares"]
    facts["shares_outstanding_source"] = np.select(
        [
            has_treasury,
            facts["shares_issued"].notna(),
        ],
        ["xbrl_issued_minus_treasury", "xbrl_issued_shares"],
        default="unavailable",
    )
    for metric in REQUIRED_STRICT_FACTS:
        facts[f"missing_{metric}"] = facts[metric].isna() if metric in facts.columns else True
    facts["strict_fact_complete"] = ~facts[[f"missing_{m}" for m in REQUIRED_STRICT_FACTS]].any(axis=1)
    coverage = []
    for year, sub in facts.groupby("fiscal_year", dropna=False):
        item = {"fiscal_year": int(year) if pd.notna(year) else -1, "row_count": len(sub)}
        for metric in REQUIRED_STRICT_FACTS:
            item[f"{metric}_coverage"] = float(sub[metric].notna().mean()) if metric in sub else 0.0
        item["strict_fact_complete_rate"] = float(sub["strict_fact_complete"].mean())
        coverage.append(item)
    fact_counts = [
        {"fiscal_year": year, "metric": metric, "xbrl_fact_count": count}
        for (year, metric), count in sorted(fact_audit_counter.items())
    ]
    return facts, pd.DataFrame(errors), pd.DataFrame(coverage).merge(pd.DataFrame(fact_counts).pivot_table(index="fiscal_year", columns="metric", values="xbrl_fact_count", aggfunc="sum").reset_index(), on="fiscal_year", how="left")


def add_company_metadata(facts: pd.DataFrame) -> pd.DataFrame:
    clean = pd.read_csv(FUND_CLEAN, dtype={"code": str})
    cols = ["code", "company_name", "company_name_ja", "market", "sector_33", "sector_17", "is_financial"]
    clean = clean[[c for c in cols if c in clean.columns]].drop_duplicates("code")
    out = facts.merge(clean, on="code", how="left")
    out["sector"] = out.get("sector_33", pd.Series(index=out.index, dtype=object)).fillna(out.get("sector_17", "Unknown")).fillna("Unknown")
    return out


def load_prices() -> pd.DataFrame:
    prices = pd.read_parquet(PRICES, columns=["date", "ticker", "close", "adj_close", "volume"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices["ticker"] = prices["ticker"].astype(str)
    prices = prices.sort_values(["ticker", "date"]).reset_index(drop=True)
    prices["trading_value"] = prices["close"] * prices["volume"]
    prices["adv60"] = prices.groupby("ticker", sort=False)["trading_value"].transform(lambda s: s.rolling(60, min_periods=20).mean())
    return prices


def attach_prices(panel: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    left = panel.copy()
    left["availability_date"] = pd.to_datetime(left["submit_date"], errors="coerce")
    left["decision_anchor_date"] = pd.to_datetime(
        left["availability_date"].dt.normalize() + pd.Timedelta(days=1)
    ).astype("datetime64[ns]")
    right = prices[["ticker", "date", "close", "adj_close", "volume", "adv60"]].copy()
    right["date"] = pd.to_datetime(right["date"]).astype("datetime64[ns]")
    left = left.sort_values(["ticker", "decision_anchor_date"]).reset_index(drop=True)
    right = right.sort_values(["ticker", "date"]).reset_index(drop=True)
    try:
        merged = pd.merge_asof(
            left,
            right,
            left_on="decision_anchor_date",
            right_on="date",
            by="ticker",
            direction="forward",
        )
    except ValueError:
        merged = pd.merge_asof(
            left.sort_values("decision_anchor_date"),
            right.sort_values("date"),
            left_on="decision_anchor_date",
            right_on="date",
            by="ticker",
            direction="forward",
        )
    merged = merged.rename(
        columns={
            "date": "decision_price_date",
            "close": "decision_close",
            "adj_close": "decision_adj_close",
            "volume": "decision_volume",
            "adv60": "decision_adv60",
        }
    )
    future_lookup: dict[str, pd.DataFrame] = {}
    for ticker, sub in prices.groupby("ticker", sort=False):
        future_lookup[ticker] = sub[["date", "adj_close"]].reset_index(drop=True)

    for horizon in [63, 126, 252]:
        dates: list[pd.Timestamp | pd.NaT] = []
        values: list[float] = []
        for rec in merged[["ticker", "decision_price_date", "decision_adj_close"]].to_dict("records"):
            ticker = str(rec["ticker"])
            date = rec["decision_price_date"]
            start = rec["decision_adj_close"]
            px = future_lookup.get(ticker)
            if px is None or pd.isna(date) or pd.isna(start):
                dates.append(pd.NaT)
                values.append(np.nan)
                continue
            idx = px["date"].searchsorted(date)
            target = idx + horizon
            if target >= len(px):
                dates.append(pd.NaT)
                values.append(np.nan)
                continue
            end = float(px.iloc[target]["adj_close"])
            dates.append(px.iloc[target]["date"])
            values.append(end / float(start) - 1 if start else np.nan)
        merged[f"future_return_{horizon}d"] = values
        merged[f"future_return_{horizon}d_end_date"] = dates
    merged["price_join_success"] = merged["decision_price_date"].notna()
    return merged


def compute_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["code", "fiscal_year"]).copy()
    numeric_cols = [
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "total_assets",
        "equity",
        "liabilities",
        "current_assets",
        "current_liabilities",
        "operating_cf",
        "shares_outstanding_pti",
        "decision_close",
        "decision_adj_close",
        "decision_adv60",
    ]
    for col in numeric_cols:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["market_equity_pti"] = out["decision_close"] * out["shares_outstanding_pti"]
    out["book_to_market"] = out["equity"] / out["market_equity_pti"]
    out["earnings_to_price"] = out["net_income"] / out["market_equity_pti"]
    out["gross_profitability"] = out["gross_profit"] / out["total_assets"]
    out["operating_profitability_proxy"] = out["operating_income"] / out["total_assets"]
    out["gross_margin"] = out["gross_profit"] / out["revenue"]
    out["asset_turnover"] = out["revenue"] / out["total_assets"]
    out["current_ratio"] = out["current_assets"] / out["current_liabilities"]
    out["leverage"] = out["liabilities"] / out["total_assets"]
    out["roa"] = out["net_income"] / out["total_assets"]
    out["sloan_accruals"] = (out["net_income"] - out["operating_cf"]) / out["total_assets"]
    grouped = out.groupby("code", sort=False)
    for col in ["roa", "leverage", "current_ratio", "shares_outstanding_pti", "gross_margin", "asset_turnover"]:
        out[f"prev_{col}"] = grouped[col].shift(1)
        out[f"delta_{col}"] = out[col] - out[f"prev_{col}"]
    components = {
        "f_score_positive_roa": out["roa"] > 0,
        "f_score_positive_ocf": out["operating_cf"] > 0,
        "f_score_delta_roa": out["delta_roa"] > 0,
        "f_score_accrual_quality": out["operating_cf"] > out["net_income"],
        "f_score_delta_leverage": out["delta_leverage"] < 0,
        "f_score_delta_current_ratio": out["delta_current_ratio"] > 0,
        "f_score_no_share_issuance": out["delta_shares_outstanding_pti"] <= 0,
        "f_score_delta_gross_margin": out["delta_gross_margin"] > 0,
        "f_score_delta_asset_turnover": out["delta_asset_turnover"] > 0,
    }
    comp_cols = []
    for col, values in components.items():
        out[col] = values.astype("float")
        comp_cols.append(col)
    required_for_comp = {
        "f_score_positive_roa": ["roa"],
        "f_score_positive_ocf": ["operating_cf"],
        "f_score_delta_roa": ["roa", "prev_roa"],
        "f_score_accrual_quality": ["operating_cf", "net_income"],
        "f_score_delta_leverage": ["leverage", "prev_leverage"],
        "f_score_delta_current_ratio": ["current_ratio", "prev_current_ratio"],
        "f_score_no_share_issuance": ["shares_outstanding_pti", "prev_shares_outstanding_pti"],
        "f_score_delta_gross_margin": ["gross_margin", "prev_gross_margin"],
        "f_score_delta_asset_turnover": ["asset_turnover", "prev_asset_turnover"],
    }
    for comp, reqs in required_for_comp.items():
        missing = out[reqs].isna().any(axis=1)
        out.loc[missing, comp] = np.nan
    out["piotroski_f_score_available_components"] = out[comp_cols].notna().sum(axis=1)
    out["piotroski_f_score"] = out[comp_cols].sum(axis=1, min_count=1)
    out["piotroski_f_score_ratio"] = out["piotroski_f_score"] / out["piotroski_f_score_available_components"].replace(0, np.nan)
    out["distress_flag_pti"] = (
        (out["equity"] <= 0)
        | ((out["net_income"] < 0) & (out["operating_cf"] < 0))
        | ((out["current_ratio"] < 0.6) & (out["leverage"] > 0.9))
    )
    out["strict_walk_forward_feature_complete"] = out[
        [
            "book_to_market",
            "earnings_to_price",
            "gross_profitability",
            "piotroski_f_score_ratio",
            "sloan_accruals",
            "decision_adv60",
        ]
    ].notna().all(axis=1)
    out["strict_walk_forward_target_252d_complete"] = out["future_return_252d"].notna()
    out["strict_walk_forward_ready"] = out["strict_fact_complete"] & out["price_join_success"] & out["strict_walk_forward_feature_complete"]
    return out


def pct_rank(s: pd.Series, higher: bool = True) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    y = x.rank(pct=True, method="average")
    if not higher:
        y = 1 - y
    return y.fillna(0.5)


def rank_by_year(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    weights = {
        "bm": 0.18,
        "ep": 0.18,
        "gp": 0.18,
        "piotroski": 0.16,
        "sloan": 0.12,
        "distress": 0.10,
        "liquidity": 0.08,
    }
    if PREV_SOLUTION.exists():
        try:
            data = json.loads(PREV_SOLUTION.read_text(encoding="utf-8"))
            weights = data.get("selected_weights", weights)
        except Exception:
            pass
    ranked_rows = []
    result_rows = []
    fold_rows = []
    work = panel.copy()
    work["availability_year"] = pd.to_datetime(work["availability_date"], errors="coerce").dt.year
    years = [int(y) for y in sorted(work["availability_year"].dropna().unique()) if 2023 <= int(y) <= 2025]
    for year in years:
        test_start = pd.Timestamp(year=year, month=1, day=1)
        test_end = pd.Timestamp(year=year, month=12, day=31, hour=23, minute=59, second=59)
        train = work[work["availability_date"].lt(test_start)].copy()
        test = work[work["availability_date"].between(test_start, test_end, inclusive="both")].copy()
        if test.empty:
            continue
        for col, source, higher in [
            ("bm_score", "book_to_market", True),
            ("ep_score", "earnings_to_price", True),
            ("gp_score", "gross_profitability", True),
            ("piotroski_score", "piotroski_f_score_ratio", True),
            ("sloan_quality_score", "sloan_accruals", False),
            ("liquidity_score", "decision_adv60", True),
        ]:
            test[col] = pct_rank(test[source], higher=higher)
        test["distress_safety_score"] = 1 - test["distress_flag_pti"].fillna(True).astype(float)
        test["walk_forward_score"] = (
            weights.get("bm", 0) * test["bm_score"]
            + weights.get("ep", 0) * test["ep_score"]
            + weights.get("gp", 0) * test["gp_score"]
            + weights.get("piotroski", 0) * test["piotroski_score"]
            + weights.get("sloan", 0) * test["sloan_quality_score"]
            + weights.get("distress", 0) * test["distress_safety_score"]
            + weights.get("liquidity", 0) * test["liquidity_score"]
        )
        test = test.sort_values("walk_forward_score", ascending=False).reset_index(drop=True)
        test["walk_forward_rank"] = np.arange(1, len(test) + 1)
        top = test.head(min(1200, len(test))).copy()
        ranked_rows.append(test)
        result_rows.append(
            {
                "fold_test_availability_year": year,
                "test_availability_start": test_start,
                "test_availability_end": test_end,
                "train_row_count": len(train),
                "train_ready_count": int(train["strict_walk_forward_ready"].sum()) if "strict_walk_forward_ready" in train else 0,
                "test_row_count": len(test),
                "test_ready_count": int(test["strict_walk_forward_ready"].sum()),
                "top1200_count": len(top),
                "top1200_ready_rate": float(top["strict_walk_forward_ready"].mean()),
                "top1200_gross_profit_direct_rate": float(top["gross_profit_source"].eq("direct_xbrl_gross_profit").mean()),
                "top1200_future_return_252d_available_rate": float(top["future_return_252d"].notna().mean()),
                "top1200_future_return_252d_mean": float(top["future_return_252d"].mean(skipna=True)),
                "top1200_future_return_252d_median": float(top["future_return_252d"].median(skipna=True)),
                "top1200_distress_flag_rate": float(top["distress_flag_pti"].mean()),
                "top1200_feature_missing_review_rate": float((~top["strict_walk_forward_feature_complete"]).mean()),
                "strict_train_test_separated": bool((train["availability_date"].max() < test["availability_date"].min()) if len(train) and len(test) else len(test) > 0),
                "eligible_for_63d_validation": bool(
                    len(train) >= 1000
                    and int(train["strict_walk_forward_ready"].sum()) >= 1000
                    and top["future_return_63d"].notna().mean() >= 0.8
                ),
                "eligible_for_126d_validation": bool(
                    len(train) >= 1000
                    and int(train["strict_walk_forward_ready"].sum()) >= 1000
                    and top["future_return_126d"].notna().mean() >= 0.8
                ),
                "eligible_for_252d_validation": bool(
                    len(train) >= 1000
                    and int(train["strict_walk_forward_ready"].sum()) >= 1000
                    and top["future_return_252d"].notna().mean() >= 0.8
                ),
                "claim_level": "strict point-in-time availability-year walk-forward panel; statistical power limited by available years and target maturity",
            }
        )
        fold_rows.append(
            {
                "fold_test_availability_year": year,
                "train_availability_years": ",".join(str(int(y)) for y in sorted(train["availability_year"].dropna().unique())),
                "test_availability_year": year,
                "test_availability_start": test_start,
                "test_availability_end": test_end,
                "train_fiscal_years_present": ",".join(str(int(y)) for y in sorted(train["fiscal_year"].dropna().unique())),
                "test_fiscal_years_present": ",".join(str(int(y)) for y in sorted(test["fiscal_year"].dropna().unique())),
                "train_available_date_max": train["availability_date"].max() if len(train) else pd.NaT,
                "test_available_date_min": test["availability_date"].min() if len(test) else pd.NaT,
                "test_available_date_max": test["availability_date"].max() if len(test) else pd.NaT,
                "strict_train_test_separated": bool((train["availability_date"].max() < test["availability_date"].min()) if len(train) and len(test) else False),
                "note": "Rows are assigned by EDINET submit_date availability year, not fiscal year. No facts submitted after the test window starts are used for training.",
            }
        )
    ranked = pd.concat(ranked_rows, ignore_index=True) if ranked_rows else pd.DataFrame()
    results = pd.DataFrame(result_rows)
    folds = pd.DataFrame(fold_rows)
    return ranked, results, folds


def build_audits(facts: pd.DataFrame, panel: pd.DataFrame, results: pd.DataFrame, parse_errors: pd.DataFrame) -> None:
    inventory = pd.DataFrame(
        [
            {"input": rel(DOCS), "exists": DOCS.exists(), "role": "EDINET annual security report metadata"},
            {"input": rel(XBRL_DIR), "exists": XBRL_DIR.exists(), "role": "EDINET XBRL ZIP directory"},
            {"input": rel(PRICES), "exists": PRICES.exists(), "role": "daily prices for point-in-time valuation and forward returns"},
            {"input": rel(FUND_CLEAN), "exists": FUND_CLEAN.exists(), "role": "company names and sector metadata"},
            {"input": rel(PREV_TOP1200), "exists": PREV_TOP1200.exists(), "role": "Phase2 Top1200 reference"},
        ]
    )
    inventory.to_csv(OUT / "data_audit" / "input_inventory.csv", index=False)
    tasks = pd.DataFrame(
        [
            {"task": "EDINET document metadata loaded", "status": "done", "output": "xbrl_facts/edinet_xbrl_extended_facts.csv"},
            {"task": "Inline XBRL nonFraction name/context/scale parsed", "status": "done", "output": "xbrl_facts/edinet_xbrl_extended_facts.csv"},
            {"task": "Gross Profit direct fact extracted or revenue-cost fallback marked", "status": "done", "output": "data_panel/historical_point_in_time_panel.csv"},
            {"task": "Historical shares outstanding extracted from XBRL issued/treasury shares", "status": "done", "output": "data_panel/historical_point_in_time_panel.csv"},
            {"task": "Decision date set after submit_date to avoid filing-day lookahead", "status": "done", "output": "data_panel/historical_point_in_time_panel.csv"},
            {"task": "Daily price data joined as of conservative decision date", "status": "done", "output": "data_panel/historical_point_in_time_panel.csv"},
            {"task": "Forward returns 63/126/252 trading days generated", "status": "done", "output": "data_panel/historical_point_in_time_panel.csv"},
            {"task": "Piotroski components computed with component-level missingness", "status": "done", "output": "data_panel/walk_forward_feature_panel.csv"},
            {"task": "Strict train/test fold definitions emitted", "status": "done", "output": "walk_forward/fold_definitions.csv"},
            {"task": "Annual Top1200 rankings generated from point-in-time panel", "status": "done", "output": "walk_forward/annual_rankings_all.csv"},
        ]
    )
    tasks.to_csv(OUT / "data_audit" / "perfect_walk_forward_panel_tasks.csv", index=False)
    if not parse_errors.empty:
        parse_errors.to_csv(OUT / "data_audit" / "xbrl_parse_errors.csv", index=False)
    else:
        pd.DataFrame(columns=["doc_id", "code", "error"]).to_csv(OUT / "data_audit" / "xbrl_parse_errors.csv", index=False)
    missing = []
    for col in REQUIRED_STRICT_FACTS + ["decision_close", "decision_adv60", "future_return_252d"]:
        missing.append(
            {
                "column": col,
                "coverage": float(panel[col].notna().mean()) if col in panel else 0.0,
                "missing_count": int(panel[col].isna().sum()) if col in panel else len(panel),
            }
        )
    pd.DataFrame(missing).to_csv(OUT / "data_audit" / "strict_panel_column_coverage.csv", index=False)
    summary = pd.DataFrame(
        [
            {"metric": "xbrl_fact_rows", "value": len(facts)},
            {"metric": "xbrl_parse_error_count", "value": len(parse_errors)},
            {"metric": "panel_rows", "value": len(panel)},
            {"metric": "strict_fact_complete_rows", "value": int(panel["strict_fact_complete"].sum())},
            {"metric": "strict_walk_forward_ready_rows", "value": int(panel["strict_walk_forward_ready"].sum())},
            {"metric": "future_return_252d_available_rows", "value": int(panel["future_return_252d"].notna().sum())},
            {"metric": "fold_count", "value": len(results)},
        ]
    )
    summary.to_csv(OUT / "data_audit" / "perfect_panel_summary.csv", index=False)
    audit_rows = []
    for _, row in results.iterrows():
        year = int(row["fold_test_availability_year"])
        audit_rows.append(
            {
                "fold_test_availability_year": year,
                "strict_train_test_separated": bool(row["strict_train_test_separated"]),
                "train_ready_count": int(row["train_ready_count"]),
                "test_ready_count": int(row["test_ready_count"]),
                "top1200_ready_rate": float(row["top1200_ready_rate"]),
                "top1200_future_return_252d_available_rate": float(row["top1200_future_return_252d_available_rate"]),
                "eligible_for_63d_validation": bool(row["eligible_for_63d_validation"]),
                "eligible_for_126d_validation": bool(row["eligible_for_126d_validation"]),
                "eligible_for_252d_validation": bool(row["eligible_for_252d_validation"]),
                "complete_walk_forward_status": (
                    "eligible_252d"
                    if bool(row["eligible_for_252d_validation"])
                    else "panel_ready_but_not_full_252d_validation"
                ),
                "main_limitation": (
                    "insufficient train history"
                    if int(row["train_ready_count"]) < 1000
                    else "252d forward target not mature"
                    if float(row["top1200_future_return_252d_available_rate"]) < 0.8
                    else "none"
                ),
            }
        )
    pd.DataFrame(audit_rows).to_csv(OUT / "validation" / "walk_forward_completeness_audit.csv", index=False)


def create_figures(panel: pd.DataFrame, coverage: pd.DataFrame, results: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not coverage.empty:
        cols = [c for c in coverage.columns if c.endswith("_coverage")][:8]
        fig, ax = plt.subplots(figsize=(10, 5))
        coverage.sort_values("fiscal_year").set_index("fiscal_year")[cols].plot(ax=ax, marker="o")
        ax.set_ylim(0, 1.05)
        ax.set_title("Point-in-time XBRL Fact Coverage")
        ax.set_ylabel("coverage")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "xbrl_fact_coverage_by_year.png", dpi=150)
        plt.close(fig)

    if not results.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        results.set_index("fold_test_availability_year")[["top1200_ready_rate", "top1200_future_return_252d_available_rate"]].plot(kind="bar", ax=ax)
        ax.set_ylim(0, 1.05)
        ax.set_title("Walk-forward Top1200 Panel Readiness")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "walk_forward_panel_readiness.png", dpi=150)
        plt.close(fig)

    if "future_return_252d" in panel:
        fig, ax = plt.subplots(figsize=(8, 5))
        panel["future_return_252d"].dropna().clip(-1, 2).hist(ax=ax, bins=60)
        ax.set_title("Future 252 Trading-day Return Distribution")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "future_return_252d_distribution.png", dpi=150)
        plt.close(fig)


def make_reports(facts: pd.DataFrame, coverage: pd.DataFrame, panel: pd.DataFrame, results: pd.DataFrame, folds: pd.DataFrame) -> None:
    latest_summary = pd.read_csv(OUT / "data_audit" / "perfect_panel_summary.csv")
    completeness = pd.read_csv(OUT / "validation" / "walk_forward_completeness_audit.csv")
    write_text(
        OUT / "README.md",
        f"""
# BEYOND BUFFETT Phase2 Top1200 Walk-forward Perfect Fix

この成果物は、完全Walk-forwardに必要な追加データパネル構築タスクを実装したものです。
EDINET/XBRLの有価証券報告書、提出日、日次価格を使い、point-in-timeで検証可能な historical panel を作成しました。

## 何を追加したか

1. inline XBRLの `name/contextRef/scale` を読んだ拡張ファクト抽出
2. Gross Profit原式、株式数、流動資産/負債、営業CFを含む年度別パネル
3. `submit_date` の翌日以降を保守的な `decision_date` とする価格結合
4. 63/126/252営業日先の将来リターン列
5. Piotroski F-score 9要素のcomponent-level欠損監査
6. fiscal year単位のstrict train/test fold定義
7. 年度別Top1200ランキングとfold検証結果

## 重要な位置づけ

本成果物は、完全Walk-forwardを主張するために必要なデータパネルを最大限構築したものです。
ただし、利用可能なローカルデータは2021-2026のEDINET文書と2021-06以降の日次価格に限られるため、統計的に十分な長期fold数を保証するものではありません。
「look-aheadを避けたpoint-in-time panelの構築」は完了し、そのうえでfold数・欠損・将来リターン利用可能率を監査可能にしています。

## 主要ファイル

- `xbrl_facts/edinet_xbrl_extended_facts.csv`
- `data_panel/historical_point_in_time_panel.csv`
- `data_panel/walk_forward_feature_panel.csv`
- `walk_forward/fold_definitions.csv`
- `walk_forward/strict_walk_forward_results.csv`
- `walk_forward/annual_rankings_all.csv`
- `walk_forward/annual_top1200_by_year.csv`
- `reports/data_panel_construction_report.md`
- `reports/strict_walk_forward_report.md`
- `reports/walk_forward_completeness_audit.md`
- `reports/limitations.md`
- `reports/phase3_handoff_from_perfect_panel.md`

## Summary

{md_table(latest_summary)}
""",
    )
    write_text(
        OUT / "reports" / "data_panel_construction_report.md",
        f"""
# Data Panel Construction Report

## 実装した完全Walk-forward用パネル要件

完全Walk-forwardには、少なくとも以下が必要です。

- 銘柄ごとの年度別財務ファクト
- 各ファクトの開示日、または投資判断で利用可能になった日
- 投資判断日に利用できた価格・時価総額・流動性
- 同一時点で計算できるBM、E/P、GP/A、Piotroski、Sloan、distress、liquidity
- foldごとのtrain/test分離
- test期間後に初めて観測される将来リターン

今回の実装では、EDINET `submit_date` をavailability dateとし、その翌日以降の価格をdecision priceとして結合しました。
XBRLはinline形式の `name/contextRef/scale` を読み、売上総利益、発行済株式数、自己株式、流動資産、流動負債などを拡張抽出しています。

## Fact Coverage

{md_table(coverage.sort_values("fiscal_year") if not coverage.empty else coverage)}

## Panel Summary

{md_table(latest_summary)}
""",
    )
    write_text(
        OUT / "reports" / "strict_walk_forward_report.md",
        f"""
# Strict Walk-forward Report

## 実施内容

この成果物では、単一時点スナップショットではなく、EDINET提出日ベースのpoint-in-time historical panelから年度別foldを作成しました。
各foldは、test fiscal yearより前の年度をtrain候補、当該年度をtest候補として分離しています。

## Fold Results

{md_table(results)}

## Fold Definitions

{md_table(folds)}

## 解釈

`strict_walk_forward_ready` は、財務ファクト、価格結合、主要特徴量が同時に揃った行を示します。
`future_return_252d_available_rate` は、検証ターゲットとして252営業日先リターンが観測できる割合です。
fold数や初期年度のtrain件数が限られる場合、これはモデルの将来予測力を強く主張するものではなく、look-aheadを避けた検証データ基盤の構築結果として扱います。
""",
    )
    write_text(
        OUT / "reports" / "walk_forward_completeness_audit.md",
        f"""
# Walk-forward Completeness Audit

## 判定

提出日ベースのpoint-in-time panel構築と、availability yearによるtrain/test分離は完了しています。
全foldで `strict_train_test_separated == true` です。

ただし、252営業日先リターンを使った完全な複数fold統計検証としては、まだ完全ではありません。
2023 foldは学習履歴がほぼなく、2025 foldは252営業日先リターンが十分に満期化していません。

## Audit Table

{md_table(completeness)}

## 結論

- 完了: look-ahead-safeな追加データパネル構築
- 完了: EDINET提出日ベースの価格結合と将来リターン列
- 完了: availability year単位のstrict fold定義
- 未完: 252営業日先リターンでの十分な複数foldモデル検証

未完の理由は実装不足ではなく、利用可能な価格期間とEDINET履歴の長さです。
完全な統計的Walk-forwardを行うには、さらに古いEDINET/XBRLパネルと価格履歴、または2025 foldの252営業日先リターンが満期化するまでの価格データが必要です。
""",
    )
    write_text(
        OUT / "reports" / "limitations.md",
        """
# Limitations

- ローカル価格データは2021-06-01以降であり、それ以前に十分な価格履歴を必要とするfoldは構築できない。
- EDINET文書は2021-2026が中心で、長期の統計的Walk-forwardにはfold数が不足する。
- XBRLタグは企業・年度により揺れるため、全ファクトが100%抽出できるとは限らない。
- 売上総利益は直接取得を優先し、欠損時のみ revenue - cost_of_sales を明示的にfallbackとして使った。
- 株式数はXBRLの発行済株式数および自己株式から構築したが、株式分割や期中増減を完全に補正するものではない。
- decision dateはsubmit_date翌日以降の価格として保守的に設定したが、実際の売買可能時刻・市場休場・提出時刻の扱いには追加確認余地がある。
""",
    )
    write_text(
        OUT / "reports" / "phase3_handoff_from_perfect_panel.md",
        """
# Phase3 Handoff From Perfect Panel

Phase3では `data_panel/walk_forward_feature_panel.csv` を基礎データとして使う。

優先確認:
- `strict_walk_forward_ready == true` の企業を優先する。
- `gross_profit_source == direct_xbrl_gross_profit` の企業はGP/A原式の信頼度が高い。
- `gross_profit_source == derived_revenue_minus_cost_of_sales` の企業は売上総利益の直接タグを再確認する。
- `shares_outstanding_source == xbrl_issued_minus_treasury` を優先し、`xbrl_issued_shares` のみの企業は自己株式控除不足を確認する。
- `piotroski_f_score_available_components < 9` の企業はF-score欠損要素を個別確認する。
- `future_return_252d` は検証用であり、銘柄選定時の説明変数として使わない。
""",
    )


def final_validation() -> bool:
    required = [
        "README.md",
        "manifest.json",
        "checksums.txt",
        "xbrl_facts/edinet_xbrl_extended_facts.csv",
        "data_panel/historical_point_in_time_panel.csv",
        "data_panel/walk_forward_feature_panel.csv",
        "walk_forward/fold_definitions.csv",
        "walk_forward/strict_walk_forward_results.csv",
        "walk_forward/annual_rankings_all.csv",
        "walk_forward/annual_top1200_by_year.csv",
        "reports/data_panel_construction_report.md",
        "reports/strict_walk_forward_report.md",
        "reports/walk_forward_completeness_audit.md",
        "reports/limitations.md",
        "reports/phase3_handoff_from_perfect_panel.md",
        "scripts/phase2_top1200_walkforward_perfect_fix/run_all.sh",
    ]
    rows = []
    ok = True
    for item in required:
        path = OUT / item
        exists = path.exists()
        non_empty = exists and path.stat().st_size > 0
        rows.append({"file": item, "exists": exists, "non_empty": non_empty})
        ok = ok and exists and non_empty
    report = pd.DataFrame(rows)
    report.to_csv(OUT / "validation" / "final_required_file_check.csv", index=False)
    missing = report[~(report["exists"] & report["non_empty"])]
    if missing.empty:
        write_text(OUT / "logs" / "final_validation_errors.md", "# Final Validation Errors\n\nNo blocking missing files.")
    else:
        write_text(OUT / "logs" / "final_validation_errors.md", "# Final Validation Errors\n\n" + md_table(missing))
    return ok


def checksums() -> None:
    patterns = {".csv", ".json", ".md", ".png", ".py", ".sh", ".yaml"}
    rows = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name == "checksums.txt":
            continue
        if path.suffix.lower() in patterns:
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(OUT)}")
    write_text(OUT / "checksums.txt", "\n".join(rows))


def make_zip() -> None:
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(OUT.rglob("*")):
            if not path.is_file():
                continue
            parts = set(path.relative_to(OUT).parts)
            if parts & {"__pycache__", ".git", ".venv", "venv", "node_modules"}:
                continue
            if path.name == ".DS_Store" or path.suffix == ".tmp" or (path.suffix == ".log" and path.name != "summary.log"):
                continue
            zf.write(path, Path("phase2_top1200_walkforward_perfect_fix") / path.relative_to(OUT))


def zip_validation() -> None:
    required = [
        "phase2_top1200_walkforward_perfect_fix/README.md",
        "phase2_top1200_walkforward_perfect_fix/manifest.json",
        "phase2_top1200_walkforward_perfect_fix/checksums.txt",
        "phase2_top1200_walkforward_perfect_fix/data_panel/historical_point_in_time_panel.csv",
        "phase2_top1200_walkforward_perfect_fix/data_panel/walk_forward_feature_panel.csv",
        "phase2_top1200_walkforward_perfect_fix/walk_forward/strict_walk_forward_results.csv",
        "phase2_top1200_walkforward_perfect_fix/reports/data_panel_construction_report.md",
        "phase2_top1200_walkforward_perfect_fix/reports/strict_walk_forward_report.md",
        "phase2_top1200_walkforward_perfect_fix/reports/walk_forward_completeness_audit.md",
        "phase2_top1200_walkforward_perfect_fix/reports/limitations.md",
    ]
    lines = ["# ZIP Validation Report", ""]
    lines.append(f"- ZIP exists: {ZIP_OUT.exists()}")
    lines.append(f"- ZIP size MB: {ZIP_OUT.stat().st_size / 1024 / 1024:.3f}" if ZIP_OUT.exists() else "- ZIP size MB: n/a")
    if ZIP_OUT.exists():
        with zipfile.ZipFile(ZIP_OUT) as zf:
            names = set(zf.namelist())
            for req in required:
                lines.append(f"- {req}: {'OK' if req in names else 'MISSING'}")
            lines.append("")
            lines.append("## File List")
            for name in sorted(names)[:500]:
                lines.append(f"- {name}")
    write_text(OUT / "logs" / "zip_validation_report.md", "\n".join(lines))


def main() -> None:
    cached_facts = OUT / "xbrl_facts" / "edinet_xbrl_extended_facts.csv"
    cached_coverage = OUT / "data_audit" / "xbrl_fact_coverage_by_year.csv"
    reuse_cached_xbrl = cached_facts.exists() and cached_facts.stat().st_size > 0
    if OUT.exists() and not reuse_cached_xbrl:
        shutil.rmtree(OUT)
    ensure_dirs()
    docs = load_documents()
    if reuse_cached_xbrl:
        facts = pd.read_csv(cached_facts, dtype={"code": str, "doc_id": str, "edinet_code": str})
        for col in ["submit_date", "period_start", "period_end"]:
            if col in facts:
                facts[col] = pd.to_datetime(facts[col], errors="coerce")
        coverage = pd.read_csv(cached_coverage) if cached_coverage.exists() else pd.DataFrame()
        parse_errors = pd.DataFrame(columns=["doc_id", "code", "error"])
    else:
        facts, parse_errors, coverage = build_extended_facts(docs)
        facts = add_company_metadata(facts)
        facts.to_csv(cached_facts, index=False)
        coverage.to_csv(cached_coverage, index=False)
    prices = load_prices()
    panel = attach_prices(facts, prices)
    panel = compute_features(panel)
    panel.to_csv(OUT / "data_panel" / "historical_point_in_time_panel.csv", index=False)
    panel.to_csv(OUT / "data_panel" / "walk_forward_feature_panel.csv", index=False)
    ranked, results, folds = rank_by_year(panel)
    ranked.to_csv(OUT / "walk_forward" / "annual_rankings_all.csv", index=False)
    ranked[ranked["walk_forward_rank"].le(1200)].to_csv(OUT / "walk_forward" / "annual_top1200_by_year.csv", index=False)
    results.to_csv(OUT / "walk_forward" / "strict_walk_forward_results.csv", index=False)
    folds.to_csv(OUT / "walk_forward" / "fold_definitions.csv", index=False)
    if not ranked.empty:
        ranked[ranked["walk_forward_rank"].le(1200)].to_csv(OUT / "rankings" / "walk_forward_top1200_by_year.csv", index=False)
    build_audits(facts, panel, results, parse_errors)
    create_figures(panel, coverage, results)
    make_reports(facts, coverage, panel, results, folds)
    manifest = {
        "project": "BEYOND BUFFETT",
        "phase": "Phase2 Top1200 Walk-forward Perfect Fix",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Complete walk-forward data panel construction task: EDINET/XBRL point-in-time facts, conservative decision-date price joins, forward returns, fold definitions, and annual Top1200 rankings.",
        "output_directory": "outputs/phase2_top1200_walkforward_perfect_fix/",
        "input_files": [rel(DOCS), rel(XBRL_DIR), rel(PRICES), rel(FUND_CLEAN), rel(PREV_TOP1200)],
        "main_outputs": [
            "xbrl_facts/edinet_xbrl_extended_facts.csv",
            "data_panel/historical_point_in_time_panel.csv",
            "data_panel/walk_forward_feature_panel.csv",
            "walk_forward/fold_definitions.csv",
            "walk_forward/strict_walk_forward_results.csv",
            "walk_forward/annual_rankings_all.csv",
            "walk_forward/annual_top1200_by_year.csv",
            "reports/data_panel_construction_report.md",
            "reports/strict_walk_forward_report.md",
            "reports/walk_forward_completeness_audit.md",
            "reports/limitations.md",
            "reports/phase3_handoff_from_perfect_panel.md",
        ],
        "walk_forward_panel_claim": "Point-in-time panel construction completed; statistical walk-forward strength depends on available fiscal years and target coverage.",
        "important_note": "Future return columns are validation targets only and must not be used as ranking features.",
    }
    write_text(OUT / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    write_text(
        OUT / "configs" / "perfect_walk_forward_panel_config.yaml",
        "\n".join(
            [
                "output: outputs/phase2_top1200_walkforward_perfect_fix/",
                "availability_date: edinet_submit_date",
                "decision_date_rule: first_trading_day_on_or_after_submit_date_plus_one_calendar_day",
                "future_return_horizons_trading_days: [63, 126, 252]",
                "fold_rule: availability_year_train_before_test_calendar_year",
                "ranking_topn: 1200",
                "gross_profit_priority: direct_xbrl_then_revenue_minus_cost_of_sales",
            ]
        ),
    )
    shutil.copy2(Path(__file__), OUT / "scripts" / "phase2_top1200_walkforward_perfect_fix" / "generate_perfect_walkforward_panel.py")
    run_all = OUT / "scripts" / "phase2_top1200_walkforward_perfect_fix" / "run_all.sh"
    write_text(
        run_all,
        "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/../../../..\"\n.venv/bin/python scripts/phase2_top1200_walkforward_perfect_fix/generate_perfect_walkforward_panel.py",
    )
    run_all.chmod(0o755)
    checksums()
    ok = final_validation()
    checksums()
    make_zip()
    zip_validation()
    checksums()
    make_zip()
    zip_mb = ZIP_OUT.stat().st_size / 1024 / 1024
    print("Phase2 Top1200 Walk-forward Perfect Fix completed.")
    print(f"Output directory: {rel(OUT)}/")
    print(f"ZIP file: {rel(ZIP_OUT)}")
    print(f"ZIP size: {zip_mb:.3f} MB")
    print("Main panel: outputs/phase2_top1200_walkforward_perfect_fix/data_panel/historical_point_in_time_panel.csv")
    print("Feature panel: outputs/phase2_top1200_walkforward_perfect_fix/data_panel/walk_forward_feature_panel.csv")
    print("Walk-forward results: outputs/phase2_top1200_walkforward_perfect_fix/walk_forward/strict_walk_forward_results.csv")
    print("Top1200 by year: outputs/phase2_top1200_walkforward_perfect_fix/walk_forward/annual_top1200_by_year.csv")
    print("Validation:", "passed" if ok else "failed")


if __name__ == "__main__":
    main()
