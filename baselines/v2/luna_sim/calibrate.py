"""Calibration is separate from policy experiments; no scenario-specific refitting."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import time
import numpy as np
from scipy.optimize import differential_evolution, minimize
from .config import ROOT, ModelParams, ScenarioConfig
from .engine import simulate
from .data import load_targets, group_targets
from .metrics import fit_metrics,first_depeg

# Log-scaled depths/capacity make searches comparable across orders of magnitude.
SEARCH = [
    ('hazard_base',-14.,-6.5), ('hazard_size',0.,1.),
    ('hazard_discount',10.,250.), ('hazard_outflow',0.,120.),
    ('hazard_luna',0.,30.), ('log_ust_depth',9.,11.2),
    ('ust_depth_luna_beta',0.,2.5), ('log_luna_depth',7.5,10.2),
    ('luna_depth_growth',.2,1.1), ('log_arb_capacity',8.,9.5),
    ('luna_beta_btc',.3,5.),
    ('ust_confidence_beta',.03,1.5),
    ('luna_residual_bid_fraction',.005,.20),
]


def unpack(values,base=None):
    p=asdict(base or ModelParams())
    for (key,_,_),value in zip(SEARCH,values):
        if key=='log_ust_depth': p['ust_depth_usd']=10**value
        elif key=='log_luna_depth': p['luna_depth_usd']=10**value
        elif key=='log_arb_capacity': p['arb_capacity_day']=10**value
        else: p[key]=float(value)
    return ModelParams(**p)


def calibrate(generations=12,popsize=4,split='train',population=1000,resume=True):
    output=ROOT/'outputs'/'calibration'; output.mkdir(parents=True,exist_ok=True)
    target=load_targets(); groups=group_targets()
    mask=target.index<'2022-05-11T00:00:00Z' if split=='train' else np.ones(len(target),dtype=bool)
    target=target.loc[mask]
    best={'loss':float('inf'),'calls':0}; started=time.perf_counter()
    config=ScenarioConfig(n_depositors=population,stochastic=False,funding_timing='early')
    log=[]
    def objective(values):
        p=unpack(values)
        try:
            t,_,_=simulate(replace(config,params=p),engine='fast',keep_ledger=False)
            t=t.reindex(target.index)
            tolerance=np.where(target.ust_price>=.98,.025,.08)
            u=np.mean(((t.ust_price-target.ust_price)/tolerance)**2)
            d=np.mean((t.anchor_deposits-target.anchor_deposits)**2)/(target.anchor_deposits.iloc[0]*.12)**2
            l=np.mean((np.log10(t.luna_price.clip(lower=1e-12))-np.log10(target.luna_price.clip(lower=1e-12)))**2)/(.7**2)
            s=np.mean((np.log10(t.luna_supply.clip(lower=1))-np.log10(target.luna_supply.clip(lower=1)))**2)/(.5**2)
            g=np.mean([np.mean((t[f'group_{i}_remaining']-groups[i].reindex(t.index))**2) for i in range(6)])/(.2**2)
            native_daily=t.native_served.resample('1D').sum()
            observed_daily=target.native_ust.resample('1D').sum()
            native_volume=np.mean((native_daily-observed_daily)**2)/max(observed_daily.max()*.25,1)**2
            fee_mask=target.native_ust.gt(0)&target.native_fee.notna()
            native_fee=np.mean(((t.loc[fee_mask,'native_fee']-target.loc[fee_mask,'native_fee'])/.10)**2) if fee_mask.any() else 0.
            truth_break=first_depeg(target.ust_price); model_break=first_depeg(t.ust_price)
            timing=min(20.,abs((truth_break-model_break).total_seconds())/3600/12) if truth_break is not None and model_break is not None else 10.
            loss=float(u+d+l+s+.4*g+.2*timing+native_volume+.2*native_fee)
            if not np.isfinite(loss): loss=1e6
        except (AssertionError,ValueError,OverflowError,FloatingPointError):
            loss=1e6
        best['calls']+=1
        if loss<best['loss']:
            best.update(loss=loss,values=np.asarray(values).tolist())
            (output/f'best_{split}.json').write_text(json.dumps({'loss':loss,'calls':best['calls'],'parameters':asdict(p),'search_values':best['values'],'fit_split':split},indent=2),encoding='utf-8')
        if best['calls']%25==0:
            print(f"calls={best['calls']} best_loss={best['loss']:.5f} elapsed={time.perf_counter()-started:.0f}s",flush=True)
        return loss
    x0=None
    previous=output/f'best_{split}.json'
    if resume and previous.exists():
        x0=np.asarray(json.loads(previous.read_text())['search_values'])
        if len(x0)==11: x0=np.append(x0,.18)
        if len(x0)==12: x0=np.append(x0,.08)
    elif (output/'best_train.json').exists():
        x0=np.asarray(json.loads((output/'best_train.json').read_text())['search_values'])
        if len(x0)==11: x0=np.append(x0,.18)
        if len(x0)==12: x0=np.append(x0,.08)
    init='latinhypercube'
    if x0 is not None:
        rng=np.random.default_rng(42); lows=np.array([lo for _,lo,hi in SEARCH]); highs=np.array([hi for _,lo,hi in SEARCH]); count=popsize*len(SEARCH)
        initial=np.clip(x0+rng.normal(0,.12,(count,len(SEARCH)))*(highs-lows),lows,highs)
        initial[:max(5,count//4)]=rng.uniform(lows,highs,(max(5,count//4),len(SEARCH)))
        initial[-1]=x0; init=initial
    result=differential_evolution(objective,[(lo,hi) for _,lo,hi in SEARCH],maxiter=generations,popsize=popsize,seed=42,polish=False,x0=x0,init=init,tol=.005,workers=1)
    # Refinement uses exactly the same training targets.
    local=minimize(objective,result.x,method='Nelder-Mead',bounds=[(lo,hi) for _,lo,hi in SEARCH],options={'maxiter':max(30,generations*10),'xatol':.002,'fatol':.002})
    fitted=unpack(best['values'])
    t,m,_=simulate(replace(config,params=fitted),engine='cadcad',keep_ledger=False)
    name='parameters.json' if split=='train' else 'parameters_full_fit.json'
    (output/name).write_text(json.dumps(asdict(fitted),indent=2),encoding='utf-8')
    report={'fit_split':split,'objective_version':'prices_stocks_groups_onset_native_volume_fee_v2','calls':best['calls'],'objective':best['loss'],'runtime_seconds':time.perf_counter()-started,'train':fit_metrics(t,split='train'),'validation':fit_metrics(t,split='validation'),'all':fit_metrics(t),'financial_metrics':m,'limitations':['Price/depth parameters are not uniquely identified by the supplied extracts.','Historical intervention replay is resource constrained, not exact Jump/TFL execution.','If any fidelity gate fails, policy results are exploratory and not historical causal evidence.']}
    (output/f'report_{split}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    t.to_parquet(output/f'trajectory_{split}.parquet')
    return report


def refresh_report(split='train'):
    """Publish metrics from the current source, not a stale optimizer process."""
    output=ROOT/'outputs'/'calibration'
    name='parameters.json' if split=='train' else 'parameters_full_fit.json'
    params=ModelParams(**json.loads((output/name).read_text(encoding='utf-8')))
    config=ScenarioConfig(params=params,stochastic=False,funding_timing='early')
    t,m,l=simulate(config,engine='cadcad')
    path=output/f'report_{split}.json'
    report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    report.pop('validation_is_independent',None)
    report.update(fit_split=split,train=fit_metrics(t,split='train'),validation=fit_metrics(t,split='validation'),all=fit_metrics(t),financial_metrics=m,validation_is_parameter_holdout=split=='train',structural_validation_is_independent=False,reference_funding_timing='early',source_sha256=m['engine_source_sha256'])
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    t.to_parquet(output/f'trajectory_{split}.parquet')
    l.to_csv(output/f'ledger_{split}.csv',index=False)
    config.save(output/f'config_{split}.json')
    return report
