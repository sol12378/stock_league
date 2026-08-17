# 「AIキーワードのみ577社除外」の根拠と正しい解釈(監査ノート)

作成日: 2026-07-18
対象記述: 「開示資料でＡＩに言及しながら具体的な製品・顧客・数量の裏づけを欠く企業が577社に上った」

## 1. 結論(正しい解釈)

> 候補1200社のうち、社名・業種・引き継ぎメモへの**機械的なキーワード照合ではAI関連テーマとの接点があるように見えるが、製品・顧客・数量まで遡れる開示証拠(L2以上)を確認できなかった非選定銘柄が577社**あり、これらを一律除外して監査記録した。

- 「AIに言及した577社を精査して落とした」のではない。
- 「**証拠を確認できた14社以外は疑わしきものとして落とした結果が577社だった**」が実態。
- 「開示資料で言及」は不正確(開示資料本文は読んでいない)。「裏づけを欠く」は正確。

## 2. データ上の根拠

出典: `outputs/phase3_beyond_buffett_v2/data/phase3_rejected_candidates.csv`(除外監査リスト、862行)

| rejection_reason_category | 社数 |
|---|---|
| ai_keyword_only | **577** |
| already_represented_by_better_candidate | 221 |
| distress_or_quality_risk | 32 |
| value_trap_risk | 17 |
| low_pbr_only | 15 |
| 計 | 862 |

## 3. 判定の仕組み(コードの実挙動)

実装: `outputs/phase3_beyond_buffett_v2/scripts/phase3_selection/phase3_v2_pipeline.py` の `keyword_screen()`(275行目付近)

Top1200の各社に証拠レベルを付与:

| レベル | 意味 | 判定方法 | 該当数 |
|---|---|---|---|
| L3 | 数量まで確認(顧客3,000社等) | 手作業キュレーション(curated_evidence.csv、IR/製品ページURL+引用) | 6 |
| L2 | 製品・顧客を確認 | 同上 | 8 |
| L1 | キーワードヒットのみ | 機械的スクリーニング | 586 |
| L0 | 接点なし | 非該当 | 600 |

- L1判定 = `emerging_keyword_only_flag`。照合対象テキストは **社名 + 業種 + phase3_handoff_note**(開示資料本文ではない)。
- `KEYWORDS` 辞書(半導体・データセンター・電力・光通信・自動化・セキュリティ等10カテゴリ)+ `SECTOR_HINTS`(機械・電気機器・情報通信などは**業種所属だけで自動L1**)。
- L1の586社に一律18点のテーマ過熱ペナルティ + `ai_keyword_only` ガードで選定不可。
- 586社中、非選定で除外監査リスト(862行)にai_keyword_onlyとして載った分が **577社**。差分9社の内訳: **2社は最終選定入り**(6430 大黒電機・9470 学研ＨＤ=いずれも守の固定枠。EM=1のキーワード接点あり)、**7社はlow_pbr_onlyとして計上**(ai_keyword_onlyではなく別カテゴリで除外記録)。※旧記述「差分9社は選定済み」は不正確だったため訂正(2026-07-20、EXPERT_AUDIT_v4.md指摘31)。
- L2/L3(計14社)のみEmerging系役割の選定資格を持つ。

## 4. 既知の弱点(内部監査で指摘済み)

出典: `outputs/beyond_buffett_fable_loop_final/phase0_input_audit/phase3_v2_reconstruction.md`

- **D7**: ai_keyword_only が catch-all 化(577/862件)。報告プローズの粒度(10種)と実カテゴリ(5種)が乖離。
- **D2**: L2+ の証拠は curated_evidence.csv の**14社の手作業に完全依存**。systematic screen は L0/L1 どまり。

## 5. レポート文言の問題点

「**開示資料で**AIに言及しながら」は実装より強い主張になっている:

1. 照合したのは社名・業種・メモであり、有価証券報告書・決算説明資料の本文は読んでいない。
2. 業種ヒントにより、開示でAIに一言も触れていない会社もL1(=言及あり扱い)に含まれ得る。

### 推奨する言い換え

> 「AI関連テーマとの接点がキーワード・業種レベルの機械的スクリーニングでしか確認できず、製品・顧客・数量まで遡れる開示証拠(L2以上)を確認できなかった577社を除外し、監査記録した」

手作業14社という制約は「証拠のハードルを高く置いた保守的設計(疑わしきは除外)」として説明するとデータと主張が一致し、強みに転じる。

## 6. 想定問答(審査対応)

**Q. 577社の開示資料をどう分析したのか?**
A. 全社の開示を精査したのではなく、逆方向の設計。製品・顧客・数量の開示証拠を個別に確認・記録できた14社だけをEmerging候補として通し、キーワード・業種レベルの接点しか確認できなかった577社は「証拠不十分」として一律除外した。除外の理由コードは862社全件について監査リストに記録してあり、後から反証可能。

## 7. 該当記述の所在(修正する場合の対象)

- `outputs/beyond_buffett_fable_loop_final/phase7_final_report/final_report.md` (L183, L203)
- `outputs/beyond_buffett_fable_loop_final/phase7_final_report/final_report_academic_variant.md` (L148, L160)
- `outputs/beyond_buffett_fable_loop_final/phase3_moat_construction/phase3_explanation_for_report.md` (L15, L27)
- `outputs/beyond_buffett_fable_loop_final/explain_docs/phase3_explanation_material.md` (L17, L32)
- `docs/explain_docs/phase3_methodology_report.tex`
- 提出版 `outputs/stockleague_edition/beyond_buffett_stockleague_v3.docx/pdf` の該当箇所(修正時はVERSION繰り上げでv4として生成)
