from dataclasses import replace
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
from .config import ROOT, ScenarioConfig, PolicyConfig, load_params
from .engine import simulate
from .metrics import fit_metrics


def scenario_presets(params=None,stochastic=True,stress_days=7):
    params=params or load_params()
    base=ScenarioConfig(params=params,stochastic=stochastic,stress_days=stress_days)
    buy=PolicyConfig('buy_ust',max_spend_per_hour=50e6,duration_hours=120)
    lp=PolicyConfig('liquidity',max_spend_per_hour=20e6,duration_hours=120,allocation_fraction=.3)
    return {
        'historical':replace(base,name='historical',mode='historical',funding_timing='early'),
        'no_rescue':replace(base,name='no_rescue',mode='no_rescue'),
        'buy_ust':replace(base,name='buy_ust',mode='counterfactual',policies=[buy]),
        'liquidity':replace(base,name='liquidity',mode='counterfactual',policies=[replace(lp,allocation_fraction=1.)]),
        'native_swap':replace(base,name='native_swap',mode='counterfactual',policies=[PolicyConfig('native_swap',pool_multiplier=4.,recovery_multiplier=.5,duration_hours=120)]),
        'withdrawal_gate':replace(base,name='withdrawal_gate',mode='counterfactual',policies=[PolicyConfig('withdrawal_gate',withdrawal_fraction_per_day=.2,duration_hours=48)]),
        'combined':replace(base,name='combined',mode='counterfactual',policies=[replace(buy,allocation_fraction=.7),lp,PolicyConfig('native_swap',pool_multiplier=2.,duration_hours=120)])
    }


