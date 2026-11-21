"""Six ordered cadCAD blocks with an identical low-memory calibration runner.

The simulator never reads target prices, target withdrawals or target supplies.
Only initial observations, BTC prices, two seed-wallet actions, and reference
intervention windows are supplied to it. USD, UST and LUNA have explicit owners.
"""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import copy
import json
import math
import time
import hashlib
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit
from .config import ROOT, ScenarioConfig
from .data import initial_facts, build_population, seed_shocks, read_source, utc, GROUPS


def clone(book, arrays=()):
    out=book.copy()
    for key in arrays:
        out[key]=book[key].copy()
    out['events']=list(book['events'])
    return out


def event(b, kind, owner, amount, asset, **extra):
    if abs(amount)>1e-9:
        b['events'].append({'time':b['time'],'kind':kind,'owner':owner,'amount':float(amount),'asset':asset,**extra})


@lru_cache(maxsize=8)
def boundary_data(dt):
    _,wallets=seed_shocks(dt)
    tx=read_source('anchor_run/anchor_run_tx_cleaned.parquet')
    tx['time']=utc(tx.time)
    seed_tx=tx[(tx.sender.isin(wallets))&(tx.time>='2022-05-07T00:00:00Z')&(tx.time<'2022-05-08T00:00:00Z')].copy()
    seed_tx['signed']=np.where(seed_tx.action=='withdraw',seed_tx.ust_vol,-seed_tx.ust_vol)
    seed_tx['bucket']=seed_tx.time.dt.ceil(f'{dt}min')
    shocks=seed_tx.groupby(['bucket','sender']).signed.sum().unstack('sender').reindex(columns=wallets,fill_value=0).fillna(0)
    sources=json.loads((ROOT/'data'/'sources.json').read_text(encoding='utf-8'))
    btc=pd.read_parquet(ROOT/'data'/'external'/'btc_usdt_minute.parquet').set_index('time').btc_price
    return shocks,sources,btc


def context(config):
    config.validate()
    facts=initial_facts()
    agents, institution=build_population(config.n_depositors,config.seed)
    # Exact initial holdings of seed wallets are kept if they are sampled.
    amounts, wallets=seed_shocks(config.dt_minutes)
    agent_indices=[np.flatnonzero(agents.address.to_numpy()==w) for w in wallets]
    shocks,sources,btc=boundary_data(config.dt_minutes)
    start,end=pd.Timestamp('2022-05-06T00:15:00Z'),pd.Timestamp(config.end)
    index=pd.date_range(start,end+pd.Timedelta(days=config.stress_days),freq=f'{config.dt_minutes}min',inclusive='left')
    btc_aligned=btc.reindex(index,method='ffill')
    if btc_aligned.isna().any(): raise ValueError('BTC price is missing; run prepare first')
    # The stress tail holds the final observed BTC price; never imports future UST/LUNA.
    btc_aligned.loc[btc_aligned.index>=end]=float(btc.loc[btc.index<end].iloc[-1])
    rng=np.random.default_rng(config.seed)
    return {'config':config,'p':config.params,'facts':facts,'agents':agents,'institution':institution,'shocks':shocks,'wallets':wallets,'seed_indices':agent_indices,'index':index,'btc':btc_aligned.to_numpy(),'sources':sources,'rng':rng,'signals':np.empty((0,4))}


