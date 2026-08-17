from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("..").resolve()
OUT_DIR = Path("outputs/tenbagger_screen_20260814")


def main() -> None:
    screen = pd.read_csv(OUT_DIR / "screening_all_companies.csv", dtype={"code": str, "doc_id": str})
    screen["code"] = screen["code"].str.zfill(4)

    facts_path = ROOT / "outputs/phase2_top1200_walkforward_perfect_fix/xbrl_facts/edinet_xbrl_extended_facts.csv"
    facts = pd.read_csv(facts_path, usecols=["code", "doc_id", "shares_outstanding_pti"], dtype={"code": str, "doc_id": str})
    facts["code"] = facts["code"].str.zfill(4)
    facts = facts.drop_duplicates("doc_id", keep="last")

    latest = pd.read_csv(ROOT / "data/processed/latest_prices.csv", dtype={"ticker": str})[
        ["ticker", "latest_date", "close", "avg_trading_value_60d", "history_days"]
    ]
    scores = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str})
    scores["code"] = scores["code"].str.zfill(4)
    score_cols = [
        "code",
        "annual_volatility",
        "max_drawdown",
        "investment_eligible",
        "investment_exclusion_reasons",
        "adjusted_bb_score",
        "score_rank",
        "category",
    ]
    scores = scores[score_cols].drop_duplicates("code", keep="last")

    drop_cols = [
        "shares_outstanding_pti",
        "latest_date",
        "close",
        "avg_trading_value_60d",
        "history_days",
        "annual_volatility",
        "max_drawdown",
        "investment_eligible",
        "investment_exclusion_reasons",
        "adjusted_bb_score",
        "score_rank",
        "category",
        "market_cap_proxy_jpy",
        "price_to_sales_proxy",
        "purchase_risk_notes",
    ]
    screen = screen.drop(columns=[c for c in drop_cols if c in screen.columns])
    screen = screen.merge(facts, on=["code", "doc_id"], how="left").merge(latest, on="ticker", how="left").merge(scores, on="code", how="left")
    screen["market_cap_proxy_jpy"] = screen["close"] * screen["shares_outstanding_pti"]
    screen["price_to_sales_proxy"] = screen["market_cap_proxy_jpy"] / screen["revenue_p4"].replace(0, np.nan)

    def risk_notes(row: pd.Series) -> str:
        notes: list[str] = []
        if row.get("investment_eligible") is False:
            notes.append(f"既存適格性フィルター不通過: {row.get('investment_exclusion_reasons') or '理由要確認'}")
        if pd.notna(row.get("avg_trading_value_60d")) and row["avg_trading_value_60d"] < 20_000_000:
            notes.append("60日平均売買代金2,000万円未満")
        if pd.notna(row.get("annual_volatility")) and row["annual_volatility"] >= 0.60:
            notes.append("年率ボラティリティ60%以上")
        if pd.notna(row.get("max_drawdown")) and row["max_drawdown"] <= -0.60:
            notes.append("ローカル5年最大下落率-60%以下")
        if pd.notna(row.get("price_to_sales_proxy")) and row["price_to_sales_proxy"] >= 15:
            notes.append("概算PSR15倍以上")
        return " / ".join(notes) if notes else "目立つ機械的警告なし（定性確認は別途必要）"

    screen["purchase_risk_notes"] = screen.apply(risk_notes, axis=1)
    screen.to_csv(OUT_DIR / "screening_all_companies.csv", index=False)
    candidate_mask = (
        (screen["strict_overlap_count"] >= 3)
        | (screen["cagr_overlap_count"] >= 3)
        | (screen["cagr_owner_proxy_overlap_count"] >= 3)
    )
    screen[candidate_mask].to_csv(OUT_DIR / "ranked_candidates.csv", index=False)


if __name__ == "__main__":
    main()
