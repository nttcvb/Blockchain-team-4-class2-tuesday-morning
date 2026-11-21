from dataclasses import replace
import json
import numpy as np
import pandas as pd
import pytest
from luna_sim.config import ScenarioConfig,PolicyConfig,ModelParams,ROOT
from luna_sim.engine import simulate,context,initialize,observation,rescue,markets,anchor,invariants,BLOCKS
from luna_sim.data import initial_facts,load_targets,build_population
from luna_sim.metrics import evaluate


def short(**kwargs):
    return ScenarioConfig(end='2022-05-06T04:00:00Z',n_depositors=100,stochastic=False,**kwargs)


def observed_start(ctx):
    b=initialize(ctx)
    b['step']=int(ctx['index'].get_indexer([pd.Timestamp(ctx['config'].start)])[0])-1
    return observation(ctx,b)


def test_real_data_units_and_initial_snapshot():
    facts=initial_facts()
    assert 14e9<facts['anchor_deposits']<14.1e9
    assert 18e9<facts['ust_supply']<19e9
    assert abs(facts['anchor_cash']+facts['loan_balance']-facts['anchor_deposits'])<1e-3
    assert load_targets().index.tz is not None
    agents,institution=build_population()
    assert len(agents)==1000
    assert 'full_maxusd' not in agents
    assert abs((agents.prerun_usd*agents.weight).sum()+institution-facts['anchor_deposits'])<.01


@pytest.mark.parametrize('stochastic',[False,True])
def test_cadcad_matches_ordered_calibration_runner(stochastic):
    config=replace(short(),stochastic=stochastic)
    fast,_,lf=simulate(config,engine='fast')
    actual,_,la=simulate(config,engine='cadcad')
    pd.testing.assert_frame_equal(fast,actual,rtol=1e-12,atol=1e-5)
    pd.testing.assert_frame_equal(lf,la)


def test_policy_cannot_use_future_assets_and_delay():
    policy=PolicyConfig('buy_ust',trigger='time',start_time='2022-05-07T12:00:00Z',delay_minutes=60)
    c=replace(short(mode='counterfactual',policies=[policy]),start='2022-05-07T12:00:00Z',end='2022-05-07T14:00:00Z')
    ctx=context(c); b=observed_start(ctx)
    b=rescue(ctx,b)
    assert b['fund_usd'].sum()==0 and b['fund_btc'].sum()==0
    assert not b['active_policies'].any()
    assert b['fund_spent'].sum()==0


def test_zero_budget_cannot_buy_and_buy_is_not_a_burn():
    policy=PolicyConfig('buy_ust',trigger='time',start_time='2022-05-07T00:00:00Z',delay_minutes=0)
    c=replace(short(mode='counterfactual',policies=[policy]),start='2022-05-08T03:00:00Z',end='2022-05-08T03:15:00Z')
    ctx=context(c); b=observed_start(ctx); before=b['ust_supply']
    b['active_policies'][0]=True
    zero=b.copy(); zero['fund_usd']=np.zeros(2); zero['fund_btc']=np.zeros(2)
    out=rescue(ctx,zero)
    assert out['fund_spent'].sum()==0
    funded=rescue(ctx,b)
    assert funded['fund_spent'].sum()>0
    assert funded['ust_supply']==before
    assert funded['fund_ust'].sum()>0
    invariants(ctx,funded)


def test_btc_liquidation_and_internal_transfers_are_not_new_funding():
    c=replace(short(mode='counterfactual',policies=[PolicyConfig('buy_ust',trigger='time',start_time='2022-05-09T00:00:00Z',delay_minutes=0,max_spend_per_hour=2e9)]),start='2022-05-11T00:00:00Z',end='2022-05-11T01:00:00Z')
    ctx=context(c); b=observed_start(ctx); initial=b['locked_btc']+b['fund_btc'].sum()
    b['ust_price']=.90
    b=rescue(ctx,b)
    assert b['btc_sold']>0
    assert abs(b['locked_btc']+b['fund_btc'].sum()+b['btc_sold']-initial)<1e-6
    assert b['tfl_added']<=613616889
    assert any(e['kind']=='btc_liquidation' and e['fee_usd']>0 for e in b['events'])
    invariants(ctx,b)


def test_withdrawal_gate_retains_claims_and_queue():
    p=PolicyConfig('withdrawal_gate',trigger='time',start_time='2022-05-07T00:00:00Z',delay_minutes=0,withdrawal_fraction_per_day=.01)
    c=replace(short(mode='counterfactual',policies=[p]),start='2022-05-07T01:00:00Z',end='2022-05-07T01:15:00Z')
    ctx=context(c); b=observed_start(ctx); before=b['ust_supply']
    b['queue']=b['deposit'].copy(); b['institution_queue']=b['institution_deposit']
    out=anchor(ctx,b)
    assert out['withdraw_served']<=b['withdraw_limit']+.01
    assert out['queue'].sum()>0
    assert out['deposit'].sum()>0
    assert out['ust_supply']==before
    invariants(ctx,out)


def test_native_swap_burn_mint_and_no_negative_stocks():
    ctx=context(short()); b=observation(ctx,initialize(ctx)); b['ust_price']=.80
    u,l=b['ust_supply'],b['luna_supply']
    out=markets(ctx,b)
    assert out['native_served']>0
    assert out['ust_supply']<u and out['luna_supply']>l
    assert np.isclose(out['ust_supply'],u-out['new_ust_burn'])
    invariants(ctx,out)