def initialize(ctx):
    f,p,c=ctx['facts'],ctx['p'],ctx['config']
    a=ctx['agents']
    deposits=(a.prerun_usd*a.weight).to_numpy(float)
    pocket=np.zeros(len(a))
    # Seed-wallet deposit legs are an explicit conditional boundary experiment.
    # Prefunding is inferred, not treated as a calibrated behavioral feature.
    for indices,wallet in zip(ctx['seed_indices'],ctx['wallets']):
        if len(indices): pocket[indices[0]]=float((-ctx['shocks'][wallet].clip(upper=0)).sum())
    market_ust=f['ust_supply']-f['anchor_cash']-f['loan_balance']-f['anchor_reserve']-pocket.sum()
    if market_ust<0: raise ValueError('Initial UST stocks exceed supply')
    source_limits=ctx['sources']['historical_resource_limits']
    return {'time':ctx['index'][0],'step':-1,'deposit':deposits,'wallet_ust':pocket,'realized_usd':np.zeros(len(a)),
        'queue':np.zeros(len(a)),'institution_deposit':ctx['institution'],'institution_wallet':0.,'institution_queue':0.,
        'institution_realized':0.,'arb_usd':np.full(c.n_arbitrageurs,p.arb_capital_usd/c.n_arbitrageurs),
        'arb_luna':np.zeros(c.n_arbitrageurs),'fund_usd':np.zeros(2),'fund_btc':np.zeros(2),
        'fund_ust':np.zeros(2),'fund_luna':np.zeros(2),'fund_spent':np.zeros(2),
        'locked_stable':source_limits['lfg_usdt']+source_limits['lfg_usdc'],'locked_btc':float(source_limits['lfg_btc_initial']),
        'btc_sold':0.,'tfl_added':0.,'btc_cash_created':0.,'fees_usd':0.,'external_cash':1e9,'external_ust':0.,
        'market_usd':p.market_cash_usd,'market_ust':market_ust,'market_luna':p.market_luna_inventory,
        'outside_luna':f['luna_supply']-p.market_luna_inventory,'fee_luna':0.,
        'anchor_cash':f['anchor_cash'],'loan_ust':f['loan_balance'],'loan_balance':f['loan_balance'],
        'anchor_reserve':f['anchor_reserve'],'ust_supply':f['ust_supply'],'luna_supply':f['luna_supply'],
        'ust_price':f['ust_price'],'luna_price':f['luna_price'],'oracle_luna':f['luna_price'],
        'ust_confidence':min(1.,f['luna_supply']*f['luna_price']/f['ust_supply']),
        'virtual_delta':0.,'native_fee':p.min_spread,'native_requested':0.,'native_served':0.,'native_total_requested':0.,'native_total_served':0.,
        'native_quiet_minutes':1440.,
        'withdraw_requested':0.,'withdraw_served':0.,'withdraw_total_requested':0.,'withdraw_total_served':0.,
        'net_ust_sale':0.,'net_luna_sale':0.,'new_ust_burn':0.,'new_luna_mint':0.,
        'policy_since':np.full(len(c.policies),-1,dtype=int),'policy_runs':np.zeros(len(c.policies),dtype=int),
        'active_policies':np.zeros(len(c.policies),dtype=bool),'policy_spent':np.zeros(len(c.policies)),
        'lp_committed':np.zeros(len(c.policies)),'withdraw_limit':math.inf,'pool_multiplier':1.,'recovery_multiplier':1.,
        'funding_done':np.zeros(len(ctx['sources']['funding_timing_intervals']),dtype=bool),
        'historical_buy_backlog':0.,'historical_luna_backlog':0.,'historical_requested_usd':0.,'historical_executed_usd':0.,
        'native_open':True,'events':[],'signals':np.empty((0,4)),
        'ust_error':0.,'luna_error':0.,'usd_error':0.,'claim_error':0.}


def observation(ctx,b):
    b=clone(b,['fund_usd','fund_btc','funding_done','policy_since','policy_runs','active_policies'])
    b['events']=[]
    b['step']+=1; b['time']=ctx['index'][b['step']]
    b['net_ust_sale']=0.; b['net_luna_sale']=0.; b['new_ust_burn']=0.; b['new_luna_mint']=0.
    b['withdraw_requested']=0.; b['withdraw_served']=0.; b['native_requested']=0.; b['native_served']=0.
    c,p=ctx['config'],ctx['p']
    for j,tranche in enumerate(ctx['sources']['funding_timing_intervals']):
        release=pd.Timestamp(tranche[c.funding_timing])
        if not b['funding_done'][j] and b['time']>=release:
            owner=0 if tranche['owner']=='LFG' else 1
            amount=float(tranche['amount'])
            if tranche['asset']=='btc':
                amount=min(amount,max(0,b['locked_btc']-313))
                b['locked_btc']-=amount; b['fund_btc'][owner]+=amount
            else:
                if owner==0: b['locked_stable']-=amount
                else: b['tfl_added']+=amount
                b['fund_usd'][owner]+=amount
            b['funding_done'][j]=True
            event(b,'funding_release',tranche['owner'],amount,tranche['asset'],uncertainty=tranche['basis'])
    b['withdraw_limit']=math.inf; b['pool_multiplier']=1.; b['recovery_multiplier']=1.
    if c.mode=='historical':
        # Reference capacity change is a dated approximation, not a claim of block-accurate execution.
        if b['time']>=pd.Timestamp('2022-05-11T12:00:00Z'): b['pool_multiplier']=4.
        b['native_open']=b['time']<pd.Timestamp('2022-05-13T02:00:00Z')
    else: b['native_open']=True
    for j,policy in enumerate(c.policies):
        condition=(b['time']>=pd.Timestamp(policy.start_time)) if policy.trigger=='time' else (b['ust_price']<policy.threshold and b['time']>=pd.Timestamp('2022-05-07T00:00:00Z'))
        b['policy_runs'][j]=b['policy_runs'][j]+1 if condition else 0
        if b['policy_since'][j]<0 and b['policy_runs'][j]>= (1 if policy.trigger=='time' else policy.trigger_steps):
            b['policy_since'][j]=b['step']
        age=(b['step']-b['policy_since'][j])*c.dt_minutes if b['policy_since'][j]>=0 else -1
        active=age>=policy.delay_minutes and age<policy.delay_minutes+policy.duration_hours*60
        b['active_policies'][j]=active and c.mode=='counterfactual'
        if b['active_policies'][j]:
            if policy.action=='native_swap':
                b['pool_multiplier']=policy.pool_multiplier; b['recovery_multiplier']=policy.recovery_multiplier
            if policy.action=='withdrawal_gate':
                b['withdraw_limit']=min(b['withdraw_limit'],total_deposits(b)*policy.withdrawal_fraction_per_day*c.dt_minutes/1440)
    return b


