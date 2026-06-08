from __future__ import annotations

import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError
from lxml import etree
from tqdm import tqdm

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


TAG_CANDIDATES: dict[str, list[str]] = {
    "revenue": [
        "NetSales",
        "Revenue",
        "SalesRevenue",
        "OperatingRevenue1",
        "RevenueFromContractsWithCustomers",
    ],
    "operating_income": ["OperatingIncome", "OperatingProfit", "OperatingProfitLoss"],
    "ordinary_income": ["OrdinaryIncome", "OrdinaryProfitLoss"],
    "net_income": [
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLoss",
        "NetIncome",
        "ProfitAttributableToOwnersOfParent",
    ],
    "total_assets": ["Assets", "TotalAssets"],
    "equity": [
        "Equity",
        "NetAssets",
        "EquityAttributableToOwnersOfParent",
        "NetAssetsSummaryOfBusinessResults",
    ],
    "operating_cf": ["NetCashProvidedByUsedInOperatingActivities"],
    "investing_cf": ["NetCashProvidedByUsedInInvestingActivities"],
    "financing_cf": ["NetCashProvidedByUsedInFinancingActivities"],
    "rd_expense": ["ResearchAndDevelopmentExpenses", "ResearchAndDevelopmentExpense"],
    "capex": ["PurchaseOfPropertyPlantAndEquipment", "PaymentsForPurchaseOfPropertyPlantAndEquipment"],
    "employees": ["NumberOfEmployees"],
}


def _local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1]


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    text = text.replace("△", "-").replace("−", "-")
    text = re.sub(r"^\((.*)\)$", r"-\1", text)
    if text in {"", "-", "－"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _context_priority(context_ref: str, metric: str) -> int:
    context = context_ref or ""
    if metric in {"total_assets", "equity", "employees"}:
        preferences = ["CurrentYearInstant", "CurrentYear", "Current", "Prior"]
    else:
        preferences = ["CurrentYearDuration", "CurrentYear", "Current", "Prior"]
    for idx, token in enumerate(preferences):
        if token in context:
            return idx
    return 99


def _candidate_metric(local_name: str) -> str | None:
    for metric, candidates in TAG_CANDIDATES.items():
        if local_name in candidates:
            return metric
    return None


def _iter_xml_members(zip_file: zipfile.ZipFile) -> list[str]:
    return [
        name
        for name in zip_file.namelist()
        if name.lower().endswith((".xbrl", ".xml", ".htm", ".html", ".xhtml"))
    ]


def parse_xbrl_zip(zip_path: Path) -> dict[str, float]:
    found: dict[str, list[tuple[int, float]]] = {metric: [] for metric in TAG_CANDIDATES}
    parser = etree.XMLParser(recover=True, huge_tree=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in _iter_xml_members(zf):
            try:
                root = etree.fromstring(zf.read(member), parser=parser)
            except Exception:
                continue
            for elem in root.iter():
                local = _local_name(str(elem.tag))
                metric = _candidate_metric(local)
                if metric is None:
                    continue
                number = _parse_number(elem.text)
                if number is None:
                    continue
                context_ref = elem.attrib.get("contextRef") or elem.attrib.get("contextref") or ""
                found[metric].append((_context_priority(context_ref, metric), number))

    result: dict[str, float] = {}
    for metric, values in found.items():
        if not values:
            result[metric] = np.nan
            continue
        values = sorted(values, key=lambda item: (item[0], -abs(item[1])))
        result[metric] = values[0][1]
    return result


def parse_all_edinet(config: AppConfig) -> pd.DataFrame:
    logger = setup_logger("parse_edinet_xbrl", config.logs_dir)
    docs_path = config.data_processed_dir / "edinet_documents.csv"
    if not docs_path.exists():
        empty = pd.DataFrame()
        empty.to_csv(config.data_processed_dir / "fundamentals_raw.csv", index=False)
        return empty

    try:
        docs = pd.read_csv(docs_path, dtype={"code": str, "doc_id": str})
    except EmptyDataError:
        docs = pd.DataFrame()
    if docs.empty:
        empty = pd.DataFrame(
            columns=[
                "code",
                "ticker",
                "doc_id",
                "filer_name",
                "submit_date",
                "period_start",
                "period_end",
                *TAG_CANDIDATES.keys(),
            ]
        )
        empty.to_csv(config.data_processed_dir / "fundamentals_raw.csv", index=False)
        pd.DataFrame(columns=["doc_id", "error"]).to_csv(
            config.logs_dir / "edinet_parse_failed.csv", index=False
        )
        logger.info("No EDINET documents to parse")
        return empty
    rows: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    for row in tqdm(docs.to_dict("records"), desc="parse edinet"):
        doc_id = str(row.get("doc_id"))
        zip_path = config.edinet_raw_dir / "xbrl" / f"{doc_id}.zip"
        if not zip_path.exists():
            failed.append({"doc_id": doc_id, "error": "zip missing"})
            continue
        try:
            metrics = parse_xbrl_zip(zip_path)
        except Exception as exc:
            failed.append({"doc_id": doc_id, "error": str(exc)})
            continue
        rows.append(
            {
                "code": row.get("code"),
                "ticker": f"{row.get('code')}.T",
                "doc_id": doc_id,
                "filer_name": row.get("filer_name"),
                "submit_date": row.get("submit_date"),
                "period_start": row.get("period_start"),
                "period_end": row.get("period_end"),
                **metrics,
            }
        )

    raw = pd.DataFrame(rows)
    raw.to_csv(config.data_processed_dir / "fundamentals_raw.csv", index=False)
    pd.DataFrame(failed).to_csv(config.logs_dir / "edinet_parse_failed.csv", index=False)
    logger.info("Parsed %s EDINET fact rows", len(raw))
    return raw


def main() -> None:
    parse_all_edinet(load_config())


if __name__ == "__main__":
    main()
