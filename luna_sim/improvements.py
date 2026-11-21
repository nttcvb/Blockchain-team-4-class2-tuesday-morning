"""Reproducible, common-observation comparisons with the frozen v2 engine.

The frozen engine is deliberately rebound to today's observation layer for
the controlled structural ablation. Its original published report is kept in
a separate row because changing a target's availability convention can change
a score without improving the simulation. No comparison run calibrates itself.
"""
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import ROOT, DEFAULT_SOURCE, ModelParams, ScenarioConfig
from .data import initial_facts, load_targets, group_targets, build_population, seed_shocks
from .metrics import fit_metrics
from .calibrate import _source_hashes


ERROR_METRICS = {
    'ust_mae': ('MAE giá UST, USD', .05),
    'deposit_nrmse': ('NRMSE tiền gửi Anchor', .10),
    'luna_price_log_rmse': ('RMSE log10 giá LUNA', .5),
    'luna_supply_log_rmse': ('RMSE log10 nguồn cung LUNA', .5),
    'group_mae_max': ('MAE nhóm lớn nhất', .15),
    'depeg_error_hours': ('Sai lệch onset, giờ', 6.),
    'native_daily_nrmse': ('NRMSE native theo ngày', None),
    'native_fee_mae': ('MAE phí native', None),
}