def export_run(config,trajectory,metrics,ledger,directory=None):
    directory=Path(directory or ROOT/'outputs'/'runs'/f'{config.name}_seed{config.seed}')
    directory.mkdir(parents=True,exist_ok=True)
    config.save(directory/'config.json')
    trajectory.to_parquet(directory/'trajectory.parquet')
    trajectory.to_csv(directory/'trajectory.csv')
    ledger.to_csv(directory/'ledger.csv',index=False)
    (directory/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    return directory


def run_suite(seeds=20,names=None,engine='cadcad',stress_days=7,resume=False):
    directory=ROOT/'outputs'/'experiments'; directory.mkdir(parents=True,exist_ok=True)
    presets=scenario_presets(stress_days=stress_days)
    names=names or list(presets)
    records=[]; bands=[]
    completed=set()
    if resume and (directory/'runs.csv').exists():
        prior=pd.read_csv(directory/'runs.csv')
        current_hash=hashlib.sha256((ROOT/'luna_sim'/'engine.py').read_bytes()).hexdigest()
        if not prior.engine_source_sha256.eq(current_hash).all(): raise ValueError('Engine changed: run a fresh suite')
        for name in names:
            saved=prior[prior.scenario==name]
            if len(saved)==seeds and set(saved.seed)==set(range(42,42+seeds)):
                c=ScenarioConfig.from_dict(json.loads((ROOT/'outputs'/'runs'/f'{name}_seed42'/'config.json').read_text(encoding='utf-8')))
                if c.to_dict()!=replace(presets[name],seed=42).to_dict(): raise ValueError(f'Configuration changed: {name}')
                completed.add(name)
        records=prior[prior.scenario.isin(completed)].to_dict('records')
        old_bands=pd.read_parquet(directory/'bands.parquet')
        bands=[old_bands[old_bands.scenario.isin(completed)]]
    metadata={'status':'running','seeds':seeds,'scenarios':names,'completed_scenarios':sorted(completed),
        'parameters':presets[names[0]].params.__dict__,
        'engine_source_sha256':hashlib.sha256((ROOT/'luna_sim'/'engine.py').read_bytes()).hexdigest()}
    metadata_path=directory/'execution_metadata.json'
    metadata_path.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    for name in names:
        if name in completed:
            print(f'{name}: verified checkpoint {seeds}/{seeds}',flush=True)
            continue
        config=presets[name]; trajectories=[]
        for seed in range(seeds):
            c=replace(config,seed=42+seed)
            t,m,l=simulate(c,engine=engine,keep_ledger=seed==0)
            m.update(scenario=name,seed=c.seed)
            records.append({k:v for k,v in m.items() if not isinstance(v,dict)})
            if seed==0:
                export_run(c,t,m,l)
            trajectories.append(t[['ust_price','luna_price','luna_supply','anchor_deposits','support_spent','withdraw_queue','depositor_loss_fraction']])
            print(f'{name}: {seed+1}/{seeds}, UST={m["final_ust_price"]:.4f}, rescued={m["rescued"]}, runtime={m["runtime_seconds"]:.2f}s',flush=True)
        stack=np.stack([t.to_numpy() for t in trajectories])
        for q,label in [(.05,'p05'),(.5,'median'),(.95,'p95')]:
            band=pd.DataFrame(np.quantile(stack,q,axis=0),index=trajectories[0].index,columns=trajectories[0].columns)
            band['scenario']=name; band['quantile']=label; bands.append(band.reset_index())
        pd.DataFrame(records).to_csv(directory/'runs.csv',index=False)
        pd.concat(bands,ignore_index=True).to_parquet(directory/'bands.parquet',index=False)
        metadata['completed_scenarios'].append(name)
        metadata_path.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    runs=pd.DataFrame(records)
    numeric=runs.select_dtypes('number').columns.difference(['seed'])
    summary=runs.groupby('scenario')[numeric].median()
    summary['rescue_rate']=runs.groupby('scenario').rescued.mean()
    summary['n_runs']=runs.groupby('scenario').size()
    summary.to_csv(directory/'summary.csv')
    metadata['status']='complete'
    metadata_path.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return summary


def sensitivity(engine='cadcad'):
    params=load_params(); base=scenario_presets(params,stochastic=False,stress_days=7)['combined']
    records=[]
    settings=[('baseline',base)]
    for field in ['ust_depth_usd','luna_depth_usd','hazard_discount','hazard_outflow']:
        for factor in [.75,1.25]:
            settings.append((f'{field}_{factor}',replace(base,params=replace(params,**{field:getattr(params,field)*factor}))))
    for timing in ['early','late']:
        settings.append((f'funding_{timing}',replace(base,funding_timing=timing)))
    for delay in [15,60,360]:
        settings.append((f'delay_{delay}',replace(base,policies=[replace(p,delay_minutes=delay) for p in base.policies])))
    for threshold in [.995,.99,.98,.95]:
        settings.append((f'trigger_{threshold}',replace(base,policies=[replace(p,threshold=threshold) for p in base.policies])))
    for pool in [1.,2.,4.,8.]:
        policies=[replace(p,pool_multiplier=pool) if p.action=='native_swap' else p for p in base.policies]
        settings.append((f'native_pool_{pool}',replace(base,policies=policies)))
    for name,c in settings:
        _,m,_=simulate(c,engine=engine,keep_ledger=False)
        records.append({'setting':name,**{k:v for k,v in m.items() if not isinstance(v,dict)}})
        print('sensitivity',name,m['final_ust_price'],flush=True)
    result=pd.DataFrame(records)
    directory=ROOT/'outputs'/'experiments'; directory.mkdir(parents=True,exist_ok=True)
    result.to_csv(directory/'sensitivity.csv',index=False)
    return result


def timestep_check(engine='cadcad'):
    base=ScenarioConfig(params=load_params(),stochastic=False,funding_timing='early')
    t15,m15,_=simulate(base,engine=engine,keep_ledger=False)
    t5,m5,_=simulate(replace(base,dt_minutes=5),engine=engine,keep_ledger=False)
    aligned=t5.reindex(t15.index)
    result={'ust_mae_between_steps':float(abs(aligned.ust_price-t15.ust_price).mean()),
        'deposit_nrmse_between_steps':float(np.sqrt(np.mean((aligned.anchor_deposits-t15.anchor_deposits)**2))/t15.anchor_deposits.iloc[0]),
        'luna_log_rmse_between_steps':float(np.sqrt(np.mean((np.log10(aligned.luna_price)-np.log10(t15.luna_price))**2))),
        '15min_fit':fit_metrics(t15),'5min_fit':fit_metrics(t5,dt=5),
        'note':'A large discrepancy means event ordering/coarse time resolution affects policy conclusions.'}
    directory=ROOT/'outputs'/'experiments'; directory.mkdir(parents=True,exist_ok=True)
    (directory/'timestep_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