def test_historical_cap_full_run_and_no_input_mutation():
    c=ScenarioConfig(n_depositors=100,stochastic=True)
    ctx=context(c); original=initialize(ctx); copied=original['deposit'].copy()
    updated=observation(ctx,original)
    for fn in BLOCKS[1:]: updated=fn(ctx,updated)
    np.testing.assert_array_equal(original['deposit'],copied)
    t,m,l=simulate(c,engine='fast')
    assert m['btc_sold']<=80081+.001
    assert m['tfl_own_contribution_usd']<=613616889+.001
    assert t[['market_usd','anchor_cash','anchor_deposits','support_remaining']].min().min()>=-.001
    assert max(m['max_accounting_errors'].values())<.1


def test_forced_historical_stop_is_not_applied_to_counterfactual():
    c=replace(short(),start='2022-05-14T00:00:00Z',end='2022-05-14T01:00:00Z')
    a,_,_=simulate(c,engine='fast')
    b,_,_=simulate(replace(c,mode='counterfactual'),engine='fast')
    assert not a.native_open.any() and b.native_open.all()


def test_config_round_trip_and_invalid_policy():
    config=short(policies=[PolicyConfig('buy_ust')])
    assert ScenarioConfig.from_dict(config.to_dict()).to_dict()==config.to_dict()
    with pytest.raises(ValueError): PolicyConfig('invent_cash').validate()
    with pytest.raises(ValueError): PolicyConfig('withdrawal_gate',withdrawal_fraction_per_day=-1).validate()
    with pytest.raises(ValueError): simulate(short(mode='counterfactual',policies=[PolicyConfig('buy_ust',trigger_steps=0)]),engine='fast')


def test_48h_quiet_before_event_is_not_rescue():
    c=replace(short(),end='2022-05-08T00:00:00Z')
    t,m,_=simulate(c,engine='fast')
    assert not m['rescued'] and not m['stress_tail_verified']


def test_late_start_is_warmed_from_original_snapshot():
    full=replace(short(),end='2022-05-07T02:00:00Z')
    all_steps,_,_=simulate(full,engine='fast')
    later,_,_=simulate(replace(full,start='2022-05-07T00:00:00Z'),engine='fast')
    pd.testing.assert_frame_equal(later,all_steps.loc[later.index])


def test_post_halt_residual_bid_does_not_create_cash_or_tokens():
    c=replace(short(),start='2022-05-13T03:00:00Z',end='2022-05-13T03:15:00Z')
    ctx=context(c); b=observed_start(ctx)
    b['luna_price']=1e-10; b['oracle_luna']=1e-10
    before_usd=b['market_usd']+b['arb_usd'].sum()+b['external_cash']+b['fees_usd']+b['realized_usd'].sum()+b['institution_realized']
    out=markets(ctx,b)
    after_usd=out['market_usd']+out['arb_usd'].sum()+out['external_cash']+out['fees_usd']+out['realized_usd'].sum()+out['institution_realized']
    assert out['luna_price']>b['luna_price']
    assert np.isclose(before_usd,after_usd,rtol=1e-12)
    assert out['luna_supply']==b['luna_supply']
    assert out['ust_supply']==b['ust_supply']
    invariants(ctx,out)


def test_nonmonetary_policy_can_qualify_without_spending_usd():
    c=ScenarioConfig(mode='counterfactual',stress_days=7,policies=[PolicyConfig('native_swap')])
    index=pd.date_range('2022-05-08', '2022-05-23',freq='15min',inclusive='left',tz='UTC')
    columns=['withdraw_requested','withdraw_served','native_requested','native_served','withdraw_queue','ust_sell_queue','support_spent','btc_sold','tfl_added','depositor_loss_fraction','ust_error','luna_error','usd_error','claim_error','historical_requested_usd','historical_executed_usd']
    t=pd.DataFrame(0.,index=index,columns=columns)
    for field in ['ust_price','luna_price','luna_supply','anchor_deposits','support_remaining','native_open','active_policies']: t[field]=1.
    t['support_remaining']=100.
    assert evaluate(t,c)['rescued']
    t['active_policies']=0
    assert not evaluate(t,c)['rescued']


def test_shared_cash_allocation_when_funding_binds():
    policies=[PolicyConfig(action,trigger='time',start_time='2022-05-08T03:00:00Z',delay_minutes=0,max_spend_per_hour=2e9,allocation_fraction=fraction) for action,fraction in [('buy_ust',.7),('liquidity',.3)]]
    c=replace(short(mode='counterfactual',policies=policies,funding_timing='early'),start='2022-05-08T03:00:00Z',end='2022-05-08T03:15:00Z')
    ctx=context(c); b=observed_start(ctx); b['ust_price']=.90
    budget=b['fund_usd'].sum()
    out=rescue(ctx,b)
    assert np.isclose(out['policy_spent'][0]/budget,.7)
    assert np.isclose(out['lp_committed'][1]/budget,.3)
    assert np.isclose(out['fund_spent'].sum(),budget)
    assert out['fund_usd'].sum()<.001
    invariants(ctx,out)
