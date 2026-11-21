import numpy as np
import pandas as pd
from .data import GROUPS, load_targets, group_targets


def longest_streak(mask,minutes):
    best=run=0
    for value in np.asarray(mask,dtype=bool):
        run=run+1 if value else 0; best=max(best,run)
    return best*minutes/60


def first_depeg(series):
    # Sustained break: below .98 for one hour, evaluated without future peek.
    duration=max(1,int(round(60/((series.index[1]-series.index[0]).total_seconds()/60)))) if len(series)>1 else 1
    flag=(series<.98).rolling(duration,min_periods=duration).sum()>=duration
    return series.index[np.flatnonzero(flag.to_numpy())[0]] if flag.any() else None


def group_fit_diagnostics(trajectory, groups):
    """Evaluate initial-principal survival only on finite paired observations.

    Coverage is reported for every group, including groups with no samples.
    No observed pairs yields None rather than a fabricated perfect score.
    """
    groups=groups.reindex(trajectory.index)
    details=[]
    for i,label in enumerate(GROUPS):
        observed=groups[i] if i in groups else pd.Series(np.nan,index=trajectory.index)
        predicted=trajectory[f'group_{i}_remaining']
        observed_mask=np.isfinite(observed.to_numpy(dtype=float))
        paired_mask=observed_mask&np.isfinite(predicted.to_numpy(dtype=float))
        observed_index=trajectory.index[observed_mask]
        paired_index=trajectory.index[paired_mask]
        details.append({'group':i,'label':label,
            'mae':float(abs(predicted.loc[paired_mask]-observed.loc[paired_mask]).mean()) if paired_mask.any() else None,
            'paired_count':int(paired_mask.sum()),'observed_count':int(observed_mask.sum()),
            'observed_start_utc':observed_index[0].isoformat() if len(observed_index) else None,
            'observed_end_utc':observed_index[-1].isoformat() if len(observed_index) else None,
            'paired_start_utc':paired_index[0].isoformat() if len(paired_index) else None,
            'paired_end_utc':paired_index[-1].isoformat() if len(paired_index) else None})
    errors=[item['mae'] for item in details if item['mae'] is not None]
    return {'group_mae_max':max(errors) if errors else None,
            'group_metrics':details,'group_paired_count':sum(item['paired_count'] for item in details),
            'group_observed_count':sum(item['observed_count'] for item in details)}


def fit_metrics(trajectory,dt=15,split='all',start=None,end=None):
    target=load_targets(dt)
    aligned=trajectory.join(target[['ust_price','luna_price','anchor_deposits','luna_supply']],rsuffix='_true',how='inner')
    if split=='train': aligned=aligned[aligned.index<'2022-05-11T00:00:00Z']
    elif split=='validation': aligned=aligned[aligned.index>='2022-05-11T00:00:00Z']
    if start is not None: aligned=aligned[aligned.index>=pd.Timestamp(start)]
    if end is not None: aligned=aligned[aligned.index<pd.Timestamp(end)]
    if aligned.empty: return {}
    result={'ust_mae':float(abs(aligned.ust_price-aligned.ust_price_true).mean()),
        'deposit_nrmse':float(np.sqrt(np.mean((aligned.anchor_deposits-aligned.anchor_deposits_true)**2))/target.anchor_deposits.iloc[0]),
        'luna_price_log_rmse':float(np.sqrt(np.mean((np.log10(aligned.luna_price.clip(lower=1e-12))-np.log10(aligned.luna_price_true.clip(lower=1e-12)))**2))),
        'luna_supply_log_rmse':float(np.sqrt(np.mean((np.log10(aligned.luna_supply.clip(lower=1))-np.log10(aligned.luna_supply_true.clip(lower=1)))**2)))}
    groups=group_targets(dt).reindex(aligned.index)
    result.update(group_fit_diagnostics(aligned,groups))
    # Use the complete event for onset; slicing validation would report a false zero.
    predicted,observed=first_depeg(trajectory.ust_price),first_depeg(load_targets(dt).ust_price)
    result['depeg_error_hours']=float(abs((predicted-observed).total_seconds())/3600) if predicted is not None and observed is not None else None
    result['predicted_depeg_utc']=predicted.isoformat() if predicted is not None else None
    result['observed_depeg_utc']=observed.isoformat() if observed is not None else None
    result['depeg_signed_error_hours']=float((predicted-observed).total_seconds()/3600) if predicted is not None and observed is not None else None
    thresholds={'ust_mae':.05,'deposit_nrmse':.10,'luna_price_log_rmse':.5,'luna_supply_log_rmse':.5,'group_mae_max':.15,'depeg_error_hours':6.}
    result['gates']={k:result[k] is not None and result[k]<=v for k,v in thresholds.items()}
    result['passes_all']=all(result['gates'].values())
    native=load_targets(dt).reindex(aligned.index)
    result['native_ust_observed_total']=float(native.native_ust.sum())
    result['native_ust_simulated_total']=float(aligned.native_served.sum())
    daily=aligned.native_served.resample('1D').sum()
    real_daily=native.native_ust.resample('1D').sum()
    result['native_daily_nrmse']=float(np.sqrt(np.mean((daily-real_daily)**2))/max(real_daily.max(),1))
    fee_mask=native.native_ust.gt(0)&native.native_fee.notna()
    result['native_fee_mae']=float(abs(aligned.loc[fee_mask,'native_fee']-native.loc[fee_mask,'native_fee']).mean()) if fee_mask.any() else None
    return result


