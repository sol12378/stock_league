#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
export PHASE3_REPO_ROOT="$REPO_ROOT"

: > "$REPO_ROOT/outputs/phase3_beyond_buffett/logs/run.log"
: > "$REPO_ROOT/outputs/phase3_beyond_buffett/logs/warnings.log"
: > "$REPO_ROOT/outputs/phase3_beyond_buffett/logs/missing_features.log"
: > "$REPO_ROOT/outputs/phase3_beyond_buffett/logs/validation_errors.log"

python3 "$SCRIPT_DIR/00_unzip_phase2_bundle.py"
python3 "$SCRIPT_DIR/01_load_phase2_inputs.py"
python3 "$SCRIPT_DIR/02_build_seed_universe.py"
python3 "$SCRIPT_DIR/03_phase2_confidence.py"
python3 "$SCRIPT_DIR/04_transformation_lite.py"
python3 "$SCRIPT_DIR/05_enrich_disclosures.py"
python3 "$SCRIPT_DIR/06_transformation_full.py"
python3 "$SCRIPT_DIR/07_emerging_score.py"
python3 "$SCRIPT_DIR/08_evidence_leveling.py"
python3 "$SCRIPT_DIR/09_grade_assignment.py"
python3 "$SCRIPT_DIR/10_role_assignment.py"
python3 "$SCRIPT_DIR/11_select_final20.py"
python3 "$SCRIPT_DIR/12_allocation.py"
python3 "$SCRIPT_DIR/13_ablation.py"
python3 "$SCRIPT_DIR/14_generate_reports.py"

cd "$REPO_ROOT/outputs"
rm -f phase3_beyond_buffett.zip
zip -qr phase3_beyond_buffett.zip phase3_beyond_buffett

python3 - "$REPO_ROOT" <<'PY'
import sys
from pathlib import Path
import pandas as pd
root=Path(sys.argv[1])
out=root/'outputs/phase3_beyond_buffett'
seed=pd.read_csv(out/'data/phase3_seed_universe_from_phase2.csv',low_memory=False)
final=pd.read_csv(out/'data/phase3_final20_selected.csv',low_memory=False)
evidence=pd.read_csv(out/'data/phase3_evidence_levels.csv',low_memory=False)
trans=pd.read_csv(out/'data/phase3_transformation_scores.csv',low_memory=False)
em=pd.read_csv(out/'data/phase3_emerging_scores.csv',low_memory=False)
print(f"成果物フォルダ: {out}")
print(f"zip: {root/'outputs/phase3_beyond_buffett.zip'}")
print("主要入力: formal Top1200 review-ready / Top100 / Top300 / Top2000 reference / normalization / point-in-time panel")
print(f"Top1200件数: {len(seed)}")
print(f"Phase1 Top5照合: {int(seed.phase1_top5_flag.astype(str).str.lower().eq('true').sum())}/5")
print(f"phase3_review_required実CSV再集計: {int(seed.phase3_review_required.astype(str).str.lower().eq('true').sum())}")
print(f"Transformation欠損率平均: {pd.to_numeric(trans.transformation_lite_missing_rate,errors='coerce').mean():.2%}")
print(f"Emerging欠損率平均: {pd.to_numeric(em.emerging_missing_rate,errors='coerce').mean():.2%}")
print(f"Evidence Level件数: {evidence.evidence_level.value_counts().sort_index().to_dict()}")
print(f"最終20社役割構成: {final.final_role.value_counts().to_dict()}")
viol=[]
if len(final)!=20: viol.append('count')
if final.sector.value_counts().max()>3: viol.append('sector_count')
if not final.top1200_flag.astype(str).str.lower().eq('true').all(): viol.append('top1200')
print(f"制約違反: {viol if viol else 'なし'}")
print("次に確認: docs/phase3_final20_rationale.md, reports/phase3_selection_audit.md, reports/phase3_evidence_audit_report.md, data/phase3_allocation_plan.csv")
PY
