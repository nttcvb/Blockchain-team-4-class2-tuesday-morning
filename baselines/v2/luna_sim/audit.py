"""Read-only completion audit and file-backed reproduction manifest."""
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
import platform
import pandas as pd
from .config import ROOT, DEFAULT_SOURCE
from .experiments import scenario_presets


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def audit_outputs():
    folder=ROOT/'outputs'/'experiments'
    runs=pd.read_csv(folder/'runs.csv')
    execution=json.loads((folder/'execution_metadata.json').read_text(encoding='utf-8'))
    assert execution['status']=='complete' and execution['seeds']==20
    expected=set(scenario_presets())
    counts=runs.groupby('scenario').size().to_dict()
    assert set(counts)==expected and all(v==20 for v in counts.values()),counts
    assert not runs[['scenario','seed']].duplicated().any()
    assert runs.engine.eq('cadcad').all()
    assert runs.btc_sold.le(80081+.001).all()
    assert runs.tfl_own_contribution_usd.le(613616889+.001).all()
    assert runs.support_remaining_usd.ge(-.001).all()
    assert runs.seed.between(42,61).all()
    engine_hash=sha(ROOT/'luna_sim'/'engine.py')
    assert runs.engine_source_sha256.eq(engine_hash).all()
    traces={}
    presets=scenario_presets()
    for name in sorted(expected):
        directory=ROOT/'outputs'/'runs'/f'{name}_seed42'
        for filename in ['config.json','trajectory.parquet','trajectory.csv','ledger.csv','metrics.json']:
            assert (directory/filename).exists()
        stored=json.loads((directory/'config.json').read_text(encoding='utf-8'))
        assert stored==presets[name].to_dict(),f'Stale parameters/configuration: {name}'
        t=pd.read_parquet(directory/'trajectory.parquet')
        assert len(t)==1631 and str(t.index.tz)=='UTC', (name,len(t))
        assert t.index[0]==pd.Timestamp('2022-05-06T00:15:00Z')
        assert t.index[-1]==pd.Timestamp('2022-05-22T23:45:00Z')
        assert t[['market_usd','anchor_cash','anchor_deposits','support_remaining']].min().min()>=-.001
        tail=t.loc['2022-05-16':]
        assert tail.support_spent.diff().fillna(0).abs().max()<.01
        traces[name]={'rows':len(t),'tail_rows':len(tail),'max_absolute_accounting_errors':t[['ust_error','luna_error','usd_error','claim_error']].abs().max().to_dict()}
    sensitivity=pd.read_csv(folder/'sensitivity.csv')
    assert len(sensitivity)==22
    timestep=json.loads((folder/'timestep_check.json').read_text(encoding='utf-8'))
    for filename in ['report_train.json','report_all.json','parameters.json','parameters_full_fit.json','diagnostics.json','cross_venue_15min.parquet']:
        assert (ROOT/'outputs'/'calibration'/filename).exists(),filename
    for split in ['train','all']:
        report=json.loads((ROOT/'outputs'/'calibration'/f'report_{split}.json').read_text(encoding='utf-8'))
        assert report.get('objective_version')=='prices_stocks_groups_onset_native_volume_fee_v2'
    assert (ROOT/'data'/'processed'/'event_timeline.csv').exists()
    assert len(pd.read_csv(folder/'summary.csv'))==7
    assert len(pd.read_parquet(folder/'bands.parquet').groupby(['scenario','quantile']))==21
    files=list((ROOT/'luna_sim').glob('*.py'))+[ROOT/'app.py',ROOT/'pyproject.toml',ROOT/'data'/'sources.json']
    files+=list((ROOT/'outputs'/'calibration').glob('*.json'))
    files+=list((ROOT/'data'/'processed').glob('*'))
    files+=list((ROOT/'data'/'external').glob('*'))
    files+=list((ROOT/'tests').glob('test_*.py'))
    files+=[ROOT/'.streamlit'/'config.toml',ROOT/'Start.ps1',ROOT/'requirements-tested.txt',ROOT/'outputs'/'test-results.xml']
    files+=[ROOT/'PLAN_APPROVED.md',ROOT/'MODEL_SPEC.md',ROOT/'README.md',ROOT/'DEMO_VI.md',ROOT/'outputs'/'dashboard-final-tests.xml',ROOT/'outputs'/'REPORT_VI.md',ROOT/'outputs'/'historical_comparison.html',ROOT/'outputs'/'dashboard-proof.jpg']
    files+=[ROOT/'outputs'/'COMPLETION_AUDIT.md']
    files+=list(folder.glob('*'))
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),
        'python':platform.python_version(),
        'versions':{name:importlib.metadata.version(name) for name in ['cadCAD','numpy','pandas','pyarrow','scipy','plotly','streamlit','pytest']},
        'runs':len(runs),'seeds_per_scenario':counts,'rescue_counts':runs.groupby('scenario').rescued.sum().to_dict(),
        'sensitivity_settings':len(sensitivity),'timestep_check':timestep,
        'traces':traces,'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files if p.is_file()},
        'input_files_sha256':{str(p.relative_to(DEFAULT_SOURCE)):sha(p) for p in (DEFAULT_SOURCE/'data').rglob('*.parquet')},
        'qualification':'Fidelity gates fail. These are reproducible exploratory policy experiments, not causal evidence of a historical rescue.'}
    target=ROOT/'outputs'/'REPRODUCIBILITY.json'
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'audit':'passed','runs':len(runs),'seeds_per_scenario':counts,'manifest':str(target)}
