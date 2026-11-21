"""Supplementary historical checks; never consumed as agent signals."""
import json
import numpy as np
import pandas as pd
from .config import ROOT
from .data import read_source,utc,load_targets
from .metrics import fit_metrics


def build_diagnostics():
    folder=ROOT/'outputs'/'calibration'
    t=pd.read_parquet(folder/'trajectory_all.parquet')
    observed=load_targets()
    venues=t[['ust_price','luna_price']].rename(columns=lambda c:'model_'+c).copy()
    venues['aggregate_ust_price']=observed.ust_price
    ftx=read_source('prices/ust_luna_minute_price_run.parquet')
    ftx=ftx.assign(time=utc(ftx.time)).set_index('time').sort_index()
    ftx=ftx.loc['2022-05-06':'2022-05-15']
    for column,name in [('UST','ust_price'),('LUNA','luna_price')]:
        venues['ftx_'+name]=ftx[column].reindex(t.index,method='ffill')
    venue_metrics={}
    for name,filename,price,amount in [
        ('binance','exchange/binance_ustusdt_may7.parquet','price','amount'),
        ('curve','curve/curve_ust_3pool_may7.parquet','price_native','sell_amount')]:
        d=read_source(filename).copy(); d['time']=utc(d.time)
        if name=='curve': d=d[d.quote_asset!='3Crv']
        d=d.set_index('time').sort_index()
        d['signed_ust']=np.where(d.taker_side_sell,d[amount],-d[amount])
        price15=d[price].resample('15min',label='right',closed='right').last()
        signed=d.signed_ust.resample('15min',label='right',closed='right').sum()
        venues[name+'_ust_price']=price15.reindex(t.index)
        venues[name+'_net_ust_sell']=signed.reindex(t.index)
        x=venues[[name+'_ust_price','model_ust_price','aggregate_ust_price']].dropna()
        change=np.log(x[name+'_ust_price']).diff()
        flow=signed.reindex(x.index)
        venue_metrics[name]={'bins_with_trades':len(x),'mae_model':float(abs(x[name+'_ust_price']-x.model_ust_price).mean()),
            'mae_aggregate_reference':float(abs(x[name+'_ust_price']-x.aggregate_ust_price).mean()),
            'net_sell_return_correlation':float(flow.corr(change)),
            'gross_sell_ust':float(d.loc[d.taker_side_sell,amount].sum()),
            'qualification':'Single-venue descriptive check; USDT/USDC/DAI treated near USD. No volume match with aggregate market is assumed.'}
    x=venues.dropna(subset=['ftx_ust_price','ftx_luna_price'])
    venue_metrics['ftx']={'aligned_rows':len(x),'ust_mae_model':float(abs(x.ftx_ust_price-x.model_ust_price).mean()),
        'ust_mae_aggregate_reference':float(abs(x.ftx_ust_price-x.aggregate_ust_price).mean()),
        'luna_log_rmse_model':float(np.sqrt(np.mean((np.log10(x.ftx_luna_price.clip(lower=1e-12))-np.log10(x.model_luna_price.clip(lower=1e-12)))**2))),
        'qualification':'2022 panel is FTX USD spot, separate from the main price target.'}
    native_halt='2022-05-13T02:00:00Z'
    result={'venues':venue_metrics,'before_native_stop':fit_metrics(t,end=native_halt),
        'after_native_stop':fit_metrics(t,start=native_halt),
        'qualification':'Full-event parameters, in-sample diagnostics. Onset error uses the complete event; before/after boundaries are dated model approximations.'}
    (folder/'diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    venues.to_parquet(folder/'cross_venue_15min.parquet')
    events=[
        ('2022-05-06T00:15:00Z','Khởi tạo từ epoch 00:14','epoch_state_fig10','snapshot','Khởi tạo mô hình'),
        ('2022-05-07T00:00:00Z','Cửa sổ hành động hai ví A/B','wallet_A_B transactions','observed window','Cú sốc có điều kiện theo từng giao dịch'),
        ('2022-05-08T00:00:00Z','TFL mua UST + LFG stablecoin','JS Held, bảng mua ngày 08','daily aggregate','Ý định mua gộp, bị chặn bởi quỹ/market'),
        ('2022-05-09T00:00:00Z','LFG mở tranche BTC cho Jump','JS Held, ngày 09','early bound','Quỹ sớm/muộn là giả định'),
        ('2022-05-10T00:00:00Z','LFG mở tranche BTC còn lại','JS Held, ngày 10','early bound','Không cộng chuyển nội bộ thành quỹ mới'),
        ('2022-05-11T12:00:00Z','Tăng virtual pool/capacity','Terra Market + native swap volume','approximate','Pool ×4 trong replay; không tái lập từng block'),
        (native_halt,'Đóng native/Anchor trong replay','Mốc native cuối trong dữ liệu','approximate simplifying assumption','Đóng phục vụ Anchor cùng native là giả định thô, không mô hình các lần restart'),
        ('2022-05-16T00:00:00Z','Bắt đầu tail không giải ngân mới','Experiment protocol','counterfactual test','Giữ BTC cuối cửa sổ, tiếp tục bảy ngày')]
    pd.DataFrame(events,columns=['time_utc','event','source','certainty','model_effect']).to_csv(ROOT/'data'/'processed'/'event_timeline.csv',index=False,encoding='utf-8-sig')
    return result
