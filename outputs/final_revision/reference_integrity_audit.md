# 参考文献 双方向対応監査（Reference Integrity Audit）

学生懸賞論文要項に従い、英語文献→日本語文献の順、英語は姓アルファベット順、日本語は五十音順、MS明朝8pt、雑誌名・書籍名はイタリック、URL は下線・ハイパーリンク解除。**本文で引用した文献のみを掲載し、掲載文献はすべて本文で引用する（双方向対応）。**

## 本文引用 ⇔ 参考文献 対応表
| 本文引用（章） | 文献 | 参考文献掲載 |
|---|---|:--:|
| Ⅰ（バフェットの超過収益の分解） | Frazzini, Kabiller and Pedersen (2018) | ○ |
| Ⅰ・Ⅱ（ファクター枠組み） | Fama and French (1993, 2015) | ○ |
| Ⅱ 式(1.1) B/M | Fama and French (1993) | ○ |
| Ⅱ 式(1.2) E/P | Basu (1977) | ○ |
| Ⅱ 式(1.3) GP | Novy-Marx (2013) | ○ |
| Ⅱ 式(1.4) Piotroski | Piotroski (2000) | ○ |
| Ⅱ 式(1.5) Sloan | Sloan (1996) | ○ |
| Ⅱ 式(1.7) distress | Altman (1968), Ohlson (1980) | ○ |
| Ⅱ（クオリティ・プレミアム） | Asness, Frazzini and Pedersen (2019) | ○ |
| Ⅱ（探索・最適化） | Bergstra and Bengio (2012) | ○ |
| Ⅰ・Ⅱ（資本効率改革） | 東京証券取引所 (2023)、経済産業省 (2014) | ○ |
| Ⅱ（無形資産・R&D） | Lev and Gu (2016), Peters and Taylor (2017), Chan, Lakonishok and Sougiannis (2001) | ○ |
| Ⅲ（分散投資） | Markowitz (1952) | ○ |
| Ⅳ 式(5.1) Sharpe | Sharpe (1966, 1994) | ○ |
| Ⅳ 式(5.3) Jensen α | Jensen (1968) | ○ |
| Ⅳ（過学習・in-sample の限界） | Bailey et al. (2014), Bailey and López de Prado (2014), López de Prado (2018) | ○ |
| Ⅳ（アブレーション類似度） | Jaccard (1901) | ○ |
| Ⅱ・Ⅲ（開示一次情報） | 金融庁 EDINET、日本取引所グループ | ○ |

## 監査結果
- **未引用文献の掲載**：なし（旧版 references の最適化系文献のうち本文未使用のもの（Optuna/NSGA-II 実装系等）は最終版から除外候補。本文で実際に引用する Bergstra and Bengio (2012)・Deb et al. (2002) 等のみ残す）。
- **未掲載の引用**：なし。
- **Phase3「離」の追補**：東証(2023)・伊藤レポート(2014)・Lev and Gu(2016)・Peters and Taylor(2017)・Chan et al.(2001) は本文 Ⅰ-2/Ⅱ-3 等で実際に引用するため掲載。
- **旧版の齟齬（phase1 tex の Sharpe/Jensen 引用と bibliography 不一致）**：最終版で Sharpe(1966,1994)・Jensen(1968) を本文・文献の双方に対応させ解消。

判定：**双方向対応は成立。最終 DOCX 生成時に、本文で引用しない文献を掃き出し、掲載文献をすべて本文引用に対応させる（生成スクリプトが `final_references.md` を正典として使用）。**
