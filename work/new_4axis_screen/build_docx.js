// 簡易スクリーニングレポートの docx を組み立てる。10_build_docx.py から呼ばれる。
const fs = require("fs");
const path = require("path");
const MODS = "/private/tmp/claude-501/-Users-satouryuuichi-Desktop-product-hobby-stock-league/f04bb6c3-a171-48b8-803c-40a74d574cc3/scratchpad/node_modules";
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Footer, PageNumber, convertInchesToTwip,
} = require(path.join(MODS, "docx"));

const P = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

const FONT = "Yu Gothic";
const INK = "1B1F27";
const MUTED = "5B6373";
const ACCENT = "2F4B8F";
const RULE = "C9CEDA";
const HEADFILL = "EDF0F6";
const ZEBRA = "F7F8FB";

// A4 縦、左右マージン 850 DXA → 本文幅 10206
const CONTENT_W = 11906 - 850 * 2;

const cellBorders = {
  top: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
  right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
};

function txt(text, opt = {}) {
  return new TextRun({
    text: String(text),
    font: FONT,
    size: opt.size || 18,
    bold: !!opt.bold,
    color: opt.color || INK,
  });
}

function para(text, opt = {}) {
  return new Paragraph({
    alignment: opt.align || AlignmentType.LEFT,
    spacing: { before: opt.before ?? 0, after: opt.after ?? 120, line: opt.line || 300 },
    indent: opt.indent,
    border: opt.border,
    children: Array.isArray(text) ? text : [txt(text, opt)],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 6 } },
    children: [txt(text, { size: 26, bold: true, color: ACCENT })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 110 },
    children: [txt(text, { size: 21, bold: true })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "dots", level: 0 },
    spacing: { after: 70, line: 290 },
    children: [txt(text)],
  });
}

function cell(text, w, opt = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    borders: cellBorders,
    shading: opt.fill
      ? { type: ShadingType.CLEAR, fill: opt.fill, color: "auto" }
      : undefined,
    children: [
      new Paragraph({
        alignment: opt.align || AlignmentType.LEFT,
        spacing: { before: 0, after: 0, line: 250 },
        children: [txt(text, { size: opt.size || 16, bold: opt.bold, color: opt.color })],
      }),
    ],
  });
}

function table(widths, header, rows, opt = {}) {
  const aligns = opt.aligns || widths.map(() => AlignmentType.LEFT);
  const size = opt.size || 16;
  const head = new TableRow({
    tableHeader: true,
    children: header.map((t, i) =>
      cell(t, widths[i], { fill: HEADFILL, bold: true, align: aligns[i], size })),
  });
  const body = rows.map((r, ri) =>
    new TableRow({
      children: r.map((t, i) =>
        cell(t, widths[i], {
          align: aligns[i],
          size,
          fill: ri % 2 === 1 ? ZEBRA : undefined,
          bold: opt.boldCols && opt.boldCols.includes(i),
        })),
    }));
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    rows: [head, ...body],
  });
}

const R = AlignmentType.RIGHT;
const C = AlignmentType.CENTER;
const L = AlignmentType.LEFT;
const s = P.summary;
const x = P.extra;

const body = [];

// ---------- 表紙ブロック ----------
body.push(new Paragraph({
  spacing: { after: 60 },
  children: [txt("STOCKリーグ提出版", { size: 17, color: MUTED })],
}));
body.push(new Paragraph({
  spacing: { after: 60 },
  children: [txt(P.meta.title, { size: 36, bold: true })],
}));
body.push(new Paragraph({
  spacing: { after: 140 },
  children: [txt(P.meta.subtitle, { size: 21, color: ACCENT })],
}));
body.push(new Paragraph({
  spacing: { after: 300 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 8 } },
  children: [txt(`${P.meta.date}　／　${P.meta.asof}`, { size: 16, color: MUTED })],
}));

// ---------- 1. 結論 ----------
body.push(h1("1. 結論"));
body.push(para(
  `全上場${s.universe.toLocaleString()}社から投資可能な${s.eligible.toLocaleString()}社を母集団とし、` +
  `4つの軸（Moat・Change・Future・Price）を各0〜100点の順位点にして25%ずつ合計、` +
  `同一業種2社までの制約をかけて${s.picked}社を選んだ。${s.sectors}業種に分散している。`));
body.push(para(
  `選んだ20社はPER中央値${s.per_median}倍・PBR中央値${s.pbr_median}倍・時価総額中央値${s.mcap_median}億円で、` +
  `ROE中央値は${s.roe_median}%。投資枠500万円に対し${s.invested}円を配分し、余剰現金は${s.cash}円（${s.cash_pct}%）。`));
body.push(para([
  txt("現行版（守破離の重み30/25/30/15）の20社との重複は", {}),
  txt(`${s.overlap}社`, { bold: true }),
  txt("。この方式に変えることは、銘柄の入れ替えではなくポートフォリオの総入れ替えを意味する。", {}),
]));

