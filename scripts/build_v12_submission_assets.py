from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.portfolio.allocate import cap_weights  # noqa: E402
from src.portfolio.metrics import cumulative_returns, performance_row  # noqa: E402
from src.utils.prices import repair_split_jumps  # noqa: E402

ASSET_DIR = ROOT / "submission_assets"
ZIP_PATH = ROOT / "submission_assets.zip"
NAVY = "#17365D"
BLUE = "#D9EAF7"
MID_BLUE = "#5B9BD5"
GREY = "#EEF2F6"
LINE = "#B8C2CC"
ORANGE = "#C55A11"
GREEN = "#70AD47"
RED = "#C00000"
JAPANESE_FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"

DIRS = {
    "screening": ASSET_DIR / "screening",
    "scores": ASSET_DIR / "scores",
    "final20": ASSET_DIR / "final20",
    "portfolio": ASSET_DIR / "portfolio",
    "backtest": ASSET_DIR / "backtest",
    "fig_bg": ASSET_DIR / "figures" / "background",
    "fig_analysis": ASSET_DIR / "figures" / "analysis",
    "finance": ASSET_DIR / "finance_handling",
    "snippets": ASSET_DIR / "report_snippets",
}

SCORE_COLUMNS = [
    "moat_score",
    "transformation_score",
    "future_moat_score",
    "valuation_score",
    "momentum_score",
    "risk_score",
    "adjusted_bb_score",
]

COMPONENT_COLUMNS = [
    "moat_component_profitability",
    "moat_component_cashflow",
    "moat_component_stability",
    "moat_component_competitive_position",
    "transformation_component_valuation_gap",
    "transformation_component_capital_efficiency",
    "transformation_component_shareholder_return",
    "transformation_component_reform_signal",
    "future_moat_component_ai_infrastructure",
    "future_moat_component_intangible_asset",
    "future_moat_component_automation",
    "future_moat_component_data",
    "future_moat_component_trust",
]

ROLE_ORDER = ["守る堀", "変わる堀", "生まれる堀", "分散・橋渡し枠"]
ROLE_COLORS = {
    "守る堀": NAVY,
    "変わる堀": ORANGE,
    "生まれる堀": MID_BLUE,
    "分散・橋渡し枠": GREEN,
}

CODE_BUSINESS_BASIS = {
    "9022": "東海道新幹線を中核とする鉄道インフラと不動産・関連サービス。",
    "9501": "首都圏の電力供給、送配電、発電を担う社会インフラ。",
    "7181": "郵政ネットワークを背景にした生命保険事業と資本政策。",
    "8473": "証券・銀行・保険を横断する総合金融プラットフォーム。",
    "9503": "関西圏の電力供給、原子力・火力・再エネを含む電源ポートフォリオ。",
    "8309": "信託銀行、資産管理、不動産、年金・運用機能を持つ金融基盤。",
    "6524": "光通信用部品・電子部品を供給するAIインフラ周辺企業。",
    "6777": "光通信・光測定・医療用画像関連の高収益ニッチ企業。",
    "6627": "半導体テスト受託を通じAI半導体需要を支える後工程企業。",
    "6861": "FAセンサー、測定、画像処理機器を通じ現場実装を支える企業。",
    "6920": "半導体検査装置を通じ先端半導体投資に接続する企業。",
    "6356": "歯車・減速機・バルブ開閉装置など社会インフラ向け機械部品。",
    "6387": "半導体・電子部品向け製造装置を展開する装置メーカー。",
    "3449": "配管・継手・防災関連のニッチ製造業。",
    "4368": "半導体材料周辺にも接続する高機能化学品企業。",
    "4971": "電子基板・半導体パッケージ向け薬品を展開する化学企業。",
    "3723": "ゲームIPとソフトウェア資産を持つコンテンツ企業。",
    "1662": "資源開発、天然ガス、エネルギー供給に接続する資源企業。",
    "9513": "発電・卸電力・再エネを担う電力インフラ企業。",
    "6419": "アミューズメント向け機器・システムを持つ高収益ニッチ企業。",
}


def setup_style() -> None:
    if Path(JAPANESE_FONT_PATH).exists():
        font_manager.fontManager.addfont(JAPANESE_FONT_PATH)
        plt.rcParams["font.family"] = "Hiragino Sans"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"


def reset_dirs() -> None:
    if ASSET_DIR.exists():
        shutil.rmtree(ASSET_DIR)
    for path in DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def read_processed(name: str, **kwargs) -> pd.DataFrame:
    path = ROOT / "data" / "processed" / name
    if not path.exists():
        return pd.DataFrame()
    kwargs.setdefault("dtype", {"code": str})
    return pd.read_csv(path, **kwargs)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def display_name(df: pd.DataFrame) -> pd.Series:
    fallback = df.get("company_name", pd.Series("", index=df.index)).fillna("").astype(str)
    if "company_name_ja" not in df.columns:
        return fallback
    ja = df["company_name_ja"].fillna("").astype(str).str.strip()
    return ja.where(ja.str.len() > 0, fallback)


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float) != 0
    return series.fillna("").astype(str).str.lower().isin({"true", "1", "yes", "y"})


def num(series: pd.Series | object, default: float = 0.0) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce").fillna(default)
    return pd.Series(default)


def pct(value: object, digits: int = 1) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value) * 100:.{digits}f}%"
    except Exception:
        return ""


def yen(value: object) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{int(round(float(value))):,}円"
    except Exception:
        return ""


