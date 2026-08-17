// スクリーニング簡易レポートの docx を組み立てる。10_build_docx.py から呼ばれる。
// レポート単体で「何をやったか」が追えるよう、用語・データ出所・式・検証まで収める。
const fs = require("fs");
const path = require("path");
const MODS = "/private/tmp/claude-501/-Users-satouryuuichi-Desktop-product-hobby-stock-league/f04bb6c3-a171-48b8-803c-40a74d574cc3/scratchpad/node_modules";
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Footer, PageNumber, ImageRun,
} = require(path.join(MODS, "docx"));

const P = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const EQ = P.eq_index ? JSON.parse(fs.readFileSync(P.eq_index, "utf8")) : {};

const FONT = "Yu Gothic";
const INK = "1B1F27";
const MUTED = "5B6373";
const ACCENT = P.theme === "established" ? "1F5B4E" : "2F4B8F";
const RULE = "C9CEDA";
const HEADFILL = P.theme === "established" ? "E6F0EC" : "EDF0F6";
const ZEBRA = "F7F8FB";
const CALLFILL = P.theme === "established" ? "E6F0EC" : "E4E9F5";

const R = AlignmentType.RIGHT;
const L = AlignmentType.LEFT;
const cellBorders = {
  top: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
  right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
};

function txt(text, o = {}) {
  return new TextRun({
    text: String(text), font: FONT, size: o.size || 18,
    bold: !!o.bold, italics: !!o.italics, color: o.color || INK,
  });
}
function para(text, o = {}) {
  return new Paragraph({
    alignment: o.align || L,
    spacing: { before: o.before ?? 0, after: o.after ?? 130, line: o.line || 300 },
    border: o.border,
    children: Array.isArray(text) ? text : [txt(text, o)],
  });
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1, spacing: { before: 380, after: 170 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 6 } },
    children: [txt(text, { size: 26, bold: true, color: ACCENT })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 115 },
    children: [txt(text, { size: 21, bold: true })],
  });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: "dots", level: 0 },
    spacing: { after: 80, line: 295 },
    children: [txt(text)],
  });
}
function num(text) {
  return new Paragraph({
    numbering: { reference: "nums", level: 0 },
    spacing: { after: 80, line: 295 },
    children: [txt(text)],
  });
}
function note(text) {
  return new Paragraph({
    spacing: { before: 110, after: 150, line: 285 },
    children: [txt(text, { size: 16, color: MUTED })],
  });
}
function callout(text) {
  return new Paragraph({
    spacing: { before: 170, after: 190, line: 300 },
    shading: { type: ShadingType.CLEAR, fill: CALLFILL, color: "auto" },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 10 } },
    indent: { left: 130, right: 130 },
    children: Array.isArray(text) ? text : [txt(text)],
  });
}
function code(lines) {
  return lines.map((l, i) => new Paragraph({
    spacing: { before: i === 0 ? 140 : 0, after: i === lines.length - 1 ? 160 : 0, line: 265 },
    shading: { type: ShadingType.CLEAR, fill: "F2F4F8", color: "auto" },
    indent: { left: 130, right: 130 },
    children: [new TextRun({ text: l || " ", font: "SFMono-Regular", size: 15, color: INK })],
  }));
}
function cell(text, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    margins: { top: 58, bottom: 58, left: 88, right: 88 },
    borders: cellBorders,
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: "auto" } : undefined,
    children: [new Paragraph({
      alignment: o.align || L, spacing: { before: 0, after: 0, line: 248 },
      children: [txt(text, { size: o.size || 16, bold: o.bold, color: o.color })],
    })],
  });
}
function table(widths, header, rows, o = {}) {
  const aligns = o.aligns || widths.map(() => L);
  const size = o.size || 16;
  const head = new TableRow({
    tableHeader: true,
    children: header.map((t, i) =>
      cell(t, widths[i], { fill: HEADFILL, bold: true, align: aligns[i], size })),
  });
  const body = rows.map((r, ri) => new TableRow({
    children: r.map((t, i) => cell(t, widths[i], {
      align: aligns[i], size, fill: ri % 2 === 1 ? ZEBRA : undefined,
      bold: o.boldCols && o.boldCols.includes(i),
    })),
  }));
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    rows: [head, ...body],
  });
}
function caption(t) {
  return new Paragraph({
    spacing: { before: 150, after: 60 },
    children: [txt(t, { size: 16, bold: true, color: MUTED })],
  });
}

