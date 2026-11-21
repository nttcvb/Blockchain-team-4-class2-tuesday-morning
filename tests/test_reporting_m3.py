"""Test suite for Milestone M3: Quantitative Evaluation Report & Dashboard Modernization."""
from pathlib import Path
import json
import pytest
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
OUTPUTS = PROJECT / 'outputs'
REPORT_PATH = OUTPUTS / 'BAILOUT_EVALUATION_REPORT_VI.md'
ANALYSIS_PATH = OUTPUTS / 'analysis_report.md'

REQUIRED_SCENARIO_KEYS = [
    'sc01_baseline_no_rescue',
    'sc02_staggered_tranches',
    'sc03_concentrated_bidwall',
    'sc04_buyback_burn',
    'sc05_tiered_gates',
    'sc06_market_defense',
    'sc07_combined_realistic',
    'sc08_frontloaded_shock',
    'sc09_circuit_breaker',
    'sc10_maximum_extreme',
]


class TestBailoutEvaluationReport:
    """Verifies that the analytical evaluation report meets all quantitative and structural requirements."""

    def test_report_files_exist_and_sufficient_size(self):
        assert REPORT_PATH.exists(), f"Missing primary report at {REPORT_PATH}"
        assert ANALYSIS_PATH.exists(), f"Missing mirrored analysis report at {ANALYSIS_PATH}"
        assert REPORT_PATH.stat().st_size > 8000, "Primary report is unexpectedly small"
        assert ANALYSIS_PATH.stat().st_size > 8000, "Mirrored report is unexpectedly small"

    def test_report_mirrored_content(self):
        primary_text = REPORT_PATH.read_text(encoding='utf-8')
        mirrored_text = ANALYSIS_PATH.read_text(encoding='utf-8')
        assert primary_text == mirrored_text, "Mirrored report does not match primary report"

    def test_report_contains_all_10_scenario_keys(self):
        text = REPORT_PATH.read_text(encoding='utf-8')
        for sc in REQUIRED_SCENARIO_KEYS:
            assert sc in text, f"Scenario {sc} missing from BAILOUT_EVALUATION_REPORT_VI.md"

    def test_report_contains_definitive_insolvency_conclusion(self):
        text = REPORT_PATH.read_text(encoding='utf-8')
        assert "KHÔNG THỂ CỨU VÃN" in text or "Không thể cứu vãn" in text
        assert "Insolvent" in text or "insolvent" in text or "Unsalvageable" in text or "unsalvageable" in text
        assert "rescued = False" in text or "rescued = false" in text or "Tỷ lệ cứu vãn" in text

    def test_report_contains_all_required_mechanism_sections(self):
        text = REPORT_PATH.read_text(encoding='utf-8')
        # 1. Executive summary
        assert "TÓM TẮT ĐIỀU HÀNH" in text or "Executive Summary" in text
        # 2. Results table
        assert "BẢNG SO SÁNH KẾT QUẢ ĐỊNH LƯỢNG" in text or "COMPREHENSIVE RESULTS" in text
        # 3. Unburned buyback vs buyback & burn
        assert "Unburned Buyback Trap" in text or "Mua lại không tiêu hủy" in text
        assert "Buyback & Burn" in text or "SC-04" in text
        # 4. Concentrated bid-wall
        assert "Concentrated Bid-Wall" in text or "tường mua tập trung" in text.lower() or "SC-03" in text
        # 5. Frontloaded shock
        assert "Frontloaded" in text or "bơm vốn đầu kỳ" in text.lower() or "SC-08" in text
        # 6. Capital controls and market defense
        assert "Capital Controls" in text or "Kiểm soát vốn" in text or "SC-05" in text
        assert "SC-06" in text and "SC-07" in text and "SC-09" in text and "SC-10" in text
        # 7. Mathematical & Invariant proof
        assert "CHỨNG MINH TOÁN HỌC" in text or "MATHEMATICAL" in text
        assert "Bất biến" in text or "Invariant" in text or "thâm hụt" in text.lower()

    def test_report_reflects_actual_empirical_metrics_from_summary(self):
        summary_path = OUTPUTS / 'experiments' / 'summary.csv'
        assert summary_path.exists(), "summary.csv does not exist"
        df = pd.read_csv(summary_path).set_index('scenario')
        text = REPORT_PATH.read_text(encoding='utf-8')

        # Check empirical values present in report
        # SC-08 peg hours (45.5)
        sc08_peg = df.loc['sc08_frontloaded_shock', 'peg_hours_longest']
        assert f"{sc08_peg:.2f}".replace('.', ',') in text or f"{sc08_peg:.1f}".replace('.', ',') in text or "45,50" in text or "45.5" in text

        # SC-10 btc sold (80,081)
        assert "80.081" in text or "80,081" in text

        # SC-07 lowest depositor loss (17.61%)
        assert "17,61%" in text or "17.61%" in text or "17.6%" in text


