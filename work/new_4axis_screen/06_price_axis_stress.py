"""Part 6: Price軸の効きは株数エラー(分割ズレ)の産物ではないか、を潰す。

Part 3 で Price軸の rank IC は 0.21〜0.43 と全コホートで最大だった。
Part 5 で「株数が古いと時価総額が過小 → 見かけ上いちばん割安 → 上位に張り付く」ことが分かった。
その両者が同じ現象なら、Price軸の効きは見せかけになる。以下で切り分ける。

  A. 実装不能に安い行(PER<3 or PBR<0.3)を除いても IC は残るか
  B. E/P・B/M を1-99%でウィンザライズしても残るか
  C. 上下5%を落とした中央90%だけでも残るか
  D. 上位十分位から順に外していったとき IC がどこで消えるか
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"
LIQUIDITY_YEN = 20_000_000
COHORTS = {"FY2024_252d": ("future_return_252d", 2024),
           "FY2025_126d": ("future_return_126d", 2025),
           "FY2023_252d": ("future_return_252d", 2023)}


def pr(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").mul(100.0)


def ic(x: pd.Series, y: pd.Series) -> float:
    return round(float(x.corr(y, method="spearman")), 4)


def main() -> None:
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False)
    report: dict[str, object] = {}

    for key, (retcol, year) in COHORTS.items():
        d = panel[panel["fiscal_year"] == year].copy()
        d = d[
            d["price_join_success"].fillna(False)
            & ~d["financial_exclusion_flag"].fillna(False)
            & ~d["distress_hard_exclusion_flag"].fillna(False)
            & ~d["negative_equity_flag"].fillna(False)
            & (d["decision_adv60"].fillna(0) >= LIQUIDITY_YEN)
            & d[retcol].notna()
            & (d["market_equity_pti"] > 0)
        ].copy()

        d["per"] = d["market_equity_pti"] / d["net_income"].where(d["net_income"] > 0)
        d["pbr"] = d["market_equity_pti"] / d["equity"].where(d["equity"] > 0)
        d["implausible"] = ((d["per"] < 3.0) | (d["pbr"] < 0.30)).fillna(False)
        ret = d[retcol]

        base = pd.DataFrame({c: pr(d[c]) for c in ["earnings_to_price", "book_to_market"]}).mean(axis=1)
        r: dict[str, object] = {
            "n": int(len(d)),
            "implausible_n": int(d["implausible"].sum()),
            "implausible_pct": round(float(d["implausible"].mean() * 100), 1),
            "A_baseline_ic": ic(base, ret),
        }
        # 実装不能に安い行を除外した後の残存企業だけで順位を作り直す
        keep = d[~d["implausible"]].copy()
        base_keep = pd.DataFrame(
            {c: pr(keep[c]) for c in ["earnings_to_price", "book_to_market"]}).mean(axis=1)
        r["A_excl_implausible_ic"] = ic(base_keep, keep[retcol])
        r["A_excl_implausible_n"] = int(len(keep))
        r["A_implausible_group_mean_return"] = round(float(d.loc[d["implausible"], retcol].mean()), 4)
        r["A_plausible_group_mean_return"] = round(float(d.loc[~d["implausible"], retcol].mean()), 4)

        # B. ウィンザライズ
        w = d.copy()
        for c in ["earnings_to_price", "book_to_market"]:
            lo, hi = w[c].quantile([0.01, 0.99])
            w[c] = w[c].clip(lo, hi)
        r["B_winsorized_ic"] = ic(
            pd.DataFrame({c: pr(w[c]) for c in ["earnings_to_price", "book_to_market"]}).mean(axis=1),
            w[retcol],
        )

        # C. 中央90%(Price順位点の上下5%を落とす)
        p = base
        mid = d[(p >= p.quantile(0.05)) & (p <= p.quantile(0.95))].copy()
        mid_p = pd.DataFrame(
            {c: pr(mid[c]) for c in ["earnings_to_price", "book_to_market"]}).mean(axis=1)
        r["C_middle90pct_ic"] = ic(mid_p, mid[retcol])
        r["C_middle90pct_n"] = int(len(mid))

        # D. 上位十分位から順に落としたときの IC 推移
        trims = {}
        for drop in [0, 10, 20, 30, 40, 50]:
            thr = np.percentile(base, 100 - drop) if drop > 0 else np.inf
            sub = d[base < thr] if drop > 0 else d
            sp = pd.DataFrame(
                {c: pr(sub[c]) for c in ["earnings_to_price", "book_to_market"]}).mean(axis=1)
            trims[f"drop_top_{drop}pct"] = {"n": int(len(sub)), "ic": ic(sp, sub[retcol])}
        r["D_trim_from_top"] = trims

        # 参考: 十分位ごとの平均リターン(単調性の確認)
        q = pd.qcut(base.rank(method="first"), 10, labels=False)
        r["decile_mean_returns"] = [round(float(ret[q == i].mean()), 4) for i in range(10)]

        report[key] = r
        print(f"[{key}] baseline={r['A_baseline_ic']} excl={r['A_excl_implausible_ic']} "
              f"wins={r['B_winsorized_ic']} mid90={r['C_middle90pct_ic']}")

    (OUT / "price_stress_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
