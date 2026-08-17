# Outliers Style Extraction（式セクション様式の抽出）

## 1. 探索結果

指示された `docs/outliers*` は、プロジェクト全体（深さ無制限、.venv/.git 除外）を探索した結果、**ファイル名一致 0 件で存在しない**。
なお文字列 "outlier" は phase2 tex 中に正規化タグ（Outlier-sensitive、622社）として登場するが、これはコンテンツであり様式ファイルではない。

## 2. 代替スタイル正典

`missing_inputs.md` に記録の上、**同等の役割を果たす様式正典**として以下を採用する：

- `docs/explain_docs/phase1_buffett_methodology_report_flow_v2.tex`
- `docs/explain_docs/phase2_methodology_report_polished.tex`

## 3. 抽出した式セクションの「型」（本ループの全式説明で遵守）

各式は必ず次の4段構成で提示する。

1. **導入文**（1〜2文）：この式が「何を測るか」を日本語で述べる。式を孤立させない。
2. **数式環境**：定義は `\coloneqq`、番号参照が必要な式は `equation` + `\label{eq:...}`、複数行整列は `align`。`eqnarray` 禁止。
3. **変数定義（後置）**：式の直後に「ここで，$X_i$ は…」と全変数を定義する。
4. **解釈・直感**：数値例（「簿価100億円を市場が80億円で評価すれば BM=1.25」型）と注意点（バリュートラップ等）。

### 表記規約

- 会計項目・略語はローマン体：$\mathrm{BE}, \mathrm{ME}, \mathrm{CFO}, \mathrm{TA}$
- 上付き属性ラベル：$S^{\mathrm{Trans}}_i$, $S^{\mathrm{Emerg}}_i$, $R^{\mathrm{avail}}_i$, $S^{\mathrm{mkt}}_{i,m}$ 型
- 演算子は `\max, \min, \log, \exp, \operatorname{rank}` 等の立体
- 指示関数 $\mathbb{1}\{\cdot\}$、場合分けは `cases`
- 式参照は本文で「式（1）」形式

### 章の型

- 冒頭に「まず結果」（結論先出し：ファネル図＋通過社数＋最終テーブル）
- 各式セクション冒頭に「フローでの位置：Step X」を明記し、絞り込み社数を添える
- 表キャプションは上、図キャプションは下
- 強調は keybox（要点）／warnbox（注意）／defbox（定義・直感）の3種に対応する Markdown 引用ブロックで代替
