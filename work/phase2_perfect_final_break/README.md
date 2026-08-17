
# BEYOND BUFFETT Phase2 Perfect Final Break

## これは何か

BEYOND BUFFETT Phase2（破）の最終統合成果物である。Phase1の式の定義は変えず、式の使い方を最適化した。正式候補群はTop1200である。utility最大化のTop2000は参照群である。

## Phase2で体現した「破」

- 重み最適化
- TopN比較
- Top1200正式採用
- Top2000参照群
- 金融業除外
- Distress hard exclude
- Normalization consensus
- Anomaly / Review flag監査
- EDINET提出日ベースpoint-in-time panel
- fixed-weight out-of-time validation
- Phase3 handoff

## 主要ファイル

- `formal_top1200/phase2_formal_top1200_candidates.csv`
- `formal_top1200/phase2_formal_top1200_candidates_review_ready.csv`
- `top2000_reference/final_weighted_top2000_reference.csv`
- `normalization/normalization_consensus_table.csv`
- `walk_forward/fixed_weight_annual_validation.csv`
- `optimization/selected_phase2_solution_clean.json`
- `reports/phase2_final_integrated_report.md`
- `reports/phase2_to_phase3_handoff_final.md`
- `reports/report_text_for_paper.md`

## 注意

- Exploratory Weighted Buffett Scoreは正式なPhase1式ではない
- 将来リターン予測モデルではない
- true walk-forward optimizationは未完了
- fixed-weight out-of-time validationは実施済み
- Phase3 review flagsは除外理由ではなく追加確認論点である
