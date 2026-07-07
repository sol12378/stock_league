# portfolio allocation rationale

投資額は 5,000,000円、購入単位は1株、1銘柄上限は 8% とした。
実投資額は 4,999,452円、残現金は 548円。

配分は adjusted_bb_score を正値化して正規化し、上限8%を掛けた後、残現金を上位スコア銘柄へ1株単位で追加した。
比較として等金額配分、カテゴリ均等配分、リスク調整配分も作成した。

## Role allocation
- 守る堀: 5社、22.7%
- 変わる堀: 6社、36.5%
- 生まれる堀: 7社、32.2%
- 分散・橋渡し枠: 2社、8.7%

## Sector concentration
- Electric Appliances: 5社、22.6%
- Electric Power and Gas: 3社、15.7%
- Machinery: 3社、13.3%
- Chemicals: 2社、8.6%
- Land Transportation: 1社、8.0%
- Insurance: 1社、8.0%
- Metal Products: 1社、6.0%
- Securities and Commodities Futures: 1社、4.9%

## Strategy comparison
- adjusted_bb_score加重: 投資額4,912,164円、残現金87,836円、最大比率7.3%
- 等金額配分: 投資額4,902,585円、残現金97,415円、最大比率5.0%
- カテゴリ均等配分: 投資額4,895,576円、残現金104,424円、最大比率8.0%
- リスク調整配分: 投資額4,882,844円、残現金117,156円、最大比率8.0%
