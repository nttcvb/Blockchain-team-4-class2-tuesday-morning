from pathlib import Path
import base64
import io
import json

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


PROJECT = Path(__file__).resolve().parents[1]
CORE_CHARTS = {
    'Giá UST / USD': 'ust_price',
    'Tiền gửi Anchor / UST': 'anchor_deposits',
    'Giá LUNA / USD': 'luna_price',
    'Nguồn cung LUNA': 'luna_supply',
}


def _forbid_simulation(monkeypatch):
    import luna_sim.engine

    def forbidden(*args, **kwargs):
        pytest.fail('Dashboard trình bày kết quả đã lưu không được chạy mô phỏng mới.')

    monkeypatch.setattr(luna_sim.engine, 'simulate', forbidden)


def _app():
    return AppTest.from_file(str(PROJECT / 'app.py'), default_timeout=60).run()


def _figures(at):
    figures = [json.loads(element.proto.spec) for element in at.get('plotly_chart')]
    return {figure['layout'].get('title', {}).get('text'): figure for figure in figures}


def _plotly_array(value):
    if isinstance(value, dict) and 'bdata' in value:
        array = np.frombuffer(base64.b64decode(value['bdata']), dtype=value['dtype'])
        if value.get('shape'):
            array = array.reshape(tuple(map(int, value['shape'].split(','))))
        return array
    return np.asarray(value)


def _assert_chart_data(at, split, start='2022-05-06T00:00Z', end='2022-05-16T00:00Z'):
    from luna_sim.data import load_targets
    saved = pd.read_parquet(PROJECT / 'outputs' / 'calibration' / f'trajectory_{split}.parquet')
    observed = load_targets()
    figures = _figures(at)
    for title, field in CORE_CHARTS.items():
        figure = figures[title]
        assert len(figure['data']) == 2
        for trace, frame in zip(figure['data'], [observed, saved]):
            selected = frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index < pd.Timestamp(end))]
            actual_time = pd.DatetimeIndex(pd.to_datetime(_plotly_array(trace['x']), utc=True))
            pd.testing.assert_index_equal(actual_time, selected.index.tz_convert('UTC'), check_names=False, exact=False)
            np.testing.assert_array_equal(_plotly_array(trace['y']), selected[field].to_numpy())
            assert trace.get('connectgaps') is False
        expected_axis = 'log' if field in {'luna_price', 'luna_supply'} else 'linear'
        assert figure['layout'].get('yaxis', {}).get('type', 'linear') == expected_axis


@pytest.mark.parametrize('split', ['all', 'train'])
def test_saved_presentation_loads_exact_completed_result_without_simulating(monkeypatch, split):
    _forbid_simulation(monkeypatch)
    at = _app()
    assert not at.exception
    selected = next(control for control in at.selectbox if control.label == 'Bộ tham số tái hiện lịch sử')
    assert selected.value == 'Bản tốt nhất hiện có · khớp toàn sự kiện (v4)'
    if split == 'train':
        selected.select('Hiệu chỉnh 06–10/05; kiểm định 11–15/05').run()
        assert not at.exception
    report = json.loads((PROJECT / 'outputs' / 'calibration' / f'report_{split}.json').read_text(encoding='utf-8'))
    presentation = at.session_state['presentation']
    assert presentation['loaded_saved_result'] is True
    assert presentation['split'] == split
    assert presentation['selected_run_id'] == report['optimizer']['run_id']
    assert presentation['trajectory_path'] == str(PROJECT / 'outputs' / 'calibration' / f'trajectory_{split}.parquet')
    assert presentation['parameter_sha256'] == report['parameter_sha256']
    assert [tab.label for tab in at.tabs] == ['01 · Đối chiếu lịch sử', '02 · Báo cáo tái hiện']
    assert not at.multiselect
    assert not any(button.label == 'Chạy thí nghiệm' for button in at.button)
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics['Sai số giá UST (MAE)'] == f'{report["all"]["ust_mae"]:.4f} USD'
    assert metrics['Sai số tiền gửi Anchor'] == f'{report["all"]["deposit_nrmse"]:.2%}'
    assert metrics['RMSE log giá LUNA'] == f'{report["all"]["luna_price_log_rmse"]:.4f}'
    assert metrics['Ngưỡng tái hiện đạt'] == f'{sum(report["all"]["gates"].values())}/6'
    if split == 'all':
        assert metrics['Ngưỡng tái hiện đạt'] == '1/6'
        assert any('đối chiếu trong mẫu' in element.value for element in at.info)
        assert any('09/05 18:15 UTC' in element.value and '09/05 19:00 UTC' in element.value for element in at.caption)
    else:
        assert any('kiểm định giữ nguyên tham số' in element.value for element in at.info)
    _assert_chart_data(at, split)


def test_saved_presentation_filters_exact_series_without_changing_all_period_metrics(monkeypatch):
    _forbid_simulation(monkeypatch)
    at = _app()
    initial_metrics = {metric.label: metric.value for metric in at.metric}
    run_id = at.session_state['presentation']['selected_run_id']
    for label, start, end in [
        ('06–10/05 · giai đoạn đầu', '2022-05-06T00:00Z', '2022-05-11T00:00Z'),
        ('11–15/05 · vòng xoáy sụp đổ', '2022-05-11T00:00Z', '2022-05-16T00:00Z'),
    ]:
        next(control for control in at.radio if control.label == 'Cửa sổ xem biểu đồ').set_value(label).run()
        assert not at.exception
        assert at.session_state['presentation']['selected_run_id'] == run_id
        assert {metric.label: metric.value for metric in at.metric} == initial_metrics
        _assert_chart_data(at, 'all', start, end)