// 中央寄せの別行立て数式。右端に式番号を置く。
function equation(key, number) {
  const e = EQ[key];
  if (!e) return para(`[式が見つかりません: ${key}]`, { color: "AA0000" });
  const img = new ImageRun({
    type: "png", data: fs.readFileSync(e.file),
    transformation: { width: e.w, height: e.h },
  });
  const cells = [
    new TableCell({
      width: { size: 9106, type: WidthType.DXA },
      margins: { top: 90, bottom: 90, left: 0, right: 0 },
      borders: {
        top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 0 }, children: [img],
      })],
    }),
    new TableCell({
      width: { size: 1100, type: WidthType.DXA },
      margins: { top: 90, bottom: 90, left: 0, right: 0 },
      verticalAlign: "center",
      borders: {
        top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      },
      children: [new Paragraph({
        alignment: AlignmentType.RIGHT, spacing: { before: 0, after: 0 },
        children: [txt(`(${number})`, { size: 17 })],
      })],
    }),
  ];
  return new Table({
    columnWidths: [9106, 1100],
    width: { size: 10206, type: WidthType.DXA },
    rows: [new TableRow({ children: cells })],
  });
}

// ブロック列を描画する。章4〜7はこれで組み立てる。
function blocks(list) {
  const out = [];
  for (const b of list) {
    if (b.t === "p") out.push(para(b.text));
    else if (b.t === "h3") out.push(new Paragraph({
      spacing: { before: 220, after: 100 },
      children: [txt(b.text, { size: 18, bold: true })],
    }));
    else if (b.t === "eq") {
      out.push(equation(b.key, b.num));
      if (b.cap) out.push(new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 20, after: 130 },
        children: [txt(b.cap, { size: 15, color: MUTED })],
      }));
    } else if (b.t === "table") {
      if (b.cap) out.push(caption(b.cap));
      out.push(table(b.widths, b.header, b.rows,
        { aligns: (b.aligns || []).map((a) => (a === "r" ? R : L)), size: b.size || 16 }));
    } else if (b.t === "callout") out.push(callout(b.text));
    else if (b.t === "note") out.push(note(b.text));
    else if (b.t === "bullets") b.items.forEach((i) => out.push(bullet(i)));
    else if (b.t === "nums") b.items.forEach((i) => out.push(num(i)));
  }
  return out;
}

const P_ = P;
const B = [];

/* ===================== 表紙 ===================== */
B.push(new Paragraph({ spacing: { after: 60 }, children: [txt("STOCKリーグ提出版", { size: 17, color: MUTED })] }));
B.push(new Paragraph({ spacing: { after: 60 }, children: [txt(P.meta.title, { size: 34, bold: true })] }));
B.push(new Paragraph({ spacing: { after: 150 }, children: [txt(P.meta.subtitle, { size: 21, color: ACCENT })] }));
B.push(new Paragraph({
  spacing: { after: 320 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 8 } },
  children: [txt(`${P.meta.date}　／　${P.meta.asof}`, { size: 16, color: MUTED })],
}));

/* ===================== 0. 本書について ===================== */
B.push(h1("0. 本書について"));
B.push(para(P.about.purpose));
B.push(caption("本書の構成"));
B.push(table([1100, 9106], ["章", "内容"], P.about.toc, { aligns: [L, L] }));
B.push(note(P.about.standalone));