def save_fig(fig: plt.Figure, path: Path, *, svg: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    if svg:
        fig.savefig(path.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def enrich_final20(portfolio: pd.DataFrame) -> pd.DataFrame:
    out = portfolio.copy()
    out["company_name_report"] = display_name(out)
    if "primary_role" not in out.columns:
        out["primary_role"] = out.get("category", "").map(
            {
                "Core Moat": "守る堀",
                "Transformation Moat": "変わる堀",
                "Future Moat": "生まれる堀",
                "Discovery": "分散・橋渡し枠",
            }
        ).fillna("分散・橋渡し枠")
    if "secondary_role" not in out.columns:
        out["secondary_role"] = ""
    out["business_basis"] = out.apply(business_basis, axis=1)
    out["adoption_reason"] = out.apply(adoption_reason, axis=1)
    out["main_risk"] = out.apply(risk_note, axis=1)
    out["largest_score_contribution"] = out.apply(largest_score_contribution, axis=1)
    out["qualitative_check_points"] = out.apply(qualitative_check_points, axis=1)
    out["future_moat_business_basis"] = out.apply(future_business_basis, axis=1)
    return out


def business_basis(row: pd.Series) -> str:
    code = str(row.get("code", ""))
    return CODE_BUSINESS_BASIS.get(
        code,
        f"{row.get('sector_33', 'Unknown')} セクターに属する既存事業基盤。",
    )


def adoption_reason(row: pd.Series) -> str:
    role = str(row.get("primary_role", ""))
    score_text = (
        f"守る堀 {float(row.get('moat_score', 0)):.2f}、"
        f"変わる堀 {float(row.get('transformation_score', 0)):.2f}、"
        f"生まれる堀 {float(row.get('future_moat_score', 0)):.2f}"
    )
    if role == "守る堀":
        return f"既存事業の収益基盤・安定性を主役割として評価。{score_text}。"
    if role == "変わる堀":
        return f"PBR是正、資本効率改善、株主還元を通じた再評価余地を評価。{score_text}。"
    if role == "生まれる堀":
        return f"AI時代の半導体・光通信・電力・現場実装への接続を評価。{score_text}。"
    return f"役割間の分散とポートフォリオの橋渡しを評価。{score_text}。"


def risk_note(row: pd.Series) -> str:
    risks: list[str] = []
    sector = str(row.get("sector_33", ""))
    role = str(row.get("primary_role", ""))
    risk_score = float(row.get("risk_score", 0) or 0)
    max_dd = float(row.get("max_drawdown", 0) or 0)
    if risk_score > 0.8 or max_dd < -0.45:
        risks.append("株価変動率と過去ドローダウンが大きい")
    if role == "生まれる堀":
        risks.append("AI・半導体・設備投資サイクルの期待剥落")
    if sector == "Electric Power and Gas":
        risks.append("燃料価格、規制、電源構成、事故・安全対応")
    if bool(row.get("is_financial_like", row.get("is_financial", False))):
        risks.append("金利環境、信用コスト、金融規制")
    if not risks:
        risks.append("バリュエーション変化と事業環境悪化")
    return "、".join(risks) + "。"


def largest_score_contribution(row: pd.Series) -> str:
    scores = {
        "守る堀": row.get("moat_score", np.nan),
        "変わる堀": row.get("transformation_score", np.nan),
        "生まれる堀": row.get("future_moat_score", np.nan),
        "価格規律": row.get("valuation_score", np.nan),
        "Momentum": row.get("momentum_score", np.nan),
    }
    return max(scores, key=lambda key: float(scores[key]) if pd.notna(scores[key]) else -999)


def qualitative_check_points(row: pd.Series) -> str:
    role = str(row.get("primary_role", ""))
    if role == "生まれる堀":
        return "根拠キーワードが実際の売上・顧客・投資計画に結びつくか、有報・決算説明資料で確認。"
    if role == "変わる堀":
        return "PBR是正、ROE改善、自己株買い、政策保有株縮減、中期経営計画を一次資料で確認。"
    if role == "守る堀":
        return "利益率・CFの持続性、競争地位、価格転嫁力を一次資料で確認。"
    return "ポートフォリオ内の分散効果と主役割の補完関係を確認。"


def future_business_basis(row: pd.Series) -> str:
    if str(row.get("primary_role", "")) != "生まれる堀" and float(row.get("future_moat_score", 0) or 0) < 0.7:
        return ""
    flags = str(row.get("future_moat_category_flags", ""))
    evidence = str(row.get("future_moat_keyword_evidence", ""))
    basis = business_basis(row)
    return f"該当カテゴリ: {flags or '要確認'} / 根拠: {evidence or basis}"


def final20_table(portfolio: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "code",
        "ticker",
        "company_name_report",
        "sector_33",
        "market",
        "primary_role",
        "secondary_role",
        *SCORE_COLUMNS,
        "adoption_reason",
        "main_risk",
        "largest_score_contribution",
        "qualitative_check_points",
        "future_moat_business_basis",
    ]
    table = portfolio[[c for c in cols if c in portfolio.columns]].copy()
    table = table.rename(
        columns={
            "company_name_report": "company_name",
            "sector_33": "sector",
        }
    )
    return table


def write_screening_assets(scores: pd.DataFrame, portfolio: pd.DataFrame) -> pd.DataFrame:
    summary = read_processed("screening_summary.csv")
    stage_labels = {
        "universe": "東証上場企業",
        "price_available": "株価取得可能",
        "liquid_20m_60d": "流動性条件通過",
        "investment_eligible": "投資適格性通過",
        "scored": "スコア算出対象",
        "candidates_top80": "統合スコア上位80社",
        "portfolio_candidates": "最終20社",
    }
    summary["stage_label"] = summary["stage"].map(stage_labels).fillna(summary["stage"])
    summary = summary[["stage", "stage_label", "count"]]
    write_csv(summary, DIRS["screening"] / "screening_summary.csv")

    for name in [
        "investment_eligibility_exclusions.csv",
        "investment_eligibility_exclusion_summary.csv",
    ]:
        copy_if_exists(ROOT / "data" / "processed" / name, DIRS["screening"] / name)

    plot_screening_funnel(summary, DIRS["screening"] / "screening_funnel.png", svg=True)
    copy_if_exists(DIRS["screening"] / "screening_funnel.png", DIRS["screening"] / "screening_funnel_japanese.png")
    copy_if_exists(DIRS["screening"] / "screening_funnel.png", DIRS["fig_analysis"] / "screening_funnel.png")
    copy_if_exists(DIRS["screening"] / "screening_funnel.svg", DIRS["fig_analysis"] / "screening_funnel.svg")

    plot_market_funnel(scores, portfolio, DIRS["fig_analysis"] / "market_screening_funnel.png")
    plot_sector_summary(scores, portfolio, DIRS["fig_analysis"] / "sector_screening_summary.png")
    return summary


def plot_screening_funnel(summary: pd.DataFrame, path: Path, *, svg: bool = False) -> None:
    labels = summary["stage_label"].tolist()
    values = summary["count"].astype(int).tolist()
    fig, ax = plt.subplots(figsize=(9, 5.6))
    y = np.arange(len(labels))
    colors = [NAVY, "#2F5597", MID_BLUE, "#9DC3E6", GREEN, "#F4B183", ORANGE]
    ax.barh(y, values, color=colors[: len(values)])
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("社数")
    ax.set_title("3,649社から20社へ、投資可能性と3つの堀で絞り込む", color=NAVY, fontsize=15, weight="bold")
    max_value = max(values) if values else 1
    for i, value in enumerate(values):
        ax.text(value + max_value * 0.01, i, f"{value:,}社", va="center", fontsize=10, color=NAVY)
    ax.grid(axis="x", color=LINE, linewidth=0.6, alpha=0.5)
    ax.spines[["top", "right", "left"]].set_visible(False)
    save_fig(fig, path, svg=svg)


def write_score_assets(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_scores = scores.copy()
    all_scores["company_name_report"] = display_name(all_scores)
    write_csv(all_scores, DIRS["scores"] / "all_scores.csv")

    score_components = all_scores[
        [
            "code",
            "ticker",
            "company_name_report",
            "market",
            "sector_33",
            "investment_eligible",
            "score_calculation_target",
            *[c for c in COMPONENT_COLUMNS if c in all_scores.columns],
            *[c for c in SCORE_COLUMNS if c in all_scores.columns],
            *[c for c in all_scores.columns if c.endswith("_rank") or c.endswith("_percentile")],
            "future_moat_category_flags",
            "future_moat_keyword_evidence",
            "score_treatment",
        ]
    ].rename(columns={"company_name_report": "company_name"})
    write_csv(score_components, DIRS["scores"] / "score_components.csv")

    for column in [
        "moat_score",
        "transformation_score",
        "future_moat_score",
        "valuation_score",
        "momentum_score",
        "risk_score",
    ]:
        plot_score_distribution(scores, column, DIRS["scores"] / f"score_distribution_{column.removesuffix('_score')}.png")
        copy_if_exists(
            DIRS["scores"] / f"score_distribution_{column.removesuffix('_score')}.png",
            DIRS["fig_analysis"] / f"score_distribution_{column.removesuffix('_score')}.png",
        )

    corr = scores[SCORE_COLUMNS].apply(pd.to_numeric, errors="coerce").corr()
    corr.reset_index(names="score").to_csv(DIRS["scores"] / "score_correlation.csv", index=False)
    plot_score_correlation(corr, DIRS["scores"] / "score_correlation_heatmap.png")
    copy_if_exists(DIRS["scores"] / "score_correlation_heatmap.png", DIRS["fig_analysis"] / "score_correlation_heatmap.png")

    sensitivity, overlap, summary_md = score_weight_sensitivity(scores)
    write_csv(sensitivity, DIRS["scores"] / "score_weight_sensitivity.csv")
    write_csv(overlap, DIRS["scores"] / "score_weight_sensitivity_top20_overlap.csv")
    (DIRS["scores"] / "score_weight_sensitivity_summary.md").write_text(summary_md, encoding="utf-8")
    return score_components, corr


def plot_score_distribution(scores: pd.DataFrame, column: str, path: Path) -> None:
    data = pd.to_numeric(scores[column], errors="coerce").dropna()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.hist(data, bins=42, color=MID_BLUE, edgecolor="white")
    ax.axvline(data.median(), color=ORANGE, linestyle="--", linewidth=1.4, label="中央値")
    ax.set_title(f"{column} の分布は偏りと外れ値を確認する", color=NAVY, weight="bold")
    ax.set_xlabel(column)
    ax.set_ylabel("社数")
    ax.grid(axis="y", color=LINE, alpha=0.5, linewidth=0.6)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_score_correlation(corr: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6.5))
    image = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.index)), corr.index)
    ax.set_title("スコア間の相関で、単一テーマへの偏りを点検する", color=NAVY, weight="bold")
    for i, row in enumerate(corr.index):
        for j, col in enumerate(corr.columns):
            value = corr.loc[row, col]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=8)
    save_fig(fig, path)


