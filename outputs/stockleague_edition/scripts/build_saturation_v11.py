# -*- coding: utf-8 -*-
"""W5: the measurement problem (contribution A).

Two things, measured rather than asserted:

1. SATURATION. How much firm-level resolution the thematic-exposure score actually has,
   and the mechanism that destroys it. We do not merely count ties; we show the score is
   almost exactly a function of the 33-sector code, and we identify why from the
   construction: the keyword match runs over firm metadata (name, sector labels, market,
   scale category) rather than disclosure text, a hard-coded sector bonus is added on top,
   and the one continuous firm-level input -- R&D intensity, carrying 25% of the weight --
   is missing for all but 2 of 3,649 firms and silently imputed to zero.

2. THE EVIDENCE LADDER. The distribution of firms across the three evidence levels on the
   candidate pool, and the size of the level-1 (keyword-only) population that a
   disclosure-graded measure would have to triage.

Output: outputs/stockleague_edition/saturation_v11.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
P3 = ROOT / "outputs/phase3_beyond_buffett_v2"

SCORE = "future_moat_score"
TIE_EXAMPLES = ["6920", "6745", "7762", "6741", "6777"]

# ---------------------------------------------------------------- saturation
s = pd.read_csv(ROOT / "data/processed/scores.csv", dtype={"code": str}, low_memory=False)
s["code"] = s["code"].str.zfill(4)
s["fm"] = s[SCORE].round(4)
n_firms = len(s)

vc = s.fm.value_counts().sort_index(ascending=False)
shares = (vc / n_firms).values
tie_cluster = float(vc.idxmax()) if False else float(vc.index[vc.argmax()])
biggest = vc.max()

# the cluster the paper's example firms sit in
ex_val = float(s.loc[s.code == TIE_EXAMPLES[0], "fm"].iloc[0])
ex_cluster_n = int((s.fm == ex_val).sum())
n_above = int((s.fm > ex_val).sum())

sector_median = s.groupby("sector_33")["fm"].transform("median")
exact = int((s.fm == sector_median).sum())
g = s.groupby("sector_33")["fm"].agg(distinct="nunique", n="count")

saturation = {
    "score_column": SCORE,
    "n_firms": n_firms,
    "n_distinct_values": int(s.fm.nunique()),
    "effective_number_of_levels": round(float(1.0 / (shares ** 2).sum()), 2),
    "largest_tie_size": int(biggest),
    "top5_tie_sizes": [int(x) for x in vc.sort_values(ascending=False).head(5).values],
    "top5_tie_coverage_share": round(float(vc.sort_values(ascending=False).head(5).sum() / n_firms), 4),
    "example_cluster": {
        "score_value": ex_val,
        "n_firms_tied": ex_cluster_n,
        "n_firms_strictly_above": n_above,
        "firms": [{"code": c,
                   "name": str(s.loc[s.code == c, "company_name"].iloc[0]),
                   "sector": str(s.loc[s.code == c, "sector_33"].iloc[0]),
                   "business": biz}
                  for c, biz in zip(TIE_EXAMPLES,
                                    ["semiconductor photomask inspection; sole global supplier",
                                     "fire alarms and detection equipment",
                                     "wristwatches",
                                     "railway signalling",
                                     "optical test instruments for fibre networks"])],
    },
    "sector_determinism": {
        "firms_exactly_at_sector_median": exact,
        "share_exactly_at_sector_median": round(exact / n_firms, 4),
        "single_valued_sectors": int((g.distinct == 1).sum()),
        "n_sectors": int(len(g)),
        "firms_in_single_valued_sectors": int(g[g.distinct == 1].n.sum()),
    },
    "mechanism": {
        "matched_text_fields": ["company_name", "sector_33", "sector_17", "market", "scale_category"],
        "matched_disclosure_text": False,
        "hard_coded_sector_bonus": ("+2 to the AI-infrastructure bucket for Electric Appliances, "
                                    "Machinery, Chemicals, Nonferrous Metals, Metal Products and "
                                    "Precision Instruments; +2 to automation for Machinery, Electric "
                                    "Appliances, Precision Instruments and automobiles; +2 to "
                                    "data/software for Information & Communication and Services; +1 to "
                                    "trust/security for Services, Information & Communication and "
                                    "Insurance."),
        "continuous_firm_level_input": "R&D intensity (rd_ratio), weight 0.25",
        "rd_ratio_non_missing": int(s.rd_ratio.notna().sum()),
        "shares_outstanding_non_missing": int(s.shares_outstanding.notna().sum()),
        "rd_ratio_imputed_to_zero": int((s.intangible_investment_score == 0).sum()),
        "diagnosis": ("The only input that varies across firms within a sector is missing for all but "
                      "%d of %d firms and is filled with zero, so the score reduces to a weighted "
                      "function of sector membership. What is presented as a firm-level thematic "
                      "exposure measure is a sector label."
                      % (int(s.rd_ratio.notna().sum()), n_firms)),
    },
    "tie_table": [{"score": float(v), "n_firms": int(k)} for v, k in zip(vc.index, vc.values)],
}

# ---------------------------------------------------------------- evidence ladder
lev = pd.read_csv(P3 / "data/phase3_evidence_levels.csv", dtype=str)
rej = pd.read_csv(P3 / "data/phase3_rejected_candidates.csv", dtype=str, low_memory=False)
cur = pd.read_csv(P3 / "scripts/phase3_selection/curated_evidence.csv", dtype=str)

dist = lev.emerging_disclosure_level.value_counts().sort_index()
ladder = {
    "pool": "Top-1200 candidate pool from the contest edition's value-quality screen",
    "pool_size": int(len(lev)),
    "levels": {
        "0_no_thematic_link": int(dist.get("0", 0)),
        "1_keyword_hit_only": int(dist.get("1", 0)),
        "2_named_product_or_customer": int(dist.get("2", 0)),
        "3_disclosed_quantity": int(dist.get("3", 0)),
    },
    "operational_definition": {
        "level_1": ("A keyword match places the firm in a theme bucket, with no artefact naming a "
                    "product, a customer, or an investment plan. In the measure audited above the "
                    "match is against firm metadata, so level 1 is reachable without the firm having "
                    "said anything about the theme."),
        "level_2": ("A retrievable artefact -- a filing passage, product page, or IR document -- names "
                    "a specific product, a specific customer, or a specific committed investment tied "
                    "to the theme. The coder records the URL and the quoted passage."),
        "level_3": ("The artefact carries a number attributable to the theme: revenue, order book, "
                    "unit or customer count, or capital expenditure. The number and its as-of date "
                    "are recorded alongside the quotation."),
        "coding_protocol": ("Each level-2 and level-3 assignment in this study carries a source URL, a "
                            "source type, and a quoted snippet in curated_evidence.csv, so a third "
                            "party can re-open the artefact and disagree with the assignment. Level 1 "
                            "and level 0 are assigned mechanically and require no judgement."),
    },
    "curated_count": int(len(cur)),
    "curated_source_types": cur.source_type.value_counts().to_dict(),
    "keyword_only_rejected": int((rej.rejection_reason_category == "ai_keyword_only").sum()),
    "rejection_categories": rej.rejection_reason_category.value_counts().to_dict(),
    "honest_reading_of_the_577": (
        "The 577 figure is not 577 firms that discussed the theme in their filings and were found "
        "wanting on inspection. It is the residual: firms whose metadata matched a theme keyword and "
        "for which no level-2 or level-3 artefact was found, discarded as a block. The filings of "
        "these firms were not read. Stating it the other way round would overstate the work done."),
    "validation_status": {
        "validated": False,
        "what_is_missing": ("We have not shown that the ladder predicts anything. A validation would "
                           "require (i) coding the ladder at an as-of date from filings available "
                           "then, on a sample large enough to support a cross-sectional test; (ii) a "
                           "pre-specified outcome measured afterwards -- realised theme-attributable "
                           "revenue growth is the natural one, and is disclosed by only a minority of "
                           "firms; (iii) inter-coder agreement statistics on the level assignments, "
                           "since levels 2 and 3 require judgement; and (iv) a comparison against the "
                           "saturated keyword measure on the same sample and horizon. None of that is "
                           "in this paper."),
    },
}

# ---------------------------------------------------------------- audit of our own portfolio
# Applying the ladder to the portfolio this paper studies. This is the uncomfortable check:
# the manuscript previously described the fifteen discretionary holdings as "selected by reading
# disclosures", and the record does not support that description.
pfj = json.load(open(ROOT / "work/pure_buffett_benchmark/portfolio_v7.json"))
own_codes = [t.replace(".T", "") for t in pfj["weights_v7"]]
final20 = pd.read_csv(P3 / "data/phase3_final20_selected.csv", dtype=str, low_memory=False)

lev_idx = lev.set_index("code")
present = [c for c in own_codes if c in lev_idx.index]
absent = [c for c in own_codes if c not in lev_idx.index]
sub = lev_idx.loc[present]
dist_own = sub.emerging_disclosure_level.value_counts().sort_index()
curated_own = [c for c in present if str(lev_idx.loc[c, "curated_evidence_flag"]).lower() == "true"]

own_audit = {
    "portfolio_source": "work/pure_buffett_benchmark/portfolio_v7.json (the 20 holdings v10 reports)",
    "n_holdings": len(own_codes),
    "in_candidate_pool_file": len(present),
    "absent_from_candidate_pool_file": absent,
    "absent_note": ("These holdings do not appear in the Top-1200 candidate pool at all, so no "
                    "thematic evidence level was ever assigned to them."),
    "thematic_level_distribution": {str(k): int(v) for k, v in dist_own.items()},
    "hand_verified_holdings": [{"code": c, "name": str(lev_idx.loc[c, "company_name"])}
                               for c in curated_own],
    "n_hand_verified": len(curated_own),
    "overlap_with_pipeline_final20": sorted(set(own_codes) & set(final20.code)),
    "finding": (
        "Of %d holdings, exactly %d carries a hand-verified level-2 thematic artefact (%s); %d sit at "
        "thematic level 1 -- reachable by the metadata keyword screen alone -- %d at level 0, and %d "
        "were never scored because they are outside the candidate pool. The portfolio also shares only "
        "%d name with the selection pipeline's own final-20 list. The thematic leg of this portfolio "
        "therefore sits almost entirely inside the saturated region documented above: it does NOT "
        "clear the evidence ladder this paper proposes."
        % (len(own_codes), len(curated_own),
           (str(lev_idx.loc[curated_own[0], "company_name"]) if curated_own else "none"),
           int(dist_own.get("1", 0)), int(dist_own.get("0", 0)), len(absent),
           len(set(own_codes) & set(final20.code)))),
    "correction_to_earlier_description": (
        "Earlier drafts described the fifteen non-mechanical holdings as chosen by reading company "
        "disclosures. The record does not support that. The role rationales were drafted from general "
        "knowledge of the firms, under an explicit note in the working file that each description "
        "'requires verification against IR/EDINET before submission' -- a verification that was "
        "completed for the curated set, not for these holdings. The accurate description is narrative "
        "judgement informed by general familiarity, with artefact-backed thematic evidence for one "
        "holding."),
}

out = {"saturation": saturation, "evidence_ladder": ladder, "own_portfolio_audit": own_audit}
json.dump(out, open(ED / "saturation_v11.json", "w"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- console
sa = saturation
print("SATURATION")
print("  %d firms take %d distinct score values (effective levels %.2f)"
      % (sa["n_firms"], sa["n_distinct_values"], sa["effective_number_of_levels"]))
print("  five largest ties: %s = %.1f%% of the cross-section"
      % (sa["top5_tie_sizes"], sa["top5_tie_coverage_share"] * 100))
print("  example cluster at %.4f: %d firms tied, only %d strictly above"
      % (sa["example_cluster"]["score_value"], sa["example_cluster"]["n_firms_tied"],
         sa["example_cluster"]["n_firms_strictly_above"]))
for f in sa["example_cluster"]["firms"]:
    print("      %s %-32s %s" % (f["code"], f["name"][:32], f["business"]))
sd = sa["sector_determinism"]
print("  %.2f%% of firms sit exactly at their sector median; %d of %d sectors are single-valued"
      % (sd["share_exactly_at_sector_median"] * 100, sd["single_valued_sectors"], sd["n_sectors"]))
print("  mechanism: R&D intensity present for %d of %d firms (weight 0.25, imputed to zero otherwise)"
      % (sa["mechanism"]["rd_ratio_non_missing"], sa["n_firms"]))
print("\nEVIDENCE LADDER (pool of %d)" % ladder["pool_size"])
for k, v in ladder["levels"].items():
    print("  %-28s %4d" % (k, v))
print("  curated level-2/3 artefacts: %d; keyword-only rejections: %d"
      % (ladder["curated_count"], ladder["keyword_only_rejected"]))
oa = own_audit
print("\nOWN-PORTFOLIO AUDIT (applying the ladder to the portfolio this paper studies)")
print("  holdings %d; in candidate pool %d; never scored %d %s"
      % (oa["n_holdings"], oa["in_candidate_pool_file"], len(oa["absent_from_candidate_pool_file"]),
         oa["absent_from_candidate_pool_file"]))
print("  thematic level distribution: %s" % oa["thematic_level_distribution"])
print("  hand-verified holdings: %d %s" % (oa["n_hand_verified"],
                                           [x["name"] for x in oa["hand_verified_holdings"]]))
print("  overlap with the pipeline's own final-20: %s" % oa["overlap_with_pipeline_final20"])
print("  -> %s" % oa["finding"])

print("\nwritten -> saturation_v11.json")