class TestDashboardModernizationM3:
    """Verifies that app.py is properly modernized with comparative bailout visualizations and components."""

    @pytest.fixture(scope='class')
    def app_source(self):
        app_file = PROJECT / 'app.py'
        assert app_file.exists(), f"app.py does not exist at {app_file}"
        return app_file.read_text(encoding='utf-8')

    def test_app_contains_bailout_comparison_tab(self, app_source):
        assert "So sánh chính sách cứu trợ (Bailout Policy Comparison)" in app_source
        assert "bailout_tab" in app_source

    def test_app_contains_green_corridor_spec(self, app_source):
        assert "0.98" in app_source
        assert "1.02" in app_source
        assert "rgba(34, 197, 94" in app_source or "rgba(34,197,94" in app_source
        assert "show_corridor" in app_source or "add_hrect" in app_source

    def test_app_contains_all_four_comparative_charts(self, app_source):
        # 1. UST Price
        assert "ust_price" in app_source
        # 2. Anchor Deposits
        assert "anchor_deposits" in app_source
        # 3. LUNA Supply (Log scale)
        assert "luna_supply" in app_source
        # 4. Intervention Capital
        assert "support_spent" in app_source

    def test_app_contains_scenario_matrix_keys(self, app_source):
        for sc in ['sc01_baseline_no_rescue', 'sc03_concentrated_bidwall', 'sc07_combined_realistic', 'sc08_frontloaded_shock', 'sc10_maximum_extreme']:
            assert sc in app_source, f"Key scenario {sc} missing from app.py"

    def test_app_helper_functions_load_cached_runs(self):
        import app
        summary = app.load_matrix_summary()
        assert summary is not None, "load_matrix_summary returned None"
        assert len(summary) >= 10, f"Expected at least 10 scenarios, got {len(summary)}"

        sc01_traj = app.load_scenario_run_trajectory('sc01_baseline_no_rescue')
        assert sc01_traj is not None, "load_scenario_run_trajectory returned None for sc01"
        assert len(sc01_traj) == 1631, f"Expected 1631 steps, got {len(sc01_traj)}"
        assert 'ust_price' in sc01_traj.columns

        sc10_traj = app.load_scenario_run_trajectory('sc10_maximum_extreme')
        assert sc10_traj is not None, "load_scenario_run_trajectory returned None for sc10"
        assert len(sc10_traj) == 1631
        assert 'support_spent' in sc10_traj.columns

    def test_app_chart_function_includes_corridor_shape(self):
        import app
        traj = app.load_scenario_run_trajectory('sc01_baseline_no_rescue')
        fig = app.chart({'SC-01': traj}, 'ust_price', 'Test Chart', show_corridor=True, historical=False)
        # Check shapes / hrect in layout
        shapes = fig.layout.shapes
        assert len(shapes) >= 1, "Expected corridor shape in figure layout"
        corridor_shapes = [s for s in shapes if getattr(s, 'y0', None) == 0.98 and getattr(s, 'y1', None) == 1.02]
        assert len(corridor_shapes) == 1, "Did not find expected [0.98, 1.02] corridor rectangle shape"
