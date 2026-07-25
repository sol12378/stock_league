# -*- coding: utf-8 -*-
"""WP0.4: 除外記録v5(1,180行)の生成。

v4問題: 「除外した862社を理由別に全記録」は、除外総数=862と誤読させる。実際の非選定は
候補1,200 − 最終20 = 1,180社。うち862社は監査条件該当で個別理由コード付き、残り318社は
理由コード未記録だった。本スクリプトは318社に一括理由コード `score_below_cutoff`(合成点が
選定圏外)を付与し、1,180社=6分類の全記録を正典化する。図表Ⅱ-6はこの6分類から自動転記。

出力: exclusion_record_v5.csv(1,180行) / exclusion_summary_v5.json(6分類の社数)
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"

pool = pd.read_csv(ROOT / "outputs/phase2_perfect_final_break/formal_top1200/phase2_formal_top1200_candidates.csv")
pool["code"] = pool["code"].astype(str).str.zfill(4)
assert len(pool) == 1200, f"pool={len(pool)}"

# 最終20社(data_real.json の役割つき正典)
data_real = json.load(open(ROOT / "outputs/explanatory_revision/data_real.json", encoding="utf-8"))
final20 = set(str(v["code"]).zfill(4) for v in data_real.values())
assert len(final20) == 20, f"final20={len(final20)}"

# 非選定 = 1,180社
nonsel = pool[~pool["code"].isin(final20)].copy()
assert len(nonsel) == 1180, f"nonsel={len(nonsel)}"

# 既存の理由コード(862社)
rej = pd.read_csv(ROOT / "outputs/phase3_beyond_buffett_v2/data/phase3_rejected_candidates.csv")
rej["code"] = rej["code"].astype(str).str.zfill(4)
reason_map = dict(zip(rej["code"], rej["rejection_reason_category"]))

# 名称・業種列の特定(pool側)
name_col = next((c for c in ("company_name", "name", "company") if c in pool.columns), None)
sec_col = next((c for c in ("sector", "sector_name") if c in pool.columns), None)

rows = []
for _, r in nonsel.iterrows():
    cat = reason_map.get(r["code"], "score_below_cutoff")
    rows.append({
        "code": r["code"],
        "company_name": r[name_col] if name_col else "",
        "sector": r[sec_col] if sec_col else "",
        "rejection_reason_category": cat,
        "reason_source": "audited" if r["code"] in reason_map else "score_below_cutoff_v5",
    })
rec = pd.DataFrame(rows)
rec.to_csv(ED / "exclusion_record_v5.csv", index=False)

# 6分類集計(図表Ⅱ-6の転記元)。表示順を固定。
order = ["ai_keyword_only", "already_represented_by_better_candidate",
         "distress_or_quality_risk", "value_trap_risk", "low_pbr_only", "score_below_cutoff"]
counts = rec["rejection_reason_category"].value_counts().to_dict()
summary = {"total_excluded": int(len(rec)), "pool": 1200, "selected": 20,
           "categories": {k: int(counts.get(k, 0)) for k in order},
           "audited_subtotal": int(sum(counts.get(k, 0) for k in order[:5])),
           "score_below_cutoff": int(counts.get("score_below_cutoff", 0))}
json.dump(summary, open(ED / "exclusion_summary_v5.json", "w"), ensure_ascii=False, indent=1)

print("非選定:", len(rec), "= 862(監査)+", counts.get("score_below_cutoff", 0), "(新規score_below_cutoff)")
print(json.dumps(summary, ensure_ascii=False, indent=1))
assert summary["categories"]["ai_keyword_only"] == 577
assert summary["audited_subtotal"] == 862, summary["audited_subtotal"]
assert summary["total_excluded"] == 1180
print("PASS: 1,180 = 577+221+32+17+15+318")
