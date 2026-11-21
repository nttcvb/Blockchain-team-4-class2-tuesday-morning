"""File-backed regressions for stale results after a model/parameter update.

These checks use a temporary project, real parameter JSON and actual SHA readers.
They do not run cadCAD or substitute a mocked provenance implementation.
"""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import pytest

from luna_sim import calibrate, config, diagnostics, experiments, report


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def project(tmp_path, monkeypatch):
    original = config.ROOT
    paths = ['luna_sim/calibrate.py', 'luna_sim/engine.py', 'luna_sim/config.py',
             'luna_sim/data.py', 'luna_sim/metrics.py', 'luna_sim/experiments.py',
             'luna_sim/report.py', 'data/sources.json',
             'data/external/btc_usdt_minute.parquet', 'data/external/btc_metadata.json']
    for relative in paths:
        destination = tmp_path/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((original/relative).read_bytes())
    for module in [config, calibrate, diagnostics, experiments, report]:
        monkeypatch.setattr(module, 'ROOT', tmp_path)
    parameters = asdict(config.ModelParams())
    for name in ['parameters.json', 'parameters_full_fit.json']:
        write_json(tmp_path/'outputs/calibration'/name, parameters)
    (tmp_path/'outputs/experiments').mkdir(parents=True, exist_ok=True)
    return tmp_path


def publish_sensitivity(project, status='complete'):
    folder = project/'outputs/experiments'
    result = folder/'sensitivity.csv'
    result.write_text('setting,final_ust_price\nbaseline,0.4\n', encoding='utf-8')
    write_json(folder/'sensitivity_metadata.json', {
        'status':status, 'provenance':experiments.artifact_provenance(),
        'settings':1, 'result_sha256':digest(result)})
    return result


def publish_timestep(project):
    folder = project/'outputs/experiments'
    result = folder/'timestep_check.json'
    write_json(result, {'provenance':experiments.artifact_provenance(),
                        'ust_mae_between_steps':0.04,
                        'deposit_nrmse_between_steps':0.03,
                        'luna_log_rmse_between_steps':0.2})
    # The independent identity matches the sensitivity writer's convention.
    # Keeping it file-backed makes result edits observable to the guard.
    write_json(folder/'timestep_check_metadata.json', {
        'status':'complete', 'provenance':experiments.artifact_provenance(),
        'result_sha256':digest(result)})
    return result


def publish_report(project):
    folder = project/'outputs'
    for name in ['REPORT_VI.md', 'historical_comparison.html']:
        (folder/name).write_text('Current model report\n', encoding='utf-8')
    write_json(folder/'report_metadata.json', {
        'provenance':report.report_provenance(),
        'artifacts_sha256':{name:digest(folder/name)
                            for name in ['REPORT_VI.md', 'historical_comparison.html']}})


def change_parameters(project):
    parameters = replace(config.ModelParams(), hazard_discount=24.)
    write_json(project/'outputs/calibration/parameters_full_fit.json', asdict(parameters))


def change_source(project):
    path = project/'luna_sim/engine.py'
    path.write_bytes(path.read_bytes()+b'\n# A changed engine version\n')


def test_sensitivity_needs_completed_metadata_and_result(project):
    assert not experiments.experiment_artifact_current('sensitivity')
    result = publish_sensitivity(project, status='running')
    assert not experiments.experiment_artifact_current('sensitivity')
    publish_sensitivity(project)
    assert experiments.experiment_artifact_current('sensitivity')
    result.unlink()
    assert not experiments.experiment_artifact_current('sensitivity')


@pytest.mark.parametrize('change', ['parameters', 'source', 'result'])
def test_sensitivity_rejects_a_different_checkpoint_or_result(project, change):
    result = publish_sensitivity(project)
    assert experiments.experiment_artifact_current('sensitivity')
    if change == 'parameters':
        change_parameters(project)
    elif change == 'source':
        change_source(project)
    else:
        result.write_text('setting,final_ust_price\nbaseline,1.0\n', encoding='utf-8')
    assert not experiments.experiment_artifact_current('sensitivity')


