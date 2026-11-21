"""Local Vietnamese dashboard. Start with streamlit run app.py."""
from dataclasses import replace
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from luna_sim.config import ROOT, ScenarioConfig, PolicyConfig, load_params
from luna_sim.data import GROUPS, load_targets, group_targets
from luna_sim.engine import simulate
from luna_sim.metrics import fit_metrics
from luna_sim.experiments import export_run, scenario_presets, experiment_sources, experiment_artifact_current, SCENARIO_MATRIX_KEYS
from luna_sim.calibrate import _source_hashes
from luna_sim.diagnostics import diagnostic_sources
from luna_sim.report import report_artifact_current

st.set_page_config(page_title='Luna–UST | Mô phỏng Khủng hoảng & Đánh giá Cứu trợ', page_icon='🌘', layout='wide', initial_sidebar_state='collapsed')
st.markdown('''<style>
.block-container {max-width:1440px;padding-top:2.5rem;} h1{letter-spacing:-.035em;}
[data-testid="stMetric"] {border:1px solid #26394c;border-radius:12px;padding:16px;background:#101b29;}
[data-testid="stMetricValue"] {font-size:clamp(1.05rem,1.7vw,1.8rem);}
.stTabs [data-baseweb="tab-list"]{gap:24px;} .stTabs [data-baseweb="tab"]{height:54px;}
@media (max-width:1200px) {
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {flex-wrap:wrap;}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {min-width:calc(50% - 1rem);}
}
</style>''', unsafe_allow_html=True)

st.caption('Phương pháp: Agent-Based Model + System Dynamics · Công cụ: cadCAD / Python · Sự kiện: Tháng 05/2022')
st.title('Mô phỏng Khủng hoảng & Đánh giá Cứu trợ Terra Luna – UST')
st.write('Ứng dụng mô hình Agent-Based kết hợp System Dynamics để tái hiện cuộc khủng hoảng tháng 5/2022 và đánh giá hiệu quả của các phương án cứu trợ hệ sinh thái Terra Luna – UST.')

PARAM_PATH = ROOT / 'outputs' / 'calibration' / 'parameters.json'
if not (ROOT / 'data' / 'external' / 'btc_usdt_minute.parquet').exists():
    st.error('Chưa chuẩn bị dữ liệu. Chạy: python -m luna_sim.cli prepare')
    st.stop()

if not PARAM_PATH.exists():
    st.warning('Đang dùng tham số khởi đầu, chưa hiệu chỉnh với dữ liệu lịch sử.')

full_path = ROOT / 'outputs' / 'calibration' / 'parameters_full_fit.json'
options = ['Hiệu chỉnh 06–10/05; kiểm định 11–15/05']
if full_path.exists():
    options.insert(0, 'Bản tốt nhất hiện có · khớp toàn sự kiện (v4)')

selected_model = st.selectbox('Bộ tham số mô phỏng', options)
is_best = selected_model.startswith('Bản tốt nhất')
params = load_params(full_path if is_best else PARAM_PATH)
parameter_key = json.dumps(params.__dict__, sort_keys=True)
engine_key = hashlib.sha256((ROOT / 'luna_sim' / 'engine.py').read_bytes()).hexdigest()
source_key = hashlib.sha256(b''.join(path.read_bytes() for path in [
    ROOT / 'luna_sim' / 'engine.py',
    ROOT / 'luna_sim' / 'config.py',
    ROOT / 'luna_sim' / 'data.py',
    ROOT / 'luna_sim' / 'metrics.py',
    ROOT / 'data' / 'sources.json'
])).hexdigest()


@st.cache_data(show_spinner=False, max_entries=12)
def cached_run(payload, model_source_key):
    return simulate(ScenarioConfig.from_dict(json.loads(payload)))


@st.cache_data(show_spinner=False)
def load_scenario_run_trajectory(scenario_name, seed=42):
    parquet_path = ROOT / 'outputs' / 'runs' / f'{scenario_name}_seed{seed}' / 'trajectory.parquet'
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    csv_path = ROOT / 'outputs' / 'runs' / f'{scenario_name}_seed{seed}' / 'trajectory.csv'
    if csv_path.exists():
        return pd.read_csv(csv_path, index_col=0, parse_dates=True)
    return None


@st.cache_data(show_spinner=False)
def load_scenario_run_metrics(scenario_name, seed=42):
    path = ROOT / 'outputs' / 'runs' / f'{scenario_name}_seed{seed}' / 'metrics.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return None


@st.cache_data(show_spinner=False)
def load_matrix_summary():
    path = ROOT / 'outputs' / 'experiments' / 'summary.csv'
    if path.exists():
        return pd.read_csv(path)
    return None


