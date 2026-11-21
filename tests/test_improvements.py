"""Regression checks for errors that motivated the v3 fidelity work."""
from dataclasses import replace
import json
import numpy as np
import pandas as pd
from luna_sim.config import ROOT, ScenarioConfig, ModelParams, PolicyConfig
from luna_sim.engine import (
    context, initialize, observation, anchor, rescue, markets, invariants,
    continuous_sell_fraction, native_quote, vwap_proceeds, vwap_fill,
    native_delivered_and_derivative, native_vwap_profit, native_vwap_optimum,
    _market_minute,
)
from luna_sim.data import load_targets, read_source, utc
from luna_sim.calibrate import (CalibrationObjective, pack, unpack, parameter_sha256,
                               SEARCH, hybrid_initial_population, bounded_initial_simplex)
from luna_sim.improvements import parameter_hash
from luna_sim.metrics import evaluate


def at_time(timestamp,**kwargs):
    c=ScenarioConfig(start=timestamp,end=(pd.Timestamp(timestamp)+pd.Timedelta(minutes=15)).isoformat(),n_depositors=100,stochastic=False,**kwargs)
    ctx=context(c); book=initialize(ctx)
    book['step']=int(ctx['index'].get_indexer([pd.Timestamp(timestamp)])[0])-1
    return ctx,observation(ctx,book)


def test_continuous_selling_is_independent_of_partition():
    full=1-continuous_sell_fraction(.92,15)
    split=(1-continuous_sell_fraction(.92,1))**15
    assert np.isclose(full,split,atol=1e-14)
    assert continuous_sell_fraction(.92,0)==0


def test_native_fee_owner_and_pool_congestion():
    gross,delivered,fee=native_quote(50e6,0,5e6,10,.005)
    assert np.isclose(gross,delivered+fee)
    _,congested,congested_fee=native_quote(50e6,20e6,5e6,10,.005)
    assert congested<delivered and congested_fee>fee
    assert native_quote(50e6,0,0,10,.005)==(0,0,0)


def test_vwap_fill_integrates_declining_price_and_retains_cash_limited_tokens():
    quantity,price,depth=100.,10.,50.
    gross=vwap_proceeds(quantity,price,depth)
    assert price/(1+quantity/depth)<gross/quantity<price
    epsilon=.001
    marginal=(vwap_proceeds(quantity+epsilon,price,depth)-vwap_proceeds(quantity-epsilon,price,depth))/(2*epsilon)
    assert np.isclose(marginal,price/(1+quantity/depth),rtol=1e-9)
    filled,paid=vwap_fill(quantity,price,depth,30.)
    assert 0<filled<quantity and paid<=30.
    assert np.isclose(vwap_proceeds(filled,price,depth),paid,atol=1e-12)
    assert vwap_fill(quantity,price,depth,1000.)==(quantity,gross)
    assert vwap_fill(quantity,price,depth,0.)==(0.,0.)


def test_native_marginal_quote_matches_delivered_tokens_in_both_spread_regimes():
    for q,delta in [(1e4,0.),(5e6,0.),(5e6,20e6)]:
        delivered,derivative=native_delivered_and_derivative(q,50e6,delta,10.,.005)
        assert np.isclose(delivered,native_quote(50e6,delta,q,10.,.005)[1])
        epsilon=q*1e-5
        upper=native_quote(50e6,delta,q+epsilon,10.,.005)[1]
        lower=native_quote(50e6,delta,q-epsilon,10.,.005)[1]
        assert np.isclose(derivative,(upper-lower)/(2*epsilon),rtol=1e-8)


def test_vwap_optimum_keeps_small_profitable_orders_in_large_search_interval():
    # Twelve midpoint iterations formerly returned 87,598 UST at a $6,023
    # loss, discarding a valid order of roughly 745 UST at a $7.15 profit.
    args=(584493992.7688059,1035953820.8918883,.0037306602696356187,.005,
          .08017309568998285,.004224520916605052,68677.85576203617,
          31423.37251012906,828846315077.75,.001)
    limit=717601268.6324173
    q=native_vwap_optimum(limit,*args)
    assert 740<q<750 and native_vwap_profit(q,*args)>7.15
    nearby=[native_vwap_profit(max(0.,q+offset),*args) for offset in [-10.,10.]]
    assert native_vwap_profit(q,*args)>max(nearby)
    assert native_vwap_optimum(limit,*args[:-2],0.,args[-1])==0.


