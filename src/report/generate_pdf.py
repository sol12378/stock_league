from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import shorten

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


PAGE_WIDTH = 1654
PAGE_HEIGHT = 2339
MARGIN_X = 92
MARGIN_Y = 88
LINE_GAP = 8

FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size, index=0)
    return ImageFont.load_default()


def _display_name(row: pd.Series) -> str:
    name = str(row.get("company_name_ja", "") or "").strip()
    if name:
        return name
    return str(row.get("company_name", "") or row.get("ticker", "")).strip()


def _pct(value: object, digits: int = 1) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value) * 100:.{digits}f}%"
    except Exception:
        return "-"


def _yen(value: object) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{int(round(float(value))):,}円"
    except Exception:
        return "-"


def _num(value: object, digits: int = 2) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):.{digits}f}"
    except Exception:
        return "-"


def _strongest_component(row: pd.Series) -> str:
    labels = {
        "Moat": row.get("moat_score", 0),
        "Transformation": row.get("transformation_score", 0),
        "Future Moat": row.get("future_moat_score", 0),
        "Valuation": row.get("valuation_score", 0),
        "Momentum": row.get("momentum_score", 0),
    }
    return max(labels, key=lambda key: float(labels[key]) if pd.notna(labels[key]) else -999)


def _selection_reason(row: pd.Series) -> str:
    category = str(row.get("category", ""))
    strongest = _strongest_component(row)
    reasons: list[str] = []
    if category == "Core Moat":
        reasons.append("既存Moatを中核に採用")
    elif category == "Transformation Moat":
        reasons.append("変革余地と再評価余地を中核に採用")
    elif category == "Future Moat":
        reasons.append("AI時代のFuture Moatを中核に採用")
    else:
        reasons.append("市場に見落とされやすいDiscovery枠として採用")

    if pd.notna(row.get("price_to_book")):
        pbr = float(row["price_to_book"])
        if pbr < 0.8:
            reasons.append(f"PBR {_num(pbr)}倍で資産価値対比の割安感")
        elif pbr > 3:
            reasons.append(f"PBR {_num(pbr)}倍でも成長・テーマ性を評価")
    if pd.notna(row.get("trailing_pe")) and float(row["trailing_pe"]) > 0:
        pe = float(row["trailing_pe"])
        if pe < 12:
            reasons.append(f"PER {_num(pe)}倍で利益対比の割安感")
    if pd.notna(row.get("roe")) and float(row["roe"]) > 0.10:
        reasons.append(f"ROE {_pct(row['roe'])}の収益性")
    if pd.notna(row.get("operating_margin")) and float(row["operating_margin"]) > 0.15:
        reasons.append(f"営業利益率 {_pct(row['operating_margin'])}の収益力")
    if pd.notna(row.get("return_12m_ex_1m")) and float(row["return_12m_ex_1m"]) > 0.5:
        reasons.append(f"直近12か月リターン {_pct(row['return_12m_ex_1m'])}の市場評価")
    if strongest not in " ".join(reasons):
        reasons.append(f"スコア上の最大寄与は{strongest}")
    return "、".join(reasons) + "。"


def _main_risk(row: pd.Series) -> str:
    sector = str(row.get("sector_33", ""))
    category = str(row.get("category", ""))
    risks: list[str] = []
    if pd.notna(row.get("annual_volatility")) and float(row["annual_volatility"]) > 0.30:
        risks.append("株価変動率が高い")
    if pd.notna(row.get("max_drawdown")) and float(row["max_drawdown"]) < -0.35:
        risks.append("過去ドローダウンが大きい")
    if bool(row.get("is_financial", False)):
        risks.append("金融規制・金利環境の影響")
    if "Electric Power" in sector:
        risks.append("規制・燃料価格・政策変更")
    elif "Electric Appliances" in sector or "Machinery" in sector:
        risks.append("半導体サイクルと設備投資減速")
    elif "Transportation" in sector or "Land Transportation" in sector:
        risks.append("景気・為替・需要変動")
    elif "Iron and Steel" in sector:
        risks.append("市況・原材料価格・脱炭素投資負担")
    if category == "Future Moat":
        risks.append("成長期待の剥落")
    if not risks:
        risks.append("市場全体の下落と業績モメンタム鈍化")
    return "、".join(dict.fromkeys(risks)) + "。"


