# True Walk-forward Status Report

できていること: EDINET提出日ベースのpoint-in-time panelを構築し、固定済みPhase2重みを年度別snapshotに適用し、非金融・non-distressの年度別Top1200を作成した。

できていないこと: 十分な複数foldによるtrue walk-forward optimization、train年度で重みを再推定しtest年度で完全評価する検証、将来リターン予測力の証明。

| item | value |
| --- | --- |
| strict_true_walk_forward_completed | False |
| reason | Eligible train/test folds were insufficient for reliable true walk-forward optimization. |
| fixed_weight_out_of_time_validation_completed | True |
| point_in_time_panel_built | True |
| what_was_done | The selected Phase2 weights were applied to EDINET submit-date based annual snapshots to verify candidate-universe quality outside the original snapshot. |
| what_was_not_done | Weights were not re-optimized within each training window and evaluated on multiple independent future test windows. |
| claim_allowed | Point-in-time fixed-weight out-of-time validation was performed. |
| claim_not_allowed | Strict train/test walk-forward optimization proved future predictive performance. |