def test_vwap_optimum_respects_existing_inventory_and_cash_profit_cap():
    args=(50e6,0.,10.,.005,.6,10.,1e6,0.,1e6,.001)
    limit=1e7
    q=native_vwap_optimum(limit,*args)
    profit=native_vwap_profit(q,*args)
    assert profit>0 and 0<q<limit
    alternatives=np.linspace(0.,limit,101)
    assert profit>=max(native_vwap_profit(other,*args) for other in alternatives)-1e-6
    # Old unsold tokens consume buyer cash before incremental native receipts.
    blocked=(*args[:7],1e6,*args[8:])
    assert vwap_proceeds(blocked[7],blocked[5],blocked[6])>blocked[8]
    assert native_vwap_optimum(limit,*blocked)==0.


def test_native_vwap_ledger_uses_frozen_depth_and_conserves_all_three_assets():
    ctx,book=at_time('2022-05-08T12:00:00Z')
    book['ust_price']=.8
    opening_supply=book['luna_supply']
    p,f=ctx['p'],ctx['facts']
    depth=p.luna_depth_usd/f['luna_price']*max(opening_supply/f['luna_supply'],1)**p.luna_depth_growth
    _market_minute(ctx,book,1.,0.,0.,0.,0.)
    sales=[e for e in book['events'] if e['kind']=='luna_sale']
    assert len(sales)==1 and book['new_luna_mint']>0
    sale=sales[0]
    assert sale['liquidation_depth']==depth
    assert sale['price']<sale['opening_price']
    assert np.isclose(sale['gross_usd'],vwap_proceeds(sale['amount'],sale['opening_price'],depth))
    assert np.isclose(book['luna_price'],sale['opening_price']/(1+sale['amount']/depth))
    invariants(ctx,book)


def test_luna_execution_keeps_opening_residual_cash_restriction():
    ctx,book=at_time('2022-05-08T12:00:00Z')
    ctx['p']=replace(ctx['p'],luna_depth_usd=1e15,normal_demand_day=0.)
    p=ctx['p']
    book['native_open']=False
    book['ust_price']=.8
    book['luna_price']=1.009*p.luna_residual_bid_fraction*book['market_usd']/book['luna_supply']
    # Move existing owned LUNA to an arbitrageur, with no mint or external cash.
    held=book['outside_luna']+book['market_luna']
    book['arb_luna'][0]=held
    book['outside_luna']=0.; book['market_luna']=0.
    book['market_ust']+=float(book['wallet_ust'].sum())
    book['wallet_ust'][:]=0.
    initial_cash=book['market_usd']
    _market_minute(ctx,book,1.,0.,0.,0.,0.)
    assert book['market_usd']>=initial_cash*(1-p.luna_residual_bid_fraction)-.001
    assert book['arb_luna'].sum()>0
    invariants(ctx,book)


def test_anchor_can_withdraw_after_chain_restart_without_native_mint():
    ctx,book=at_time('2022-05-13T11:30:00Z')
    assert book['chain_open'] and book['anchor_open'] and not book['native_open']
    book['queue']=book['deposit']*.01
    out=anchor(ctx,book)
    assert out['withdraw_served']>0 and out['queue'].sum()<book['queue'].sum()
    invariant_errors=invariants(ctx,out)
    assert max(map(abs,invariant_errors.values()))<.01


def test_halt_retains_withdrawal_claims_until_restart():
    ctx,book=at_time('2022-05-13T08:00:00Z')
    book['queue']=book['deposit']*.01
    before=book['queue'].copy()
    out=anchor(ctx,book)
    assert not book['chain_open'] and not book['anchor_open']
    assert out['withdraw_served']==0
    np.testing.assert_array_equal(out['queue'],before)
    invariants(ctx,out)