def score_weight_sensitivity(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    eligible = scores[bool_series(scores["investment_eligible"])].copy()
    patterns = {
        "基本配分": (0.30, 0.25, 0.30, 0.15),
        "Moat重視": (0.40, 0.20, 0.25, 0.15),
        "Transformation重視": (0.25, 0.35, 0.25, 0.15),
        "Future Moat重視": (0.25, 0.20, 0.40, 0.15),
        "価格規律重視": (0.25, 0.25, 0.25, 0.25),
    }
    rows: list[dict[str, object]] = []
    top_sets: dict[str, set[str]] = {}
    for name, weights in patterns.items():
        moat_w, trans_w, future_w, val_w = weights
        score = (
            moat_w * pd.to_numeric(eligible["moat_score"], errors="coerce").fillna(0)
            + trans_w * pd.to_numeric(eligible["transformation_score"], errors="coerce").fillna(0)
            + future_w * pd.to_numeric(eligible["future_moat_score"], errors="coerce").fillna(0)
            + val_w * pd.to_numeric(eligible["valuation_score"], errors="coerce").fillna(0)
            + 0.10 * pd.to_numeric(eligible["momentum_score"], errors="coerce").fillna(0)
            - 0.10 * pd.to_numeric(eligible["risk_score"], errors="coerce").fillna(0)
        )
        ranked = eligible.assign(sensitivity_score=score).sort_values("sensitivity_score", ascending=False).head(20)
        top_sets[name] = set(ranked["code"].astype(str))
        for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
            rows.append(
                {
                    "scenario": name,
                    "rank": rank,
                    "code": row["code"],
                    "ticker": row["ticker"],
                    "company_name": display_name(pd.DataFrame([row])).iloc[0],
                    "sector_33": row.get("sector_33", ""),
                    "sensitivity_score": row["sensitivity_score"],
                }
            )
    base = top_sets["基本配分"]
    overlap_rows = [
        {
            "scenario": name,
            "overlap_with_basic_top20": len(codes & base),
            "overlap_ratio": len(codes & base) / 20,
        }
        for name, codes in top_sets.items()
    ]
    summary = [
        "# スコア重み感度分析",
        "",
        "5つの重みパターンで上位20社を比較した。バックテスト結果ではなく、スコア設計の安定性確認として実施した。",
        "",
    ]
    for row in overlap_rows:
        summary.append(
            f"- {row['scenario']}: 基本配分との重複 {row['overlap_with_basic_top20']}/20 ({row['overlap_ratio']:.0%})"
        )
    return pd.DataFrame(rows), pd.DataFrame(overlap_rows), "\n".join(summary) + "\n"


def write_final20_assets(portfolio: pd.DataFrame) -> None:
    final20 = final20_table(portfolio)
    write_csv(final20, DIRS["final20"] / "final20_portfolio.csv")
    component_cols = [
        "code",
        "ticker",
        "company_name_report",
        "primary_role",
        "secondary_role",
        *[c for c in COMPONENT_COLUMNS if c in portfolio.columns],
        *SCORE_COLUMNS,
        "future_moat_category_flags",
        "future_moat_keyword_evidence",
        "score_treatment",
    ]
    write_csv(
        portfolio[[c for c in component_cols if c in portfolio.columns]].rename(
            columns={"company_name_report": "company_name"}
        ),
        DIRS["final20"] / "final20_score_components.csv",
    )
    role_map = portfolio[
        [
            "code",
            "ticker",
            "company_name_report",
            "primary_role",
            "secondary_role",
            "sector_33",
            "actual_weight",
            "adoption_reason",
        ]
    ].rename(columns={"company_name_report": "company_name", "sector_33": "sector"})
    write_csv(role_map, DIRS["final20"] / "final20_role_map.csv")

    old_path = ROOT / "data" / "processed" / "portfolio_before_v12.csv"
    old = pd.read_csv(old_path, dtype={"code": str}) if old_path.exists() else pd.DataFrame()
    before_after, removed, added = before_after_tables(old, portfolio)
    write_csv(before_after, DIRS["final20"] / "final20_before_after_comparison.csv")
    write_csv(removed, DIRS["final20"] / "final20_removed_candidates.csv")
    write_csv(added, DIRS["final20"] / "final20_added_candidates.csv")
    (DIRS["final20"] / "final20_selection_rationale.md").write_text(
        selection_rationale(portfolio, removed, added),
        encoding="utf-8",
    )


def before_after_tables(old: pd.DataFrame, new: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if old.empty:
        old_codes: set[str] = set()
        old_base = pd.DataFrame(columns=["code", "company_name", "old_selected"])
    else:
        old = old.copy()
        old["company_name"] = display_name(old)
        old_codes = set(old["code"].astype(str))
        old_base = old[["code", "ticker", "company_name", "sector_33", "category"]].copy()
        old_base["old_selected"] = True
    new = new.copy()
    new["company_name"] = new["company_name_report"]
    new_codes = set(new["code"].astype(str))
    new_base = new[["code", "ticker", "company_name", "sector_33", "primary_role"]].copy()
    new_base["new_selected"] = True
    merged = old_base.merge(new_base, on="code", how="outer", suffixes=("_old", "_new"))
    merged["status"] = np.select(
        [
            merged["old_selected"].fillna(False) & merged["new_selected"].fillna(False),
            merged["old_selected"].fillna(False) & ~merged["new_selected"].fillna(False),
            ~merged["old_selected"].fillna(False) & merged["new_selected"].fillna(False),
        ],
        ["kept", "removed", "added"],
        default="",
    )
    removed = old[old["code"].astype(str).isin(old_codes - new_codes)].copy() if not old.empty else pd.DataFrame()
    added = new[new["code"].astype(str).isin(new_codes - old_codes)].copy()
    if not removed.empty:
        removed["removal_reason"] = removed.apply(
            lambda row: "v12の役割バランス・業種分散を優先し、より説明しやすい候補に入れ替え。", axis=1
        )
    if not added.empty:
        added["addition_reason"] = added["adoption_reason"]
    return merged, removed, added


def selection_rationale(portfolio: pd.DataFrame, removed: pd.DataFrame, added: pd.DataFrame) -> str:
    role_counts = portfolio["primary_role"].value_counts().reindex(ROLE_ORDER, fill_value=0)
    sector_counts = portfolio["sector_33"].value_counts()
    lines = [
        "# final20 selection rationale",
        "",
        "v12では、バックテスト結果ではなく、守る堀・変わる堀・生まれる堀・分散枠の説明可能性を基準に最終20社を決定した。",
        "上位80社を母集団とし、役割別スコア、1業種5社上限、金融・電力の過集中抑制を同時に確認した。",
        "",
        "## Role Counts",
        "",
    ]
    for role, count in role_counts.items():
        lines.append(f"- {role}: {int(count)}社")
    lines.extend(["", "## Sector Counts", ""])
    for sector, count in sector_counts.items():
        lines.append(f"- {sector}: {int(count)}社")
    lines.extend(["", "## Added", ""])
    if added.empty:
        lines.append("- 追加なし")
    else:
        for _, row in added.iterrows():
            lines.append(f"- {row['code']} {row['company_name_report']}: {row['addition_reason']}")
    lines.extend(["", "## Removed", ""])
    if removed.empty:
        lines.append("- 除外なし")
    else:
        for _, row in removed.iterrows():
            lines.append(f"- {row['code']} {display_name(pd.DataFrame([row])).iloc[0]}: {row['removal_reason']}")
    return "\n".join(lines) + "\n"


def write_portfolio_assets(portfolio: pd.DataFrame, config) -> None:
    allocation = portfolio.copy()
    allocation["company_name"] = allocation["company_name_report"]
    write_csv(allocation, DIRS["portfolio"] / "portfolio_allocation.csv")

    role_alloc = allocation.groupby("primary_role", as_index=False).agg(
        companies=("code", "count"),
        investment_yen=("actual_investment", "sum"),
        weight=("actual_weight", "sum"),
    )
    role_alloc = role_alloc.set_index("primary_role").reindex(ROLE_ORDER, fill_value=0).reset_index()
    write_csv(role_alloc, DIRS["portfolio"] / "portfolio_role_allocation.csv")

    sector_alloc = allocation.groupby("sector_33", as_index=False).agg(
        companies=("code", "count"),
        investment_yen=("actual_investment", "sum"),
        weight=("actual_weight", "sum"),
    ).sort_values("weight", ascending=False)
    write_csv(sector_alloc, DIRS["portfolio"] / "portfolio_sector_allocation.csv")

    comparison = allocation_comparison(allocation, config)
    write_csv(comparison, DIRS["portfolio"] / "portfolio_equal_weight_comparison.csv")
    (DIRS["portfolio"] / "portfolio_allocation_rationale.md").write_text(
        portfolio_rationale(allocation, role_alloc, sector_alloc, comparison, config),
        encoding="utf-8",
    )

    plot_role_allocation(role_alloc, DIRS["fig_analysis"] / "role_allocation.png")
    plot_sector_allocation(sector_alloc, DIRS["fig_analysis"] / "sector_allocation.png")
    plot_portfolio_table(allocation, DIRS["fig_analysis"] / "portfolio_allocation_table.png")


def allocation_comparison(portfolio: pd.DataFrame, config) -> pd.DataFrame:
    strategies = {
        "adjusted_bb_score加重": portfolio["adjusted_bb_score"].clip(lower=0),
        "等金額配分": pd.Series(1.0, index=portfolio.index),
        "カテゴリ均等配分": portfolio["primary_role"].map(
            portfolio["primary_role"].value_counts().rdiv(1.0)
        ).astype(float),
        "リスク調整配分": portfolio["adjusted_bb_score"].clip(lower=0)
        / (1 + portfolio["risk_score"].clip(lower=0)),
    }
    rows = []
    prices = pd.to_numeric(portfolio["previous_close"], errors="coerce").fillna(0)
    for name, raw in strategies.items():
        weights = cap_weights(pd.to_numeric(raw, errors="coerce").fillna(0), config.max_weight)
        target = weights * config.total_capital
        shares = np.floor(target / prices.replace(0, np.nan)).fillna(0)
        investment = shares * prices
        cash = config.total_capital - investment.sum()
        rows.append(
            {
                "strategy": name,
                "investment_yen": investment.sum(),
                "cash_yen": cash,
                "max_single_weight": (investment / config.total_capital).max(),
                "role_weight_summary": "; ".join(
                    f"{role}:{(investment[portfolio['primary_role'] == role].sum() / config.total_capital):.1%}"
                    for role in ROLE_ORDER
                ),
            }
        )
    return pd.DataFrame(rows)


def portfolio_rationale(
    portfolio: pd.DataFrame,
    role_alloc: pd.DataFrame,
    sector_alloc: pd.DataFrame,
    comparison: pd.DataFrame,
    config,
) -> str:
    invested = portfolio["actual_investment"].sum()
    cash = config.total_capital - invested
    return "\n".join(
        [
            "# portfolio allocation rationale",
            "",
            f"投資額は {config.total_capital:,}円、購入単位は1株、1銘柄上限は {config.max_weight:.0%} とした。",
            f"実投資額は {invested:,.0f}円、残現金は {cash:,.0f}円。",
            "",
            "配分は adjusted_bb_score を正値化して正規化し、上限8%を掛けた後、残現金を上位スコア銘柄へ1株単位で追加した。",
            "比較として等金額配分、カテゴリ均等配分、リスク調整配分も作成した。",
            "",
            "## Role allocation",
            *[
                f"- {row.primary_role}: {row.companies}社、{row.weight:.1%}"
                for _, row in role_alloc.iterrows()
            ],
            "",
            "## Sector concentration",
            *[
                f"- {row.sector_33}: {row.companies}社、{row.weight:.1%}"
                for _, row in sector_alloc.head(8).iterrows()
            ],
            "",
            "## Strategy comparison",
            *[
                f"- {row.strategy}: 投資額{row.investment_yen:,.0f}円、残現金{row.cash_yen:,.0f}円、最大比率{row.max_single_weight:.1%}"
                for _, row in comparison.iterrows()
            ],
            "",
        ]
    )


def load_returns(tickers: list[str]) -> pd.DataFrame:
    prices = pd.read_parquet(ROOT / "data" / "processed" / "prices_daily.parquet")
    prices = prices.copy()
    prices["ticker"] = prices["ticker"].astype(str)
    prices["price_for_return"] = prices["adj_close"].fillna(prices["close"])
    pivot = (
        prices[prices["ticker"].isin(tickers)]
        .pivot_table(index="date", columns="ticker", values="price_for_return", aggfunc="last")
        .sort_index()
    )
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.apply(repair_split_jumps, axis=0)
    return pivot.pct_change().replace([np.inf, -np.inf], np.nan)


def weighted_returns(returns: pd.DataFrame, tickers: list[str], weights: pd.Series | None = None) -> pd.Series:
    available = [ticker for ticker in tickers if ticker in returns.columns]
    if not available:
        return pd.Series(dtype=float)
    if weights is None:
        weights = pd.Series(1 / len(available), index=available)
    else:
        weights = weights.reindex(available).fillna(0)
        total = weights.sum()
        weights = weights / total if total > 0 else pd.Series(1 / len(available), index=available)
    return returns[available].mul(weights, axis=1).sum(axis=1, min_count=1).fillna(0)


def write_backtest_assets(portfolio: pd.DataFrame, scores: pd.DataFrame, config) -> None:
    tickers = sorted(set(portfolio["ticker"].astype(str)) | {config.topix_proxy, config.nikkei})
    returns = load_returns(tickers)
    weights = portfolio.set_index("ticker")["actual_weight"]
    final_returns = weighted_returns(returns, portfolio["ticker"].astype(str).tolist(), weights)
    topix = returns[config.topix_proxy].dropna() if config.topix_proxy in returns else None

    summary = read_processed("performance_summary.csv")
    write_csv(summary, DIRS["backtest"] / "backtest_summary.csv")
    write_csv(summary, DIRS["backtest"] / "benchmark_comparison.csv")

    ablation = build_ablation(scores, portfolio, returns, config)
    write_csv(ablation, DIRS["backtest"] / "ablation_analysis.csv")
    category_perf, category_cum = role_performance(portfolio, returns, topix)
    write_csv(category_perf, DIRS["backtest"] / "category_performance.csv")

    contribution = read_processed("contribution_by_stock.csv")
    if not contribution.empty:
        contribution = contribution.merge(
            portfolio[["ticker", "code", "company_name_report", "primary_role", "sector_33"]],
            on="ticker",
            how="left",
        )
    write_csv(contribution, DIRS["backtest"] / "contribution_by_stock.csv")

    concentration = concentration_analysis(portfolio, returns, final_returns, contribution, config)
    write_csv(concentration, DIRS["backtest"] / "concentration_risk_analysis.csv")
    drawdown = drawdown_periods(final_returns)
    write_csv(drawdown, DIRS["backtest"] / "drawdown_periods.csv")
    (DIRS["backtest"] / "backtest_limitations.md").write_text(
        backtest_limitations(summary, concentration, drawdown),
        encoding="utf-8",
    )

    plot_cumulative_from_returns(
        {
            "最終20社（調整後スコア加重）": final_returns,
            "TOPIX ETF（1306）": returns[config.topix_proxy].fillna(0) if config.topix_proxy in returns else pd.Series(dtype=float),
            "日経平均": returns[config.nikkei].fillna(0) if config.nikkei in returns else pd.Series(dtype=float),
        },
        DIRS["fig_analysis"] / "cumulative_return_comparison.png",
        "最終20社は指数比較で累積リターンを検証する",
    )
    plot_drawdown(final_returns, DIRS["fig_analysis"] / "drawdown_chart.png")
    plot_ablation_cumulative(scores, portfolio, returns, config, DIRS["fig_analysis"] / "ablation_cumulative_return.png")
    plot_cumulative_from_returns(category_cum, DIRS["fig_analysis"] / "category_cumulative_return.png", "役割別リターンで寄与の偏りを見る")
    plot_contribution(contribution, DIRS["fig_analysis"] / "contribution_by_stock.png")
    plot_table_image(concentration, DIRS["fig_analysis"] / "concentration_risk_table.png", "集中リスク分析")


def build_ablation(scores: pd.DataFrame, portfolio: pd.DataFrame, returns: pd.DataFrame, config) -> pd.DataFrame:
    series_by_label: dict[str, pd.Series] = {}
    weights = portfolio.set_index("ticker")["actual_weight"]
    final_tickers = portfolio["ticker"].astype(str).tolist()
    series_by_label["final20 adjusted score weight"] = weighted_returns(returns, final_tickers, weights)
    series_by_label["final20 equal weight"] = weighted_returns(returns, final_tickers)
    eligible = scores[bool_series(scores["investment_eligible"])].copy()
    for column in ["moat_score", "transformation_score", "future_moat_score", "valuation_score"]:
        tickers = eligible.sort_values(column, ascending=False)["ticker"].astype(str).head(20).tolist()
        series_by_label[f"{column} top20"] = weighted_returns(returns, tickers)
    if config.topix_proxy in returns:
        series_by_label["TOPIX ETF 1306.T"] = returns[config.topix_proxy].fillna(0)
    if config.nikkei in returns:
        series_by_label["Nikkei 225 ^N225"] = returns[config.nikkei].fillna(0)
    benchmark = returns[config.topix_proxy].dropna() if config.topix_proxy in returns else None
    rows = []
    for label, series in series_by_label.items():
        row = performance_row(label, series, benchmark)
        row["label"] = row.pop("name")
        rows.append(row)
    return pd.DataFrame(rows)


def role_performance(
    portfolio: pd.DataFrame,
    returns: pd.DataFrame,
    benchmark: pd.Series | None,
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    rows = []
    cumulative: dict[str, pd.Series] = {}
    for role, group in portfolio.groupby("primary_role"):
        weights = group.set_index("ticker")["actual_weight"]
        role_returns = weighted_returns(returns, group["ticker"].astype(str).tolist(), weights)
        row = performance_row(role, role_returns, benchmark)
        row["category"] = row.pop("name")
        row["portfolio_weight"] = group["actual_weight"].sum()
        row["companies"] = len(group)
        rows.append(row)
        cumulative[role] = role_returns
    return pd.DataFrame(rows), cumulative


def concentration_analysis(
    portfolio: pd.DataFrame,
    returns: pd.DataFrame,
    final_returns: pd.Series,
    contribution: pd.DataFrame,
    config,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    weights = portfolio.set_index("ticker")["actual_weight"]
    final_tickers = portfolio["ticker"].astype(str).tolist()
    base_cum = (1 + final_returns.fillna(0)).prod() - 1
    rows.append({"analysis": "baseline", "cumulative_return": base_cum, "note": "v12 final20"})
    for label, remove_tickers in {
        "santec除外": ["6777.T"],
        "上位3寄与銘柄除外": contribution.sort_values("contribution", ascending=False)["ticker"].astype(str).head(3).tolist()
        if not contribution.empty
        else [],
        "上位5寄与銘柄除外": contribution.sort_values("contribution", ascending=False)["ticker"].astype(str).head(5).tolist()
        if not contribution.empty
        else [],
    }.items():
        kept = [ticker for ticker in final_tickers if ticker not in set(remove_tickers)]
        if len(kept) == len(final_tickers):
            note = "対象銘柄は最終20社に含まれない" if label == "santec除外" else "対象なし"
        else:
            note = f"除外: {', '.join(remove_tickers)}"
        series = weighted_returns(returns, kept, weights)
        rows.append({"analysis": label, "cumulative_return": (1 + series.fillna(0)).prod() - 1, "note": note})
    future_weight = portfolio.loc[portfolio["primary_role"] == "生まれる堀", "actual_weight"].sum()
    future_contribution = 0.0
    if not contribution.empty and "primary_role" in contribution.columns:
        future_contribution = contribution.loc[contribution["primary_role"] == "生まれる堀", "contribution"].sum()
    rows.append(
        {
            "analysis": "Future Moat寄与集中",
            "cumulative_return": np.nan,
            "note": f"Future Moat weight={future_weight:.1%}, contribution={future_contribution:.1%}",
        }
    )
    rows.append(
        {
            "analysis": "単一銘柄上限",
            "cumulative_return": np.nan,
            "note": f"max weight={portfolio['actual_weight'].max():.1%}, limit={config.max_weight:.1%}",
        }
    )
    return pd.DataFrame(rows)


def drawdown_periods(returns: pd.Series) -> pd.DataFrame:
    wealth = (1 + returns.fillna(0)).cumprod()
    if wealth.empty:
        return pd.DataFrame(columns=["period_rank", "peak_date", "trough_date", "recovery_date", "max_drawdown"])
    running_max = wealth.cummax()
    dd = wealth / running_max - 1
    trough = dd.idxmin()
    peak = wealth.loc[:trough].idxmax()
    recovery_candidates = wealth.loc[trough:][wealth.loc[trough:] >= wealth.loc[peak]]
    recovery = recovery_candidates.index[0] if not recovery_candidates.empty else pd.NaT
    return pd.DataFrame(
        [
            {
                "period_rank": 1,
                "peak_date": peak.date() if hasattr(peak, "date") else peak,
                "trough_date": trough.date() if hasattr(trough, "date") else trough,
                "recovery_date": recovery.date() if hasattr(recovery, "date") else "",
                "max_drawdown": dd.loc[trough],
            }
        ]
    )


def backtest_limitations(summary: pd.DataFrame, concentration: pd.DataFrame, drawdown: pd.DataFrame) -> str:
    max_dd = ""
    if not summary.empty and "max_drawdown" in summary.columns:
        portfolio = summary[summary["name"].astype(str).eq("Portfolio")]
        if not portfolio.empty:
            max_dd = pct(portfolio["max_drawdown"].iloc[0])
    return "\n".join(
        [
            "# backtest limitations",
            "",
            "バックテストは最終20社を決めた後の検証であり、銘柄選定には使用していない。",
            f"最大ドローダウンは {max_dd or '別表参照'} で、下落局面のリスクとして本文に記録する。",
            "現在上場企業を母集団とするため、生存者バイアスを含む。",
            "現在時点の財務・価格データで過去を検証するため、ルックアヘッドバイアスを完全には排除できない。",
            "Future Moat銘柄は半導体サイクル、AI期待剥落、設備投資サイクルの影響を受けやすい。",
            "金融業は営業CF、自己資本比率、レバレッジの意味が一般事業会社と異なるため、業種内比較を優先した。",
            "EDINET XBRLとyfinanceには欠損・時点差があるため、最終提出前に有報本文、決算説明資料、中期経営計画で補完する。",
            "",
        ]
    )


def write_finance_assets() -> None:
    for name in [
        "financial_sector_handling_summary.csv",
        "financial_sector_exclusion_check.csv",
        "financial_sector_score_components.csv",
    ]:
        copy_if_exists(ROOT / "data" / "processed" / name, DIRS["finance"] / name)


def plot_market_funnel(scores: pd.DataFrame, portfolio: pd.DataFrame, path: Path) -> None:
    rows = []
    selected = set(portfolio["code"].astype(str))
    for market, group in scores.groupby(scores["market"].fillna("Unknown")):
        rows.append(
            {
                "market": market,
                "東証上場企業": len(group),
                "株価取得可能": bool_series(group["price_available"]).sum(),
                "流動性条件通過": bool_series(group["liquid_20m_60d"]).sum(),
                "投資適格性通過": bool_series(group["investment_eligible"]).sum(),
                "最終20社": group["code"].astype(str).isin(selected).sum(),
            }
        )
    table = pd.DataFrame(rows).sort_values("投資適格性通過", ascending=False).head(8)
    fig, ax = plt.subplots(figsize=(10, 5))
    table.set_index("market")[["投資適格性通過", "最終20社"]].plot(kind="bar", ax=ax, color=[MID_BLUE, ORANGE])
    ax.set_title("市場区分別に、投資適格性から最終20社への偏りを確認する", color=NAVY, weight="bold")
    ax.set_ylabel("社数")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=20)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_sector_summary(scores: pd.DataFrame, portfolio: pd.DataFrame, path: Path) -> None:
    selected = set(portfolio["code"].astype(str))
    rows = []
    for sector, group in scores.groupby(scores["sector_33"].fillna("Unknown")):
        rows.append(
            {
                "sector": sector,
                "投資適格性通過": bool_series(group["investment_eligible"]).sum(),
                "最終20社": group["code"].astype(str).isin(selected).sum(),
            }
        )
    table = pd.DataFrame(rows).sort_values(["最終20社", "投資適格性通過"], ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(9, 6))
    y = np.arange(len(table))
    ax.barh(y - 0.18, table["投資適格性通過"], height=0.36, color=MID_BLUE, label="投資適格性通過")
    ax.barh(y + 0.18, table["最終20社"], height=0.36, color=ORANGE, label="最終20社")
    ax.set_yticks(y, table["sector"])
    ax.invert_yaxis()
    ax.set_title("業種別に、最終20社の集中度を点検する", color=NAVY, weight="bold")
    ax.set_xlabel("社数")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_role_allocation(role_alloc: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.4))
    colors = [ROLE_COLORS.get(role, MID_BLUE) for role in role_alloc["primary_role"]]
    ax.bar(role_alloc["primary_role"], role_alloc["weight"], color=colors)
    ax.set_title("4つの役割が、500万円ポートフォリオの意味を分担する", color=NAVY, weight="bold")
    ax.set_ylabel("投資比率")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    ax.tick_params(axis="x", rotation=15)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_sector_allocation(sector_alloc: pd.DataFrame, path: Path) -> None:
    plot = sector_alloc.sort_values("weight").tail(12)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.barh(plot["sector_33"], plot["weight"], color=MID_BLUE)
    ax.set_title("業種分散で、半導体・電力・金融への集中を抑える", color=NAVY, weight="bold")
    ax.set_xlabel("投資比率")
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_portfolio_table(portfolio: pd.DataFrame, path: Path) -> None:
    table = portfolio[["code", "company_name_report", "primary_role", "sector_33", "actual_weight"]].copy()
    table["actual_weight"] = table["actual_weight"].map(lambda value: f"{value:.1%}")
    table = table.rename(columns={"company_name_report": "企業名", "sector_33": "業種", "primary_role": "役割", "actual_weight": "比率"})
    plot_table_image(table, path, "最終20社と投資比率")


def plot_table_image(table: pd.DataFrame, path: Path, title: str) -> None:
    shown = table.copy()
    if len(shown) > 24:
        shown = shown.head(24)
    fig, ax = plt.subplots(figsize=(11, max(3.5, len(shown) * 0.34 + 1.2)))
    ax.axis("off")
    ax.set_title(title, color=NAVY, weight="bold", pad=12)
    tbl = ax.table(cellText=shown.values, colLabels=shown.columns, loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.25)
    for (row, _col), cell in tbl.get_celld().items():
        cell.set_edgecolor(LINE)
        cell.set_linewidth(0.5)
        if row == 0:
            cell.set_facecolor(BLUE)
            cell.set_text_props(color=NAVY, weight="bold")
        else:
            cell.set_facecolor("white")
    save_fig(fig, path)


def plot_cumulative_from_returns(series_by_label: dict[str, pd.Series], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, series in series_by_label.items():
        if series.empty:
            continue
        cumulative = cumulative_returns(series)
        ax.plot(pd.to_datetime(cumulative.index), cumulative, label=label, linewidth=1.8)
    ax.axhline(0, color=LINE, linewidth=0.8)
    ax.set_title(title, color=NAVY, weight="bold")
    ax.set_ylabel("累積リターン")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_drawdown(returns: pd.Series, path: Path) -> None:
    wealth = (1 + returns.fillna(0)).cumprod()
    dd = wealth / wealth.cummax() - 1
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.fill_between(pd.to_datetime(dd.index), dd, 0, color="#A9C4E4", alpha=0.7)
    ax.plot(pd.to_datetime(dd.index), dd, color=NAVY, linewidth=1.4)
    ax.set_title("高リターンの裏側にある最大下落局面を確認する", color=NAVY, weight="bold")
    ax.set_ylabel("ドローダウン")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def plot_ablation_cumulative(scores: pd.DataFrame, portfolio: pd.DataFrame, returns: pd.DataFrame, config, path: Path) -> None:
    eligible = scores[bool_series(scores["investment_eligible"])]
    series = {
        "最終20社（スコア加重）": weighted_returns(
            returns,
            portfolio["ticker"].astype(str).tolist(),
            portfolio.set_index("ticker")["actual_weight"],
        ),
        "最終20社（等金額）": weighted_returns(returns, portfolio["ticker"].astype(str).tolist()),
    }
    labels = {
        "moat_score": "守る堀 上位20",
        "transformation_score": "変わる堀 上位20",
        "future_moat_score": "生まれる堀 上位20",
        "valuation_score": "価格規律 上位20",
    }
    for column in ["moat_score", "transformation_score", "future_moat_score", "valuation_score"]:
        tickers = eligible.sort_values(column, ascending=False)["ticker"].astype(str).head(20).tolist()
        series[labels[column]] = weighted_returns(returns, tickers)
    plot_cumulative_from_returns(series, path, "スコア別上位20との比較で統合スコアの意味を確認する")


def plot_contribution(contribution: pd.DataFrame, path: Path) -> None:
    if contribution.empty:
        plot_table_image(pd.DataFrame({"message": ["No contribution data"]}), path, "銘柄別寄与度")
        return
    shown = contribution.sort_values("contribution").tail(20).copy()
    labels = shown["company_name_report"].fillna(shown.get("company_name_ja", shown["ticker"]))
    fig, ax = plt.subplots(figsize=(9, 5.8))
    ax.barh(labels, shown["contribution"], color=MID_BLUE)
    ax.set_title("銘柄別寄与度で、一部銘柄への依存を確認する", color=NAVY, weight="bold")
    ax.set_xlabel("寄与度")
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, path)


def write_background_figures(portfolio: pd.DataFrame, screening_summary: pd.DataFrame) -> None:
    bg1_buffett_vs_beyond()
    bg2_four_roles()
    bg3_evolving_moat()
    bg4_three_turning_points()
    bg5_three_requirements()
    bg6_issue_requirement_screening()
    bg7_ai_infrastructure_map()
    bg8_company_matrix(portfolio)
    copy_if_exists(DIRS["screening"] / "screening_funnel.png", DIRS["fig_bg"] / "09_screening_funnel.png")
    copy_if_exists(DIRS["screening"] / "screening_funnel.svg", DIRS["fig_bg"] / "09_screening_funnel.svg")
    bg10_final20_role_map(portfolio)


def simple_box(ax, x: float, y: float, w: float, h: float, text: str, color: str = BLUE) -> None:
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, edgecolor=LINE, linewidth=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=NAVY, fontsize=11, wrap=True)


def bg1_buffett_vs_beyond() -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")
    ax.set_title("BEYOND BUFFETTは、完成された堀ではなく進化する堀を探す", color=NAVY, weight="bold", fontsize=15)
    simple_box(ax, 0.06, 0.25, 0.36, 0.48, "バフェット型\n完成された堀\n高収益・強ブランド・安定CF", GREY)
    simple_box(ax, 0.58, 0.25, 0.36, 0.48, "BEYOND BUFFETT\n進化する堀\n守る・変わる・生まれる", BLUE)
    ax.annotate("", xy=(0.56, 0.49), xytext=(0.44, 0.49), arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 2})
    save_fig(fig, DIRS["fig_bg"] / "01_buffett_vs_beyond_buffett.png", svg=True)