def canonical_hash(value):
    """Hash parameter/config dictionaries independent of JSON whitespace."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def parameter_hash(params):
    """Match the calibration checkpoint's sorted JSON with default separators.

    This convention is intentionally distinct from compact metadata hashing.
    All parameter keys/values are ASCII and finite; JSON whitespace is fixed
    by the exact expression also used by the calibration report writer.
    """
    values = params if isinstance(params, dict) else asdict(params)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode('utf-8')).hexdigest()


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_hash(frame):
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    values = pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()
    metadata = json.dumps([str(c) for c in frame.columns], separators=(',', ':')).encode()
    return hashlib.sha256(metadata + values).hexdigest()


def input_fingerprint(dt=15, seed=42, population=1000):
    """Record actual observed targets and finite-stock simulator inputs.

    File fingerprints include every raw Parquet: the source tree is not
    mutated, and checking unused observations is inexpensive and transparent.
    Semantic fingerprints expose the evaluated grid and cohort conventions.
    """
    agents, institution = build_population(population, seed)
    shocks, wallets = seed_shocks(dt)
    files = {}
    for path in sorted((DEFAULT_SOURCE / 'data').rglob('*.parquet')):
        files['source/' + path.relative_to(DEFAULT_SOURCE / 'data').as_posix()] = _file_hash(path)
    for relative in ['luna_sim/data.py', 'luna_sim/config.py', 'luna_sim/metrics.py',
                     'data/sources.json', 'data/external/btc_usdt_minute.parquet']:
        path = ROOT / relative
        files[relative] = _file_hash(path)
    semantic = {
        'dt_minutes': dt, 'seed': seed, 'population': population,
        'initial_facts': initial_facts(), 'institutional_claim_ust': institution,
        'population_sha256': _frame_hash(agents), 'seed_shocks_sha256': _frame_hash(shocks),
        'seed_wallets': wallets, 'targets_sha256': _frame_hash(load_targets(dt)),
        'group_targets_sha256': _frame_hash(group_targets(dt)),
    }
    payload = {'file_sha256': files, 'semantic': semantic}
    return {'sha256': canonical_hash(payload), **payload}


def _load_engine(path, name):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'Engine missing: {path}')
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load baseline engine: {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_baseline_engine(baseline_dir=None):
    """Load old code under this package so its relative imports use current data."""
    directory = Path(baseline_dir or ROOT / 'baselines' / 'v2')
    return _load_engine(directory / 'luna_sim' / 'engine.py', 'luna_sim.baseline_engine')


def compare_errors(reference, candidate):
    """Compare only error magnitudes on the same target definitions; lower wins."""
    changes = {}
    for key in ERROR_METRICS:
        before, after = reference.get(key), candidate.get(key)
        if before is None or after is None:
            changes[key] = {'before': before, 'after': after, 'delta': None, 'direction': 'missing'}
            continue
        delta = float(after - before)
        tolerance = 1e-9 * max(1., abs(before), abs(after))
        direction = 'improved' if delta < -tolerance else ('worsened' if delta > tolerance else 'unchanged')
        changes[key] = {'before': float(before), 'after': float(after), 'delta': delta, 'direction': direction}
    counts = {name: sum(item['direction'] == name for item in changes.values())
              for name in ['improved', 'worsened', 'unchanged', 'missing']}
    return {'error_changes': changes, 'counts': counts,
            'reference_gates_passed': sum(reference.get('gates', {}).values()),
            'candidate_gates_passed': sum(candidate.get('gates', {}).values()),
            'candidate_passes_all': bool(candidate.get('passes_all', False))}


def checkpoint_status(params, engine_hash, parameter_path, report_path=None):
    """A current fit requires evidence linking the report to this exact engine/params."""
    report_path = Path(report_path or ROOT / 'outputs' / 'calibration' / 'report_all.json')
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    recorded_engine = report.get('source_sha256') or report.get('financial_metrics', {}).get('engine_source_sha256')
    recorded_params = report.get('parameter_sha256')
    proof = 'report.parameter_sha256'
    if recorded_params is None:
        config_path = report_path.parent / 'config_all.json'
        if config_path.exists():
            frozen = json.loads(config_path.read_text(encoding='utf-8')).get('params')
            recorded_params = parameter_hash(frozen) if frozen is not None else None
        proof = 'config_all.params fallback'
    actual_params = parameter_hash(params)
    sources_match = report.get('provenance', {}).get('source_sha256') == _source_hashes()
    matches = recorded_engine == engine_hash and recorded_params == actual_params and sources_match
    return {'status': 'verified_parameters' if matches else 'provisional',
            'engine_matches_report': recorded_engine == engine_hash,
            'parameters_match_report': recorded_params == actual_params,
            'fitted_sources_match_report': sources_match,
            'current_engine_sha256': engine_hash, 'reported_engine_sha256': recorded_engine,
            'parameter_sha256': actual_params, 'reported_parameter_sha256': recorded_params,
            'parameter_evidence': proof, 'parameter_file': str(Path(parameter_path).resolve()),
            'report_file': str(report_path.resolve()),
            'note': 'Fingerprint records current data. A verified parameter checkpoint is not a fidelity pass or independent structural validation.'}


def _run_variant(simulator, config, output, name):
    trajectory, financial, _ = simulator(config, engine='fast', keep_ledger=False)
    path = output / f'trajectory_{name}.parquet'
    trajectory.to_parquet(path)
    return trajectory, {'name': name, 'fit_all': fit_metrics(trajectory, dt=config.dt_minutes),
                        'fit_train': fit_metrics(trajectory, dt=config.dt_minutes, split='train'),
                        'fit_validation': fit_metrics(trajectory, dt=config.dt_minutes, split='validation'),
                        'financial_metrics': financial, 'config': config.to_dict(),
                        'parameter_sha256': parameter_hash(config.params),
                        'trajectory_file': str(path.resolve()), 'trajectory_sha256': _file_hash(path)}


def _format(value):
    return 'thiếu' if value is None else f'{value:.6g}'


def render_comparison_report(result):
    variants = result['variants']
    labels = {'v2_rebased': 'V2, dữ liệu đã sửa',
              'current_engine_legacy_params': 'Engine mới, tham số cũ',
              'current_engine_full_fit': 'Engine mới, tham số fit hiện tại'}
    lines = ['# So sánh cải thiện mô hình', '',
             f"Trạng thái: **{result['status']}**. Tạo lúc {result['created_utc']}.", '',
             'Các hàng kiểm soát dùng cùng dữ liệu hiện tại, seed 42, 1.000 tác nhân, deterministic, quỹ early và cửa sổ 06–15/05. V2 rebased giữ mã/tham số cũ nhưng dùng lớp quan sát đã sửa; vì vậy nó tách sửa định nghĩa dữ liệu khỏi sửa cơ chế. Full-fit vẫn là kết quả trong mẫu.', '',
             '| Chỉ số (càng thấp càng tốt) | Ngưỡng | ' + ' | '.join(labels[name] for name in variants) + ' |',
             '|---|---:|' + '---:|' * len(variants)]
    for key, (label, threshold) in ERROR_METRICS.items():
        cells = []
        for variant in variants.values():
            value = variant['fit_all'].get(key)
            gate = variant['fit_all'].get('gates', {}).get(key)
            cells.append(_format(value) + ((' · đạt' if gate else ' · chưa đạt') if gate is not None else ''))
        lines.append('| ' + label + ' | ' + ('chẩn đoán' if threshold is None else _format(threshold)) + ' | ' + ' | '.join(cells) + ' |')
    lines += ['', 'Giá trị V2 đã công bố được lưu riêng với định nghĩa quan sát cũ; không dùng hàng đó để đếm cải thiện:', '',
              '| Chỉ số | V2 gốc | V2 dùng dữ liệu hiện tại |', '|---|---:|---:|']
    for key, (label, _) in ERROR_METRICS.items():
        lines.append(f"| {label} | {_format(result['original_v2']['fit_all'].get(key))} | {_format(variants['v2_rebased']['fit_all'].get(key))} |")
    lines += ['', 'Đối chiếu mỗi cơ chế và mỗi checkpoint với V2 rebased:']
    for name, comparison in result['comparisons'].items():
        count = comparison['counts']
        lines.append(f"- {labels[name]}: {count['improved']} sai số giảm, {count['worsened']} tăng, {count['unchanged']} không đổi; đạt {comparison['candidate_gates_passed']}/6 gate lịch sử.")
    if result.get('timestep') is not None:
        step = result['timestep']
        lines += ['', f"Độ nhạy 5/15 phút với cùng tham số hiện tại: MAE chênh giá UST {_format(step['ust_mae_difference'])}; MAE chênh tiền gửi / tiền gửi đầu {_format(step['deposit_normalized_mae_difference'])}; RMSE log10 chênh giá LUNA {_format(step['luna_log_rmse_difference'])}. Đây là kiểm tra hội tụ nhịp, không phải sai số với lịch sử."]
    lines += ['', 'Nếu trạng thái provisional, báo cáo chưa chứng minh bộ tham số đã được hiệu chỉnh cho mã hiện tại. Mỗi trajectory, engine, bộ tham số và đầu vào có fingerprint trong comparison.json. Không kết luận chính sách cứu được lịch sử chỉ từ giảm sai số hoặc từ việc test phần mềm đạt.', '']
    return '\n'.join(lines)


def run_comparison(include_refit=True, include_timestep=False, output_dir=None,
                   baseline_dir=None, current_params_path=None):
    """Run controlled comparisons; pass include_refit=False during calibration.

    This function never overwrites calibration checkpoints or the frozen
    baseline. Root may invoke it once the current fit has been published.
    """
    baseline = Path(baseline_dir or ROOT / 'baselines' / 'v2')
    output = Path(output_dir or ROOT / 'outputs' / 'improvement')
    output.mkdir(parents=True, exist_ok=True)
    original_report_path = baseline / 'outputs' / 'calibration' / 'report_all.json'
    original = json.loads(original_report_path.read_text(encoding='utf-8'))
    legacy_path = baseline / 'outputs' / 'calibration' / 'parameters_full_fit.json'
    legacy = ModelParams(**json.loads(legacy_path.read_text(encoding='utf-8')))
    current_path = Path(current_params_path or ROOT / 'outputs' / 'calibration' / 'parameters_full_fit.json')
    current = ModelParams(**json.loads(current_path.read_text(encoding='utf-8')))
    config = ScenarioConfig(params=legacy, stochastic=False, funding_timing='early')
    engine_hash = _file_hash(ROOT / 'luna_sim' / 'engine.py')
    # Re-import exact disk code even if a calling process imported the engine
    # before an edit. This avoids a current disk hash labeling stale functions.
    current_engine = _load_engine(ROOT / 'luna_sim' / 'engine.py', 'luna_sim.comparison_current_engine')
    old_engine = load_baseline_engine(baseline)
    old, old_row = _run_variant(old_engine.simulate, config, output, 'v2_rebased')
    new_legacy, legacy_row = _run_variant(current_engine.simulate, config, output, 'current_engine_legacy_params')
    variants = {'v2_rebased': old_row, 'current_engine_legacy_params': legacy_row}
    comparisons = {'current_engine_legacy_params': compare_errors(old_row['fit_all'], legacy_row['fit_all'])}
    checkpoint = checkpoint_status(current, engine_hash, current_path)
    new_fit = None
    if include_refit:
        new_fit, fit_row = _run_variant(current_engine.simulate, replace(config, params=current), output, 'current_engine_full_fit')
        variants['current_engine_full_fit'] = fit_row
        comparisons['current_engine_full_fit'] = compare_errors(old_row['fit_all'], fit_row['fit_all'])
    timestep = None
    if include_timestep:
        if new_fit is None:
            new_fit, _ = _run_variant(current_engine.simulate, replace(config, params=current), output, 'timestep_15min')
        t5, row5 = _run_variant(current_engine.simulate, replace(config, params=current, dt_minutes=5), output, 'timestep_5min')
        aligned = new_fit.join(t5[['ust_price', 'luna_price', 'anchor_deposits']], rsuffix='_5min', how='inner')
        timestep = {'parameter_sha256': parameter_hash(current), 'seed': config.seed,
                    'ust_mae_difference': float(abs(aligned.ust_price - aligned.ust_price_5min).mean()),
                    'deposit_normalized_mae_difference': float(abs(aligned.anchor_deposits - aligned.anchor_deposits_5min).mean() / new_fit.anchor_deposits.iloc[0]),
                    'luna_log_rmse_difference': float(np.sqrt(np.mean((np.log10(aligned.luna_price.clip(lower=1e-12)) - np.log10(aligned.luna_price_5min.clip(lower=1e-12))) ** 2))),
                    'five_minute': row5}
    result = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'status': checkpoint['status'] if include_refit else 'provisional_ablation',
              'comparison_source_sha256': _file_hash(Path(__file__)),
              'current_engine_sha256': engine_hash,
              'baseline_engine_sha256': _file_hash(baseline / 'luna_sim' / 'engine.py'),
              'common_inputs': input_fingerprint(), 'current_checkpoint': checkpoint,
              'original_v2': {'fit_all': original['all'], 'source_report_file': str(original_report_path.resolve()),
                              'source_report_sha256': _file_hash(original_report_path),
                              'qualification': 'Original published v2 scores use the frozen v2 observation definitions. They are excluded from common-target improvement counts.'},
              'variants': variants, 'comparisons': comparisons, 'timestep': timestep}
    # Detect a concurrent code edit; a comparison must not silently mix revisions.
    if _file_hash(ROOT / 'luna_sim' / 'engine.py') != engine_hash:
        result['status'] = 'provisional'
        result['concurrent_engine_change'] = True
    parameters_now = json.loads(current_path.read_text(encoding='utf-8'))
    if parameter_hash(ModelParams(**parameters_now)) != parameter_hash(current):
        result['status'] = 'provisional'
        result['concurrent_parameter_change'] = True
    (output / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (output / 'COMPARISON_VI.md').write_text(render_comparison_report(result), encoding='utf-8')
    return result
