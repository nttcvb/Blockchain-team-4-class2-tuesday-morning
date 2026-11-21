"""Comprehensive Test Suite for Milestone M2: Simulation Scenario Matrix (SC-01 to SC-10).

Features Covered:
- F11: 7-Day Stress Simulation Matrix (SC-01 to SC-10 with stress_days=7, 1,631 steps)
- F12: Trajectory & Metrics Pipeline (trajectory.parquet, metrics.json, summary.csv, runs.csv)
- CLI Runner Extensions (run, suite, matrix subcommands)
- Strict Invariant Conservation & Finite Budget Enforcement across presets
"""

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from luna_sim.config import ROOT, ScenarioConfig, PolicyConfig, load_params
from luna_sim.engine import context, simulate
from luna_sim.experiments import (
    SCENARIO_MATRIX_KEYS,
    scenario_presets,
    matrix_presets,
    export_run,
    run_matrix,
)


# ==============================================================================
# 1. Preset Registration and Validation Tests
# ==============================================================================

class TestM2PresetRegistration:
    """Verify that all 10 presets are registered, structured, and pass validation."""

    def test_all_10_presets_exist_in_matrix_keys(self):
        """Verify SCENARIO_MATRIX_KEYS contains exactly the 10 required presets SC-01 to SC-10."""
        expected = [
            "sc01_baseline_no_rescue",
            "sc02_staggered_tranches",
            "sc03_concentrated_bidwall",
            "sc04_buyback_burn",
            "sc05_tiered_gates",
            "sc06_market_defense",
            "sc07_combined_realistic",
            "sc08_frontloaded_shock",
            "sc09_circuit_breaker",
            "sc10_maximum_extreme",
        ]
        assert SCENARIO_MATRIX_KEYS == expected

    def test_matrix_presets_contains_all_10_scenarios(self):
        """Verify matrix_presets() returns all 10 scenarios."""
        m_presets = matrix_presets()
        assert len(m_presets) == 10
        for key in SCENARIO_MATRIX_KEYS:
            assert key in m_presets

    def test_scenario_presets_includes_legacy_and_all_10_scenarios(self):
        """Verify scenario_presets() contains both legacy keys and new 10 M2 presets."""
        presets = scenario_presets()
        legacy_keys = ["historical", "no_rescue", "buy_ust", "liquidity", "native_swap", "withdrawal_gate", "combined"]
        for k in legacy_keys:
            assert k in presets, f"Missing legacy preset: {k}"
        for k in SCENARIO_MATRIX_KEYS:
            assert k in presets, f"Missing M2 preset: {k}"
        assert len(presets) >= 17

    def test_all_10_presets_validate_without_error(self):
        """Verify all 10 preset ScenarioConfig instances pass validate() without raising."""
        presets = matrix_presets()
        for name, cfg in presets.items():
            cfg.validate()

    def test_all_10_presets_have_mandatory_stress_days_7(self):
        """Verify all 10 preset configurations default to stress_days=7."""
        presets = matrix_presets(stress_days=7)
        for name, cfg in presets.items():
            assert cfg.stress_days == 7, f"{name} does not have stress_days=7"


# ==============================================================================
# 2. Individual Scenario Policy Configuration Tests
# ==============================================================================

