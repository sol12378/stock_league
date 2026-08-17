"""Part 9c: 上位候補だけ株数を確実に埋める。

Yahoo のレート制限で全社ぶんは一度に取り切れない。だが正確な時価総額が本当に要るのは
「上位20社に入りうる会社」だけなので、暫定スコアの上位N社に絞って未取得ぶんを埋める。
分割ズレは時価総額を過小に見せる＝Price軸を押し上げる方向にしか働かないので、
Price軸の高い側さえ潰せば選抜は安定する。

使い方: 07_final_screen.py を回す前に実行。取れるまで数回繰り返してよい。
"""
from __future__ import annotations

import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"
TOP_N = 150
WORKERS = 3


def pctrank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").mul(100.0)


def blend(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return pd.DataFrame({c: pctrank(df[c]) for c in cols}).mean(axis=1, skipna=True)


def fetch(ticker: str) -> dict[str, object]:
    time.sleep(random.uniform(0.4, 1.2))
    try:
        fi = yf.Ticker(ticker).fast_info
        return {"ticker": ticker, "shares_live": fi.get("shares"),
                "last_price": fi.get("lastPrice"), "market_cap_live": fi.get("marketCap"),
                "status": "ok"}
    except Exception as exc:
        return {"ticker": ticker, "status": f"error:{type(exc).__name__}"}


def main() -> None:
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False)
    live = pd.read_csv(OUT / "shares_live.csv", dtype={"code": str})

    panel = panel.sort_values(["code", "fiscal_year"])
    for src, dst in [("revenue", "revenue_growth"), ("operating_income", "oi_growth")]:
        prev = panel.groupby("code")[src].shift(1)
        panel[dst] = (panel[src] - prev) / prev.abs().replace(0, np.nan)
    fin = panel.groupby("code", as_index=False).last()

    d = scores[["code", "ticker", "close", "future_moat_score", "investment_eligible"]].merge(
        fin[["code", "shares_outstanding_pti", "revenue", "operating_income", "net_income",
             "equity", "operating_cf", "leverage", "roa", "gross_profitability",
             "piotroski_f_score", "delta_roa", "delta_gross_margin", "delta_asset_turnover",
             "revenue_growth", "oi_growth"]], on="code", how="left"
    ).merge(live[["code", "shares_live"]].dropna(subset=["code"]).drop_duplicates("code"),
            on="code", how="left")
    u = d[d["investment_eligible"].fillna(False).astype(bool)].copy()

    shares = u["shares_live"].fillna(u["shares_outstanding_pti"])
    mc = (shares * u["close"]).where(lambda s: s > 0)
    u["earnings_to_price"] = u["net_income"] / mc
    u["book_to_market"] = u["equity"] / mc
    u["gp_to_assets"] = u["gross_profitability"]
    u["op_margin"] = u["operating_income"] / u["revenue"].replace(0, np.nan)
    u["ocf_margin"] = u["operating_cf"] / u["revenue"].replace(0, np.nan)
    u["equity_ratio"] = 1.0 - u["leverage"]
    u["total"] = pd.concat([
        blend(u, ["gp_to_assets", "op_margin", "roa", "ocf_margin", "equity_ratio"]),
        blend(u, ["piotroski_f_score", "delta_roa", "delta_gross_margin",
                  "delta_asset_turnover", "revenue_growth", "oi_growth"]),
        pctrank(u["future_moat_score"]),
        blend(u, ["earnings_to_price", "book_to_market"]),
    ], axis=1).mean(axis=1)

    cand = u.nlargest(TOP_N, "total")
    todo = cand.loc[cand["shares_live"].isna(), "ticker"].dropna().tolist()
    print(f"暫定上位{TOP_N}社のうち未取得 {len(todo)} 件", file=sys.stderr)
    if not todo:
        print("上位候補はすべて実勢株数を持っている")
        return

    rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for f in as_completed([ex.submit(fetch, t) for t in todo]):
            rows.append(f.result())
    got = pd.DataFrame(rows)
    ok = got[got.get("shares_live").notna()] if "shares_live" in got else got.iloc[0:0]
    print(f"取得成功 {len(ok)} / {len(todo)}")

    for _, r in ok.iterrows():
        m = live["ticker"] == r["ticker"]
        for k in ["shares_live", "last_price", "market_cap_live", "status"]:
            live.loc[m, k] = r[k]
    live.to_csv(OUT / "shares_live.csv", index=False)
    print("累計:", int(live["shares_live"].notna().sum()), "/", len(live))


if __name__ == "__main__":
    main()