@dataclass
class PdfPageWriter:
    pages: list[Image.Image]
    image: Image.Image
    draw: ImageDraw.ImageDraw
    y: int

    @classmethod
    def create(cls) -> "PdfPageWriter":
        image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
        return cls([], image, ImageDraw.Draw(image), MARGIN_Y)

    def _new_page(self) -> None:
        self.pages.append(self.image)
        self.image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.y = MARGIN_Y

    def _ensure(self, height: int) -> None:
        if self.y + height > PAGE_HEIGHT - MARGIN_Y:
            self._new_page()

    def text(self, value: str, size: int = 28, fill: str = "#222222", gap: int = 12, indent: int = 0) -> None:
        font = _font(size)
        max_width = PAGE_WIDTH - 2 * MARGIN_X - indent
        lines = self._wrap(value, font, max_width)
        line_height = int(size * 1.45)
        self._ensure(max(line_height, len(lines) * line_height) + gap)
        for line in lines:
            self.draw.text((MARGIN_X + indent, self.y), line, font=font, fill=fill)
            self.y += line_height
        self.y += gap

    def heading(self, value: str, level: int = 1) -> None:
        if level == 0:
            self.text(value, size=46, fill="#111111", gap=18)
        elif level == 1:
            self.y += 14
            self.text(value, size=34, fill="#15365f", gap=10)
        else:
            self.text(value, size=27, fill="#254d7a", gap=8)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int], font_size: int = 19) -> None:
        font = _font(font_size)
        header_font = _font(font_size)
        line_height = int(font_size * 1.35)
        padding = 10
        x0 = MARGIN_X

        def row_height(cells: list[str]) -> tuple[int, list[list[str]]]:
            wrapped = [self._wrap(str(cell), font, widths[idx] - 2 * padding) for idx, cell in enumerate(cells)]
            return max(line_height + 2 * padding, max(len(lines) for lines in wrapped) * line_height + 2 * padding), wrapped

        h, header_lines = row_height(headers)
        self._ensure(h)
        self._draw_table_row(x0, headers, widths, h, header_lines, header_font, "#dce9f7", bold=True)
        for cells in rows:
            h, wrapped = row_height(cells)
            self._ensure(h)
            self._draw_table_row(x0, cells, widths, h, wrapped, font, "#ffffff")
        self.y += 18

    def _draw_table_row(
        self,
        x0: int,
        cells: list[str],
        widths: list[int],
        height: int,
        wrapped: list[list[str]],
        font: ImageFont.ImageFont,
        fill: str,
        bold: bool = False,
    ) -> None:
        x = x0
        padding = 10
        line_height = int((font.size if hasattr(font, "size") else 18) * 1.35)
        for idx, _cell in enumerate(cells):
            self.draw.rectangle([x, self.y, x + widths[idx], self.y + height], outline="#c8d1dc", fill=fill)
            yy = self.y + padding
            for line in wrapped[idx]:
                self.draw.text((x + padding, yy), line, font=font, fill="#111111")
                yy += line_height
            x += widths[idx]
        self.y += height

    def image_file(self, path: Path, max_height: int = 560) -> None:
        if not path.exists():
            return
        with Image.open(path) as img:
            img = img.convert("RGB")
            max_width = PAGE_WIDTH - 2 * MARGIN_X
            ratio = min(max_width / img.width, max_height / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            self._ensure(new_size[1] + 20)
            resized = img.resize(new_size)
            x = MARGIN_X + (max_width - new_size[0]) // 2
            self.image.paste(resized, (x, self.y))
            self.y += new_size[1] + 24

    def save(self, path: Path) -> None:
        self.pages.append(self.image)
        first, rest = self.pages[0], self.pages[1:]
        first.save(path, "PDF", resolution=150, save_all=True, append_images=rest)

    def _wrap(self, value: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        text = str(value).replace("\n", " ").strip()
        if not text:
            return [""]
        lines: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            bbox = self.draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines


def _portfolio_with_reasons(portfolio: pd.DataFrame) -> pd.DataFrame:
    df = portfolio.copy()
    df["企業名"] = df.apply(_display_name, axis=1)
    df["selection_reason"] = df.apply(_selection_reason, axis=1)
    df["main_risk"] = df.apply(_main_risk, axis=1)
    return df


def _screening_stage_label(stage: object) -> str:
    labels = {
        "universe": "母集団",
        "price_available": "株価取得可能",
        "liquid_20m_60d": "流動性条件通過",
        "investment_eligible": "投資適格性通過",
        "scored": "スコア算出対象",
        "candidates_top80": "統合スコア上位80社",
        "portfolio_candidates": "最終20銘柄",
    }
    return labels.get(str(stage), str(stage))


def generate_pdf(config: AppConfig) -> Path:
    logger = setup_logger("generate_pdf", config.logs_dir)
    summary = pd.read_csv(config.data_processed_dir / "screening_summary.csv")
    top80 = pd.read_csv(config.data_processed_dir / "candidates_top80.csv", dtype={"code": str})
    portfolio = pd.read_csv(config.data_processed_dir / "portfolio.csv", dtype={"code": str})
    performance = pd.read_csv(config.data_processed_dir / "performance_summary.csv")
    edinet = pd.read_csv(config.data_processed_dir / "edinet_documents.csv", dtype={"code": str})
    download_status = pd.read_csv(config.logs_dir / "edinet_download_status.csv")
    missing = pd.read_csv(config.logs_dir / "edinet_missing_companies.csv", dtype={"code": str})

    portfolio = _portfolio_with_reasons(portfolio)
    reasons_path = config.reports_tables_dir / "portfolio_selection_reasons.csv"
    portfolio[["code", "ticker", "企業名", "category", "selection_reason", "main_risk"]].to_csv(
        reasons_path,
        index=False,
    )

    pdf = PdfPageWriter.create()
    pdf.heading("BEYOND BUFFETT 自動分析レポート", level=0)
    pdf.text("Ⅱ スクリーニング / Ⅲ ポートフォリオ決定 / パフォーマンス分析", size=27)
    pdf.text(
        "東証上場企業全体を母集団とし、JPX上場銘柄一覧、yfinance価格データ、EDINET API v2の有価証券報告書XBRLを用いて、"
        "既存Moat、Transformation、Future Moat、Valuation、Momentum、Riskを統合評価した。",
        size=23,
    )
    pdf.text("本資料は日経STOCKリーグ用の調査材料であり、個別の投資助言ではない。", size=21, fill="#555555")

    pdf.heading("1. スクリーニング", level=1)
    pdf.text(
        "BEYOND BUFFETT企業を、既存の競争優位だけでなく、資本効率改善・事業構造改革・AI時代の新しい堀によって"
        "競争優位が進化する企業と定義した。スコアは全社を同じ物差しで標準化し、最終段階で業種・カテゴリ分散を加えた。",
        size=22,
    )
    summary_rows = [[_screening_stage_label(r.stage), f"{int(r['count']):,}"] for _, r in summary.iterrows()]
    pdf.table(["段階", "社数"], summary_rows, [500, 220], font_size=20)
    pdf.text(
        f"EDINET取得は有価証券報告書候補 {len(edinet):,} 件、会社数 {edinet['code'].nunique():,} 社。"
        f"XBRL ZIP取得成功は {int(download_status['ok'].sum()):,}/{len(download_status):,} 件。"
        f"有報が十分に見つからない銘柄は {len(missing):,} 社としてログ化した。",
        size=22,
    )

    pdf.heading("2. スコア設計", level=1)
    pdf.text(
        "Adjusted BB Score = 0.30×Moat + 0.25×Transformation + 0.30×Future Moat + 0.15×Valuation "
        "+ 0.10×Momentum - 0.10×Risk。",
        size=22,
    )
    pdf.text(
        "Moatは収益性・キャッシュ創出・安定性・競争地位、Transformationは低PBR/低PER・成長・配当、"
        "Future MoatはAIインフラ、半導体、データ/ソフトウェア、セキュリティ、無形投資を評価した。",
        size=22,
    )
    top_rows = []
    for _, row in top80.head(12).iterrows():
        top_rows.append(
            [
                str(row["code"]),
                shorten(_display_name(row), width=18, placeholder="…"),
                str(row["category"]),
                _num(row["adjusted_bb_score"], 3),
            ]
        )
    pdf.table(["コード", "企業名", "カテゴリ", "Score"], top_rows, [130, 450, 280, 130], font_size=18)
    pdf.image_file(config.reports_figures_dir / "score_distribution.png", max_height=430)

    pdf.heading("3. ポートフォリオ構成", level=1)
    invested = portfolio["actual_investment"].sum()
    cash = portfolio["cash_remaining"].iloc[0] if "cash_remaining" in portfolio else config.total_capital - invested
    pdf.text(
        f"投資額は {config.total_capital:,} 円、20銘柄、1株単位。Adjusted BB Scoreを正値化して加重し、"
        f"1銘柄上限 {config.max_weight * 100:.0f}% を適用した。実投資額は {_yen(invested)}、残現金は {_yen(cash)}。",
        size=22,
    )
    alloc_rows = []
    for _, row in portfolio.iterrows():
        alloc_rows.append(
            [
                str(row["code"]),
                shorten(row["企業名"], width=16, placeholder="…"),
                str(row["category"]).replace(" Moat", ""),
                _pct(row["actual_weight"], 2),
                _yen(row["actual_investment"]),
                str(int(row["shares"])),
            ]
        )
    pdf.table(["コード", "企業名", "分類", "比率", "投資額", "株数"], alloc_rows, [115, 420, 185, 120, 205, 95], font_size=17)
    pdf.image_file(config.reports_figures_dir / "category_allocation.png", max_height=420)
    pdf.image_file(config.reports_figures_dir / "sector_allocation.png", max_height=560)

    pdf.heading("4. 20銘柄の選定理由", level=1)
    for _, row in portfolio.iterrows():
        pdf.text(
            f"{row['code']} {row['企業名']}（{row['category']}、{_pct(row['actual_weight'], 2)}）: "
            f"{row['selection_reason']} 主なリスクは{row['main_risk']}",
            size=19,
            gap=6,
        )

    pdf.heading("5. パフォーマンス分析", level=1)
    perf_rows = []
    for _, row in performance.iterrows():
        perf_rows.append(
            [
                str(row["name"]),
                _pct(row["cumulative_return"], 2),
                _pct(row["annualized_return"], 2),
                _pct(row["annualized_volatility"], 2),
                _num(row["sharpe_ratio"], 2),
                _pct(row["max_drawdown"], 2),
                _num(row.get("capm_beta"), 2),
                _pct(row.get("capm_alpha"), 2),
            ]
        )
    pdf.table(["対象", "累積", "年率", "Vol", "Sharpe", "MaxDD", "β", "α"], perf_rows, [180, 130, 130, 130, 130, 130, 90, 130], font_size=18)
    pdf.text(
        "バックテストではポートフォリオがTOPIX proxyおよび日経平均を上回った。ただし、半導体・電力・金融・景気敏感株を含むため、"
        "高リターンは一定の価格変動リスクとセットで解釈する必要がある。",
        size=22,
    )
    pdf.image_file(config.reports_figures_dir / "cumulative_return.png", max_height=520)
    pdf.image_file(config.reports_figures_dir / "drawdown.png", max_height=430)
    pdf.image_file(config.reports_figures_dir / "contribution_by_stock.png", max_height=560)
    pdf.image_file(config.reports_figures_dir / "risk_return_scatter.png", max_height=500)

    pdf.heading("6. 結論と限界", level=1)
    pdf.text(
        "本ポートフォリオは、Core Moatの安定性、Transformation Moatの再評価余地、Future Moatの成長性を混ぜることで、"
        "従来のバフェット型投資を日本株・AI時代向けに拡張する設計になった。"
        "一方で、無料データの欠損、EDINET項目の標準化限界、生存者バイアス、過去リターンに依存するモメンタム評価には注意が必要である。",
        size=22,
    )

    output = config.reports_draft_dir / "beyond_buffett_screening_portfolio_analysis.pdf"
    pdf.save(output)
    logger.info("Wrote %s", output)
    return output


def main() -> None:
    generate_pdf(load_config())


if __name__ == "__main__":
    main()
