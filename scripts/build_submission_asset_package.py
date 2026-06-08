from __future__ import annotations

from pathlib import Path
import shutil
import sys
import zipfile

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.report.generate_pdf import _main_risk, _selection_reason  # noqa: E402

ASSET_DIR = ROOT / "reports" / "submission_assets"
TABLES_DIR = ASSET_DIR / "tables"
FIGURES_DIR = ASSET_DIR / "figures"
DOCS_DIR = ASSET_DIR / "docs"
ZIP_PATH = ROOT / "reports" / "submission_report_assets.zip"
JAPANESE_FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"

if Path(JAPANESE_FONT_PATH).exists():
    font_manager.fontManager.addfont(JAPANESE_FONT_PATH)
    plt.rcParams["font.family"] = "Hiragino Sans"
plt.rcParams["axes.unicode_minus"] = False


def ensure_dirs() -> None:
    for path in [TABLES_DIR, FIGURES_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def read_csv(name: str, *, base: str = "processed") -> pd.DataFrame:
    root = ROOT / "data" / base if base != "reports" else ROOT / "reports" / "tables"
    return pd.read_csv(root / name, dtype={"code": str})


def copy_file(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def pct(value: object, digits: int = 2) -> str:
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
        return f"{int(round(float(value))):,}"
    except Exception:
        return ""


def num(value: object, digits: int = 2) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def display_name(df: pd.DataFrame) -> pd.Series:
    fallback = df["company_name"].fillna(df["ticker"]).astype(str)
    if "company_name_ja" not in df.columns:
        return fallback
    japanese = df["company_name_ja"].fillna("").astype(str).str.strip()
    return japanese.where(japanese.str.len() > 0, fallback)


def screening_summary_for_report(summary: pd.DataFrame) -> pd.DataFrame:
    labels = {
        "universe": "母集団",
        "price_available": "株価取得可能",
        "liquid_20m_60d": "流動性条件通過",
        "investment_eligible": "投資適格性通過",
        "scored": "スコア算出対象",
        "candidates_top80": "統合スコア上位80社",
        "portfolio_candidates": "最終20銘柄",
    }
    table = summary.copy()
    table["stage"] = table["stage"].map(labels).fillna(table["stage"])
    return table.rename(columns={"stage": "段階", "count": "社数"})


def strongest_axis(row: pd.Series) -> str:
    scores = {
        "Moat": row.get("moat_score", np.nan),
        "Transformation": row.get("transformation_score", np.nan),
        "Future Moat": row.get("future_moat_score", np.nan),
        "Valuation": row.get("valuation_score", np.nan),
        "Momentum": row.get("momentum_score", np.nan),
    }
    return max(scores, key=lambda key: float(scores[key]) if pd.notna(scores[key]) else -999)


def business_axis(row: pd.Series) -> str:
    code = str(row.get("code", ""))
    mapping = {
        "9022": "東海道新幹線を中核とする鉄道・不動産・関連サービス",
        "7267": "二輪・四輪・パワープロダクツを持つグローバル輸送機器",
        "9501": "首都圏電力供給、送配電、発電、エネルギーインフラ",
        "8309": "信託銀行、資産管理、不動産、年金・運用機能",
        "3449": "配管・継手・防災関連のニッチ製造業",
        "8473": "証券、銀行、保険、暗号資産など総合金融プラットフォーム",
        "8630": "国内外損害保険、リスク管理、資産運用",
        "7181": "生命保険、郵政ネットワークを背景にした保険事業",
        "6178": "郵便、物流、金融、保険を束ねる社会インフラ",
        "5844": "京都地盤の銀行持株会社、地域金融と資本効率改善",
        "6524": "光通信用部品・電子部品を供給するAIインフラ周辺企業",
        "6627": "半導体テスト受託、AI半導体需要を支える後工程",
        "6777": "光通信・光測定・医療用画像関連の高収益ニッチ企業",
        "5076": "建設、インフラ運営、土木・道路を担う社会基盤企業",
        "6800": "車載・通信アンテナ、電子部品、コネクタ",
        "9513": "発電、卸電力、再エネ・脱炭素電源インフラ",
        "6387": "半導体・電子部品向け製造装置",
        "8050": "時計、電子デバイス、精密部品、ブランド事業",
        "5411": "鉄鋼、素材、インフラ・製造業向け基礎素材",
        "9984": "通信由来の投資会社、AI・半導体・デジタル投資",
    }
    return mapping.get(code, str(row.get("sector_33", "")))


def future_axis(row: pd.Series) -> str:
    code = str(row.get("code", ""))
    mapping = {
        "6777": "光通信・光計測・データセンター周辺",
        "6627": "AI半導体需要を支える半導体検査・後工程",
        "6524": "光通信・電子部品・AIインフラ周辺部材",
        "6387": "半導体製造装置・化合物半導体",
        "6800": "通信・車載・電子部品",
        "8050": "精密機器・電子デバイス・ブランド資産",
        "9984": "AI投資、半導体、デジタルプラットフォーム",
        "9501": "電力インフラ・データセンター需要",
        "9513": "電力インフラ・脱炭素投資",
        "7267": "EV・モビリティ変革、省人化・電動化",
        "5411": "素材供給、脱炭素・インフラ更新",
    }
    if code in mapping:
        return mapping[code]
    if row.get("category") == "Core Moat":
        return "既存事業の堀と資本効率改善"
    return "資本効率改善または既存事業の再評価"


def scenario_text(row: pd.Series) -> str:
    category = str(row.get("category", ""))
    if category == "Future Moat":
        return "AI・半導体・光通信・省人化投資の拡大が収益成長と再評価につながる。"
    if category == "Transformation Moat":
        return "低PBR是正、株主還元、金利・電力需要・事業改革が再評価を促す。"
    return "既存の収益基盤と市場地位を背景に、安定収益と株主還元が評価される。"


def write_core_tables() -> None:
    config = load_config()
    portfolio = read_csv("portfolio.csv")
    portfolio["company_name_report"] = display_name(portfolio)
    summary = read_csv("screening_summary.csv")
    performance = read_csv("performance_summary.csv")
    contribution = read_csv("contribution_by_stock.csv")
    category_returns = read_csv("category_returns.csv")

    screening_summary_for_report(summary).to_csv(TABLES_DIR / "screening_summary.csv", index=False)
    for filename in [
        "investment_eligibility_exclusions.csv",
        "investment_eligibility_exclusion_summary.csv",
    ]:
        source = config.data_processed_dir / filename
        if source.exists():
            pd.read_csv(source, dtype={"code": str}).to_csv(TABLES_DIR / filename, index=False)

    edinet_docs = read_csv("edinet_documents.csv")
    download_status = pd.read_csv(ROOT / "logs" / "edinet_download_status.csv")
    pd.DataFrame(
        [
            {"data": "上場企業一覧", "source": "JPX上場銘柄一覧", "usage": "母集団作成", "count_or_note": "3,649社"},
            {"data": "株価・出来高", "source": "yfinance", "usage": "流動性、リターン、リスク分析", "count_or_note": "価格取得3,648社"},
            {"data": "PER・PBR・配当利回り", "source": "yfinance", "usage": "Valuation Score", "count_or_note": "取得可能指標を使用"},
            {
                "data": "有価証券報告書",
                "source": "EDINET API v2",
                "usage": "財務、研究開発費、CF等",
                "count_or_note": f"候補{len(edinet_docs):,}件",
            },
            {
                "data": "XBRL ZIP",
                "source": "EDINET API v2",
                "usage": "財務指標抽出",
                "count_or_note": f"{int(download_status['ok'].sum()):,}/{len(download_status):,}件成功",
            },
            {"data": "企業IR・中期経営計画", "source": "各社公開資料", "usage": "定性評価・選定理由", "count_or_note": "提出前に個別確認"},
        ]
    ).to_csv(TABLES_DIR / "data_sources_table.csv", index=False)

    pd.DataFrame(
        [
            {"score": "Moat", "weight": 0.30, "evaluation": "既存の堀", "main_indicators": "収益性、キャッシュ創出力、安定性、競争地位"},
            {"score": "Transformation", "weight": 0.25, "evaluation": "変革余地", "main_indicators": "低PBR、低PER、成長、配当、資本効率"},
            {"score": "Future Moat", "weight": 0.30, "evaluation": "AI時代の堀", "main_indicators": "AIインフラ、半導体、データ、ソフトウェア、セキュリティ"},
            {"score": "Valuation", "weight": 0.15, "evaluation": "価格規律", "main_indicators": "PER、PBR、配当利回り"},
            {"score": "Momentum", "weight": 0.10, "evaluation": "市場評価", "main_indicators": "直近12か月リターン"},
            {"score": "Risk", "weight": -0.10, "evaluation": "リスク調整", "main_indicators": "ボラティリティ、最大DD、財務レバレッジ"},
        ]
    ).to_csv(TABLES_DIR / "score_formula_table.csv", index=False)

    final20 = portfolio.copy()
    final20["main_axis"] = final20.apply(strongest_axis, axis=1)
    final20[
        [
            "code",
            "company_name_report",
            "market",
            "sector_33",
            "category",
            "adjusted_bb_score",
            "main_axis",
        ]
    ].rename(columns={"company_name_report": "company_name"}).to_csv(
        TABLES_DIR / "scores_top20.csv", index=False
    )

    portfolio_table = final20[
        [
            "code",
            "company_name_report",
            "market",
            "sector_33",
            "category",
            "previous_close",
            "shares",
            "actual_investment",
            "actual_weight",
        ]
    ].rename(
        columns={
            "company_name_report": "company_name",
            "sector_33": "sector",
            "previous_close": "price",
            "actual_investment": "investment_yen",
            "actual_weight": "weight",
        }
    )
    portfolio_table.to_csv(TABLES_DIR / "portfolio_table.csv", index=False)

    pd.DataFrame(
        [
            {"item": "投資額", "value": f"{config.total_capital:,}円"},
            {"item": "実投資額", "value": f"{int(round(portfolio['actual_investment'].sum())):,}円"},
            {"item": "残現金", "value": f"{int(round(portfolio['cash_remaining'].iloc[0])):,}円"},
            {"item": "銘柄数", "value": "20銘柄"},
            {"item": "購入単位", "value": "1株単位"},
            {"item": "1銘柄上限", "value": f"{config.max_weight:.0%}"},
        ]
    ).to_csv(TABLES_DIR / "portfolio_policy_summary.csv", index=False)

    reason_rows = []
    for _, row in final20.iterrows():
        reason_rows.append(
            {
                "company_name": row["company_name_report"],
                "category": row["category"],
                "business": business_axis(row),
                "selection_reason": _selection_reason(row),
                "existing_moat": "収益性・市場地位・ブランド/ネットワークを評価"
                if row["category"] == "Core Moat"
                else "既存事業基盤は確認しつつ、主眼は再評価・成長余地",
                "transformation": "低PBR是正、資本効率改善、還元強化、事業改革"
                if row["category"] == "Transformation Moat"
                else "必要に応じて資本効率改善を確認",
                "future_moat": future_axis(row),
                "risk": _main_risk(row),
                "expected_scenario": scenario_text(row),
            }
        )
    pd.DataFrame(reason_rows).to_csv(TABLES_DIR / "selection_reason_table.csv", index=False)

    perf_table = performance.copy()
    perf_table["cumulative_return_pct"] = perf_table["cumulative_return"].map(pct)
    perf_table["annualized_return_pct"] = perf_table["annualized_return"].map(pct)
    perf_table["annualized_volatility_pct"] = perf_table["annualized_volatility"].map(pct)
    perf_table["max_drawdown_pct"] = perf_table["max_drawdown"].map(pct)
    perf_table.to_csv(TABLES_DIR / "performance_summary.csv", index=False)

    ablation = read_csv("ablation_performance.csv")
    ablation.to_csv(TABLES_DIR / "ablation_performance.csv", index=False)
    category_weights = portfolio.groupby("category", as_index=False)["actual_weight"].sum()
    category_top = (
        contribution.merge(portfolio[["ticker", "category"]], on="ticker", how="left")
        .sort_values("contribution", ascending=False)
        .groupby("category")["company_name_ja"]
        .apply(lambda values: "、".join(values.head(3).dropna().astype(str)))
        .reset_index(name="main_contributors")
    )
    category_table = category_returns.merge(category_weights, on="category", how="left").merge(
        category_top, on="category", how="left"
    )
    category_table.to_csv(TABLES_DIR / "category_returns.csv", index=False)

    sensitivity_src = ROOT / "reports" / "tables" / "contribution_sensitivity.csv"
    if sensitivity_src.exists():
        sensitivity = pd.read_csv(sensitivity_src)
    else:
        sensitivity = pd.DataFrame()
    sensitivity.to_csv(TABLES_DIR / "santec_exclusion_analysis.csv", index=False)

    make_future_moat_classification(final20).to_csv(
        TABLES_DIR / "future_moat_classification.csv", index=False
    )
    make_edinet_qualitative_summary(final20).to_csv(
        TABLES_DIR / "edinet_qualitative_summary.csv", index=False
    )
    make_limitations_table().to_csv(TABLES_DIR / "limitations_table.csv", index=False)
    read_csv("screening_by_market.csv").to_csv(TABLES_DIR / "screening_by_market.csv", index=False)
    read_csv("screening_by_sector.csv").to_csv(TABLES_DIR / "screening_by_sector.csv", index=False)
    read_csv("score_correlation.csv").to_csv(TABLES_DIR / "score_correlation.csv", index=False)


def make_future_moat_classification(portfolio: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in portfolio.iterrows():
        code = str(row["code"])
        compute = code in {"6627", "6387", "9984"}
        infra = code in {"6777", "6524", "9501", "9513", "6800"}
        implementation = code in {"7267", "6387", "6800", "8050", "5076", "5411"}
        data = code in {"9984", "6777", "6627"}
        trust = code in {"8309", "8630", "8473", "7181", "6178", "5844"}
        rows.append(
            {
                "code": code,
                "company_name": row["company_name_report"],
                "計算資源": "○" if compute else "",
                "インフラ": "○" if infra else "",
                "現場実装": "○" if implementation else "",
                "データ": "○" if data else "",
                "信頼": "○" if trust else "",
                "根拠": future_axis(row),
            }
        )
    return pd.DataFrame(rows)


def make_edinet_qualitative_summary(portfolio: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in portfolio.iterrows():
        rows.append(
            {
                "code": row["code"],
                "company_name": row["company_name_report"],
                "business_summary": business_axis(row),
                "issues_to_address": "資本効率改善、成長投資、事業ポートフォリオ最適化を確認する。",
                "business_risks": _main_risk(row),
                "rd_activity": future_axis(row)
                if row["category"] == "Future Moat"
                else "研究開発よりも資本政策・収益基盤の確認を優先。",
                "governance_capital_policy": "低PBR是正、株主還元、政策保有株、資本配分方針を有報・IRで確認。",
                "investment_hypothesis": scenario_text(row),
                "source_note": "EDINET XBRL取得済み。定性文は提出前に有価証券報告書本文・IR資料で最終確認するドラフト。",
            }
        )
    return pd.DataFrame(rows)


def make_limitations_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "limitation": "ルックアヘッドバイアス",
                "risk": "現在データで選んだ20社の過去リターンを確認している。",
                "mitigation": "将来成果の保証ではなく、過去特性の検証として明記する。",
            },
            {
                "limitation": "生存者バイアス",
                "risk": "現在上場している企業が母集団で、上場廃止企業を含まない。",
                "mitigation": "提出本文で限界として明記し、過度な一般化を避ける。",
            },
            {
                "limitation": "EDINET定性情報",
                "risk": "XBRLは定量指標に強いが、事業リスクや課題は文章確認が必要。",
                "mitigation": "最終提出前に有報本文・中計・IR資料で補完する。",
            },
            {
                "limitation": "金融銘柄の比較可能性",
                "risk": "営業CF、営業利益率、自己資本比率の意味が一般事業会社と異なる。",
                "mitigation": "PBR、ROE、金利環境、還元方針を中心に別枠評価する。",
            },
            {
                "limitation": "寄与集中",
                "risk": "santecなど一部Future Moat銘柄の寄与が大きい。",
                "mitigation": "santec除外・上位寄与銘柄除外分析を併記する。",
            },
            {
                "limitation": "データ欠損・API差異",
                "risk": "yfinance指標やEDINETタグには欠損・時点差がある。",
                "mitigation": "欠損ログと一次資料確認で補完する。",
            },
        ]
    )


def plot_screening_funnel() -> None:
    summary = read_csv("screening_summary.csv")
    stages = [
        ("東証上場企業", "universe"),
        ("株価取得可能", "price_available"),
        ("流動性条件", "liquid_20m_60d"),
        ("投資適格性", "investment_eligible"),
        ("スコア算出対象", "scored"),
        ("統合スコア上位", "candidates_top80"),
        ("定性評価・分散調整", "portfolio_candidates"),
    ]
    counts = {
        str(row["stage"]): int(row["count"])
        for _, row in summary.iterrows()
    }
    labels = [label for label, _ in stages]
    values = [counts[key] for _, key in stages]
    fig, ax = plt.subplots(figsize=(9, 5.8))
    y = np.arange(len(values))
    colors = ["#294c7a", "#3569a4", "#4e8bc5", "#78add8", "#91b96b", "#e0a83a", "#c95f43"]
    ax.barh(y, values, color=colors)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("社数")
    ax.set_title("スクリーニング・ファネル")
    for i, value in enumerate(values):
        ax.text(value + max(values) * 0.01, i, f"{value:,}社", va="center", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "screening_funnel.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_score_distributions() -> None:
    scores = read_csv("scores.csv")
    columns = [
        ("moat_score", "Moat Score分布"),
        ("transformation_score", "Transformation Score分布"),
        ("future_moat_score", "Future Moat Score分布"),
        ("adjusted_bb_score", "Adjusted BB Score分布"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, (column, title) in zip(axes.ravel(), columns, strict=True):
        ax.hist(pd.to_numeric(scores[column], errors="coerce").dropna(), bins=40, color="#3569a4", alpha=0.85)
        ax.set_title(title)
        ax.set_ylabel("社数")
        ax.axvline(scores[column].median(), color="#c95f43", linestyle="--", linewidth=1)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "score_component_distributions.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    for column, title in columns[:-1]:
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        ax.hist(pd.to_numeric(scores[column], errors="coerce").dropna(), bins=40, color="#3569a4", alpha=0.85)
        ax.set_title(title)
        ax.set_ylabel("社数")
        ax.axvline(scores[column].median(), color="#c95f43", linestyle="--", linewidth=1)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"{column}_distribution.png", dpi=180, bbox_inches="tight")
        plt.close(fig)


def copy_existing_assets() -> None:
    figure_names = [
        "score_distribution.png",
        "score_correlation_heatmap.png",
        "category_allocation.png",
        "sector_allocation.png",
        "cumulative_return.png",
        "drawdown.png",
        "contribution_by_stock.png",
        "risk_return_scatter.png",
        "ablation_cumulative_return.png",
        "category_cumulative_return.png",
        "screening_funnel_by_market.png",
        "screening_funnel_by_sector.png",
    ]
    for name in figure_names:
        copy_file(ROOT / "reports" / "figures" / name, FIGURES_DIR / name)

    doc_names = [
        "submission_report_draft.md",
        "submission_report_draft.docx",
        "submission_report_draft.pdf",
        "beyond_buffett_screening_portfolio_analysis.pdf",
    ]
    for name in doc_names:
        copy_file(ROOT / "reports" / "draft" / name, DOCS_DIR / name)


def write_readme_and_manifest() -> list[Path]:
    assets = sorted([p for p in ASSET_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store"])
    manifest = pd.DataFrame(
        [
            {
                "relative_path": str(path.relative_to(ASSET_DIR)),
                "type": path.suffix.lower().lstrip("."),
                "bytes": path.stat().st_size,
            }
            for path in assets
        ]
    )
    manifest.to_csv(ASSET_DIR / "asset_manifest.csv", index=False)

    figure_index = pd.DataFrame(
        [
            {"file": "figures/screening_funnel.png", "section": "Ⅱ スクリーニング", "purpose": "3,649社から20社への絞り込みを示す"},
            {"file": "figures/score_distribution.png", "section": "Ⅱ スクリーニング", "purpose": "Adjusted BB Scoreの全体分布"},
            {"file": "figures/score_component_distributions.png", "section": "Ⅱ スクリーニング", "purpose": "Moat/Transformation/Future/Adjustedの分布比較"},
            {"file": "figures/score_correlation_heatmap.png", "section": "Ⅱ スクリーニング", "purpose": "スコア間の重複と独立性の確認"},
            {"file": "figures/category_allocation.png", "section": "Ⅲ ポートフォリオ", "purpose": "Core/Transformation/Futureの役割配分"},
            {"file": "figures/sector_allocation.png", "section": "Ⅲ ポートフォリオ", "purpose": "セクター分散とテーマ接続"},
            {"file": "figures/cumulative_return.png", "section": "Ⅲ-2 パフォーマンス", "purpose": "TOPIX proxy/日経平均との累積リターン比較"},
            {"file": "figures/drawdown.png", "section": "Ⅲ-2 パフォーマンス", "purpose": "高リターンの裏側にある下落リスク"},
            {"file": "figures/contribution_by_stock.png", "section": "Ⅲ-2 パフォーマンス", "purpose": "銘柄別リターン源泉とsantec依存度"},
            {"file": "figures/ablation_cumulative_return.png", "section": "Ⅲ-2 パフォーマンス", "purpose": "統合スコアの意味を比較"},
        ]
    )
    figure_index.to_csv(ASSET_DIR / "figure_index.csv", index=False)

    readme = "\n".join(
        [
            "# BEYOND BUFFETT 提出レポート素材パッケージ",
            "",
            "提出用レポート作成に必要な図表、数値、テーブルを集約したフォルダです。",
            "",
            "## ディレクトリ",
            "",
            "- `tables/`: CSV形式の表・数値",
            "- `figures/`: PNG形式の図表",
            "- `docs/`: 草案PDF/DOCX/Markdownと元分析PDF",
            "",
            "## 最優先で使う素材",
            "",
            "- `tables/screening_summary.csv` と `figures/screening_funnel.png`",
            "- `tables/investment_eligibility_exclusion_summary.csv` と `tables/investment_eligibility_exclusions.csv`",
            "- `tables/score_formula_table.csv`",
            "- `tables/scores_top20.csv`",
            "- `tables/portfolio_table.csv` と `tables/portfolio_policy_summary.csv`",
            "- `figures/category_allocation.png` と `figures/sector_allocation.png`",
            "- `tables/selection_reason_table.csv`",
            "- `tables/performance_summary.csv`",
            "- `figures/cumulative_return.png`、`figures/drawdown.png`、`figures/contribution_by_stock.png`",
            "- `tables/ablation_performance.csv`、`tables/category_returns.csv`、`tables/santec_exclusion_analysis.csv`",
            "- `tables/future_moat_classification.csv`、`tables/edinet_qualitative_summary.csv`、`tables/limitations_table.csv`",
            "",
            "## 注意",
            "",
            "投資適格性フィルターでは、500万円の仮想ポートフォリオに組み入れる前提として、流動性に加え、財務安全性、継続的な収益力、キャッシュ創出力、主要指標の異常値を確認しました。財務的な持続可能性を欠く企業や、データの信頼性が著しく低い企業は長期投資の対象として不適切であるため除外しています。",
            "",
            "EDINET定性要約は提出前の確認用ドラフトです。EDINET XBRL取得済みの定量情報と既存分類をもとに作成していますが、最終提出前には有価証券報告書本文・IR資料で文言を確認してください。",
            "",
        ]
    )
    (ASSET_DIR / "README.md").write_text(readme, encoding="utf-8")
    return sorted([p for p in ASSET_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store"])


def make_zip(files: list[Path]) -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in files:
            zipf.write(path, path.relative_to(ASSET_DIR.parent))


def main() -> None:
    ensure_dirs()
    write_core_tables()
    plot_screening_funnel()
    plot_score_distributions()
    copy_existing_assets()
    files = write_readme_and_manifest()
    make_zip(files)
    print(ASSET_DIR)
    print(ZIP_PATH)
    print(len(files))


if __name__ == "__main__":
    main()