def bg2_four_roles() -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.axis("off")
    ax.set_title("最終20社は4つの役割でポートフォリオを構成する", color=NAVY, weight="bold", fontsize=15)
    positions = [(0.06, 0.58), (0.54, 0.58), (0.06, 0.18), (0.54, 0.18)]
    texts = [
        "守る堀\n既存事業の強さ",
        "変わる堀\n資本効率改革",
        "生まれる堀\nAI時代の産業基盤",
        "分散・橋渡し枠\n役割と業種の補完",
    ]
    for (x, y), text, color in zip(positions, texts, [BLUE, "#FCE4D6", "#E2F0D9", GREY], strict=True):
        simple_box(ax, x, y, 0.38, 0.24, text, color)
    save_fig(fig, DIRS["fig_bg"] / "02_four_roles.png", svg=True)


def bg3_evolving_moat() -> None:
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.axis("off")
    ax.set_title("完成された堀から、進化する堀へ", color=NAVY, weight="bold", fontsize=15)
    xs = [0.08, 0.38, 0.68]
    labels = ["守る堀\n収益性・CF・安定性", "変わる堀\nPBR是正・ROE改善", "生まれる堀\nAIインフラ・信頼基盤"]
    for x, label, color in zip(xs, labels, [BLUE, "#FCE4D6", "#E2F0D9"], strict=True):
        simple_box(ax, x, 0.35, 0.24, 0.28, label, color)
    for x in [0.32, 0.62]:
        ax.annotate("", xy=(x + 0.04, 0.49), xytext=(x, 0.49), arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 2})
    save_fig(fig, DIRS["fig_bg"] / "03_evolving_moat.png", svg=True)