def test_later_deposits_and_interest_do_not_restore_initial_principal():
    ctx,book=at_time('2022-05-08T12:00:00Z')
    initial=book['initial_principal'].copy()
    book['queue']=book['deposit']*.5
    out=anchor(ctx,book)
    np.testing.assert_allclose(out['initial_principal'],initial*.5,rtol=1e-12)
    # The holder sends part of the withdrawn balance back to Anchor. Claims
    # rise, but the initial-principal cohort has already exited once.
    transfer=out['wallet_ust']*.1
    out['wallet_ust']-=transfer
    out['deposit']+=transfer
    out['anchor_cash']+=float(transfer.sum())
    again=anchor(ctx,out)
    np.testing.assert_allclose(again['initial_principal'],initial*.5,rtol=1e-12)
    assert (again['deposit']>again['initial_principal']).all()
    invariants(ctx,again)


def test_market_substeps_aggregate_actual_burns_and_conserve_assets():
    ctx,book=at_time('2022-05-08T12:00:00Z')
    book['ust_price']=.8
    ust_before,luna_before=book['ust_supply'],book['luna_supply']
    out=markets(ctx,book)
    burns=[e for e in out['events'] if e['kind']=='native_burn']
    assert len(burns)>1
    assert np.isclose(sum(e['amount'] for e in burns),out['native_served'])
    assert np.isclose(sum(e['luna_minted'] for e in burns),out['new_luna_mint'])
    assert np.isclose(ust_before-out['ust_supply'],out['new_ust_burn'])
    assert np.isclose(out['luna_supply']-luna_before,out['new_luna_mint'])
    weighted_fee=sum(e['fee_luna'] for e in burns)/sum(e['luna_minted'] for e in burns)
    assert np.isclose(out['native_fee'],weighted_fee)
    invariants(ctx,out)


def test_substeps_apply_btc_market_return_once():
    ctx,book=at_time('2022-05-06T01:00:00Z')
    ctx['p']=replace(ctx['p'],normal_demand_day=0,luna_residual_bid_fraction=0)
    ctx['btc'][book['step']-1]=100
    ctx['btc'][book['step']]=110
    old=book['luna_price']
    out=markets(ctx,book)
    assert out['native_served']==0
    assert np.isclose(out['luna_price'],old*1.1**ctx['p'].luna_beta_btc,rtol=1e-10)


def test_btc_budget_never_precedes_evidenced_transfer():
    sources=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))
    tranches=[t for t in sources['funding_timing_intervals'] if t['asset']=='btc']
    assert sum(t['amount'] for t in tranches)==80081
    assert pd.Timestamp(min(t['early'] for t in tranches))==pd.Timestamp('2022-05-09T03:45:00Z')
    ctx,before=at_time('2022-05-09T03:30:00Z')
    assert before['fund_btc'].sum()==0
    _,at=at_time('2022-05-09T03:45:00Z',funding_timing='early')
    assert at['fund_btc'].sum()==22189


def test_supply_end_of_hour_is_not_available_at_bucket_start():
    raw=read_source('native_swaps/luna_total_supply_run.parquet')
    raw.index=utc(raw.index)
    target=load_targets()
    assert target.loc['2022-05-13T01:00:00Z','luna_supply']==raw.loc['2022-05-13T00:00:00Z','luna_supply']
    assert target.loc['2022-05-13T02:00:00Z','luna_supply']==raw.loc['2022-05-13T01:00:00Z','luna_supply']


def synthetic_objective(onset_lag_hours):
    index=pd.date_range('2022-05-06T00:15:00Z','2022-05-11T00:00:00Z',freq='15min',inclusive='left')
    target=pd.DataFrame({'ust_price':np.where(index<pd.Timestamp('2022-05-07T00:00:00Z'),1.,.5),
                         'luna_price':10.,'luna_supply':1e9,'anchor_deposits':10e9,
                         'native_ust':0.,'native_fee':np.nan},index=index)
    target.attrs['initial_deposits']=10e9
    groups=pd.DataFrame(1.,index=index,columns=range(6))
    model=target.drop(columns=['native_ust']).copy()
    model['ust_price']=np.where(index<pd.Timestamp('2022-05-07T00:00:00Z')+pd.Timedelta(hours=onset_lag_hours),1.,.5)
    model['native_served']=0.
    for i in range(6): model[f'group_{i}_remaining']=1.
    objective=CalibrationObjective(ScenarioConfig(stochastic=False,end='2022-05-11T00:00:00Z'),target,groups,ModelParams())
    return objective.components(model)