def chart(trajectories, column, title, log=False, historical=True, window=None, show_corridor=False, show_legend=True):
    fig = go.Figure()
    if historical:
        targets = load_targets()
        target_column = 'native_ust' if column == 'native_served' else column
        if target_column in targets:
            df_hist = targets
            if window:
                df_hist = df_hist.loc[(df_hist.index >= window[0]) & (df_hist.index < window[1])]
            fig.add_trace(go.Scatter(
                x=df_hist.index, y=df_hist[target_column],
                name='Dữ liệu thực tế',
                connectgaps=False,
                showlegend=False,
                line={'color': '#cbd5e1', 'width': 2, 'dash': 'dot'}
            ))

    palette = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316', '#a855f7', '#6366f1']
    for i, (name, t) in enumerate(trajectories.items()):
        if t is None or column not in t.columns:
            continue
        df_plot = t
        if window:
            df_plot = df_plot.loc[(df_plot.index >= window[0]) & (df_plot.index < window[1])]
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot[column],
            name=name, connectgaps=False,
            showlegend=False,
            line={'color': palette[i % len(palette)], 'width': 2}
        ))

    if show_corridor and column == 'ust_price':
        # Add prominent green shaded corridor [0.98, 1.02] USD
        fig.add_hrect(
            y0=0.98, y1=1.02,
            fillcolor='rgba(34, 197, 94, 0.18)',
            line_width=1,
            line_color='rgba(34, 197, 94, 0.6)',
            line_dash='dash',
            annotation_text='Vùng peg ổn định [$0,98 – $1,02]',
            annotation_position='top left',
            annotation_font_color='#86efac'
        )
        fig.add_hline(y=1.0, line_dash='dot', line_color='#64748b', opacity=0.7)
    elif column == 'ust_price':
        fig.add_hline(y=1.0, line_dash='dash', line_color='#64748b', opacity=0.6)

    fig.update_layout(
        title=title, template='plotly_dark', height=380,
        hovermode='x unified', margin={'l': 20, 'r': 20, 't': 65, 'b': 25},
        showlegend=False,
        paper_bgcolor='#0e1621', plot_bgcolor='#0e1621',
        xaxis_title='Thời gian UTC'
    )
    fig.update_xaxes(showspikes=True, spikemode='across', tickformat='%d/%m\n%H:%M')
    if log:
        fig.update_yaxes(type='log')
    return fig


report_path = ROOT / 'outputs' / 'calibration' / 'report_train.json'
report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
calibration_source_key = _source_hashes()


def fit_complete(payload, split):
    status_path = ROOT / 'outputs' / 'calibration' / f'calibration_status_{split}.json'
    if not status_path.exists():
        return False
    status = json.loads(status_path.read_text(encoding='utf-8'))
    return (
        status.get('status') == 'complete'
        and status.get('run_id') == payload.get('optimizer', {}).get('run_id')
        and payload.get('provenance', {}).get('source_sha256') == calibration_source_key
    )


report_current = bool(report and fit_complete(report, 'train'))
chosen_split = 'all' if is_best else 'train'
chosen_report_path = ROOT / 'outputs' / 'calibration' / f'report_{chosen_split}.json'
chosen_report = json.loads(chosen_report_path.read_text(encoding='utf-8')) if chosen_report_path.exists() else {}
chosen_current = (
    fit_complete(chosen_report, chosen_split)
    and chosen_report.get('parameter_sha256') == hashlib.sha256(parameter_key.encode()).hexdigest()
)

from luna_sim.reconstruction import reconstruction_artifact_current, GATE_SPECS

presentation_valid = bool(chosen_current and reconstruction_artifact_current())
st.session_state.pop('presentation', None)

saved_trajectory = ROOT / 'outputs' / 'calibration' / f'trajectory_{chosen_split}.parquet'
base = pd.read_parquet(saved_trajectory) if saved_trajectory.exists() else pd.DataFrame()
base_metrics = chosen_report.get('financial_metrics', {'historical_execution_gap_usd': 0.0, 'max_accounting_errors': {}})
fit = chosen_report.get('all', {})
run_id = chosen_report.get('optimizer', {}).get('run_id', 'unknown_run')
config_path = ROOT / 'outputs' / 'calibration' / f'config_{chosen_split}.json'
config = ScenarioConfig.from_dict(json.loads(config_path.read_text(encoding='utf-8'))) if config_path.exists() else None

if presentation_valid and saved_trajectory.exists() and run_id != 'unknown_run':
    st.session_state['presentation'] = {
        'selected_run_id': run_id,
        'loaded_saved_result': True,
        'split': chosen_split,
        'trajectory_path': str(saved_trajectory),
        'parameter_sha256': chosen_report.get('parameter_sha256', '')
    }

with st.sidebar:
    st.subheader('Cấu hình mô phỏng')
    st.write('Giai đoạn mô phỏng: 06–23/05/2022 · 17 ngày · Giờ UTC')
    if config:
        st.caption(f"Quy mô mô hình: {config.n_depositors:,} người gửi tiền đại diện, {config.n_arbitrageurs} nhà kinh doanh chênh lệch giá, bước thời gian {config.dt_minutes} phút.")
    st.caption('Toàn bộ kết quả mô phỏng được lưu trong thư mục outputs/runs/.')
    with st.expander('Mã định danh kết quả mô hình'):
        st.code(run_id, language=None)
        st.caption(f"Engine: {engine_key[:12]} · tham số: {chosen_report.get('parameter_sha256', '')[:12]}")

show_legacy = st.sidebar.checkbox('Mở công cụ chính sách cũ', value=False)

tab_names = [
    '01 · So sánh chính sách cứu trợ (Bailout Policy Comparison)',
    '02 · Đối chiếu với dữ liệu lịch sử'
]
if show_legacy:
    tab_names.append('Thử nghiệm tùy chỉnh')
    bailout_tab, history_tab, policy_tab = st.tabs(tab_names)