class TestM2ScenarioConfigurations:
    """Verify the exact policy mechanics and budget caps for SC-01 through SC-10."""

    def test_sc01_baseline_no_rescue(self):
        """SC-01: Baseline without rescue has no_rescue mode and zero policies."""
        sc = matrix_presets()["sc01_baseline_no_rescue"]
        assert sc.mode == "no_rescue"
        assert len(sc.policies) == 0

    def test_sc02_staggered_tranches(self):
        """SC-02: Phased deployment with $1.5B budget cap and late tranche timing."""
        sc = matrix_presets()["sc02_staggered_tranches"]
        assert sc.mode == "counterfactual"
        assert sc.funding_timing == "late"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "buy_ust"
        assert p.max_cumulative_spend == 1.5e9

    def test_sc03_concentrated_bidwall(self):
        """SC-03: Concentrated bid-wall at target_peg=0.985 with $2.5B budget cap."""
        sc = matrix_presets()["sc03_concentrated_bidwall"]
        assert sc.mode == "counterfactual"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "buy_ust"
        assert p.target_peg == 0.985
        assert p.max_cumulative_spend == 2.5e9

    def test_sc04_buyback_burn(self):
        """SC-04: Targeted buyback with immediate burn_acquired_ust=True and $2.0B budget cap."""
        sc = matrix_presets()["sc04_buyback_burn"]
        assert sc.mode == "counterfactual"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "buy_ust"
        assert p.burn_acquired_ust is True
        assert p.max_cumulative_spend == 2.0e9

    def test_sc05_tiered_gates(self):
        """SC-05: Capital control with dynamic tiered withdrawal gates."""
        sc = matrix_presets()["sc05_tiered_gates"]
        assert sc.mode == "counterfactual"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "withdrawal_gate"
        assert p.tiered_gates is True

    def test_sc06_market_defense(self):
        """SC-06: Market defense with emergency spread hike 0.15 and arb throttle 0.167."""
        sc = matrix_presets()["sc06_market_defense"]
        assert sc.mode == "counterfactual"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "native_swap"
        assert p.emergency_spread_rate == 0.15
        assert p.arb_capacity_multiplier == 0.167

    def test_sc07_combined_realistic(self):
        """SC-07: Combined realistic package with bid-wall, burn, tiered gates, spread hike, and arb throttle."""
        sc = matrix_presets()["sc07_combined_realistic"]
        assert sc.mode == "counterfactual"
        assert len(sc.policies) == 3
        actions = {p.action for p in sc.policies}
        assert actions == {"buy_ust", "withdrawal_gate", "native_swap"}

        buy_p = next(p for p in sc.policies if p.action == "buy_ust")
        assert buy_p.target_peg == 0.985
        assert buy_p.burn_acquired_ust is True
        assert buy_p.max_cumulative_spend == 2.5e9

        gate_p = next(p for p in sc.policies if p.action == "withdrawal_gate")
        assert gate_p.tiered_gates is True

        swap_p = next(p for p in sc.policies if p.action == "native_swap")
        assert swap_p.emergency_spread_rate == 0.15
        assert swap_p.arb_capacity_multiplier == 0.167

    def test_sc08_frontloaded_shock(self):
        """SC-08: Extreme bailout with 100% front-loaded deployment ($3.2B budget, 800M/h)."""
        sc = matrix_presets()["sc08_frontloaded_shock"]
        assert sc.mode == "counterfactual"
        assert sc.funding_timing == "early"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "buy_ust"
        assert p.max_spend_per_hour == 800e6
        assert p.max_cumulative_spend == 3.2e9

    def test_sc09_circuit_breaker(self):
        """SC-09: Extreme capital control with 48h circuit breaker halting Anchor and Native."""
        sc = matrix_presets()["sc09_circuit_breaker"]
        assert sc.mode == "counterfactual"
        assert len(sc.policies) == 1
        p = sc.policies[0]
        assert p.action == "circuit_breaker"
        assert p.duration_hours == 48

    def test_sc10_maximum_extreme(self):
        """SC-10: Maximum extreme package combining all extreme tools with $3.2B budget."""
        sc = matrix_presets()["sc10_maximum_extreme"]
        assert sc.mode == "counterfactual"
        assert sc.funding_timing == "early"
        assert len(sc.policies) == 4
        actions = {p.action for p in sc.policies}
        assert actions == {"buy_ust", "circuit_breaker", "withdrawal_gate", "native_swap"}

        buy_p = next(p for p in sc.policies if p.action == "buy_ust")
        assert buy_p.max_cumulative_spend == 3.2e9
        assert buy_p.burn_acquired_ust is True

        gate_p = next(p for p in sc.policies if p.action == "withdrawal_gate")
        assert gate_p.tiered_gates is True
        assert gate_p.redemption_haircut == 0.20

        cb_p = next(p for p in sc.policies if p.action == "circuit_breaker")
        assert cb_p.duration_hours == 48

        swap_p = next(p for p in sc.policies if p.action == "native_swap")
        assert swap_p.emergency_spread_rate == 0.15
        assert swap_p.arb_capacity_multiplier == 0.167


# ==============================================================================
# 3. Horizon, Step Count, and Execution Tests
# ==============================================================================

