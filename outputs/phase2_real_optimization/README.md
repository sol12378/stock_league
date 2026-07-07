# BEYOND BUFFETT Phase2 Real Optimization

## この成果物の位置づけ

これはBEYOND BUFFETT Phase2（破）の本格最適化版である。  
Phase1の正式ルールを置き換えるものではない。  
Phase1で使った先行研究式の定義は変えていない。  
本成果物では、本物のOptuna TPEとNSGA-IIを用いて、重み・候補群サイズ・欠損処理・業種調整・TopNの妥当性を検証した。

## 重要な結論

- selected TopN: 2000
- Top1200 optimal: False
- Top1200 defensible: True
- Phase1 Top5 coverage in Top1200: 5/5
- selected weights: `{"bm": 0.18445915574257452, "distress": 0.2506101343460851, "ep": 0.05724894173929047, "gp": 0.14717910156895553, "liquidity": 0.33011280681347804, "piotroski": 0.009821470657685773, "sloan": 0.020568389131930525}`
- Optuna trial数: 5000
- NSGA-II trial数: 3000
- stability結果: `{"top100_jaccard": 0.7316037805236146, "top300_jaccard": 0.7258616732282179, "top1000_jaccard": 0.7403021217327665, "top1200_jaccard": 0.7505669348883376}`

## 注意

Exploratory Weighted Buffett Scoreは正式なBuffett Scoreではない。  
将来リターン最大化モデルではない。  
AIは銘柄を直接選ぶのではなく、Phase1式の使い方を比較・検証するために使った。