/* ===================== 1. 結論 ===================== */
B.push(h1("1. 結論"));
P.conclusion.forEach((t) => B.push(para(t)));
B.push(caption("要約数値"));
B.push(table([3400, 1900, 4906], ["項目", "値", "意味"], P.headline, { aligns: [L, R, L], boldCols: [1] }));

/* ===================== 2. 用語 ===================== */
B.push(h1("2. 用語の説明"));
B.push(para("本書に出てくる指標を、はじめて読む人向けに定義する。"));
B.push(table([2400, 7806], ["用語", "定義"], P.glossary, { aligns: [L, L] }));

/* ===================== 3. データ ===================== */
B.push(new Paragraph({ children: [], pageBreakBefore: true }));
B.push(h1("3. 使ったデータ"));
B.push(table([2200, 3400, 4606], ["項目", "出所", "時点・備考"], P.data_sources, { aligns: [L, L, L] }));
B.push(caption("主要項目のカバレッジ（母集団に対する取得率）"));
B.push(table([3600, 1700, 4906], ["項目", "取得率", "備考"], P.coverage, { aligns: [L, R, L] }));
P.data_notes.forEach((t) => B.push(note(t)));

/* ===================== 4. Step 0 ===================== */
B.push(h1("4. Step 0 — 母集団の絞り込み"));
B.push(para("「儲かる会社を選ぶ」段ではなく、「そもそも買えない会社・データが信用できない会社を落とす」段である。"));
B.push(caption("除外条件"));
B.push(table([650, 4650, 4906], ["#", "条件", "趣旨"], P.step0_conditions, { aligns: [R, L, L] }));
if (P.step0_blocks) B.push(...blocks(P.step0_blocks));
B.push(caption("ファネル（実測）"));
B.push(table([3700, 1300, 5206], ["段階", "社数", "内容"], P.funnel, { aligns: [L, R, L] }));
P.step0_notes.forEach((t) => B.push(note(t)));

/* ===================== 5. 4軸 ===================== */
B.push(new Paragraph({ children: [], pageBreakBefore: true }));
B.push(h1("5. Step 1 — 4つの評価軸"));
B.push(para(P.axes_intro));
if (P.notation) {
  B.push(caption("記号の約束"));
  B.push(table([1700, 4200, 4306], ["記号", "意味", "備考"], P.notation, { aligns: [L, L, L] }));
  B.push(note("添字 i は企業、k は軸を構成する成分を表す。指標名は立体（ローマン体）で書き、"
    + "変数は斜体で書く。定義には := を、恒等な等式には = を用いる。"));
}
P.axes.forEach((a) => {
  B.push(h2(a.title));
  if (a.source) B.push(para([txt("出典: ", { bold: true, size: 17 }), txt(a.source, { size: 17 })]));
  if (a.blocks) {
    B.push(...blocks(a.blocks));
  } else {
    B.push(para(a.what));
    B.push(...code(a.formula));
    B.push(caption("成分の意味"));
    B.push(table([2700, 5200, 2306], ["成分", "定義", "取得率"], a.components,
      { aligns: [L, L, R] }));
    if (a.note) B.push(note(a.note));
  }
});

/* ===================== 6. 合成 ===================== */
B.push(h1("6. Step 2 — 合成"));
if (P.composite.blocks) {
  B.push(...blocks(P.composite.blocks));   // blocks 側に趣旨の説明が入っているので text は出さない
} else {
  B.push(...code(P.composite.formula));
  B.push(para(P.composite.text));
}
B.push(caption("名目の配点と、実際に総合点を動かした割合"));
B.push(table([2606, 1900, 1900, 1900, 1900], ["", "Moat", "Change", "Future", "Price"],
  P.composite.effective, { aligns: [L, R, R, R, R], boldCols: [0] }));
B.push(note(P.composite.effective_note));
B.push(caption("軸どうしの順位相関（同じものを重複して測っていないかの確認）"));
B.push(table([2206, 2000, 2000, 2000, 2000], ["", "Moat", "Change", "Future", "Price"],
  P.composite.corr, { aligns: [L, R, R, R, R], boldCols: [0] }));
