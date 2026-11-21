"""Group-survival targets must not invent observations after the extract ends."""
import numpy as np
import pandas as pd
import pytest

from luna_sim import data, metrics
from luna_sim.calibrate import CalibrationObjective, GATES, _normalised_metrics
from luna_sim.config import ModelParams, ScenarioConfig


@pytest.fixture(autouse=True)
def clear_group_cache():
    clear_target=data.load_targets.cache_clear
    clear_target()
    data.group_targets.cache_clear()
    yield
    clear_target()
    data.group_targets.cache_clear()


def install_source(monkeypatch, index, transactions, size=None):
    if size is None:
        size=pd.DataFrame({'address':['holder'],'prerun_usd':[100.], 'prerun_aust':[100.]})
    sources={
        'loss/depositor_prerun_size.parquet':size,
        'labels/interdm_addresses.parquet':pd.DataFrame({'address':['excluded']}),
        'anchor_run/anchor_run_tx_cleaned.parquet':pd.DataFrame(transactions,columns=['time','sender','action','ust_vol']),
    }
    monkeypatch.setattr(data,'read_source',lambda name,source: sources[name].copy())
    monkeypatch.setattr(data,'load_targets',lambda dt,source: pd.DataFrame(index=index))


def test_missing_end_days_are_censored_but_final_observed_bucket_is_kept(monkeypatch):
    index=pd.date_range('2022-05-06T00:15:00Z','2022-05-16T00:00:00Z',freq='15min',inclusive='left')
    install_source(monkeypatch,index,[
        ('2022-05-06T00:00:01Z','holder','withdraw',20.),
        ('2022-05-13T23:59:39Z','unmatched','deposit',1.),
    ])
    observed=data.group_targets(source='synthetic')
    assert observed.loc['2022-05-14T00:00:00Z',0]==.8
    assert observed.loc['2022-05-14T00:15:00Z':].isna().all().all()
    assert observed[0].notna().sum()==768
    assert observed.attrs['observation_coverage']['raw_end_utc']=='2022-05-13T23:59:39+00:00'
    # End coverage comes from the whole extract, even when this group is quiet.
    assert observed.loc['2022-05-13T12:00:00Z',0]==.8


def test_transaction_targets_distinguish_observed_quiet_buckets_from_missing_days(monkeypatch):
    sources={
        'prices/ust_price_may2022.parquet':pd.DataFrame({'time':['2022-05-05T00:00:00Z'],'ust_price':[1.]}),
        'prices/luna_price_may2022.parquet':pd.DataFrame({'time':['2022-05-05T00:00:00Z'],'luna_price':[10.]}),
        'anchor_run/epoch_state_fig10.parquet':pd.DataFrame({'time_utc':['2022-05-05T00:00:00Z'],'deposit_b_ust':[10.]}),
        'native_swaps/luna_total_supply_run.parquet':pd.DataFrame({'luna_supply':[1e9]},index=pd.to_datetime(['2022-05-05T23:00:00Z'])),
        'anchor_run/anchor_run_tx_cleaned.parquet':pd.DataFrame({
            'time':['2022-05-06T00:00:01Z','2022-05-13T23:59:39Z'],
            'action':['withdraw','deposit'],'ust_vol':[20.,1.]}),
        'native_swaps/ust_luna_swaps_run.parquet':pd.DataFrame({
            'time':pd.Series([],dtype='datetime64[ns, UTC]'),'offer_amount':pd.Series([],dtype=float),
            'swap_amount':pd.Series([],dtype=float),'fee_amount':pd.Series([],dtype=float)}),
    }
    monkeypatch.setattr(data,'read_source',lambda name,source: sources[name].copy())
    target=data.load_targets(source='synthetic_transactions')
    assert target.loc['2022-05-06T00:15:00Z','observed_withdraw']==20.
    assert target.loc['2022-05-06T00:30:00Z',['observed_withdraw','observed_deposit']].eq(0.).all()
    assert target.loc['2022-05-14T00:00:00Z','observed_deposit']==1.
    assert target.loc['2022-05-14T00:15:00Z':,['observed_withdraw','observed_deposit']].isna().all().all()
    assert target[['ust_price','luna_price','anchor_deposits','luna_supply','native_ust']].notna().all().all()
    assert target.attrs['anchor_transaction_observation_coverage']['last_bucket_end_utc']=='2022-05-14T00:00:00+00:00'


def test_prestart_withdrawals_survive_alignment_and_redeposit_does_not_restore_fifo(monkeypatch):
    index=pd.date_range('2022-05-06T00:30:00Z',periods=3,freq='15min')
    install_source(monkeypatch,index,[
        ('2022-05-06T00:00:01Z','holder','withdraw',30.),
        ('2022-05-06T00:20:00Z','holder','deposit',100.),
        ('2022-05-06T00:40:00Z','holder','withdraw',100.),
        ('2022-05-06T00:59:00Z','unmatched','deposit',1.),
    ])
    observed=data.group_targets(source='synthetic')
    np.testing.assert_allclose(observed[0],[.7,0.,0.])


