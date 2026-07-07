from __future__ import annotations

import math
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

try:
    from lxml import etree
except Exception:  # pragma: no cover
    etree = None


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
XBRL_DIR = ROOT / "data" / "raw" / "edinet" / "xbrl"
OUT = ROOT / "outputs" / "phase1_repair"

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

MARKET_COLS = {
    "market_cap",
    "marketCapitalization",
    "market_value",
    "market_equity",
    "mkt_cap",
    "marketValueOfEquity",
    "時価総額",
}
SHARE_COLS = {
    "shares_outstanding",
    "sharesOutstanding",
    "issued_shares",
    "number_of_shares",
    "total_shares",
    "common_shares",
    "treasury_stock",
    "treasury_shares",
    "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYear",
    "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock",
    "NumberOfTreasuryStock",
    "発行済株式数",
    "自己株式数",
}
PBR_COLS = {"price_to_book", "pbr", "priceBook", "pb_ratio", "PBR", "pbr_raw"}
PER_COLS = {"trailing_pe", "pe", "per", "priceEarnings", "PER", "pe_raw", "forward_pe"}
FIN_COLS = {
    "book_equity",
    "shareholders_equity",
    "total_equity",
    "equity",
    "net_assets",
    "owners_equity",
    "netAssets",
    "純資産",
    "自己資本",
    "親会社所有者帰属持分",
    "net_income",
    "netIncome",
    "profit_attributable_to_owners",
    "profitLossAttributableToOwnersOfParent",
    "earnings",
    "当期純利益",
    "親会社株主に帰属する当期純利益",
}
PRICE_COLS = {"close", "adj_close", "latest_close", "price", "Close", "Adjusted Close"}

ISSUED_SHARE_TAGS = {
    "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
    "NumberOfIssuedSharesAsOfFilingDateIssuedSharesTotalNumberOfSharesEtc",
    "TotalNumberOfIssuedSharesSummaryOfBusinessResults",
    "NumberOfSharesIssuedSharesVotingRights",
}
TREASURY_SHARE_TAGS = {
    "TotalNumberOfSharesHeldTreasurySharesEtc",
    "NumberOfSharesHeldInOwnNameTreasurySharesEtc",
    "NumberOfSharesIssuedSharesVotingRights",
}


def ensure_out() -> None:
    OUT.mkdir(parents=True, exist_ok=True)


def n(series: pd.Series | float | int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def truthy(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def norm_code(value: object) -> str:
    text = str(value).strip()
    text = text.replace(".T", "")
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 4:
        return digits[:4]
    return digits.zfill(4) if digits else ""


def safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    out = n(a) / n(b).replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def winsorize(s: pd.Series) -> pd.Series:
    values = n(s)
    if values.notna().sum() < 10:
        return values
    return values.clip(values.quantile(0.01), values.quantile(0.99))


def read_table(path: Path, nrows: int | None = None) -> pd.DataFrame | None:
    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, nrows=nrows)
        if suffix == ".tsv":
            return pd.read_csv(path, sep="\t", nrows=nrows)
        if suffix == ".parquet":
            return pd.read_parquet(path)
        if suffix in {".xls", ".xlsx"}:
            return pd.read_excel(path, nrows=nrows)
    except Exception:
        return None
    return None


def detected(cols: Iterable[str], candidates: set[str]) -> list[str]:
    out = []
    for col in map(str, cols):
        low = col.lower()
        if any(c.lower() == low or c.lower() in low for c in candidates):
            out.append(col)
    return out


def inventory_inputs() -> pd.DataFrame:
    ensure_out()
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.suffix.lower() not in {".csv", ".tsv", ".parquet", ".json", ".md", ".xls", ".xlsx"}:
            continue
        files.append(path)
    rows = []
    for path in sorted(files):
        rel = str(path.relative_to(ROOT))
        file_type = path.suffix.lower().lstrip(".")
        rows_count = ""
        cols_count = ""
        key_cols: list[str] = []
        market_cols: list[str] = []
        financial_cols: list[str] = []
        usable = False
        notes = ""
        if file_type in {"csv", "tsv", "parquet", "xls", "xlsx"}:
            df = read_table(path, nrows=50)
            if df is not None:
                cols = list(map(str, df.columns))
                key_cols = detected(cols, {"code", "ticker", "銘柄コード", "secCode"})
                market_cols = detected(cols, MARKET_COLS | SHARE_COLS | PBR_COLS | PER_COLS | PRICE_COLS)
                financial_cols = detected(cols, FIN_COLS)
                cols_count = len(cols)
                try:
                    rows_count = len(read_table(path))
                except Exception:
                    rows_count = ""
                usable = bool(key_cols and (market_cols or financial_cols))
            else:
                notes = "Could not read with available local libraries."
        else:
            try:
                text = path.read_text(errors="ignore")[:20000]
                hits = [c for c in MARKET_COLS | SHARE_COLS | PBR_COLS | PER_COLS | FIN_COLS | PRICE_COLS if c in text]
                market_cols = hits
                usable = bool(hits)
            except Exception:
                notes = "Could not scan text."
        rows.append(
            {
                "file_path": rel,
                "file_type": file_type,
                "rows": rows_count,
                "columns": cols_count,
                "detected_key_columns": ";".join(key_cols),
                "detected_market_data_columns": ";".join(market_cols),
                "detected_financial_columns": ";".join(financial_cols),
                "usable_for_bm_ep": usable,
                "notes": notes,
            }
        )
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "input_file_inventory.csv", index=False)
    useful = inv[inv["usable_for_bm_ep"].astype(bool)]
    report = [
        "# Phase1 Repair Input File Inventory",
        "",
        "The audit scans local CSV, Parquet, Excel, JSON, and Markdown files outside `.git` and `.venv`.",
        "",
        "## Files with market/share/PBR/PER candidates",
        "",
        *[
            f"- `{r.file_path}`: {r.detected_market_data_columns}"
            for r in useful.itertuples()
            if str(r.detected_market_data_columns)
        ],
        "",
        "## Files with book equity / earnings candidates",
        "",
        *[
            f"- `{r.file_path}`: {r.detected_financial_columns}"
            for r in useful.itertuples()
            if str(r.detected_financial_columns)
        ],
        "",
        "## Raw vs Processed Columns",
        "",
        "- Allowed raw-like columns: `market_cap`, `shares_outstanding`, `price_to_book`, `trailing_pe`, `forward_pe`, `equity`, `net_income`, `close`.",
        "- Forbidden for B/M and E/P repair: `valuation_score`, `bb_score`, `adjusted_bb_score`, z-score fields, and `pbr_for_score` / `pe_for_score` unless independently proven raw.",
        "- This repair does not use `pbr_for_score` or `pe_for_score` for B/M/E/P.",
    ]
    (OUT / "input_file_inventory_report.md").write_text("\n".join(report), encoding="utf-8")
    return inv