def evaluate(trajectory,config):
    dt=config.dt_minutes
    window=max(1,1440//dt)
    requested=trajectory.withdraw_requested.rolling(window,min_periods=1).sum()
    served=trajectory.withdraw_served.rolling(window,min_periods=1).sum()
    # The workload includes claims already queued at the start of each window.
    # Zero new requests do not mean service is healthy while old claims remain.
    initial_queue=max(0.,float(trajectory.withdraw_queue.iloc[0]+trajectory.withdraw_served.iloc[0]-trajectory.withdraw_requested.iloc[0]))
    opening_queue=trajectory.withdraw_queue.shift(window).fillna(initial_queue)
    workload=requested+opening_queue
    ratio=np.minimum(1,served/workload.clip(lower=1)).where(workload>1,1.)
    nr=trajectory.native_requested.rolling(window,min_periods=1).sum()
    ns=trajectory.native_served.rolling(window,min_periods=1).sum()
    native_ratio=np.minimum(1,ns/nr.clip(lower=1)).where(nr>1,1.)
    queues=trajectory.withdraw_queue+trajectory.ust_sell_queue
    queue_stable=(queues-queues.shift(window).fillna(queues.iloc[0]))<=trajectory.anchor_deposits.iloc[0]*.001
    anchor_open=trajectory.anchor_open if 'anchor_open' in trajectory else pd.Series(True,index=trajectory.index)
    active=(trajectory.ust_price.between(.98,1.02)&(ratio>=.95)&(native_ratio>=.95)&trajectory.native_open&anchor_open&queue_stable)
    remaining=trajectory.support_remaining
    # Exclude quiet hours before the event and require actual intervention activation
    # for a rescue claim; no-policy trajectories can still be financially stable.
    after_event=trajectory.index>=pd.Timestamp('2022-05-08T00:00:00Z')
    active=active & after_event
    peg_hours=longest_streak(trajectory.ust_price.between(.98,1.02)&after_event,dt)
    operational_hours=longest_streak(active,dt)
    stress=trajectory[trajectory.index>=pd.Timestamp(config.end)]
    stress_mask=active.reindex(stress.index)
    post_supported=False
    if len(stress)>=7*1440//dt:
        # Entire seven-day no-new-support tail must remain operational and pegged.
        post_supported=bool(stress_mask.all() and stress.support_remaining.iloc[-1]>1 and np.diff(stress.support_spent).max(initial=0)<.01)
    adequate=operational_hours>=48 and remaining.iloc[-1]>1
    intervention_used=bool((trajectory.active_policies>0).any()) if 'active_policies' in trajectory else trajectory.support_spent.iloc[-1]>0
    rescued=bool(adequate and post_supported and config.mode=='counterfactual' and intervention_used)
    label='Phục hồi trong mô hình' if rescued else ('Giữ peg tạm thời / chưa xác minh 7 ngày' if adequate else 'Không đạt tiêu chí cứu vãn')
    return {'classification':label,'rescued':rescued,'peg_hours_longest':peg_hours,'operational_hours_longest':operational_hours,
        'stress_tail_verified':post_supported,'support_spent_usd':float(trajectory.support_spent.iloc[-1]),
        'support_remaining_usd':float(remaining.iloc[-1]),'btc_sold':float(trajectory.btc_sold.iloc[-1]),
        'tfl_own_contribution_usd':float(trajectory.tfl_added.iloc[-1]),'final_ust_price':float(trajectory.ust_price.iloc[-1]),
        'min_ust_price':float(trajectory.ust_price.min()),'final_luna_price':float(trajectory.luna_price.iloc[-1]),
        'final_luna_supply':float(trajectory.luna_supply.iloc[-1]),'final_anchor_deposits':float(trajectory.anchor_deposits.iloc[-1]),
        'final_withdraw_queue':float(trajectory.withdraw_queue.iloc[-1]),'depositor_loss_fraction':float(trajectory.depositor_loss_fraction.iloc[-1]),
        'withdraw_service_ratio':float(min(1,trajectory.withdraw_served.sum()/max(trajectory.withdraw_requested.sum()+initial_queue,1))) if trajectory.withdraw_requested.sum()+initial_queue>1 else 1.,
        'native_service_ratio':float(min(1,trajectory.native_served.sum()/max(trajectory.native_requested.sum(),1))) if trajectory.native_requested.sum()>1 else 1.,
        'max_accounting_errors':{k:float(trajectory[k].abs().max()) for k in ['ust_error','luna_error','usd_error','claim_error']},
        'historical_execution_gap_usd':float(trajectory.historical_requested_usd.iloc[-1]-trajectory.historical_executed_usd.iloc[-1]),
        'qualification':'Conditional financial experiment; validator security and exact exchange/Jump execution are outside the model.'}
