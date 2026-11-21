"""Offline-first inputs. Targets and simulator inputs deliberately live apart."""
from pathlib import Path
from io import BytesIO
import hashlib
import json
import zipfile
from functools import lru_cache
import numpy as np
import pandas as pd
import requests
from .config import ROOT, DEFAULT_SOURCE

GROUPS = ["<1K", "1K–10K", "10K–100K", "100K–1M", "1M–10M", ">10M"]
BINS = [-np.inf, 1e3, 1e4, 1e5, 1e6, 1e7, np.inf]


def utc(values):
    return pd.to_datetime(values, utc=True)


def read_source(relative, source=DEFAULT_SOURCE):
    return pd.read_parquet(Path(source) / "data" / relative)


def fetch_external():
    directory = ROOT / "data" / "external"
    directory.mkdir(parents=True, exist_ok=True)
    sources = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    btc_path = directory / "btc_usdt_minute.parquet"
    if not btc_path.exists():
        response = requests.get(sources["btc"], timeout=90)
        response.raise_for_status()
        payload = response.content
        expected = requests.get(sources["btc_checksum"], timeout=30)
        expected.raise_for_status()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected.text.split()[0]:
            raise ValueError("BTC archive checksum mismatch")
        with zipfile.ZipFile(BytesIO(payload)) as z:
            raw = pd.read_csv(z.open(z.namelist()[0]), header=None)
        df = pd.DataFrame({"time":pd.to_datetime(raw[0], unit="ms", utc=True), "btc_price":raw[4].astype(float), "btc_volume":raw[5].astype(float)})
        df.to_parquet(btc_path, index=False)
        (directory / "btc_metadata.json").write_text(json.dumps({"source":sources["btc"], "sha256":digest, "quote":"USDT, modeled at 1 USD; basis risk excluded", "rows":len(df)}, indent=2), encoding="utf-8")
    audit_path = directory / "LFG-Audit-2022-11-14.pdf"
    if not audit_path.exists():
        response = requests.get(sources["audit"], timeout=60)
        response.raise_for_status()
        audit_path.write_bytes(response.content)
    from pypdf import PdfReader
    extracted = "\n".join(f"\n--- PDF page {i+1} ---\n" + (p.extract_text() or "") for i,p in enumerate(PdfReader(audit_path).pages))
    (directory / "lfg_audit.txt").write_text(extracted, encoding="utf-8")
    if "613,616,889" not in extracted or "80,394" not in extracted:
        raise ValueError("Audit evidence does not match configured resource caps")


@lru_cache(maxsize=8)
def load_targets(dt=15, source=DEFAULT_SOURCE):
    index = pd.date_range("2022-05-06T00:15:00Z", "2022-05-16T00:00:00Z", freq=f"{dt}min", inclusive="left")
    result = pd.DataFrame(index=index)
    for fn,col in [("prices/ust_price_may2022.parquet","ust_price"),("prices/luna_price_may2022.parquet","luna_price")]:
        d = read_source(fn,source)
        # These are evaluation targets, not values consumed by the model.
        s = d.assign(time=utc(d.time)).set_index("time")[col].sort_index()
        result[col] = s.reindex(index, method="ffill")
    d = read_source("anchor_run/epoch_state_fig10.parquet",source)
    s = d.assign(time=utc(d.time_utc)).set_index("time").deposit_b_ust * 1e9
    result["anchor_deposits"] = s.reindex(index, method="ffill")
    d = read_source("native_swaps/luna_total_supply_run.parquet",source)
    d.index = utc(d.index)
    result["luna_supply"] = d.luna_supply.reindex(index,method="ffill")
    tx = read_source("anchor_run/anchor_run_tx_cleaned.parquet",source)
    tx["time"] = utc(tx.time)
    for action in ["withdraw","deposit"]:
        s = tx.loc[tx.action==action].set_index("time").ust_vol.resample(f"{dt}min", label="right",closed="right").sum()
        result[f"observed_{action}"] = s.reindex(index,fill_value=0)
    swap = read_source("native_swaps/ust_luna_swaps_run.parquet",source)
    swap["time"] = utc(swap.time)
    swap = swap[(swap.time>=index[0])&(swap.time<=index[-1])].set_index("time")
    agg = swap.resample(f"{dt}min", label="right",closed="right").sum(numeric_only=True)
    result["native_ust"] = agg.offer_amount.reindex(index,fill_value=0)
    result["native_fee"] = (agg.fee_amount/(agg.swap_amount+agg.fee_amount)).reindex(index)
    return result