else:
    bailout_tab, history_tab = st.tabs(tab_names)
    policy_tab = None

# -------------------------------------------------------------------------------------------------
# TAB 1: SO SÁNH CHÍNH SÁCH CỨU TRỢ (BAILOUT POLICY COMPARISON)
# -------------------------------------------------------------------------------------------------
with bailout_tab:
    st.subheader('So sánh chính sách cứu trợ (Bailout Policy Comparison)')
    st.markdown("""
<div style="background-color: #2b1116; border: 1px solid #7f1d1d; border-radius: 10px; padding: 14px 18px; margin-bottom: 22px;">
    <h4 style="color: #f87171; margin: 0 0 6px 0; font-size: 1.15rem;">KẾT LUẬN CHÍNH: KHÔNG CÓ PHƯƠNG ÁN NÀO CỨU ĐƯỢC HỆ THỐNG</h4>
    <p style="color: #fca5a5; margin: 0; font-size: 0.95rem; line-height: 1.5;">
        Với tổng nguồn lực cứu trợ thực tế khoảng <strong>$3,0B – $3,5B USD</strong>
        (bao gồm 80.081 BTC, $49,8M stablecoin và $613,6M hạn mức từ TFL — theo kiểm toán JS Held),
        mô hình đã thử nghiệm <strong>10 kịch bản can thiệp khác nhau và tất cả đều thất bại</strong>
        trong việc giữ giá UST neo ổn định ở mức $1 xuyên suốt 7 ngày kiểm tra.
        Nguyên nhân cốt lõi nằm ở quy mô nghĩa vụ nợ: tổng tiền gửi trên Anchor Protocol lên tới $14 tỷ UST,
        vượt xa khả năng chi trả của quỹ dự trữ. Khi nguồn vốn cứu trợ cạn kiệt,
        cơ chế đổi UST → LUNA kích hoạt vòng xoáy phát hành token không kiểm soát, dẫn đến sụp đổ toàn bộ hệ sinh thái.
    </p>
</div>
""", unsafe_allow_html=True)

    SCENARIO_DISPLAY = {
        'sc01_baseline_no_rescue': 'SC-01: Kịch bản cơ sở — không can thiệp',
        'sc02_staggered_tranches': 'SC-02: Phân bổ vốn theo từng đợt ($1,5B mỗi đợt)',
        'sc03_concentrated_bidwall': 'SC-03: Đặt lệnh mua tập trung tại ngưỡng $0,985 ($2,5B)',
        'sc04_buyback_burn': 'SC-04: Mua lại UST và tiêu hủy ngay lập tức ($2,0B)',
        'sc05_tiered_gates': 'SC-05: Giới hạn rút tiền theo từng mức (không chi vốn)',
        'sc06_market_defense': 'SC-06: Phòng vệ thị trường — phí 15% + hạn chế kinh doanh chênh lệch giá',
        'sc07_combined_realistic': 'SC-07: Gói kết hợp thực tế ($2,5B — nhiều biện pháp đồng thời)',
        'sc08_frontloaded_shock': 'SC-08: Bơm vốn tập trung ngay đầu kỳ ($663,5M trong 4 giờ)',
        'sc09_circuit_breaker': 'SC-09: Ngắt mạch khẩn cấp — đóng băng giao dịch 48 giờ',
        'sc10_maximum_extreme': 'SC-10: Gói can thiệp tối đa ($3,2B + cắt giảm nợ 20%)',
    }
    DEFAULT_COMPARE = [
        'sc01_baseline_no_rescue',
        'sc03_concentrated_bidwall',
        'sc07_combined_realistic',
        'sc08_frontloaded_shock',
        'sc10_maximum_extreme',
    ]

    ctrl_col1, ctrl_col2 = st.columns([3, 1])
    with ctrl_col1:
        chosen_scenarios = st.multiselect(
            'Chọn các kịch bản cứu trợ để hiển thị trên biểu đồ:',
            options=list(SCENARIO_DISPLAY.keys()),
            default=DEFAULT_COMPARE,
            format_func=lambda k: SCENARIO_DISPLAY.get(k, k)
        )
    with ctrl_col2:
        bailout_window_label = st.selectbox(
            'Giai đoạn hiển thị:',
            ['Toàn bộ 17 ngày (06–23/05)', '10 ngày đầu khủng hoảng (06–16/05)', '7 ngày kiểm tra sau cứu trợ (16–23/05)']
        )

    b_window = None
    if bailout_window_label == '10 ngày đầu khủng hoảng (06–16/05)':
        b_window = (pd.Timestamp('2022-05-06T00:00Z'), pd.Timestamp('2022-05-16T00:00Z'))
    elif bailout_window_label == '7 ngày kiểm tra sau cứu trợ (16–23/05)':
        b_window = (pd.Timestamp('2022-05-16T00:00Z'), pd.Timestamp('2022-05-23T00:00Z'))

    # Load summary dataframe
    summary_data = load_matrix_summary()
    if summary_data is not None and len(chosen_scenarios) > 0:
        sel_summary = summary_data[summary_data['scenario'].isin(chosen_scenarios)]
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric(
            'Thời gian giữ peg dài nhất',
            f"{sel_summary['peg_hours_longest'].max():.1f} giờ",
            help='Kịch bản SC-08 duy trì được peg lâu nhất là 45,5 giờ nhờ bơm vốn tập trung ngay từ đầu. SC-10 đạt 42,25 giờ.'
        )
        sm2.metric(
            'Tổng vốn đã chi (cao nhất)',
            f"${sel_summary['support_spent_usd'].max() / 1e9:.2f} tỷ USD",
            help='SC-10 đã sử dụng tối đa $3,20 tỷ USD, tương đương bán toàn bộ 80.081 BTC trong quỹ dự trữ.'
        )
        sm3.metric(
            'Tiền gửi Anchor còn lại (cao nhất)',
            f"${sel_summary['final_anchor_deposits'].max() / 1e6:.1f}M USD",
            help='SC-10 bảo toàn được $221,3M tiền gửi — cao gấp 30 lần so với mức $7,4M khi không can thiệp.'
        )
        sm4.metric(
            'Mức tổn thất thấp nhất cho người gửi',
            f"{sel_summary['depositor_loss_fraction'].min():.1%}",
            help='SC-07 giúp giảm tổn thất xuống còn 17,61%, so với 21,03% khi không có biện pháp cứu trợ nào.'
        )

    # Load trajectories
    trajectories_dict = {}
    for sc in chosen_scenarios:
        t_df = load_scenario_run_trajectory(sc)
        if t_df is not None:
            trajectories_dict[SCENARIO_DISPLAY.get(sc, sc)] = t_df

    st.markdown('---')
    st.subheader('Biểu đồ so sánh diễn biến các kịch bản cứu trợ')

    # -- Shared legend for all 4 charts --
    _legend_palette = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
                       '#06b6d4', '#ec4899', '#f97316', '#a855f7', '#6366f1']
    _legend_items = []
    # Historical data trace (dotted grey)
    _legend_items.append(
        '<span style="display:inline-flex;align-items:center;margin-right:18px;">'
        '<span style="display:inline-block;width:28px;height:0;border-top:2px dotted #cbd5e1;margin-right:6px;"></span>'
        '<span style="color:#cbd5e1;font-size:0.85rem;">Dữ liệu thực tế</span></span>'
    )
    for i, name in enumerate(trajectories_dict.keys()):
        color = _legend_palette[i % len(_legend_palette)]
        _legend_items.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:18px;">'
            f'<span style="display:inline-block;width:28px;height:0;border-top:2.5px solid {color};margin-right:6px;"></span>'
            f'<span style="color:{color};font-size:0.85rem;">{name}</span></span>'
        )
    _legend_html = (
        '<div style="background:#182233;border:1px solid #334155;border-radius:8px;'
        'padding:10px 16px;margin-bottom:12px;display:flex;flex-wrap:wrap;'
        'justify-content:center;gap:4px 0;">'
        + ''.join(_legend_items) +
        '</div>'
    )
    st.markdown(_legend_html, unsafe_allow_html=True)

    # Chart 1: UST Price Trajectory with Green Corridor [0.98, 1.02]
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            chart(
                trajectories_dict, 'ust_price',
                '1. Diễn biến giá UST theo thời gian',
                historical=True, window=b_window, show_corridor=True
            ),
            width='stretch'
        )
        st.caption('Dải màu xanh lá đánh dấu vùng giá UST được coi là ổn định (từ $0,98 đến $1,02). Kịch bản bơm vốn tập trung (SC-08) giữ được peg lâu nhất — 45,5 giờ — nhưng sau đó tất cả các kịch bản đều mất peg khi nguồn vốn cạn kiệt.')

    # Chart 2: Anchor Deposits & Cash Trajectory
    with c2:
        st.plotly_chart(
            chart(
                trajectories_dict, 'anchor_deposits',
                '2. Lượng tiền gửi trên Anchor Protocol theo thời gian',
                historical=False, window=b_window
            ),
            width='stretch'
        )
        st.caption('Tiền gửi trên Anchor giảm nhanh chóng do người dùng rút ồ ạt: từ $14,0 tỷ xuống chỉ còn $7,4M nếu không can thiệp. Các biện pháp như giới hạn rút tiền (SC-07: $50,5M) và gói tối đa (SC-10: $221,3M) giúp giữ lại một phần tiền gửi.')

    # Chart 3: LUNA Supply Inflation Trajectory (Log scale)
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(
            chart(
                trajectories_dict, 'luna_supply',
                '3. Tổng cung LUNA theo thời gian (thang logarit)',
                log=True, historical=True, window=b_window
            ),
            width='stretch'
        )
        st.caption('Khi quỹ cứu trợ cạn kiệt, cơ chế đổi UST sang LUNA buộc hệ thống phát hành lượng token khổng lồ — từ 725 triệu lên hàng nghìn tỷ LUNA — tạo ra vòng xoáy siêu lạm phát khiến giá LUNA mất gần hết giá trị.')

    # Chart 4: Intervention Capital Spent vs Remaining
    with c4:
        # Build comparative support spent / remaining chart
        fig_cap = go.Figure()
        palette = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316', '#a855f7', '#6366f1']
        for i, (name, t_df) in enumerate(trajectories_dict.items()):
            if 'support_spent' in t_df.columns:
                df_c = t_df
                if b_window:
                    df_c = df_c.loc[(df_c.index >= b_window[0]) & (df_c.index < b_window[1])]
                fig_cap.add_trace(go.Scatter(
                    x=df_c.index, y=df_c['support_spent'] / 1e9,
                    name=f'{name} (Đã chi)',
                    showlegend=False,
                    line={'color': palette[i % len(palette)], 'width': 2}
                ))
        fig_cap.update_layout(
            title='4. Tổng vốn cứu trợ đã chi theo thời gian (tỷ USD)',
            template='plotly_dark', height=380, hovermode='x unified',
            paper_bgcolor='#0e1621', plot_bgcolor='#0e1621',
            yaxis_title='Tỷ USD', xaxis_title='Thời gian UTC',
            showlegend=False
        )
        st.plotly_chart(fig_cap, width='stretch')
        st.caption('Biểu đồ cho thấy tốc độ tiêu hao ngân sách cứu trợ của từng kịch bản. SC-10 tiêu hết trần $3,2B (bán toàn bộ 80.081 BTC); SC-03 và SC-07 dừng ở mức $2,5B; SC-08 tập trung bơm $663,5M chỉ trong 4 giờ đầu.')

    st.markdown('---')
    st.subheader('Bảng tổng hợp kết quả 10 kịch bản cứu trợ')
    if summary_data is not None:
        display_summary = summary_data.copy()
        col_rename = {
            'scenario': 'Kịch bản',
            'peg_hours_longest': 'Giữ peg (giờ)',
            'operational_hours_longest': 'Thời gian vận hành (giờ)',
            'final_ust_price': 'Giá UST cuối kỳ (USD)',
            'min_ust_price': 'Giá UST thấp nhất (USD)',
            'final_anchor_deposits': 'Tiền gửi Anchor còn lại (USD)',
            'final_withdraw_queue': 'Lệnh rút đang chờ (UST)',
            'final_luna_supply': 'Tổng cung LUNA cuối kỳ',
            'support_spent_usd': 'Vốn cứu trợ đã chi (USD)',
            'btc_sold': 'Số BTC đã bán',
            'depositor_loss_fraction': 'Tỷ lệ tổn thất người gửi',
            'withdraw_service_ratio': 'Tỷ lệ phục vụ lệnh rút',
        }
        avail_cols = [c for c in col_rename.keys() if c in display_summary.columns]
        display_df = display_summary[avail_cols].rename(columns=col_rename)
        st.dataframe(
            display_df, width='stretch', hide_index=True,
            column_config={
                'Giữ peg (giờ)': st.column_config.NumberColumn(format='%.2f h'),
                'Thời gian vận hành (giờ)': st.column_config.NumberColumn(format='%.2f h'),
                'Giá UST cuối kỳ (USD)': st.column_config.NumberColumn(format='$%.6f'),
                'Giá UST thấp nhất (USD)': st.column_config.NumberColumn(format='$%.6f'),
                'Tiền gửi Anchor còn lại (USD)': st.column_config.NumberColumn(format='$%,.0f'),
                'Lệnh rút đang chờ (UST)': st.column_config.NumberColumn(format='%,.0f'),
                'Tổng cung LUNA cuối kỳ': st.column_config.NumberColumn(format='%,.0f'),
                'Vốn cứu trợ đã chi (USD)': st.column_config.NumberColumn(format='$%,.0f'),
                'Số BTC đã bán': st.column_config.NumberColumn(format='%,.2f BTC'),
                'Tỷ lệ tổn thất người gửi': st.column_config.NumberColumn(format='%.2%'),
                'Tỷ lệ phục vụ lệnh rút': st.column_config.NumberColumn(format='%.2%'),
            }
        )

        dcols = st.columns(3)
        dcols[0].download_button('Tải bảng tổng hợp kết quả (.csv)', summary_data.to_csv(index=False).encode('utf-8-sig'), file_name='summary.csv', mime='text/csv')
        runs_path = ROOT / 'outputs' / 'experiments' / 'runs.csv'
        if runs_path.exists():
            dcols[1].download_button('Tải dữ liệu chi tiết từng bước (.csv)', runs_path.read_bytes(), file_name='runs.csv', mime='text/csv')
        rep_vi_path = ROOT / 'outputs' / 'BAILOUT_EVALUATION_REPORT_VI.md'
        if rep_vi_path.exists():
            dcols[2].download_button('Tải báo cáo phân tích đầy đủ (.md)', rep_vi_path.read_bytes(), file_name='BAILOUT_EVALUATION_REPORT_VI.md', mime='text/markdown')

    with st.expander('Phân tích chi tiết: Vì sao từng phương án cứu trợ đều thất bại?'):
        st.markdown(r"""
### 1. Mua lại UST nhưng không tiêu hủy — bài học từ thực tế và kịch bản SC-04

Trong thực tế, Quỹ LFG và Jump Trading đã mua gom một lượng lớn UST nhưng chỉ giữ trên ví hoặc tài khoản sàn giao dịch, không tiêu hủy trên chuỗi. Điều này có nghĩa là tổng nghĩa vụ nợ của hệ sinh thái không hề giảm.

Kịch bản SC-04 thử nghiệm phương án ngược lại: tiêu hủy ngay lập tức 2,0 tỷ UST đã mua (chi phí 2,0 tỷ USD, tương đương 61.272 BTC). Kết quả cho thấy cung UST lưu hành giảm từ 18,7 tỷ xuống 16,7 tỷ, nhưng phần còn lại trên Anchor (hơn 12 tỷ UST) vẫn gấp 6 lần thanh khoản thứ cấp, nên depeg chỉ được trì hoãn thêm khoảng 2 giờ.

### 2. Đặt lệnh mua tập trung $2,5B tại ngưỡng giá — kịch bản SC-03

SC-03 tập trung toàn bộ $2,5 tỷ USD vào một lệnh mua lớn tại mức giá $0,985 nhằm tạo lực đỡ mạnh và hạn chế trượt giá. Tuy nhiên, với tốc độ rút tiền từ Anchor lên tới $200–$350 triệu mỗi giờ, toàn bộ số vốn này bị quét sạch chỉ sau 11 giờ (bán hết 77.137 BTC). Ngay khi lệnh mua hết vốn, sổ lệnh trống rỗng và giá UST rơi tự do.

### 3. Bơm vốn tập trung ngay đầu kỳ — kịch bản SC-08

SC-08 áp dụng chiến thuật bơm vốn sốc với tốc độ $800 triệu mỗi giờ ngay trong 4 giờ đầu tiên (thực chi $663,5 triệu), giúp đè bẹp đợt hoảng loạn đầu tiên trên sàn Curve và giữ peg thành công trong 45,5 giờ — lâu nhất trong tất cả các kịch bản có chi vốn. Tuy nhiên, khi nhà đầu tư nhận ra ngân sách đã gần cạn kiệt, làn sóng hoảng loạn thứ hai bùng phát và peg không thể phục hồi.

### 4. Kiểm soát dòng vốn và cắt giảm nợ — các kịch bản SC-05, SC-06, SC-07, SC-10

Nhóm kịch bản này tập trung vào biện pháp hành chính: giới hạn tốc độ rút tiền (SC-05), áp phí giao dịch 15% kết hợp hạn chế kinh doanh chênh lệch giá (SC-06), hoặc kết hợp nhiều biện pháp cùng lúc (SC-07, SC-10). Kết quả cho thấy các biện pháp này giúp bảo toàn được một phần tiền gửi Anchor ($17–$221 triệu tùy kịch bản) và kiềm chế tốc độ lạm phát LUNA, nhưng không đủ để giữ peg. Kịch bản cực đoan nhất (SC-10) kết hợp đóng băng giao dịch, thuế rút 20%, lệnh mua tập trung và bơm vốn — tổng chi $3,2 tỷ và bán hết 80.081 BTC — nhưng giá UST cuối cùng vẫn giảm về $0,0020.

### 5. Giải thích bằng toán học: Tại sao hệ thống không thể cứu được?

- **Chênh lệch quá lớn giữa nghĩa vụ nợ và dự trữ**: Nghĩa vụ nợ Anchor ($14,0 tỷ) trừ đi dự trữ tối đa ($3,2 tỷ) để lại thâm hụt $10,8 tỷ USD — gấp hơn 3 lần khả năng chi trả.
- **Thời gian cầm cự có giới hạn**: Với tốc độ rút tiền trung bình $1,2 tỷ mỗi ngày, ngay cả kịch bản tốt nhất cũng chỉ trụ được tối đa khoảng $T_{\text{max}} \le 3{,}2 / 1{,}2 \approx 64 \text{ giờ}$.
- **Điểm không thể quay lại**: Khi vốn cứu trợ hết, cơ chế đổi UST → LUNA kích hoạt phát hành token không giới hạn, tạo vòng xoáy siêu lạm phát mà không có cách nào ngăn chặn: $\lim_{P_{\text{LUNA}} \to 0} \frac{d S_{\text{LUNA}}}{dt} = +\infty$.
""")

