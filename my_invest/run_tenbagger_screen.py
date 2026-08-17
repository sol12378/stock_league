from __future__ import annotations

import io
import json
import math
import re
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lxml import etree, html


ROOT = Path("..").resolve()
OUT_DIR = Path("outputs/tenbagger_screen_20260814")
OUTER_ZIP = ROOT / "data/raw/edinet/xbrl.zip"
AS_OF_DATE = pd.Timestamp("2026-08-14")
LISTING_CUTOFF = AS_OF_DATE - pd.DateOffset(years=5)

REVENUE_KEYWORDS = (
    "Revenue",
    "NetSales",
    "OperatingRevenue",
    "OperatingRevenues",
    "OrdinaryRevenue",
    "OrdinaryRevenues",
)
OPERATING_INCOME_KEYWORDS = ("OperatingIncome", "OperatingProfitLoss", "OperatingProfit")
SUMMARY_CONTEXTS = [
    "Prior4YearDuration",
    "Prior3YearDuration",
    "Prior2YearDuration",
    "Prior1YearDuration",
    "CurrentYearDuration",
]
CORPORATE_WORDS = (
    "株式会社",
    "有限会社",
    "合同会社",
    "銀行",
    "信託",
    "保険",
    "証券",
    "投資法人",
    "投資事業",
    "組合",
    "財団",
    "機構",
    "FUND",
    "CAPITAL",
    "HOLDINGS",
    "LTD",
    "LIMITED",
    "INC",
    "LLC",
    "CORPORATION",
    "PARTNERS",
    "TRUST",
    "NOMINEES",
)


def local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1]


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", value).strip().replace(",", "")
    text = text.replace("△", "-").replace("−", "-")
    text = re.sub(r"^\((.*)\)$", r"-\1", text)
    if text in {"", "-", "－"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).upper()
    text = re.sub(r"[\s\u3000・･\.。,，()（）\[\]【】'\"‐ー\-]", "", text)
    return text


def parse_context_periods(root: etree._Element) -> dict[str, dict[str, str | None]]:
    periods: dict[str, dict[str, str | None]] = {}
    for elem in root.iter():
        if local_name(str(elem.tag)) != "context":
            continue
        context_id = elem.attrib.get("id", "")
        start = end = instant = None
        for child in elem.iter():
            child_name = local_name(str(child.tag))
            if child_name == "startDate":
                start = child.text
            elif child_name == "endDate":
                end = child.text
            elif child_name == "instant":
                instant = child.text
        periods[context_id] = {"start": start, "end": end, "instant": instant}
    return periods


def context_variant(context: str, base: str) -> str | None:
    if context == base:
        return "consolidated"
    if context == f"{base}_NonConsolidatedMember":
        return "nonconsolidated"
    return None


def concept_priority(name: str, kind: str) -> int:
    if kind == "revenue":
        order = ["RevenueIFRS", "NetSales", "Revenue", "OperatingRevenue1", "OperatingRevenues"]
    else:
        order = ["OperatingProfitLossIFRS", "OperatingIncome", "OperatingProfitLoss", "OperatingProfit"]
    for idx, token in enumerate(order):
        if name.startswith(token):
            return len(order) - idx
    return 0


def choose_summary_series(
    facts: dict[str, dict[str, float]], kind: str
) -> tuple[str | None, str | None, list[float | None], list[str | None]]:
    keywords = REVENUE_KEYWORDS if kind == "revenue" else OPERATING_INCOME_KEYWORDS
    options: list[tuple[tuple[int, int, int], str, str, list[float | None], list[str | None]]] = []
    for concept, by_context in facts.items():
        if "SummaryOfBusinessResults" not in concept or not any(k in concept for k in keywords):
            continue
        for variant in ("consolidated", "nonconsolidated"):
            values: list[float | None] = []
            contexts: list[str | None] = []
            for base in SUMMARY_CONTEXTS:
                context = base if variant == "consolidated" else f"{base}_NonConsolidatedMember"
                values.append(by_context.get(context))
                contexts.append(context if context in by_context else None)
            present = sum(v is not None and np.isfinite(v) for v in values)
            score = (present, 1 if variant == "consolidated" else 0, concept_priority(concept, kind))
            options.append((score, concept, variant, values, contexts))
    if not options:
        return None, None, [None] * 5, [None] * 5
    _, concept, variant, values, contexts = max(options, key=lambda x: x[0])
    return concept, variant, values, contexts