@lru_cache(maxsize=4)
def initial_facts(source=DEFAULT_SOURCE):
    start = pd.Timestamp("2022-05-06T00:15:00Z")
    epoch = read_source("anchor_run/epoch_state_fig10.parquet",source)
    epoch["t"] = utc(epoch.time_utc)
    row = epoch.loc[epoch.t<=start].iloc[-1]
    ads = read_source("anchor/Anchor_daily_stats.parquet",source)
    ads.index = utc(ads.index)
    ads = ads.loc[ads.index<start.normalize()].iloc[-1]
    global_state = read_source("anchor/Anchor_global_stats_fullnode.parquet",source)
    global_state.index=utc(global_state.index)
    g=global_state.loc[global_state.index<=start].iloc[-1]
    balances=read_source("daily_balances/columbus-5-lunaust-supply-breakdown-fullnode.parquet",source)
    balances["date"]=utc(balances.date)
    balances=balances[balances.date==pd.Timestamp("2022-05-05T00:00:00Z")]
    dep=float(row.deposit_b_ust*1e9)
    loan=float(g.total_liabilities/1e6)
    facts={"anchor_deposits":dep,"anchor_cash":max(dep-loan,0),"loan_balance":loan,"anchor_reserve":float(g.prev_interest_buffer/1e6),"deposit_apr":float(ads['deposit APR']),"borrow_apr":float(ads['borrow APR']),"aust_rate":float(row.exchange_rate),"ust_supply":float(balances.loc[balances.denom.isin(['UST','uusd'])].balance.sum())}
    for fn,col in [('prices/ust_price_may2022.parquet','ust_price'),('prices/luna_price_may2022.parquet','luna_price')]:
        d=read_source(fn,source); d['time']=utc(d.time)
        facts[col]=float(d.loc[d.time<=start].iloc[-1][col])
    d=read_source('native_swaps/luna_total_supply_run.parquet',source); d.index=utc(d.index)
    facts['luna_supply']=float(d.loc[d.index<=start].iloc[-1].luna_supply)
    return facts


