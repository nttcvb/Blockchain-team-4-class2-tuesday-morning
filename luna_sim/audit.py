"""Read-only completion audit and file-backed reproduction manifest."""
import hashlib
import importlib.metadata
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
import platform
import pandas as pd
from .config import ROOT, DEFAULT_SOURCE
from .experiments import scenario_presets, experiment_sources, experiment_artifact_current
from .calibrate import (OBJECTIVE_VERSION, TRAIN_END, CalibrationObjective,
                       _source_hashes, _frame_hash, parameter_sha256)
from .config import ModelParams, ScenarioConfig
from .data import load_targets, group_targets
from .metrics import fit_metrics, evaluate
from .diagnostics import diagnostic_sources
from .report import report_artifact_current


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def _assert_nested_equal(actual, expected, label, rtol=1e-9, atol=1e-8):
    """Compare recomputed diagnostics, including categorical gate decisions."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f'{label}: expected a mapping'
        assert set(actual)==set(expected), f'{label}: diagnostic fields differ'
        for key in expected:
            _assert_nested_equal(actual[key], expected[key], f'{label}.{key}', rtol, atol)
    elif isinstance(expected, (list, tuple)):
        assert isinstance(actual, (list, tuple)) and len(actual)==len(expected), f'{label}: sequence differs'
        for i,(a,e) in enumerate(zip(actual,expected)):
            _assert_nested_equal(a,e,f'{label}[{i}]',rtol,atol)
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert actual==expected and type(actual)==type(expected), f'{label}: {actual!r} != {expected!r}'
    elif isinstance(expected, (int,float)):
        assert isinstance(actual,(int,float)) and not isinstance(actual,bool), f'{label}: expected a number'
        assert math.isfinite(float(actual)) and math.isfinite(float(expected)), f'{label}: non-finite number'
        assert math.isclose(float(actual),float(expected),rel_tol=rtol,abs_tol=atol), f'{label}: {actual!r} != {expected!r}'
    else:
        assert actual==expected, f'{label}: {actual!r} != {expected!r}'


def audit_calibration(split, current_sources=None):
    """Recompute fitted-report evidence from stored trajectories, without simulation.

    The train optimizer uses only rows before TRAIN_END; its published
    trajectory still covers the complete event for temporal validation.
    """
    assert split in {'train','all'}, f'Unknown calibration split: {split}'
    folder=ROOT/'outputs'/'calibration'
    report=json.loads((folder/f'report_{split}.json').read_text(encoding='utf-8'))
    status=json.loads((folder/f'calibration_status_{split}.json').read_text(encoding='utf-8'))
    config=ScenarioConfig.from_dict(json.loads((folder/f'config_{split}.json').read_text(encoding='utf-8')))
    name='parameters.json' if split=='train' else 'parameters_full_fit.json'
    parameters=ModelParams(**json.loads((folder/name).read_text(encoding='utf-8')))
    sources=_source_hashes() if current_sources is None else current_sources
    provenance=report.get('provenance',{})
    assert status.get('status')=='complete', f'{split}: calibration has not completed'
    assert report.get('fit_split')==split and provenance.get('fit_split')==split
    assert report.get('objective_version')==OBJECTIVE_VERSION
    assert status.get('objective_version')==OBJECTIVE_VERSION
    assert provenance.get('objective_version')==OBJECTIVE_VERSION
    assert report.get('source_sha256')==sources['engine.py'], f'{split}: stale engine'
    assert provenance.get('source_sha256')==sources, f'{split}: stale fitted sources'
    assert status.get('source_sha256')==sources, f'{split}: execution sources differ'
    run_id=report.get('optimizer',{}).get('run_id')
    assert run_id and status.get('run_id')==run_id, f'{split}: status/report run mismatch'
    assert status.get('calls')==report.get('calls'), f'{split}: execution/report call counts differ'
    assert report.get('fast_cadcad_equivalence_verified') is True
    assert report.get('parameter_sha256')==parameter_sha256(parameters)
    assert config.params==parameters, f'{split}: stored trajectory configuration has different parameters'
    assert config.mode=='historical' and not config.stochastic and config.funding_timing=='early'
    assert config.dt_minutes==15 and config.stress_days==0

    # Reload file-backed targets rather than trusting an old process cache.
    load_targets.cache_clear(); group_targets.cache_clear()
    full_target=load_targets(config.dt_minutes)
    target=full_target.loc[full_target.index<TRAIN_END].copy() if split=='train' else full_target.copy()
    target.attrs['initial_deposits']=float(full_target.anchor_deposits.iloc[0])
    groups=group_targets(config.dt_minutes).reindex(target.index)
    assert provenance.get('target_sha256')==_frame_hash(target), f'{split}: targets differ from fitted inputs'
    assert provenance.get('group_sha256')==_frame_hash(groups), f'{split}: group observations differ from fitted inputs'
    assert provenance.get('fit_start')==str(target.index[0])
    assert provenance.get('fit_end')==str(target.index[-1])
    trajectory=pd.read_parquet(folder/f'trajectory_{split}.parquet')
    assert trajectory.index.equals(full_target.index), f'{split}: published trajectory does not cover the full event'
    fit_config=replace(config,end=str(TRAIN_END)) if split=='train' else config
    objective=CalibrationObjective(fit_config,target,groups,parameters)
    recomputed=objective.components(trajectory)
    _assert_nested_equal(report.get('objective_details'),recomputed,f'{split}.objective_details')
    _assert_nested_equal(report.get('objective'),recomputed['loss'],f'{split}.objective')
    _assert_nested_equal(status.get('objective'),recomputed['loss'],f'{split}.execution_objective')
    for metric_split in ['train','validation','all']:
        _assert_nested_equal(report.get(metric_split),fit_metrics(trajectory,dt=config.dt_minutes,split=metric_split),f'{split}.{metric_split}')
    financial=evaluate(trajectory,config)
    reported_financial=report.get('financial_metrics',{})
    _assert_nested_equal({key:reported_financial.get(key) for key in financial},financial,f'{split}.financial_metrics')

    # A run archive independently identifies the trajectory that was verified
    # before publication; a matching status alone would not prove its identity.
    archive=folder/'runs'/run_id
    archived_trajectory=pd.read_parquet(archive/'trajectory.parquet')
    assert _frame_hash(archived_trajectory)==_frame_hash(trajectory), f'{split}: trajectory differs from its run archive'
    archived_report=json.loads((archive/'report.json').read_text(encoding='utf-8'))
    archived_execution=json.loads((archive/'execution.json').read_text(encoding='utf-8'))
    assert archived_execution==status, f'{split}: final execution archive differs from status'
    assert archived_report.get('parameter_sha256')==report.get('parameter_sha256')
    assert archived_report.get('provenance')==provenance
    _assert_nested_equal(archived_report.get('objective_details'),recomputed,f'{split}.archived_objective')
    return {'run_id':run_id,'objective_recomputed':recomputed['loss'],
            'rows':len(trajectory),'fit_rows':len(target),
            'target_sha256':provenance['target_sha256'],'group_sha256':provenance['group_sha256'],
            'report_metrics_recomputed':True,'financial_metrics_recomputed':True,
            'published_trajectory_matches_run_archive':True,
            'fidelity':{'metric_split':'validation' if split=='train' else 'all',
                        'gates':report['validation' if split=='train' else 'all']['gates'],
                        'passes_all':report['validation' if split=='train' else 'all']['passes_all'],
                        'is_parameter_holdout':split=='train'}}


def fidelity_summary(calibration_checks):
    """Keep temporal holdout and historical reconstruction distinct from reproduction."""
    checks={split:calibration_checks[split]['fidelity'] for split in ['train','all']}
    failed={split:[name for name,passed in check['gates'].items() if not passed]
            for split,check in checks.items()}
    passed=all(check['passes_all'] and not failed[split] for split,check in checks.items())
    if passed:
        qualification=('Temporal holdout and full-event reconstruction fidelity gates pass. '
                       'Policy results remain conditional model experiments; passing numerical gates '
                       'does not establish a historical causal rescue.')
    else:
        labels={'train':'temporal parameter holdout','all':'full-event reconstruction'}
        failures='; '.join(f"{labels[split]}: {', '.join(names)}" for split,names in failed.items() if names)
        qualification=(f'Fidelity gates fail ({failures}). These are reproducible exploratory policy '
                       'experiments, not causal evidence of a historical rescue.')
    return {'passes_all':passed,'checks':checks,'failed_gates':failed,'qualification':qualification}


def audit_outputs():
    folder=ROOT/'outputs'/'experiments'
    runs=pd.read_csv(folder/'runs.csv')
    execution=json.loads((folder/'execution_metadata.json').read_text(encoding='utf-8'))
    assert execution['status']=='complete' and execution['seeds']==20
    assert execution.get('source_sha256')==experiment_sources(), 'Seed-suite sources differ from the current model'
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
    assert experiment_artifact_current('sensitivity'), 'Sensitivity analysis differs from the current source/parameter checkpoint'
    assert len(sensitivity)==22
    timestep=json.loads((folder/'timestep_check.json').read_text(encoding='utf-8'))
    assert experiment_artifact_current('timestep_check'), 'Timestep check differs from the current source/parameter checkpoint'
    for filename in ['report_train.json','report_all.json','parameters.json','parameters_full_fit.json','diagnostics.json','cross_venue_15min.parquet']:
        assert (ROOT/'outputs'/'calibration'/filename).exists(),filename
    current_sources=_source_hashes()
    calibration_checks={split:audit_calibration(split,current_sources) for split in ['train','all']}
    diagnostic=json.loads((ROOT/'outputs'/'calibration'/'diagnostics.json').read_text(encoding='utf-8'))
    assert diagnostic.get('source_sha256')==diagnostic_sources(), 'Supplemental diagnostics differ from the current fitted trajectory'
    fidelity=fidelity_summary(calibration_checks)
    assert report_artifact_current(), 'Written report or its inputs differ from the current model artifacts'
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
    files+=[ROOT/'outputs'/'report_metadata.json',ROOT/'outputs'/'v3-tests.xml']
    files+=[ROOT/'IMPROVEMENT_PLAN_VI.md']
    files+=list((ROOT/'outputs'/'improvement').glob('*'))
    files+=list(folder.glob('*'))
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),
        'python':platform.python_version(),
        'versions':{name:importlib.metadata.version(name) for name in ['cadCAD','numpy','pandas','pyarrow','scipy','plotly','streamlit','pytest']},
        'runs':len(runs),'seeds_per_scenario':counts,'rescue_counts':runs.groupby('scenario').rescued.sum().to_dict(),
        'sensitivity_settings':len(sensitivity),'timestep_check':timestep,
        'reproduction_pass':True,'fidelity_pass':fidelity['passes_all'],'fidelity':fidelity,
        'traces':traces,'calibration_checks':calibration_checks,'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files if p.is_file()},
        'input_files_sha256':{str(p.relative_to(DEFAULT_SOURCE)):sha(p) for p in (DEFAULT_SOURCE/'data').rglob('*.parquet')},
        'qualification':fidelity['qualification']}
    target=ROOT/'outputs'/'REPRODUCIBILITY.json'
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'audit':'passed','reproduction_pass':True,'fidelity_pass':fidelity['passes_all'],
            'fidelity':fidelity,'runs':len(runs),'seeds_per_scenario':counts,'manifest':str(target)}