def bg4_three_turning_points() -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.axis("off")
    ax.set_title("現代日本株の3つの転換点が、進化する堀を生む", color=NAVY, weight="bold", fontsize=15)
    for i, text in enumerate(["資本効率改革\nPBR是正", "AI産業基盤\n半導体・電力・光通信", "信頼インフラ\n金融・セキュリティ・監査"]):
        simple_box(ax, 0.08 + i * 0.30, 0.32, 0.24, 0.32, text, [BLUE, "#E2F0D9", "#FCE4D6"][i])
    save_fig(fig, DIRS["fig_bg"] / "04_three_turning_points.png", svg=True)


def bg5_three_requirements() -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis("off")
    ax.set_title("BEYOND BUFFETT企業の3要件", color=NAVY, weight="bold", fontsize=15)
    circle_specs = [(0.38, 0.58, "守る堀"), (0.28, 0.36, "変わる堀"), (0.50, 0.36, "生まれる堀")]
    for x, y, label in circle_specs:
        ax.add_patch(plt.Circle((x, y), 0.19, facecolor=BLUE, edgecolor=NAVY, alpha=0.45))
        ax.text(x, y, label, ha="center", va="center", color=NAVY, weight="bold")
    ax.text(0.39, 0.43, "進化する堀", ha="center", va="center", color=NAVY, fontsize=14, weight="bold")
    save_fig(fig, DIRS["fig_bg"] / "05_three_requirements.png", svg=True)