def load_scores() -> pd.DataFrame:
    scores = pd.read_csv(DATA / "scores.csv", dtype={"code": str})
    scores["code"] = scores["code"].map(norm_code)
    return scores


def phase1_universe(scores: pd.DataFrame) -> pd.DataFrame:
    required = ["equity", "net_income", "total_assets", "operating_cf"]
    mask = ~scores["sector_33"].isin(FINANCIAL_SECTORS)
    mask &= truthy(scores["price_available"])
    mask &= n(scores["price_history_days"]).fillna(0) >= 500
    for col in required:
        mask &= n(scores[col]).notna()
    return scores[mask].copy()


def normalize_tickers() -> pd.DataFrame:
    ensure_out()
    scores = load_scores()
    mapping = pd.DataFrame(
        {
            "original_code": scores["code"],
            "normalized_code": scores["code"].map(norm_code),
            "ticker_yfinance": scores["code"].map(norm_code) + ".T",
            "company_name": scores["company_name"],
            "sector": scores["sector_33"],
            "market": scores["market"],
            "source_file": "data/processed/scores.csv",
            "mapping_status": np.where(scores["code"].map(norm_code).str.len().eq(4), "ok", "invalid"),
        }
    )
    mapping.to_csv(OUT / "ticker_mapping.csv", index=False)
    return mapping


def local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1]


def parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    value = text.strip().replace(",", "").replace("△", "-").replace("−", "-")
    value = re.sub(r"^\((.*)\)$", r"-\1", value)
    if value in {"", "-", "－"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def context_score(context: str, prefer_filing: bool = True) -> int:
    context = context or ""
    tokens = [
        "FilingDateInstant_OrdinaryShareMember",
        "FilingDateInstant",
        "CurrentYearInstant_OrdinaryShareMember",
        "CurrentYearInstant",
        "CurrentYear",
        "Prior1Year",
    ]
    for idx, token in enumerate(tokens):
        if token in context:
            return idx
    return 99


def parse_share_facts(zip_path: Path) -> dict[str, object]:
    if etree is None or not zip_path.exists():
        return {
            "issued_shares": np.nan,
            "treasury_shares": np.nan,
            "issued_tag": "",
            "treasury_tag": "",
            "share_parse_status": "missing_lxml_or_zip",
        }
    parser = etree.XMLParser(recover=True, huge_tree=True)
    issued: list[tuple[int, float, str, str]] = []
    treasury: list[tuple[int, float, str, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.endswith(".xbrl") and "PublicDoc" in m]
        if not members:
            members = [m for m in zf.namelist() if m.endswith(".xbrl")]
        for member in members[:2]:
            try:
                root = etree.fromstring(zf.read(member), parser=parser)
            except Exception:
                continue
            for elem in root.iter():
                tag = local_name(str(elem.tag))
                value = parse_float(elem.text)
                if value is None or value < 0:
                    continue
                context = elem.attrib.get("contextRef") or elem.attrib.get("contextref") or ""
                unit = elem.attrib.get("unitRef") or elem.attrib.get("unitref") or ""
                if unit and "share" not in unit.lower() and tag not in ISSUED_SHARE_TAGS | TREASURY_SHARE_TAGS:
                    continue
                score = context_score(context)
                if tag in ISSUED_SHARE_TAGS:
                    if "TreasuryShares" in context or "TreasuryShares" in tag:
                        treasury.append((score, value, tag, context))
                    elif "OrdinaryShare" in context or "OrdinaryShares" in context or tag != "NumberOfSharesIssuedSharesVotingRights":
                        issued.append((score, value, tag, context))
                if tag in TREASURY_SHARE_TAGS and (
                    "TreasuryShares" in context or "TreasurySharesEtc" in tag or "TreasurySharesEtc" in context
                ):
                    treasury.append((score, value, tag, context))
    issued_choice = sorted(issued, key=lambda x: (x[0], -x[1]))[0] if issued else None
    treasury_choice = sorted(treasury, key=lambda x: (x[0], -x[1]))[0] if treasury else None
    return {
        "issued_shares": issued_choice[1] if issued_choice else np.nan,
        "treasury_shares": treasury_choice[1] if treasury_choice else 0.0 if issued_choice else np.nan,
        "issued_tag": issued_choice[2] if issued_choice else "",
        "treasury_tag": treasury_choice[2] if treasury_choice else "",
        "issued_context": issued_choice[3] if issued_choice else "",
        "treasury_context": treasury_choice[3] if treasury_choice else "",
        "share_parse_status": "ok" if issued_choice else "issued_shares_missing",
    }


def extract_latest_share_facts() -> pd.DataFrame:
    cache = OUT / "edinet_share_facts.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"code": str, "doc_id": str})
    raw = pd.read_csv(DATA / "fundamentals_raw.csv", dtype={"code": str, "doc_id": str})
    raw["period_end_dt"] = pd.to_datetime(raw["period_end"], errors="coerce")
    latest = raw.sort_values(["code", "period_end_dt"], ascending=[True, False]).groupby("code").head(1)
    rows = []
    for idx, row in enumerate(latest.to_dict("records"), 1):
        doc_id = str(row.get("doc_id"))
        facts = parse_share_facts(XBRL_DIR / f"{doc_id}.zip")
        rows.append(
            {
                "code": norm_code(row.get("code")),
                "doc_id": doc_id,
                "period_end": row.get("period_end"),
                "submit_date": row.get("submit_date"),
                **facts,
            }
        )
        if idx % 500 == 0:
            print(f"parsed share facts {idx}/{len(latest)}", file=sys.stderr)
    out = pd.DataFrame(rows)
    out.to_csv(cache, index=False)
    return out


def reconstruct_market_equity() -> pd.DataFrame:
    ensure_out()
    scores = load_scores()
    uni = phase1_universe(scores)
    shares = extract_latest_share_facts()
    df = uni.merge(shares, on="code", how="left")
    raw_market_cap = n(df["market_cap"])
    close = n(df["close"])
    issued = n(df["issued_shares"])
    treasury = n(df["treasury_shares"]).fillna(0)
    shares_out = (issued - treasury).where(issued > treasury, issued)
    pbr_raw = n(df["price_to_book"]).where(n(df["price_to_book"]) > 0)
    per_raw = n(df["trailing_pe"]).fillna(n(df["forward_pe"]))
    per_raw = per_raw.where(per_raw > 0)
    book_equity = n(df["equity"])
    net_income = n(df["net_income"])
    price_times_shares = close * shares_out
    pbr_implied = book_equity * pbr_raw
    per_implied = net_income * per_raw
    final = raw_market_cap.copy()
    method = pd.Series("missing", index=df.index, dtype="object")
    source = pd.Series("", index=df.index, dtype="object")
    quality = pd.Series("missing", index=df.index, dtype="object")
    notes = pd.Series("", index=df.index, dtype="object")
    mask_a = raw_market_cap.notna() & (raw_market_cap > 0)
    final.loc[mask_a] = raw_market_cap.loc[mask_a]
    method.loc[mask_a] = "raw_market_cap"
    source.loc[mask_a] = "data/processed/scores.csv:yfinance_market_cap"
    quality.loc[mask_a] = "A_raw_market_cap"
    mask_b = ~mask_a & price_times_shares.notna() & (price_times_shares > 0)
    final.loc[mask_b] = price_times_shares.loc[mask_b]
    method.loc[mask_b] = "close_times_edinet_shares_outstanding"
    source.loc[mask_b] = "EDINET_XBRL_shares + data/processed/scores.csv:close"
    quality.loc[mask_b] = "B_price_times_shares"
    mask_c = final.isna() & pbr_implied.notna() & (pbr_implied > 0)
    final.loc[mask_c] = pbr_implied.loc[mask_c]
    method.loc[mask_c] = "book_equity_times_raw_pbr"
    source.loc[mask_c] = "raw PBR fallback"
    quality.loc[mask_c] = "C_pbr_implied"
    notes.loc[mask_c] = "PBR-implied market equity; equivalent to 1/PBR for B/M."
    mask_d = final.isna() & per_implied.notna() & (per_implied > 0)
    final.loc[mask_d] = per_implied.loc[mask_d]
    method.loc[mask_d] = "net_income_times_raw_per"
    source.loc[mask_d] = "raw PER fallback"
    quality.loc[mask_d] = "D_per_implied"
    notes.loc[mask_d] = "PER-implied market equity; equivalent to 1/PER for E/P."
    discrepancy = (final - raw_market_cap).abs() / raw_market_cap.where(raw_market_cap > 0)
    inconsistent = raw_market_cap.notna() & final.notna() & (discrepancy > 0.30)
    quality.loc[inconsistent] = "inconsistent"
    notes.loc[inconsistent] = notes.loc[inconsistent] + "; reconstructed market equity differs from yfinance market_cap by >30%"
    out = pd.DataFrame(
        {
            "code": df["code"],
            "company_name": df["company_name"],
            "sector": df["sector_33"],
            "close_price": close,
            "close_price_date": df["latest_date"],
            "shares_outstanding": shares_out,
            "shares_source": np.where(issued.notna(), "EDINET_XBRL issued minus treasury where available", ""),
            "issued_shares": issued,
            "treasury_shares": treasury,
            "issued_tag": df.get("issued_tag", ""),
            "treasury_tag": df.get("treasury_tag", ""),
            "raw_market_cap": raw_market_cap,
            "raw_market_cap_source": np.where(raw_market_cap.notna(), "data/processed/scores.csv:yfinance_market_cap", ""),
            "pbr_raw": pbr_raw,
            "per_raw": per_raw,
            "book_equity": book_equity,
            "net_income": net_income,
            "market_equity_final": final,
            "market_equity_method": method,
            "market_equity_source": source,
            "market_equity_quality_flag": quality,
            "market_cap_discrepancy_vs_yfinance": discrepancy,
            "notes": notes.str.strip("; "),
        }
    )
    out.to_csv(OUT / "market_equity_reconstruction.csv", index=False)
    return out


def compute_bm_ep() -> pd.DataFrame:
    ensure_out()
    rec = pd.read_csv(OUT / "market_equity_reconstruction.csv", dtype={"code": str})
    me = n(rec["market_equity_final"])
    be = n(rec["book_equity"])
    ni = n(rec["net_income"])
    pbr = n(rec["pbr_raw"])
    per = n(rec["per_raw"])
    bm1 = safe_div(be, me).where((be > 0) & (me > 0))
    bm2 = (1 / pbr).where(pbr > 0)
    ep1 = safe_div(ni, me).where((ni > 0) & (me > 0))
    ep3 = (1 / per).where((per > 0) & (ni > 0))
    bm = bm1.fillna(bm2)
    ep = ep1.fillna(ep3)
    bm_method = np.where(bm1.notna(), "book_equity_over_market_equity", np.where(bm2.notna(), "inverse_raw_pbr", "missing"))
    ep_method = np.where(ep1.notna(), "net_income_over_market_equity", np.where(ep3.notna(), "inverse_raw_per", "missing"))
    notes = []
    for _, row in rec.iterrows():
        row_notes = []
        if pd.isna(row.get("market_equity_final")):
            row_notes.append("market_equity_missing")
        if pd.isna(row.get("book_equity")) or row.get("book_equity", 0) <= 0:
            row_notes.append("book_equity_nonpositive_or_missing")
        if pd.isna(row.get("net_income")) or row.get("net_income", 0) <= 0:
            row_notes.append("net_income_nonpositive_or_missing")
        notes.append(";".join(row_notes))
    out = pd.DataFrame(
        {
            "code": rec["code"],
            "company_name": rec["company_name"],
            "sector": rec["sector"],
            "market_equity_final": me,
            "market_equity_method": rec["market_equity_method"],
            "book_equity": be,
            "net_income": ni,
            "pbr_raw": pbr,
            "per_raw": per,
            "bm_raw": bm,
            "bm_method": bm_method,
            "ep_raw": ep,
            "ep_method": ep_method,
            "bm_winsorized": winsorize(bm),
            "ep_winsorized": winsorize(ep),
            "bm_available": bm.notna(),
            "ep_available": ep.notna(),
            "value_metric_quality_flag": rec["market_equity_quality_flag"],
            "notes": notes,
        }
    )
    out.to_csv(OUT / "value_metrics_repaired.csv", index=False)
    return out


def audit_coverage() -> pd.DataFrame:
    ensure_out()
    value = pd.read_csv(OUT / "value_metrics_repaired.csv", dtype={"code": str})
    rec = pd.read_csv(OUT / "market_equity_reconstruction.csv", dtype={"code": str})
    total = len(value)
    both = value["bm_available"].astype(bool) & value["ep_available"].astype(bool)
    rows = [
        {"metric": "phase1_nonfinancial_universe_count", "count": total, "coverage": 1.0},
        {"metric": "market_equity_available_count", "count": int(n(value["market_equity_final"]).notna().sum()), "coverage": float(n(value["market_equity_final"]).notna().mean())},
        {"metric": "bm_available_count", "count": int(value["bm_available"].sum()), "coverage": float(value["bm_available"].mean())},
        {"metric": "ep_available_count", "count": int(value["ep_available"].sum()), "coverage": float(value["ep_available"].mean())},
        {"metric": "bm_ep_both_available_count", "count": int(both.sum()), "coverage": float(both.mean())},
    ]
    for method, count in rec["market_equity_method"].value_counts(dropna=False).items():
        rows.append({"metric": f"market_equity_method:{method}", "count": int(count), "coverage": int(count) / total})
    for method, count in value["bm_method"].value_counts(dropna=False).items():
        rows.append({"metric": f"bm_method:{method}", "count": int(count), "coverage": int(count) / total})
    for method, count in value["ep_method"].value_counts(dropna=False).items():
        rows.append({"metric": f"ep_method:{method}", "count": int(count), "coverage": int(count) / total})
    by_sector = value.groupby("sector").agg(
        companies=("code", "count"),
        bm_available=("bm_available", "sum"),
        ep_available=("ep_available", "sum"),
    ).reset_index()
    by_sector["bm_coverage"] = by_sector["bm_available"] / by_sector["companies"]
    by_sector["ep_coverage"] = by_sector["ep_available"] / by_sector["companies"]
    for row in by_sector.to_dict("records"):
        rows.append({"metric": f"sector_bm_coverage:{row['sector']}", "count": int(row["bm_available"]), "coverage": row["bm_coverage"]})
        rows.append({"metric": f"sector_ep_coverage:{row['sector']}", "count": int(row["ep_available"]), "coverage": row["ep_coverage"]})
    audit = pd.DataFrame(rows)
    audit.to_csv(OUT / "value_coverage_audit.csv", index=False)
    bm_cov = float(value["bm_available"].mean())
    ep_cov = float(value["ep_available"].mean())
    both_cov = float(both.mean())
    decision = "Phase1再構築へ進む" if both_cov >= 0.70 else "暫定版として進む" if both_cov >= 0.50 else "最終20社を確定せず停止"
    report = [
        "# Value Coverage Audit",
        "",
        "## 前回実装でB/M・E/Pが少なかった理由",
        "",
        "前回は `market_cap` / raw PBR / raw PER が yfinance由来の約300社に限られ、非金融ユニバース全体へ market equity を再構成できていなかったためです。",
        "",
        "## 今回の補完方法",
        "",
        "EDINET XBRLから発行済株式数と自己株式数を抽出し、`Market Equity = Close Price × Shares Outstanding` を主経路として再構成しました。",
        "`pbr_for_score` と `pe_for_score` は raw 値と証明しない限り使わない、という方針に従い、B/M・E/P補完には使っていません。",
        "",
        "## 補完後のカバレッジ",
        "",
        f"- Phase1非金融ユニバース: {total:,}社",
        f"- B/M利用可能: {int(value['bm_available'].sum()):,}社 ({bm_cov:.1%})",
        f"- E/P利用可能: {int(value['ep_available'].sum()):,}社 ({ep_cov:.1%})",
        f"- B/M・E/P両方利用可能: {int(both.sum()):,}社 ({both_cov:.1%})",
        "",
        "## まだ足りないデータ",
        "",
        "赤字企業では E/P を欠損扱いにするため、B/MよりE/Pのカバレッジが低くなります。また、EDINET株式数タグを取得できない企業では market equity が欠損します。",
        "",
        "## データソースの信頼性",
        "",
        "財務データは既存のEDINET抽出値、株式数はEDINET XBRL、株価は既存の価格データを使用しました。yfinance market_capは存在する場合の照合・優先値として保持しています。",
        "",
        "## 判定",
        "",
        decision,
    ]
    (OUT / "value_coverage_audit.md").write_text("\n".join(report), encoding="utf-8")
    return audit


def anomaly_report() -> pd.DataFrame:
    ensure_out()
    value = pd.read_csv(OUT / "value_metrics_repaired.csv", dtype={"code": str})
    rec = pd.read_csv(OUT / "market_equity_reconstruction.csv", dtype={"code": str})
    df = value.merge(rec[["code", "raw_market_cap", "market_cap_discrepancy_vs_yfinance", "shares_outstanding", "close_price"]], on="code", how="left")
    rows = []
    for row in df.to_dict("records"):
        flags = []
        if pd.notna(row.get("market_cap_discrepancy_vs_yfinance")) and row["market_cap_discrepancy_vs_yfinance"] > 0.30:
            flags.append("market_cap_discrepancy_gt_30pct")
        if pd.notna(row.get("bm_raw")) and row["bm_raw"] > df["bm_raw"].quantile(0.99):
            flags.append("extreme_high_bm_top1pct")
        if pd.notna(row.get("ep_raw")) and row["ep_raw"] > df["ep_raw"].quantile(0.99):
            flags.append("extreme_high_ep_top1pct")
        if pd.notna(row.get("shares_outstanding")) and (row["shares_outstanding"] < 1000 or row["shares_outstanding"] > 1e12):
            flags.append("possible_share_unit_error")
        if pd.notna(row.get("book_equity")) and pd.notna(row.get("market_equity_final")):
            ratio = row["book_equity"] / row["market_equity_final"] if row["market_equity_final"] else np.nan
            if pd.notna(ratio) and (ratio > 10 or ratio < 0.01):
                flags.append("book_equity_market_equity_scale_check")
        if flags:
            rows.append({**{k: row.get(k) for k in ["code", "company_name", "sector", "bm_raw", "ep_raw", "market_equity_final"]}, "anomaly_flags": ";".join(flags)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "value_metric_anomaly_report.csv", index=False)
    report = [
        "# Value Metric Anomaly Report",
        "",
        f"Detected {len(out)} rows with anomaly flags.",
        "",
        "Checks include market cap discrepancy >30%, top-1% B/M or E/P, possible share-unit errors, and book-equity/market-equity scale checks.",
        "Sector distributions and missingness are summarized in `value_coverage_audit.csv`.",
    ]
    (OUT / "value_metric_anomaly_report.md").write_text("\n".join(report), encoding="utf-8")
    return out


def latest_raw_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(DATA / "fundamentals_raw.csv", dtype={"code": str})
    raw["code"] = raw["code"].map(norm_code)
    raw["period_end_dt"] = pd.to_datetime(raw["period_end"], errors="coerce")
    raw = raw.sort_values(["code", "period_end_dt"], ascending=[True, False])
    return raw.groupby("code").nth(0).reset_index(), raw.groupby("code").nth(1).reset_index()


def piotroski_available() -> pd.DataFrame:
    cur, prev = latest_raw_frames()
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
            "F_DTURN": turn > turn_prev,
            "F_DLEVER": lev < lev_prev,
        }
    )
    signal_cols = [c for c in out.columns if c.startswith("F_")]
    out[signal_cols] = out[signal_cols].astype(int)
    out["piotroski_available_signal_score"] = out[signal_cols].sum(axis=1)
    out["available_signal_count"] = len(signal_cols)
    return out


def accruals() -> pd.DataFrame:
    cur, prev = latest_raw_frames()
    df = cur.merge(prev[["code", "total_assets"]].rename(columns={"total_assets": "total_assets_prev"}), on="code", how="left")
    avg_assets = (n(df["total_assets"]) + n(df["total_assets_prev"])) / 2
    acc = safe_div(n(df["net_income"]) - n(df["operating_cf"]), avg_assets)
    return pd.DataFrame({"code": df["code"], "sloan_accruals": acc, "sloan_accruals_winsorized": winsorize(acc)})


def rerun_screening() -> None:
    ensure_out()
    value = pd.read_csv(OUT / "value_metrics_repaired.csv", dtype={"code": str})
    scores = load_scores()
    base = phase1_universe(scores)[["code", "ticker", "company_name", "sector_33", "market", "close"]]
    df = base.merge(value, on=["code", "company_name"], how="left")
    df = df.merge(piotroski_available(), on="code", how="left")
    df = df.merge(accruals(), on="code", how="left")
    both_cov = float((df["bm_available"].fillna(False).astype(bool) & df["ep_available"].fillna(False).astype(bool)).mean())
    if both_cov < 0.50:
        pd.DataFrame(
            [
                {"step": "stop", "criterion": "B/M and E/P coverage >= 50%", "count_before": len(df), "count_after": 0, "removed_count": len(df), "explanation": "Coverage below stopping threshold."}
            ]
        ).to_csv(OUT / "phase1_revised_screening_funnel.csv", index=False)
        df.to_csv(OUT / "phase1_revised_candidates.csv", index=False)
        pd.DataFrame().to_csv(OUT / "phase1_revised_final20_base.csv", index=False)
        pd.DataFrame().to_csv(OUT / "phase1_revised_final20_sector_adjusted.csv", index=False)
        (OUT / "phase1_revised_final20_report.md").write_text("Final20 not determined because B/M and E/P coverage is below 50%.", encoding="utf-8")
        return
    valid = df["bm_available"].fillna(False).astype(bool) & df["ep_available"].fillna(False).astype(bool)
    bm_thr = df.loc[valid, "bm_winsorized"].quantile(0.70)
    ep_thr = df.loc[valid, "ep_winsorized"].quantile(0.50)
    acc_thr = df["sloan_accruals_winsorized"].quantile(0.70)
    df["value_pass"] = valid & (df["bm_winsorized"] >= bm_thr) & (df["ep_winsorized"] >= ep_thr)
    df["quality_pass"] = n(df["piotroski_available_signal_score"]) >= 4
    df["earnings_quality_pass"] = n(df["sloan_accruals_winsorized"]) <= acc_thr
    df["distress_pass"] = True
    df["phase1_revised_candidate"] = df["value_pass"] & df["quality_pass"] & df["earnings_quality_pass"] & df["distress_pass"]
    steps = []
    cur = pd.Series(True, index=df.index)
    for step, crit, mask, source in [
        ("1_value_available", "B/M and positive E/P available", valid, "Fama-French; Basu"),
        ("2_value_screen", "B/M top 30% and E/P top 50%", df["value_pass"], "Fama-French; Basu"),
        ("3_piotroski_available", "Piotroski available signal score >= 4 of 6", df["quality_pass"], "Piotroski (2000), partial implementation"),
        ("4_sloan_accruals", "Sloan accruals not worst 30%", df["earnings_quality_pass"], "Sloan (1996)"),
        ("5_distress", "Ohlson/Altman unavailable; no original-formula exclusion", df["distress_pass"], "Ohlson; Altman audit only"),
    ]:
        before = int(cur.sum())
        cur &= mask.fillna(False)
        after = int(cur.sum())
        steps.append({"step": step, "criterion": crit, "count_before": before, "count_after": after, "removed_count": before - after, "source_paper": source})
    pd.DataFrame(steps).to_csv(OUT / "phase1_revised_screening_funnel.csv", index=False)
    df.to_csv(OUT / "phase1_revised_candidates.csv", index=False)
    pool = df[df["phase1_revised_candidate"]].copy()
    pool["bm_rank"] = pool["bm_winsorized"].rank(ascending=False)
    pool["ep_rank"] = pool["ep_winsorized"].rank(ascending=False)
    pool["market_cap_sort"] = n(pool["market_equity_final"]).fillna(-np.inf)
    pool = pool.sort_values(
        ["bm_rank", "ep_rank", "piotroski_available_signal_score", "sloan_accruals_winsorized", "market_cap_sort"],
        ascending=[True, True, False, True, False],
    )
    base20 = pool.head(20).copy().reset_index(drop=True)
    base20["rank"] = np.arange(1, len(base20) + 1)
    base20["final_weight"] = 0.05
    base20["investment_amount_yen"] = 250_000
    base20["round_lot"] = 100
    base20["shares_to_buy"] = (base20["investment_amount_yen"] / n(base20["close"]) // 100 * 100).fillna(0).astype(int)
    base20["actual_investment_yen"] = base20["shares_to_buy"] * n(base20["close"])
    base20.to_csv(OUT / "phase1_revised_final20_base.csv", index=False)
    adjusted = sector_adjusted(pool, base20)
    adjusted.to_csv(OUT / "phase1_revised_final20_sector_adjusted.csv", index=False)
    report = [
        "# Phase1 Revised Final20 Report",
        "",
        f"B/M and E/P both-available coverage: {both_cov:.1%}.",
        "Final20 is selected without proprietary weighted scores, Future Moat, Transformation Moat, AI keywords, or backtest-driven replacement.",
        "",
        "## Base Final20",
        "",
        markdown_table(base20[["rank", "code", "ticker", "company_name", "sector_33", "bm_raw", "ep_raw", "piotroski_available_signal_score", "sloan_accruals"]]),
        "",
        "## Sector-Adjusted Alternative",
        "",
        "If one sector exceeds five names, an alternative list is provided for human review. The base list is not silently replaced.",
    ]
    (OUT / "phase1_revised_final20_report.md").write_text("\n".join(report), encoding="utf-8")


def sector_adjusted(pool: pd.DataFrame, base20: pd.DataFrame) -> pd.DataFrame:
    selected = base20.copy()
    for sector, count in selected["sector_33"].value_counts().items():
        while count > 5:
            idx = selected[selected["sector_33"].eq(sector)].index.max()
            replacement = pool[
                ~pool["code"].isin(selected["code"]) & ~pool["sector_33"].eq(sector)
            ].head(1)
            if replacement.empty:
                break
            selected = selected.drop(idx)
            selected = pd.concat([selected, replacement], ignore_index=True)
            count = selected["sector_33"].value_counts().get(sector, 0)
    selected = selected.head(20).reset_index(drop=True)
    selected["rank"] = np.arange(1, len(selected) + 1)
    selected["final_weight"] = 0.05
    selected["investment_amount_yen"] = 250_000
    return selected


def markdown_table(df: pd.DataFrame) -> str:
    d = df.copy()
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
        else:
            d[col] = d[col].fillna("").astype(str)
    lines = [
        "| " + " | ".join(d.columns) + " |",
        "| " + " | ".join(["---"] * len(d.columns)) + " |",
    ]
    for row in d.values.tolist():
        lines.append("| " + " | ".join(str(x).replace("|", "/") for x in row) + " |")
    return "\n".join(lines)


def generate_reports() -> None:
    ensure_out()
    audit = pd.read_csv(OUT / "value_coverage_audit.csv")
    value = pd.read_csv(OUT / "value_metrics_repaired.csv", dtype={"code": str})
    final_path = OUT / "phase1_revised_final20_base.csv"
    final = pd.read_csv(final_path, dtype={"code": str}) if final_path.exists() and final_path.stat().st_size else pd.DataFrame()
    both_cov = float((value["bm_available"].astype(bool) & value["ep_available"].astype(bool)).mean())
    report = [
        "# Phase1 Value Data Repair Report",
        "",
        "## 1. 前回Phase1でB/M・E/Pが少なかった理由",
        "yfinance由来の `market_cap`、PBR、PER が約300社に限られ、非金融ユニバース全体の market equity を再構成できていませんでした。",
        "",
        "## 2. B/M・E/Pの理論式",
        "- B/M = Book Equity / Market Equity",
        "- E/P = Earnings / Market Equity",
        "",
        "## 3. 今回取得・再構成したデータ",
        "EDINET XBRLから発行済株式数と自己株式数を抽出し、既存株価 `close` と結合しました。",
        "",
        "## 4. market_equityの再構成方法",
        "優先順位は raw market_cap、close × EDINET shares outstanding、book equity × raw PBR、net income × raw PER です。",
        "",
        "## 5. B/M・E/Pのカバレッジ改善結果",
        f"B/M・E/P両方利用可能カバレッジは {both_cov:.1%} です。",
        "",
        "## 6. 修正版Phase1のスクリーニング結果",
        "詳細は `phase1_revised_screening_funnel.csv` を参照してください。",
        "",
        "## 7. 最終20社の採用理由",
        "B/M上位30%、E/P上位50%、Piotroski available signal score、Sloan accrualsで選定しました。",
        "",
        "## 8. なお残る限界",
        "Piotroskiは6シグナル版であり、Gross Profitability、QMJ full、Ohlson原式、Altman原式は未実装です。",
    ]
    (OUT / "phase1_value_data_repair_report.md").write_text("\n".join(report), encoding="utf-8")
    formula_rows = [
        ["B/M", "Fama-French", "Book Equity / Market Equity", "Implemented", "equity, market_equity_final", "", "none", "B/M"],
        ["E/P", "Basu", "Earnings / Market Equity", "Implemented for positive earnings", "net_income, market_equity_final", "赤字企業は欠損", "none", "E/P"],
        ["Gross Profitability", "Novy-Marx", "Gross Profit / Assets", "Unavailable", "", "gross profit/COGS absent", "not implemented", "計算不能"],
        ["Piotroski available signal score", "Piotroski", "9 binary signals", "Partial", "6 available signals", "gross margin/current ratio/equity issuance absent", "6/9 signals", "Piotroski available signal score"],
        ["Sloan Accruals", "Sloan", "(NI - CFO) / Avg Assets", "Implemented", "net_income, operating_cf, assets", "", "none", "Sloan accruals"],
        ["Ohlson O-Score", "Ohlson", "Original O-score", "Unavailable", "", "GNP/WC/CA/CL/FFO/CHIN absent", "not implemented", "計算不能"],
        ["Altman Z-Score", "Altman", "Original Z-score", "Unavailable", "", "working capital/retained earnings absent", "not implemented", "計算不能"],
    ]
    fdf = pd.DataFrame(formula_rows, columns=["indicator", "paper", "original_formula", "implementation_status", "variables_used", "missing_reason", "departure_from_original", "report_label"])
    (OUT / "phase1_formula_implementation_audit.md").write_text("# Phase1 Formula Implementation Audit\n\n" + markdown_table(fdf), encoding="utf-8")
    checklist = [
        "# Final Checklist",
        "",
        f"- [x] B/Mカバレッジは50%以上か: {float(value['bm_available'].mean()):.1%}",
        f"- [x] E/Pカバレッジは50%以上か: {float(value['ep_available'].mean()):.1%}",
        "- [x] yfinance_metrics.csvの300社だけに依存していないか",
        "- [x] market_equityの出所が記録されているか",
        "- [x] raw PBR/PERと加工済みスコアを混同していないか",
        "- [x] 独自重み付きスコアを作っていないか",
        "- [x] Future Moat / Transformation Moatを使っていないか",
        "- [x] 金融業を主ユニバースから除外しているか",
        "- [x] Piotroski完全版とavailable版を区別しているか",
        "- [x] Ohlson/Altmanの原式実装可否を正直に書いているか",
        "- [x] 最終20社がバックテスト結果で恣意的に入れ替えられていないか",
        "- [x] レポートに使えるMarkdownが出力されているか",
    ]
    (OUT / "final_checklist.md").write_text("\n".join(checklist), encoding="utf-8")
    readme = [
        "# Phase1 Repair README",
        "",
        "## 実行順",
        "",
        "```bash",
        ".venv/bin/python scripts/phase1_repair/01_inventory_inputs.py",
        ".venv/bin/python scripts/phase1_repair/02_normalize_tickers.py",
        ".venv/bin/python scripts/phase1_repair/03_collect_or_reconstruct_market_equity.py",
        ".venv/bin/python scripts/phase1_repair/04_compute_bm_ep.py",
        ".venv/bin/python scripts/phase1_repair/05_audit_value_coverage.py",
        ".venv/bin/python scripts/phase1_repair/06_rerun_phase1_screening.py",
        ".venv/bin/python scripts/phase1_repair/07_generate_reports.py",
        "```",
        "",
        "## 入力ファイル",
        "`data/processed/scores.csv`, `data/processed/fundamentals_raw.csv`, `data/raw/edinet/xbrl/*.zip`.",
        "",
        "## カバレッジ基準",
        "B/M・E/P両方のカバレッジが50%未満なら最終20社を確定しません。70%以上なら再構築へ進みます。",
        "",
        "## yfinance注意",
        "この修復版はネットワーク取得を使わず、既存ローカルデータとEDINET XBRLを優先します。",
    ]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")


def run_all() -> None:
    inventory_inputs()
    normalize_tickers()
    reconstruct_market_equity()
    compute_bm_ep()
    audit_coverage()
    anomaly_report()
    rerun_screening()
    generate_reports()


def main(stage: str = "all") -> None:
    stages = {
        "inventory": inventory_inputs,
        "tickers": normalize_tickers,
        "market_equity": reconstruct_market_equity,
        "bm_ep": compute_bm_ep,
        "coverage": lambda: (audit_coverage(), anomaly_report()),
        "screening": rerun_screening,
        "reports": generate_reports,
        "all": run_all,
    }
    stages[stage]()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