// ---------- 2. 手順 ----------
body.push(h1("2. スクリーニングの手順"));
body.push(h2("2-1. 母集団の絞り込み（Step 0）"));
body.push(table(
  [3700, 1300, 5206],
  ["段階", "社数", "内容"],
  P.funnel,
  { aligns: [L, R, L] }));
body.push(para(
  "条件9（バリュエーション範囲の検査）は、これまで株価指標を取得できていた売買代金上位300社にしか" +
  "適用されていなかった。今回から全社の時価総額を用意したため、全社に適用している。",
  { before: 120, size: 16, color: MUTED }));

body.push(h2("2-2. 4つの評価軸（Step 1）"));
body.push(table(
  [2600, 5106, 2500],
  ["軸", "使う指標", "作り方"],
  P.axes,
  { aligns: [L, L, L] }));
body.push(para(
  "各指標は母集団内の順位を0〜100点に直して平均する。欠測はゼロで埋めず、平均から外す" +
  "（ゼロ埋めは「平均並み」を意味してしまうため）。",
  { before: 120, size: 16, color: MUTED }));

body.push(h2("2-3. 合成（Step 2）"));
body.push(para("総合点 ＝ 0.25×Moat ＋ 0.25×Change ＋ 0.25×Future ＋ 0.25×Price"));
body.push(para(
  "ただし名目の25%は、実際に総合点を動かす割合とは一致しない。各軸が合成点の分散に" +
  "どれだけ寄与しているかを測ると次のとおり。"));
body.push(table(
  [2606, 1900, 1900, 1900, 1900],
  ["", "Moat", "Change", "Future", "Price"],
  P.effective_weight,
  { aligns: [L, R, R, R, R], boldCols: [0] }));
body.push(para(
  "Priceが下がるのは、割安な会社ほど収益性が低い傾向があり、足し合わせの中で打ち消されるため。" +
  "「等しく配点する」ことと「等しく効く」ことは別である。",
  { before: 120, size: 16, color: MUTED }));

body.push(h2("2-4. 選抜と保有比率（Step 3・4）"));
body.push(bullet("総合点の降順に、同一の33業種分類は最大2社までとして20社を採る。"));
body.push(bullet(
  `業種上限を外すと20社が${x.sectors_nodiv}業種に偏る（${x.nodiv_top}）。` +
  `上限を入れると平均総合点は${x.mean_without_cap}点から${x.mean_with_cap}点へ下がるが、集中は解消される。`));
body.push(bullet(
  `保有比率は均等5%を目標とし、売買単位100株の制約の中で目標に最も近くなるよう単元数を決める。` +
  `結果の比率は${s.w_min}%〜${s.w_max}%に収まった。`));

// ---------- 3. 選定20社 ----------
body.push(new Paragraph({ children: [], pageBreakBefore: true }));
body.push(h1("3. 選定した20社"));
body.push(para("数値は各軸の0〜100点。総合点はその単純平均。", { size: 16, color: MUTED }));
body.push(table(
  [560, 780, 2400, 1700, 1100, 780, 780, 780, 780, 546],
  ["#", "コード", "会社名", "業種", "市場", "Moat", "Chg", "Fut", "Price", "総合"],
  P.picks.map((p) => [p.rank, p.code, p.name, p.sector, p.market,
    p.moat, p.change, p.future, p.price, p.total]),
  { aligns: [R, R, L, L, L, R, R, R, R, R], size: 15, boldCols: [9] }));

// ---------- 4. ポートフォリオ ----------
body.push(h1("4. ポートフォリオ構成"));
body.push(para(
  `投資枠500万円、売買単位100株、1銘柄あたりの上限8%。` +
  `合計${P.totals.cost}円（${P.totals.weight}）を配分し、残る現金は${s.cash}円。`));
body.push(table(
  [780, 2500, 1000, 800, 800, 1100, 1000, 1300, 926],
  ["コード", "会社名", "株価", "PER", "PBR", "時価総額", "株数", "投資額", "比率"],
  P.holdings.map((h) => [h.code, h.name, h.close, h.per, h.pbr,
    h.mcap + "億", h.shares, h.cost, h.weight]),
  { aligns: [R, L, R, R, R, R, R, R, R], size: 15, boldCols: [8] }));
body.push(para(
  `※ 株価・時価総額は2026-08-17時点の実勢値（発行済株式数×株価）。PER・PBRは各社最新の有価証券報告書の当期純利益・自己資本で算出。`,
  { before: 100, size: 15, color: MUTED }));

// ---------- 5. 構成の特徴 ----------
body.push(h1("5. 構成の特徴"));
body.push(h2("5-1. 業種"));
body.push(table([5106, 5100], ["業種", "社数"],
  P.sector_rows, { aligns: [L, R] }));
