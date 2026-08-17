#!/usr/bin/env python
"""Phase3 rebuild: fix D1 (role-aware final_evidence_level), regenerate
phase3_moat_construction CSVs from canonical v2 data, and run +/-20% weight
sensitivity for Transformation / Emerging scores.

Selection membership is NOT changed: the v2 selection gates use
emerging_disclosure_level / grades, never final_evidence_level (verified by
code audit). Only the reported final_evidence_level is corrected.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats  # available? fall back if not

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
V2 = ROOT / "outputs/phase3_beyond_buffett_v2/data"
OUT = ROOT / "outputs/beyond_buffett_fable_loop_final"
P3 = OUT / "phase3_moat_construction"
P3.mkdir(parents=True, exist_ok=True)
(OUT / "data").mkdir(exist_ok=True)


def normalize_code(x) -> str:
    s = str(x).strip().replace(".T", "").replace("﻿", "")
    s = s.split(".")[0]
    return s.zfill(4)


m = pd.read_csv(V2 / "phase3_scoring_master.csv")
f20 = pd.read_csv(V2 / "phase3_final20_selected.csv")
m["code_n"] = m["code"].map(normalize_code)
f20["code_n"] = f20["code"].map(normalize_code)
final_role = f20.set_index("code_n")["final_role"]
sel_order = f20.set_index("code_n")["selection_order"]
m["final_role"] = m["code_n"].map(final_role)
m["in_final20"] = m["final_role"].notna()

# ---- D1 fix: role-aware final evidence level -------------------------------
TQ = m["transformation_quant_evidence_level"].fillna(0).astype(int)
TR = m["transformation_reform_disclosure_level"].fillna(0).astype(int)
TS = m["transformation_shareholder_return_evidence_level"].fillna(0).astype(int)
EM = m["emerging_disclosure_level"].fillna(0).astype(int)
role_eff = m["final_role"].fillna(m["role_candidate"])  # final role wins

fel = np.maximum(TQ, EM)  # default
fel = np.where(role_eff == "Transformation Core", np.maximum.reduce([TQ, TS, TR]), fel)
fel = np.where(role_eff == "Emerging Core", EM, fel)
fel = np.where(role_eff == "Dual Moat", np.minimum(TQ, np.maximum(EM, 0)), fel)
m["final_evidence_level_v2_buggy"] = m["final_evidence_level"]
m["final_evidence_level"] = fel.astype(int)
m["final_evidence_level_changed"] = m["final_evidence_level"] != m["final_evidence_level_v2_buggy"]

# ---- outputs ----------------------------------------------------------------
id_cols = ["code_n", "code", "company_name", "sector"]

trans_cols = id_cols + [
    "valuation_gap_score", "capital_efficiency_improvement_score", "fcf_proxy_score",
    "execution_reliability_score", "quality_trap_resistance_score", "phase2_confidence_score",
    "value_trap_penalty", "value_trap_penalty_reasons", "transformation_partial_score",
    "transformation_lite_score", "transformation_score", "transformation_score_type",
    "transformation_fullness_score", "transformation_grade",
]
m[trans_cols].to_csv(P3 / "transformation_scores.csv", index=False)

emerg_cols = id_cols + [
    "intangible_capital_score", "innovation_capacity_score", "bottleneck_pricing_power_score",
    "ai_infrastructure_exposure_score", "data_customer_base_score", "trust_safety_infrastructure_score",
    "evidence_level_bonus", "theme_hype_penalty", "financial_guardrail_penalty",
    "emerging_score", "emerging_grade", "emerging_evidence_category", "emerging_keyword_only_flag",
]
m[emerg_cols].to_csv(P3 / "emerging_scores.csv", index=False)

ev_cols = id_cols + [
    "transformation_quant_evidence_level", "transformation_reform_disclosure_level",
    "transformation_shareholder_return_evidence_level", "emerging_disclosure_level",
    "final_evidence_level", "final_evidence_level_v2_buggy", "final_evidence_level_changed",
    "curated_evidence_flag", "systematic_screening_flag", "role_candidate", "final_role",
]
m[ev_cols].to_csv(P3 / "evidence_levels.csv", index=False)

role_cols = id_cols + [
    "transformation_score", "emerging_score", "dual_combined_score", "bridge_score",
    "transformation_grade", "emerging_grade", "role_candidate", "final_role",
    "ai_keyword_only_flag", "low_pbr_only_flag", "base_hard_exclusion_flag",
]
m[role_cols].to_csv(P3 / "role_assignment.csv", index=False)

score_cols = id_cols + [
    "phase2_rank", "phase2_confidence_score", "transformation_score", "emerging_score",
    "transformation_quant_evidence_level", "emerging_disclosure_level", "final_evidence_level",
    "transformation_grade", "emerging_grade", "role_candidate", "final_role",
    "ai_infrastructure_category", "close", "avg_trading_value_60d",
]
m[score_cols].to_csv(P3 / "phase3_scorecard.csv", index=False)

# final20 files: corrected evidence level merged in
f20u = f20.drop(columns=["final_evidence_level"], errors="ignore").merge(
    m[["code_n", "final_evidence_level", "final_evidence_level_v2_buggy", "final_evidence_level_changed"]],
    on="code_n", how="left",
)
f20u.to_csv(P3 / "final20_selected.csv", index=False)
cand = pd.read_csv(V2 / "phase3_final20_candidates.csv")
cand.to_csv(P3 / "final20_candidates.csv", index=False)

# summary of the fix on the final 20
f20s = f20u[["code_n", "company_name", "sector", "final_role",
             "transformation_score", "emerging_score",
             "final_evidence_level", "final_evidence_level_v2_buggy"]].copy()
f20s = f20s.sort_values("final_role")
print("=== Final20 corrected evidence levels ===")
print(f20s.to_string(index=False))
print("\ncorrected distribution:", f20u["final_evidence_level"].value_counts().sort_index().to_dict())
print("buggy distribution:    ", f20u["final_evidence_level_v2_buggy"].value_counts().sort_index().to_dict())
print("changed rows in final20:", int(f20u["final_evidence_level_changed"].sum()))
print("changed rows in 1200:   ", int(m["final_evidence_level_changed"].sum()))

# ---- +/-20% weight sensitivity ----------------------------------------------
def spearman(a, b):
    ar = pd.Series(a).rank()
    br = pd.Series(b).rank()
    return float(np.corrcoef(ar, br)[0, 1])

sens_rows = []

# Transformation partial score reconstruction
tw = {"valuation_gap_score": 0.22, "capital_efficiency_improvement_score": 0.24,
      "fcf_proxy_score": 0.10, "execution_reliability_score": 0.18,
      "quality_trap_resistance_score": 0.16, "conf": 0.10}
conf_term = (m["phase2_confidence_score"].fillna(0) / 1.1) * 100
comp = {k: m[k].fillna(0) for k in list(tw)[:-1]}
comp["conf"] = conf_term
trap = m["value_trap_penalty"].fillna(0)
base_T = sum(comp[k] * w for k, w in tw.items()) - trap
base_T = base_T.clip(0, 100)

t_core = set(f20u.loc[f20u.final_role == "Transformation Core", "code_n"])
pool_t = m[(m.role_candidate == "Transformation Core") & (~m.ai_keyword_only_flag.fillna(False))
           & (~m.low_pbr_only_flag.fillna(False)) & (~m.base_hard_exclusion_flag.fillna(False))
           & (m.final_role.isna() | m.final_role.eq("Transformation Core"))].copy()

for wname in tw:
    for mult in (0.8, 1.2):
        w2 = dict(tw)
        w2[wname] = tw[wname] * mult
        s = sum(w2.values())
        w2 = {k: v / s for k, v in w2.items()}
        varT = (sum(comp[k] * w for k, w in w2.items()) - trap).clip(0, 100)
        rho = spearman(base_T, varT)
        top5 = set(pool_t.assign(v=varT.loc[pool_t.index]).nlargest(5, "v")["code_n"])
        sens_rows.append({"score": "transformation", "weight": wname, "mult": mult,
                          "spearman_vs_base": round(rho, 4),
                          "selected5_in_variant_top5": len(t_core & top5)})

# Emerging score reconstruction
ew = {"intangible_capital_score": 0.18, "innovation_capacity_score": 0.15,
      "bottleneck_pricing_power_score": 0.18, "ai_infrastructure_exposure_score": 0.22,
      "data_customer_base_score": 0.14, "trust_safety_infrastructure_score": 0.13}
ecomp = {k: m[k].fillna(0) for k in ew}
eextra = m["evidence_level_bonus"].fillna(0) - m["theme_hype_penalty"].fillna(0) - m["financial_guardrail_penalty"].fillna(0)
base_E = (sum(ecomp[k] * w for k, w in ew.items()) + eextra).clip(0, 100)

e_core = set(f20u.loc[f20u.final_role == "Emerging Core", "code_n"])
pool_e = m[(EM >= 2) & (~m.base_hard_exclusion_flag.fillna(False))].copy()

for wname in ew:
    for mult in (0.8, 1.2):
        w2 = dict(ew)
        w2[wname] = ew[wname] * mult
        s = sum(w2.values())
        w2 = {k: v / s for k, v in w2.items()}
        varE = (sum(ecomp[k] * w for k, w in w2.items()) + eextra).clip(0, 100)
        rho = spearman(base_E, varE)
        # top8 of EM>=2 pool (5 emerging + 3 dual candidates share this pool)
        top8 = set(pool_e.assign(v=varE.loc[pool_e.index]).nlargest(8, "v")["code_n"])
        sens_rows.append({"score": "emerging", "weight": wname, "mult": mult,
                          "spearman_vs_base": round(rho, 4),
                          "selected5_in_variant_top8": len(e_core & top8)})

sens = pd.DataFrame(sens_rows)
sens.to_csv(P3 / "weight_sensitivity_pm20.csv", index=False)
print("\n=== weight sensitivity (min spearman) ===")
print(sens.groupby("score")["spearman_vs_base"].min())
tcol = sens.loc[sens.score == "transformation", "selected5_in_variant_top5"]
ecol = sens.loc[sens.score == "emerging", "selected5_in_variant_top8"]
print("transformation: selected5 retained in variant top5, min/max:", int(tcol.min()), int(tcol.max()))
print("emerging: selected5 retained in variant top8, min/max:", int(ecol.min()), int(ecol.max()))

# consistency check vs stored scores
chk_T = float((base_T - m["transformation_partial_score"].fillna(base_T)).abs().max())
chk_E = float((base_E - m["emerging_score"].fillna(base_E)).abs().max())
print("\nreconstruction max abs diff: T=", round(chk_T, 3), " E=", round(chk_E, 3))

json.dump({
    "final20_membership_changed": False,
    "evidence_level_changed_in_final20": int(f20u["final_evidence_level_changed"].sum()),
    "evidence_level_changed_in_1200": int(m["final_evidence_level_changed"].sum()),
    "corrected_final20_distribution": {str(k): int(v) for k, v in f20u["final_evidence_level"].value_counts().sort_index().items()},
    "buggy_final20_distribution": {str(k): int(v) for k, v in f20u["final_evidence_level_v2_buggy"].value_counts().sort_index().items()},
    "sensitivity_min_spearman": {"transformation": float(sens.loc[sens.score=='transformation','spearman_vs_base'].min()),
                                  "emerging": float(sens.loc[sens.score=='emerging','spearman_vs_base'].min())},
    "reconstruction_max_abs_diff": {"transformation": chk_T, "emerging": chk_E},
}, open(P3 / "phase3_rebuild_summary.json", "w"), indent=2)
print("\nwritten to", P3)