def choose_current_operating_fact(
    facts: dict[str, dict[str, float]], preferred_variant: str | None
) -> tuple[str | None, str | None, float | None, str | None]:
    options = []
    for concept, by_context in facts.items():
        if not any(k in concept for k in OPERATING_INCOME_KEYWORDS):
            continue
        if any(blocked in concept for blocked in ("Segment", "PerShare", "Margin", "GrowthRate")):
            continue
        for variant in ("consolidated", "nonconsolidated"):
            context = "CurrentYearDuration" if variant == "consolidated" else "CurrentYearDuration_NonConsolidatedMember"
            value = by_context.get(context)
            if value is None:
                continue
            score = (
                2 if variant == preferred_variant else 0,
                1 if variant == "consolidated" else 0,
                concept_priority(concept, "operating"),
                1 if "SummaryOfBusinessResults" not in concept else 0,
            )
            options.append((score, concept, variant, value, context))
    if not options:
        return None, None, None, None
    _, concept, variant, value, context = max(options, key=lambda x: x[0])
    return concept, variant, value, context


def parse_japanese_month(value: str) -> tuple[int, int, int] | None:
    clean = unicodedata.normalize("NFKC", value)
    match = re.search(r"(19\d{2}|20\d{2})年\s*(\d{1,2})月(?:\s*(\d{1,2})日)?", clean)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3) or 1)
    try:
        date(year, month, day)
    except ValueError:
        return None
    return year, month, day


def extract_history_listing(text_block: str | None) -> tuple[str | None, str | None]:
    if not text_block:
        return None, None
    try:
        root = html.fromstring(f"<div>{text_block}</div>")
        rows = []
        for tr in root.xpath(".//tr"):
            cells = [" ".join(cell.text_content().split()) for cell in tr.xpath("./th|./td")]
            if len(cells) >= 2:
                rows.append((cells[0], " ".join(cells[1:])))
    except Exception:
        rows = []
    candidates: list[tuple[date, str]] = []
    for date_text, event in rows:
        event_clean = unicodedata.normalize("NFKC", event)
        if "上場" not in event_clean:
            continue
        if not any(token in event_clean for token in ("証券取引所", "JASDAQ", "ジャスダック", "マザーズ")):
            continue
        parsed = parse_japanese_month(date_text)
        if not parsed:
            continue
        candidates.append((date(*parsed), f"{date_text}: {event_clean}"))
    if not candidates:
        plain = " ".join(html.fromstring(f"<div>{text_block}</div>").text_content().split())
        for match in re.finditer(r"((?:19|20)\d{2}年\s*\d{1,2}月(?:\s*\d{1,2}日)?).{0,120}?上場", plain):
            parsed = parse_japanese_month(match.group(1))
            if parsed:
                candidates.append((date(*parsed), match.group(0)))
    if not candidates:
        return None, None
    listing_date, evidence = min(candidates, key=lambda x: x[0])
    return listing_date.isoformat(), evidence[:500]


def is_individual_holder(name: str | None) -> bool:
    if not name:
        return False
    normalized = unicodedata.normalize("NFKC", name).upper()
    return not any(word in normalized for word in CORPORATE_WORDS)


