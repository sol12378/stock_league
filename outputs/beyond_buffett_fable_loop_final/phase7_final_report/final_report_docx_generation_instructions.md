# final_report.docx 生成・再生成手順（日経 STOCK リーグ様式）

## 状況
`final_report.docx` は **生成済み**（`scripts/phase7_build_docx.py`、python-docx 1.2.0）。昨年度入賞レポート（25_01.pdf / 25_04.pdf）の様式を反映：

- **構成**：要旨→目次→Ⅰ背景・投資テーマ決定→Ⅱスクリーニング（守・破・離＋式＋アブレーション）→Ⅲポートフォリオの決定・銘柄紹介・パフォーマンス→Ⅳインタビュー・アンケート→Ⅴ学んだこと→注・参考文献。
- **見出し**：カラーバナー（Ⅰ＝ティール塗り＋白文字／サブ＝淡色ボックス＋左罫／サブサブ＝破線下罫＋ティール文字）。
- **式ボックス**：「モデル名（引用）」ティールバナー＋**mathtext でレンダリングした式画像**＋変数定義（8pt）＋図表番号キャプション（下部）。入賞レポートの式挿入手法（25_04 p.14 の CFO 修正ジョーンズモデル）に準拠。
- **表**：ティール色ヘッダ行＋下部に図表番号キャプション。ポートフォリオ表（図表 III-1）はデータから自動生成。
- **記入テンプレート**：表紙メタ／銘柄紹介 20 社（図表 III-2、左列自動記入・右2列空欄）／インタビュー（ご質問内容＋企業別ボックス×3）／学んだこと（プロンプト付きスケルトン）。
- **図・式画像**：計 23 点埋め込み。

## 再生成
```
.venv/bin/python outputs/beyond_buffett_fable_loop_final/scripts/phase7_concept_figures.py  # 概念図
.venv/bin/python outputs/beyond_buffett_fable_loop_final/scripts/phase7_funnel_figure.py    # funnel
.venv/bin/python outputs/beyond_buffett_fable_loop_final/scripts/phase7_build_docx.py        # docx
```
`final_report.md`／`final_figures/`／`final_references.md` を編集後に再実行すれば docx が更新される。式は md の ```formula ブロック（CAPTION/EQ/DEF）から自動レンダリングされる。

## 提出者が仕上げる箇所
1. **表紙メタ**：チーム名・チームID・学校・学年・メンバー・指導教員（`<!-- COVERMETA -->` または docx 表紙で記入）。
2. **銘柄紹介**（図表 III-2）：20 社の「企業概要」「Moat の根拠」を記入（左列は自動記入済み）。
3. **インタビュー・アンケート**：質問・対象企業・回答を記入。
4. **学んだこと**：チームの経験・謝辞（STOCK リーグは氏名・謝辞可）。
5. **基礎学習**：本ループでは未作成。必要なら別途追加。

## 既知の限界
- 式は画像として埋め込み済み（そのまま提出可）。テキスト編集が必要なら `final_report_latex_equations.md` の LaTeX を Word 数式エディタへ。
- mermaid 図（守・破・離のフロー）は PNG 化して `final_figures/` に格納済み。
- STOCK リーグ公式の最新ページ数・提出様式規定は要項で最終確認（人間）。
