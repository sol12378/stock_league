# Phase2 Review Comments（loop 1）

## 良い点

1. **「破」の範囲規律**：何を守り（式・思想・除外規律）、何を破ったか（固定閾値・固定候補数・単一正規化・単一時点評価）が明示され、「式を変えずに使い方を最適化する」という Phase2 の定義が実装と一致している。
2. **Phase2 スコアの位置づけの明確さ**：Exploratory Weighted Buffett Score は候補宇宙形成のための探索スコアであり、正式な Phase1 式でも最終選定スコアでもないことが README・レポートの双方に明記されている。Phase3 が Phase2 スコアを最終スコアとして流用していないことの根拠になる。
3. **正規化のコンセンサス設計**：market percentile / sector percentile / robust z / winsorized z の4方式で共通上位に残る銘柄に core/robust タグを付与し、単一正規化への依存を排除。outlier_sensitive 622 社の明示は誠実。
4. **検証の誠実さ**：strict walk-forward 未完了を隠さず、fixed-weight out-of-time validation で代替した上で、許される主張と禁止される主張を文書で規定している。この「主張の上限管理」は論文品質に直結する。

## 懸念点と対応

1. **distress 重みのパラドクス**（重み 0.251、ablation 寄与 0.0017）：distress は hard exclusion（184+11社除外）で既に効いており、生き残った母集団内では distress スコアの分散が小さく限界効果が消える。これは二重適用の無駄ではなく「除外＋残余リスクの微調整」という多層防御だが、説明がないと「重みが飾り」に見える。→ explain_docs で構造を明記した。
2. **件数不一致（825/840）**：flag 集計と最終監査の集計時点差。採用値を 825 に統一し脚注開示。
3. **utility と formal 採用の乖離**（Top2000 が utility 最適、formal は Top1200）：判断根拠は開示済みだが、レポートでは「なぜ最適値をそのまま採らないのか」を1段落で言語化する必要がある（Phase7 Ⅳ章）。
4. **金融業除外の見かけ上の空振り**（applied=true / excluded=0）：母集団構築段階で金融業が既に除外済み。表現を統一する。

## 結論

Phase2 は再実行不要。候補宇宙（formal_top1200）を Phase3 の唯一の母集団として確定する。