def bg6_issue_requirement_screening() -> None:
    table = pd.DataFrame(
        {
            "課題": ["長期保有に耐えるか", "日本株改革を取り込むか", "AI時代に接続するか", "高値掴みを避けるか"],
            "要件": ["守る堀", "変わる堀", "生まれる堀", "価格規律・リスク調整"],
            "スクリーニング": ["第1", "第2", "第3", "第4"],
        }
    )
    plot_table_image(table, DIRS["fig_bg"] / "06_issue_requirement_screening.png", "課題・要件・スクリーニング対応表")


def bg7_ai_infrastructure_map() -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.axis("off")
    ax.set_title("AI時代の産業基盤は、計算資源だけでなく周辺インフラに広がる", color=NAVY, weight="bold", fontsize=15)
    labels = ["電力・冷却", "半導体・検査", "光通信", "データセンター", "現場実装", "信頼・セキュリティ"]
    for i, label in enumerate(labels):
        x = 0.04 + i * 0.155
        simple_box(ax, x, 0.36, 0.125, 0.26, label, BLUE if i % 2 == 0 else GREY)
        if i < len(labels) - 1:
            ax.annotate("", xy=(x + 0.145, 0.49), xytext=(x + 0.126, 0.49), arrowprops={"arrowstyle": "->", "color": ORANGE})
    save_fig(fig, DIRS["fig_bg"] / "07_ai_infrastructure_map.png", svg=True)


