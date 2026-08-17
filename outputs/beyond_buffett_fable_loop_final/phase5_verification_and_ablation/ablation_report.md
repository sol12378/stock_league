# Phase5 — アブレーション報告書（A1〜A16）

**フレーミング（厳守）**: 本ポートフォリオは 2026-06 時点で入手可能なデータから構築されており、あらゆる履歴的シミュレーションは構造上 in-sample である。本節のアブレーションは**「Final20 が単一要素・単一テーマ・後付け最適化に依存していないこと」を確認する構造検査**であり、将来リターンの主張ではない。指標は overlap（20 銘柄中いくつが一致するか）と Jaccard 係数、および流入・流出銘柄の役割／テーマ傾向である。

**コード照合**: 全変種で `normalize_code`（str 化 → BOM/`.T` 除去 → 数字部抽出 → zfill(4)）を用いて Final20 と突合。**ベースライン（全ガード適用）が実際の Final20 を 20/20 で再現することを確認したうえで**各変種を実行した（`scripts/phase5_ablation.py` 冒頭の assert）。A1〜A15 の overlap は Phase3 v2 の `phase3_ablation_results.csv` と完全一致し、実装の同一性を担保している。

---

## 1. 結果一覧

| 変種 | 内容 | overlap/20 | Jaccard | 解釈の要点 |
|---|---|---:|---:|---|
| A1 | Transformation Score のみで選定 | 12 | 0.43 | 中程度の入替。Emerging（半導体・電機）が抜け non_ai が流入 |
| A2 | Emerging Score のみで選定 | 16 | 0.67 | 頑健。中核は概ね維持 |
| A3 | Evidence Level を外す | 13 | 0.48 | 中程度。cybersecurity 等の低根拠名が流入、non_ai が流出 |
| A4 | Value Trap Penalty を外す | 16 | 0.67 | 頑健。入替は限定的 |
| A5 | Theme Hype Penalty を外す | 13 | 0.48 | 中程度。ペナルティは選定を有意に形づくる |
| A6 | Phase2 Confidence を外す | 15 | 0.60 | 頑健 |
| A7 | 業種制約を外す | 13 | 0.48 | 中程度。業種上限がなければ Machinery 等に集中 |
| **A8** | **Top100 だけから選定** | **7** | **0.21** | **最小。母集団の広さが選定の主要ドライバー** |
| A9 | Top300 だけから選定 | 12 | 0.43 | 中程度。母集団を狭めると入替が進む |
| A10 | Top1200 全体から選定 | 15 | 0.60 | 頑健 |
| A11 | Buffett Core 固定を外す | 11 | 0.38 | 中程度。固定を外すと Top5 の一部が押し出される |
| A12 | Dual Moat 枠を外す | 16 | 0.67 | 頑健 |
| A13 | Bridge 枠を外す | 16 | 0.67 | 頑健 |
| A14 | Emerging Evidence Level≥2 制約を外す | 15 | 0.60 | 頑健。ただし低根拠名の混入余地が生じる |
| A15 | Transformation Reform Evidence を外す | 15 | 0.60 | 頑健（TR は全社=1 で識別力ゼロのため） |
| **A16** | **ai_keyword_only ガードを Emerging系役割のみに限定（D4）** | **16** | **0.67** | **頑健。ガードを Transformation/Bridge に効かせなくても中核不変** |

数値の一次ソース: `ablation_results.csv`（A1〜A16、role/sector/theme distribution・changed_in/out・interpretation を全行格納）。図: `../figures/ablation_overlap.png`（A8=7 を最小点として強調）。

---

## 2. 解釈

### 2.1 単一要素依存の否定
Transformation のみ（A1, overlap 12）、Emerging のみ（A2, 16）、いずれもベースを完全再現しない。**片方のスコアだけでは Final20 は再現できず**、変わる Moat と生まれる Moat の二軸合成が選定の本体であることを示す。とりわけ A1 では半導体・電機（Emerging Core の 6315/6920/6526/5803 等）が脱落し non_ai の Value 系が流入する——Emerging 軸が Final20 の「生まれる Moat」を担っていることの裏返しである。

### 2.2 母集団の広さが最大の駆動要因（A8/A9/A10）
overlap が最小になるのは **A8（Top100 限定, 7/20）**。Phase2 で母集団を Top1200 に広げた「破」の意思決定こそが、Final20 の過半を規定している。Top100 に絞ると流入 13 銘柄が non_ai（Foods 中心）に偏り、Emerging・Transformation の中核が失われる。A9（Top300, 12）→ A10（Top1200, 15）と母集団を広げるほどベースに近づく。**これは「Top1200 を正式母集団とする」設計の妥当性を定量的に裏づける**（設計の後付けではなく前提が効いている）。

### 2.3 ペナルティ・証拠制約は「効いているが支配的ではない」
Value Trap（A4, 16）、Theme Hype（A5, 13）、Evidence Level（A3, 13）、Emerging L2 制約（A14, 15）はいずれも overlap を下げるが 10 未満にはしない。**ガードは選定を有意に整形するが、これらを外しても選定が崩壊するわけではない**——恣意的な一撃で結果を作っていないことの証左。

### 2.4 役割設計の妥当性（A11/A12/A13）
Buffett 固定を外す A11（11）は最も影響が大きく、**Top5 を「守」の土台として明示的に固定する意思決定が構成に本質的**であることを示す。一方 Dual/Bridge 枠除去（A12/A13, ともに 16）は影響が小さく、これらは構成の「調整弁」であって中核ではない。

### 2.5 A16 — ai_keyword_only ガードの D4 検証（新規）
Phase3 の `ai_keyword_only` ガードは全役割に一律適用されている（v2 実装）。これが Transformation Core / Bridge のような非 Emerging 役割にまで過度に拘束的でないかを定量化したのが A16 である。ガードを **Emerging Core / Dual Moat のみに限定**して再選定すると overlap は 16——**流出 4（2112, 3863, 5233, 8037：いずれも non_ai の Transformation/Bridge 名）、流入 4（1961, 4113, 9612, 9616：quality_assurance/Services 系）**にとどまる。すなわち当該ガードは Final20 に対して**過度に拘束的ではなく**、緩めても Buffett/Emerging 中核と Dual Moat は不変である。D4（AI キーワード単独ガードの緊張）は、選定結果を歪める規模ではないと結論できる。ただし緩和すると Transformation 枠に quality_assurance 系が混入するため、**保守的にガードを維持する**という現行判断は説明可能である。

---

## 3. 限界
- overlap/Jaccard は **構造的類似度**であり、リターン優劣ではない。in-sample であることは §performance_validation.md および risk_analysis.md に明記。
- A16 の流入名（1961 等）の Emerging 根拠水準は本ループでは未精査。ガード緩和を採用しない理由（証拠水準の担保）と整合。
- TR（改革開示レベル）は Top1200 全社=1 で識別力ゼロ（A15 が頑健なのはこのため）。最終論文で TR を選定根拠として引用しない。
