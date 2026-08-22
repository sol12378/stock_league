from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
PRICE_FILE = PROJECT_ROOT / "data/processed/prices_daily.parquet"
FINANCIAL_FILE = (
    PROJECT_ROOT
    / "outputs/phase2_top1200_walkforward_perfect_fix/data_panel/historical_point_in_time_panel.csv"
)
OUT = ROOT / "outputs/supervised_double_model_20260630"
REMOTE_PRICE_FILE = OUT / "yfinance_prices_actions_20220601_20260701.parquet"
SNAPSHOT_YEARS = (2023, 2024, 2025)
NUMERIC_FEATURES = [
    "log_market_cap",
    "book_to_market",
    "earnings_yield",
    "sales_yield",
    "ocf_yield",
    "gross_profitability",
    "operating_margin",
    "net_margin",
    "roa",
    "roe",
    "current_ratio",
    "leverage",
    "asset_turnover",
    "sloan_accruals",
    "revenue_growth",
    "operating_income_growth",
    "net_income_growth",
    "asset_growth",
    "equity_growth",
    "operating_cf_growth",
    "share_growth",
    "piotroski_f_score_ratio",
    "mom_21d",
    "mom_63d",
    "mom_126d",
    "mom_252d",
    "volatility_63d",
    "volatility_252d",
    "max_drawdown_252d",
    "distance_52w_high",
    "log_adv60",
    "turnover_value_proxy",
    "amihud_63d",
    "report_age_days",
    "price_history_days",
]
CATEGORICAL_FEATURES = ["market", "sector_17", "is_financial"]


def _download_chunk(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=False,
        actions=True,
        progress=False,
        threads=True,
        group_by="column",
        timeout=30,
    )
    if raw.empty:
        return pd.DataFrame()
    parts = []
    if isinstance(raw.columns, pd.MultiIndex):
        for field, output_name in [
            ("Close", "close"),
            ("Adj Close", "adj_close"),
            ("Volume", "volume"),
            ("Stock Splits", "stock_splits"),
        ]:
            if field not in raw.columns.get_level_values(0):
                continue
            block = raw[field].copy()
            if isinstance(block, pd.Series):
                block = block.to_frame(name=tickers[0])
            long = block.stack(future_stack=True).rename(output_name).reset_index()
            long.columns = ["date", "ticker", output_name]
            parts.append(long)
    else:
        one = tickers[0]
        frame = raw.reset_index().rename(
            columns={
                "Date": "date", "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
                "Stock Splits": "stock_splits",
            }
        )
        frame["ticker"] = one
        if "stock_splits" not in frame:
            frame["stock_splits"] = 0.0
        return frame[["date", "ticker", "close", "adj_close", "volume", "stock_splits"]]
    if not parts:
        return pd.DataFrame()
    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on=["date", "ticker"], how="outer")
    return out.dropna(subset=["close", "adj_close"], how="all")