@lru_cache(maxsize=40)
def build_population(n=1000, seed=42, source=DEFAULT_SOURCE):
    size=read_source('loss/depositor_prerun_size.parquet',source)[['address','prerun_usd','prerun_aust']]
    # full_maxusd and realized losses are never features.
    size=size.loc[(size.prerun_usd>0)&(size.prerun_aust>0)].copy()
    excluded=set(read_source('labels/interdm_addresses.parquet',source).address)
    retail=size.loc[~size.address.isin(excluded)].copy()
    retail['group']=pd.cut(retail.prerun_usd,BINS,labels=False,right=False).astype(int)
    top=retail.nlargest(20,'prerun_usd').copy()
    rest=retail.loc[~retail.address.isin(top.address)]
    rng=np.random.default_rng(seed)
    rows=[top.assign(weight=1.0)]
    counts=rest.groupby('group').size().reindex(range(6),fill_value=0)
    allocations=np.full(6,(n-20)//6,dtype=int); allocations[:(n-20)%6]+=1
    for group,k in enumerate(allocations):
        candidates=rest.loc[rest.group==group]
        if candidates.empty: continue
        picked=candidates.iloc[rng.integers(0,len(candidates),size=k)].copy()
        picked['weight']=len(candidates)/k
        target=candidates.prerun_usd.sum()
        picked['prerun_usd']*=target/(picked.prerun_usd*picked.weight).sum()
        rows.append(picked)
    agents=pd.concat(rows,ignore_index=True)
    # Reconcile all claims, including intermediaries, without inflating retail counts.
    if len(agents)<n:
        missing=n-len(agents)
        fill=agents.tail(1).loc[agents.tail(1).index.repeat(missing)].copy()
        fill['weight']=0.0; agents=pd.concat([agents,fill],ignore_index=True)
    facts=initial_facts(source)
    represented=(agents.prerun_usd*agents.weight).sum()
    institutional=max(0.,facts['anchor_deposits']-represented)
    if represented>facts['anchor_deposits']:
        agents['prerun_usd']*=facts['anchor_deposits']/represented
    agents['log_size']=np.log10(agents.prerun_usd.clip(lower=1))
    agents['lag_minutes']=np.where(agents.group>=4,15,np.where(agents.group>=2,60,120))
    # Pre-run sophistication modifies observation delays; unavailable features use size only.
    features=read_source('loss/anchor_loss_panel.parquet',source)[['address','log_volume_adj','cex_degree','used_bridge','log_age_months']]
    features=features.drop_duplicates('address').set_index('address')
    score=(features-features.mean())/features.std().replace(0,1)
    score=score.fillna(0).sum(axis=1)
    mapped=agents.address.map(score).fillna(0).to_numpy()
    agents['lag_minutes']=np.where(mapped>score.quantile(.75),15,agents.lag_minutes)
    return agents, institutional


@lru_cache(maxsize=8)
def seed_shocks(dt=15,source=DEFAULT_SOURCE):
    tx=read_source('anchor_run/anchor_run_tx_cleaned.parquet',source)
    tx['time']=utc(tx.time)
    day=tx[(tx.time>='2022-05-07T00:00:00Z')&(tx.time<'2022-05-08T00:00:00Z')].copy()
    day['signed']=np.where(day.action=='withdraw',day.ust_vol,-day.ust_vol)
    wallets=day.groupby('sender').signed.sum().nlargest(2).index.tolist()
    event=day.loc[day.sender.isin(wallets)&(day.action=='withdraw')].set_index('time').ust_vol
    amounts=event.resample(f'{dt}min',label='right',closed='right').sum()
    return amounts, wallets


@lru_cache(maxsize=8)
def group_targets(dt=15,source=DEFAULT_SOURCE):
    size=read_source('loss/depositor_prerun_size.parquet',source)[['address','prerun_usd']]
    size=size[size.prerun_usd>0].copy()
    excluded=set(read_source('labels/interdm_addresses.parquet',source).address)
    size=size[~size.address.isin(excluded)]
    size['group']=pd.cut(size.prerun_usd,BINS,labels=False,right=False).astype(int)
    tx=read_source('anchor_run/anchor_run_tx_cleaned.parquet',source).merge(size[['address','group','prerun_usd']],left_on='sender',right_on='address',how='inner')
    tx=tx[tx.action=='withdraw'].copy()
    tx['time']=utc(tx.time)
    tx=tx.sort_values('time')
    withdrawn=tx.groupby('sender').ust_vol.cumsum()
    clipped=np.minimum(withdrawn,tx.prerun_usd)
    previous=pd.Series(clipped,index=tx.index).groupby(tx.sender).shift().fillna(0)
    tx['initial_principal_exit']=clipped-previous
    tx['time']=tx.time.dt.ceil(f'{dt}min')
    flow=-tx.groupby(['time','group']).initial_principal_exit.sum().unstack('group').reindex(columns=range(6),fill_value=0).fillna(0)
    # FIFO survival of initial principal, not net balances inflated by later deposits.
    initial=size.groupby('group').prerun_usd.sum().reindex(range(6),fill_value=0)
    index=load_targets(dt,source).index
    flow=flow.reindex(index,fill_value=0).cumsum()
    return ((flow+initial)/initial.replace(0,np.nan)).clip(lower=0)


def prepare(source=DEFAULT_SOURCE):
    fetch_external()
    directory=ROOT/'data'/'processed'; directory.mkdir(parents=True,exist_ok=True)
    targets=load_targets(15,source); targets.to_parquet(directory/'historical_15min.parquet')
    group_targets(15,source).to_parquet(directory/'groups_15min.parquet')
    facts=initial_facts(source)
    (directory/'initial_facts.json').write_text(json.dumps(facts,indent=2),encoding='utf-8')
    agents,institutional=build_population(1000,42,source)
    agents.to_parquet(directory/'population.parquet',index=False)
    report={'source_directory':str(Path(source).resolve()),'time_zone':'UTC','initial_facts':facts,'targets_rows':len(targets),'missing_targets':targets.isna().sum().to_dict(),'institutional_claim_ust':institutional,'notes':['Micro-aUST in epoch_state divided by 1e6. Transaction amounts are already whole tokens.','Group observations are deposit/withdraw events, not aUST transfers.','First epoch_state at 00:14 UTC is used at 00:15; no backwards fill.','Full-window maximum wealth and realized loss are excluded from agent decisions.','Trading depth is not observed; it must be calibrated and tested for sensitivity.']}
    (directory/'quality_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