def extract_one_document(raw_zip: bytes) -> dict[str, Any]:
    parser = etree.XMLParser(recover=True, huge_tree=True)
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as inner:
        members = [
            n
            for n in inner.namelist()
            if n.startswith("XBRL/PublicDoc/") and n.lower().endswith(".xbrl")
        ]
        if not members:
            return {"parse_error": "public xbrl instance missing"}
        root = etree.fromstring(inner.read(members[0]), parser=parser)

    context_periods = parse_context_periods(root)
    facts: dict[str, dict[str, float]] = defaultdict(dict)
    text_facts: dict[str, dict[str, str]] = defaultdict(dict)
    wanted_text = {
        "NameMajorShareholders",
        "NameInformationAboutDirectorsAndCorporateAuditors",
        "OfficialTitleOrPositionInformationAboutDirectorsAndCorporateAuditors",
        "CompanyHistoryTextBlock",
    }
    wanted_numeric = {
        "ShareholdingRatio",
        "NumberOfSharesHeld",
        "NumberOfSharesHeldOrdinarySharesInformationAboutDirectorsAndCorporateAuditors",
    }
    for elem in root.iter():
        name = local_name(str(elem.tag))
        context = elem.attrib.get("contextRef") or elem.attrib.get("contextref") or ""
        current_operating_fact = (
            any(k in name for k in OPERATING_INCOME_KEYWORDS)
            and context in {"CurrentYearDuration", "CurrentYearDuration_NonConsolidatedMember"}
        )
        if "SummaryOfBusinessResults" in name or name in wanted_numeric or name in wanted_text or current_operating_fact:
            if name in wanted_text:
                if elem.text:
                    text_facts[name][context] = elem.text
            else:
                number = parse_number(elem.text)
                if number is not None:
                    facts[name][context] = number

    revenue_concept, variant, revenues, revenue_contexts = choose_summary_series(facts, "revenue")
    op_concept, op_variant, op_values, op_contexts = choose_summary_series(facts, "operating_income")
    if variant and op_variant and variant != op_variant:
        # Preserve consolidation consistency when an alternate operating series exists.
        matching = []
        for concept, by_context in facts.items():
            if "SummaryOfBusinessResults" not in concept or not any(k in concept for k in OPERATING_INCOME_KEYWORDS):
                continue
            contexts = [base if variant == "consolidated" else f"{base}_NonConsolidatedMember" for base in SUMMARY_CONTEXTS]
            values = [by_context.get(c) for c in contexts]
            matching.append((sum(v is not None for v in values), concept_priority(concept, "operating"), concept, values, contexts))
        if matching:
            _, _, op_concept, op_values, op_contexts = max(matching)
            op_variant = variant
    if op_values[-1] is None:
        fallback_concept, fallback_variant, fallback_value, fallback_context = choose_current_operating_fact(facts, variant)
        if fallback_value is not None:
            op_concept = fallback_concept
            op_variant = fallback_variant
            op_values[-1] = fallback_value
            op_contexts[-1] = fallback_context

    period_starts: list[str | None] = []
    period_ends: list[str | None] = []
    for context in revenue_contexts:
        meta = context_periods.get(context or "", {})
        period_starts.append(meta.get("start"))
        period_ends.append(meta.get("end"))

    shareholders = []
    for context, name in text_facts.get("NameMajorShareholders", {}).items():
        match = re.search(r"No(\d+)MajorShareholdersMember", context)
        if not match:
            continue
        shareholders.append(
            {
                "rank": int(match.group(1)),
                "name": " ".join(name.split()),
                "ratio": facts.get("ShareholdingRatio", {}).get(context),
                "shares": facts.get("NumberOfSharesHeld", {}).get(context),
            }
        )
    shareholders.sort(key=lambda x: x["rank"])

    officer_names = text_facts.get("NameInformationAboutDirectorsAndCorporateAuditors", {})
    officer_titles = text_facts.get("OfficialTitleOrPositionInformationAboutDirectorsAndCorporateAuditors", {})
    officers = []
    for context, name in officer_names.items():
        title = officer_titles.get(context, "")
        shares = facts.get("NumberOfSharesHeldOrdinarySharesInformationAboutDirectorsAndCorporateAuditors", {}).get(context)
        officers.append({"name": " ".join(name.split()), "title": " ".join(title.split()), "shares": shares})
    leader_regex = re.compile(r"代表|社長|CEO|ＣＥＯ", re.I)
    leaders = [o for o in officers if leader_regex.search(o["title"])]
    top_holder = shareholders[0] if shareholders else {"rank": None, "name": None, "ratio": None, "shares": None}
    top_norm = normalize_name(top_holder.get("name"))
    matched_leader = None
    for leader in leaders:
        leader_norm = normalize_name(leader["name"])
        if leader_norm and top_norm and (leader_norm == top_norm or leader_norm in top_norm or top_norm in leader_norm):
            matched_leader = leader
            break
    history = next(iter(text_facts.get("CompanyHistoryTextBlock", {}).values()), None)
    history_listing_date, history_listing_evidence = extract_history_listing(history)

    return {
        "revenue_concept": revenue_concept,
        "revenue_variant": variant,
        **{f"revenue_p{i}": value for i, value in enumerate(revenues)},
        **{f"period_start_p{i}": value for i, value in enumerate(period_starts)},
        **{f"period_end_p{i}": value for i, value in enumerate(period_ends)},
        "operating_income_concept": op_concept,
        "operating_income_variant": op_variant,
        "operating_income_current": op_values[-1],
        "operating_income_context": op_contexts[-1],
        "top_shareholder_name": top_holder.get("name"),
        "top_shareholder_ratio": top_holder.get("ratio"),
        "top_shareholder_shares": top_holder.get("shares"),
        "top_holder_is_individual": is_individual_holder(top_holder.get("name")),
        "leaders": " / ".join(f"{o['name']}（{o['title']}）" for o in leaders),
        "leader_names": " / ".join(o["name"] for o in leaders),
        "leader_is_top_shareholder": matched_leader is not None,
        "matched_leader": matched_leader["name"] if matched_leader else None,
        "history_listing_date": history_listing_date,
        "history_listing_evidence": history_listing_evidence,
        "shareholders_json": json.dumps(shareholders, ensure_ascii=False),
        "officers_json": json.dumps(officers, ensure_ascii=False),
        "parse_error": None,
    }


