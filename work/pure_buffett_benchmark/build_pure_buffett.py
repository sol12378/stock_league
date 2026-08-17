# -*- coding: utf-8 -*-
"""真バフェット・ベンチマーク(本物のクオリティ・バリュー)の事前定義的構築と比較。

設計思想(査読防御):
 - 「勝つように逆算」しない。バフェット基準を文献で事前定義 → バックテスト → 出た数字をそのまま報告。
 - 現行対照群(=Grahamの深バリュー screen)と同一ユニバース(investment_eligible & 非金融 & 価格あり)
   から選び、差は「選定ルール」だけにする。
 - 計測規約は phase5_validation.py / make_control_comparison.py と完全一致
   (756/252営業日、1306.T×10補正、pct_change(fill_method=None)、TOPIX=1306.T、日経=^N225)。
 - フレーミングは phase5 と同じ「in-sample のリスク特性であって成績予測ではない」。

真バフェット基準(事前定義, Buffett letters + Frazzini-Kabiller-Pedersen 2018 "Buffett's Alpha" /
Asness-Frazzini-Pedersen QMJ / Greenblatt Magic Formula):
  クオリティ関門(すべて必須):
   - 高収益     : ROE >= 15%
   - 堀/価格支配力: 営業利益率 >= 10%
   - 財務健全   : 自己資本比率 >= 50% (低負債)
   - 予測可能性 : 直近3期に営業赤字/純赤字/営業CF赤字が一度も無い
   - 現金創出   : 営業CF > 0
   - 非縮小     : 増収 かつ 増益 (revenue_growth>=0 & operating_income_growth>=0)
  適正価格(overpayしない): クオリティ通過銘柄を Greenblatt型(ROE順位 + 益回り順位)で並べる。
  集中とセクター規律: 同一セクター上限2社(対照群と同じ規律), 上位N社。
  重み: 時価総額加重(上限25%)を主系列(バークシャー型の集中を模す)。等金額を感応度に併記。
  保有: 買い持ち(fore ver, 株数固定)を主系列。日次リバランスを感応度に併記。
  レバレッジ: 無レバを主系列。1.6倍(Buffett's Alphaの実測レバ)を併記, 調達0.25%/年。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
WORK = ROOT / "work/pure_buffett_benchmark"
WORK.mkdir(parents=True, exist_ok=True)

ANN = 252
WINDOWS = {"3y": 756, "1y": 252}
SPLIT_FIXES = {"1306.T": (pd.Timestamp("2026-03-30"), 10.0)}
BORROW_RATE_ANN = 0.0025  # JPY短期調達 0.25%/年(2023-2026の政策金利上げを踏まえた保守値)

# ---------------------------------------------------------------- universe & screen
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)
s["ticker"] = s["code"] + ".T"


def truthy(df, col):
    return df[col].astype(str).str.lower().isin(["true", "1", "1.0"])


elig = s[truthy(s, "investment_eligible") & ~truthy(s, "is_financial") & truthy(s, "price_available")].copy()
for c in ["roe", "operating_margin", "equity_ratio", "operating_cf", "net_income", "equity",
          "revenue_growth", "operating_income_growth", "operating_loss_years_3y",
          "net_loss_years_3y", "negative_ocf_years_3y", "shares_outstanding", "beta"]:
    elig[c] = pd.to_numeric(elig[c], errors="coerce")

# 価格(最新)から時価総額・PBR・益回りを自前計算(yfinance依存を避ける)
px_all = pd.read_parquet(ROOT / "data/processed/prices_daily.parquet",
                         columns=["date", "ticker", "adj_close"])
last_px = px_all.sort_values("date").groupby("ticker")["adj_close"].last()
elig["price"] = elig["ticker"].map(last_px)
elig["mcap"] = elig["price"] * elig["shares_outstanding"]
elig["pbr"] = elig["mcap"] / elig["equity"]
elig["ey"] = elig["net_income"] / elig["mcap"]

quality = elig[
    (elig.roe >= 0.15) & (elig.operating_margin >= 0.10) & (elig.equity_ratio >= 0.50) &
    (elig.operating_loss_years_3y == 0) & (elig.net_loss_years_3y == 0) &
    (elig.negative_ocf_years_3y == 0) & (elig.operating_cf > 0) &
    (elig.revenue_growth >= 0) & (elig.operating_income_growth >= 0)
].copy()
print(f"[screen] eligible universe={len(elig)}  pass quality gates={len(quality)}")
priceable = quality.dropna(subset=["ey", "pbr", "mcap"])
priceable = priceable[priceable.ey > 0].copy()
print(f"[screen] with computable positive valuation={len(priceable)} "
      f"(時価総額データ被覆の制約 => 大型優良に限定. バフェット=大型優良と整合)")

# Greenblatt型ランク + 同一セクター上限2
priceable["r_q"] = priceable.roe.rank(ascending=False)
priceable["r_p"] = priceable.ey.rank(ascending=False)
priceable["mf"] = priceable.r_q + priceable.r_p
priceable = priceable.sort_values("mf")


def pick(df, n, sector_cap=2):
    cnt, picked = {}, []
    for _, r in df.iterrows():
        sec = r["sector_33"]
        if cnt.get(sec, 0) >= sector_cap:
            continue
        cnt[sec] = cnt.get(sec, 0) + 1
        picked.append(r["code"])
        if len(picked) == n:
            break
    return picked


# ---------------------------------------------------------------- price panel & returns
def load_panel(tickers):
    need = set(tickers) | {"1306.T", "^N225"}
    p = px_all[px_all["ticker"].isin(need)]
    wide = p.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
    for t, (d0, factor) in SPLIT_FIXES.items():
        if t in wide.columns:
            wide.loc[wide.index >= d0, t] = wide.loc[wide.index >= d0, t] * factor
    return wide


def detect_cliffs(wide, tickers):
    r = wide[tickers].pct_change(fill_method=None)
    cliffs = {}
    for t in tickers:
        bad = r[t][(r[t] < -0.5) | (r[t] > 1.0)]
        if len(bad):
            cliffs[t] = [(str(d.date()), round(float(v), 3)) for d, v in bad.items()]
    return cliffs


def series_stats(rp, rb, rn):
    def ann_ret(x):
        return float((1 + x).prod() ** (ANN / len(x)) - 1)

    def mdd(x):
        c = (1 + x).cumprod()
        return float((c / c.cummax() - 1).min())

    vol = float(rp.std() * np.sqrt(ANN))
    beta = float(rp.cov(rb) / rb.var())
    te = float((rp - rb).std() * np.sqrt(ANN))
    ir = float((rp - rb).mean() * ANN / te) if te > 0 else float("nan")
    ar = ann_ret(rp)
    return {
        "ann_return": round(ar, 4), "topix_ann_return": round(ann_ret(rb), 4),
        "nikkei_ann_return": round(ann_ret(rn), 4), "excess_vs_topix": round(ar - ann_ret(rb), 4),
        "volatility": round(vol, 4), "sharpe": round(ar / vol, 3) if vol else None,
        "max_drawdown": round(mdd(rp), 4), "topix_max_drawdown": round(mdd(rb), 4),
        "beta_vs_topix": round(beta, 3), "information_ratio": round(ir, 3),
    }


def port_returns(wide, weights, window, mode):
    """mode: 'rebal' (fixed-weight daily rebalanced) or 'bh' (buy-and-hold, fixed shares)."""
    w = pd.Series(weights)
    have = [t for t in w.index if t in wide.columns]
    sub = wide[have].tail(window)
    # 履歴不足銘柄を除外して正規化
    ok = [t for t in have if sub[t].notna().sum() >= window - 1]
    w = w[ok]
    w = w / w.sum()
    sub = wide[list(w.index)].tail(window)
    if mode == "rebal":
        r = sub.pct_change(fill_method=None)
        rp = (r[w.index] * w.values).sum(axis=1)
    else:  # buy-and-hold: value = sum shares_i * price_i, shares_i ∝ w_i / price_i(t0)
        p0 = sub.iloc[0]
        shares = w / p0
        val = (sub * shares).sum(axis=1)
        rp = val.pct_change(fill_method=None)
    return rp.dropna(), list(w.index)


def levered(rp, L=1.6, borrow_ann=BORROW_RATE_ANN):
    return L * rp - (L - 1) * (borrow_ann / ANN)


# ---------------------------------------------------------------- build & compare
# ours & Graham control weights (再現して整合確認)
alloc = pd.read_csv(OUT / "phase4_portfolio_allocation/allocation_final.csv")
alloc["ticker"] = alloc["code_n"].astype(str).str.zfill(4) + ".T"
w_ours = alloc.set_index("ticker")["target_weight_final"].to_dict()

pool = pd.read_csv(ROOT / "outputs/phase1_top5/phase1_top5_candidate_pool.csv")
pool["code"] = pool["code"].astype(str).str.zfill(4)
sc, gcodes = {}, []
for _, r in pool.iterrows():
    if sc.get(r["sector"], 0) >= 2:
        continue
    sc[r["sector"]] = sc.get(r["sector"], 0) + 1
    gcodes.append(r["code"])
    if len(gcodes) == 20:
        break
w_graham = {c + ".T": 1.0 / 20 for c in gcodes}

# Buffett primary: top12, 時価総額加重(上限25%)
buf_codes = pick(priceable, 12)
buf_df = priceable[priceable.code.isin(buf_codes)].copy()
mc = buf_df.set_index("code")["mcap"]
wcap = (mc / mc.sum()).clip(upper=0.25)
wcap = wcap / wcap.sum()
w_buffett_cap = {c + ".T": float(wcap[c]) for c in buf_codes}
w_buffett_eq = {c + ".T": 1.0 / len(buf_codes) for c in buf_codes}

all_names = set(w_ours) | set(w_graham) | set(w_buffett_cap)
wide = load_panel(all_names)
cliffs = detect_cliffs(wide, [t for t in (set(w_buffett_cap) | set(w_graham)) if t in wide.columns])
if cliffs:
    print("[warn] split-like cliffs detected (要確認):", json.dumps(cliffs, ensure_ascii=False))
else:
    print("[ok] no split-like cliffs among Buffett/Graham names")

rb_full = wide["1306.T"].pct_change(fill_method=None)
rn_full = wide["^N225"].pct_change(fill_method=None)

portfolios = {
    "ours_rebal": (w_ours, "rebal"),
    "graham_control_rebal": (w_graham, "rebal"),
    "buffett_capw_bh": (w_buffett_cap, "bh"),
    "buffett_capw_rebal": (w_buffett_cap, "rebal"),
    "buffett_eqw_bh": (w_buffett_eq, "bh"),
}

results = {}
for wname, win in WINDOWS.items():
    rb = rb_full.tail(win)
    rn = rn_full.tail(win)
    results[wname] = {}
    for pname, (w, mode) in portfolios.items():
        rp, used = port_returns(wide, w, win, mode)
        idx = rp.index
        st = series_stats(rp, rb.reindex(idx), rn.reindex(idx))
        st["n_names"] = len(used)
        results[wname][pname] = st
        if pname == "buffett_capw_bh":  # レバ版
            rl = levered(rp)
            results[wname]["buffett_capw_bh_1.6x"] = series_stats(rl, rb.reindex(idx), rn.reindex(idx))
            results[wname]["buffett_capw_bh_1.6x"]["n_names"] = len(used)

# ---------------------------------------------------------------- fundamental profile
def profile(codes, df):
    d = df[df.code.isin(codes)]
    return {"roe_median": round(float(d.roe.median()), 3),
            "opm_median": round(float(d.operating_margin.median()), 3),
            "equity_ratio_median": round(float(d.equity_ratio.median()), 3),
            "pbr_median": round(float(d.pbr.median()), 2) if d.pbr.notna().any() else None,
            "mcap_median_oku": round(float(d.mcap.median() / 1e8), 0) if d.mcap.notna().any() else None}


buf_members = [{"code": r.code, "name": r.company_name, "sector": r.sector_33,
                "roe": round(float(r.roe), 3), "opm": round(float(r.operating_margin), 3),
                "equity_ratio": round(float(r.equity_ratio), 3), "pbr": round(float(r.pbr), 2),
                "ey": round(float(r.ey), 3), "mcap_oku": round(float(r.mcap / 1e8), 0),
                "weight_cap": round(w_buffett_cap[r.code + ".T"], 4)}
               for _, r in buf_df.sort_values("mf").iterrows()]

out = {
    "framing": "in-sample のリスク特性. 成績予測ではない. バフェット基準は文献で事前定義し勝つよう逆算していない.",
    "method": {
        "universe": "investment_eligible & 非金融 & 価格あり (Graham対照群と同一)",
        "quality_gates": "ROE>=15%, 営業益率>=10%, 自己資本比率>=50%, 直近3期無赤字(営業/純/営業CF), 営業CF>0, 増収, 増益",
        "price_rank": "Greenblatt型(ROE順位+益回り順位). 時価総額は shares_outstanding×最新株価で自前算出",
        "selection": "同一セクター上限2, 上位12. 主系列=時価総額加重(上限25%)・買い持ち. 無レバ",
        "leverage_note": f"1.6x = Frazzini-Kabiller-Pedersen(2018)の実測レバ. 調達{BORROW_RATE_ANN*100:.2f}%/年",
        "measurement": "phase5_validation.pyと同一(756/252日, 1306.T×10補正, pct_change fill_method=None)",
        "valuation_coverage_caveat": f"時価総額算出可能は {len(priceable)}社(大型優良中心). バフェット=大型優良と整合だが開示する",
    },
    "results": results,
    "buffett_members_top12": buf_members,
    "graham_control_codes": gcodes,
    "profiles": {
        "buffett_top12": profile(buf_codes, priceable),
    },
    "cliffs": cliffs,
}
json.dump(out, open(WORK / "pure_buffett_results.json", "w"), ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- console summary
def row(label, st):
    return (f"  {label:28} 年率={st['ann_return']*100:6.1f}%  対TOPIX={st['excess_vs_topix']*100:+6.1f}pt "
            f"σ={st['volatility']*100:5.1f}%  MDD={st['max_drawdown']*100:6.1f}%  β={st['beta_vs_topix']:.2f} "
            f"IR={st['information_ratio']:+.2f}  n={st.get('n_names','-')}")

order = ["ours_rebal", "graham_control_rebal", "buffett_capw_bh", "buffett_capw_bh_1.6x",
         "buffett_capw_rebal", "buffett_eqw_bh"]
for wname in ["3y", "1y"]:
    tp = results[wname]["ours_rebal"]["topix_ann_return"] * 100
    nk = results[wname]["ours_rebal"]["nikkei_ann_return"] * 100
    print(f"\n===== {wname}  (TOPIX={tp:.1f}% / 日経={nk:.1f}%) =====")
    for k in order:
        if k in results[wname]:
            print(row(k, results[wname][k]))

print("\n真バフェット Top12 メンバー(Greenblatt順):")
for m in buf_members:
    print(f"  {m['code']} {m['name'][:24]:24} ROE={m['roe']*100:4.1f}% PBR={m['pbr']:4.1f} "
          f"{m['sector'][:12]:12} 時価総額={m['mcap_oku']:6.0f}億 w={m['weight_cap']*100:4.1f}%")
print(f"\nprofile Buffett12: {out['profiles']['buffett_top12']}")
print(f"\nwritten -> {WORK/'pure_buffett_results.json'}")
