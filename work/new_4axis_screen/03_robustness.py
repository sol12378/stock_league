"""Part 3: 頑健性。Price軸の効きは本当に「割安さ」なのか、それとも小型株を拾っているだけなのか。

- 規模(log時価総額)との相関
- 横断回帰: 先行リターン ~ 4軸 + log時価総額 (規模を入れても Price は残るか)
- 規模中立版 Price軸(時価総額三分位の中で順位付け)の rank IC
- 大型半分・小型半分に分けたときの各軸の rank IC
- 単一レジーム問題: 3コホートはいずれも2023-2025の同一相場に属する
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
COHORTS = {
    "FY2024_252d": "future_return_252d",
    "FY2025_126d": "future_return_126d",
    "FY2023_252d": "future_return_252d",
}
AXES = ["moat_p", "change_p", "future_p", "price_p"]


def ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    s2 = (resid @ resid) / dof
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(s2 * xtx_inv))
    return beta, se


def main() -> None:
    report: dict[str, object] = {}
    for key, retcol in COHORTS.items():
        d = pd.read_csv(OUT / f"pit_scored_{key}.csv", dtype={"code": str})
        d = d[d[retcol].notna() & (d["market_equity_pti"] > 0)].copy()
        d["log_mcap"] = np.log(d["market_equity_pti"])
        d["size_p"] = d["log_mcap"].rank(pct=True) * 100
        ret = d[retcol]

        r: dict[str, object] = {
            "n": int(len(d)),
            "spearman_axis_vs_log_mcap": {
                a: round(float(d[a].corr(d["log_mcap"], method="spearman")), 4) for a in AXES
            },
            "rank_ic_size_alone": round(float(d["size_p"].corr(ret, method="spearman")), 4),
        }

        # --- 横断回帰(順位点は0-100なので係数は「1パーセンタイルあたりのリターン」) ---
        # リターンは外れ値の影響が大きいので順位化して回帰する(Spearman型)
        yq = ret.rank(pct=True).to_numpy()
        for label, cols in [
            ("axes_only", AXES),
            ("axes_plus_size", AXES + ["size_p"]),
            ("price_and_size", ["price_p", "size_p"]),
        ]:
            X = np.column_stack([np.ones(len(d))] + [d[c].rank(pct=True).to_numpy() for c in cols])
            beta, se = ols(X, yq)
            r[f"regression_{label}"] = {
                c: {"coef": round(float(beta[i + 1]), 4), "t": round(float(beta[i + 1] / se[i + 1]), 2)}
                for i, c in enumerate(cols)
            }
            r[f"regression_{label}"]["r2"] = round(
                float(1 - ((yq - X @ beta) ** 2).sum() / ((yq - yq.mean()) ** 2).sum()), 4
            )

        # --- 規模中立版 Price 軸 ---
        d["size_tercile"] = pd.qcut(d["log_mcap"], 3, labels=["small", "mid", "large"])
        d["price_p_neutral"] = d.groupby("size_tercile", observed=True)["price_p"].transform(
            lambda s: s.rank(pct=True) * 100
        )
        r["rank_ic_price_size_neutral"] = round(
            float(d["price_p_neutral"].corr(ret, method="spearman")), 4
        )
        r["rank_ic_price_raw"] = round(float(d["price_p"].corr(ret, method="spearman")), 4)
        r["rank_ic_by_size_tercile"] = {
            str(t): {a: round(float(g[a].corr(g[retcol], method="spearman")), 4) for a in AXES}
            | {"n": int(len(g))}
            for t, g in d.groupby("size_tercile", observed=True)
        }

        # --- 等重み合成を規模中立Priceで作り直したら ---
        d["total_equal25_sizeneutral"] = d[["moat_p", "change_p", "future_p"]].sum(axis=1).add(
            d["price_p_neutral"]
        ) / 4
        r["rank_ic_total_equal25"] = round(float(d["total_equal25"].corr(ret, method="spearman")), 4)
        r["rank_ic_total_equal25_sizeneutral"] = round(
            float(d["total_equal25_sizeneutral"].corr(ret, method="spearman")), 4
        )
        report[key] = r
        print(f"[{key}] done")

    (OUT / "robustness_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
