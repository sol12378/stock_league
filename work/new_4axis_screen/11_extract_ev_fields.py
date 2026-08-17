"""Part 11: 既存式を使うために足りない財務項目をXBRLから追加抽出する。

背景:
  既存の名前のついた式を使いたいが、いまのパネルには材料が足りない。
    現預金・有利子負債 → 企業価値(EV)が作れない
                       → Greenblatt マジックフォーミュラの益回り(EBIT/EV)が使えない
    利益剰余金・有形固定資産 → Altman Z-Score・マジックフォーミュラのROCが作れない
    研究開発費・設備投資 → Chan-Lakonishok-Sougiannis(2001)・Mohanram G-Score(2005)が作れない

  なお `src/data/parse_edinet_xbrl.py` は研究開発費を `ResearchAndDevelopmentExpenses` で
  探しており、これでは EDINET の実タグ `ResearchAndDevelopmentExpensesSGA` に当たらない。
  「研究開発費は3,649社中2社しかない」という既存監査の記述は、データの不在ではなく
  **タグ名の取り違えによる抽出漏れ**である。本スクリプトはそれを是正する。

タグ名は実ファイル25社をサンプリングして実在を確認したものだけを使う。

出力: work/new_4axis_screen/out/ev_fields.csv
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
XBRL_DIR = ROOT / "data/raw/edinet/xbrl"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"

# 単一値を取る項目(タグ優先順)
SINGLE: dict[str, list[str]] = {
    "cash": ["CashAndCashEquivalents", "CashAndDeposits",
             "CashAndCashEquivalentsSummaryOfBusinessResults"],
    "retained_earnings": ["RetainedEarnings", "RetainedEarningsBroughtForward"],
    "ppe": ["PropertyPlantAndEquipment"],
    "rd_expense": ["ResearchAndDevelopmentExpensesSGA",
                   "ResearchAndDevelopmentExpensesResearchAndDevelopmentActivities",
                   "ResearchAndDevelopmentExpenses"],
    "capex": ["CapitalExpendituresOverviewOfCapitalExpendituresEtc",
              "PurchaseOfPropertyPlantAndEquipmentInvCF"],
    "depreciation": ["DepreciationAndAmortizationOpeCF", "DepreciationSGA"],
}
# タグごとに1つ取って合算する項目(有利子負債)
SUMMED: dict[str, list[str]] = {
    "short_term_debt": ["ShortTermLoansPayable", "CurrentPortionOfLongTermLoansPayable",
                        "CommercialPapersLiabilities"],
    "long_term_debt": ["LongTermLoansPayable", "BondsPayable"],
}

CTX = re.compile(rb'contextRef="([^"]+)"')


def _pat(tag: str) -> re.Pattern[bytes]:
    t = tag.encode()
    return re.compile(rb"<[\w\-]+:" + t + rb"\s([^>]*?)>([^<]*)</[\w\-]+:" + t + rb">")


PATS_SINGLE = {k: [(t, _pat(t)) for t in v] for k, v in SINGLE.items()}
PATS_SUMMED = {k: [(t, _pat(t)) for t in v] for k, v in SUMMED.items()}


def _best(blob: bytes, pat: re.Pattern[bytes]) -> float | None:
    """当期・連結を優先して1タグから1値。"""
    best: tuple[int, float] | None = None
    for m in pat.finditer(blob):
        attrs, raw = m.group(1), m.group(2)
        ctx_m = CTX.search(attrs)
        ctx = ctx_m.group(1).decode(errors="ignore") if ctx_m else ""
        if "Prior" in ctx:
            continue
        rank = (0 if "CurrentYear" in ctx else 1) + (2 if "NonConsolidated" in ctx else 0)
        try:
            val = float(raw.decode().strip().replace(",", "").replace("△", "-"))
        except (ValueError, UnicodeDecodeError):
            continue
        if best is None or rank < best[0]:
            best = (rank, val)
    return None if best is None else best[1]


def main() -> None:
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False,
                        usecols=["code", "doc_id", "fiscal_year"])
    import sys
    all_years = "--all-years" in sys.argv
    if all_years:
        latest = panel.copy()
        print(f"対象 {len(latest)} 件(全提出分)")
    else:
        latest = panel.sort_values("fiscal_year").groupby("code", as_index=False).last()
        print(f"対象 {len(latest)} 社(最新提出分のみ)")

    rows = []
    for r in tqdm(latest.itertuples(index=False), total=len(latest), desc="xbrl"):
        rec: dict[str, object] = {"code": r.code, "fiscal_year": r.fiscal_year}
        path = XBRL_DIR / f"{r.doc_id}.zip"
        if not path.exists():
            rows.append(rec | {"status": "zip_missing"})
            continue
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
                blob = z.read(names[0])
        except Exception as exc:
            rows.append(rec | {"status": f"error:{type(exc).__name__}"})
            continue
        for key, pats in PATS_SINGLE.items():
            val = None
            for _tag, pat in pats:
                val = _best(blob, pat)
                if val is not None:
                    break
            rec[key] = val
        for key, pats in PATS_SUMMED.items():
            vals = [v for _t, p in pats if (v := _best(blob, p)) is not None]
            rec[key] = float(sum(vals)) if vals else None
        rows.append(rec | {"status": "ok"})

    out = pd.DataFrame(rows)
    out["interest_bearing_debt"] = out[["short_term_debt", "long_term_debt"]].sum(
        axis=1, min_count=1)
    out.to_csv(OUT / ("ev_fields_all_years.csv" if all_years else "ev_fields.csv"),
               index=False)
    print()
    for c in list(SINGLE) + list(SUMMED) + ["interest_bearing_debt"]:
        print(f"{c:22s} 取得 {int(out[c].notna().sum()):5d} / {len(out)} "
              f"({out[c].notna().mean()*100:5.1f}%)")


if __name__ == "__main__":
    main()