def total_deposits(b):
    return float(b['deposit'].sum()+b['institution_deposit'])


def raise_cash(ctx,b,need,allowed=(0,1)):
    p=ctx['p']; btc_price=float(ctx['btc'][b['step']])
    available=sum(b['fund_usd'][i] for i in allowed)
    remaining=max(need-available,0.)
    for owner in allowed:
        if remaining<=0: break
        qty=min(b['fund_btc'][owner],remaining/(btc_price*(1-p.btc_slippage-p.btc_fee)))
        gross=qty*btc_price; fee=gross*(p.btc_slippage+p.btc_fee); net=gross-fee
        b['fund_btc'][owner]-=qty; b['btc_sold']+=qty
        b['fund_usd'][owner]+=net; b['fees_usd']+=fee; b['btc_cash_created']+=gross
        remaining=max(0,remaining-net)
        event(b,'btc_liquidation',['LFG','TFL'][owner],qty,'BTC',gross_usd=gross,fee_usd=fee,net_usd=net)


def spend(ctx,b,need,allowed=(0,1),kind='rescue_buy',policy_index=-1,asset='UST'):
    raise_cash(ctx,b,max(need,0),allowed)
    remaining=max(need,0.); amounts=np.zeros(2)
    for owner in allowed:
        q=min(remaining,b['fund_usd'][owner]); b['fund_usd'][owner]-=q; b['fund_spent'][owner]+=q
        amounts[owner]=q; remaining-=q
    spent=float(amounts.sum())
    if spent<=0: return 0.
    fee=spent*ctx['p'].execution_fee if kind!='liquidity_commit' else 0.
    b['fees_usd']+=fee; b['market_usd']+=spent-fee
    if kind!='liquidity_commit':
        price=max(b['ust_price'] if asset=='UST' else b['luna_price'],1e-12)
        inventory=b['market_ust'] if asset=='UST' else b['market_luna']
        qty=(spent-fee)/price
        if qty>inventory+1e-3: raise AssertionError('Rescue bought more tokens than market inventory')
        if asset=='UST':
            b['fund_ust']+=amounts/spent*qty; b['market_ust']-=qty; b['net_ust_sale']-=qty
        else:
            b['fund_luna']+=amounts/spent*qty; b['market_luna']-=qty; b['net_luna_sale']-=qty
    for owner,q in enumerate(amounts):
        event(b,kind,['LFG','TFL'][owner],q,'USD',policy_index=policy_index,token=asset)
    return spent


