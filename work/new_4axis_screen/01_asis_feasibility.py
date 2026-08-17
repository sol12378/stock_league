"""Part 1: 新4軸案(Moat/Change/Future/Price 等重み25%)を現行データでそのまま再現し、
実行可能性・実効重み・軸間相関・上位20社を実測する。

入力: data/processed/scores.csv (現行v10の scoring.py 出力)
出力: work/new_4axis_screen/out/asis_*.csv / asis_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

AXES = {
    "moat": "moat_score",
    "change": "transformation_score",
    "future": "future_moat_score",
    "price": "valuation_score",
}


def pct_rank_0_100(s: pd.Series) -> pd.Series:
    """提案どおりの「0〜100の順位点」。同値は平均順位(pandas既定)。"""
    return s.rank(pct=True, method="average") * 100.0


def variance_contribution(parts: pd.DataFrame, weights: dict[str, float], composite: pd.Series) -> dict[str, float]:
    """実効重み = Cov(w_i * X_i, S) / Var(S)。合計は 1 になる。"""
    var_s = composite.var()
    return {k: float(weights[k] * parts[k].cov(composite) / var_s) for k in parts.columns}


def main() -> None:
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)

    report: dict[str, object] = {}

    # ---- Step 0: 現行の投資適格フィルタをそのまま使う(提案どおり「現状のモノでいい」) ----
    elig = scores[scores["investment_eligible"].fillna(False).astype(bool)].copy()
    report["step0"] = {
        "universe": int(len(scores)),
        "eligible": int(len(elig)),
        "price_available": int(scores["price_available"].fillna(False).sum()),
        "liquid_20m_60d": int(scores["liquid_20m_60d"].fillna(False).sum()),
    }

    # ---- Step 1/2: 4軸を0-100順位点にして等重み25% ----
    for name, col in AXES.items():
        elig[f"{name}_p"] = pct_rank_0_100(elig[col])
    parts = elig[[f"{n}_p" for n in AXES]].rename(columns=lambda c: c[:-2])
    weights = {k: 0.25 for k in AXES}
    elig["total_p"] = sum(weights[k] * parts[k] for k in AXES)

    # ---- 診断1: 各軸の退化(同値タイ)状況 ----
    degeneracy = []
    for name, col in AXES.items():
        raw = elig[col]
        modal = raw.value_counts(dropna=False)
        top_val = modal.index[0]
        degeneracy.append(
            {
                "axis": name,
                "source_column": col,
                "n": int(raw.notna().sum()),
                "n_exact_zero": int((raw == 0).sum()),
                "share_exact_zero_pct": round(float((raw == 0).mean() * 100), 2),
                "largest_tie_value": float(top_val) if pd.notna(top_val) else None,
                "largest_tie_n": int(modal.iloc[0]),
                "largest_tie_share_pct": round(float(modal.iloc[0] / len(raw) * 100), 2),
                "distinct_values": int(raw.nunique(dropna=True)),
                "raw_std": round(float(raw.std()), 4),
                "pct_std": round(float(elig[f"{name}_p"].std()), 4),
            }
        )
    deg = pd.DataFrame(degeneracy)
    deg.to_csv(OUT / "asis_axis_degeneracy.csv", index=False)
    report["degeneracy"] = deg.to_dict("records")

    # ---- 診断2: 軸間相関(Spearman) ----
    corr = parts.corr(method="spearman").round(4)
    corr.to_csv(OUT / "asis_axis_correlation.csv")
    report["spearman_corr"] = corr.to_dict()

    # ---- 診断3: 実効重み(分散寄与) ----
    eff = variance_contribution(parts, weights, elig["total_p"])
    report["effective_weight_variance_share"] = {k: round(v, 4) for k, v in eff.items()}

    # ---- 診断4: Price軸は「割安さ」か「データ在庫」か ----
    has_mcap = elig["market_cap"].notna()
    lav = np.log10(elig["avg_trading_value_60d"].where(elig["avg_trading_value_60d"] > 0))
    report["price_axis_is_data_inventory"] = {
        "n_with_valuation_inputs": int(has_mcap.sum()),
        "share_with_inputs_pct": round(float(has_mcap.mean() * 100), 2),
        "price_p_mean_with_inputs": round(float(elig.loc[has_mcap, "price_p"].mean()), 2),
        "price_p_mean_without_inputs": round(float(elig.loc[~has_mcap, "price_p"].mean()), 2),
        "spearman_price_p_vs_log_trading_value": round(
            float(elig["price_p"].corr(lav, method="spearman")), 4
        ),
        "auc_price_p_predicts_has_data": round(
            float(
                (
                    elig.loc[has_mcap, "price_p"].rank().mean()
                    - (has_mcap.sum() + 1) / 2
                )
                / (~has_mcap).sum()
            ),
            4,
        ),
    }

    # ---- 診断5: Change軸とPrice軸の成分重複(式レベル) ----
    # transformation = .35 z(1/PBR) + .20 z(1/PER) + .20 avg_z(growth) + .15 z(div)   (合計0.90)
    # valuation      = .50 z(1/PER) + .35 z(1/PBR) + .15 z(div)                        (合計1.00)
    report["formula_overlap"] = {
        "change_weight_on_price_multiples": 0.35 + 0.20,
        "change_weight_on_dividend": 0.15,
        "change_weight_on_growth": 0.20,
        "change_weights_sum": 0.90,
        "price_weight_on_price_multiples": 0.50 + 0.35,
        "price_weight_on_dividend": 0.15,
        "nominal_price_exposure_at_equal_25pct": round(0.25 * 1.00 + 0.25 * (0.55 + 0.15), 4),
    }

    # ---- Step 3: 上位20社(分散なし / 業種上限2) ----
    def pick(df: pd.DataFrame, n: int, sector_cap: int | None) -> pd.DataFrame:
        df = df.sort_values("total_p", ascending=False)
        if sector_cap is None:
            return df.head(n)
        out, counts = [], {}
        for _, row in df.iterrows():
            sec = row["sector_33"]
            if counts.get(sec, 0) >= sector_cap:
                continue
            out.append(row)
            counts[sec] = counts.get(sec, 0) + 1
            if len(out) == n:
                break
        return pd.DataFrame(out)

    cols = [
        "code", "company_name", "company_name_ja", "sector_33", "scale_category",
        "market_cap", "avg_trading_value_60d",
        "moat_p", "change_p", "future_p", "price_p", "total_p",
    ]
    top20_raw = pick(elig, 20, None)[cols]
    top20_div = pick(elig, 20, 2)[cols]
    top20_raw.to_csv(OUT / "asis_top20_nodiv.csv", index=False)
    top20_div.to_csv(OUT / "asis_top20_sectorcap2.csv", index=False)

    cur = pd.read_csv(ROOT / "data/processed/portfolio.csv", dtype={"code": str})
    report["top20"] = {
        "nodiv_has_valuation_inputs": int(top20_raw["market_cap"].notna().sum()),
        "sectorcap2_has_valuation_inputs": int(top20_div["market_cap"].notna().sum()),
        "nodiv_sector_counts": top20_raw["sector_33"].value_counts().to_dict(),
        "sectorcap2_sector_counts": top20_div["sector_33"].value_counts().to_dict(),
        "overlap_with_current_v10_nodiv": int(len(set(top20_raw["code"]) & set(cur["code"]))),
        "overlap_with_current_v10_sectorcap2": int(len(set(top20_div["code"]) & set(cur["code"]))),
        "overlap_codes": sorted(set(top20_div["code"]) & set(cur["code"])),
    }

    # ---- 診断6: 4軸すべてが同時に高い会社は存在するか(ANDの実行可能性) ----
    and_counts = {}
    for thr in [50, 60, 70, 80, 90]:
        m = (parts >= thr).all(axis=1)
        and_counts[thr] = int(m.sum())
    report["all_four_axes_above_threshold"] = and_counts

    # ---- 診断7: 「どれか1軸に賭けない」は成立しているか ----
    # 上位20社が各軸で何パーセンタイルにいるか
    report["top20_axis_profile_sectorcap2"] = {
        f"{a}_p": {
            "min": round(float(top20_div[f"{a}_p"].min()), 1),
            "median": round(float(top20_div[f"{a}_p"].median()), 1),
            "max": round(float(top20_div[f"{a}_p"].max()), 1),
        }
        for a in AXES
    }

    elig[["code", "company_name", "sector_33", "market_cap"] + [f"{a}_p" for a in AXES] + ["total_p"]].to_csv(
        OUT / "asis_all_eligible_scored.csv", index=False
    )
    (OUT / "asis_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
