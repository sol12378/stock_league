from __future__ import annotations

import pandas as pd

from src.data.load_jpx import build_universe


def test_universe_excludes_etf_and_keeps_domestic_stock(tmp_path) -> None:
    source = tmp_path / "listed.xlsx"
    output = tmp_path / "universe.csv"
    pd.DataFrame(
        [
            {
                "Effective Date": "20260430",
                "Local Code": "1306",
                "Name (English)": "NEXT FUNDS TOPIX Exchange Traded Fund",
                "Section/Products": "ETFs/ ETNs",
                "33 Sector(Code)": "-",
                "33 Sector(name)": "-",
                "17 Sector(Code)": "-",
                "17 Sector(name)": "-",
                "Size Code (New Index Series)": "-",
                "Size (New Index Series)": "-",
            },
            {
                "Effective Date": "20260430",
                "Local Code": "7203",
                "Name (English)": "TOYOTA MOTOR CORPORATION",
                "Section/Products": "Prime Market (Domestic)",
                "33 Sector(Code)": "3700",
                "33 Sector(name)": "Transportation Equipment",
                "17 Sector(Code)": "6",
                "17 Sector(name)": "AUTOMOBILES TRANSPORTATION EQUIPMENT",
                "Size Code (New Index Series)": "1",
                "Size (New Index Series)": "TOPIX Core30",
            },
        ]
    ).to_excel(source, index=False)
    universe = build_universe(source, output)
    assert universe["ticker"].tolist() == ["7203.T"]