def test_onset_loss_matches_six_hour_gate_and_has_no_weak_cap():
    assert synthetic_objective(0)['loss']==0
    assert np.isclose(synthetic_objective(6)['components']['onset'],2.)
    assert np.isclose(synthetic_objective(47)['components']['onset'],2*(47/6)**2)
    assert 'post_may11' not in synthetic_objective(6)['phase_losses']


def test_named_parameter_search_round_trip():
    p=ModelParams()
    actual=unpack(pack(p),p)
    assert np.isclose(actual.ust_depth_usd,p.ust_depth_usd)
    assert np.isclose(actual.luna_depth_usd,p.luna_depth_usd)
    assert np.isclose(actual.arb_capacity_day,p.arb_capacity_day)
    assert actual.hazard_base==p.hazard_base


def test_parameter_proof_matches_calibration_writer():
    assert parameter_hash(ModelParams())==parameter_sha256(ModelParams())


def test_optimizer_starts_are_reproducible_bounded_and_not_degenerate():
    lower=np.array([lo for _,lo,_ in SEARCH]); upper=np.array([hi for _,_,hi in SEARCH])
    for start in [lower,upper,(lower+upper)/2]:
        population=hybrid_initial_population(start,seed=42)
        np.testing.assert_array_equal(population,hybrid_initial_population(start,seed=42))
        np.testing.assert_array_equal(population[0],start)
        assert (population>=lower).all() and (population<=upper).all()
        assert not np.array_equal(population,hybrid_initial_population(start,seed=43))
        simplex=bounded_initial_simplex(start)
        assert (simplex>=lower).all() and (simplex<=upper).all()
        assert np.linalg.matrix_rank(simplex[1:]-simplex[0])==len(SEARCH)


def test_buy_controller_accounts_for_committed_active_liquidity():
    policies=[PolicyConfig('buy_ust',max_spend_per_hour=200e6),PolicyConfig('liquidity')]
    ctx,book=at_time('2022-05-09T12:00:00Z',mode='counterfactual',policies=policies)
    ctx['p']=replace(ctx['p'],ust_depth_usd=1e6)
    book['ust_price']=.9
    book['active_policies'][:]=True
    book['fund_usd'][0]=50e6
    book['fund_btc'][:]=0.
    no_lp=rescue(ctx,book)['policy_spent'][0]
    book['lp_committed'][1]=20e6
    with_lp=rescue(ctx,book)['policy_spent'][0]
    assert with_lp>no_lp*10


def test_idle_new_orders_do_not_hide_unserved_legacy_claims():
    index=pd.date_range('2022-05-08T00:00:00Z','2022-05-23T00:00:00Z',freq='15min',inclusive='left')
    columns=['withdraw_requested','withdraw_served','native_requested','native_served','withdraw_queue','ust_sell_queue','support_spent','btc_sold','tfl_added','depositor_loss_fraction','ust_error','luna_error','usd_error','claim_error','historical_requested_usd','historical_executed_usd']
    trajectory=pd.DataFrame(0.,index=index,columns=columns)
    for key in ['ust_price','luna_price','luna_supply','native_open','anchor_open','active_policies']: trajectory[key]=1.
    trajectory['anchor_deposits']=14e9
    trajectory['withdraw_queue']=14e9
    trajectory['support_remaining']=100.
    config=ScenarioConfig(mode='counterfactual',stress_days=7)
    result=evaluate(trajectory,config)
    assert not result['rescued'] and not result['stress_tail_verified']
    assert result['operational_hours_longest']==0 and result['withdraw_service_ratio']==0
    trajectory['withdraw_queue']=0
    trajectory['anchor_open']=False
    assert not evaluate(trajectory,config)['rescued']
    trajectory['anchor_open']=True
    idle=evaluate(trajectory,config)
    assert idle['rescued'] and idle['native_service_ratio']==1.