# -------------------------------------------------------------------------------------------------
# TAB 2: ĐỐI CHIẾU LỊCH SỬ (HISTORICAL RECONSTRUCTION)
# -------------------------------------------------------------------------------------------------
with history_tab:
    if not presentation_valid:
        st.warning('Lưu ý: Kết quả hiển thị được tải từ lần chạy trước. Phiên bản engine hiện tại đã được nâng cấp để phục vụ nghiên cứu các phương án cứu trợ.')

    if not fit:
        st.error('Chưa tìm thấy dữ liệu hiệu chỉnh mô hình. Vui lòng chạy bước calibration trước.')
    else:
        cols = st.columns(4)
        cols[0].metric('Sai số trung bình giá UST (MAE)', f'{fit.get("ust_mae", 0.0):.4f} USD', help='Sai số tuyệt đối trung bình giữa giá UST mô phỏng và thực tế. Mục tiêu: ≤ 0,05 USD.')
        cols[1].metric('Sai số tiền gửi Anchor (NRMSE)', f'{fit.get("deposit_nrmse", 0.0):.2%}', help='Sai số căn bậc hai trung bình, chuẩn hóa theo giá trị tiền gửi đầu kỳ. Mục tiêu: ≤ 10%.')
        cols[2].metric('Sai số giá LUNA (RMSE log)', f'{fit.get("luna_price_log_rmse", 0.0):.4f}', help='Sai số căn bậc hai trung bình trên thang logarit (log₁₀) của giá LUNA. Mục tiêu: ≤ 0,5.')
        cols[3].metric('Số ngưỡng đạt yêu cầu', f'{sum(fit.get("gates", {}).values())}/6', help='Mô hình được đánh giá trên 6 ngưỡng chất lượng. Số hiển thị cho biết bao nhiêu ngưỡng đạt yêu cầu.')
        st.caption('Các chỉ số sai số được tính trên toàn bộ giai đoạn 06–15/05. Mô hình tốt nhất hiện có vẫn còn chênh lệch nhất định so với diễn biến lịch sử thực tế.')

        view = st.radio('Chọn giai đoạn hiển thị trên biểu đồ:', ['Toàn bộ sự kiện', '06–10/05 · Giai đoạn đầu khủng hoảng', '11–15/05 · Giai đoạn sụp đổ'], horizontal=True)
        boundaries = {
            'Toàn bộ sự kiện': ('2022-05-06T00:00Z', '2022-05-16T00:00Z'),
            '06–10/05 · Giai đoạn đầu khủng hoảng': ('2022-05-06T00:00Z', '2022-05-11T00:00Z'),
            '11–15/05 · Giai đoạn sụp đổ': ('2022-05-11T00:00Z', '2022-05-16T00:00Z')
        }
        window = tuple(pd.Timestamp(value) for value in boundaries[view])
        model_label = 'Bản tốt nhất · v4' if is_best else 'Bộ khớp 06–10/05'

        left, right = st.columns(2)
        left.plotly_chart(chart({model_label: base}, 'ust_price', 'Diễn biến giá UST so với thực tế (USD)', window=window), width='stretch')
        right.plotly_chart(chart({model_label: base}, 'anchor_deposits', 'Lượng tiền gửi Anchor so với thực tế (UST)', window=window), width='stretch')
        left.plotly_chart(chart({model_label: base}, 'luna_price', 'Diễn biến giá LUNA so với thực tế (USD, thang log)', log=True, window=window), width='stretch')
        right.plotly_chart(chart({model_label: base}, 'luna_supply', 'Tổng cung LUNA so với thực tế (thang log)', log=True, window=window), width='stretch')

        st.subheader('Đánh giá mức độ khớp giữa mô hình và dữ liệu lịch sử')
        if 'gates' in fit:
            st.dataframe(
                pd.DataFrame([{'Chỉ số': label, 'Sai số': float(fit[key]), 'Ngưỡng tối đa': limit, 'Kết luận': 'Đạt' if fit['gates'][key] else 'Chưa đạt'} for key, label, limit in GATE_SPECS]),
                hide_index=True, width='stretch',
                column_config={'Sai số': st.column_config.NumberColumn(format='%.6f'), 'Ngưỡng tối đa': st.column_config.NumberColumn(format='%.3f')}
            )
        if 'observed_depeg_utc' in fit and 'predicted_depeg_utc' in fit:
            observed_onset = pd.Timestamp(fit['observed_depeg_utc']).tz_convert('UTC')
            predicted_onset = pd.Timestamp(fit['predicted_depeg_utc']).tz_convert('UTC')
            st.caption(f"Thời điểm mất peg kéo dài: dữ liệu thực tế ghi nhận lúc {observed_onset:%d/%m %H:%M} UTC, mô hình dự đoán lúc {predicted_onset:%d/%m %H:%M} UTC — chênh lệch {fit['depeg_signed_error_hours']:+.2f} giờ. (Định nghĩa mất peg: giá UST dưới $0,98 liên tục trong ít nhất 1 giờ.)")

