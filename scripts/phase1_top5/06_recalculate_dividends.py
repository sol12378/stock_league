from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "phase1_top5"
ZIP_PATH = ROOT / "phase1_top5.zip"


def pct(v: float) -> str:
    return "" if pd.isna(v) else f"{v:.2%}"


def markdown_table(df: pd.DataFrame) -> str:
    d = df.copy()
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            if "yield" in col or col.endswith("_weight") or col.endswith("_contribution"):
                d[col] = d[col].map(pct)
            else:
                d[col] = d[col].map(lambda v: "" if pd.isna(v) else f"{v:,.2f}")
        else:
            d[col] = d[col].fillna("").astype(str)
    lines = [
        "| " + " | ".join(d.columns) + " |",
        "| " + " | ".join(["---"] * len(d.columns)) + " |",
    ]
    lines.extend("| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in d.values.tolist())
    return "\n".join(lines)


def fetch_dividend(row: pd.Series) -> dict[str, object]:
    ticker = f"{row['code']}.T"
    info = yf.Ticker(ticker).info
    price = info.get("regularMarketPrice") or info.get("currentPrice") or row.get("latest_price")
    forward_dps = info.get("dividendRate")
    trailing_dps = info.get("trailingAnnualDividendRate")
    chosen_dps = forward_dps if pd.notna(forward_dps) and forward_dps is not None else trailing_dps
    recalculated_yield = float(chosen_dps) / float(price) if chosen_dps is not None and price else None
    trailing_yield = float(trailing_dps) / float(price) if trailing_dps is not None and price else None
    return {
        "code": row["code"],
        "ticker": ticker,
        "company_name": row["company_name"],
        "sector": row["sector"],
        "price_used": price,
        "forward_annual_dps": forward_dps,
        "trailing_annual_dps": trailing_dps,
        "chosen_annual_dps": chosen_dps,
        "recalculated_dividend_yield": recalculated_yield,
        "trailing_dividend_yield_recalculated": trailing_yield,
        "yfinance_dividend_yield_raw": info.get("dividendYield"),
        "data_source": "Yahoo Finance via yfinance",
        "calculation": "chosen_annual_dps / price_used",
    }


def update_zip(paths: list[Path]) -> None:
    if not ZIP_PATH.exists():
        return
    with zipfile.ZipFile(ZIP_PATH, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        existing = set(zf.namelist())
        for path in paths:
            arc = str(path.relative_to(ROOT))
            if arc not in existing:
                zf.write(path, arc)


def main() -> None:
    top5 = pd.read_csv(OUT / "phase1_buffett_core_top5.csv", dtype={"code": str})
    rows = [fetch_dividend(row) for _, row in top5.iterrows()]
    div = pd.DataFrame(rows)
    div["core_weight_min"] = 0.04
    div["core_weight_max"] = 0.05
    div["portfolio_yield_contribution_min"] = div["recalculated_dividend_yield"] * div["core_weight_min"]
    div["portfolio_yield_contribution_max"] = div["recalculated_dividend_yield"] * div["core_weight_max"]
    div["annual_dividend_on_5m_if_4pct_weight"] = 5_000_000 * div["core_weight_min"] * div["recalculated_dividend_yield"]
    div["annual_dividend_on_5m_if_5pct_weight"] = 5_000_000 * div["core_weight_max"] * div["recalculated_dividend_yield"]
    csv_path = OUT / "phase1_top5_dividend_recalculation.csv"
    md_path = OUT / "phase1_top5_dividend_recalculation.md"
    div.to_csv(csv_path, index=False)
    weighted_min = div["portfolio_yield_contribution_min"].sum()
    weighted_max = div["portfolio_yield_contribution_max"].sum()
    annual_min = div["annual_dividend_on_5m_if_4pct_weight"].sum()
    annual_max = div["annual_dividend_on_5m_if_5pct_weight"].sum()
    md = [
        "# Phase1 Top5 Dividend Recalculation",
        "",
        "Top5のローカル配当利回りは欠損していたため、Yahoo Finance via yfinanceから年間DPSと株価を取得し、`年間DPS / 株価` で再計算した。",
        "",
        markdown_table(div[[
            "code",
            "company_name",
            "price_used",
            "chosen_annual_dps",
            "recalculated_dividend_yield",
            "trailing_annual_dps",
            "trailing_dividend_yield_recalculated",
        ]]),
        "",
        f"- Top5を最終20社内で各4%保有した場合の配当利回り寄与: {weighted_min:.2%}",
        f"- Top5を最終20社内で各5%保有した場合の配当利回り寄与: {weighted_max:.2%}",
        f"- 500万円ポートフォリオ換算の年間配当額目安（各4%）: {annual_min:,.0f}円",
        f"- 500万円ポートフォリオ換算の年間配当額目安（各5%）: {annual_max:,.0f}円",
        "",
        "注意: これは最新取得時点のDPS・株価に基づく概算であり、配当予想の変更、記念配当、無配転落、株価変動で変わる。",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    update_zip([csv_path, md_path])
    print(div[["code", "company_name", "price_used", "chosen_annual_dps", "recalculated_dividend_yield"]].to_string(index=False))
    print(f"annual dividend estimate if 4% each: {annual_min:,.0f} yen")
    print(f"annual dividend estimate if 5% each: {annual_max:,.0f} yen")


if __name__ == "__main__":
    main()
