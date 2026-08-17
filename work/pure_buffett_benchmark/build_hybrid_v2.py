# -*- coding: utf-8 -*-
"""ハイブリッド守破離 v2(試作): 破/離を study スコアから新規形成 + 守5重み最適化 + 累積図。

ユーザー要望(2026-07-20):
 1. 破・離の15社を study スコアから新規形成し直す(現行ours流用でなく):
    守5 = 真バフェットTop12上位(ours非収録) = ZOZO/日本オラクル/名村/サンリオ/SCREEN
    離8 = category "Future Moat" を adjusted_bb_score 上位で(未来の堀/エマージング)
    破7 = category "Transformation Moat" を adjusted_bb_score 上位で(割安×変革)
    ガード(事前定義): investment_eligible & 非金融 & 流動 & 価格 & >=756d & 営業黒字 & 純黒字 & 同一セクター上限2
 2. 守5含む20社の重みを 均等 / 役割予算(3スリーブ均等) / 最小分散(scipy, 上限15%) の3方式で比較。
 3. 累積リターン図(守/破/離/バフェット/TOPIX + ハイブリッド)。
規律: in-sample特性(2026-06選定→過去適用)。選定は study スコアの機械適用でチューニングなし。計測phase5規約。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Hiragino Sans"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
WORK = ROOT / "work/pure_buffett_benchmark"
ANN = 252
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}

# ---------------- data ----------------
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4); s["ticker"] = s["code"] + ".T"
def truthy(df, c): return df[c].astype(str).str.lower().isin(["true", "1", "1.0"])
for c in ["adjusted_bb_score", "roe", "operating_margin", "equity_ratio", "operating_cf",
          "revenue_growth", "operating_income_growth", "operating_loss_years_3y", "net_loss_years_3y",
          "negative_ocf_years_3y", "operating_income", "net_income", "equity", "shares_outstanding",
          "annual_volatility"]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet", columns=["date", "ticker", "adj_close"])
px_all["date"] = pd.to_datetime(px_all["date"])
histd = px_all.groupby("ticker")["adj_close"].apply(lambda x: x.notna().sum())
s["histd"] = s["ticker"].map(histd).fillna(0)
first_valid = px_all.dropna(subset=["adj_close"]).groupby("ticker")["date"].min()
last_px = px_all.sort_values("date").groupby("ticker")["adj_close"].last()

base = truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available") & \
       truthy(s, "liquid_20m_60d") & (s.histd >= 756)

# 守5 = genuine Buffett Top12 上位(ours非収録)
s["mcap"] = s.ticker.map(last_px) * s.shares_outstanding
s["ey"] = s.net_income / s.mcap
bqmask = base & (s.roe >= 0.15) & (s.operating_margin >= 0.10) & (s.equity_ratio >= 0.50) & \
         (s.operating_loss_years_3y == 0) & (s.net_loss_years_3y == 0) & (s.negative_ocf_years_3y == 0) & \
         (s.operating_cf > 0) & (s.revenue_growth >= 0) & (s.operating_income_growth >= 0) & \
         (s.ey > 0) & s.mcap.notna()
bq = s[bqmask].copy(); bq["mf"] = bq.roe.rank(ascending=False) + bq.ey.rank(ascending=False)
d = bq.sort_values("mf"); cnt, buf12 = {}, []
for _, r in d.iterrows():
    if cnt.get(r.sector_33, 0) >= 2: continue
    cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1; buf12.append(r.code)
    if len(buf12) == 12: break
a = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
a["code"] = a["code_n"].astype(str).str.zfill(4); a["ticker"] = a["code"] + ".T"
ours_codes = set(a.code)
shu5 = [c for c in buf12 if c not in ours_codes][:5]
mc = bq.set_index("code").loc[buf12, "mcap"]; wcap = (mc / mc.sum()).clip(upper=0.25); wcap /= wcap.sum()
w_buf12 = {c + ".T": float(wcap[c]) for c in buf12}

# 破/離 新規形成: category × adjusted_bb_score + 黒字ガード
def pick_cat(cat, n, exclude):
    pool = s[base & (s.category == cat) & (s.operating_income > 0) & (s.net_income > 0) &
             (~s.code.isin(exclude))].sort_values("adjusted_bb_score", ascending=False)
    cnt, out = {}, []
    for _, r in pool.iterrows():
        if cnt.get(r.sector_33, 0) >= 2: continue
        cnt[r.sector_33] = cnt.get(r.sector_33, 0) + 1; out.append(r.code)
        if len(out) == n: break
    return out

ri8 = pick_cat("Future Moat", 8, set(shu5))
ha7 = pick_cat("Transformation Moat", 7, set(shu5) | set(ri8))
sleeves = {"守(真Buffett)": shu5, "破(Transformation)": ha7, "離(FutureMoat)": ri8}
hybrid = shu5 + ha7 + ri8
assert len(hybrid) == 20, len(hybrid)
names = s.set_index("code")["company_name"].to_dict()
info = s.set_index("code")

print("=== ハイブリッドv2 構成 (守5 + 破7 + 離8 = 20) ===")
for tag, cs in sleeves.items():
    print(f"\n[{tag}] {len(cs)}社")
    for c in cs:
        r = info.loc[c]
        roe = r.roe * 100 if pd.notna(r.roe) else float("nan")
        print(f'  {c} {str(names[c])[:22]:22} ROE={roe:4.0f}% bb={r.adjusted_bb_score:.2f} vol={r.annual_volatility:.2f} {str(r.sector_33)[:13]}')

# ---------------- price panel ----------------
tickers = [c + ".T" for c in hybrid]
need = set(tickers) | set(w_buf12) | set(a.ticker) | {"1306.T", "^N225"}
wide = px_all[px_all.ticker.isin(need)].pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
for t, (d0, f) in SPLIT_FIXES.items():
    if t in wide.columns: wide.loc[wide.index >= d0, t] *= f

def bh(weights, d0, d1):
    idx = wide.loc[d0:d1].index; start = idx[0]
    cand = [t for t in weights if t in wide.columns and pd.notna(first_valid.get(t, pd.NaT))
            and first_valid.get(t) <= start + pd.Timedelta(days=10)]
    if not cand: return pd.Series(dtype=float), 0, len(weights)
    w = pd.Series({t: weights[t] for t in cand}); w /= w.sum()
    sub = wide.loc[d0:d1, cand].ffill().dropna(); shares = w / sub.iloc[0]
    return (sub * shares).sum(axis=1).pct_change(fill_method=None).dropna(), len(cand), len(weights)

# ---------------- weight schemes ----------------
w_equal = {t: 1 / 20 for t in tickers}
# 役割予算: 3スリーブ均等(各1/3), スリーブ内均等
w_rb = {}
for cs in sleeves.values():
    for c in cs:
        w_rb[c + ".T"] = (1 / 3) / len(cs)
ssum = sum(w_rb.values()); w_rb = {k: v / ssum for k, v in w_rb.items()}
# 最小分散: 直近756日の共分散, long-only, 上限15%
ret3 = wide[tickers].tail(756).ffill().pct_change(fill_method=None).dropna()
cov = ret3.cov().values
n = len(tickers)
def pvar(w): return float(w @ cov @ w)
cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
bnds = [(0.0, 0.15)] * n
res = minimize(pvar, np.repeat(1 / n, n), method="SLSQP", bounds=bnds, constraints=cons,
               options={"maxiter": 500, "ftol": 1e-12})
w_mv = {tickers[i]: float(max(res.x[i], 0)) for i in range(n)}
mvs = sum(w_mv.values()); w_mv = {k: v / mvs for k, v in w_mv.items()}

# ---------------- backtest ----------------
def stats(rp, rb):
    m = len(rp)
    if m < 5: return {"ann_return": None, "excess_vs_topix": None, "volatility": None,
                      "sharpe": None, "max_drawdown": None, "beta": None}
    ann = float((1 + rp).prod() ** (ANN / m) - 1) if m > 20 else float((1 + rp).prod() - 1)
    mdd = float(((1 + rp).cumprod() / (1 + rp).cumprod().cummax() - 1).min())
    vol = float(rp.std() * np.sqrt(ANN)); rb = rb.reindex(rp.index)
    annb = float((1 + rb).prod() ** (ANN / m) - 1) if m > 20 else float((1 + rb).prod() - 1)
    beta = float(rp.cov(rb) / rb.var()) if rb.var() > 0 else float("nan")
    return {"ann_return": round(ann, 4), "excess_vs_topix": round(ann - annb, 4),
            "volatility": round(vol, 4), "sharpe": round(ann / vol, 3) if vol else None,
            "max_drawdown": round(mdd, 4), "beta": round(beta, 3)}

PERIODS = {"full": ("2021-06-01", "2026-06-01"), "P1_利上21-22": ("2021-06-01", "2022-12-31"),
           "P2_AI前半23-24": ("2023-01-01", "2024-06-30"), "P3_直近24-26": ("2024-07-01", "2026-06-01")}
w_ours = a.set_index("ticker")["target_weight_final"].to_dict()
baskets = {"buf12": w_buf12, "old_ours": w_ours,
           "hybrid_equal": w_equal, "hybrid_rolebudget": w_rb, "hybrid_minvar": w_mv}
results = {}
for p, (d0, d1) in PERIODS.items():
    rb = wide.loc[d0:d1, "1306.T"].pct_change(fill_method=None).dropna()
    results[p] = {"topix": stats(rb, rb)}
    for b, w in baskets.items():
        rp, nu, nt = bh(w, d0, d1); rp = rp.reindex(rb.index).dropna()
        results[p][b] = {**stats(rp, rb), "coverage": f"{nu}/{nt}"}

# ---------------- cumulative chart (full window) ----------------
d0, d1 = PERIODS["full"]
lines = {}
for tag, cs in sleeves.items():
    w = {c + ".T": 1 / len(cs) for c in cs}
    rp, _, _ = bh(w, d0, d1); lines[tag] = (1 + rp).cumprod()
rp_h, _, _ = bh(w_equal, d0, d1); lines["ハイブリッド20(均等)"] = (1 + rp_h).cumprod()
rp_b, _, _ = bh(w_buf12, d0, d1); lines["真バフェットTop12"] = (1 + rp_b).cumprod()
rb = wide.loc[d0:d1, "1306.T"].pct_change(fill_method=None).dropna(); lines["TOPIX"] = (1 + rb).cumprod()

fig, ax = plt.subplots(figsize=(10, 6))
styles = {"ハイブリッド20(均等)": dict(color="#c0392b", lw=3.0, zorder=10),
          "守(真Buffett)": dict(color="#2c3e50", lw=1.6, ls="-"),
          "破(Transformation)": dict(color="#16a085", lw=1.6, ls="-"),
          "離(FutureMoat)": dict(color="#8e44ad", lw=1.6, ls="-"),
          "真バフェットTop12": dict(color="#e67e22", lw=2.0, ls="--"),
          "TOPIX": dict(color="#7f8c8d", lw=1.8, ls=":")}
for k in ["ハイブリッド20(均等)", "真バフェットTop12", "守(真Buffett)", "離(FutureMoat)", "破(Transformation)", "TOPIX"]:
    v = lines[k].reindex(lines["TOPIX"].index).ffill()
    ax.plot(v.index, v.values, label=f"{k} (×{v.iloc[-1]:.2f})", **styles[k])
ax.set_title("守破離ハイブリッド vs 真バフェット vs TOPIX  累積リターン(2021-06〜2026-06)\n※in-sample自己検証:2026-06選定を過去適用。成績予測ではない", fontsize=11)
ax.set_ylabel("累積(初期=1.0)"); ax.legend(fontsize=9, loc="upper left"); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(WORK / "cumulative_shuhari.png", dpi=150); plt.close(fig)

# ---------------- outputs ----------------
json.dump({"shu5": shu5, "ha7": ha7, "ri8": ri8, "buf12": buf12,
           "weights": {"equal": w_equal, "role_budget": w_rb, "min_var": w_mv},
           "results": results,
           "note": "hybrid v2: 破/離 freshly re-selected from study category×adjusted_bb_score(黒字ガード). in-sample. phase5-consistent."},
          open(WORK / "hybrid_v2_results.json", "w"), ensure_ascii=False, indent=2)

lab = {"topix": "TOPIX", "buf12": "真バフェットTop12(目標)", "old_ours": "旧ours",
       "hybrid_equal": "★hybrid 均等", "hybrid_rolebudget": "★hybrid 役割予算", "hybrid_minvar": "★hybrid 最小分散"}
for p in PERIODS:
    print(f"\n===== {p} =====")
    print(f'{"":26}{"年率":>7}{"対TOPIX":>9}{"σ":>7}{"MDD":>8}{"β":>6}{"Sharpe":>8}')
    for k in ["topix", "buf12", "old_ours", "hybrid_equal", "hybrid_rolebudget", "hybrid_minvar"]:
        st = results[p][k]
        if st["ann_return"] is None: print(f'{lab[k]:26} (n不足)'); continue
        exc = f'{st["excess_vs_topix"]*100:+6.1f}pt' if k != "topix" else "   ---  "
        print(f'{lab[k]:26}{st["ann_return"]*100:6.1f}%{exc:>9}{st["volatility"]*100:6.1f}%{st["max_drawdown"]*100:7.1f}%{st["beta"]:6.2f}{(st["sharpe"] if st["sharpe"] else float("nan")):8.2f}')
print("\n最小分散の上位重み:", sorted([(round(v,3),k) for k,v in w_mv.items()], reverse=True)[:6])
print("chart ->", WORK / "cumulative_shuhari.png")
print("json  ->", WORK / "hybrid_v2_results.json")
