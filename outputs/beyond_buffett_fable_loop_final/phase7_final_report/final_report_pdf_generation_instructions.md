# final_report.pdf 生成手順

## 状況：生成済み
`final_report.pdf`（**19 ページ**）は、このマシンにインストール済みの **Microsoft Word** を AppleScript 経由で駆動して docx から書き出し済みである。図・式・カラーバナー・記入テンプレートを含む完全版が PDF 化されている。

## 再生成（Word・macOS）
docx を更新したら、次で PDF を作り直せる。
```bash
DOCX="outputs/beyond_buffett_fable_loop_final/phase7_final_report/final_report.docx"
PDF="outputs/beyond_buffett_fable_loop_final/phase7_final_report/final_report.pdf"
osascript <<EOF
tell application "Microsoft Word"
    launch
    close (every document) saving no
    set d to open file name (POSIX file "$PWD/$DOCX" as text)
    save as d file name (POSIX file "$PWD/$PDF" as text) file format format PDF
    close d saving no
    quit saving no
end tell
EOF
```
注意：Word が同名文書を開いたままだと**古い版がそのまま PDF 化される**ことがある。上記のように毎回 `close (every document)` してから開くこと（本ループで一度踏んだ落とし穴）。

## 代替手段
- **LibreOffice**（要インストール）：`soffice --headless --convert-to pdf --outdir <dir> final_report.docx`
- **pandoc + LaTeX**（要インストール）：`final_report.md` から直接 PDF 化する場合。数式は `final_report_latex_equations.md` の LaTeX を本文へ差し込む。

## 提出前の仕上げ（人間対応）
- 表紙メタ・銘柄紹介・インタビュー・アンケート・学んだことのテンプレートを記入後、PDF を再生成する。
- STOCK リーグ公式の最新ページ規定・提出様式・締切を確認する。