def bg8_company_matrix(portfolio: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for role, group in portfolio.groupby("primary_role"):
        ax.scatter(group["transformation_score"], group["future_moat_score"], s=80, label=role, color=ROLE_COLORS.get(role, MID_BLUE), alpha=0.85)
        for _, row in group.iterrows():
            ax.text(row["transformation_score"], row["future_moat_score"], str(row["code"]), fontsize=8, ha="left", va="bottom")
    ax.axhline(0, color=LINE, linewidth=0.8)
    ax.axvline(0, color=LINE, linewidth=0.8)
    ax.set_title("企業分類マトリクスで、変革余地とFuture Moatを同時に見る", color=NAVY, weight="bold")
    ax.set_xlabel("変わる堀 score")
    ax.set_ylabel("生まれる堀 score")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, DIRS["fig_bg"] / "08_company_matrix.png", svg=True)


def bg10_final20_role_map(portfolio: pd.DataFrame) -> None:
    rows = []
    for role in ROLE_ORDER:
        names = portfolio.loc[portfolio["primary_role"] == role, "company_name_report"].tolist()
        rows.append({"役割": role, "企業": "、".join(names)})
    plot_table_image(pd.DataFrame(rows), DIRS["fig_bg"] / "10_final20_role_map.png", "最終20社の役割マップ")


