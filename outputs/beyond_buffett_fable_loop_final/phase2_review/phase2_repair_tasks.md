# Phase2 Repair Tasks（loop 1）

スコア 96/100（PASS）のため再最適化は不要。修復はすべて説明・開示レベル。

| ID | タスク | 重要度 | 対応先 | 状態 |
|---|---|---|---|---|
| R2-1 | distress 重み（0.251）と ablation 寄与（0.0017）の乖離説明：distress は hard exclusion で既に適用済みのため、スコア重みとしての限界効果がほぼゼロになる構造を明記 | 中 | explain_docs/phase2_optimization_explanation.md | **本ループで対応済み** |
| R2-2 | phase3_review_required 件数不一致（final_audit 840 vs flag_audit 825）の開示。採用値は flag_audit の 825、差異は集計時点差として脚注化 | 中 | Phase7 final_report 脚注 | Phase7 で対応 |
| R2-3 | fixed-weight out-of-time validation の実データ参照先（`walk_forward/fixed_weight_annual_validation.csv`）の明記 | 低 | explain_docs/phase2_explanation_material.md | **本ループで対応済み** |
| R2-4 | 「金融業除外 applied=true / excluded_count=0」の表現統一（母集団構築段階で除外済みのため追加除外 0） | 低 | Phase7 final_report | Phase7 で対応 |

## 修復しないと決めた事項（理由つき）

- **strict true walk-forward の追実装**：fold 不足という構造的制約は本ループでも変わらない。fixed-weight out-of-time validation（point-in-time panel、2023/2024/2025 snapshot）による代替と「将来リターン予測力を主張しない」という制限表現がすでに学術的に誠実な着地であり、Phase5 の検証も同じ位置づけ（リスク確認であり予測力証明ではない）で統一する。
- **Top1200 の再選定**：utility 最適は Top2000 だが、Phase3 review 負荷と品質のバランスで Top1200 を採る判断は文書化済み。ここを弄ると Phase3 v2 の全成果物と整合しなくなる。