def test_timestep_rejects_legacy_output_without_identity(project):
    assert not experiments.experiment_artifact_current('timestep_check')
    result = project/'outputs/experiments/timestep_check.json'
    write_json(result, {'ust_mae_between_steps':0.04})
    assert not experiments.experiment_artifact_current('timestep_check')
    write_json(result, {'provenance':experiments.artifact_provenance(), 'ust_mae_between_steps':0.04})
    assert not experiments.experiment_artifact_current('timestep_check')
    publish_timestep(project)
    assert experiments.experiment_artifact_current('timestep_check')


def test_timestep_requires_finished_metadata_and_result(project):
    result = publish_timestep(project)
    metadata_path = result.with_name('timestep_check_metadata.json')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    metadata['status'] = 'running'
    write_json(metadata_path, metadata)
    assert not experiments.experiment_artifact_current('timestep_check')
    metadata['status'] = 'complete'
    write_json(metadata_path, metadata)
    assert experiments.experiment_artifact_current('timestep_check')
    result.unlink()
    assert not experiments.experiment_artifact_current('timestep_check')


@pytest.mark.parametrize('change', ['parameters', 'source', 'result'])
def test_timestep_rejects_a_different_checkpoint_or_result(project, change):
    result = publish_timestep(project)
    assert experiments.experiment_artifact_current('timestep_check')
    if change == 'parameters':
        change_parameters(project)
    elif change == 'source':
        change_source(project)
    else:
        payload = json.loads(result.read_text(encoding='utf-8'))
        payload['ust_mae_between_steps'] = 0.
        write_json(result, payload)
    assert not experiments.experiment_artifact_current('timestep_check')


def test_report_requires_metadata_and_both_published_files(project):
    assert not report.report_artifact_current()
    publish_report(project)
    assert report.report_artifact_current()
    (project/'outputs/historical_comparison.html').unlink()
    assert not report.report_artifact_current()


def test_report_requires_identity_for_the_downloaded_report(project):
    publish_report(project)
    assert report.report_artifact_current()
    metadata_path = project/'outputs/report_metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    del metadata['artifacts_sha256']['REPORT_VI.md']
    write_json(metadata_path, metadata)
    # A valid chart digest cannot verify the separately downloaded report.
    assert not report.report_artifact_current()


@pytest.mark.parametrize('change', ['report', 'chart', 'parameters', 'source', 'upstream'])
def test_report_rejects_edits_to_outputs_or_their_inputs(project, change):
    publish_report(project)
    assert report.report_artifact_current()
    if change == 'parameters':
        change_parameters(project)
    elif change == 'source':
        change_source(project)
    elif change == 'upstream':
        # A suite result changes while the model/parameters themselves do not.
        (project/'outputs/experiments/summary.csv').write_text('scenario,rescue_rate\nbuy_ust,1\n', encoding='utf-8')
    else:
        filename = 'REPORT_VI.md' if change == 'report' else 'historical_comparison.html'
        (project/'outputs'/filename).write_text('Outdated or modified report\n', encoding='utf-8')
    assert not report.report_artifact_current()


@pytest.mark.parametrize('change', ['parameters', 'source', 'trajectory'])
def test_diagnostics_identity_tracks_actual_fitted_inputs(project, change):
    trajectory = project/'outputs/calibration/trajectory_all.parquet'
    trajectory.write_bytes(b'Original fitted trajectory')
    published = diagnostics.diagnostic_sources()
    assert published == diagnostics.diagnostic_sources()
    if change == 'parameters':
        change_parameters(project)
    elif change == 'source':
        change_source(project)
    else:
        trajectory.write_bytes(b'Another fitted trajectory')
    assert published != diagnostics.diagnostic_sources()