# -------------------------------------------------------------------------------------------------
# TAB 3: THỬ CỨU TRỢ (LEGACY POLICY TAB)
# -------------------------------------------------------------------------------------------------
if show_legacy and policy_tab is not None:
    with policy_tab:
        controls, results = st.columns([1, 2.5], gap='large')
        with controls:
            st.subheader('Thiết lập phương án can thiệp')
            with st.form('policy_form'):
                actions = st.multiselect('Biện pháp can thiệp:', options=['Mua UST', 'Bổ sung thanh khoản', 'Điều chỉnh native swap', 'Giới hạn rút Anchor'], default=['Mua UST'])
                trigger = st.radio('Điều kiện kích hoạt:', options=['Ngưỡng giá', 'Thời điểm cố định'], horizontal=True)
                threshold = st.slider('Ngưỡng giá UST kích hoạt (USD)', .90, .999, .990, .001)
                date = st.date_input('Ngày bắt đầu can thiệp', value=pd.Timestamp('2022-05-08').date(), min_value=pd.Timestamp('2022-05-07').date(), max_value=pd.Timestamp('2022-05-15').date())
                hour = st.slider('Giờ bắt đầu (UTC)', 0, 23, 0)
                delay = st.selectbox('Độ trễ thực thi', options=[15, 60, 360], index=1, format_func=lambda x: f'{x} phút')
                duration = st.slider('Thời gian can thiệp (giờ)', 6, 192, 120, 6)
                spend = st.slider('Hạn mức chi mỗi giờ (triệu USD)', 1, 200, 50, 1)
                allocation = st.slider('Tỷ lệ phân bổ vốn cho mua UST', 0., 1., .7, .05)
                pool = st.slider('Hệ số nhân kích thước virtual pool', .5, 8., 2., .5)
                recovery = st.select_slider('Tốc độ phục hồi pool (hệ số)', options=[.25, .5, 1., 2., 4.], value=.5)
                gate = st.slider('Giới hạn rút tiền hàng ngày (% tổng tiền gửi)', 1, 100, 20, 1)
                funding = st.selectbox('Thời điểm quỹ khả dụng', options=['late', 'early'], format_func=lambda x: 'Muộn — thận trọng' if x == 'late' else 'Sớm — giả định thuận lợi')
                funder = st.selectbox('Nguồn vốn cứu trợ', options=['both', 'LFG', 'TFL'], format_func=lambda x: 'LFG + TFL (cả hai)' if x == 'both' else x)
                stochastic = st.checkbox('Cho phép yếu tố ngẫu nhiên', value=True)
                seed = st.number_input('Seed', min_value=0, max_value=100000, value=42, step=1)
                stress = st.checkbox('Chạy thêm 7 ngày kiểm tra sau khi dừng hỗ trợ', value=True)
                submitted = st.form_submit_button('Chạy mô phỏng', type='primary', width='stretch')

            st.caption('Ngân sách cứu trợ được tính từ dữ liệu kiểm toán thực tế, không cho phép nhập tùy ý. Các biện pháp can thiệp thay thế cho phần cứu trợ lịch sử và chia sẻ cùng một sổ tài sản.')
            uploaded = st.file_uploader('Nạp cấu hình từ file JSON', type='json')
            import_run = st.button('Chạy với cấu hình đã nạp', disabled=uploaded is None)

        if submitted:
            mapping = {'Mua UST': 'buy_ust', 'Bổ sung thanh khoản': 'liquidity', 'Điều chỉnh native swap': 'native_swap', 'Giới hạn rút Anchor': 'withdrawal_gate'}
            policies = []
            for name in actions:
                fraction = (allocation if name == 'Mua UST' else 1 - allocation) if 'Mua UST' in actions and 'Bổ sung thanh khoản' in actions else 1.
                policies.append(PolicyConfig(mapping[name], trigger='price' if trigger == 'Ngưỡng giá' else 'time', threshold=threshold, start_time=f'{date}T{hour:02d}:00:00Z', delay_minutes=delay, duration_hours=duration, max_spend_per_hour=spend * 1e6, allocation_fraction=fraction, pool_multiplier=pool, recovery_multiplier=recovery, withdrawal_fraction_per_day=gate / 100, funder=funder))
            st.session_state['scenario'] = ScenarioConfig(name='dashboard_policy', mode='counterfactual', seed=int(seed), stochastic=stochastic, funding_timing=funding, stress_days=7 if stress else 0, params=params, policies=policies).to_dict()

        if import_run:
            try:
                loaded = ScenarioConfig.from_dict(json.load(uploaded))
                st.session_state['scenario'] = loaded.to_dict()
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                st.error(f'Cấu hình không hợp lệ: {e}')

        with results:
            if 'scenario' not in st.session_state:
                st.info('Vui lòng chọn các biện pháp can thiệp ở cột bên trái và bấm "Chạy mô phỏng". Kết quả sẽ được so sánh với kịch bản không can thiệp và diễn biến lịch sử thực tế.')
            else:
                policy_config = ScenarioConfig.from_dict(st.session_state['scenario'])
                with st.spinner('Đang chạy mô phỏng và kiểm tra sổ tài sản…'):
                    trial, metrics, ledger = cached_run(json.dumps(policy_config.to_dict(), sort_keys=True), source_key)
                    reference_config = replace(policy_config, name='matched_historical', mode='historical', funding_timing='early', policies=[])
                    matched_base, _, _ = cached_run(json.dumps(reference_config.to_dict(), sort_keys=True), source_key)
                    control_config = replace(policy_config, name='matched_no_rescue', mode='no_rescue', policies=[])
                    matched_control, control_metrics, _ = cached_run(json.dumps(control_config.to_dict(), sort_keys=True), source_key)

                st.session_state['last_result'] = (trial, metrics, ledger)
                st.session_state['matched_control_config'] = control_config.to_dict()
                st.subheader(metrics['classification'])
                cols = st.columns(3)
                cols[0].metric('Giá UST cuối kỳ', f'{metrics["final_ust_price"]:.4f} USD')
                cols[1].metric('Tổng vốn đã chi', f'{metrics["support_spent_usd"]/1e9:.2f} tỷ USD')
                cols[2].metric('Giữ peg liên tục lâu nhất', f'{metrics["peg_hours_longest"]:.1f} giờ')

                st.plotly_chart(chart({'Lịch sử': matched_base, 'Không cứu trợ': matched_control, 'Phương án thử nghiệm': trial}, 'ust_price', 'So sánh giá UST: lịch sử, không can thiệp và phương án thử nghiệm', show_corridor=True), width='stretch')
                st.plotly_chart(chart({'Lịch sử': matched_base, 'Không cứu trợ': matched_control, 'Phương án thử nghiệm': trial}, 'luna_supply', 'Tổng cung LUNA: so sánh 3 kịch bản', log=True), width='stretch')