B.push(note(P.composite.corr_note));
B.push(caption("4軸すべてが基準以上の企業数"));
B.push(table([3400, 3400, 3406], ["基準", "社数", "母集団に対する割合"], P.composite.all_four,
  { aligns: [L, R, R] }));
B.push(callout(P.composite.all_four_note));

/* ===================== 7. 選抜と配分 ===================== */
B.push(h1("7. Step 3・4 — 選抜と保有比率"));
B.push(h2("7-1. 選抜ルール"));
P.selection.rules.forEach((t) => B.push(num(t)));
B.push(caption("業種上限の効果"));
B.push(table([3400, 2200, 4606], ["", "業種数", "上位業種の集中"], P.selection.cap_effect,
  { aligns: [L, R, L] }));
B.push(note(P.selection.cap_note));
B.push(h2("7-2. 保有比率の決め方"));
if (P.selection.alloc_blocks) B.push(...blocks(P.selection.alloc_blocks));
else B.push(...code(P.selection.alloc_formula));
B.push(para(P.selection.alloc_text));

/* ===================== 8. 選定20社 ===================== */
B.push(new Paragraph({ children: [], pageBreakBefore: true }));
B.push(h1("8. 選定した20社"));
B.push(note("数値は各軸の0〜100点。総合点はその単純平均。"));
B.push(table([520, 760, 2320, 1560, 1020, 760, 760, 760, 760, 986],
  ["#", "コード", "会社名", "業種", "市場", "Moat", "Chg", "Fut", "Price", "総合"],
  P.picks.map((p) => [p.rank, p.code, p.name, p.sector, p.market,
    p.moat, p.change, p.future, p.price, p.total]),
  { aligns: [R, R, L, L, L, R, R, R, R, R], size: 15, boldCols: [9] }));

B.push(h2("8-1. 各社が選ばれた理由"));
B.push(note("総合点は4軸の平均なので、同じ点でも中身は違う。何が効いて入ったかを一社ずつ示す。"));
B.push(table([740, 2100, 7366], ["コード", "会社名", "選定の要因"],
  P.rationale, { aligns: [R, L, L], size: 15 }));

B.push(new Paragraph({ children: [], pageBreakBefore: true }));
B.push(h2("8-2. 財務指標"));
B.push(table([740, 2140, 1160, 1180, 1000, 1200, 1260, 1526],
  ["コード", "会社名", "売上高", "営業利益率", "ROE", "自己資本比率", "営業CF率", "時価総額"],
  P.financials, { aligns: [R, L, R, R, R, R, R, R], size: 15 }));
B.push(note("売上高・時価総額は億円。営業CF率＝営業キャッシュフロー÷売上高。財務は各社最新の有価証券報告書。"));

/* ===================== 9. ポートフォリオ ===================== */
B.push(h1("9. ポートフォリオ構成"));
B.push(para(P.portfolio.text));
B.push(table([740, 2160, 940, 780, 780, 1060, 940, 1280, 1526],
  ["コード", "会社名", "株価", "PER", "PBR", "時価総額", "株数", "投資額", "比率"],
  P.holdings.map((h) => [h.code, h.name, h.close, h.per, h.pbr, h.mcap + "億",
    h.shares, h.cost, h.weight]),
  { aligns: [R, L, R, R, R, R, R, R, R], size: 15, boldCols: [8] }));
B.push(note(P.portfolio.note));

/* ===================== 10. 構成の特徴 ===================== */
B.push(h1("10. 構成の特徴"));
B.push(caption("業種"));
B.push(table([5106, 5100], ["業種", "社数"], P.sector_rows, { aligns: [L, R] }));
B.push(caption("市場区分と規模区分"));
B.push(table([2553, 2553, 2550, 2550], ["市場", "社数", "規模区分", "社数"],
  P.market_scale, { aligns: [L, R, L, R] }));
