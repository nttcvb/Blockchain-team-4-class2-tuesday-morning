"""Gate-scaled calibration, isolated from policy experiments and target forcing."""
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import multiprocessing
import os
import time
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, minimize
from scipy.special import expit
from scipy.stats import qmc
from .config import ROOT, ModelParams, ScenarioConfig
from .engine import simulate
from .data import load_targets, group_targets
from .metrics import fit_metrics, first_depeg, group_fit_diagnostics

OBJECTIVE_VERSION = 'gate_phase_onset_native_v3_group_coverage_v1'
GATES = {'ust_mae': .05, 'deposit_nrmse': .10, 'luna_price_log_rmse': .5,
         'luna_supply_log_rmse': .5, 'group_mae_max': .15, 'depeg_error_hours': 6.}
TRAIN_END = pd.Timestamp('2022-05-11T00:00:00Z')
# Log-scaled depths/capacity span orders of magnitude. Names define warm starts.
SEARCH = [
    ('hazard_base', -14., -6.5), ('hazard_size', 0., 1.),
    ('hazard_discount', 10., 250.), ('hazard_outflow', 0., 120.),
    ('hazard_luna', 0., 30.), ('log_ust_depth', 9., 11.2),
    ('ust_depth_luna_beta', 0., 2.5), ('log_luna_depth', 7.5, 10.2),
    ('luna_depth_growth', .2, 1.1), ('log_arb_capacity', 8., 10.5),
    ('luna_beta_btc', .3, 5.), ('ust_confidence_beta', .03, 1.5),
    ('luna_residual_bid_fraction', .005, .20),
]
LOG_PARAMETERS = {'log_ust_depth': 'ust_depth_usd', 'log_luna_depth': 'luna_depth_usd',
                  'log_arb_capacity': 'arb_capacity_day'}
INITIALIZER = 'hybrid_latin_hypercube_gaussian'
LOCAL_FRACTION = .25
LOCAL_SCALE = .03
SIMPLEX_STEP = .02


def unpack(values, base=None):
    if len(values) != len(SEARCH):
        raise ValueError('Candidate length must match the named search space')
    params = asdict(base or ModelParams())
    for (key, _, _), value in zip(SEARCH, values):
        params[LOG_PARAMETERS.get(key, key)] = float(10.**value if key in LOG_PARAMETERS else value)
    return ModelParams(**params)


def pack(params, clip=True):
    values = asdict(params)
    result = np.asarray([np.log10(values[LOG_PARAMETERS[key]]) if key in LOG_PARAMETERS
                         else values[key] for key, _, _ in SEARCH], dtype=float)
    if not np.isfinite(result).all():
        raise ValueError('Warm starts must be finite and positive where log-scaled')
    return np.clip(result, [lo for _, lo, _ in SEARCH], [hi for _, _, hi in SEARCH]) if clip else result


def _bounded_start(values):
    values = np.asarray(values, dtype=float)
    lower = np.asarray([lo for _, lo, _ in SEARCH])
    upper = np.asarray([hi for _, _, hi in SEARCH])
    if values.shape != lower.shape or not np.isfinite(values).all():
        raise ValueError('Initialization requires one finite value per search dimension')
    if np.any(values < lower) or np.any(values > upper):
        raise ValueError('Initialization start must lie inside the search bounds')
    return values, lower, upper


def hybrid_initial_population(values, popsize=4, seed=42,
                              local_fraction=LOCAL_FRACTION, local_scale=LOCAL_SCALE):
    """75% global Latin-hypercube / 25% warm neighborhood, exact warm point first.

    The warm point occupies one neighborhood slot. Integer rounding may change
    the nominal fraction for small populations. Separate deterministic streams
    preserve reproducibility without coupling the Latin and Gaussian draws.
    """
    start, lower, upper = _bounded_start(values)
    if not isinstance(popsize, int) or isinstance(popsize, bool) or popsize < 1 or seed < 0:
        raise ValueError('Population multiplier and seed must be nonnegative integers')
    if not 0 < local_fraction < 1 or not np.isfinite(local_scale) or local_scale <= 0:
        raise ValueError('Invalid local initialization fraction or scale')
    count = max(5, popsize*len(SEARCH))
    local_count = min(count-1, max(1, int(round(count*local_fraction))))
    global_count = count-local_count
    global_seed, local_seed = np.random.SeedSequence(seed).spawn(2)
    sampler = qmc.LatinHypercube(d=len(SEARCH), seed=np.random.default_rng(global_seed))
    global_points = qmc.scale(sampler.random(global_count), lower, upper)
    rng = np.random.default_rng(local_seed)
    local_points = np.clip(start+rng.normal(0., local_scale, (local_count, len(SEARCH)))*(upper-lower), lower, upper)
    local_points[0] = start
    return np.vstack([local_points, global_points])


