from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config import load_config
from src.utils.logging import setup_logger


FINANCIAL_SECTORS = {
    "Banks",
    "Insurance",
    "Securities and Commodities Futures",
    "Other Financing Business",
}

EXCLUDED_PRODUCT_KEYWORDS = [
    "ETF",
    "ETN",
    "REIT",
    "Infrastructure Fund",
    "Infrastructure Funds",
    "Venture Funds",
    "Country Funds",
    "Foreign",
    "Equity Contribution Securities",
]

EXCLUDED_NAME_KEYWORDS = [
    "Exchange Traded Fund",
    "ETF",
    "ETN",
    "REIT",
    "Investment Corporation",
    "Infrastructure Fund",
    "Bond-Type Class Shares",
    "Preferred",
    "Class Shares",
]


def normalize_code(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    if re.fullmatch(r"\d{1,4}", text):
        return text.zfill(4)
    return text


def read_jpx_excel(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, dtype=str).rename(
        columns={
            "Local Code": "code",
            "Name (English)": "company_name",
            "Section/Products": "market",
            "33 Sector(Code)": "sector_33_code",
            "33 Sector(name)": "sector_33",
            "17 Sector(Code)": "sector_17_code",
            "17 Sector(name)": "sector_17",
            "Size Code (New Index Series)": "scale_category_code",
            "Size (New Index Series)": "scale_category",
            "Effective Date": "effective_date",
        }
    )


def _contains_any(series: pd.Series, keywords: list[str]) -> pd.Series:
    escaped = [re.escape(k) for k in keywords]
    return series.fillna("").str.contains("|".join(escaped), case=False, regex=True)


def build_universe(input_path: Path, output_path: Path) -> pd.DataFrame:
    raw = read_jpx_excel(input_path)
    df = raw.copy()
    df["code"] = df["code"].map(normalize_code)
    df["ticker"] = df["code"] + ".T"
    df["company_name"] = df["company_name"].fillna("").str.strip()
    df["market"] = df["market"].fillna("").str.strip()
    df["sector_33"] = df["sector_33"].replace("-", pd.NA)
    df["sector_17"] = df["sector_17"].replace("-", pd.NA)
    df["scale_category"] = df["scale_category"].replace("-", pd.NA)

    product_excluded = _contains_any(df["market"], EXCLUDED_PRODUCT_KEYWORDS)
    name_excluded = _contains_any(df["company_name"], EXCLUDED_NAME_KEYWORDS)
    valid_code = df["code"].str.match(r"^\d{4}[A-Z]?$", na=False)
    valid_sector = df["sector_33"].notna()
    ordinary_domestic = df["market"].str.contains("Domestic|PRO Market", case=False, na=False)
    keep = valid_code & valid_sector & ordinary_domestic & ~product_excluded & ~name_excluded

    universe = df.loc[keep].copy()
    universe["is_financial"] = universe["sector_33"].isin(FINANCIAL_SECTORS)
    universe = universe[
        [
            "effective_date",
            "code",
            "ticker",
            "company_name",
            "market",
            "sector_33_code",
            "sector_33",
            "sector_17_code",
            "sector_17",
            "scale_category_code",
            "scale_category",
            "is_financial",
        ]
    ].drop_duplicates("ticker")
    universe = universe.sort_values("ticker").reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(output_path, index=False)
    return universe


def main() -> None:
    config = load_config()
    logger = setup_logger("load_jpx", config.logs_dir)
    output = config.data_processed_dir / "universe.csv"
    universe = build_universe(config.jpx_listed_companies_path, output)
    logger.info("Wrote %s rows to %s", len(universe), output)


if __name__ == "__main__":
    main()