@pytest.mark.parametrize('problem', ['missing_trajectory', 'tampered_trajectory', 'stale_execution'])
def test_saved_presentation_refuses_invalid_publication_without_fallback(monkeypatch, problem):
    _forbid_simulation(monkeypatch)
    trajectory = PROJECT / 'outputs' / 'calibration' / 'trajectory_all.parquet'
    status = PROJECT / 'outputs' / 'calibration' / 'calibration_status_all.json'
    if problem == 'missing_trajectory':
        original_open = Path.open

        def missing_open(path, *args, **kwargs):
            if path == trajectory:
                raise FileNotFoundError(str(path))
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'open', missing_open)
    elif problem == 'tampered_trajectory':
        original_open = Path.open
        data = trajectory.read_bytes() + b'tampered publication'

        def altered_open(path, *args, **kwargs):
            if path == trajectory and (args[0] if args else kwargs.get('mode', 'r')) == 'rb':
                return io.BytesIO(data)
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'open', altered_open)
    else:
        original_read = Path.read_text
        payload = json.loads(status.read_text(encoding='utf-8'))
        payload['run_id'] = 'unfinished_other_run'
        monkeypatch.setattr(Path, 'read_text', lambda path, *args, **kwargs: json.dumps(payload) if path == status else original_read(path, *args, **kwargs))
    at = _app()
    assert not at.exception
    assert any('Kết quả đã lưu chưa được xác nhận' in element.value for element in at.error)
    assert not at.get('plotly_chart')
    assert 'presentation' not in at.session_state


def test_saved_presentation_clears_prior_identity_after_same_session_invalidation(monkeypatch):
    _forbid_simulation(monkeypatch)
    at = _app()
    assert not at.exception
    assert at.session_state['presentation']['loaded_saved_result'] is True
    status = PROJECT / 'outputs' / 'calibration' / 'calibration_status_all.json'
    original_read = Path.read_text
    payload = json.loads(status.read_text(encoding='utf-8'))
    payload['status'] = 'running'
    monkeypatch.setattr(Path, 'read_text', lambda path, *args, **kwargs: json.dumps(payload) if path == status else original_read(path, *args, **kwargs))
    at.run()
    assert not at.exception
    assert any('Kết quả đã lưu chưa được xác nhận' in element.value for element in at.error)
    assert not at.get('plotly_chart')
    assert 'presentation' not in at.session_state


def test_dashboard_defaults_to_history_and_legacy_policy_opt_in_produces_result():
    app=Path(__file__).resolve().parents[1]/'app.py'
    at=AppTest.from_file(str(app),default_timeout=60).run()
    assert not at.exception
    assert [tab.label for tab in at.tabs]==['01 · Đối chiếu lịch sử','02 · Báo cáo tái hiện']
    assert at.title[0].value=='Tái hiện vụ sụp đổ Luna–UST'
    legacy=next(c for c in at.checkbox if c.label=='Mở công cụ chính sách cũ')
    assert legacy.value is False
    assert not at.multiselect
    assert not any(b.label=='Chạy thí nghiệm' for b in at.button)
    assert 'scenario' not in at.session_state
    legacy.set_value(True).run()
    assert not at.exception
    assert [tab.label for tab in at.tabs]==['01 · Đối chiếu lịch sử','02 · Thử cứu trợ','03 · Báo cáo tái hiện']
    button=next(b for b in at.button if b.label=='Chạy thí nghiệm')
    button.click().run()
    assert not at.exception
    assert 'last_result' in at.session_state
    t,m,ledger=at.session_state['last_result']
    assert len(t)>959  # Includes the seven-day no-new-support tail.
    assert m['engine']=='cadcad'
    assert m['btc_sold']<=80081+.001
    assert len(ledger)>0
    control=at.session_state['matched_control_config']
    trial=at.session_state['scenario']
    assert control['mode']=='no_rescue' and control['policies']==[]
    for key in ['params','seed','stochastic','funding_timing','dt_minutes','end','stress_days']:
        assert control[key]==trial[key]


def test_combination_uses_four_controls_and_shared_budget():
    app=Path(__file__).resolve().parents[1]/'app.py'
    at=AppTest.from_file(str(app),default_timeout=60).run()
    next(c for c in at.checkbox if c.label=='Mở công cụ chính sách cũ').set_value(True).run()
    assert not at.exception
    choices=['Mua UST','Bổ sung thanh khoản','Điều chỉnh native swap','Giới hạn rút Anchor']
    next(control for control in at.multiselect if control.label=='Chính sách').set_value(choices)
    next(b for b in at.button if b.label=='Chạy thí nghiệm').click().run()
    assert not at.exception
    config=at.session_state['scenario']
    assert len(config['policies'])==4
    assert sum(p['allocation_fraction'] for p in config['policies'] if p['action'] in ['buy_ust','liquidity'])==1.
    t,m,_=at.session_state['last_result']
    assert m['tfl_own_contribution_usd']<=613616889.001
