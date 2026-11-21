from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_dashboard_runs_and_policy_form_produces_result():
    app=Path(__file__).resolve().parents[1]/'app.py'
    at=AppTest.from_file(str(app),default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs)==3
    assert at.title[0].value=='Luna–UST: có thể cứu vãn?'
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
    choices=['Mua UST','Bổ sung thanh khoản','Điều chỉnh native swap','Giới hạn rút Anchor']
    at.multiselect[0].set_value(choices)
    next(b for b in at.button if b.label=='Chạy thí nghiệm').click().run()
    assert not at.exception
    config=at.session_state['scenario']
    assert len(config['policies'])==4
    assert sum(p['allocation_fraction'] for p in config['policies'] if p['action'] in ['buy_ust','liquidity'])==1.
    t,m,_=at.session_state['last_result']
    assert m['tfl_own_contribution_usd']<=613616889.001