def download_remote_prices(tickers: list[str], force: bool = False) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    if REMOTE_PRICE_FILE.exists() and not force:
        return pd.read_parquet(REMOTE_PRICE_FILE)
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    chunk_size = 80
    for start_idx in range(0, len(tickers), chunk_size):
        chunk = tickers[start_idx : start_idx + chunk_size]
        frame = pd.DataFrame()
        for attempt in range(3):
            try:
                frame = _download_chunk(chunk, "2022-06-01", "2026-07-02")
                if not frame.empty:
                    break
            except Exception as exc:  # noqa: BLE001
                print(f"download retry {attempt + 1}: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(1.5 * (attempt + 1))
        if frame.empty:
            failures.extend(chunk)
        else:
            frames.append(frame)
            observed = set(frame["ticker"].astype(str).unique())
            failures.extend([ticker for ticker in chunk if ticker not in observed])
        print(f"downloaded {min(start_idx + chunk_size, len(tickers))}/{len(tickers)}", flush=True)
        time.sleep(0.25)
    remote = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not remote.empty:
        remote["date"] = pd.to_datetime(remote["date"]).dt.tz_localize(None)
        remote = remote.drop_duplicates(["date", "ticker"], keep="last").sort_values(["ticker", "date"])
        remote.to_parquet(REMOTE_PRICE_FILE, index=False)
    (OUT / "yfinance_download_audit.json").write_text(
        json.dumps(
            {
                "requested_tickers": len(tickers),
                "downloaded_tickers": int(remote["ticker"].nunique()) if not remote.empty else 0,
                "rows": len(remote),
                "min_date": str(remote["date"].min()) if not remote.empty else None,
                "max_date": str(remote["date"].max()) if not remote.empty else None,
                "failed_tickers": sorted(set(failures)),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return remote


def load_price_data(download: bool, force: bool) -> tuple[pd.DataFrame, dict[str, object]]:
    local = pd.read_parquet(PRICE_FILE, columns=["date", "ticker", "close", "adj_close", "volume"])
    local["date"] = pd.to_datetime(local["date"]).dt.tz_localize(None)
    local["ticker"] = local["ticker"].astype(str)
    local["stock_splits"] = 0.0
    remote = pd.DataFrame()
    if download:
        remote = download_remote_prices(sorted(local["ticker"].unique()), force=force)
    elif REMOTE_PRICE_FILE.exists():
        remote = pd.read_parquet(REMOTE_PRICE_FILE)
        remote["date"] = pd.to_datetime(remote["date"]).dt.tz_localize(None)
    prices = local
    if not remote.empty:
        local_cut = local[local["date"] < pd.Timestamp("2022-06-01")].copy()
        # The local archive was frozen on 2026-06-01. Align its earlier adjusted
        # prices to the newer extraction for any splits occurring afterwards.
        later_splits = remote[
            (remote["date"] > pd.Timestamp("2026-06-01"))
            & remote["stock_splits"].fillna(0).ne(0)
        ].groupby("ticker")["stock_splits"].prod()
        if not later_splits.empty:
            factors = local_cut["ticker"].map(later_splits).fillna(1.0)
            local_cut["close"] = local_cut["close"] / factors
            local_cut["adj_close"] = local_cut["adj_close"] / factors
            local_cut["volume"] = local_cut["volume"] * factors
        # A single current Yahoo extraction is used from 2022-06 onward so that
        # later splits are reflected consistently in both the 2025 entry price
        # and its 2026 outcome path.
        prices = pd.concat(
            [local_cut, remote],
            ignore_index=True,
        )
    prices = prices.drop_duplicates(["date", "ticker"], keep="last")
    prices = prices.sort_values(["ticker", "date"]).reset_index(drop=True)
    audit = {
        "local_rows": len(local),
        "local_min_date": str(local["date"].min().date()),
        "local_max_date": str(local["date"].max().date()),
        "remote_rows": len(remote),
        "remote_tickers": int(remote["ticker"].nunique()) if not remote.empty else 0,
        "combined_rows": len(prices),
        "combined_min_date": str(prices["date"].min().date()),
        "combined_max_date": str(prices["date"].max().date()),
    }
    return prices, audit


def signed_growth(current: pd.Series, previous: pd.Series) -> pd.Series:
    scale = previous.abs().replace(0, np.nan)
    return ((current - previous) / scale).clip(-3, 5)


def prepare_financial_panel() -> pd.DataFrame:
    usecols = [
        "code", "ticker", "doc_id", "filer_name", "submit_date", "period_end", "revenue",
        "gross_profit", "operating_income", "net_income", "total_assets", "equity", "liabilities",
        "current_assets", "current_liabilities", "operating_cf", "shares_outstanding_pti", "company_name_ja",
        "market", "sector_17", "is_financial", "piotroski_f_score_ratio", "sloan_accruals",
    ]
    panel = pd.read_csv(FINANCIAL_FILE, usecols=usecols, dtype={"code": str, "ticker": str})
    panel["code"] = panel["code"].str.zfill(4)
    panel["submit_date"] = pd.to_datetime(panel["submit_date"], errors="coerce")
    panel["period_end"] = pd.to_datetime(panel["period_end"], errors="coerce")
    panel = panel.dropna(subset=["code", "ticker", "submit_date"]).sort_values(["code", "submit_date"])
    raw_cols = [
        "revenue", "operating_income", "net_income", "total_assets", "equity", "operating_cf",
        "shares_outstanding_pti",
    ]
    for col in raw_cols:
        panel[f"prev_{col}"] = panel.groupby("code")[col].shift(1)
    return panel


def price_features_asof(prices: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    pre = prices[(prices["date"] <= cutoff) & (prices["date"] >= cutoff - pd.Timedelta(days=520))]

    def one(group: pd.DataFrame) -> pd.Series:
        group = group.sort_values("date").dropna(subset=["adj_close"])
        adj = group["adj_close"].astype(float).to_numpy()
        close = group["close"].astype(float).to_numpy()
        volume = group["volume"].fillna(0).astype(float).to_numpy()
        dates = group["date"].to_numpy()
        if len(adj) == 0:
            return pd.Series(dtype=float)
        returns = pd.Series(adj).pct_change().replace([np.inf, -np.inf], np.nan)

        def momentum(days: int) -> float:
            return adj[-1] / adj[-days - 1] - 1 if len(adj) > days and adj[-days - 1] > 0 else np.nan

        last252 = adj[-252:]
        running_max = np.maximum.accumulate(last252)
        drawdowns = last252 / running_max - 1
        traded = close * volume
        r63 = returns.tail(63).to_numpy()
        value63 = traded[-63:]
        valid = np.isfinite(r63) & np.isfinite(value63) & (value63 > 0)
        amihud = np.nan
        if valid.any():
            amihud = float(np.nanmean(np.abs(r63[valid]) / value63[valid]) * 1e9)
        return pd.Series(
            {
                "entry_date": pd.Timestamp(dates[-1]),
                "entry_close": close[-1],
                "entry_adj_close": adj[-1],
                "mom_21d": momentum(21),
                "mom_63d": momentum(63),
                "mom_126d": momentum(126),
                "mom_252d": momentum(252),
                "volatility_63d": returns.tail(63).std(ddof=1) * math.sqrt(252),
                "volatility_252d": returns.tail(252).std(ddof=1) * math.sqrt(252),
                "max_drawdown_252d": float(np.nanmin(drawdowns)) if len(drawdowns) else np.nan,
                "distance_52w_high": adj[-1] / np.nanmax(last252) - 1 if len(last252) else np.nan,
                "adv60": float(np.nanmean(traded[-60:])),
                "amihud_63d": amihud,
                "price_history_days": len(group),
            }
        )

    result = pre.groupby("ticker", sort=False).apply(one, include_groups=False).reset_index()
    return result


def outcome_labels(
    prices: pd.DataFrame,
    entries: pd.DataFrame,
    horizon_years: int,
    end_limit: pd.Timestamp | None = None,
) -> pd.DataFrame:
    price_groups = {ticker: g for ticker, g in prices.groupby("ticker", sort=False)}
    rows = []
    for row in entries[["ticker", "entry_date", "entry_adj_close"]].itertuples(index=False):
        group = price_groups.get(row.ticker)
        horizon_end = pd.Timestamp(row.entry_date) + pd.DateOffset(years=horizon_years)
        if end_limit is not None:
            horizon_end = min(horizon_end, end_limit)
        if group is None or not np.isfinite(row.entry_adj_close) or row.entry_adj_close <= 0:
            continue
        future = group[(group["date"] > row.entry_date) & (group["date"] <= horizon_end)].dropna(
            subset=["adj_close"]
        )
        if future.empty:
            continue
        multiples = future["adj_close"].astype(float) / float(row.entry_adj_close)
        hit_mask = multiples >= 2.0
        hit = bool(hit_mask.any())
        first_hit_date = future.loc[hit_mask, "date"].iloc[0] if hit else pd.NaT
        last_date = pd.Timestamp(future["date"].iloc[-1])
        expected_days = (horizon_end - pd.Timestamp(row.entry_date)).days
        observed_days = (last_date - pd.Timestamp(row.entry_date)).days
        complete = observed_days >= expected_days - 35
        # A positive hit remains known even if the security later delists.
        label_observed = complete or hit
        rows.append(
            {
                "ticker": row.ticker,
                f"hit_2x_{horizon_years}y": int(hit) if label_observed else np.nan,
                f"end_2x_{horizon_years}y": int(multiples.iloc[-1] >= 2.0) if complete else np.nan,
                f"forward_max_multiple_{horizon_years}y": float(multiples.max()),
                f"forward_end_return_{horizon_years}y": float(multiples.iloc[-1] - 1),
                f"outcome_end_date_{horizon_years}y": last_date,
                f"days_to_2x_{horizon_years}y": (
                    int((pd.Timestamp(first_hit_date) - pd.Timestamp(row.entry_date)).days) if hit else np.nan
                ),
                f"label_complete_{horizon_years}y": bool(label_observed),
            }
        )
    return pd.DataFrame(rows)


def build_snapshot(panel: pd.DataFrame, prices: pd.DataFrame, year: int) -> pd.DataFrame:
    cutoff = pd.Timestamp(f"{year}-06-30")
    latest = panel[panel["submit_date"] <= cutoff + pd.Timedelta(hours=23, minutes=59, seconds=59)]
    latest = latest.groupby("code", as_index=False).tail(1).copy()
    pfeat = price_features_asof(prices, cutoff)
    snap = latest.merge(pfeat, on="ticker", how="inner")
    snap["snapshot_year"] = year
    snap["cutoff_date"] = cutoff
    snap["report_age_days"] = (cutoff - snap["submit_date"].dt.normalize()).dt.days
    split_events = prices[
        prices.get("stock_splits", pd.Series(index=prices.index, dtype=float)).fillna(0).ne(0)
    ][["ticker", "date", "stock_splits"]]
    split_map = {
        ticker: list(zip(group["date"], group["stock_splits"].astype(float)))
        for ticker, group in split_events.groupby("ticker", sort=False)
    }

    def future_split_factor(row: pd.Series) -> float:
        reference_date = row["period_end"] if pd.notna(row["period_end"]) else row["submit_date"]
        factors = [
            factor for event_date, factor in split_map.get(row["ticker"], [])
            if pd.Timestamp(event_date) > pd.Timestamp(reference_date) and factor > 0
        ]
        return float(np.prod(factors)) if factors else 1.0

    snap["split_adjustment_factor"] = snap.apply(future_split_factor, axis=1)
    snap["shares_outstanding_split_adjusted"] = (
        snap["shares_outstanding_pti"] * snap["split_adjustment_factor"]
    )
    snap["market_cap"] = snap["entry_close"] * snap["shares_outstanding_split_adjusted"]
    snap["log_market_cap"] = np.log(snap["market_cap"].where(snap["market_cap"] > 0))
    snap["book_to_market"] = snap["equity"] / snap["market_cap"]
    snap["earnings_yield"] = snap["net_income"] / snap["market_cap"]
    snap["sales_yield"] = snap["revenue"] / snap["market_cap"]
    snap["ocf_yield"] = snap["operating_cf"] / snap["market_cap"]
    snap["gross_profitability"] = snap["gross_profit"] / snap["total_assets"]
    snap["operating_margin"] = snap["operating_income"] / snap["revenue"]
    snap["net_margin"] = snap["net_income"] / snap["revenue"]
    snap["roa"] = snap["net_income"] / snap["total_assets"]
    snap["roe"] = snap["net_income"] / snap["equity"]
    snap["current_ratio"] = snap["current_assets"] / snap["current_liabilities"]
    snap["leverage"] = snap["liabilities"] / snap["total_assets"]
    snap["asset_turnover"] = snap["revenue"] / snap["total_assets"]
    snap["revenue_growth"] = signed_growth(snap["revenue"], snap["prev_revenue"])
    snap["operating_income_growth"] = signed_growth(
        snap["operating_income"], snap["prev_operating_income"]
    )
    snap["net_income_growth"] = signed_growth(snap["net_income"], snap["prev_net_income"])
    snap["asset_growth"] = signed_growth(snap["total_assets"], snap["prev_total_assets"])
    snap["equity_growth"] = signed_growth(snap["equity"], snap["prev_equity"])
    snap["operating_cf_growth"] = signed_growth(snap["operating_cf"], snap["prev_operating_cf"])
    snap["share_growth"] = signed_growth(
        snap["shares_outstanding_pti"], snap["prev_shares_outstanding_pti"]
    )
    snap["log_adv60"] = np.log(snap["adv60"].where(snap["adv60"] > 0))
    snap["turnover_value_proxy"] = snap["adv60"] / snap["market_cap"]
    snap["is_financial"] = snap["is_financial"].fillna(False).astype(str)
    snap["market"] = snap["market"].fillna("Unknown").astype(str)
    snap["sector_17"] = snap["sector_17"].fillna("Unknown").astype(str)
    snap = snap[
        (snap["entry_date"] >= cutoff - pd.Timedelta(days=10))
        & (snap["report_age_days"].between(0, 550))
        & (snap["entry_close"] >= 100)
        & (snap["market_cap"] >= 1e9)
        & (snap["adv60"] >= 5e6)
    ].copy()
    labels1 = outcome_labels(prices, snap, 1)
    snap = snap.merge(labels1, on="ticker", how="left")
    available_horizon = 2026 - year
    if available_horizon >= 2:
        labels_long = outcome_labels(
            prices,
            snap,
            available_horizon,
            end_limit=pd.Timestamp("2026-06-30"),
        )
        snap = snap.merge(labels_long, on="ticker", how="left")
    return snap


def metric_row(y: pd.Series, prob: np.ndarray, cohort: str, model: str) -> dict[str, float | str]:
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    y = pd.Series(y).astype(int).reset_index(drop=True)
    prob = np.asarray(prob)
    result: dict[str, float | str] = {
        "cohort": cohort,
        "model": model,
        "n": len(y),
        "positives": int(y.sum()),
        "base_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, prob)) if y.nunique() > 1 else np.nan,
        "average_precision": float(average_precision_score(y, prob)) if y.nunique() > 1 else np.nan,
        "brier_score": float(brier_score_loss(y, prob)),
    }
    order = np.argsort(-prob)
    for frac in (0.01, 0.05, 0.10):
        n_top = max(10, math.ceil(len(y) * frac))
        precision = float(y.iloc[order[:n_top]].mean())
        result[f"precision_top_{int(frac * 100)}pct"] = precision
        result[f"lift_top_{int(frac * 100)}pct"] = precision / y.mean() if y.mean() else np.nan
    return result


def build_models(
    panel: pd.DataFrame, target: str, probability_column: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, object, list[str]]:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    eligible = panel[panel[target].notna()].copy()
    train23 = eligible[eligible["snapshot_year"] == 2023]
    valid24 = eligible[eligible["snapshot_year"] == 2024]
    test25 = eligible[eligible["snapshot_year"] == 2025]
    # Only features with observations in the earliest training cohort are
    # eligible. This prevents later-cohort coverage improvements from entering
    # the final model without having been validated out of time.
    active_numeric = [feature for feature in NUMERIC_FEATURES if train23[feature].notna().any()]
    features = active_numeric + CATEGORICAL_FEATURES
    preprocessor = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                active_numeric,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    candidates: list[tuple[str, object]] = []
    for c_value in (0.03, 0.1, 0.3, 1.0):
        candidates.append(
            (
                f"logistic_C{c_value}",
                Pipeline(
                    [
                        ("prep", preprocessor),
                        (
                            "model",
                            LogisticRegression(
                                C=c_value,
                                class_weight="balanced",
                                max_iter=3000,
                                solver="liblinear",
                                random_state=42,
                            ),
                        ),
                    ]
                ),
            )
        )
    # Numeric-only nonlinear alternative. Hyperparameters are selected solely
    # on the 2024 cohort; the 2025 labels remain untouched until final testing.
    numeric_pre = Pipeline(
        [("impute", SimpleImputer(strategy="median", add_indicator=True))]
    )
    for leaves, rate, l2 in ((7, 0.04, 3.0), (15, 0.04, 5.0), (15, 0.08, 5.0)):
        candidates.append(
            (
                f"histgb_l{leaves}_r{rate}_l2{l2}",
                Pipeline(
                    [
                        ("prep", numeric_pre),
                        (
                            "model",
                            HistGradientBoostingClassifier(
                                max_iter=220,
                                learning_rate=rate,
                                max_leaf_nodes=leaves,
                                min_samples_leaf=30,
                                l2_regularization=l2,
                                class_weight="balanced",
                                random_state=42,
                            ),
                        ),
                    ]
                ),
            )
        )
    validation_rows = []
    fitted_candidates: list[tuple[str, object, dict[str, object]]] = []
    for name, model in candidates:
        cols = features if name.startswith("logistic") else active_numeric
        model.fit(train23[cols], train23[target].astype(int))
        prob = model.predict_proba(valid24[cols])[:, 1]
        metrics = metric_row(valid24[target], prob, "2024_validation", name)
        validation_rows.append(metrics)
        fitted_candidates.append((name, model, metrics))
    winner_name, _, _ = max(
        fitted_candidates,
        key=lambda item: (item[2]["average_precision"], item[2]["roc_auc"]),
    )
    winner_template = dict(candidates)[winner_name]
    winner_cols = features if winner_name.startswith("logistic") else active_numeric
    train = eligible[eligible["snapshot_year"].isin([2023, 2024])]
    winner_template.fit(train[winner_cols], train[target].astype(int))
    test_prob = winner_template.predict_proba(test25[winner_cols])[:, 1]
    test_metrics = metric_row(test25[target], test_prob, "2025_holdout", winner_name)
    metrics_df = pd.DataFrame(validation_rows + [test_metrics])
    predictions = test25[
        [
            "snapshot_year", "code", "ticker", "company_name_ja", "market", "sector_17",
            "entry_date", "entry_close", "market_cap", "hit_2x_1y", "end_2x_1y",
            "forward_max_multiple_1y", "forward_end_return_1y", "days_to_2x_1y",
        ]
    ].copy()
    predictions[probability_column] = test_prob
    predictions = predictions.sort_values(probability_column, ascending=False)
    metrics_df.insert(0, "target", target)
    return metrics_df, predictions, eligible, winner_template, winner_cols


def feature_effects(train: pd.DataFrame, target: str) -> pd.DataFrame:
    rows = []
    base = train[target].mean()
    for feature in NUMERIC_FEATURES:
        data = train[[feature, target]].dropna()
        if len(data) < 100 or data[feature].nunique() < 10:
            continue
        try:
            buckets = pd.qcut(data[feature], 5, duplicates="drop")
        except ValueError:
            continue
        grouped = data.assign(bucket=buckets).groupby("bucket", observed=True).agg(
            n=(target, "size"), positives=(target, "sum"), hit_rate=(target, "mean"),
            feature_median=(feature, "median")
        )
        if grouped.empty:
            continue
        best = grouped.sort_values(["hit_rate", "n"], ascending=False).iloc[0]
        rows.append(
            {
                "feature": feature,
                "base_rate": base,
                "best_bucket": str(grouped["hit_rate"].idxmax()),
                "best_bucket_n": int(best["n"]),
                "best_bucket_positives": int(best["positives"]),
                "best_bucket_hit_rate": float(best["hit_rate"]),
                "best_bucket_lift": float(best["hit_rate"] / base) if base else np.nan,
                "best_bucket_feature_median": float(best["feature_median"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["best_bucket_lift", "best_bucket_n"], ascending=False)


def exploratory_three_year_model(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    source = panel[(panel["snapshot_year"] == 2023) & panel["end_2x_3y"].notna()].copy()
    current = panel[panel["snapshot_year"] == 2025].copy()
    active_numeric = [feature for feature in NUMERIC_FEATURES if source[feature].notna().any()]
    model = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=0.05,
                    class_weight="balanced",
                    max_iter=3000,
                    solver="liblinear",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(source[active_numeric], source["end_2x_3y"].astype(int))
    prob = model.predict_proba(current[active_numeric])[:, 1]
    candidates = current[
        ["code", "ticker", "company_name_ja", "market", "sector_17", "entry_date", "entry_close", "market_cap"]
    ].copy()
    candidates["exploratory_probability_3y_2x"] = prob
    candidates = candidates.sort_values("exploratory_probability_3y_2x", ascending=False)
    fitted = model.predict_proba(source[active_numeric])[:, 1]
    diagnostics = metric_row(source["end_2x_3y"], fitted, "2023_in_sample_3y", "exploratory_logistic")
    effects = feature_effects(source, "end_2x_3y")
    return candidates, effects, diagnostics


def price_only_horizon_summary(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    summaries = []
    for year in (2021, 2022, 2023, 2024, 2025):
        cutoff = pd.Timestamp(f"{year}-06-30")
        horizon = 2026 - year
        entries = price_features_asof(prices, cutoff)
        entries = entries[
            (entries["entry_date"] >= cutoff - pd.Timedelta(days=10))
            & (entries["entry_close"] >= 100)
            & (entries["adv60"] >= 5e6)
        ].copy()
        labels = outcome_labels(prices, entries, horizon, end_limit=pd.Timestamp("2026-06-30"))
        cohort = entries[["ticker", "entry_date", "entry_close", "entry_adj_close"]].merge(
            labels, on="ticker", how="left"
        )
        cohort["snapshot_year"] = year
        cohort["available_horizon_years"] = horizon
        label = f"hit_2x_{horizon}y"
        observed = cohort[cohort[label].notna()]
        summaries.append(
            {
                "snapshot_year": year,
                "available_horizon_years": horizon,
                "eligible": len(observed),
                "doublers": int(observed[label].sum()),
                "doubling_rate": float(observed[label].mean()),
                "endpoint_doublers": int(observed[f"end_2x_{horizon}y"].fillna(0).sum()),
                "endpoint_doubling_rate": float(observed[f"end_2x_{horizon}y"].mean()),
                "median_max_multiple": float(observed[f"forward_max_multiple_{horizon}y"].median()),
                "median_end_return": float(observed[f"forward_end_return_{horizon}y"].median()),
            }
        )
        rows.append(cohort)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(summaries)


def write_post_analysis(
    panel: pd.DataFrame,
    predictions_hit: pd.DataFrame,
    predictions_end: pd.DataFrame,
    candidates3: pd.DataFrame,
) -> None:
    test = panel[(panel["snapshot_year"] == 2025) & panel["end_2x_1y"].notna()].copy()
    sector = test.groupby("sector_17").agg(
        n=("end_2x_1y", "size"),
        hit_2x_rate=("hit_2x_1y", "mean"),
        endpoint_2x_rate=("end_2x_1y", "mean"),
        average_end_return=("forward_end_return_1y", "mean"),
        median_end_return=("forward_end_return_1y", "median"),
    ).sort_values("endpoint_2x_rate", ascending=False)
    sector.to_csv(OUT / "sector_outcomes_2025.csv")

    rank_rows = []
    for label, frame in [("hit_model", predictions_hit), ("endpoint_model", predictions_end)]:
        for fraction in (0.01, 0.05, 0.10):
            n_top = max(10, math.ceil(len(frame) * fraction))
            selected = frame.head(n_top)
            rank_rows.append(
                {
                    "model": label,
                    "top_fraction": fraction,
                    "n": n_top,
                    "average_end_return": selected["forward_end_return_1y"].mean(),
                    "median_end_return": selected["forward_end_return_1y"].median(),
                    "hit_2x_rate": selected["hit_2x_1y"].mean(),
                    "endpoint_2x_rate": selected["end_2x_1y"].mean(),
                }
            )
    pd.DataFrame(rank_rows).to_csv(OUT / "model_rank_bucket_performance.csv", index=False)

    diff_rows = []
    for feature in NUMERIC_FEATURES:
        winners = test.loc[test["end_2x_1y"] == 1, feature].dropna()
        others = test.loc[test["end_2x_1y"] == 0, feature].dropna()
        all_values = test[feature].dropna()
        if winners.empty or others.empty:
            continue
        iqr = all_values.quantile(0.75) - all_values.quantile(0.25)
        diff_rows.append(
            {
                "feature": feature,
                "winner_median": winners.median(),
                "other_median": others.median(),
                "median_difference_in_iqr": (
                    (winners.median() - others.median()) / iqr if iqr else np.nan
                ),
                "winner_observations": len(winners),
            }
        )
    pd.DataFrame(diff_rows).sort_values(
        "median_difference_in_iqr", key=lambda s: s.abs(), ascending=False
    ).to_csv(OUT / "realized_endpoint_doubler_factors_2025.csv", index=False)

    interim = candidates3.merge(
        test[
            [
                "code", "hit_2x_1y", "end_2x_1y", "forward_end_return_1y",
                "forward_max_multiple_1y", "is_financial",
            ]
        ],
        on="code",
        how="left",
    )
    interim.to_csv(OUT / "three_year_exploratory_interim_2025_to_2026.csv", index=False)
    interim_rows = []
    for n_top in (32, 50, 100, 316):
        selected = interim.head(n_top)
        interim_rows.append(
            {
                "top_n": n_top,
                "average_1y_return": selected["forward_end_return_1y"].mean(),
                "median_1y_return": selected["forward_end_return_1y"].median(),
                "hit_2x_1y_rate": selected["hit_2x_1y"].mean(),
                "endpoint_2x_1y_rate": selected["end_2x_1y"].mean(),
                "financial_sector_share": selected["is_financial"].astype(str).eq("True").mean(),
            }
        )
    pd.DataFrame(interim_rows).to_csv(OUT / "three_year_exploratory_interim_summary.csv", index=False)

    realized = test[test["hit_2x_1y"] == 1].sort_values("forward_end_return_1y", ascending=False)
    realized[
        [
            "code", "ticker", "company_name_ja", "market", "sector_17", "entry_date", "entry_close",
            "market_cap", "hit_2x_1y", "end_2x_1y", "forward_max_multiple_1y",
            "forward_end_return_1y", "days_to_2x_1y",
        ]
    ].to_csv(OUT / "realized_doublers_2025_to_2026.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-test-prices", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prices, price_audit = load_price_data(args.download_test_prices, args.force_download)
    financial = prepare_financial_panel()
    snapshots = []
    for year in SNAPSHOT_YEARS:
        print(f"building snapshot {year}", flush=True)
        snapshots.append(build_snapshot(financial, prices, year))
    panel = pd.concat(snapshots, ignore_index=True)
    panel.to_csv(OUT / "market_snapshot_panel.csv", index=False)
    metrics_hit, predictions_hit, eligible_hit, _model_hit, model_cols_hit = build_models(
        panel, "hit_2x_1y", "predicted_probability_1y_hit_2x"
    )
    metrics_end, predictions_end, eligible_end, _model_end, model_cols_end = build_models(
        panel, "end_2x_1y", "predicted_probability_1y_end_2x"
    )
    metrics = pd.concat([metrics_hit, metrics_end], ignore_index=True)
    metrics.to_csv(OUT / "model_metrics.csv", index=False)
    predictions_hit.to_csv(OUT / "test_2025_predictions_hit_2x.csv", index=False)
    predictions_end.to_csv(OUT / "test_2025_predictions_end_2x.csv", index=False)
    effects1_hit = feature_effects(
        eligible_hit[eligible_hit["snapshot_year"].isin([2023, 2024])], "hit_2x_1y"
    )
    effects1_end = feature_effects(
        eligible_end[eligible_end["snapshot_year"].isin([2023, 2024])], "end_2x_1y"
    )
    effects1_hit.to_csv(OUT / "feature_effects_1y_hit.csv", index=False)
    effects1_end.to_csv(OUT / "feature_effects_1y_end.csv", index=False)
    candidates3, effects3, diagnostics3 = exploratory_three_year_model(panel)
    candidates3.to_csv(OUT / "candidates_3y_exploratory.csv", index=False)
    effects3.to_csv(OUT / "feature_effects_3y_exploratory.csv", index=False)
    price_cohorts, horizon_summary = price_only_horizon_summary(prices)
    price_cohorts.to_csv(OUT / "price_only_horizon_cohorts.csv", index=False)
    horizon_summary.to_csv(OUT / "price_only_horizon_summary.csv", index=False)
    write_post_analysis(panel, predictions_hit, predictions_end, candidates3)
    winner_names = metrics[metrics["cohort"] == "2025_holdout"].set_index("target")["model"].to_dict()
    audit = {
        "cutoffs": {
            "train": ["2023-06-30", "2024-06-30"],
            "validation": "train 2023 / validate 2024",
            "test_features": "2025-06-30",
            "test_label_end": "2026-06-30",
        },
        "price_data": price_audit,
        "financial_file": str(FINANCIAL_FILE),
        "financial_max_submit_used_by_snapshot": {
            str(year): str(panel.loc[panel["snapshot_year"] == year, "submit_date"].max())
            for year in SNAPSHOT_YEARS
        },
        "snapshot_rows": panel.groupby("snapshot_year").size().astype(int).to_dict(),
        "label_rows": panel.groupby("snapshot_year")["hit_2x_1y"].count().astype(int).to_dict(),
        "winner_models": winner_names,
        "feature_columns_hit": model_cols_hit,
        "feature_columns_end": model_cols_end,
        "three_year_model_status": "exploratory in-sample only; one mature financial cohort",
        "four_five_year_status": "price-only descriptive; point-in-time financial filings unavailable for robust supervised validation",
        "known_biases": [
            "Local historical price master may omit securities delisted before collection (survivorship bias).",
            "EDINET archive has almost no 2022 filings, so later filings are not backfilled into 2022 features.",
            "One-year doubling is rare; PR-AUC and top-decile lift are primary, ROC-AUC is secondary.",
            "Corporate actions are handled with adjusted close from one Yahoo extraction for the 2025 test window.",
        ],
    }
    audit["three_year_diagnostics"] = diagnostics3
    (OUT / "leakage_and_model_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(metrics.to_string(index=False), flush=True)
    print(horizon_summary.to_string(index=False), flush=True)
    print(predictions_hit.head(20).to_string(index=False), flush=True)
    print(predictions_end.head(20).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
