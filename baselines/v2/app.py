"""Local Vietnamese dashboard. Start with streamlit run app.py."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from luna_sim.config import ROOT, ScenarioConfig, PolicyConfig, load_params
from luna_sim.data import GROUPS,load_targets,group_targets
from luna_sim.engine import simulate
from luna_sim.metrics import fit_metrics
from luna_sim.experiments import export_run,scenario_presets

st.set_page_config(page_title='Luna–UST | Phòng thí nghiệm',page_icon='🌘',layout='wide')
st.markdown('''<style>
.block-container {max-width:1400px;padding-top:3.5rem;} h1{letter-spacing:-.035em;}
[data-testid="stMetric"] {border:1px solid #26394c;border-radius:12px;padding:16px;background:#101b29;}
[data-testid="stMetricValue"] {font-size:clamp(1.05rem,1.7vw,1.8rem);}
.stTabs [data-baseweb="tab-list"]{gap:24px;} .stTabs [data-baseweb="tab"]{height:54px;}
</style>''',unsafe_allow_html=True)
st.caption('ABM + SYSTEM DYNAMICS · cadCAD · THÁNG 05/2022')
st.title('Luna–UST: có thể cứu vãn?')
st.write('Đối chiếu khủng hoảng thật, thay đổi cách can thiệp và theo dõi chi phí cùng khả năng phục hồi.')

PARAM_PATH=ROOT/'outputs'/'calibration'/'parameters.json'
if not (ROOT/'data'/'external'/'btc_usdt_minute.parquet').exists():
    st.error('Chưa chuẩn bị dữ liệu. Chạy: python -m luna_sim.cli prepare'); st.stop()
if not PARAM_PATH.exists():
    st.warning('Đang dùng tham số khởi đầu, chưa hiệu chỉnh. Kết quả chưa đủ cơ sở để đánh giá chính sách.')
full_path=ROOT/'outputs'/'calibration'/'parameters_full_fit.json'
options=['Hiệu chỉnh 06–10/05; kiểm định 11–15/05']
if full_path.exists(): options.insert(0,'Khớp toàn sự kiện; chỉ đánh giá trong mẫu')
selected_model=st.selectbox('Bộ tham số dùng chung cho lịch sử và chính sách',options)
params=load_params(full_path if selected_model.startswith('Khớp') else PARAM_PATH)
if selected_model.startswith('Khớp'):
    st.caption('Bộ tham số này được ước lượng từ toàn sự kiện để trình diễn; không dùng sai số 11–15/05 làm kiểm định ngoài mẫu. Không hiệu chỉnh lại theo từng chính sách.')
parameter_key=json.dumps(params.__dict__,sort_keys=True)


@st.cache_data(show_spinner=False,max_entries=12)
def cached_run(payload):
    return simulate(ScenarioConfig.from_dict(json.loads(payload)))


def chart(trajectories,column,title,log=False,historical=True):
    fig=go.Figure()
    if historical:
        targets=load_targets()
        target_column='native_ust' if column=='native_served' else column
        if target_column in targets:
            fig.add_trace(go.Scatter(x=targets.index,y=targets[target_column],name='Dữ liệu thật',line={'color':'#cbd5e1','width':2,'dash':'dot'}))
    colors=['#56c4ff','#f5b75b','#80dfad','#e68caa']
    for i,(name,t) in enumerate(trajectories.items()):
        fig.add_trace(go.Scatter(x=t.index,y=t[column],name=name,line={'color':colors[i%len(colors)],'width':2}))
    fig.update_layout(title=title,template='plotly_dark',height=340,margin={'l':20,'r':20,'t':50,'b':20},legend={'orientation':'h','y':1.15},paper_bgcolor='#0e1621',plot_bgcolor='#0e1621',xaxis_title='Thời gian UTC')
    if log: fig.update_yaxes(type='log')
    return fig


report_path=ROOT/'outputs'/'calibration'/'report_train.json'
report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
if report and not report['validation']['passes_all']:
    st.warning('Mô hình chưa đạt toàn bộ ngưỡng kiểm định ngoài mẫu. Thí nghiệm chính sách mang tính khám phá; xem sai số trong tab Đối chiếu lịch sử.')
st.caption('Giới hạn: cơ chế tài chính tổng hợp; chưa mô phỏng an ninh validator hoặc sổ lệnh đầy đủ. Nguồn lực bị giới hạn theo lịch sử LFG/TFL.')

history_tab,policy_tab,compare_tab=st.tabs(['01 · Đối chiếu lịch sử','02 · Thử cứu trợ','03 · So sánh & báo cáo'])

with history_tab:
    with st.spinner('Chạy mô hình lịch sử bằng cadCAD…'):
        config=ScenarioConfig(params=params,stochastic=False,funding_timing='early')
        base,base_metrics,base_ledger=cached_run(json.dumps(config.to_dict(),sort_keys=True))
    fit=fit_metrics(base)
    cols=st.columns(4)
    cols[0].metric('Sai số giá UST (MAE)',f'{fit["ust_mae"]:.3f} USD',help='Mục tiêu ≤ 0,05 USD')
    cols[1].metric('Sai số tiền gửi Anchor',f'{fit["deposit_nrmse"]:.1%}',help='RMSE / tiền gửi đầu kỳ. Mục tiêu ≤ 10%.')
    cols[2].metric('Chi cứu trợ / USD',f'{base_metrics["support_spent_usd"]/1e9:.2f} tỷ')
    cols[3].metric('RMSE log nguồn cung',f'{fit["luna_supply_log_rmse"]:.2f}',help='RMSE log₁₀ nguồn cung LUNA. Mục tiêu ≤ 0,5.')
    left,right=st.columns(2)
    left.plotly_chart(chart({'Mô phỏng lịch sử':base},'ust_price','Giá UST / USD'),width='stretch')
    right.plotly_chart(chart({'Mô phỏng lịch sử':base},'anchor_deposits','Tiền gửi Anchor / UST'),width='stretch')
    left.plotly_chart(chart({'Mô phỏng lịch sử':base},'luna_price','Giá LUNA / USD',log=True),width='stretch')
    right.plotly_chart(chart({'Mô phỏng lịch sử':base},'luna_supply','Nguồn cung LUNA',log=True),width='stretch')
    with st.expander('Hành vi theo nhóm tài sản và native swap'):
        fig=go.Figure()
        real_groups=group_targets().reindex(base.index)
        palette=['#56c4ff','#f5b75b','#80dfad','#e68caa','#bba0ef','#e0df82']
        for i,name in enumerate(GROUPS):
            fig.add_trace(go.Scatter(x=base.index,y=base[f'group_{i}_remaining'],name=name+' · mô phỏng',legendgroup=name,line={'color':palette[i]}))
            fig.add_trace(go.Scatter(x=base.index,y=real_groups[i],name=name+' · dữ liệu',legendgroup=name,line={'color':palette[i],'dash':'dot','width':1}))
        fig.update_layout(template='plotly_dark',title='Tỷ lệ tiền gửi còn lại theo tài sản trước khủng hoảng',height=360)
        st.plotly_chart(fig,width='stretch')
        st.plotly_chart(chart({'Mô phỏng lịch sử':base},'native_served','UST đã đổi sang LUNA mỗi bước'),width='stretch')
    with st.expander('Kiểm định, dữ liệu và giả định'):
        if report:
            st.json({'hiệu_chỉnh_06_10':report['train'],'kiểm_định_11_15':report['validation']})
        st.json({'sai_số_bộ_tham_số_đang_chọn':fit})
        st.write('Tổng tiền gửi dùng epoch_state. Phân nhóm dùng tài sản trước sự kiện; không dùng giá trị lớn nhất trong toàn bộ khủng hoảng. Hai ví A/B là cú sốc khởi phát có điều kiện, không phải bằng chứng về nguyên nhân tấn công.')
        st.write('Độ sâu giao dịch phải hiệu chỉnh. Khoản cứu trợ lịch sử được thực hiện trong giới hạn quỹ; bản tái lập không có đầy đủ lịch giao dịch Jump hoặc vốn lưu động TFL.')
        st.write('Audit ghi nhận Jump chuyển 1,516 tỷ UST cho TFL nhưng thiếu từng giao dịch mua. Khối lượng này chưa có lịch lệnh riêng trong mô hình; sai lệch đó giới hạn đối chiếu cứu trợ lịch sử và phản thực tế. Nguồn tiền BTC vẫn được tính trong trần quỹ, không tính UST nhận về thành nguồn USD mới.')
        st.write(f'Ý định mua UST chưa thực hiện trong bản tái lập: {base_metrics["historical_execution_gap_usd"]/1e6:,.1f} triệu USD.')
        st.json(base_metrics['max_accounting_errors'])
    with st.expander('Đối chiếu riêng FTX và Curve/Binance ngày 07/05'):
        diagnostic_folder=ROOT/'outputs'/'calibration'
        if (diagnostic_folder/'cross_venue_15min.parquet').exists():
            venue=st.selectbox('Nguồn giá đối chiếu riêng',['ftx','curve','binance'])
            v=pd.read_parquet(diagnostic_folder/'cross_venue_15min.parquet')
            column=venue+'_ust_price'
            actual=v[column].dropna()
            simulated=base.ust_price.reindex(actual.index)
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=actual.index,y=actual,name=venue.upper(),line={'dash':'dot','color':'#cbd5e1'}))
            fig.add_trace(go.Scatter(x=simulated.index,y=simulated,name='Bộ tham số đang chọn',line={'color':'#56c4ff'}))
            fig.update_layout(template='plotly_dark',title='Giá UST: đối chiếu nguồn riêng',height=340,xaxis_title='UTC')
            st.plotly_chart(fig,width='stretch')
            st.caption('FTX 2022 là giá spot USD của một sàn; Curve bỏ quote 3Crv. Đối chiếu USDT/USDC/DAI giả định gần USD. Không ép mô hình đi theo giá sàn và không coi khối lượng một sàn là toàn thị trường.')
            st.json(json.loads((diagnostic_folder/'diagnostics.json').read_text(encoding='utf-8')))
            st.caption('Các số chẩn đoán trong JSON được tính từ bộ khớp toàn sự kiện, trong mẫu. Biểu đồ dùng bộ tham số đang chọn.')
        else: st.info('Chạy: python -m luna_sim.cli diagnostics')

with policy_tab:
    controls,results=st.columns([1,2.5],gap='large')
    with controls:
        st.subheader('Cấu hình can thiệp')
        with st.form('policy_form'):
            actions=st.multiselect('Chính sách',options=['Mua UST','Bổ sung thanh khoản','Điều chỉnh native swap','Giới hạn rút Anchor'],default=['Mua UST'])
            trigger=st.radio('Kích hoạt bằng',options=['Ngưỡng giá','Thời điểm'],horizontal=True)
            threshold=st.slider('Ngưỡng UST / USD',.90,.999,.990,.001)
            date=st.date_input('Ngày can thiệp',value=pd.Timestamp('2022-05-08').date(),min_value=pd.Timestamp('2022-05-07').date(),max_value=pd.Timestamp('2022-05-15').date())
            hour=st.slider('Giờ UTC',0,23,0)
            delay=st.selectbox('Độ trễ thực thi',options=[15,60,360],index=1,format_func=lambda x:f'{x} phút')
            duration=st.slider('Thời hạn can thiệp / giờ',6,192,120,6)
            spend=st.slider('Hạn mức mỗi chính sách / triệu USD mỗi giờ',1,200,50,1)
            allocation=st.slider('Phần quỹ khả dụng cho mua UST mỗi bước',0.,1.,.7,.05,help='Khi kết hợp thanh khoản, tỷ lệ giới hạn khoản lấy từ quỹ hiện có trong mỗi bước. Tỷ lệ chi tích lũy còn phụ thuộc tốc độ chi, thời hạn và nhu cầu mua.')
            pool=st.slider('Quy mô virtual pool / lần',.5,8.,2.,.5)
            recovery=st.select_slider('Thời gian phục hồi pool / lần',options=[.25,.5,1.,2.,4.],value=.5)
            gate=st.slider('Giới hạn rút / % tiền gửi mỗi ngày',1,100,20,1)
            funding=st.selectbox('Thời điểm quỹ khả dụng',options=['late','early'],format_func=lambda x:'Biên muộn, thận trọng' if x=='late' else 'Biên sớm, giả định thuận lợi')
            funder=st.selectbox('Nguồn tài trợ',options=['both','LFG','TFL'],format_func=lambda x:'LFG + TFL' if x=='both' else x)
            stochastic=st.checkbox('Hành vi ngẫu nhiên',value=True)
            seed=st.number_input('Seed',min_value=0,max_value=100000,value=42,step=1)
            stress=st.checkbox('Kiểm tra thêm 7 ngày sau khi dừng hỗ trợ',value=True)
            submitted=st.form_submit_button('Chạy thí nghiệm',type='primary',width='stretch')
        st.caption('Ngân sách không được nhập tùy ý. Chính sách thay thế phần cứu trợ lịch sử; các khoản mua chia sẻ cùng một sổ tài sản.')
        uploaded=st.file_uploader('Nạp lại cấu hình JSON',type='json')
        import_run=st.button('Chạy cấu hình đã nạp',disabled=uploaded is None)
    if submitted:
        mapping={'Mua UST':'buy_ust','Bổ sung thanh khoản':'liquidity','Điều chỉnh native swap':'native_swap','Giới hạn rút Anchor':'withdrawal_gate'}
        policies=[]
        for name in actions:
            fraction=(allocation if name=='Mua UST' else 1-allocation) if 'Mua UST' in actions and 'Bổ sung thanh khoản' in actions else 1.
            policies.append(PolicyConfig(mapping[name],trigger='price' if trigger=='Ngưỡng giá' else 'time',threshold=threshold,start_time=f'{date}T{hour:02d}:00:00Z',delay_minutes=delay,duration_hours=duration,max_spend_per_hour=spend*1e6,allocation_fraction=fraction,pool_multiplier=pool,recovery_multiplier=recovery,withdrawal_fraction_per_day=gate/100,funder=funder))
        st.session_state['scenario']=ScenarioConfig(name='dashboard_policy',mode='counterfactual',seed=int(seed),stochastic=stochastic,funding_timing=funding,stress_days=7 if stress else 0,params=params,policies=policies).to_dict()
    if import_run:
        try:
            loaded=ScenarioConfig.from_dict(json.load(uploaded)); st.session_state['scenario']=loaded.to_dict()
        except (ValueError,TypeError,json.JSONDecodeError) as e: st.error(f'Cấu hình không hợp lệ: {e}')
    with results:
        if 'scenario' not in st.session_state:
            st.info('Chọn chính sách và bấm Chạy thí nghiệm. Dashboard sẽ so sánh với mô hình lịch sử cùng bộ tham số.')
        else:
            policy_config=ScenarioConfig.from_dict(st.session_state['scenario'])
            with st.spinner('Chạy chính sách và kiểm tra sổ tài sản…'):
                trial,metrics,ledger=cached_run(json.dumps(policy_config.to_dict(),sort_keys=True))
                reference_config=replace(policy_config,name='matched_historical',mode='historical',funding_timing='early',policies=[])
                matched_base,_,_=cached_run(json.dumps(reference_config.to_dict(),sort_keys=True))
            st.session_state['last_result']=(trial,metrics,ledger)
            st.subheader(metrics['classification'])
            cols=st.columns(3)
            cols[0].metric('UST cuối kỳ',f'{metrics["final_ust_price"]:.4f} USD')
            cols[1].metric('Đã sử dụng',f'{metrics["support_spent_usd"]/1e9:.2f} tỷ USD')
            cols[2].metric('Peg liên tục lâu nhất',f'{metrics["peg_hours_longest"]:.1f} giờ')
            health=st.columns(3)
            health[0].metric('Nguồn lực còn lại',f'{metrics["support_remaining_usd"]/1e9:.2f} tỷ USD')
            health[1].metric('Phục vụ yêu cầu rút',f'{metrics["withdraw_service_ratio"]:.1%}')
            health[2].metric('Phục vụ native swap',f'{metrics["native_service_ratio"]:.1%}')
            st.caption('Đường lịch sử so sánh dùng cùng tham số, seed, kiểu hành vi và thời hạn với cấu hình chính sách đang hiển thị; lịch quỹ replay dùng biên sớm.')
            st.plotly_chart(chart({'Lịch sử':matched_base,'Chính sách':trial},'ust_price','UST: lịch sử và chính sách'),width='stretch')
            st.plotly_chart(chart({'Lịch sử':matched_base,'Chính sách':trial},'luna_supply','Nguồn cung LUNA',log=True),width='stretch')
            st.plotly_chart(chart({'Chính sách':trial},'withdraw_queue','Yêu cầu rút chưa xử lý / UST',historical=False),width='stretch')
            st.caption('Cứu vãn: peg 0,98–1,02 USD ≥ 48 giờ, phục vụ rút/đổi ≥ 95%, hàng đợi ổn định, quỹ còn và vượt qua 7 ngày không giải ngân mới. Ngừng hỗ trợ ở cuối cửa sổ lịch sử.')
            with st.expander('Quỹ, khả năng phục vụ và sổ giao dịch'):
                st.json(metrics)
                st.dataframe(ledger.tail(100),width='stretch')
            buttons=st.columns(3)
            buttons[0].download_button('Tải cấu hình',json.dumps(policy_config.to_dict(),ensure_ascii=False,indent=2),file_name='scenario.json',mime='application/json')
            buttons[1].download_button('Tải kết quả CSV',trial.to_csv().encode('utf-8-sig'),file_name='trajectory.csv',mime='text/csv')
            buttons[2].download_button('Tải sổ giao dịch',ledger.to_csv(index=False).encode('utf-8-sig'),file_name='ledger.csv',mime='text/csv')
            if st.button('Lưu thí nghiệm vào thư mục outputs'):
                location=export_run(policy_config,trial,metrics,ledger); st.success(f'Đã lưu: {location}')

with compare_tab:
    st.subheader('Kết quả nhiều seed và độ nhạy')
    directory=ROOT/'outputs'/'experiments'
    metadata_path=directory/'execution_metadata.json'
    experiment_metadata=json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    if experiment_metadata.get('status')=='running':
        st.info('Bộ nhiều seed đang chạy. Chờ hoàn tất để đối chiếu bảng dùng cùng tham số đã đóng băng.')
    elif (directory/'summary.csv').exists():
        summary=pd.read_csv(directory/'summary.csv')
        wanted=['scenario','n_runs','rescue_rate','final_ust_price','support_spent_usd','depositor_loss_fraction','withdraw_service_ratio','native_service_ratio']
        display=summary[[c for c in wanted if c in summary]].copy()
        labels={'historical':'Tái lập lịch sử','no_rescue':'Không cứu trợ','buy_ust':'Mua UST','liquidity':'Thanh khoản','native_swap':'Native swap','withdrawal_gate':'Giới hạn rút','combined':'Kết hợp'}
        display['scenario']=display.scenario.map(labels)
        display['support_spent_usd']/=1e9
        for key in ['rescue_rate','depositor_loss_fraction','withdraw_service_ratio','native_service_ratio']: display[key]*=100
        st.dataframe(display,width='stretch',hide_index=True,column_config={
            'scenario':'Kịch bản','n_runs':'Số seed',
            'rescue_rate':st.column_config.NumberColumn('Cứu vãn (%)',format='%.0f'),
            'final_ust_price':st.column_config.NumberColumn('UST cuối / USD',format='%.4f'),
            'support_spent_usd':st.column_config.NumberColumn('Chi / tỷ USD',format='%.3f'),
            'depositor_loss_fraction':st.column_config.NumberColumn('Tổn thất (%)',format='%.1f'),
            'withdraw_service_ratio':st.column_config.NumberColumn('Phục vụ rút (%)',format='%.1f'),
            'native_service_ratio':st.column_config.NumberColumn('Phục vụ đổi (%)',format='%.1f')})
        st.caption('Trung vị trên từng seed; tỷ lệ cứu vãn là số lần đạt tiêu chí / tổng số lần chạy. Cùng seed được dùng giữa các chính sách.')
        st.caption('Bảng và khoảng kết quả được tính với bộ khớp toàn sự kiện đã lưu, độc lập với lựa chọn bộ tham số ở màn hình đối chiếu. Muốn có kết quả cho bộ khác, cần chạy lại suite.')
        if (directory/'bands.parquet').exists():
            bands=pd.read_parquet(directory/'bands.parquet')
            selected=st.selectbox('Kịch bản để xem bất định',bands.scenario.unique())
            band=bands[bands.scenario==selected]
            fig=go.Figure()
            for q in ['p95','p05','median']:
                d=band[band['quantile']==q]
                fig.add_trace(go.Scatter(x=d.time,y=d.ust_price,name=q,fill='tonexty' if q=='p05' else None,line={'width':2 if q=='median' else 0},fillcolor='rgba(86,196,255,.18)'))
            fig.update_layout(template='plotly_dark',title='Giá UST: trung vị và khoảng 5–95%',height=360)
            st.plotly_chart(fig,width='stretch')
    else: st.info('Chưa có báo cáo nhiều seed. Chạy: python -m luna_sim.cli suite --seeds 20')
    if (directory/'sensitivity.csv').exists():
        with st.expander('Độ nhạy với thanh khoản, hành vi, độ trễ và lịch quỹ'):
            st.dataframe(pd.read_csv(directory/'sensitivity.csv'),width='stretch')
    if (directory/'timestep_check.json').exists():
        with st.expander('Kiểm tra bước thời gian 5 phút / 15 phút'):
            st.json(json.loads((directory/'timestep_check.json').read_text(encoding='utf-8')))
    st.markdown('[Nguồn cứu trợ: báo cáo JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf) · [Đặc tả Terra Market](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html)')
    with st.expander('Khoảng thời gian khả dụng của tài sản'):
        st.dataframe(pd.DataFrame(json.loads((ROOT/'data'/'sources.json').read_text(encoding='utf-8'))['funding_timing_intervals']),width='stretch')
    if (ROOT/'outputs'/'REPORT_VI.md').exists():
        st.download_button('Tải báo cáo bài nhóm',(ROOT/'outputs'/'REPORT_VI.md').read_bytes(),file_name='REPORT_VI.md',disabled=experiment_metadata.get('status')=='running')