def test_cohort_exclusions_and_exact_bin_boundaries_match_population(monkeypatch):
    index=pd.date_range('2022-05-06T00:15:00Z',periods=2,freq='15min')
    values=[100.,1e3,1e4,1e5,1e6,1e7]
    size=pd.DataFrame({'address':[f'g{i}' for i in range(6)]+['excluded','no_aust'],
                       'prerun_usd':values+[1e8,1e8], 'prerun_aust':values+[1e8,0.]})
    transactions=[('2022-05-06T00:01:00Z',f'g{i}','withdraw',value/2) for i,value in enumerate(values)]
    transactions += [('2022-05-06T00:20:00Z','unmatched','deposit',1.)]
    install_source(monkeypatch,index,transactions,size)
    observed=data.group_targets(source='synthetic')
    np.testing.assert_allclose(observed.iloc[0],np.full(6,.5))
    np.testing.assert_array_equal(pd.cut(pd.Series(values),data.BINS,labels=False,right=False),np.arange(6))


def synthetic_fit(index):
    target=pd.DataFrame({'ust_price':1.,'luna_price':10.,'luna_supply':1e9,
                         'anchor_deposits':10e9,'native_ust':0.,'native_fee':np.nan},index=index)
    target.attrs['initial_deposits']=10e9
    trajectory=target.drop(columns=['native_ust']).copy()
    trajectory['native_served']=0.
    for i in range(6): trajectory[f'group_{i}_remaining']=1.
    return target,trajectory


def test_zero_observations_remain_missing_and_cannot_pass_group_gate(monkeypatch):
    index=pd.date_range('2022-05-06T00:15:00Z',periods=8,freq='15min')
    install_source(monkeypatch,index,[])
    groups=data.group_targets(source='synthetic')
    assert groups.isna().all().all()
    target,trajectory=synthetic_fit(index)
    monkeypatch.setattr(metrics,'load_targets',lambda dt: target)
    monkeypatch.setattr(metrics,'group_targets',lambda dt: groups)
    result=metrics.fit_metrics(trajectory)
    assert result['group_mae_max'] is None and result['group_paired_count']==0
    assert not result['gates']['group_mae_max'] and not result['passes_all']
    with pytest.raises(ValueError,match='No finite paired group observations'):
        CalibrationObjective(ScenarioConfig(),target,groups,ModelParams()).components(trajectory)


def test_group_mae_uses_finite_pairs_and_reports_each_coverage():
    index=pd.date_range('2022-05-06T00:15:00Z',periods=6,freq='15min')
    _,trajectory=synthetic_fit(index)
    groups=pd.DataFrame(np.nan,index=index,columns=range(6))
    groups[0]=[1.,.5,np.nan,np.inf,.2,.1]
    trajectory['group_0_remaining']=[.8,np.nan,0.,.3,np.inf,.3]
    result=metrics.group_fit_diagnostics(trajectory,groups)
    first=result['group_metrics'][0]
    assert np.isclose(result['group_mae_max'],.2)
    assert first['paired_count']==2 and first['observed_count']==4
    assert first['observed_start_utc']==index[0].isoformat()
    assert first['observed_end_utc']==index[-1].isoformat()
    assert first['paired_start_utc']==index[0].isoformat()
    assert first['paired_end_utc']==index[-1].isoformat()
    assert result['group_metrics'][1]['mae'] is None


def test_unobserved_phase_omits_group_term_without_nan_or_fabricated_zero():
    index=pd.date_range('2022-05-10T23:00:00Z',periods=8,freq='15min')
    target,trajectory=synthetic_fit(index)
    groups=pd.DataFrame(np.nan,index=index,columns=range(6))
    groups.loc[index<'2022-05-11T00:00:00Z',:]=1.
    trajectory.loc[index>='2022-05-11T00:00:00Z','luna_price']=100.
    objective=CalibrationObjective(ScenarioConfig(),target,groups,ModelParams())
    result=objective.components(trajectory)
    assert np.isfinite(result['loss'])
    # Four measured ratios in this phase: one LUNA ratio of 2, the rest zero.
    assert result['phase_losses']['post_may11']==1.
    late=index>='2022-05-11T00:00:00Z'
    phase=_normalised_metrics(trajectory.loc[late],target.loc[late],groups.loc[late],require_group_observations=False)
    assert 'group_mae_max' not in phase
    assert GATES['group_mae_max']==.15 and len(GATES)==6


def test_observed_phase_with_no_finite_predictions_is_rejected():
    index=pd.date_range('2022-05-11T00:00:00Z',periods=4,freq='15min')
    target,trajectory=synthetic_fit(index)
    groups=pd.DataFrame(1.,index=index,columns=range(6))
    for i in range(6): trajectory[f'group_{i}_remaining']=np.nan
    with pytest.raises(ValueError,match='No finite paired group observations'):
        _normalised_metrics(trajectory,target,groups,require_group_observations=False)


def test_subhour_fit_has_finite_loss_and_empty_fit_is_rejected():
    index=pd.date_range('2022-05-06T00:15:00Z',periods=2,freq='15min')
    target,trajectory=synthetic_fit(index)
    groups=pd.DataFrame(1.,index=index,columns=range(6))
    assert CalibrationObjective(ScenarioConfig(),target,groups,ModelParams()).components(trajectory)['loss']==0.
    with pytest.raises(ValueError,match='nonempty fit window'):
        CalibrationObjective(ScenarioConfig(),target.iloc[:0],groups.iloc[:0],ModelParams()).components(trajectory.iloc[:0])