def growth_rate(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or not np.isfinite(current) or not np.isfinite(prior) or prior <= 0:
        return None
    return current / prior - 1.0


def safe_cagr(current: float | None, prior: float | None, years: int) -> float | None:
    if current is None or prior is None or prior <= 0 or current <= 0:
        return None
    return (current / prior) ** (1.0 / years) - 1.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    universe = pd.read_csv(ROOT / "data/processed/universe.csv", dtype={"code": str})
    universe["code"] = universe["code"].str.zfill(4)
    docs = pd.read_csv(ROOT / "data/processed/edinet_documents.csv", dtype={"code": str, "doc_id": str})
    docs["code"] = docs["code"].str.zfill(4)
    docs["submit_date_parsed"] = pd.to_datetime(docs["submit_date"], errors="coerce")
    docs = docs[docs["submit_date_parsed"] <= AS_OF_DATE].sort_values(["code", "submit_date_parsed"])
    latest_docs = docs.groupby("code", as_index=False).tail(1)

    extracted_rows = []
    with zipfile.ZipFile(OUTER_ZIP) as outer:
        available = set(outer.namelist())
        total = len(latest_docs)
        for idx, row in enumerate(latest_docs.itertuples(index=False), start=1):
            member = f"xbrl/{row.doc_id}.zip"
            base = {
                "code": row.code,
                "doc_id": row.doc_id,
                "filer_name": row.filer_name,
                "submit_date": row.submit_date,
                "period_start_latest": row.period_start,
                "period_end_latest": row.period_end,
            }
            try:
                if member not in available:
                    extracted = {"parse_error": "nested zip missing"}
                else:
                    extracted = extract_one_document(outer.read(member))
            except Exception as exc:
                extracted = {"parse_error": f"{type(exc).__name__}: {exc}"}
            extracted_rows.append({**base, **extracted})
            if idx % 250 == 0 or idx == total:
                print(f"parsed {idx}/{total}", flush=True)

    extracted_df = pd.DataFrame(extracted_rows)
    extracted_df.to_csv(OUT_DIR / "xbrl_latest_extracted.csv", index=False)

    prices = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker"])
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    price_dates = prices.groupby("ticker")["date"].agg(first_price_date="min", last_price_date="max").reset_index()

    results = universe.merge(extracted_df, on="code", how="left").merge(price_dates, on="ticker", how="left")
    for i in range(1, 5):
        results[f"revenue_growth_{i}"] = [
            growth_rate(cur, prior)
            for cur, prior in zip(results[f"revenue_p{i}"], results[f"revenue_p{i-1}"])
        ]
    results["revenue_cagr_4y"] = [
        safe_cagr(cur, prior, 4) for cur, prior in zip(results["revenue_p4"], results["revenue_p0"])
    ]
    results["revenue_5y_complete"] = results[[f"revenue_p{i}" for i in range(5)]].notna().all(axis=1)
    results["c1_each_yoy_20"] = results[[f"revenue_growth_{i}" for i in range(1, 5)]].ge(0.20).all(axis=1) & results["revenue_5y_complete"]
    results["c1_cagr_20"] = results["revenue_cagr_4y"].ge(0.20) & results["revenue_5y_complete"]
    results["operating_margin_latest"] = results["operating_income_current"] / results["revenue_p4"].replace(0, np.nan)
    results["c2_operating_margin_10"] = results["operating_margin_latest"].ge(0.10)
    results["listing_date_proxy"] = results["history_listing_date"].fillna(results["first_price_date"].dt.strftime("%Y-%m-%d"))
    results["listing_date_for_test"] = pd.to_datetime(results["listing_date_proxy"], errors="coerce")
    # For a history parser miss, a first local trade after the cutoff is still strong evidence of a recent IPO.
    results.loc[results["first_price_date"] >= LISTING_CUTOFF, "listing_date_for_test"] = results.loc[
        results["first_price_date"] >= LISTING_CUTOFF, "first_price_date"
    ]
    results["listing_date_source"] = np.where(
        results["first_price_date"] >= LISTING_CUTOFF,
        "local_price_first_trade",
        np.where(results["history_listing_date"].notna(), "EDINET_company_history", "not_identified_before_local_window"),
    )
    results["c3_listed_within_5y"] = results["listing_date_for_test"].ge(LISTING_CUTOFF)
    results["c4_leader_top_holder_strict"] = results["leader_is_top_shareholder"].fillna(False).astype(bool)
    results["c4_owner_proxy_broad"] = (
        results["c4_leader_top_holder_strict"] | results["top_holder_is_individual"].fillna(False).astype(bool)
    )
    strict_cols = ["c1_each_yoy_20", "c2_operating_margin_10", "c3_listed_within_5y", "c4_leader_top_holder_strict"]
    cagr_cols = ["c1_cagr_20", "c2_operating_margin_10", "c3_listed_within_5y", "c4_leader_top_holder_strict"]
    proxy_cols = ["c1_cagr_20", "c2_operating_margin_10", "c3_listed_within_5y", "c4_owner_proxy_broad"]
    results["strict_overlap_count"] = results[strict_cols].sum(axis=1)
    results["cagr_overlap_count"] = results[cagr_cols].sum(axis=1)
    results["cagr_owner_proxy_overlap_count"] = results[proxy_cols].sum(axis=1)

    duration_days = []
    for _, row in results.iterrows():
        spans = []
        for i in range(5):
            start = pd.to_datetime(row.get(f"period_start_p{i}"), errors="coerce")
            end = pd.to_datetime(row.get(f"period_end_p{i}"), errors="coerce")
            if pd.notna(start) and pd.notna(end):
                spans.append((end - start).days + 1)
        duration_days.append("/".join(str(x) for x in spans))
    results["fiscal_period_days"] = duration_days
    results["growth_quality_flag"] = np.where(
        results["revenue_5y_complete"],
        "OK",
        "5期売上不足",
    )

    results = results.sort_values(
        ["strict_overlap_count", "cagr_overlap_count", "cagr_owner_proxy_overlap_count", "revenue_cagr_4y", "operating_margin_latest"],
        ascending=[False, False, False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    results.insert(0, "screen_rank", np.arange(1, len(results) + 1))
    results.to_csv(OUT_DIR / "screening_all_companies.csv", index=False)

    candidate_mask = (
        (results["strict_overlap_count"] >= 3)
        | (results["cagr_overlap_count"] >= 3)
        | (results["cagr_owner_proxy_overlap_count"] >= 3)
    )
    candidates = results[candidate_mask].copy()
    candidates.to_csv(OUT_DIR / "ranked_candidates.csv", index=False)

    condition_cols = {
        "C1_strict_each_yoy": "c1_each_yoy_20",
        "C1_cagr": "c1_cagr_20",
        "C2_margin": "c2_operating_margin_10",
        "C3_recent_listing": "c3_listed_within_5y",
        "C4_leader_no1": "c4_leader_top_holder_strict",
        "C4_owner_proxy": "c4_owner_proxy_broad",
    }
    summary_rows = []
    for label, col in condition_cols.items():
        summary_rows.append({"condition": label, "matched": int(results[col].sum()), "coverage": int(results[col].notna().sum())})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT_DIR / "condition_summary.csv", index=False)

    overlap_labels = ["c1_cagr_20", "c2_operating_margin_10", "c3_listed_within_5y", "c4_leader_top_holder_strict"]
    matrix = []
    for left in overlap_labels:
        row = {"condition": left}
        for right in overlap_labels:
            row[right] = int((results[left] & results[right]).sum())
        matrix.append(row)
    pd.DataFrame(matrix).to_csv(OUT_DIR / "overlap_matrix.csv", index=False)

    distribution = (
        results.groupby("cagr_overlap_count", dropna=False).size().rename("companies").reset_index().sort_values("cagr_overlap_count")
    )
    distribution.to_csv(OUT_DIR / "overlap_distribution.csv", index=False)

    checks = {
        "universe_rows": int(len(universe)),
        "latest_docs": int(len(latest_docs)),
        "parsed_rows": int(extracted_df["parse_error"].isna().sum()),
        "parse_errors": int(extracted_df["parse_error"].notna().sum()),
        "five_year_revenue_coverage": int(results["revenue_5y_complete"].sum()),
        "operating_margin_coverage": int(results["operating_margin_latest"].notna().sum()),
        "listing_date_identified": int(results["listing_date_for_test"].notna().sum()),
        "top_shareholder_coverage": int(results["top_shareholder_name"].notna().sum()),
        "leader_coverage": int(results["leader_names"].fillna("").ne("").sum()),
        "strict_four_condition_matches": int((results["strict_overlap_count"] == 4).sum()),
        "cagr_four_condition_matches": int((results["cagr_overlap_count"] == 4).sum()),
        "cagr_proxy_four_condition_matches": int((results["cagr_owner_proxy_overlap_count"] == 4).sum()),
    }
    (OUT_DIR / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
