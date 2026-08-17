import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const data = JSON.parse(await fs.readFile("../workbook_data.json", "utf8"));
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "User" });

const C = {
  navy: "#0B1F3A",
  teal: "#007F7B",
  cyan: "#DDF4F2",
  blue: "#DCEBFA",
  green: "#DCFCE7",
  greenText: "#166534",
  yellow: "#FFF4CC",
  red: "#FDE2E2",
  redText: "#B42318",
  gray: "#F3F4F6",
  grayText: "#475467",
  white: "#FFFFFF",
  black: "#101828",
  border: "#D0D5DD",
};

function title(sheet, range, text, subtitle) {
  sheet.showGridLines = false;
  sheet.getRange(range).merge();
  const anchor = range.split(":")[0];
  sheet.getRange(anchor).values = [[text]];
  sheet.getRange(range).format = {
    fill: C.navy,
    font: { color: C.white, bold: true, size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 30;
  if (subtitle) {
    const startRow = Number(anchor.match(/\d+/)[0]) + 2;
    sheet.getRange(`A${startRow}:J${startRow}`).merge();
    sheet.getRange(`A${startRow}`).values = [[subtitle]];
    sheet.getRange(`A${startRow}:J${startRow}`).format = {
      font: { color: C.grayText, italic: true, size: 10 },
      wrapText: true,
    };
    sheet.getRange(`A${startRow}:J${startRow}`).format.rowHeight = 28;
  }
}

function headerFormat(range) {
  range.format = {
    fill: C.teal,
    font: { color: C.white, bold: true, size: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: C.border },
  };
  range.format.rowHeight = 30;
}

function sectionHeader(sheet, range, text) {
  sheet.getRange(range).merge();
  const anchor = range.split(":")[0];
  sheet.getRange(anchor).values = [[text]];
  sheet.getRange(range).format = {
    fill: C.navy,
    font: { color: C.white, bold: true, size: 11 },
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 22;
}

function setWidths(sheet, widths) {
  for (const [col, width] of Object.entries(widths)) {
    sheet.getRange(`${col}:${col}`).format.columnWidth = width;
  }
}

function linkFormula(rawRow, rawCol) {
  return `='全銘柄'!${rawCol}${rawRow}`;
}

function refsMatrix(rows, cols) {
  return rows.map((rawRow) => cols.map((col) => linkFormula(rawRow, col)));
}

const settings = workbook.worksheets.add("設定");
title(settings, "A1:E2", "10倍株スクリーニング — 設定", "青字セルは変更可能。変更すると『全銘柄』と集計数が再計算されます（条件別の抽出行そのものは作成時点のスナップショット）。");
settings.getRange("A5:E5").values = [["設定項目", "値", "単位", "用途", "初期値の根拠"]];
headerFormat(settings.getRange("A5:E5"));
settings.getRange("A6:E14").values = [
  ["各年売上成長率閾値", 0.20, "%", "条件① 厳格", "画像の20%以上"],
  ["4年売上CAGR閾値", 0.20, "%", "条件① 代替", "解釈差の感度分析"],
  ["営業利益率閾値", 0.10, "%", "条件②", "画像の10%以上"],
  ["上場後年数上限", 5, "年", "条件③", "画像の5年以内"],
  ["分析基準日", new Date("2026-08-14T00:00:00"), "日付", "条件③の判定", "この分析の基準日"],
  ["流動性警告閾値", 20000000, "円/日", "購入時の補助警告", "既存パイプライン基準"],
  ["年率ボラ警告閾値", 0.60, "%", "購入時の補助警告", "高ボラ警告"],
  ["最大下落率警告閾値", -0.60, "%", "購入時の補助警告", "大幅下落警告"],
  ["概算PSR警告閾値", 15, "倍", "購入時の補助警告", "高評価警告"],
];
settings.getRange("B6:B14").format.font = { color: "#0000FF" };
settings.getRange("B6:B8").format.numberFormat = "0.0%";
settings.getRange("B10").format.numberFormat = "yyyy-mm-dd";
settings.getRange("B11").format.numberFormat = "#,##0";
settings.getRange("B12:B13").format.numberFormat = "0.0%";
settings.getRange("B14").format.numberFormat = "0.0x";
settings.getRange("A16:E19").values = [
  ["判定ルール", "定義", "主分析での扱い", null, null],
  ["条件① 厳格", "5期売上から計算した4つの前年比がすべて閾値以上", "主ランキング", null, null],
  ["条件① CAGR", "5期の最初と最後から計算した4年CAGRが閾値以上", "感度分析。途中減収でも通過し得る", null, null],
  ["条件④ 厳格", "最新有報の代表者・社長・CEO氏名が大株主第1位と一致", "主ランキング。資産管理会社経由は拾えない場合あり", null, null],
];
settings.getRange("A16:E16").format = { fill: C.gray, font: { bold: true, color: C.black } };
settings.getRange("A16:E19").format.wrapText = true;
settings.getRange("A17:E19").format.rowHeight = 48;
settings.getRange("A16:E19").format.borders = { preset: "outside", style: "thin", color: C.border };
settings.getRange("A21:E25").values = [
  ["色の凡例", "青字", "編集可能な設定", null, null],
  [null, "黒字", "数式・計算", null, null],
  [null, "緑字", "他シート参照", null, null],
  [null, "黄背景", "要確認・注意", null, null],
  [null, "赤背景", "不通過・警告", null, null],
];
settings.getRange("B21").format.font = { color: "#0000FF" };
settings.getRange("B22").format.font = { color: C.black };
settings.getRange("B23").format.font = { color: "#008000" };
settings.getRange("B24").format.fill = C.yellow;
settings.getRange("B25").format.fill = C.red;
settings.freezePanes.freezeRows(5);
setWidths(settings, { A: 25, B: 18, C: 14, D: 28, E: 34 });
workbook.comments.addThread({ cell: settings.getRange("B6") }, "画像条件①の厳格解釈です。20% = 0.20 として入力します。");
workbook.comments.addThread({ cell: settings.getRange("B9") }, "上場後年数は分析基準日から遡って判定します。");

const all = workbook.worksheets.add("全銘柄");
all.showGridLines = false;
const allHeaders = [
  "順位", "コード", "Ticker", "会社名", "市場", "33業種",
  "売上4年前\n百万円", "売上3年前\n百万円", "売上2年前\n百万円", "売上1年前\n百万円", "最新売上\n百万円",
  "YoY①", "YoY②", "YoY③", "YoY④", "4年CAGR", "最新営業利益\n百万円", "営業利益率",
  "上場日", "上場日ソース", "筆頭株主", "筆頭比率", "代表者等", "C1 厳格", "C1 CAGR", "C2 利益率", "C3 5年内", "C4 代表=筆頭", "C4 オーナーproxy",
  "厳格重複", "CAGR重複", "CAGR+proxy重複", "株価初日", "doc_id", "売上XBRL概念", "営業利益XBRL概念", "最新決算期", "5期日数",
  "発行済株式proxy", "株価", "概算時価総額", "概算PSR", "60日平均売買代金", "年率ボラ", "最大下落率", "投資適格", "除外理由", "既存BBスコア", "既存順位", "既存カテゴリ", "購入補助警告", "有報提出日", "沿革上場日", "一致代表者", "会社名（日）", "規模区分"
];
all.getRange(`A1:BD1`).values = [allHeaders];
headerFormat(all.getRange("A1:BD1"));

const rawValues = data.all.map((r) => [
  r.screen_rank, r.code, r.ticker, r.company_name, r.market, r.sector_33,
  r.revenue_p0 == null ? null : r.revenue_p0 / 1e6,
  r.revenue_p1 == null ? null : r.revenue_p1 / 1e6,
  r.revenue_p2 == null ? null : r.revenue_p2 / 1e6,
  r.revenue_p3 == null ? null : r.revenue_p3 / 1e6,
  r.revenue_p4 == null ? null : r.revenue_p4 / 1e6,
  null, null, null, null, null,
  r.operating_income_current == null ? null : r.operating_income_current / 1e6,
  null,
  r.listing_date_for_test ? new Date(`${r.listing_date_for_test}T00:00:00`) : null,
  r.listing_date_source, r.top_shareholder_name, r.top_shareholder_ratio, r.leader_names,
  null, null, null, null, r.c4_leader_top_holder_strict, r.c4_owner_proxy_broad,
  null, null, null,
  r.first_price_date ? new Date(`${r.first_price_date}T00:00:00`) : null,
  r.doc_id, r.revenue_concept, r.operating_income_concept,
  r.period_end_latest ? new Date(`${r.period_end_latest}T00:00:00`) : null,
  r.fiscal_period_days, r.shares_outstanding_pti, r.close, null, null,
  r.avg_trading_value_60d, r.annual_volatility, r.max_drawdown, r.investment_eligible,
  r.investment_exclusion_reasons, r.adjusted_bb_score, r.score_rank, r.category, r.purchase_risk_notes,
  r.submit_date, r.history_listing_date ? new Date(`${r.history_listing_date}T00:00:00`) : null,
  r.matched_leader, r.company_name_ja, r.scale_category,
]);
const allLastRow = rawValues.length + 1;
all.getRange(`A2:BD${allLastRow}`).values = rawValues;
const formulaRows = [];
for (let row = 2; row <= allLastRow; row++) {
  formulaRows.push([
    `=IFERROR(H${row}/G${row}-1,"")`,
    `=IFERROR(I${row}/H${row}-1,"")`,
    `=IFERROR(J${row}/I${row}-1,"")`,
    `=IFERROR(K${row}/J${row}-1,"")`,
    `=IFERROR((K${row}/G${row})^(1/4)-1,"")`,
  ]);
}
all.getRange(`L2:P${allLastRow}`).formulas = formulaRows;
all.getRange(`R2:R${allLastRow}`).formulas = Array.from({ length: rawValues.length }, (_, i) => [`=IFERROR(Q${i + 2}/K${i + 2},"")`]);
all.getRange(`X2:AA${allLastRow}`).formulas = Array.from({ length: rawValues.length }, (_, i) => {
  const row = i + 2;
  return [
    `=AND(COUNT(L${row}:O${row})=4,L${row}>='設定'!$B$6,M${row}>='設定'!$B$6,N${row}>='設定'!$B$6,O${row}>='設定'!$B$6)`,
    `=AND(COUNT(G${row}:K${row})=5,P${row}>='設定'!$B$7)`,
    `=AND(ISNUMBER(R${row}),R${row}>='設定'!$B$8)`,
    `=AND(ISNUMBER(S${row}),S${row}>=DATE(YEAR('設定'!$B$10)-'設定'!$B$9,MONTH('設定'!$B$10),DAY('設定'!$B$10)))`,
  ];
});
all.getRange(`AD2:AF${allLastRow}`).formulas = Array.from({ length: rawValues.length }, (_, i) => {
  const row = i + 2;
  return [
    `=IF(X${row},1,0)+IF(Z${row},1,0)+IF(AA${row},1,0)+IF(AB${row},1,0)`,
    `=IF(Y${row},1,0)+IF(Z${row},1,0)+IF(AA${row},1,0)+IF(AB${row},1,0)`,
    `=IF(Y${row},1,0)+IF(Z${row},1,0)+IF(AA${row},1,0)+IF(AC${row},1,0)`,
  ];
});
all.getRange(`AO2:AP${allLastRow}`).formulas = Array.from({ length: rawValues.length }, (_, i) => {
  const row = i + 2;
  return [`=IFERROR(AM${row}*AN${row},"")`, `=IFERROR(AO${row}/(K${row}*1000000),"")`];
});
all.getRange(`G2:K${allLastRow}`).format.numberFormat = "#,##0;[Red](#,##0);-";
all.getRange(`L2:P${allLastRow}`).format.numberFormat = "0.0%;[Red](0.0%);-";
all.getRange(`Q2:Q${allLastRow}`).format.numberFormat = "#,##0;[Red](#,##0);-";
all.getRange(`R2:R${allLastRow}`).format.numberFormat = "0.0%;[Red](0.0%);-";
all.getRange(`S2:S${allLastRow}`).format.numberFormat = "yyyy-mm-dd";
all.getRange(`V2:V${allLastRow}`).format.numberFormat = "0.0%";
all.getRange(`AG2:AG${allLastRow}`).format.numberFormat = "yyyy-mm-dd";
all.getRange(`AK2:AK${allLastRow}`).format.numberFormat = "yyyy-mm-dd";
all.getRange(`AM2:AO${allLastRow}`).format.numberFormat = "#,##0;[Red](#,##0);-";
all.getRange(`AP2:AP${allLastRow}`).format.numberFormat = "0.0x";
all.getRange(`AQ2:AQ${allLastRow}`).format.numberFormat = "#,##0";
all.getRange(`AR2:AS${allLastRow}`).format.numberFormat = "0.0%;[Red](0.0%);-";
all.getRange(`AV2:AV${allLastRow}`).format.numberFormat = "0.00";
all.getRange(`AZ2:AZ${allLastRow}`).format.numberFormat = "yyyy-mm-dd hh:mm";
all.getRange(`BA2:BA${allLastRow}`).format.numberFormat = "yyyy-mm-dd";
all.getRange(`A2:BD${allLastRow}`).format.font = { color: C.black, size: 9 };
all.getRange(`X2:AA${allLastRow}`).format.font = { color: C.black };
all.getRange(`AB2:AC${allLastRow}`).format.font = { color: C.black };
all.getRange(`AD2:AF${allLastRow}`).conditionalFormats.add("colorScale", { colors: [C.red, C.yellow, C.green] });
all.getRange(`X2:AC${allLastRow}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "TRUE", format: { fill: C.green, font: { color: C.greenText, bold: true } } });
all.getRange(`X2:AC${allLastRow}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "FALSE", format: { fill: C.red, font: { color: C.redText } } });
all.getRange(`AT2:AT${allLastRow}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "FALSE", format: { fill: C.red, font: { color: C.redText, bold: true } } });
all.getRange(`AY2:AY${allLastRow}`).conditionalFormats.add("containsText", { text: "目立つ機械的警告なし", format: { fill: C.green, font: { color: C.greenText } } });
for (const riskText of ["不通過", "ボラティリティ", "最大下落", "売買代金", "PSR"]) {
  all.getRange(`AY2:AY${allLastRow}`).conditionalFormats.add("containsText", { text: riskText, format: { fill: C.yellow, font: { color: C.black } } });
}
all.freezePanes.freezeRows(1);
all.freezePanes.freezeColumns(4);
setWidths(all, {
  A: 8, B: 9, C: 11, D: 28, E: 22, F: 24, G: 14, H: 14, I: 14, J: 14, K: 14,
  L: 10, M: 10, N: 10, O: 10, P: 11, Q: 15, R: 11, S: 12, T: 22, U: 26, V: 10,
  W: 30, X: 10, Y: 10, Z: 10, AA: 10, AB: 12, AC: 14, AD: 9, AE: 9, AF: 12,
  AG: 12, AH: 12, AI: 34, AJ: 32, AK: 12, AL: 22, AM: 15, AN: 10, AO: 16, AP: 10,
  AQ: 17, AR: 10, AS: 11, AT: 10, AU: 30, AV: 12, AW: 10, AX: 20, AY: 58, AZ: 18,
  BA: 12, BB: 18, BC: 28, BD: 18,
});

const summary = workbook.worksheets.add("サマリー");
title(summary, "A1:L2", "10倍株条件スクリーニング — サマリー", `母集団 ${data.checks.universe_rows.toLocaleString()}社｜JPX基準 ${data.universe_effective}｜株価基準 ${data.price_as_of}｜分析基準 ${data.as_of}`);
summary.getRange("A5:L6").merge();
summary.getRange("A5").values = [["注意：これは『買いリスト』ではありません。4条件の一致度を機械判定した探索用リストです。価格、事業の持続性、希薄化、顧客集中、会計変更、経営者の売却予定を別途確認してください。"]];
summary.getRange("A5:L6").format = { fill: C.yellow, font: { color: C.black, bold: true }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: "#D6B656" } };

sectionHeader(summary, "A8:L8", "主要集計");
summary.getRange("A9:B14").values = [
  ["母集団", null], ["C1 厳格（各年+20%）", null], ["C1 CAGR（4年+20%）", null],
  ["C2 営業利益率10%", null], ["C3 上場5年以内", null], ["C4 代表者=筆頭株主", null],
];
summary.getRange("B9:B14").formulas = [
  [`=COUNTA('全銘柄'!$B$2:$B$${allLastRow})`],
  [`=COUNTIF('全銘柄'!$X$2:$X$${allLastRow},1)`],
  [`=COUNTIF('全銘柄'!$Y$2:$Y$${allLastRow},1)`],
  [`=COUNTIF('全銘柄'!$Z$2:$Z$${allLastRow},1)`],
  [`=COUNTIF('全銘柄'!$AA$2:$AA$${allLastRow},1)`],
  [`=COUNTIF('全銘柄'!$AB$2:$AB$${allLastRow},1)`],
];
summary.getRange("D9:E14").values = [
  ["厳格4条件一致", null], ["CAGR4条件一致", null], ["厳格3条件以上", null],
  ["CAGR3条件以上", null], ["5期売上カバー", null], ["営業利益率カバー", null],
];
summary.getRange("E9:E14").formulas = [
  [`=COUNTIF('全銘柄'!$AD$2:$AD$${allLastRow},4)`],
  [`=COUNTIF('全銘柄'!$AE$2:$AE$${allLastRow},4)`],
  [`=COUNTIF('全銘柄'!$AD$2:$AD$${allLastRow},">=3")`],
  [`=COUNTIF('全銘柄'!$AE$2:$AE$${allLastRow},">=3")`],
  [`=COUNTIFS('全銘柄'!$G$2:$G$${allLastRow},"<>",'全銘柄'!$H$2:$H$${allLastRow},"<>",'全銘柄'!$I$2:$I$${allLastRow},"<>",'全銘柄'!$J$2:$J$${allLastRow},"<>",'全銘柄'!$K$2:$K$${allLastRow},"<>")`],
  [`=COUNT('全銘柄'!$R$2:$R$${allLastRow})`],
];
for (const range of ["A9:B14", "D9:E14"]) {
  summary.getRange(range).format = { fill: C.gray, borders: { preset: "outside", style: "thin", color: C.border } };
}
summary.getRange("B9:B14").format.font = { color: "#008000", bold: true, size: 14 };
summary.getRange("E9:E14").format.font = { color: "#008000", bold: true, size: 14 };
summary.getRange("A16:B21").values = [
  ["条件", "該当社数"], ["C1 厳格", null], ["C1 CAGR", null], ["C2 利益率", null], ["C3 上場5年", null], ["C4 代表=筆頭", null],
];
summary.getRange("B17:B21").formulas = [["=B10"], ["=B11"], ["=B12"], ["=B13"], ["=B14"]];
headerFormat(summary.getRange("A16:B16"));
const conditionChart = summary.charts.add("bar", summary.getRange("A16:B21"));
conditionChart.title = "条件別該当社数（3,649社）";
conditionChart.hasLegend = false;
conditionChart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 9 } };
conditionChart.yAxis = { numberFormatCode: "#,##0" };
conditionChart.setPosition("D16", "L30");

sectionHeader(summary, "A32:L32", "厳格4条件一致 13社（成長率順。推奨順位ではありません）");
const sumHeaders = ["順位", "コード", "会社名", "4年CAGR", "営業利益率", "上場日", "筆頭比率", "概算時価総額\n十億円", "概算PSR", "60日売買代金\n百万円", "投資適格", "購入補助警告"];
summary.getRange("A33:L33").values = [sumHeaders];
headerFormat(summary.getRange("A33:L33"));
const strictRows = data.strict4_rows;
const sumFormulas = strictRows.map((rawRow) => [
  linkFormula(rawRow, "A"), linkFormula(rawRow, "B"), linkFormula(rawRow, "D"), linkFormula(rawRow, "P"), linkFormula(rawRow, "R"),
  linkFormula(rawRow, "S"), linkFormula(rawRow, "V"), `='全銘柄'!AO${rawRow}/1000000000`, linkFormula(rawRow, "AP"),
  `='全銘柄'!AQ${rawRow}/1000000`, linkFormula(rawRow, "AT"), linkFormula(rawRow, "AY"),
]);
summary.getRange(`A34:L${33 + strictRows.length}`).formulas = sumFormulas;
summary.getRange(`A34:L${33 + strictRows.length}`).format.font = { color: "#008000", size: 9 };
summary.getRange(`D34:E${33 + strictRows.length}`).format.numberFormat = "0.0%";
summary.getRange(`F34:F${33 + strictRows.length}`).format.numberFormat = "yyyy-mm-dd";
summary.getRange(`G34:G${33 + strictRows.length}`).format.numberFormat = "0.0%";
summary.getRange(`H34:H${33 + strictRows.length}`).format.numberFormat = "0.0";
summary.getRange(`I34:I${33 + strictRows.length}`).format.numberFormat = "0.0x";
summary.getRange(`J34:J${33 + strictRows.length}`).format.numberFormat = "#,##0.0";
summary.getRange(`L34:L${33 + strictRows.length}`).format.wrapText = true;
summary.getRange(`K34:K${33 + strictRows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "FALSE", format: { fill: C.red, font: { color: C.redText, bold: true } } });
summary.getRange(`L34:L${33 + strictRows.length}`).conditionalFormats.add("containsText", { text: "目立つ機械的警告なし", format: { fill: C.green, font: { color: C.greenText } } });
for (const riskText of ["不通過", "ボラティリティ", "最大下落", "売買代金", "PSR"]) {
  summary.getRange(`L34:L${33 + strictRows.length}`).conditionalFormats.add("containsText", { text: riskText, format: { fill: C.yellow, font: { color: C.black } } });
}
summary.getRange(`A34:L${33 + strictRows.length}`).format.rowHeight = 32;
summary.freezePanes.freezeRows(8);
setWidths(summary, { A: 22, B: 9, C: 25, D: 20, E: 12, F: 12, G: 11, H: 14, I: 10, J: 15, K: 10, L: 52 });

function buildLinkedListSheet(name, titleText, subtitle, rows, headers, rawCols, widths, formats = {}) {
  const sheet = workbook.worksheets.add(name);
  title(sheet, `A1:${String.fromCharCode(64 + headers.length)}2`, titleText, subtitle);
  sheet.getRange(`A5:${String.fromCharCode(64 + headers.length)}5`).values = [headers];
  headerFormat(sheet.getRange(`A5:${String.fromCharCode(64 + headers.length)}5`));
  if (rows.length) {
    sheet.getRange(`A6:${String.fromCharCode(64 + headers.length)}${5 + rows.length}`).formulas = refsMatrix(rows, rawCols);
    sheet.getRange(`A6:${String.fromCharCode(64 + headers.length)}${5 + rows.length}`).format.font = { color: "#008000", size: 9 };
    for (const [range, fmt] of Object.entries(formats)) {
      sheet.getRange(range.replaceAll("{last}", String(5 + rows.length))).format.numberFormat = fmt;
    }
  }
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(3);
  setWidths(sheet, widths);
  return sheet;
}

const candidates = buildLinkedListSheet(
  "候補ランキング",
  "重複3条件以上 — 候補ランキング",
  "厳格・CAGR・オーナーproxyのいずれかで3条件以上の128社。全条件値と補助警告を併読してください。",
  data.candidate_rows,
  ["順位", "コード", "会社名", "業種", "厳格重複", "CAGR重複", "C1厳格", "4年CAGR", "利益率", "上場日", "筆頭比率", "代表=筆頭", "時価総額円", "PSR", "売買代金円", "年率ボラ", "最大下落", "投資適格", "購入補助警告", "doc_id"],
  ["A", "B", "D", "F", "AD", "AE", "X", "P", "R", "S", "V", "AB", "AO", "AP", "AQ", "AR", "AS", "AT", "AY", "AH"],
  { A: 8, B: 9, C: 28, D: 25, E: 10, F: 10, G: 10, H: 11, I: 11, J: 12, K: 11, L: 12, M: 16, N: 10, O: 16, P: 11, Q: 11, R: 10, S: 58, T: 12 },
  { "H6:I{last}": "0.0%", "J6:J{last}": "yyyy-mm-dd", "K6:K{last}": "0.0%", "M6:M{last}": "#,##0", "N6:N{last}": "0.0x", "O6:O{last}": "#,##0", "P6:Q{last}": "0.0%" },
);
candidates.getRange(`E6:F${5 + data.candidate_rows.length}`).conditionalFormats.add("colorScale", { colors: [C.red, C.yellow, C.green] });
candidates.getRange(`R6:R${5 + data.candidate_rows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "FALSE", format: { fill: C.red, font: { color: C.redText, bold: true } } });
candidates.getRange(`S6:S${5 + data.candidate_rows.length}`).format.wrapText = true;
candidates.getRange(`A6:T${5 + data.candidate_rows.length}`).format.rowHeight = 26;

const c1 = buildLinkedListSheet(
  "C1_売上成長", "条件① — 売上成長", "CAGR20%以上の370社。『厳格』=TRUEは4つの前年比がすべて20%以上（61社）。",
  data.c1_rows,
  ["順位", "コード", "会社名", "業種", "厳格", "CAGR", "YoY①", "YoY②", "YoY③", "YoY④", "最新売上百万円", "doc_id"],
  ["A", "B", "D", "F", "X", "P", "L", "M", "N", "O", "K", "AH"],
  { A: 8, B: 9, C: 28, D: 25, E: 10, F: 11, G: 10, H: 10, I: 10, J: 10, K: 16, L: 12 },
  { "F6:J{last}": "0.0%", "K6:K{last}": "#,##0" },
);
c1.getRange(`E6:E${5 + data.c1_rows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "TRUE", format: { fill: C.green, font: { color: C.greenText, bold: true } } });

buildLinkedListSheet(
  "C2_営業利益率", "条件② — 営業利益率10%以上", "最新有報の連結売上・営業利益を優先。金融業は営業収益定義が一般事業会社と異なるため要注意。",
  data.c2_rows,
  ["順位", "コード", "会社名", "業種", "営業利益率", "最新売上百万円", "営業利益百万円", "投資適格", "除外理由", "doc_id"],
  ["A", "B", "D", "F", "R", "K", "Q", "AT", "AU", "AH"],
  { A: 8, B: 9, C: 28, D: 25, E: 12, F: 16, G: 17, H: 10, I: 35, J: 12 },
  { "E6:E{last}": "0.0%", "F6:G{last}": "#,##0" },
);

buildLinkedListSheet(
  "C3_上場5年", "条件③ — 上場から5年以内", "基準日2026-08-14。ローカル価格初日が閾値後ならそれを優先し、それ以外は有報『沿革』の上場日を利用。",
  data.c3_rows,
  ["順位", "コード", "会社名", "市場", "上場日", "ソース", "厳格重複", "CAGR重複", "売買代金円", "doc_id"],
  ["A", "B", "D", "E", "S", "T", "AD", "AE", "AQ", "AH"],
  { A: 8, B: 9, C: 28, D: 24, E: 12, F: 24, G: 10, H: 10, I: 18, J: 12 },
  { "E6:E{last}": "yyyy-mm-dd", "I6:I{last}": "#,##0" },
);

const c4 = buildLinkedListSheet(
  "C4_オーナー", "条件④ — オーナー企業 / 社長が筆頭株主", "厳格=代表者・社長・CEOと筆頭株主名が一致。proxyは『筆頭株主が個人』も含むため、資産管理会社・実質支配関係は必ず手動確認。",
  data.c4_rows,
  ["順位", "コード", "会社名", "代表者等", "筆頭株主", "筆頭比率", "厳格", "proxy", "厳格重複", "CAGR重複", "doc_id"],
  ["A", "B", "D", "W", "U", "V", "AB", "AC", "AD", "AE", "AH"],
  { A: 8, B: 9, C: 28, D: 34, E: 28, F: 11, G: 10, H: 10, I: 10, J: 10, K: 12 },
  { "F6:F{last}": "0.0%" },
);
c4.getRange(`G6:G${5 + data.c4_rows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "TRUE", format: { fill: C.green, font: { color: C.greenText, bold: true } } });
c4.getRange(`G6:G${5 + data.c4_rows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "FALSE", format: { fill: C.yellow, font: { color: C.black } } });

const overlap = workbook.worksheets.add("重複分析");
title(overlap, "A1:H2", "条件の重複分析", "主表はC1=CAGR、C2=利益率、C3=上場5年、C4=代表者が筆頭株主。対角は各条件の該当社数。");
sectionHeader(overlap, "A5:F5", "ペアワイズ重複社数");
overlap.getRange("A6:E10").values = [
  ["条件", "C1 CAGR", "C2 利益率", "C3 上場5年", "C4 代表=筆頭"],
  ["C1 CAGR", null, null, null, null],
  ["C2 利益率", null, null, null, null],
  ["C3 上場5年", null, null, null, null],
  ["C4 代表=筆頭", null, null, null, null],
];
headerFormat(overlap.getRange("A6:E6"));
const cols = ["Y", "Z", "AA", "AB"];
const matrixFormulas = [];
for (let i = 0; i < 4; i++) {
  const row = [];
  for (let j = 0; j < 4; j++) {
    row.push(`=COUNTIFS('全銘柄'!$${cols[i]}$2:$${cols[i]}$${allLastRow},1,'全銘柄'!$${cols[j]}$2:$${cols[j]}$${allLastRow},1)`);
  }
  matrixFormulas.push(row);
}
overlap.getRange("B7:E10").formulas = matrixFormulas;
overlap.getRange("B7:E10").format.font = { color: "#008000", bold: true };
overlap.getRange("B7:E10").conditionalFormats.add("colorScale", { colors: [C.white, C.cyan, C.teal] });
sectionHeader(overlap, "A13:F13", "重複数分布（CAGR版）");
overlap.getRange("A14:B19").values = [["重複数", "企業数"], [0, null], [1, null], [2, null], [3, null], [4, null]];
headerFormat(overlap.getRange("A14:B14"));
overlap.getRange("B15:B19").formulas = [0, 1, 2, 3, 4].map((n) => [`=COUNTIF('全銘柄'!$AE$2:$AE$${allLastRow},${n})`]);
overlap.getRange("D14:H20").merge();
overlap.getRange("D14").values = [["読み方\n・CAGR版4条件一致：途中減収を許容するため28社\n・厳格版4条件一致：4年連続で各年20%以上の13社\n・C4 proxyは個人筆頭株主を含むため、厳格版より広い\n\n重複が多くても将来の株価上昇を保証しません。"]];
overlap.getRange("D14:H20").format = { fill: C.yellow, wrapText: true, verticalAlignment: "top", borders: { preset: "outside", style: "thin", color: C.border } };
sectionHeader(overlap, "A23:F23", "ペアワイズ重複社数（厳格版：C1は4年連続で各年20%以上）");
overlap.getRange("A24:E28").values = [
  ["条件", "C1 厳格", "C2 利益率", "C3 上場5年", "C4 代表=筆頭"],
  ["C1 厳格", null, null, null, null],
  ["C2 利益率", null, null, null, null],
  ["C3 上場5年", null, null, null, null],
  ["C4 代表=筆頭", null, null, null, null],
];
headerFormat(overlap.getRange("A24:E24"));
const strictCols = ["X", "Z", "AA", "AB"];
const strictMatrixFormulas = [];
for (let i = 0; i < 4; i++) {
  const row = [];
  for (let j = 0; j < 4; j++) {
    row.push(`=COUNTIFS('全銘柄'!$${strictCols[i]}$2:$${strictCols[i]}$${allLastRow},1,'全銘柄'!$${strictCols[j]}$2:$${strictCols[j]}$${allLastRow},1)`);
  }
  strictMatrixFormulas.push(row);
}
overlap.getRange("B25:E28").formulas = strictMatrixFormulas;
overlap.getRange("B25:E28").format.font = { color: "#008000", bold: true };
overlap.getRange("B25:E28").conditionalFormats.add("colorScale", { colors: [C.white, C.cyan, C.teal] });
sectionHeader(overlap, "A31:C31", "重複数分布（厳格版）");
overlap.getRange("A32:B37").values = [["重複数", "企業数"], [0, null], [1, null], [2, null], [3, null], [4, null]];
headerFormat(overlap.getRange("A32:B32"));
overlap.getRange("B33:B37").formulas = [0, 1, 2, 3, 4].map((n) => [`=COUNTIF('全銘柄'!$AD$2:$AD$${allLastRow},${n})`]);
setWidths(overlap, { A: 22, B: 14, C: 14, D: 18, E: 18, F: 14, G: 14, H: 14 });

const audit = workbook.worksheets.add("監査");
title(audit, "A1:G2", "データ品質・モデル監査", "OKは抽出処理と代表的な数式の整合を示します。欠損は不合格ではなく『判定不能』として扱います。");
audit.getRange("A5:G5").values = [["チェック", "実績", "期待/基準", "差異", "許容", "状態", "備考"]];
headerFormat(audit.getRange("A5:G5"));
audit.getRange("A6:G13").values = [
  ["母集団行数", null, data.checks.universe_rows, null, 0, null, "JPX内国株式"],
  ["XBRL最新有報解析", data.checks.parsed_rows, data.checks.latest_docs, null, 0, null, "解析エラー0"],
  ["5期売上カバー", null, data.checks.five_year_revenue_coverage, null, 0, null, "不足はC1判定不能"],
  ["営業利益率カバー", null, data.checks.operating_margin_coverage, null, 0, null, "金融業は比較注意"],
  ["上場日識別", null, data.checks.listing_date_identified, null, 0, null, "1社は株価データ欠損"],
  ["筆頭株主識別", null, data.checks.top_shareholder_coverage, null, 0, null, "有報なし70社は欠損"],
  ["厳格4条件一致", null, data.checks.strict_four_condition_matches, null, 0, null, "主結果"],
  ["CAGR4条件一致", null, data.checks.cagr_four_condition_matches, null, 0, null, "感度分析"],
];
audit.getRange("B6:B13").formulas = [
  [`=COUNTA('全銘柄'!$B$2:$B$${allLastRow})`],
  [String(data.checks.parsed_rows)],
  [`=COUNTIFS('全銘柄'!$G$2:$G$${allLastRow},"<>",'全銘柄'!$H$2:$H$${allLastRow},"<>",'全銘柄'!$I$2:$I$${allLastRow},"<>",'全銘柄'!$J$2:$J$${allLastRow},"<>",'全銘柄'!$K$2:$K$${allLastRow},"<>")`],
  [`=COUNT('全銘柄'!$R$2:$R$${allLastRow})`],
  [`=COUNT('全銘柄'!$S$2:$S$${allLastRow})`],
  [`=COUNTA('全銘柄'!$U$2:$U$${allLastRow})`],
  [`=COUNTIF('全銘柄'!$AD$2:$AD$${allLastRow},4)`],
  [`=COUNTIF('全銘柄'!$AE$2:$AE$${allLastRow},4)`],
];
audit.getRange("D6:D13").formulas = Array.from({ length: 8 }, (_, i) => [`=B${i + 6}-C${i + 6}`]);
audit.getRange("F6:F13").formulas = Array.from({ length: 8 }, (_, i) => [`=IF(ABS(D${i + 6})<=E${i + 6},"OK","要確認")`]);
audit.getRange("F6:F13").conditionalFormats.add("containsText", { text: "OK", format: { fill: C.green, font: { color: C.greenText, bold: true } } });
audit.getRange("F6:F13").conditionalFormats.add("containsText", { text: "要確認", format: { fill: C.red, font: { color: C.redText, bold: true } } });
sectionHeader(audit, "A16:G16", "既知の限界");
audit.getRange("A17:G23").values = [
  ["1", "条件①の語義", "『過去4年間』は厳格（各年）とCAGRの両方を算出。主結果は厳格。", null, null, null, null],
  ["2", "条件④", "資産管理会社・親族・共同保有・貸株を通じた実質所有は自動確定できない。proxyは要手動確認。", null, null, null, null],
  ["3", "上場日", "価格初日を優先。有報沿革は月初で記録される場合がある。市場変更・再上場は個別確認。", null, null, null, null],
  ["4", "時価総額/PSR", "有報時点株式数×2026-06-01株価の概算。株式分割・希薄化後はずれる可能性。", null, null, null, null],
  ["5", "金融業", "営業収益と営業利益の定義が一般事業会社と異なり、利益率比較は参考値。", null, null, null, null],
  ["6", "将来性", "過去成長は将来の成長や10倍化を保証しない。バリュエーションと希薄化を別評価。", null, null, null, null],
  ["7", "株価基準", "株価・リスク・流動性は2026-06-01まで。購入時点の価格と乖離し得る。", null, null, null, null],
];
audit.getRange("A17:G23").format.wrapText = true;
audit.getRange("A17:G23").format.rowHeight = 34;
setWidths(audit, { A: 8, B: 24, C: 60, D: 12, E: 12, F: 12, G: 28 });

const sources = workbook.worksheets.add("出所");
title(sources, "A1:E2", "出所・再現情報", "各社の提出書類は『全銘柄』のdoc_idで追跡できます。外部URLは一次情報の閲覧入口です。");
sources.getRange("A5:E5").values = [["項目", "ローカルファイル", "基準日", "監査メモ", "一次情報URL"]];
headerFormat(sources.getRange("A5:E5"));
sources.getRange(`A6:E${5 + data.local_sources.length}`).values = data.local_sources.map((s) => [s.item, s.path, s.as_of, s.notes, s.url]);
sources.getRange(`A6:E${5 + data.local_sources.length}`).format.wrapText = true;
sources.getRange(`A6:E${5 + data.local_sources.length}`).format.rowHeight = 34;
sources.getRange(`E6:E${5 + data.local_sources.length}`).format.font = { color: "#0000FF", underline: true };
sources.getRange("A12:E17").values = [
  ["主要XBRL概念", "NetSalesSummaryOfBusinessResults / RevenueIFRSSummaryOfBusinessResults", "売上", "連結を優先。5期コンテキスト", ""],
  ["営業利益", "OperatingIncome / OperatingProfitLossIFRS", "最新期", "連結CurrentYearDurationを優先", ""],
  ["筆頭株主", "NameMajorShareholders + ShareholdingRatio", "最新有報", "No1MajorShareholdersMember", ""],
  ["代表者", "NameInformationAboutDirectorsAndCorporateAuditors + OfficialTitleOrPosition...", "提出日", "代表・社長・CEOを抽出", ""],
  ["上場日", "CompanyHistoryTextBlock / local first trade", "分析日", "価格初日を優先", ""],
  ["免責", "本資料は調査支援用で、投資助言ではありません", "", "購入前に最新IR・株価・需給を確認", ""],
];
sources.getRange("A12:E17").format.wrapText = true;
sources.getRange("A12:E17").format.rowHeight = 28;
setWidths(sources, { A: 24, B: 66, C: 20, D: 46, E: 46 });

// Compact inspections before rendering/export.
const inspectSummary = await workbook.inspect({
  kind: "table",
  range: "サマリー!A8:L20",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 12,
  maxChars: 8000,
});
console.log(inspectSummary.ndjson);
const inspectAudit = await workbook.inspect({
  kind: "table",
  range: "監査!A5:G13",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 7,
  maxChars: 8000,
});
console.log(inspectAudit.ndjson);
const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 8000,
});
console.log(errorScan.ndjson);

const previews = [
  ["サマリー", "A1:L46", "preview_summary.png"],
  ["設定", "A1:E25", "preview_settings.png"],
  ["候補ランキング", "A1:T32", "preview_candidates.png"],
  ["全銘柄", "A1:AY24", "preview_all.png"],
  ["C1_売上成長", "A1:L28", "preview_c1.png"],
  ["C2_営業利益率", "A1:J28", "preview_c2.png"],
  ["C3_上場5年", "A1:J28", "preview_c3.png"],
  ["C4_オーナー", "A1:K28", "preview_c4.png"],
  ["重複分析", "A1:H37", "preview_overlap.png"],
  ["監査", "A1:G23", "preview_audit.png"],
  ["出所", "A1:E17", "preview_sources.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const image = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(fileName, new Uint8Array(await image.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save("../tenbagger_screening.xlsx");
console.log("exported ../tenbagger_screening.xlsx");
