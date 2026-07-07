# BEYOND BUFFETT Phase2 Top1200 Walk-forward Fix

## この成果物の位置づけ

これはBEYOND BUFFETT Phase2（破）のTop1200正式候補群版である。  
utility最大化ではTop2000が最良だったが、Phase3で分析可能な候補群としてTop1200を正式採用した。  
Top2000は取りこぼし確認用の参照群として残した。

## 主な修正

1. Phase2正式候補群をTop1200に固定
2. Walk-forward validationを可能な範囲で実施
3. 正規化方式感度問題に対してnormalization consensusを導入
4. Top1200候補にnormalization core / robust / fragile flagsを追加
5. Phase3へのhandoffを整備

## 重要な結論

- selected_topn: 1200
- utility_max_topn: 2000
- phase1_top5_coverage: 5/5
- walk_forward_level: Level 2
- normalization_core_count: 1024
- normalization_robust_count: 1320
- normalization_fragile_count: 29

## 注意

Exploratory Weighted Buffett Scoreは正式なPhase1式ではない。  
将来リターン最大化モデルではない。  
Phase2の目的は、Phase3で「変わるMoat」「生まれるMoat」を評価するための候補宇宙を作ることである。