def write_snippets(portfolio: pd.DataFrame, screening_summary: pd.DataFrame) -> None:
    role_counts = portfolio["primary_role"].value_counts().reindex(ROLE_ORDER, fill_value=0)
    finance_count = int(portfolio.get("is_financial_like", portfolio.get("is_financial", False)).astype(bool).sum())
    future_weight = portfolio.loc[portfolio["primary_role"] == "生まれる堀", "actual_weight"].sum()
    (DIRS["snippets"] / "screening_explanation.md").write_text(
        "\n".join(
            [
                "# v12スクリーニング説明",
                "",
                "v12では、BEYOND BUFFETTを「完成された堀を買う投資」ではなく「進化する堀を見つける投資」と定義した。",
                "第0スクリーニングで株価取得、流動性、財務安全性、継続収益力、営業CF、異常値、データ品質を確認し、投資適格性通過社数とスコア算出対象社数を一致させた。",
                "第1は守る堀、第2は変わる堀、第3は生まれる堀、第4は価格規律・リスク調整である。",
                "金融業は営業CF、自己資本比率、レバレッジの意味が一般事業会社と異なるため、ROE、PBR、利益安定性、株主還元、資本政策を中心に業種内比較した。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (DIRS["snippets"] / "final20_explanation.md").write_text(
        "\n".join(
            [
                "# final20 explanation",
                "",
                "最終20社は、統合スコア上位80社を母集団に、役割別スコアと分散制約から選定した。",
                "バックテスト結果は選定後の検証としてのみ使用し、銘柄入れ替えには用いていない。",
                "",
                *[f"- {role}: {int(count)}社" for role, count in role_counts.items()],
                "",
                "代表銘柄の採用理由は final20_portfolio.csv に記録した。入れ替え理由は final20_before_after_comparison.csv と final20_selection_rationale.md に整理した。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (DIRS["snippets"] / "risk_limitations.md").write_text(
        "\n".join(
            [
                "# risk limitations",
                "",
                f"Future Moat銘柄の投資比率は {future_weight:.1%}。半導体サイクル、AI期待剥落、設備投資サイクルに注意する。",
                "最大ドローダウン、寄与集中、santec除外、上位3・5銘柄除外分析は backtest/ に記録した。",
                f"金融業は {finance_count}社を組み入れた。一般事業会社と同じ営業CF・レバレッジ基準では比較しない。",
                "データ欠損、ルックアヘッドバイアス、生存者バイアス、無料データの時点差は限界として本文に明記する。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    figure_rows = figure_catalog()
    (DIRS["snippets"] / "figure_captions.md").write_text(
        "\n".join(
            ["# figure captions", ""]
            + [
                f"- {row['file']}: {row['caption']} 挿入位置: {row['section']}。読み取り: {row['reading']}"
                for row in figure_rows
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (DIRS["snippets"] / "primary_research_template.md").write_text(primary_research_template(), encoding="utf-8")


def primary_research_template() -> str:
    sections = ["金融実務家", "企業IR", "AI・半導体・電力・産業基盤関係者"]
    lines = ["# primary research template", "", "架空の回答は作成しない。実施後に人間が空欄を埋める。", ""]
    for section in sections:
        lines.extend(
            [
                f"## {section}",
                "",
                "- 対象者:",
                "- 所属:",
                "- 実施日:",
                "- 実施方法:",
                "- 質問項目:",
                "  - ",
                "  - ",
                "  - ",
                "- 得られた示唆:",
                "- 本レポートへの反映:",
                "- 引用可能な要約文:",
                "",
            ]
        )
    return "\n".join(lines)


def figure_catalog() -> list[dict[str, str]]:
    return [
        {"file": "figures/background/01_buffett_vs_beyond_buffett.png", "section": "導入", "caption": "バフェット型投資とBEYOND BUFFETTの違い", "reading": "完成された堀から進化する堀へ視点を広げる。"},
        {"file": "figures/background/02_four_roles.png", "section": "選定方針", "caption": "ポートフォリオを構成する4つの役割", "reading": "20社は役割分担で説明する。"},
        {"file": "figures/background/03_evolving_moat.png", "section": "投資テーマ", "caption": "完成された堀から進化する堀へ", "reading": "守る・変わる・生まれる堀を連続的に捉える。"},
        {"file": "figures/background/04_three_turning_points.png", "section": "市場環境", "caption": "現代日本株の3つの転換点", "reading": "資本効率改革とAIインフラ化が企業価値を変える。"},
        {"file": "figures/background/05_three_requirements.png", "section": "投資テーマ", "caption": "BEYOND BUFFETT企業の3要件", "reading": "3要件の重なりを評価する。"},
        {"file": "figures/background/06_issue_requirement_screening.png", "section": "スクリーニング", "caption": "課題・要件・スクリーニング対応表", "reading": "各課題をどのスクリーニングで確認したか示す。"},
        {"file": "figures/background/07_ai_infrastructure_map.png", "section": "Future Moat", "caption": "AI時代の産業基盤マップ", "reading": "AI関連をモデル企業だけに限定しない。"},
        {"file": "figures/background/08_company_matrix.png", "section": "最終20社", "caption": "企業分類マトリクス", "reading": "変革余地とFuture Moatの位置を比較する。"},
        {"file": "figures/background/09_screening_funnel.png", "section": "スクリーニング", "caption": "スクリーニング・ファネル", "reading": "投資可能性から最終20社までの整合性を示す。"},
        {"file": "figures/background/10_final20_role_map.png", "section": "最終20社", "caption": "最終20社の役割マップ", "reading": "各社の主役割を一覧化する。"},
        {"file": "figures/analysis/score_correlation_heatmap.png", "section": "スコア検証", "caption": "スコア相関", "reading": "単一スコアへの依存を確認する。"},
        {"file": "figures/analysis/cumulative_return_comparison.png", "section": "バックテスト", "caption": "累積リターン比較", "reading": "最終20社と指数を比較する。"},
        {"file": "figures/analysis/drawdown_chart.png", "section": "リスク", "caption": "ドローダウン", "reading": "下落局面の大きさを確認する。"},
        {"file": "figures/analysis/contribution_by_stock.png", "section": "寄与分析", "caption": "銘柄別寄与度", "reading": "寄与集中の有無を確認する。"},
    ]


def write_readme_and_manifest() -> None:
    figure_rows = figure_catalog()
    pd.DataFrame(figure_rows).to_csv(ASSET_DIR / "figure_index.csv", index=False)
    assets = sorted(p for p in ASSET_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store")
    pd.DataFrame(
        [
            {
                "relative_path": str(path.relative_to(ASSET_DIR)),
                "type": path.suffix.lower().lstrip("."),
                "bytes": path.stat().st_size,
            }
            for path in assets
        ]
    ).to_csv(ASSET_DIR / "asset_manifest.csv", index=False)
    lines = [
        "# submission_assets README",
        "",
        "BEYOND BUFFETT v12方針に基づき再生成した提出用素材集。",
        "",
        "## Directory",
        "",
        "- screening/: 投資可能性フィルター、除外理由、ファネル",
        "- scores/: 全スコア、成分、感度分析",
        "- final20/: 最終20社、役割、入れ替え理由",
        "- portfolio/: 500万円配分と比較",
        "- backtest/: 選定後の検証、寄与・集中・DD分析",
        "- figures/background/: 本文導入・構成図",
        "- figures/analysis/: 分析図表",
        "- finance_handling/: 金融業の別処理",
        "- report_snippets/: 本文貼り込み用Markdown",
        "",
        "## Figure Index",
        "",
    ]
    for row in figure_rows:
        lines.append(f"- {row['file']}: {row['section']} / {row['caption']} / {row['reading']}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "バックテストは最終20社決定後の検証であり、銘柄入れ替えには用いていない。",
            "一次情報の最終確認は report_snippets/primary_research_template.md に沿って人間が追記する。",
            "",
        ]
    )
    (ASSET_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def make_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in sorted(ASSET_DIR.rglob("*")):
            if path.is_file() and path.name != ".DS_Store":
                zipf.write(path, path.relative_to(ASSET_DIR.parent))


def quality_checks(scores: pd.DataFrame, portfolio: pd.DataFrame, config) -> pd.DataFrame:
    summary = read_processed("screening_summary.csv")
    counts = dict(zip(summary["stage"], summary["count"], strict=False))
    exclusions = read_processed("investment_eligibility_exclusion_summary.csv")
    unique_excluded = int(
        exclusions.loc[exclusions["reason"].eq("unique_excluded_total"), "excluded_companies"].iloc[0]
    )
    checks = [
        {
            "check": "liquidity_minus_eligible_equals_unique_excluded_total",
            "passed": int(counts.get("liquid_20m_60d", 0)) - int(counts.get("investment_eligible", 0)) == unique_excluded,
            "value": f"{counts.get('liquid_20m_60d', 0)} - {counts.get('investment_eligible', 0)} = {unique_excluded}",
        },
        {
            "check": "investment_eligible_equals_scored",
            "passed": int(counts.get("investment_eligible", 0)) == int(counts.get("scored", 0)),
            "value": f"{counts.get('investment_eligible', 0)} vs {counts.get('scored', 0)}",
        },
        {
            "check": "final20_all_investment_eligible",
            "passed": bool_series(portfolio["investment_eligible"]).all(),
            "value": str(bool_series(portfolio["investment_eligible"]).all()),
        },
        {
            "check": "final20_has_primary_role",
            "passed": portfolio["primary_role"].fillna("").astype(str).str.len().gt(0).all(),
            "value": "; ".join(f"{r}:{c}" for r, c in portfolio["primary_role"].value_counts().items()),
        },
        {
            "check": "investment_total_lte_capital",
            "passed": portfolio["actual_investment"].sum() <= config.total_capital,
            "value": yen(portfolio["actual_investment"].sum()),
        },
        {
            "check": "single_weight_lte_8pct",
            "passed": portfolio["actual_weight"].max() <= config.max_weight + 1e-9,
            "value": pct(portfolio["actual_weight"].max()),
        },
    ]
    table = pd.DataFrame(checks)
    write_csv(table, ASSET_DIR / "quality_checks.csv")
    if not table["passed"].all():
        raise RuntimeError("Quality checks failed:\n" + table.to_string(index=False))
    return table


def main() -> None:
    setup_style()
    reset_dirs()
    config = load_config()
    scores = read_processed("scores.csv")
    portfolio = enrich_final20(read_processed("portfolio.csv"))
    screening_summary = write_screening_assets(scores, portfolio)
    write_score_assets(scores)
    write_final20_assets(portfolio)
    write_portfolio_assets(portfolio, config)
    write_backtest_assets(portfolio, scores, config)
    write_finance_assets()
    write_background_figures(portfolio, screening_summary)
    write_snippets(portfolio, screening_summary)
    quality_checks(scores, portfolio, config)
    write_readme_and_manifest()
    make_zip()
    print(ASSET_DIR)
    print(ZIP_PATH)


if __name__ == "__main__":
    main()