def rescue(ctx,b):
    b=clone(b,['fund_usd','fund_btc','fund_ust','fund_luna','fund_spent','policy_spent','lp_committed'])
    c,p=ctx['config'],ctx['p']; dt=c.dt_minutes/1440
    if b['time']>=pd.Timestamp(c.end): return b  # No new support in the stress tail.
    if c.mode=='historical':
        day=b['time'].normalize()
        targets={8:686766346+49837261,9:321648208,10:764784725}
        # Gross trade intentions are clipped by actual resource caps. Working-capital
        # and Jump trading records are incomplete, so backlog is exposed in outputs.
        if day.month==5 and day.day in targets:
            add=targets[day.day]*dt; b['historical_buy_backlog']+=add; b['historical_requested_usd']+=add
        if day.month==5 and 8<=day.day<=11:
            b['historical_luna_backlog']+=268444270/4*dt
        limit=200e6*c.dt_minutes/60
        need=min(b['historical_buy_backlog'],limit,max(b['market_ust']*b['ust_price']/(1-p.execution_fee),0))
        depth=p.ust_depth_usd*max(b['luna_price']/ctx['facts']['luna_price'],.0001)**p.ust_depth_luna_beta
        need=min(need,max(0,depth*math.log(.999/max(b['ust_price'],1e-12))))
        if b['time']>=pd.Timestamp('2022-05-11T00:00:00Z'): need=0.
        used=spend(ctx,b,need); b['historical_buy_backlog']-=used; b['historical_executed_usd']+=used
        need=min(b['historical_luna_backlog'],limit,max(b['market_luna']*b['luna_price']/(1-p.execution_fee),0))
        luna_depth=p.luna_depth_usd/ctx['facts']['luna_price']*max(b['luna_supply']/ctx['facts']['luna_supply'],1)**p.luna_depth_growth
        need=min(need,luna_depth*b['luna_price']*.15)
        if b['time']>=pd.Timestamp('2022-05-12T00:00:00Z'): need=0.
        used=spend(ctx,b,need,asset='LUNA',kind='historical_luna_buy'); b['historical_luna_backlog']-=used
        return b
    if c.mode!='counterfactual': return b
    # Allocation fractions split the per-step funding pool, not an unlimited grant.
    budget=(b['fund_usd'].sum()+b['fund_btc'].sum()*ctx['btc'][b['step']]*(1-p.btc_slippage-p.btc_fee))
    for j,policy in enumerate(c.policies):
        if not b['active_policies'][j]: continue
        allowed=(0,1) if policy.funder=='both' else ((0,) if policy.funder=='LFG' else (1,))
        need=min(policy.max_spend_per_hour*c.dt_minutes/60,budget*policy.allocation_fraction)
        if policy.action=='buy_ust':
            # Only buy below the upper edge of the recovery band.
            need=min(need,max(b['market_ust']*b['ust_price']/(1-p.execution_fee),0)) if b['ust_price']<1.02 else 0
            effective_depth=p.ust_depth_usd*max(b['luna_price']/ctx['facts']['luna_price'],.0001)**p.ust_depth_luna_beta
            target_cost=max(0,effective_depth*math.log(1.001/max(b['ust_price'],1e-12)))
            used=spend(ctx,b,min(need,target_cost),allowed,policy_index=j)
            b['policy_spent'][j]+=used
        elif policy.action=='liquidity':
            used=spend(ctx,b,need,allowed,kind='liquidity_commit',policy_index=j)
            b['lp_committed'][j]+=used; b['policy_spent'][j]+=used
    return b