B.push(caption("バリュエーションの分布（20社 対 母集団）"));
B.push(table([3400, 3400, 3406], ["指標", "選定20社", "母集団"], P.valuation_rows,
  { aligns: [L, R, R] }));

/* ===================== 11. 自己検証 ===================== */
B.push(new Paragraph({ children: [], pageBreakBefore: true }));
B.push(h1("11. この方式は機能するか（自己検証）"));
B.push(para(P.validation.design));
B.push(caption("検証コホート"));
B.push(table([1900, 1900, 1500, 1600, 3306],
  ["コホート", "基準日", "対象社数", "測定期間", "位置づけ"],
  P.validation.cohorts, { aligns: [L, L, R, R, L] }));

B.push(h2("11-1. 軸ごとの予測力（順位相関）"));
B.push(table([4206, 2000, 2000, 2000],
  ["", "FY2024/252日", "FY2025/126日", "FY2023/252日"],
  P.validation.ic, { aligns: [L, R, R, R], boldCols: [0] }));
B.push(note(P.validation.ic_note));

B.push(h2("11-2. 十分位スプレッド"));
B.push(note("母集団を総合点で10等分し、上位10%の平均リターン − 下位10%の平均リターン。"));
B.push(table([4206, 2000, 2000, 2000], ["", "FY2024", "FY2025", "FY2023"],
  P.validation.decile, { aligns: [L, R, R, R], boldCols: [0] }));

B.push(h2("11-3. 20社ポートフォリオの実績"));
B.push(table([3406, 2200, 2300, 2300],
  ["", "FY2024/252日", "FY2025/126日", "FY2023/252日"],
  P.validation.portfolio, { aligns: [L, R, R, R], boldCols: [0] }));
B.push(note(P.validation.portfolio_note));

B.push(h2("11-4. 偶然との比較・重みの感度"));
P.validation.robustness.forEach((t) => B.push(bullet(t)));
B.push(callout(P.validation.verdict));

/* ===================== 12. 比較 ===================== */
B.push(h1("12. 他方式との比較"));
P.comparison.text.forEach((t) => B.push(para(t)));
B.push(caption("両ポートフォリオを同じ4軸で採点したときの中央値"));
B.push(table([3400, 3400, 3406], ["軸", "現行版20社", "本方式20社"], P.comparison.rows,
  { aligns: [L, R, R], boldCols: [0] }));
B.push(caption("銘柄の重なり"));
B.push(table([6806, 3400], ["比較対象", "重複"], P.comparison.overlap, { aligns: [L, R] }));

/* ===================== 13. 限界 ===================== */
B.push(h1("13. 限界と注意点"));
P.limits.forEach((t) => B.push(bullet(t)));

/* ===================== 14. 再現 ===================== */
B.push(h1("14. 再現手順"));
B.push(para("本書の数値はすべて次のコードから生成されている。"));
B.push(...code(P.repro.commands));
B.push(table([3400, 6806], ["出力ファイル", "内容"], P.repro.outputs, { aligns: [L, L] }));

B.push(new Paragraph({
  spacing: { before: 420 },
  border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 8 } },
  children: [txt(P.footer, { size: 15, color: MUTED })],
}));

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 18, color: INK } } } },
  numbering: {
    config: [
      { reference: "dots", levels: [{ level: 0, format: "bullet", text: "•",
          alignment: L, style: { paragraph: { indent: { left: 340, hanging: 200 } } } }] },
      { reference: "nums", levels: [{ level: 0, format: "decimal", text: "%1.",
          alignment: L, style: { paragraph: { indent: { left: 360, hanging: 220 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1000, bottom: 1000, left: 850, right: 850 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [P_.footer_short, "  ", PageNumber.CURRENT],
            font: FONT, size: 15, color: MUTED })],
        })],
      }),
    },
    children: B,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.mkdirSync(path.dirname(P.output), { recursive: true });
  fs.writeFileSync(P.output, buf);
  console.log("docx 書き出し完了:", P.output, `(${(buf.length / 1024).toFixed(0)} KB)`);
});
