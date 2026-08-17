# -*- coding: utf-8 -*-
"""ハイブリッド守破離(試作): 守=真バフェット5社 + 破/離=残り15社 = 20社。目標=バフェットTop12超え。

ユーザー設計(2026-07-20):
  守 = 真バフェット(Top12)から5社 → 現行oursのBuffett Core5(Graham深バリュー)を差し替え
  破/離 = 残り15社(現行ours: Emerging Core5=離/未来の堀, Transformation Core5=破/変革, Dual Moat3, Bridge2)
  合計20社でバフェット(Top12)を超えるのが理想。
規律: in-sample特性(全PF2026-06選定→過去適用)。チューニングなし。計測phase5規約。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
WORK = ROOT / "work/pure_buffett_benchmark"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

# ---- genuine Buffett Top12 (build_pure_buffett と同一) ----
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
elig = s[truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")].copy()
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "revenue_growth",
          "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "net_income", "equity", "shares_outstanding"]:
    elig[c] = pd.to_numeric(elig[c], errors="coerce")
px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px_all["date"] = pd.to_datetime(px_all["date"])
last_px = px_all.sort_values("date").groupby("ticker")["adj_close"].last()
elig["mcap"] = elig.ticker.map(last_px) * elig.shares_outstanding
elig["ey"] = elig.net_income / elig.mcap; elig["pbr"] = elig.mcap / elig.equity
bq = elig[(elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
          (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
          (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
          (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)].dropna(subset=["ey", "mcap"])
bq = bq[bq.ey > 0].copy()
bq["mf"] = bq.roe.rank(ascending=False) + bq.ey.rank(ascending=False)
d = bq.sort_values("mf"); cnt, buf12 = {}, []
for _, r in d.iterrows():
    if cnt.get(r.sector_33, 0) >= 2: continue
    cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1; buf12.append(r.code)
    if len(buf12) == 12: break
mc = bq.set_index("code").loc[buf12, "mcap"]; wcap = (mc / mc.sum()).clip(upper=0.25); wcap /= wcap.sum()
w_buf12 = {c + ".T": float(wcap[c]) for c in buf12}

# ---- ours ----
a = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
a["code"] = a["code_n"].astype(str).str.zfill(4); a["ticker"] = a["code"] + ".T"
old_core = a[a.final_role == "Buffett Core"]["code"].tolist()
other15 = a[a.final_role != "Buffett Core"].copy()
w_ours = a.set_index("ticker")["target_weight_final"].to_dict()

# ---- 守5 = 真バフェットTop12上位から、ours非収録の5社 ----
shu5 = [c for c in buf12 if c not in a.code.tolist()][:5]
core_wt_total = a[a.final_role == "Buffett Core"]["target_weight_final"].sum()  # 旧Core合計≈0.25
# ハイブリッド重み: 守5に旧Core合計を等分, 残り15は現行重み
w_hybrid = {c + ".T": core_wt_total / 5 for c in shu5}
for _, r in other15.iterrows():
    w_hybrid[r.ticker] = r.target_weight_final
ssum = sum(w_hybrid.values()); w_hybrid = {k: v / ssum for k, v in w_hybrid.items()}

names = elig.set_index("code")["company_name"].to_dict()
print("守5 (真バフェット, ours非収録の上位5):")
for c in shu5:
    r = bq.set_index("code").loc[c]
    print(f'  {c} {str(names.get(c))[:22]:22} ROE={r.roe*100:4.1f}% PBR={r.pbr:4.1f} {str(r.sector_33)[:12]}')
n_genuine = len(set(a.code.tolist()) & set(buf12))
print(f"\nハイブリッド20 = 守5(新) + 残り15(現行ours)。うち真バフェット品質名 = 5(新Core) + {n_genuine}(既存: レーザーテック/SHIFT) = {5+n_genuine}社")

# ---- multi-period harness (build_multiperiod と同一) ----
first_valid = px_all.dropna(subset=["adj_close"]).groupby("ticker")["date"].min()
need = set(w_hybrid) | set(w_ours) | set(w_buf12) | {"1306.T", "^N225"}
wide = px_all[px_all.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] *= f

def bh_slice(weights, d0, d1):
    idx = wide.loc[d0:d1].index; start = idx[0]
    cand = [t for t in weights if t in wide.columns and pd.notna(first_valid.get(t, pd.NaT))
            and first_valid.get(t) <= start + pd.Timedelta(days=10)]
    if not cand: return pd.Series(dtype=float), 0, len(weights)
    w = pd.Series({t: weights[t] for t in cand}); w /= w.sum()
    sub = wide.loc[d0:d1, cand].ffill().dropna(); shares = w / sub.iloc[0]
    return (sub * shares).sum(axis=1).pct_change(fill_method=None).dropna(), len(cand), len(weights)

def stats(rp, rb):
    n = len(rp)
    if n < 5: return {"total_return": None, "ann_return": None, "excess_vs_topix": None,
                      "volatility": None, "sharpe": None, "max_drawdown": None, "beta": None, "days": n}
    tot = float((1 + rp).prod() - 1)
    ann = float((1 + rp).prod() ** (ANN / n) - 1) if n > 20 else tot
    mdd = float(((1 + rp).cumprod() / (1 + rp).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); rb = rb.reindex(rp.index)
    annb = float((1 + rb).prod() ** (ANN / n) - 1) if n > 20 else float((1 + rb).prod() - 1)
    beta = float(rp.cov(rb) / rb.var()) if rb.var() > 0 else float("nan")
    return {"total_return": round(tot, 4), "ann_return": round(ann, 4), "excess_vs_topix": round(ann - annb, 4),
            "volatility": round(vol, 4), "sharpe": round(ann / vol, 3) if vol else None,
            "max_drawdown": round(mdd, 4), "beta": round(beta, 3), "days": n}

PERIODS = {"full": ("2021-06-01", "2026-06-01"), "P1_利上21-22": ("2021-06-01", "2022-12-31"),
           "P2_AI前半23-24": ("2023-01-01", "2024-06-30"), "P3_直近24-26": ("2024-07-01", "2026-06-01"),
           "crash24-08": ("2024-07-25", "2024-08-09")}
baskets = {"buf12_真バフェット": w_buf12, "old_ours": w_ours, "hybrid20_守破離": w_hybrid}
results = {}
for p, (d0, d1) in PERIODS.items():
    rb = wide.loc[d0:d1, "1306.T"].pct_change(fill_method=None).dropna()
    results[p] = {"topix": {**stats(rb, rb), "coverage": "-"}}
    for b, w in baskets.items():
        rp, nu, nt = bh_slice(w, d0, d1); rp = rp.reindex(rb.index).dropna()
        results[p][b] = {**stats(rp, rb), "coverage": f"{nu}/{nt}"}

json.dump({"shu5": shu5, "buf12": buf12, "results": results,
           "note": "hybrid = 守5(genuine Buffett, not in ours) + ours' other 15. in-sample. phase5-consistent."},
          open(WORK / "hybrid_results.json", "w"), ensure_ascii=False, indent=2)

lab = {"topix": "TOPIX", "buf12_真バフェット": "真バフェットTop12(目標)", "old_ours": "旧ours(Graham土台)", "hybrid20_守破離": "★ハイブリッド20(守=真バフェット5)"}
for p in PERIODS:
    print(f"\n===== {p} =====")
    print(f'{"":30}{"年率":>7}{"対TOPIX":>9}{"σ":>7}{"MDD":>8}{"β":>6}{"Sharpe":>8}{"採用":>7}')
    for k in ["topix", "buf12_真バフェット", "old_ours", "hybrid20_守破離"]:
        st = results[p][k]
        if st["ann_return"] is None:
            print(f'{lab[k]:30}  (期間内データ不足 n={st["days"]})'); continue
        exc = f'{st["excess_vs_topix"]*100:+6.1f}pt' if k != "topix" else "   ---  "
        print(f'{lab[k]:30}{st["ann_return"]*100:6.1f}%{exc:>9}{st["volatility"]*100:6.1f}%{st["max_drawdown"]*100:7.1f}%{st["beta"]:6.2f}{(st["sharpe"] if st["sharpe"] else float("nan")):8.2f}{st["coverage"]:>7}')
print("\nwritten ->", WORK / "hybrid_results.json")