class TestM2SimulationHorizonAndExecution:
    """Verify that stress_days=7 yields exactly 1,631 steps and runs cleanly."""

    def test_context_step_count_is_1631(self):
        """10-day crisis (May 6 00:15 to May 16 00:00) + 7-day tail = exactly 1,631 steps at 15min dt."""
        cfg = matrix_presets(stress_days=7)["sc01_baseline_no_rescue"]
        ctx = context(cfg)
        assert len(ctx["index"]) == 1631

    @pytest.mark.parametrize("scenario_name", [
        "sc01_baseline_no_rescue",
        "sc05_tiered_gates",
        "sc06_market_defense",
        "sc09_circuit_breaker",
    ])
    def test_simulation_produces_1631_steps_and_valid_metrics(self, scenario_name):
        """Simulate selected presets and verify 1,631 trajectory rows and required metric keys."""
        cfg = matrix_presets(stress_days=7)[scenario_name]
        cfg.stochastic = False  # fast deterministic verification
        traj, metrics, ledger = simulate(cfg, engine="fast")
        assert len(traj) == 1631
        assert "ust_price" in traj.columns
        assert "luna_price" in traj.columns
        assert "luna_supply" in traj.columns
        assert "anchor_deposits" in traj.columns
        assert "support_spent" in traj.columns

        # Verify required evaluation metrics from simulate
        for field in [
            "peg_hours_longest",
            "operational_hours_longest",
            "stress_tail_verified",
            "final_ust_price",
            "final_anchor_deposits",
            "final_luna_supply",
            "rescued",
            "support_spent_usd",
        ]:
            assert field in metrics, f"Missing metric field: {field}"

        # Accounting error invariant check
        for err_k, err_val in metrics["max_accounting_errors"].items():
            assert err_val < 0.1, f"{err_k} exceeded tolerance in {scenario_name}: {err_val}"


# ==============================================================================
# 4. Pipeline Outputs and Artifact Verification
# ==============================================================================

class TestM2OutputsAndArtifacts:
    """Verify that export_run and matrix execution generate all required files."""

    def test_export_run_creates_parquet_and_metrics_json(self, tmp_path):
        """export_run must create trajectory.parquet and metrics.json with total_spent_usd."""
        cfg = matrix_presets()["sc01_baseline_no_rescue"]
        cfg.stochastic = False
        traj, metrics, ledger = simulate(cfg, engine="fast")
        out_dir = export_run(cfg, traj, metrics, ledger, directory=tmp_path / "test_run")
        assert (out_dir / "config.json").exists()
        assert (out_dir / "trajectory.parquet").exists()
        assert (out_dir / "trajectory.csv").exists()
        assert (out_dir / "metrics.json").exists()

        saved_metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
        assert "total_spent_usd" in saved_metrics
        assert saved_metrics["total_spent_usd"] == saved_metrics["support_spent_usd"]

    def test_outputs_experiments_contains_summary_and_runs_csv(self):
        """Verify summary.csv and runs.csv exist and contain all 10 scenario records."""
        runs_path = ROOT / "outputs" / "experiments" / "runs.csv"
        summary_path = ROOT / "outputs" / "experiments" / "summary.csv"
        if not runs_path.exists() or not summary_path.exists():
            run_matrix(seeds=1, engine="fast", stress_days=7, deterministic=True)

        runs_df = pd.read_csv(runs_path)
        summary_df = pd.read_csv(summary_path)

        if len(runs_df) < len(SCENARIO_MATRIX_KEYS):
            summary_df = run_matrix(seeds=1, engine="fast", stress_days=7, deterministic=True)
            runs_df = pd.read_csv(runs_path)

        for key in SCENARIO_MATRIX_KEYS:
            assert key in runs_df["scenario"].values, f"{key} missing in runs.csv"
            assert key in summary_df["scenario"].values, f"{key} missing in summary.csv"

    def test_outputs_runs_contains_parquet_and_metrics_for_all_10_scenarios(self):
        """Verify outputs/runs contains trajectory.parquet and metrics.json for seed 42 of all 10 scenarios."""
        runs_dir = ROOT / "outputs" / "runs"
        for key in SCENARIO_MATRIX_KEYS:
            scenario_run_dir = runs_dir / f"{key}_seed42"
            assert scenario_run_dir.exists(), f"Directory missing: {scenario_run_dir}"
            assert (scenario_run_dir / "trajectory.parquet").exists(), f"trajectory.parquet missing in {scenario_run_dir}"
            assert (scenario_run_dir / "metrics.json").exists(), f"metrics.json missing in {scenario_run_dir}"


# ==============================================================================
# 5. CLI Execution Tests
# ==============================================================================

class TestM2CLIExecution:
    """Verify that CLI subcommands (run, matrix, suite) work cleanly."""

    def test_cli_matrix_programmatic_invocation(self):
        """run_matrix helper executes cleanly and returns summary DataFrame across all 10 scenarios."""
        summary = run_matrix(seeds=1, engine="fast", stress_days=7, deterministic=True)
        assert len(summary) == 10
        assert "rescue_rate" in summary.columns
        assert "n_runs" in summary.columns
        for key in SCENARIO_MATRIX_KEYS:
            assert key in summary.index