def bounded_initial_simplex(values, relative_step=SIMPLEX_STEP):
    """Full-rank axis simplex with equal fractional steps inside each bound."""
    start, lower, upper = _bounded_start(values)
    if not np.isfinite(relative_step) or not 0 < relative_step <= .5:
        raise ValueError('Simplex step must be in (0, .5] of each search range')
    simplex = np.tile(start, (len(SEARCH)+1, 1))
    # Move toward the more distant bound. At either boundary this moves inward;
    # unlike clipping a default simplex, every coordinate keeps a nonzero step.
    direction = np.where(upper-start >= start-lower, 1., -1.)
    for index in range(len(SEARCH)):
        simplex[index+1, index] += direction[index]*relative_step*(upper[index]-lower[index])
    return simplex


def _parameters_from_file(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    supplied = payload.get('parameters', payload)
    valid = {field.name for field in fields(ModelParams)}
    return ModelParams(**{key: value for key, value in supplied.items() if key in valid}), sorted(set(supplied)-valid)


def _source_hashes():
    paths = {name: ROOT/'luna_sim'/name
             for name in ['calibrate.py', 'engine.py', 'config.py', 'data.py', 'metrics.py']}
    paths.update({name: ROOT/name for name in ['data/sources.json',
                  'data/external/btc_usdt_minute.parquet', 'data/external/btc_metadata.json']})
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}


def _frame_hash(frame):
    digest = hashlib.sha256()
    digest.update(json.dumps([(str(c), str(dtype)) for c, dtype in frame.dtypes.items()]).encode())
    digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes())
    return digest.hexdigest()


def parameter_sha256(params):
    return hashlib.sha256(json.dumps(asdict(params), sort_keys=True).encode('utf-8')).hexdigest()


