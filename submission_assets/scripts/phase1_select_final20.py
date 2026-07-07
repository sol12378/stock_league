from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / 'scripts' / 'phase1_generate_report_assets.py'), run_name='__main__')
