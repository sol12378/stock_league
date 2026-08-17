"""Part 2: 欠測を直した4軸(Moat/Change/Future/Price)を時点データ(PITパネル)の上で作り直し、
前向きリターンで検証する。

Price軸は yfinance(売買代金上位300社)ではなく XBRL 由来の PIT 時価総額から作るので
全社カバレッジになる。ここが現行実装との決定的な違い。

コホート:
  FY2024 / 252日 … 4軸すべてが計算できる唯一の長期コホート(主検証)
  FY2025 / 126日 … 4軸すべて計算可、期間は短い(副検証)
  FY2023 / 252日 … パネル初年度のため前期比が取れず Change 軸が退化(参考のみ)

入力: work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv
      data/processed/scores.csv (Future軸のキーワード点のみ流用)
出力: work/new_4axis_screen/out/pit_*.csv / pit_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20260817)

PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"
LIQUIDITY_YEN = 20_000_000
N_PICK = 20
SECTOR_CAP = 2

MOAT_COLS = ["gross_profitability", "op_margin", "roa", "ocf_margin", "equity_ratio"]
CHANGE_COLS = ["piotroski_f_score", "delta_roa", "delta_gross_margin",
               "delta_asset_turnover", "revenue_growth", "oi_growth"]
FUTURE_COLS = ["future_moat_score"]
PRICE_COLS = ["earnings_to_price", "book_to_market"]

COHORTS = [
    {"year": 2024, "ret": "future_return_252d", "role": "primary"},
    {"year": 2025, "ret": "future_return_126d", "role": "secondary"},
    {"year": 2023, "ret": "future_return_252d", "role": "reference_change_degenerate"},
]


def pr(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").mul(100.0)


def blend(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """各成分を0-100順位点にして単純平均。欠測成分はゼロ埋めせず平均から外す。"""
    return pd.DataFrame({c: pr(df[c]) for c in cols}).mean(axis=1, skipna=True)


def build_axes(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["op_margin"] = d["operating_income"] / d["revenue"].replace(0, np.nan)
    d["ocf_margin"] = d["operating_cf"] / d["revenue"].replace(0, np.nan)
    d["equity_ratio"] = 1.0 - d["leverage"]
    d["moat_p"] = blend(d, MOAT_COLS)
    d["change_p"] = blend(d, CHANGE_COLS)
    d["future_p"] = blend(d, FUTURE_COLS)
    d["price_p"] = blend(d, PRICE_COLS)
    return d


def pick_sector_capped(d: pd.DataFrame, key: str, n: int, cap: int | None) -> pd.DataFrame:
    d = d.sort_values(key, ascending=False)
    if cap is None:
        return d.head(n)
    out, counts = [], {}
    for _, row in d.iterrows():
        sec = row["sector_33"]
        if counts.get(sec, 0) >= cap:
            continue
        out.append(row)
        counts[sec] = counts.get(sec, 0) + 1
        if len(out) == n:
            break
    return pd.DataFrame(out)


def decile_spread(d: pd.DataFrame, key: str, ret: str) -> dict[str, float]:
    q = pd.qcut(d[key].rank(method="first"), 10, labels=False)
    top = float(d.loc[q == 9, ret].mean())
    bot = float(d.loc[q == 0, ret].mean())
    return {"top_decile": round(top, 4), "bottom_decile": round(bot, 4), "spread": round(top - bot, 4)}


def main() -> None:
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False)
    scores = pd.read_csv(
        ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False,
        usecols=["code", "future_moat_score"],
    ).drop_duplicates("code")

    panel = panel.sort_values(["code", "fiscal_year"])
    for src, dst in [("revenue", "revenue_growth"), ("operating_income", "oi_growth")]:
        prev = panel.groupby("code")[src].shift(1)
        panel[dst] = (panel[src] - prev) / prev.abs().replace(0, np.nan)
    panel = panel.merge(scores, on="code", how="left")

    report: dict[str, object] = {
        "config": {
            "liquidity_yen": LIQUIDITY_YEN, "n_pick": N_PICK, "sector_cap": SECTOR_CAP,
            "moat_components": MOAT_COLS, "change_components": CHANGE_COLS,
            "future_components": FUTURE_COLS, "price_components": PRICE_COLS,
        },
        "caveats": [
            "Future軸のキーワード点は2026年時点のEDINET本文から作られた時点不変値であり、過去コホートに適用するのは前方視バイアスを含む。",
            "パネルは提出済みの有価証券報告書から構築しているため上場廃止企業が抜けている(生存者バイアス)。",
            "金融業はPITパネルの利益率系が比較不能なため Step 0 で除外している(現行本番実装は別扱いで残している)。",
        ],
    }
    per_cohort: dict[str, object] = {}
    picks_all = []

    for spec in COHORTS:
        year, retcol = spec["year"], spec["ret"]
        key = f"FY{year}_{retcol.replace('future_return_', '')}"
        d = panel[panel["fiscal_year"] == year].copy()
        n0 = len(d)

        step0 = (
            d["price_join_success"].fillna(False)
            & ~d["financial_exclusion_flag"].fillna(False)
            & ~d["distress_hard_exclusion_flag"].fillna(False)
            & ~d["negative_equity_flag"].fillna(False)
            & (d["decision_adv60"].fillna(0) >= LIQUIDITY_YEN)
            & d[retcol].notna()
        )
        d = d[step0].copy()
        d["op_margin"] = d["operating_income"] / d["revenue"].replace(0, np.nan)
        d["ocf_margin"] = d["operating_cf"] / d["revenue"].replace(0, np.nan)
        d["equity_ratio"] = 1.0 - d["leverage"]
        comp_cov = {
            c: round(float(d[c].notna().mean() * 100), 1)
            for c in MOAT_COLS + CHANGE_COLS + FUTURE_COLS + PRICE_COLS
        }
        d = build_axes(d)
        axes = ["moat_p", "change_p", "future_p", "price_p"]
        d["total_equal25"] = d[axes].mean(axis=1)
        d["total_current_weights"] = (
            0.30 * d["moat_p"] + 0.25 * d["change_p"] + 0.30 * d["future_p"] + 0.15 * d["price_p"]
        )
        d["total_3axis_nofuture"] = d[["moat_p", "change_p", "price_p"]].mean(axis=1)

        ret = d[retcol]
        yr: dict[str, object] = {
            "role": spec["role"],
            "return_column": retcol,
            "n_panel": int(n0),
            "n_after_step0": int(len(d)),
            "anchor_date_median": str(pd.to_datetime(d["decision_anchor_date"]).median().date()),
            "component_coverage_pct": comp_cov,
            "axis_distinct_values": {a: int(d[a].nunique()) for a in axes},
            "universe_equal_weight_return": round(float(ret.mean()), 4),
            "universe_median_return": round(float(ret.median()), 4),
            "universe_cap_weight_return": round(
                float(np.average(ret, weights=d["market_equity_pti"].clip(lower=0).fillna(0))), 4
            ),
            "spearman_corr": d[axes].corr(method="spearman").round(3).to_dict(),
        }
        var_s = d["total_equal25"].var()
        yr["effective_weight_variance_share"] = {
            a: round(float(0.25 * d[a].cov(d["total_equal25"]) / var_s), 4) for a in axes
        }
        composites = ["total_equal25", "total_current_weights", "total_3axis_nofuture"]
        yr["rank_ic"] = {a: round(float(d[a].corr(ret, method="spearman")), 4) for a in axes + composites}
        yr["decile_spread"] = {a: decile_spread(d, a, retcol) for a in axes + composites}

        ports: dict[str, object] = {}
        for label, sort_key, cap in [
            ("equal25_sectorcap2", "total_equal25", SECTOR_CAP),
            ("equal25_nodiv", "total_equal25", None),
            ("current_weights_sectorcap2", "total_current_weights", SECTOR_CAP),
            ("3axis_nofuture_sectorcap2", "total_3axis_nofuture", SECTOR_CAP),
            ("moat_only_sectorcap2", "moat_p", SECTOR_CAP),
            ("change_only_sectorcap2", "change_p", SECTOR_CAP),
            ("future_only_sectorcap2", "future_p", SECTOR_CAP),
            ("price_only_sectorcap2", "price_p", SECTOR_CAP),
        ]:
            sel = pick_sector_capped(d, sort_key, N_PICK, cap)
            boot = np.array([
                sel[retcol].sample(len(sel), replace=True, random_state=int(RNG.integers(1e9))).mean()
                for _ in range(2000)
            ])
            ports[label] = {
                "n": int(len(sel)),
                "mean_return": round(float(sel[retcol].mean()), 4),
                "median_return": round(float(sel[retcol].median()), 4),
                "excess_vs_universe_ew": round(float(sel[retcol].mean() - ret.mean()), 4),
                "bootstrap_ci95": [round(float(np.percentile(boot, 2.5)), 4),
                                   round(float(np.percentile(boot, 97.5)), 4)],
                "n_sectors": int(sel["sector_33"].nunique()),
                "median_market_cap_oku_yen": round(float(sel["market_equity_pti"].median() / 1e8), 1),
            }
            keep = sel[["code", "company_name", "sector_33", "market_equity_pti",
                        "moat_p", "change_p", "future_p", "price_p", retcol]].copy()
            keep.insert(0, "portfolio", label)
            keep.insert(0, "cohort", key)
            keep = keep.rename(columns={retcol: "forward_return"})
            picks_all.append(keep)

        draws = np.array([
            ret.sample(N_PICK, replace=False, random_state=int(RNG.integers(1e9))).mean()
            for _ in range(2000)
        ])
        obs = ports["equal25_sectorcap2"]["mean_return"]
        ports["random20_reference"] = {
            "mean": round(float(draws.mean()), 4), "sd": round(float(draws.std()), 4),
            "p05": round(float(np.percentile(draws, 5)), 4),
            "p95": round(float(np.percentile(draws, 95)), 4),
            "percentile_of_equal25": round(float((draws < obs).mean() * 100), 1),
        }
        yr["portfolios"] = ports

        W = RNG.dirichlet(np.ones(4), size=1000)
        vals = d[axes].to_numpy()
        rets = []
        for w in W:
            tmp = d.assign(_t=vals @ w)
            rets.append(pick_sector_capped(tmp, "_t", N_PICK, SECTOR_CAP)[retcol].mean())
        rets = np.array(rets)
        yr["weight_sensitivity_dirichlet1000"] = {
            "mean": round(float(rets.mean()), 4), "sd": round(float(rets.std()), 4),
            "min": round(float(rets.min()), 4), "max": round(float(rets.max()), 4),
            "range": round(float(rets.max() - rets.min()), 4),
            "equal25_percentile": round(float((rets < obs).mean() * 100), 1),
        }
        yr["all_four_axes_above_threshold"] = {
            str(t): int((d[axes] >= t).all(axis=1).sum()) for t in [50, 60, 70, 80, 90]
        }
        dm = pd.get_dummies(d["sector_33"]).astype(float).to_numpy()
        X = np.column_stack([np.ones(len(d)), dm])
        yr["r2_vs_sector33_dummies"] = {}
        for a in axes:
            y = d[a].to_numpy()
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            yr["r2_vs_sector33_dummies"][a] = round(
                float(1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()), 4
            )

        d[["code", "company_name", "sector_33", "fiscal_year", "decision_anchor_date",
           "market_equity_pti"] + axes +
          ["total_equal25", "total_current_weights", "total_3axis_nofuture", retcol]
          ].to_csv(OUT / f"pit_scored_{key}.csv", index=False)
        per_cohort[key] = yr
        print(f"[{key}] n={len(d)} done")

    report["cohorts"] = per_cohort
    picks = pd.concat(picks_all)
    picks.to_csv(OUT / "pit_portfolio_picks.csv", index=False)

    # 年をまたぐ入れ替わり(equal25 sectorcap2)
    a = set(picks[(picks.cohort == "FY2024_252d") & (picks.portfolio == "equal25_sectorcap2")]["code"])
    b = set(picks[(picks.cohort == "FY2025_126d") & (picks.portfolio == "equal25_sectorcap2")]["code"])
    report["turnover_equal25_FY2024_to_FY2025"] = {
        "overlap": len(a & b), "turnover_pct": round((1 - len(a & b) / N_PICK) * 100, 1)
    }

    (OUT / "pit_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "cohorts"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
