"""Export existing results for the illustrated guide; never run a simulation."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pandas as pd
from luna_sim.data import load_targets
from luna_sim.reconstruction import reconstruction_artifact_current

assert reconstruction_artifact_current(), 'Saved reconstruction must be current'
work=root/'.guide_work'
work.mkdir(exist_ok=True)
fields=['ust_price','luna_price','anchor_deposits','luna_supply']
saved=pd.read_parquet(root/'outputs/calibration/trajectory_all.parquet')[fields]
actual=load_targets()[fields]
saved.join(actual,rsuffix='_actual').to_csv(work/'curves.csv')
report=json.loads((root/'outputs/calibration/report_all.json').read_text(encoding='utf-8'))
(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Exported {len(saved)} saved observations; no simulation')