def _write_json(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def _normalised_metrics(trajectory, target, groups, require_group_observations=True):
    group_result = group_fit_diagnostics(trajectory, groups)
    ratios = {
        'ust_mae': float(abs(trajectory.ust_price-target.ust_price).mean())/GATES['ust_mae'],
        'deposit_nrmse': float(np.sqrt(np.mean((trajectory.anchor_deposits-target.anchor_deposits)**2)))/max(float(target.attrs['initial_deposits']), 1)/GATES['deposit_nrmse'],
        'luna_price_log_rmse': float(np.sqrt(np.mean((np.log10(trajectory.luna_price.clip(lower=1e-12))-np.log10(target.luna_price.clip(lower=1e-12)))**2)))/GATES['luna_price_log_rmse'],
        'luna_supply_log_rmse': float(np.sqrt(np.mean((np.log10(trajectory.luna_supply.clip(lower=1))-np.log10(target.luna_supply.clip(lower=1)))**2)))/GATES['luna_supply_log_rmse'],
    }
    if group_result['group_mae_max'] is not None:
        ratios['group_mae_max'] = group_result['group_mae_max']/GATES['group_mae_max']
    elif require_group_observations or group_result['group_observed_count']:
        raise ValueError('No finite paired group observations in the fit window')
    # A phase wholly outside the group's observed coverage has four measured
    # dimensions. Omit its unavailable group term; do not call it zero error.
    return ratios


@dataclass
class CalibrationObjective:
    config: ScenarioConfig
    target: pd.DataFrame
    groups: pd.DataFrame
    base: ModelParams

    def components(self, trajectory):
        target, groups = self.target, self.groups
        if target.empty:
            raise ValueError('Calibration requires a nonempty fit window')
        trajectory = trajectory.reindex(target.index)
        observed, predicted = first_depeg(target.ust_price), first_depeg(trajectory.ust_price)
        ratios = _normalised_metrics(trajectory, target, groups)
        fit_hours = (target.index[-1]-target.index[0]).total_seconds()/3600
        onset_error = (abs((predicted-observed).total_seconds())/3600
                       if predicted is not None and observed is not None
                       else (0. if predicted is None and observed is None else max(fit_hours, 12.)))
        # No missing-onset loophole and no 20x cap on a badly timed collapse.
        ratios['depeg_error_hours'] = onset_error/GATES['depeg_error_hours']
        core = [ratios[key] for key in GATES if key != 'depeg_error_hours']
        global_loss = float(np.mean(np.square(core)))
        break_time = observed if observed is not None else TRAIN_END
        masks = {'pre_depeg': target.index < break_time,
                 'run_before_may11': (target.index >= break_time)&(target.index < TRAIN_END),
                 'post_may11': target.index >= max(TRAIN_END, break_time)}
        phase_losses = {}
        for name, mask in masks.items():
            if np.any(mask):
                subset = target.loc[mask].copy()
                subset.attrs['initial_deposits'] = target.attrs['initial_deposits']
                phase_ratios = _normalised_metrics(trajectory.loc[mask], subset, groups.loc[mask], require_group_observations=False)
                phase_losses[name] = float(np.mean(np.square(list(phase_ratios.values()))))
        phase_loss = float(np.mean(list(phase_losses.values())))
        hour_steps = max(1, int(round(60/self.config.dt_minutes)))
        soft_true = pd.Series(expit((.98-target.ust_price)/.005), index=target.index).rolling(hour_steps, min_periods=hour_steps).mean()
        soft_model = pd.Series(expit((.98-trajectory.ust_price)/.005), index=target.index).rolling(hour_steps, min_periods=hour_steps).mean()
        # Smooth near-threshold information supports the discrete 1h onset term.
        # All rows and every phase are confined to this object's chosen fit split.
        soft_error = ((soft_model-soft_true).dropna()/.20)**2
        soft_loss = float(soft_error.mean()) if not soft_error.empty else 0.
        daily_true = target.native_ust.resample('1D').sum()
        daily_model = trajectory.native_served.resample('1D').sum()
        native_volume = float(np.mean((daily_model-daily_true)**2))/max(float(daily_true.max())*.25, 1.)**2
        fee_mask = target.native_ust.gt(0)&target.native_fee.notna()
        native_fee = float(np.mean(((trajectory.loc[fee_mask, 'native_fee']-target.loc[fee_mask, 'native_fee'])/.10)**2)) if fee_mask.any() else 0.
        onset_loss, worst_gate = 2.*ratios['depeg_error_hours']**2, max(core)**2
        loss = global_loss+.75*phase_loss+.25*worst_gate+onset_loss+soft_loss+native_volume+.2*native_fee
        return {'loss': float(loss), 'gate_ratios': ratios,
                'components': {'global_gate': global_loss, 'phase_balanced': phase_loss,
                               'worst_gate': worst_gate, 'onset': onset_loss,
                               'soft_depeg': soft_loss, 'native_daily_volume': native_volume,
                               'native_fee': native_fee}, 'phase_losses': phase_losses}

    def evaluate_parameters(self, params):
        try:
            trajectory, _, _ = simulate(replace(self.config, params=params), engine='fast', keep_ledger=False)
            result = self.components(trajectory)
            if not np.isfinite(result['loss']):
                raise FloatingPointError('Non-finite objective')
            return result
        except (AssertionError, ValueError, OverflowError, FloatingPointError) as error:
            return {'loss': 1e9, 'error': f'{type(error).__name__}: {error}'}

    def evaluate(self, values):
        return self.evaluate_parameters(unpack(values, self.base))


_WORKER_OBJECTIVE = None


def _initialize_worker(objective):
    global _WORKER_OBJECTIVE
    _WORKER_OBJECTIVE = objective


def _worker_evaluate(values):
    return _WORKER_OBJECTIVE.evaluate(values)


class _Tracker:
    def __init__(self, objective, checkpoint, provenance, run_dir, started):
        self.objective, self.checkpoint, self.provenance = objective, checkpoint, provenance
        self.run_dir, self.started = run_dir, started
        self.calls, self.best, self.stage, self.errors = 0, None, 'baseline', []

    def record(self, values, result):
        self.calls += 1
        if 'error' in result:
            self.errors = (self.errors+[result['error']])[-5:]
        if self.best is None or result['loss'] < self.best['loss']:
            self.best = {**result, 'parameters': asdict(unpack(values, self.objective.base)),
                         'parameter_sha256': parameter_sha256(unpack(values, self.objective.base)),
                         'search_values': {key: float(value) for (key, _, _), value in zip(SEARCH, values)},
                         'calls': self.calls, 'stage': self.stage, 'fit_split': self.provenance['fit_split'],
                         'objective_version': OBJECTIVE_VERSION, 'provenance': self.provenance}
            _write_json(self.checkpoint, self.best)
            _write_json(self.run_dir/'best.json', self.best)
        if self.calls % 25 == 0:
            print(f"stage={self.stage} calls={self.calls} best_loss={self.best['loss']:.5f} elapsed={time.perf_counter()-self.started:.0f}s", flush=True)
        return result['loss']

    def __call__(self, values):
        return self.record(values, self.objective.evaluate(values))


class _WorkerMap:
    def __init__(self, pool, tracker):
        self.pool, self.tracker = pool, tracker

    def __call__(self, function, candidates):
        # Workers use the same immutable objective context. Only the parent
        # records checkpoints, avoiding concurrent writes on Windows.
        values = list(candidates)
        results = self.pool.map(_worker_evaluate, values)
        return [self.tracker.record(candidate, result) for candidate, result in zip(values, results)]


def calibrate(generations=12, popsize=4, split='train', population=1000,
              resume=True, workers=1, refinement_iterations=None, seed=42, warm_start=None):
    if split not in {'train', 'all'} or generations < 0 or popsize < 1 or population < 40 or workers < 1 or seed < 0:
        raise ValueError('Invalid split, search budget, workers, population or seed')
    local_budget = max(30, generations*10) if refinement_iterations is None else refinement_iterations
    if local_budget < 0:
        raise ValueError('Refinement iterations must be nonnegative')
    output = ROOT/'outputs'/'calibration'
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    full_target, groups = load_targets(), group_targets()
    target = full_target.loc[full_target.index < TRAIN_END].copy() if split == 'train' else full_target.copy()
    target.attrs['initial_deposits'] = float(full_target.anchor_deposits.iloc[0])
    groups = groups.reindex(target.index)
    config = ScenarioConfig(n_depositors=population, stochastic=False, funding_timing='early')
    fit_config = replace(config, end=str(TRAIN_END)) if split == 'train' else config
    chosen, ignored, source = ModelParams(), [], None
    if warm_start:
        source = Path(warm_start)
    else:
        candidates = [output/('parameters.json' if split == 'train' else 'parameters_full_fit.json'), output/f'best_{split}.json']
        if split == 'all': candidates.append(output/'parameters.json')
        source = next((path for path in candidates if path.exists()), None)
    if source is not None:
        chosen, ignored = _parameters_from_file(source)
    fixed = {key: value for key, value in asdict(chosen).items()
             if key not in {LOG_PARAMETERS.get(name, name) for name, _, _ in SEARCH}}
    provenance = {'fit_split': split, 'objective_version': OBJECTIVE_VERSION,
                  'source_sha256': _source_hashes(), 'target_sha256': _frame_hash(target),
                  'group_sha256': _frame_hash(groups), 'search': SEARCH, 'fixed_parameters': fixed,
                  'scenario': config.to_dict(), 'fit_start': str(target.index[0]),
                  'fit_end': str(target.index[-1]), 'gates': GATES}
    checkpoint = output/f'checkpoint_{split}_v3.json'
    checkpoint_reused = False
    if resume and not warm_start and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding='utf-8'))
        if saved.get('provenance') == json.loads(json.dumps(provenance)):
            chosen, ignored = _parameters_from_file(checkpoint)
            source, checkpoint_reused = checkpoint, True
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+split
    run_dir = output/'runs'/run_id
    run_dir.mkdir(parents=True)
    status_path = output/f'calibration_status_{split}.json'
    status = {'status': 'running', 'run_id': run_id, 'objective_version': OBJECTIVE_VERSION,
              'process_id': os.getpid(), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_sha256': provenance['source_sha256'], 'workers': workers,
              'generations': generations, 'popsize': popsize, 'refinement_iterations': local_budget,
              'seed': seed, 'warm_start': str(source) if source else None,
              'ignored_old_parameters': ignored, 'exact_checkpoint_reused': checkpoint_reused,
              'initializer': INITIALIZER, 'local_fraction': LOCAL_FRACTION,
              'local_scale': LOCAL_SCALE, 'simplex_step': SIMPLEX_STEP,
              'initial_population_size': max(5, popsize*len(SEARCH))}
    _write_json(status_path, status)
    _write_json(run_dir/'provenance.json', {**provenance, 'execution': status})
    objective = CalibrationObjective(fit_config, target, groups, chosen)
    tracker = _Tracker(objective, checkpoint, provenance, run_dir, started)
    pool = None
    try:
        baseline = {}
        for name, params in [('defaults', ModelParams()), ('warm_start', chosen)]:
            baseline[name] = {**objective.evaluate_parameters(params), 'parameters': asdict(params)}
        x0 = pack(chosen)
        baseline['search_start'] = {**objective.evaluate(x0), 'parameters': asdict(unpack(x0, chosen))}
        tracker.record(x0, baseline['search_start'])
        _write_json(run_dir/'baseline.json', baseline)
        tracker.stage = 'broad_search'
        if workers > 1:
            pool = multiprocessing.get_context('spawn').Pool(workers, initializer=_initialize_worker, initargs=(objective,))
            mapper = _WorkerMap(pool, tracker)
        else:
            mapper = 1
        result = differential_evolution(tracker, [(lo, hi) for _, lo, hi in SEARCH],
                                        maxiter=generations, popsize=popsize, seed=seed,
                                        polish=False, x0=x0, init=hybrid_initial_population(x0, popsize, seed), tol=.005,
                                        workers=mapper, updating='deferred')
        if pool is not None:
            pool.close(); pool.join(); pool = None
        tracker.stage = 'refinement'
        if local_budget:
            local_start = pack(ModelParams(**tracker.best['parameters']))
            local = minimize(tracker, local_start, method='Nelder-Mead',
                             bounds=[(lo, hi) for _, lo, hi in SEARCH],
                             options={'maxiter': local_budget, 'xatol': .002, 'fatol': .002,
                                      'initial_simplex': bounded_initial_simplex(local_start)})
            refinement = {'success': bool(local.success), 'message': str(local.message), 'evaluations': int(local.nfev)}
        else:
            refinement = {'success': None, 'message': 'Disabled explicitly', 'evaluations': 0}
        if tracker.best['loss'] >= 1e9:
            raise RuntimeError(f'All candidates failed: {tracker.errors}')
        if _source_hashes() != provenance['source_sha256']:
            raise RuntimeError('Sources changed during fitting; refusing mixed-version publication')
        load_targets.cache_clear(); group_targets.cache_clear()
        if _frame_hash(load_targets().reindex(target.index)) != provenance['target_sha256'] or _frame_hash(group_targets().reindex(target.index)) != provenance['group_sha256']:
            raise RuntimeError('Targets changed during fitting; refusing publication')
        fitted = ModelParams(**tracker.best['parameters'])
        final_config = replace(config, params=fitted)
        trajectory, financial, ledger = simulate(final_config, engine='cadcad')
        fast, _, _ = simulate(final_config, engine='fast', keep_ledger=False)
        pd.testing.assert_frame_equal(fast, trajectory, rtol=1e-12, atol=1e-5)
        final_objective = objective.components(trajectory)
        report = {'fit_split': split, 'objective_version': OBJECTIVE_VERSION,
                  'calls': tracker.calls, 'objective': final_objective['loss'],
                  'objective_details': final_objective, 'baseline_compare': baseline,
                  'improvement_from_search_start': float(baseline['search_start']['loss']-final_objective['loss']),
                  'runtime_seconds': time.perf_counter()-started, 'provenance': provenance,
                  'optimizer': {'broad_search_success': bool(result.success), 'broad_search_message': str(result.message),
                                'refinement': refinement, 'run_id': run_id, 'workers': workers, 'seed': seed,
                                'initializer': INITIALIZER, 'local_fraction': LOCAL_FRACTION,
                                'local_scale': LOCAL_SCALE, 'simplex_step': SIMPLEX_STEP,
                                'initial_population_size': max(5, popsize*len(SEARCH))},
                  'train': fit_metrics(trajectory, split='train'), 'validation': fit_metrics(trajectory, split='validation'),
                  'all': fit_metrics(trajectory), 'financial_metrics': financial,
                  'validation_is_parameter_holdout': split == 'train', 'structural_validation_is_independent': False,
                  'reference_funding_timing': 'early', 'source_sha256': financial['engine_source_sha256'],
                  'parameter_sha256': parameter_sha256(fitted),
                  'fast_cadcad_equivalence_verified': True,
                  'limitations': ['Liquidity and behavioral parameters are not uniquely identified.',
                                  'Only train fitting provides a temporal parameter holdout; full fit uses all event targets.',
                                  'Historical replay is resource constrained, not exact Jump/TFL execution.',
                                  'Failed fidelity gates make policy results exploratory, not historical causal evidence.']}
        if _source_hashes() != provenance['source_sha256']:
            raise RuntimeError('Sources changed during final verification; refusing publication')
        trajectory.to_parquet(run_dir/'trajectory.parquet')
        _write_json(run_dir/'report.json', report)
        name = 'parameters.json' if split == 'train' else 'parameters_full_fit.json'
        _write_json(output/name, asdict(fitted))
        _write_json(output/f'best_{split}.json', tracker.best)
        _write_json(output/f'report_{split}.json', report)
        trajectory.to_parquet(output/f'trajectory_{split}.parquet')
        ledger.to_csv(output/f'ledger_{split}.csv', index=False)
        final_config.save(output/f'config_{split}.json')
        status.update(status='complete', calls=tracker.calls, objective=report['objective'], runtime_seconds=report['runtime_seconds'])
        _write_json(status_path, status)
        _write_json(run_dir/'execution.json', status)
        return report
    except BaseException as error:
        status.update(status='failed', error=f'{type(error).__name__}: {error}', calls=tracker.calls,
                      runtime_seconds=time.perf_counter()-started)
        _write_json(status_path, status); _write_json(run_dir/'execution.json', status)
        raise
    finally:
        if pool is not None:
            pool.terminate(); pool.join()


