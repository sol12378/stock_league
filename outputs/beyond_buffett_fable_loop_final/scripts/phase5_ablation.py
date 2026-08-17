#!/usr/bin/env python
"""Phase5 ablation (A1-A16) for BEYOND BUFFETT Fable loop.

Fixes v2 defect D6 (constant `interpretation` string) by regenerating each
variant's interpretation from its overlap / jaccard and the role/theme tendency
of the names that changed in and out. Adds A16 (defect D4 quantification):
the ai_keyword_only guard is relaxed so it binds only on Emerging-family roles
(Emerging Core / Dual Moat) and NOT on Transformation Core / Bridge.

Method: the v2 selection logic in phase3_v2_pipeline.select_final is the source
of truth. We reload the scoring master, coerce CSV string/NaN back to the dtypes
the in-memory pipeline used, and VERIFY the base variant reproduces the canonical
Final20 before trusting any variant. All code comparison uses normalize_code.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
SEL = ROOT / "outputs/phase3_beyond_buffett_v2/scripts/phase3_selection"
sys.path.insert(0, str(SEL))
import phase3_v2_pipeline as P  # noqa: E402

OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
P5 = OUT / "phase5_verification_and_ablation"
FIG = OUT / "figures"

CANONICAL = {"3539", "4350", "6430", "7803", "9470",       # Buffett Core
             "5902", "9828", "5233", "8037", "3863",       # Transformation Core
             "6368", "6315", "6920", "6526", "5803",       # Emerging Core
             "3697", "6841", "9474",                        # Dual Moat
             "3089", "2112"}                                # Bridge

# ---------------------------------------------------------------- load + repair
d = pd.read_csv(P.DATA / "phase3_scoring_master.csv", low_memory=False)
boolish = [c for c in d.columns if c.endswith("_flag")
           or c in ("phase3_review_required", "phase2_review_required")]
for c in boolish:
    d[c] = P.bools(d[c])
# NaN category -> "" so ("" or "non_ai") == "non_ai" (matches in-memory pipeline)
d["emerging_evidence_category"] = d["emerging_evidence_category"].fillna("")

base = P.select_final(d, "base")
base_codes = set(P.norm_series(base["code"]))
assert base_codes == CANONICAL, f"base does not reproduce Final20: {base_codes ^ CANONICAL}"
print("[ok] base variant reproduces canonical Final20 (20/20)")

# lookup tables for interpretation tendency
role_of = dict(zip(P.norm_series(d["code"]), d["role_candidate"].astype(str)))
theme_of = dict(zip(P.norm_series(d["code"]),
                    d["emerging_evidence_category"].replace("", "non_ai").astype(str)))
sector_of = dict(zip(P.norm_series(d["code"]), d["sector"].astype(str)))


def tendency(codes):
    """dominant theme + sector of a code set, as a short JP phrase."""
    if not codes:
        return "なし"
    th = Counter(theme_of.get(c, "non_ai") for c in codes).most_common(1)[0]
    se = Counter(sector_of.get(c, "") for c in codes).most_common(1)[0]
    return f"テーマ={th[0]}({th[1]}), 業種={se[0]}({se[1]})"


def interpret(variant, desc, overlap, jaccard, cin, cout):
    if overlap >= 15:
        head = f"重複{overlap}/20：構成は頑健。この要素を外しても中核は概ね維持される。"
    elif overlap >= 10:
        head = f"重複{overlap}/20：中程度の入替。この要素は選定を有意に形づくるが支配的ではない。"
    else:
        head = f"重複{overlap}/20（Jaccard {jaccard:.2f}）：大幅な入替。この要素が選定の主要ドライバーである。"
    io = ""
    if cin or cout:
        io = f" 流入傾向[{tendency(cin)}] / 流出傾向[{tendency(cout)}]。"
    return head + io


# ---------------------------------------------------------------- A1-A15
labels = {
    "A1": "Transformation Score のみで選定",
    "A2": "Emerging Score のみで選定",
    "A3": "Evidence Level を外して選定",
    "A4": "Value Trap Penalty を外して選定",
    "A5": "Theme Hype Penalty を外して選定",
    "A6": "Phase2 Confidence を外して選定",
    "A7": "業種制約を外して選定",
    "A8": "Top100 だけから選定",
    "A9": "Top300 だけから選定",
    "A10": "Top1200 全体から選定",
    "A11": "Buffett Core 固定を外して選定",
    "A12": "Dual Moat 枠を外して選定",
    "A13": "Bridge 枠を外して選定",
    "A14": "Emerging Evidence Level>=2 制約を外して選定",
    "A15": "Transformation Reform Evidence を外して選定",
}

rows = []
for key, desc in labels.items():
    sel = P.select_final(d, key)
    codes = set(P.norm_series(sel["code"]))
    overlap = len(codes & CANONICAL)
    union = codes | CANONICAL
    jaccard = overlap / len(union) if union else 0.0
    cin = sorted(codes - CANONICAL)
    cout = sorted(CANONICAL - codes)
    rows.append({
        "variant": key, "description": desc, "selected_count": len(codes),
        "overlap_with_final20": overlap, "jaccard_with_final20": round(jaccard, 4),
        "role_distribution": json.dumps(sel["final_role"].value_counts().to_dict(), ensure_ascii=False),
        "sector_distribution": json.dumps(sel["sector"].value_counts().to_dict(), ensure_ascii=False),
        "theme_distribution": json.dumps(
            sel["emerging_evidence_category"].replace("", "non_ai").value_counts().to_dict(),
            ensure_ascii=False),
        "changed_in": ";".join(cin), "changed_out": ";".join(cout),
        "interpretation": interpret(key, desc, overlap, jaccard, cin, cout),
    })

# ---------------------------------------------------------------- A16 (D4)
# Relax ai_keyword_only so it binds ONLY on Emerging-family roles. All other
# guards (base_hard_exclusion except Top5, low_pbr_only, sector<=3, theme<=4
# except non_ai) stay ON. Selection order mirrors the base variant.
EMERGING_FAMILY = {"Emerging Core", "Dual Moat"}


def can_add_a16(row, selected, target_role):
    if bool(row.get("base_hard_exclusion_flag", False)) and not bool(row.get("phase1_top5_flag", False)):
        return False
    if bool(row.get("low_pbr_only_flag", False)):
        return False
    if bool(row.get("ai_keyword_only_flag", False)) and target_role in EMERGING_FAMILY:
        return False  # guard relaxed: only binds on emerging-family roles
    sectors = Counter(str(x.get("sector", "")) for x in selected)
    if sectors[str(row.get("sector", ""))] >= 3:
        return False
    theme = str(row.get("emerging_evidence_category", "") or "non_ai")
    themes = Counter(str(x.get("emerging_evidence_category", "") or "non_ai") for x in selected)
    if theme != "non_ai" and themes[theme] >= 4:
        return False
    return True


def select_a16(d):
    d = d.copy()
    selected = []
    fixed = d[P.bools(d.get("phase1_top5_flag"), d.index)].sort_values("phase2_rank")
    for _, r in fixed.iterrows():
        rec = r.to_dict(); rec["final_role"] = "Buffett Core"; selected.append(rec)
    chosen = {x["code"] for x in selected}
    specs = [
        ("Dual Moat", 3, "dual_combined_score"),
        ("Emerging Core", 5, "emerging_score"),
        ("Transformation Core", 5, "transformation_score"),
        ("Bridge / Diversifier", 2, "bridge_score"),
    ]
    num = P.num
    for role, quota, score in specs:
        if role == "Dual Moat":
            pool = d[(d["transformation_grade"].isin(["A", "B"]) | num(d["transformation_score"], d.index).ge(60))
                     & d["emerging_grade"].isin(["A", "B"]) & num(d["emerging_disclosure_level"], d.index).ge(2)]
        elif role == "Emerging Core":
            pool = d[d["emerging_grade"].isin(["A", "B"]) & num(d["emerging_disclosure_level"], d.index).ge(2)]
        elif role == "Transformation Core":
            pool = d[d["transformation_grade"].isin(["A", "B"])]
        else:
            pool = d[~P.bools(d.get("base_hard_exclusion_flag"), d.index)]
        pool = pool[~pool["code"].isin(chosen)].copy()
        pool["_score"] = num(pool[score])
        picked = 0
        for _, r in pool.sort_values("_score", ascending=False).iterrows():
            if not can_add_a16(r, selected, role):
                continue
            rec = r.to_dict(); rec["final_role"] = role
            selected.append(rec); chosen.add(rec["code"]); picked += 1
            if picked >= quota:
                break
    if len(selected) < 20:
        pool = d[~d["code"].isin(chosen) & ~P.bools(d.get("base_hard_exclusion_flag"), d.index)].copy()
        pool["_score"] = pool[["transformation_score", "emerging_score", "bridge_score"]].apply(pd.to_numeric, errors="coerce").max(axis=1)
        for _, r in pool.sort_values("_score", ascending=False).iterrows():
            role = r.get("role_candidate", "Bridge / Diversifier")
            if not can_add_a16(r, selected, role):
                continue
            rec = r.to_dict(); rec["final_role"] = role
            selected.append(rec)
            if len(selected) >= 20:
                break
    out = pd.DataFrame(selected).drop_duplicates("code").head(20).copy()
    return out


a16 = select_a16(d)
codes = set(P.norm_series(a16["code"]))
overlap = len(codes & CANONICAL)
union = codes | CANONICAL
jaccard = overlap / len(union) if union else 0.0
cin = sorted(codes - CANONICAL)
cout = sorted(CANONICAL - codes)
rows.append({
    "variant": "A16",
    "description": "ai_keyword_only ガードを Emerging系役割(Emerging Core/Dual Moat)のみに限定（D4定量化）",
    "selected_count": len(codes),
    "overlap_with_final20": overlap, "jaccard_with_final20": round(jaccard, 4),
    "role_distribution": json.dumps(a16["final_role"].value_counts().to_dict(), ensure_ascii=False),
    "sector_distribution": json.dumps(a16["sector"].value_counts().to_dict(), ensure_ascii=False),
    "theme_distribution": json.dumps(
        a16["emerging_evidence_category"].replace("", "non_ai").value_counts().to_dict(), ensure_ascii=False),
    "changed_in": ";".join(cin), "changed_out": ";".join(cout),
    "interpretation": interpret("A16", "A16", overlap, jaccard, cin, cout)
    + " ガードを Transformation/Bridge に効かせない場合の影響を示す。重複が高いほど、当該ガードが最終選定に対して過度に拘束的でないことを意味する。",
})

abl = pd.DataFrame(rows)
abl.to_csv(P5 / "ablation_results.csv", index=False)
print(abl[["variant", "overlap_with_final20", "jaccard_with_final20"]].to_string(index=False))

# ---------------------------------------------------------------- figure
fig, ax = plt.subplots(figsize=(9, 4.2))
colors = ["0.3" if v == "A8" else ("0.75" if o >= 15 else "0.55")
          for v, o in zip(abl["variant"], abl["overlap_with_final20"])]
bars = ax.bar(abl["variant"], abl["overlap_with_final20"], color=colors, edgecolor="black")
ax.axhline(20, color="black", lw=0.8, ls=":")
ax.axhline(15, color="0.4", lw=0.8, ls="--")
ax.text(len(abl) - 0.4, 20.2, "Final20 = 20", fontsize=7, ha="right")
ax.text(len(abl) - 0.4, 15.2, "stable >= 15", fontsize=7, ha="right", color="0.3")
mi = int(abl["overlap_with_final20"].idxmin())
ax.annotate(f"min: A8={abl.loc[mi,'overlap_with_final20']}\n(Top100 universe drives selection)",
            xy=(mi, abl.loc[mi, "overlap_with_final20"]),
            xytext=(mi + 1.2, abl.loc[mi, "overlap_with_final20"] + 4),
            fontsize=7, arrowprops=dict(arrowstyle="->", color="black", lw=0.8))
ax.set_ylabel("overlap with Final20 (of 20)")
ax.set_title("Ablation: overlap of each variant's selection with Final20 (in-sample, structural)")
ax.set_ylim(0, 22)
fig.tight_layout()
fig.savefig(FIG / "ablation_overlap.png", dpi=200)
plt.close(fig)
print("\nwritten:", P5 / "ablation_results.csv", "and", FIG / "ablation_overlap.png")