def decisions(ctx,b):
    b=clone(b,['queue','wallet_ust','deposit'])
    c,p,a=ctx['config'],ctx['p'],ctx['agents']; dt=c.dt_minutes
    history=b['signals']
    if len(history):
        lag=np.maximum(1,np.ceil(a.lag_minutes.to_numpy()/dt).astype(int))
        positions=np.maximum(0,len(history)-lag)
        observed=history[positions,:4].copy()
        window=max(1,60//dt)
        observed[:,1]=np.convolve(history[:,1],np.ones(window),mode='full')[:len(history)][positions]
        observed[:,2]=np.convolve(history[:,2],np.ones(window),mode='full')[:len(history)][positions]
        discount,outflow,luna_fall,queue_fraction=observed.T
    else:
        discount=np.zeros(len(a)); outflow=discount.copy(); luna_fall=discount.copy(); queue_fraction=discount.copy()
    eta=p.hazard_base+p.hazard_size*(a.log_size.to_numpy()-3)+p.hazard_discount*discount+p.hazard_outflow*outflow+p.hazard_luna*luna_fall+p.hazard_queue*queue_fraction
    probability=1-(1-expit(eta))**(dt/15)
    newly_requested=np.maximum(b['deposit']-b['queue'],0)*((ctx['rng'].random(len(a))<probability) if c.stochastic else probability)
    seed_mask=a.address.isin(ctx['wallets']).to_numpy()
    newly_requested[seed_mask]=0
    if b['time'] in ctx['shocks'].index:
        for indices,wallet in zip(ctx['seed_indices'],ctx['wallets']):
            amount=float(ctx['shocks'].loc[b['time'],wallet])
            if len(indices):
                i=indices[0]
                if amount>=0: newly_requested[i]=min(amount,max(b['deposit'][i]-b['queue'][i],0))
                else:
                    amount=min(-amount,b['wallet_ust'][i]); b['wallet_ust'][i]-=amount; b['deposit'][i]+=amount; b['anchor_cash']+=amount
                    event(b,'seed_deposit',wallet,amount,'UST')
    inst_prob=1-(1-expit(p.hazard_base+p.hazard_size*4+p.hazard_discount*max(0,1-b['ust_price'])+p.hazard_outflow*(history[-1,1] if len(history) else 0)))**(dt/15)
    inst_new=max(b['institution_deposit']-b['institution_queue'],0)*inst_prob
    b['queue']+=newly_requested; b['institution_queue']+=inst_new
    b['withdraw_requested']=float(newly_requested.sum()+inst_new)
    b['withdraw_total_requested']+=b['withdraw_requested']
    return b


def anchor(ctx,b):
    b=clone(b,['queue','deposit','wallet_ust'])
    c,p,f=ctx['config'],ctx['p'],ctx['facts']; dt=c.dt_minutes/1440
    # Loan principal repayment transfers borrower UST back into available Anchor cash.
    depeg=max(0,1-b['ust_price'])
    repayment=min(b['loan_ust'],b['loan_balance']*(0.01+depeg)/p.loan_repayment_days*dt)
    b['loan_ust']-=repayment; b['loan_balance']-=repayment; b['anchor_cash']+=repayment
    event(b,'loan_repayment','borrowers',repayment,'UST',recipient='Anchor')
    income=min(b['market_ust'],p.reserve_income_day*dt)
    b['market_ust']-=income; b['anchor_reserve']+=income
    event(b,'reserve_income','market',income,'UST',recipient='Anchor yield reserve')
    interest=min(b['anchor_reserve'],total_deposits(b)*f['deposit_apr']/365*dt)
    claims=total_deposits(b)
    if claims>0:
        b['deposit']+=b['deposit']/claims*interest
        b['institution_deposit']+=b['institution_deposit']/claims*interest
    b['anchor_reserve']-=interest; b['anchor_cash']+=interest
    event(b,'deposit_interest','Anchor yield reserve',interest,'UST',recipient='deposit claims')
    requested=float(b['queue'].sum()+b['institution_queue'])
    served=min(requested,b['anchor_cash'],b['withdraw_limit']) if b['native_open'] or c.mode!='historical' else 0.
    if requested>0:
        fraction=served/requested
        q=b['queue']*fraction; iq=b['institution_queue']*fraction
        b['queue']-=q; b['deposit']-=q; b['wallet_ust']+=q
        b['institution_queue']-=iq; b['institution_deposit']-=iq; b['institution_wallet']+=iq
        b['anchor_cash']-=served
    b['withdraw_served']=served; b['withdraw_total_served']+=served
    event(b,'anchor_withdrawal','depositors',served,'UST')
    # Re-deposit only an actual wallet balance; no fresh USD is conjured.
    if .98<=b['ust_price']<=1.02 and (b['signals'][-1,1] if len(b['signals']) else 0)<.02:
        q=b['wallet_ust']*min(1,p.redeposit_day*dt)
        b['wallet_ust']-=q; b['deposit']+=q; b['anchor_cash']+=float(q.sum())
        event(b,'redeposit','depositors',float(q.sum()),'UST',recipient='Anchor')
    return b


def markets(ctx,b):
    b=clone(b,['wallet_ust','realized_usd','arb_usd','arb_luna','fund_usd','fund_btc','fund_ust','fund_luna','fund_spent'])
    c,p,f=ctx['config'],ctx['p'],ctx['facts']; dt=c.dt_minutes/1440
    up,lp=max(b['ust_price'],1e-12),max(b['luna_price'],1e-12)
    # Token sellers receive finite market cash, with a sell queue retained in wallets.
    fraction=min(1,p.sell_fraction*c.dt_minutes/15)
    desired=b['wallet_ust']*fraction; institutional=b['institution_wallet']*fraction
    qty=float(desired.sum()+institutional)
    ratio=min(1,b['market_usd']/max(qty*up,1e-12))
    sold=desired*ratio; inst_sold=institutional*ratio; qty=float(sold.sum()+inst_sold)
    b['wallet_ust']-=sold; b['realized_usd']+=sold*up*(1-p.execution_fee)
    b['institution_wallet']-=inst_sold; b['institution_realized']+=inst_sold*up*(1-p.execution_fee)
    b['fees_usd']+=qty*up*p.execution_fee; b['market_usd']-=qty*up; b['market_ust']+=qty; b['net_ust_sale']+=qty
    event(b,'ust_sale','depositors',qty,'UST',price=up)
    # Finite outside investors buy from market inventory, never a price reset.
    demand=min(b['external_cash'],p.normal_demand_day*dt*max(0,1-up)*10)
    demand=min(demand,b['market_ust']*up)
    bought=demand/up
    b['external_cash']-=demand; b['market_usd']+=demand; b['market_ust']-=bought; b['external_ust']+=bought; b['net_ust_sale']-=bought
    event(b,'outside_ust_buy','outside investors',bought,'UST',cost_usd=demand)
    # Oracle is a lagged simulated price; do not import the realized LUNA price.
    oracle=b['oracle_luna']
    base=p.base_pool_usd*b['pool_multiplier']
    x=base+b['virtual_delta']; out_luna_usd=base*base/max(x,1)
    desired_arb=min(b['market_ust'],float(b['arb_usd'].sum())/up,p.arb_capacity_day*dt*b['pool_multiplier'])
    spread=max(p.min_spread,desired_arb/max(x+desired_arb,1))
    # Predicted liquidation price includes depth: agents do not arbitrage into a certain loss.
    native_discount=max(0,1-up-p.min_spread-p.execution_fee*2)
    profitable=native_discount>0 and b['native_open']
    # Solve the profit-maximizing size under the virtual-pool marginal quote.
    # Trying the full daily capacity at a tiny discount would be unprofitable.
    optimal=max(0,base*math.sqrt(lp*(1-p.execution_fee)/(max(oracle,1e-12)*up))-x)
    lp_support=sum(b['lp_committed'][j] for j in range(len(c.policies)) if b['active_policies'][j])
    quote_depth=p.ust_depth_usd*max(lp/f['luna_price'],.0001)**p.ust_depth_luna_beta+lp_support
    # Bound orders by their own expected UST price impact; a tiny market cannot
    # fill billions at the old quote and instantaneously recover the peg.
    buy_limit=max(0,quote_depth/up*math.log(max(.999/up,1)))*.8
    optimal=min(optimal,buy_limit)
    q=min(desired_arb,optimal) if profitable else 0.
    # Count only orders an agent would submit at a profitable quoted size.
    b['native_requested']=min(desired_arb,optimal) if native_discount>0 else 0.
    b['native_total_requested']+=b['native_requested']
    minted_value=out_luna_usd*q/max(x+q,1) if q>0 else 0.
    # virtual pool quote; fee is the spread from oracle face value, not a hard cash redemption.
    minted_gross=q/max(oracle,1e-12)
    delivered=min(minted_value,q*(1-p.min_spread))/max(oracle,1e-12)
    fee_luna=max(minted_gross-delivered,0.)
    if q>0 and delivered*lp*(1-p.execution_fee)<=q*up:
        q=0.; minted_gross=0.; delivered=0.; fee_luna=0.
    if q>0:
        capital=b['arb_usd'].sum(); weights=b['arb_usd']/capital
        b['arb_usd']-=weights*q*up; b['market_usd']+=q*up; b['market_ust']-=q
        b['arb_luna']+=weights*delivered; b['fee_luna']+=fee_luna
        b['ust_supply']-=q; b['luna_supply']+=minted_gross
        b['new_ust_burn']=q; b['new_luna_mint']=minted_gross; b['virtual_delta']+=q
        b['net_ust_sale']-=q; b['native_served']=q; b['native_total_served']+=q
        event(b,'native_burn','arbitrageurs',q,'UST',luna_minted=minted_gross,luna_delivered=delivered,fee_luna=fee_luna)
    b['native_fee']=fee_luna/minted_gross if minted_gross>0 else p.min_spread
    # Arbitrageurs hold unsold tokens if cash is unavailable.
    residual_active=not b['native_open'] or b['native_quiet_minutes']>=360
    residual_bid=p.luna_residual_bid_fraction*b['market_usd']/max(b['luna_supply'],1) if residual_active else 0.
    luna_budget=b['market_usd']*p.luna_residual_bid_fraction if lp<=residual_bid*1.01 else b['market_usd']
    luna_qty=float(b['arb_luna'].sum()); serve_ratio=min(1,luna_budget/max(luna_qty*lp,1e-12))
    luna_sold=b['arb_luna']*serve_ratio; luna_qty=float(luna_sold.sum())
    b['arb_luna']-=luna_sold; b['arb_usd']+=luna_sold*lp*(1-p.execution_fee)
    b['fees_usd']+=luna_qty*lp*p.execution_fee; b['market_usd']-=luna_qty*lp; b['market_luna']+=luna_qty
    b['net_luna_sale']+=luna_qty
    event(b,'luna_sale','arbitrageurs',luna_qty,'LUNA',price=lp)
    recovery=max(.01,p.recovery_minutes*b['recovery_multiplier'])
    b['virtual_delta']*=math.exp(-c.dt_minutes/recovery)
    lp_support=sum(b['lp_committed'][j] for j in range(len(c.policies)) if b['active_policies'][j])
    confidence_depth=max(b['luna_price']/f['luna_price'],.0001)**p.ust_depth_luna_beta
    depth_u=max(1,p.ust_depth_usd*confidence_depth+lp_support)
    # Bounded inverse demand curves: prices depend on net orders and endogenous depth.
    change_u=np.clip(-b['net_ust_sale']*up/depth_u,-4.,4.)
    depth_l_tokens=p.luna_depth_usd/f['luna_price']*max(b['luna_supply']/f['luna_supply'],1)**p.luna_depth_growth
    change_l=np.clip(-np.sign(b['net_luna_sale'])*math.log1p(abs(b['net_luna_sale'])/max(depth_l_tokens,1)),-6.,3.)
    btc_return=math.log(ctx['btc'][b['step']]/ctx['btc'][max(0,b['step']-1)])
    impact_price=lp*math.exp(change_l+p.luna_beta_btc*btc_return)
    # A residual funded bid represents willingness to allocate existing market USD
    # to LUNA. Its price falls with issuance and cash depletion; no money is added.
    b['native_quiet_minutes']=0. if q>1 else b['native_quiet_minutes']+c.dt_minutes
    residual_active=not b['native_open'] or b['native_quiet_minutes']>=360
    funded_bid=p.luna_residual_bid_fraction*b['market_usd']/max(b['luna_supply'],1) if residual_active else 0.
    b['luna_price']=float(np.clip(max(impact_price,funded_bid),1e-12,200.))
    # Confidence is a demand signal, not liquid collateral or external dollars.
    # Buyers discount UST when the perceived LUNA absorption capacity collapses.
    confidence=min(1.,b['luna_supply']*b['luna_price']/max(b['ust_supply'],1))
    confidence_change=p.ust_confidence_beta*math.log(max(confidence,1e-12)/max(b['ust_confidence'],1e-12))
    b['ust_price']=float(np.clip(up*math.exp(np.clip(change_u+confidence_change,-4.,4.)),1e-6,1.2))
    b['ust_confidence']=confidence
    # A 1-minute oracle lag is approximated within the coarser timestep.
    lag=min(1,p.oracle_lag_minutes/c.dt_minutes)
    b['oracle_luna']=lp*lag+b['luna_price']*(1-lag)
    return b


def invariants(ctx,b):
    ust=b['anchor_cash']+b['loan_ust']+b['anchor_reserve']+b['market_ust']+b['wallet_ust'].sum()+b['institution_wallet']+b['external_ust']+b['fund_ust'].sum()
    luna=b['outside_luna']+b['market_luna']+b['arb_luna'].sum()+b['fund_luna'].sum()+b['fee_luna']
    usd=b['market_usd']+b['realized_usd'].sum()+b['institution_realized']+b['arb_usd'].sum()+b['fund_usd'].sum()+b['external_cash']+b['fees_usd']+b['locked_stable']
    expected_usd=ctx['p'].market_cash_usd+ctx['p'].arb_capital_usd+1e9+49837261+b['tfl_added']+b['btc_cash_created']
    claim=total_deposits(b)-(b['anchor_cash']+b['loan_balance'])
    errors={'ust_error':ust-b['ust_supply'],'luna_error':luna-b['luna_supply'],'usd_error':usd-expected_usd,'claim_error':claim}
    for key,value in errors.items():
        if not np.isfinite(value): raise AssertionError(f'Non-finite {key}')
        reference=b['ust_supply'] if key=='ust_error' else (b['luna_supply'] if key=='luna_error' else expected_usd)
        if abs(value)>max(.1,reference*1e-9): raise AssertionError(f'{key}: {value}')
    if abs(b['locked_btc']+b['fund_btc'].sum()+b['btc_sold']-80394)>.001: raise AssertionError('BTC not conserved')
    for key in ['deposit','queue','wallet_ust','arb_usd','arb_luna','fund_usd','fund_btc','fund_ust','fund_luna']:
        if np.min(b[key],initial=0)<-.001: raise AssertionError(f'Negative {key}')
    for key in ['anchor_cash','loan_ust','market_ust','market_usd','anchor_reserve','institution_deposit','locked_btc','locked_stable','external_cash']:
        if b[key]<-.001: raise AssertionError(f'Negative {key}')
    if b['queue'].sum()>b['deposit'].sum()+.1: raise AssertionError('Queue exceeds claims')
    if b['btc_sold']>80081.001 or b['tfl_added']>613616889.001: raise AssertionError('Historical cap exceeded')
    return errors


def accounting(ctx,b):
    b=clone(b)
    b.update(invariants(ctx,b))
    old=b['signals']
    previous_price=old[-1,4] if old.shape[1:]==(5,) and len(old) else ctx['facts']['luna_price']
    recent=old[-max(1,60//ctx['config'].dt_minutes):,1].sum() if len(old) else 0
    current=b['withdraw_served']/max(ctx['facts']['anchor_deposits'],1)
    luna_fall=max(0,math.log(max(previous_price,1e-12)/max(b['luna_price'],1e-12)))
    queue_fraction=(b['queue'].sum()+b['institution_queue'])/max(total_deposits(b),1)
    signal=np.array([max(0,1-b['ust_price']),current,luna_fall,queue_fraction,b['luna_price']])
    # Column 1 is per-step outflow; aggregate one hour on observation for decisions.
    if old.shape[1:]==(4,): old=np.empty((0,5))
    b['signals']=np.vstack([old,signal])[-max(40,240//ctx['config'].dt_minutes):]
    return b


BLOCKS=[observation,rescue,decisions,anchor,markets,accounting]


def summarize(ctx,b):
    a=ctx['agents']; c=ctx['config']
    row={key:float(b[key]) for key in ['ust_price','luna_price','ust_supply','luna_supply','anchor_cash','anchor_reserve','loan_balance','withdraw_requested','withdraw_served','withdraw_total_requested','withdraw_total_served','native_requested','native_served','native_total_requested','native_total_served','native_fee','market_usd','market_ust','btc_sold','tfl_added','fees_usd','ust_error','luna_error','usd_error','claim_error','historical_requested_usd','historical_executed_usd']}
    row.update(time=b['time'],anchor_deposits=total_deposits(b),withdraw_queue=float(b['queue'].sum()+b['institution_queue']),ust_sell_queue=float(b['wallet_ust'].sum()+b['institution_wallet']),native_open=bool(b['native_open']),support_spent=float(b['fund_spent'].sum()),support_remaining=float(b['fund_usd'].sum()+b['fund_btc'].sum()*ctx['btc'][b['step']]*(1-ctx['p'].btc_slippage-ctx['p'].btc_fee)),lfg_btc_remaining=float(b['locked_btc']+b['fund_btc'][0]),lfg_spent=float(b['fund_spent'][0]),tfl_spent=float(b['fund_spent'][1]),rescuer_ust=float(b['fund_ust'].sum()),rescuer_luna=float(b['fund_luna'].sum()),active_policies=int(b['active_policies'].sum()))
    total_initial=float((a.prerun_usd*a.weight).sum())
    wealth=float(b['realized_usd'].sum()+(b['wallet_ust'].sum()+b['deposit'].sum())*b['ust_price'])
    row['depositor_loss_fraction']=1-wealth/max(total_initial,1)
    for group in range(6):
        mask=a.group.to_numpy()==group
        init=float((a.prerun_usd*a.weight).to_numpy()[mask].sum())
        row[f'group_{group}_remaining']=float(b['deposit'][mask].sum()/max(init,1))
    return row


def simulate(config=None, engine='cadcad', keep_ledger=True):
    config=config or ScenarioConfig(); ctx=context(config)
    start=time.perf_counter(); initial=initialize(ctx); rows=[]; ledger=[]
    if engine=='fast':
        b=initial
        for _ in ctx['index']:
            for block in BLOCKS: b=block(ctx,b)
            rows.append(summarize(ctx,b))
            if keep_ledger: ledger.extend(b['events'])
    elif engine=='cadcad':
        from cadCAD.configuration import Experiment
        from cadCAD.configuration.utils import config_sim
        from cadCAD.engine import Executor, ExecutionContext, ExecutionMode
        def make_policy(block):
            def policy(params,substep,history,state):
                return {'next_book':block(params['context'],state['book'])}
            return policy
        def update(params,substep,history,state,signals):
            return 'book',signals['next_book']
        blocks=[{'policies':{fn.__name__:make_policy(fn)},'variables':{'book':update}} for fn in BLOCKS]
        experiment=Experiment()
        experiment.append_model(initial_state={'book':initial},partial_state_update_blocks=blocks,sim_configs=config_sim({'N':1,'T':range(len(ctx['index'])),'M':{'context':[ctx]}}))
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            records,_,_=Executor(exec_context=ExecutionContext(context=ExecutionMode().single_mode),configs=experiment.configs).execute()
        last=None
        for record in records:
            if record['substep']==len(BLOCKS):
                last=record['book']; rows.append(summarize(ctx,last))
                if keep_ledger: ledger.extend(last['events'])
        b=last
        del records
    else: raise ValueError('engine must be cadcad or fast')
    trajectory=pd.DataFrame(rows).set_index('time').loc[pd.Timestamp(config.start):]
    from .metrics import evaluate
    metrics=evaluate(trajectory,config)
    metrics['runtime_seconds']=time.perf_counter()-start
    metrics['engine']=engine; metrics['seed']=config.seed
    metrics['engine_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    ledger=pd.DataFrame(ledger)
    if len(ledger): ledger=ledger[ledger.time>=pd.Timestamp(config.start)]
    return trajectory,metrics,ledger