def refresh_report(split='train'):
    """Recompute metrics without attributing old calibration to a new engine."""
    output = ROOT/'outputs'/'calibration'
    name = 'parameters.json' if split == 'train' else 'parameters_full_fit.json'
    params, _ = _parameters_from_file(output/name)
    config = ScenarioConfig(params=params, stochastic=False, funding_timing='early')
    trajectory, financial, ledger = simulate(config, engine='cadcad')
    path = output/f'report_{split}.json'
    report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    report.pop('validation_is_independent', None)
    original = report.get('provenance', {}).get('source_sha256', {}).get('engine.py', report.get('source_sha256'))
    report.update(fit_split=split, train=fit_metrics(trajectory, split='train'), validation=fit_metrics(trajectory, split='validation'),
                  all=fit_metrics(trajectory), financial_metrics=financial, validation_is_parameter_holdout=split == 'train',
                  structural_validation_is_independent=False, reference_funding_timing='early',
                  source_sha256=financial['engine_source_sha256'], calibration_engine_matches_refresh=original == financial['engine_source_sha256'])
    report['parameter_sha256'] = parameter_sha256(params)
    report['calibration_stale_for_current_engine'] = not report['calibration_engine_matches_refresh']
    _write_json(path, report)
    trajectory.to_parquet(output/f'trajectory_{split}.parquet')
    ledger.to_csv(output/f'ledger_{split}.csv', index=False)
    config.save(output/f'config_{split}.json')
    return report