body.push(h2("5-2. 市場区分と規模"));
body.push(table([2553, 2553, 2550, 2550],
  ["市場", "社数", "規模区分", "社数"],
  (() => {
    const n = Math.max(P.market_rows.length, P.scale_rows.length);
    const out = [];
    for (let i = 0; i < n; i++) {
      const m = P.market_rows[i] || ["", ""];
      const sc = P.scale_rows[i] || ["", ""];
      out.push([m[0], m[1], sc[0], sc[1]]);
    }
    return out;
  })(),
  { aligns: [L, R, L, R] }));
body.push(para(
  `母集団全体のPER中央値は${x.per_median_universe}倍、PBR中央値は${x.pbr_median_universe}倍で、` +
  `PBR1倍割れが${x.pbr_below1}%を占める。選んだ20社はこの中でも割安側に寄っている。`,
  { before: 140 }));

// ---------- 6. 現行版との比較 ----------
body.push(h1("6. 現行版との比較"));
body.push(para("両ポートフォリオを同じ4軸で採点したときの中央値。"));
body.push(table([3402, 3402, 3402],
  ["軸", "現行版20社", "新方式20社"],
  P.compare, { aligns: [L, R, R], boldCols: [0] }));
body.push(para(
  "現行版はMoatとFutureで高い一方、Priceが母集団の中央値を下回っている。" +
  "「割安に買う」を評価軸として明示的に組み込んだ結果が、この差に表れている。",
  { before: 140 }));

// ---------- 7. 留意点 ----------
body.push(h1("7. 留意点"));
body.push(bullet(
  `4軸すべてで高得点の会社は存在しない。全4軸60点以上は${x.all4_60}社、70点以上は${x.all4_70}社、` +
  `80点以上は${x.all4_80}社。平均を取る方式である以上、選ばれた会社もどこか1軸は弱い。`));
body.push(bullet(
  "Future軸は、EDINET本文のキーワード照合で作っている。33業種の分類だけで99%以上を説明でき、" +
  "個社の判断というより「構造変化の恩恵を受けやすい業種群に属しているか」の判定である。" +
  "また構成要素のうち無形資産投資（重み0.25）は研究開発費がほぼ取得できず、実質的に機能していない。"));
body.push(bullet(
  `時価総額は実勢の発行済株式数×実勢株価で計算している。有価証券報告書の提出後に株式分割した会社は、` +
  `報告書の株式数のままだと時価総額が分割比率のぶん過小になり「異常に割安」と誤判定される。` +
  `実際、修正前の上位20社のうち6社がこれに該当していた。今回は母集団のうち${x.split_detected}社で提出後の分割を検出し、` +
  `うち${x.split_jun_aug}社は直近3か月以内の分割だった。株式数は${x.live_shares}社で実勢値を用い、` +
  `取得できなかった${x.fallback}社のみ報告書の値を使っている。`));
body.push(bullet(
  "PERは最新の有価証券報告書の当期純利益を用いている。提出後に業績が変化した会社では、" +
  "直近12か月ベースのPERと差が出る（例: 7991は有報ベース2.4倍に対し直近12か月ベースでは6.5倍）。" +
  "上位に入った銘柄は、直近四半期の利益動向を必ず確認すること。"));
body.push(bullet(
  `投資枠500万円・1銘柄上限8%の制約から、1単元が40万円を超える${x.not_buyable}社は選抜対象から除いている。` +
  `大型株の一部が構造的に選ばれないため、この点は資金量に依存する制約である。`));
body.push(bullet(
  "本スクリーニングは選定ロジックの提示であり、将来の運用成績を約束するものではない。" +
  "STOCKリーグの審査ではリターンは採点対象外であり、本書は選定の再現性と説明可能性を示すためのものである。"));

body.push(new Paragraph({
  spacing: { before: 400 },
  border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 8 } },
  children: [txt(
    "再現コード: work/new_4axis_screen/07_final_screen.py ／ 仕様: NEW4AXIS_SPEC_v1.md ／ 検証: NEW4AXIS_AUDIT_v1.md",
    { size: 15, color: MUTED })],
}));

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: 18, color: INK } },
    },
  },
  numbering: {
    config: [{
      reference: "dots",
      levels: [{
        level: 0,
        format: "bullet",
        text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 340, hanging: 200 } } },
      }],
    }],
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
          children: [new TextRun({
            children: [PageNumber.CURRENT],
            font: FONT, size: 15, color: MUTED,
          })],
        })],
      }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.mkdirSync(path.dirname(P.output), { recursive: true });
  fs.writeFileSync(P.output, buf);
  console.log("docx 書き出し完了:", P.output, `(${(buf.length / 1024).toFixed(0)} KB)`);
});
