"""Tier 5 Adversarial Stress Tests for Terra Luna - UST Bailout Simulation.

Adversarial Challenger Coverage:
1. Adversarial Parameter Configurations (negative values, non-finite, zero duration,
   extreme haircut 0.90, target peg bounds, circuit breaker, emergency spread).
2. Extreme Depeg Shocks & Invariants (invariants hold strictly: ust_error < 0.1,
   claim_error < 1e-4 even when P_UST -> 0 or P_LUNA -> 0).
3. Adversarial Budget Boundary Conditions (LFG BTC 80,081 spendable cap respected under
   massive front-loaded orders, >= 313 BTC retained, exact 80,394 BTC conserved).
4. Scenario Matrix Numerical Consistency (all 10 scenario trajectories and summary metrics
   free of NaN/Inf values, step counts verified).
5. Definitive Insolvency Verification (no scenario falsely reports rescued = True under
   finite capital, metrics evaluation rules strictly enforced).
6. Dashboard App Robustness (app.py helper functions handle corrupted, missing, empty,
   or malformed data gracefully without exceptions).
"""

import copy
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from luna_sim.config import ROOT, ModelParams, PolicyConfig, ScenarioConfig, load_params
from luna_sim.engine import (
    clone,
    context,
    initialize,
    observation,
    rescue,
    decisions,
    anchor,
    markets,
    accounting,
    invariants,
    simulate,
    spend,
    raise_cash,
    total_deposits,
)
from luna_sim.experiments import SCENARIO_MATRIX_KEYS, scenario_presets, matrix_presets
from luna_sim.metrics import evaluate, longest_streak, first_depeg


# ==============================================================================
# Helper fixtures & lightweight context generator
# ==============================================================================

def make_test_context(
    start: str = "2022-05-08T00:00:00Z",
    duration_minutes: int = 120,
    n_depositors: int = 40,
    policies: list = None,
    **scenario_kwargs,
):
    """Instantiate a lightweight valid simulation context for step-level adversarial tests."""
    end = (pd.Timestamp(start) + pd.Timedelta(minutes=duration_minutes)).isoformat()
    policies = policies or []
    cfg = ScenarioConfig(
        start=start,
        end=end,
        n_depositors=n_depositors,
        stochastic=False,
        policies=policies,
        **scenario_kwargs,
    )
    ctx = context(cfg)
    book = initialize(ctx)
    step_idx = int(ctx["index"].get_indexer([pd.Timestamp(start)])[0])
    book["step"] = step_idx - 1
    return ctx, book


# ==============================================================================
# 1. Adversarial Parameter Configurations
# ==============================================================================

class TestAdversarialParameterValidation:
    """Stress-test configuration validation against invalid, extreme, and malformed inputs."""

    @pytest.mark.parametrize(
        "param_name,invalid_value",
        [
            ("threshold", -0.01),
            ("threshold", 0.0),
            ("threshold", 1.01),
            ("delay_minutes", -1),
            ("duration_hours", -0.5),
            ("max_spend_per_hour", -100.0),
            ("allocation_fraction", -0.1),
            ("allocation_fraction", 1.05),
            ("pool_multiplier", 0.0),
            ("pool_multiplier", -2.0),
            ("pool_multiplier", 25.0),
            ("recovery_multiplier", 0.0),
            ("recovery_multiplier", -1.0),
            ("recovery_multiplier", 15.0),
            ("withdrawal_fraction_per_day", -0.05),
            ("withdrawal_fraction_per_day", 1.05),
            ("target_peg", 0.0),
            ("target_peg", -0.1),
            ("target_peg", 2.01),
            ("emergency_spread_rate", -0.01),
            ("emergency_spread_rate", 0.91),
            ("arb_capacity_multiplier", -0.1),
            ("redemption_haircut", -0.01),
            ("redemption_haircut", 0.91),
            ("circuit_breaker_threshold", -0.01),
            ("circuit_breaker_threshold", 1.01),
            ("max_cumulative_spend", -1.0),
        ],
    )
    def test_out_of_bounds_parameters_rejected(self, param_name, invalid_value):
        """Verify that out-of-bounds parameter values raise ValueError."""
        kwargs = {param_name: invalid_value}
        policy = PolicyConfig(action="buy_ust", **kwargs)
        with pytest.raises(ValueError):
            policy.validate()

    @pytest.mark.parametrize(
        "param_name",
        [
            "threshold",
            "delay_minutes",
            "duration_hours",
            "max_spend_per_hour",
            "allocation_fraction",
            "pool_multiplier",
            "recovery_multiplier",
            "withdrawal_fraction_per_day",
            "target_peg",
            "emergency_spread_rate",
            "arb_capacity_multiplier",
            "redemption_haircut",
            "circuit_breaker_threshold",
            "max_cumulative_spend",
        ],
    )
    def test_nan_parameters_strictly_rejected(self, param_name):
        """Verify that NaN values in any numeric parameter are strictly rejected."""
        kwargs = {param_name: math.nan}
        policy = PolicyConfig(action="buy_ust", **kwargs)
        with pytest.raises(ValueError):
            policy.validate()

    @pytest.mark.parametrize(
        "param_name",
        [
            "threshold",
            "delay_minutes",
            "duration_hours",
            "max_spend_per_hour",
            "allocation_fraction",
            "pool_multiplier",
            "recovery_multiplier",
            "withdrawal_fraction_per_day",
            "target_peg",
            "emergency_spread_rate",
            "arb_capacity_multiplier",
            "redemption_haircut",
            "circuit_breaker_threshold",
        ],
    )
    def test_infinite_parameters_rejected(self, param_name):
        """Verify that math.inf is rejected for finite rate/multiplier/time fields."""
        kwargs = {param_name: math.inf}
        policy = PolicyConfig(action="buy_ust", **kwargs)
        with pytest.raises(ValueError):
            policy.validate()

    def test_max_cumulative_spend_allows_inf_but_rejects_negative_or_nan(self):
        """math.inf is deliberately permitted for max_cumulative_spend (unconstrained stop-loss)."""
        p_inf = PolicyConfig(action="buy_ust", max_cumulative_spend=math.inf)
        p_inf.validate()  # Must not raise

        p_zero = PolicyConfig(action="buy_ust", max_cumulative_spend=0.0)
        p_zero.validate()  # Must not raise

        with pytest.raises(ValueError):
            PolicyConfig(action="buy_ust", max_cumulative_spend=-0.01).validate()
        with pytest.raises(ValueError):
            PolicyConfig(action="buy_ust", max_cumulative_spend=math.nan).validate()
        with pytest.raises(ValueError):
            PolicyConfig(action="buy_ust", max_cumulative_spend=True).validate()

    @pytest.mark.parametrize(
        "param_name",
        [
            "threshold",
            "delay_minutes",
            "duration_hours",
            "max_spend_per_hour",
            "target_peg",
            "redemption_haircut",
            "emergency_spread_rate",
        ],
    )
    def test_boolean_masquerading_as_number_rejected(self, param_name):
        """In Python, bool is a subclass of int. Ensure bool inputs are rejected for float params."""
        kwargs = {param_name: True}
        policy = PolicyConfig(action="buy_ust", **kwargs)
        with pytest.raises(ValueError):
            policy.validate()

    def test_extreme_haircut_boundary_0_90(self):
        """redemption_haircut = 0.90 is the exact allowable upper bound; >0.90 is rejected."""
        valid_haircut = PolicyConfig(action="withdrawal_gate", redemption_haircut=0.90)
        valid_haircut.validate()  # Must pass

        invalid_haircut = PolicyConfig(action="withdrawal_gate", redemption_haircut=0.9001)
        with pytest.raises(ValueError, match="redemption_haircut out of range"):
            invalid_haircut.validate()

    def test_target_peg_bounds(self):
        """target_peg allows (0, 2.0]. Boundaries must be respected."""
        p_low = PolicyConfig(action="buy_ust", target_peg=0.0001)
        p_low.validate()

        p_high = PolicyConfig(action="buy_ust", target_peg=2.0)
        p_high.validate()

        with pytest.raises(ValueError, match="target_peg out of range"):
            PolicyConfig(action="buy_ust", target_peg=0.0).validate()
        with pytest.raises(ValueError, match="target_peg out of range"):
            PolicyConfig(action="buy_ust", target_peg=2.0001).validate()

    def test_zero_duration_hours_behavior(self):
        """duration_hours = 0.0 validates but never becomes active during simulation."""
        p_zero = PolicyConfig(action="buy_ust", duration_hours=0.0)
        p_zero.validate()

        ctx, book = make_test_context(
            start="2022-05-08T00:00:00Z",
            duration_minutes=60,
            policies=[p_zero],
            mode="counterfactual",
        )
        # Force price condition trigger
        book["ust_price"] = 0.90
        book = observation(ctx, book)
        assert not book["active_policies"][0], "Zero-duration policy should not be active"

    def test_zero_delay_minutes_behavior(self):
        """delay_minutes = 0 validates and activates immediately upon trigger."""
        p_zero_delay = PolicyConfig(
            action="buy_ust",
            trigger="price",
            threshold=0.99,
            trigger_steps=1,
            delay_minutes=0,
            duration_hours=24,
        )
        p_zero_delay.validate()

        ctx, book = make_test_context(
            start="2022-05-08T00:00:00Z",
            duration_minutes=60,
            policies=[p_zero_delay],
            mode="counterfactual",
        )
        book["ust_price"] = 0.95
        book = observation(ctx, book)
        assert book["active_policies"][0], "Zero-delay policy should activate immediately"


# ==============================================================================
# 2. Extreme Depeg Shocks & Invariant Conservation
# ==============================================================================

class TestExtremeDepegShocksAndInvariants:
    """Verify that invariants strictly hold (ust_error < 0.1, claim_error < 1e-4) under collapse."""

    def test_invariants_hold_when_ust_price_approaches_zero(self):
        """Shock UST price down to extreme floor (1e-6 or 1e-12) and execute full PSUB cycle."""
        ctx, book = make_test_context(start="2022-05-08T00:00:00Z", duration_minutes=60)
        # Force extreme UST price collapse
        book["ust_price"] = 1e-6
        book["luna_price"] = 1.0

        # Execute full 6 PSUB blocks
        book = observation(ctx, book)
        book = rescue(ctx, book)
        book = decisions(ctx, book)
        book = anchor(ctx, book)
        book = markets(ctx, book)
        book = accounting(ctx, book)

        errors = invariants(ctx, book)
        assert abs(errors["ust_error"]) < 0.1, f"UST error violated: {errors['ust_error']}"
        assert abs(errors["claim_error"]) < 1e-4, f"Claim error violated: {errors['claim_error']}"
        assert abs(errors["luna_error"]) < max(0.1, book["luna_supply"] * 1e-9)
        assert abs(errors["usd_error"]) < 0.1, f"USD error violated: {errors['usd_error']}"
        assert np.isfinite(book["ust_price"]) and book["ust_price"] > 0
        assert np.isfinite(book["luna_price"]) and book["luna_price"] > 0

    def test_invariants_hold_when_luna_price_approaches_zero(self):
        """Shock LUNA price down to minimum floor (1e-12) and execute full PSUB cycle."""
        ctx, book = make_test_context(start="2022-05-08T00:00:00Z", duration_minutes=60)
        book["ust_price"] = 0.50
        book["luna_price"] = 1e-12

        book = observation(ctx, book)
        book = rescue(ctx, book)
        book = decisions(ctx, book)
        book = anchor(ctx, book)
        book = markets(ctx, book)
        book = accounting(ctx, book)

        errors = invariants(ctx, book)
        assert abs(errors["ust_error"]) < 0.1, f"UST error violated: {errors['ust_error']}"
        assert abs(errors["claim_error"]) < 1e-4, f"Claim error violated: {errors['claim_error']}"
        assert abs(errors["luna_error"]) < max(0.1, book["luna_supply"] * 1e-9)
        assert abs(errors["usd_error"]) < 0.1, f"USD error violated: {errors['usd_error']}"

    def test_invariants_hold_under_simultaneous_dual_price_collapse(self):
        """Simultaneous collapse of both P_UST -> 1e-6 and P_LUNA -> 1e-12."""
        ctx, book = make_test_context(start="2022-05-08T00:00:00Z", duration_minutes=60)
        book["ust_price"] = 1e-6
        book["luna_price"] = 1e-12

        book = observation(ctx, book)
        book = rescue(ctx, book)
        book = decisions(ctx, book)
        book = anchor(ctx, book)
        book = markets(ctx, book)
        book = accounting(ctx, book)

        errors = invariants(ctx, book)
        assert abs(errors["ust_error"]) < 0.1
        assert abs(errors["claim_error"]) < 1e-4
        assert abs(errors["luna_error"]) < max(0.1, book["luna_supply"] * 1e-9)
        assert abs(errors["usd_error"]) < 0.1

    def test_extreme_haircut_90_percent_burn_and_claim_conservation(self):
        """90% redemption haircut: verify exact mathematical supply burn and claim balance."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            redemption_haircut=0.90,
            duration_hours=24,
            delay_minutes=0,
        )
        ctx, book = make_test_context(
            start="2022-05-08T00:00:00Z",
            duration_minutes=60,
            policies=[policy],
            mode="counterfactual",
        )
        book = observation(ctx, book)
        initial_claims = total_deposits(book)
        initial_supply = book["ust_supply"]
        queue_amount = 100e6  # 100M UST requested
        book["queue"][:] = book["deposit"] * 0.50

        book = anchor(ctx, book)
        served = book["withdraw_served"]
        assert served > 0, "Anchor should have served withdrawals"

        expected_haircut = served * 0.90
        assert abs(book["haircut_burned_ust"] - expected_haircut) < 1.0
        assert abs(book["ust_supply"] - (initial_supply - expected_haircut)) < 1.0

        errors = invariants(ctx, book)
        assert abs(errors["ust_error"]) < 0.1, f"ust_error: {errors['ust_error']}"
        assert abs(errors["claim_error"]) < 1e-4, f"claim_error: {errors['claim_error']}"

    def test_simulation_invariants_hold_across_severe_shock_trajectory(self):
        """Run a multi-step simulation under severe shocks and verify invariants at every step."""
        cfg = ScenarioConfig(
            name="adversarial_shock_test",
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-08T04:00:00Z",  # 16 steps (4 hours)
            n_depositors=50,
            stochastic=False,
            policies=[
                PolicyConfig("buy_ust", target_peg=0.985, burn_acquired_ust=True, max_spend_per_hour=100e6),
                PolicyConfig("withdrawal_gate", tiered_gates=True, redemption_haircut=0.20),
                PolicyConfig("native_swap", emergency_spread_rate=0.15, arb_capacity_multiplier=0.2),
            ],
        )
        trajectory, metrics, _ = simulate(cfg, engine="fast", keep_ledger=False)
        assert len(trajectory) == 16

        for col in ["ust_error", "luna_error", "usd_error", "claim_error"]:
            assert col in trajectory.columns
            assert np.isfinite(trajectory[col]).all(), f"Non-finite in {col}"

        assert (trajectory["ust_error"].abs() < 0.1).all()
        assert (trajectory["claim_error"].abs() < 1e-4).all()
        assert (trajectory["luna_error"].abs() < 0.1).all()
        assert (trajectory["usd_error"].abs() < 0.1).all()


# ==============================================================================
# 3. Adversarial Budget Boundary Conditions (80,081 BTC Cap & >= 313 Retained)
# ==============================================================================

class TestAdversarialBudgetBoundaryConditions:
    """Stress-test finite capital constraints against infinite demand and frontloading."""

    def test_lfg_btc_spendable_cap_under_massive_drain(self):
        """Expose engine to $100 Billion/hr order and verify BTC sold <= 80,081 and retained >= 313."""
        cfg = ScenarioConfig(
            name="massive_drain_test",
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-08T06:00:00Z",
            funding_timing="early",
            n_depositors=40,
            stochastic=False,
            policies=[
                # Unbounded spending rate: $100B per hour
                PolicyConfig(
                    action="buy_ust",
                    trigger="price",
                    threshold=0.999,
                    delay_minutes=0,
                    max_spend_per_hour=100e9,
                    duration_hours=24,
                )
            ],
        )
        trajectory, metrics, _ = simulate(cfg, engine="fast", keep_ledger=False)

        # 1. Total BTC sold cannot exceed 80,081 BTC (JS Held audit cap)
        max_btc_sold = trajectory["btc_sold"].max()
        assert max_btc_sold <= 80081.001, f"BTC sold exceeded cap: {max_btc_sold}"

        # 2. Retained BTC must be >= 313 BTC at all times
        min_retained_btc = trajectory["lfg_btc_remaining"].min()
        assert min_retained_btc >= 312.999, f"Retained BTC fell below 313: {min_retained_btc}"

        # 3. Total BTC conserved strictly at 80,394 BTC
        final_row = trajectory.iloc[-1]
        total_btc = final_row["lfg_btc_remaining"] + final_row["btc_sold"]
        assert abs(total_btc - 80394.0) < 0.001, f"Total BTC not conserved: {total_btc}"

    def test_tfl_contribution_cap_under_massive_drain(self):
        """Verify TFL contribution cap of $613,616,889 is never exceeded."""
        cfg = ScenarioConfig(
            name="tfl_cap_test",
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-08T06:00:00Z",
            funding_timing="early",
            n_depositors=40,
            stochastic=False,
            policies=[
                PolicyConfig(
                    action="buy_ust",
                    funder="TFL",
                    delay_minutes=0,
                    max_spend_per_hour=100e9,
                    duration_hours=24,
                )
            ],
        )
        trajectory, metrics, _ = simulate(cfg, engine="fast", keep_ledger=False)
        max_tfl_added = trajectory["tfl_added"].max()
        assert max_tfl_added <= 613616889.001, f"TFL added exceeded cap: {max_tfl_added}"

    def test_zero_max_cumulative_spend_blocks_spending(self):
        """When max_cumulative_spend = 0.0, zero capital is spent."""
        cfg = ScenarioConfig(
            name="zero_spend_test",
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-08T02:00:00Z",
            funding_timing="early",
            n_depositors=40,
            stochastic=False,
            policies=[
                PolicyConfig(
                    action="buy_ust",
                    delay_minutes=0,
                    max_spend_per_hour=50e6,
                    max_cumulative_spend=0.0,
                    duration_hours=24,
                )
            ],
        )
        trajectory, metrics, _ = simulate(cfg, engine="fast", keep_ledger=False)
        assert trajectory["support_spent"].max() == 0.0
        assert trajectory["btc_sold"].max() == 0.0

    def test_strict_cumulative_spend_cutoff(self):
        """When max_cumulative_spend = 100M, total spending stops at or below 100M."""
        cap = 100e6
        cfg = ScenarioConfig(
            name="cumulative_spend_cutoff_test",
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-08T06:00:00Z",
            funding_timing="early",
            n_depositors=40,
            stochastic=False,
            policies=[
                PolicyConfig(
                    action="buy_ust",
                    delay_minutes=0,
                    max_spend_per_hour=50e6,
                    max_cumulative_spend=cap,
                    duration_hours=24,
                )
            ],
        )
        trajectory, metrics, _ = simulate(cfg, engine="fast", keep_ledger=False)
        spent = trajectory["support_spent"].max()
        assert spent <= cap + 1.0, f"Spent {spent} exceeded cap {cap}"


# ==============================================================================
# 4. Scenario Matrix Trajectories & Metrics Numerical Consistency
# ==============================================================================

class TestScenarioMatrixNumericalConsistency:
    """Verify all 10 scenario runs in outputs/ for complete step counts and absence of NaN/Inf."""

    @pytest.mark.parametrize("scenario_key", SCENARIO_MATRIX_KEYS)
    def test_trajectory_exists_and_has_exact_1631_steps(self, scenario_key):
        """Every scenario run must have trajectory.parquet with 1,631 rows (17 days @ 15 min)."""
        run_dir = ROOT / "outputs" / "runs" / f"{scenario_key}_seed42"
        parquet_path = run_dir / "trajectory.parquet"
        assert parquet_path.exists(), f"Missing trajectory for {scenario_key} at {parquet_path}"

        df = pd.read_parquet(parquet_path)
        assert len(df) == 1631, f"Scenario {scenario_key} has {len(df)} steps, expected 1631"

    @pytest.mark.parametrize("scenario_key", SCENARIO_MATRIX_KEYS)
    def test_trajectories_have_no_nan_or_inf(self, scenario_key):
        """All numeric columns in every trajectory must be finite (no NaN, no Inf)."""
        parquet_path = ROOT / "outputs" / "runs" / f"{scenario_key}_seed42" / "trajectory.parquet"
        df = pd.read_parquet(parquet_path)

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            vals = df[col].to_numpy()
            assert np.isfinite(vals).all(), f"Non-finite values found in {scenario_key} column {col}"

    @pytest.mark.parametrize("scenario_key", SCENARIO_MATRIX_KEYS)
    def test_metrics_json_integrity_and_required_keys(self, scenario_key):
        """metrics.json must contain all required fields and finite values."""
        metrics_path = ROOT / "outputs" / "runs" / f"{scenario_key}_seed42" / "metrics.json"
        assert metrics_path.exists(), f"Missing metrics.json for {scenario_key}"

        m = json.loads(metrics_path.read_text(encoding="utf-8"))
        required_fields = [
            "peg_hours_longest",
            "operational_hours_longest",
            "stress_tail_verified",
            "final_ust_price",
            "final_anchor_deposits",
            "final_luna_supply",
            "rescued",
            "total_spent_usd",
        ]
        for field in required_fields:
            assert field in m, f"Field {field} missing from metrics.json in {scenario_key}"
            if isinstance(m[field], (int, float)):
                assert math.isfinite(m[field]), f"Field {field} in {scenario_key} is non-finite"

    def test_summary_csv_consistent_with_runs_csv(self):
        """summary.csv and runs.csv must match on all scenario keys and finite metrics."""
        summary_path = ROOT / "outputs" / "experiments" / "summary.csv"
        runs_path = ROOT / "outputs" / "experiments" / "runs.csv"
        assert summary_path.exists() and runs_path.exists()

        summary = pd.read_csv(summary_path)
        runs = pd.read_csv(runs_path)

        assert len(summary) == 10
        for key in SCENARIO_MATRIX_KEYS:
            assert key in summary["scenario"].values
            assert key in runs["scenario"].values

        # Check numeric columns are completely finite
        num_cols = summary.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            assert np.isfinite(summary[col].to_numpy()).all(), f"Non-finite in summary.csv {col}"


# ==============================================================================
# 5. Definitive Insolvency Verification (rescued == False)
# ==============================================================================

class TestDefinitiveInsolvencyVerification:
    """Empirically verify that no scenario falsely reports rescued = True under finite capital."""

    def test_all_10_scenarios_strictly_unrescued_in_summary_and_runs(self):
        """Verify rescue_rate == 0.0 across all 10 scenarios in both summary and runs files."""
        summary = pd.read_csv(ROOT / "outputs" / "experiments" / "summary.csv")
        runs = pd.read_csv(ROOT / "outputs" / "experiments" / "runs.csv")

        # In summary: rescue_rate must be 0.0
        assert (summary["rescue_rate"] == 0.0).all(), "rescue_rate is not strictly 0.0 in summary.csv"

        # In runs: rescued must be False
        assert (~runs["rescued"].astype(bool)).all(), "Found spurious rescued=True in runs.csv"

    def test_metrics_evaluator_rejects_spurious_rescue_without_stress_tail(self):
        """If simulation is truncated before the 7-day stress tail, rescued must be False."""
        # Create a synthetic trajectory where UST holds 1.00 for 48 hours, but lacks 7-day tail
        index = pd.date_range("2022-05-08T00:00:00Z", periods=192, freq="15min")  # 48 hours
        df = pd.DataFrame(
            {
                "ust_price": np.full(len(index), 1.0),
                "withdraw_requested": np.full(len(index), 1000.0),
                "withdraw_served": np.full(len(index), 1000.0),
                "withdraw_queue": np.zeros(len(index)),
                "ust_sell_queue": np.zeros(len(index)),
                "native_requested": np.full(len(index), 1000.0),
                "native_served": np.full(len(index), 1000.0),
                "native_open": np.full(len(index), True),
                "anchor_open": np.full(len(index), True),
                "support_remaining": np.full(len(index), 1e9),
                "support_spent": np.full(len(index), 100e6),
                "btc_sold": np.zeros(len(index)),
                "tfl_added": np.zeros(len(index)),
                "luna_price": np.full(len(index), 80.0),
                "luna_supply": np.full(len(index), 350e6),
                "anchor_deposits": np.full(len(index), 10e9),
                "depositor_loss_fraction": np.zeros(len(index)),
                "active_policies": np.ones(len(index), dtype=int),
                "historical_requested_usd": np.zeros(len(index)),
                "historical_executed_usd": np.zeros(len(index)),
                "ust_error": np.zeros(len(index)),
                "luna_error": np.zeros(len(index)),
                "usd_error": np.zeros(len(index)),
                "claim_error": np.zeros(len(index)),
            },
            index=index,
        )
        cfg = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-16T00:00:00Z",
            stress_days=7,
        )
        m = evaluate(df, cfg)
        assert m["rescued"] is False, "Spurious rescue reported without verified stress tail"
        assert m["stress_tail_verified"] is False

    def test_metrics_evaluator_rejects_rescue_if_peg_breaks_in_stress_tail(self):
        """Even if peg holds for 10 days, breaking in the stress tail must invalidate rescue."""
        index = pd.date_range("2022-05-06T00:15:00Z", periods=1632, freq="15min")
        prices = np.full(len(index), 1.0)
        # Drop peg in the stress tail (after May 16)
        stress_idx = index >= pd.Timestamp("2022-05-16T00:00:00Z")
        prices[stress_idx] = 0.90  # Broken peg

        df = pd.DataFrame(
            {
                "ust_price": prices,
                "withdraw_requested": np.full(len(index), 1000.0),
                "withdraw_served": np.full(len(index), 1000.0),
                "withdraw_queue": np.zeros(len(index)),
                "ust_sell_queue": np.zeros(len(index)),
                "native_requested": np.full(len(index), 1000.0),
                "native_served": np.full(len(index), 1000.0),
                "native_open": np.full(len(index), True),
                "anchor_open": np.full(len(index), True),
                "support_remaining": np.full(len(index), 1e9),
                "support_spent": np.full(len(index), 100e6),
                "btc_sold": np.zeros(len(index)),
                "tfl_added": np.zeros(len(index)),
                "luna_price": np.full(len(index), 80.0),
                "luna_supply": np.full(len(index), 350e6),
                "anchor_deposits": np.full(len(index), 10e9),
                "depositor_loss_fraction": np.zeros(len(index)),
                "active_policies": np.ones(len(index), dtype=int),
                "historical_requested_usd": np.zeros(len(index)),
                "historical_executed_usd": np.zeros(len(index)),
                "ust_error": np.zeros(len(index)),
                "luna_error": np.zeros(len(index)),
                "usd_error": np.zeros(len(index)),
                "claim_error": np.zeros(len(index)),
            },
            index=index,
        )
        cfg = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-06T00:15:00Z",
            end="2022-05-16T00:00:00Z",
            stress_days=7,
        )
        m = evaluate(df, cfg)
        assert m["rescued"] is False
        assert m["stress_tail_verified"] is False


# ==============================================================================
# 6. Dashboard App Robustness Under Adversarial Data
# ==============================================================================

class TestAppRobustnessUnderAdversarialData:
    """Verify that app.py data loaders and charting helpers handle corrupt/missing data gracefully."""

    def test_load_trajectory_nonexistent_returns_none(self):
        """load_scenario_run_trajectory must return None for non-existent scenarios without throwing."""
        import app
        res = app.load_scenario_run_trajectory("nonexistent_scenario_xyz_999")
        assert res is None

    def test_load_metrics_nonexistent_returns_none(self):
        """load_scenario_run_metrics must return None for non-existent scenarios without throwing."""
        import app
        res = app.load_scenario_run_metrics("nonexistent_scenario_xyz_999")
        assert res is None

    def test_chart_handles_empty_trajectories_dict(self):
        """chart() with empty dict returns a valid Plotly Figure."""
        import app
        fig = app.chart({}, "ust_price", "Empty Chart Test")
        assert fig is not None
        assert len(fig.data) >= 0

    def test_chart_handles_none_and_empty_dataframes(self):
        """chart() with None and empty DataFrame does not raise unhandled exceptions."""
        import app
        trajectories = {
            "NoneEntry": None,
            "EmptyDF": pd.DataFrame(),
            "NoCols": pd.DataFrame(index=pd.date_range("2022-05-08T00:00:00Z", periods=5, freq="15min")),
        }
        fig = app.chart(trajectories, "ust_price", "Corrupt Input Test", historical=False)
        assert fig is not None

    def test_chart_handles_missing_column(self):
        """chart() skips DataFrames that do not have the requested column."""
        import app
        df = pd.DataFrame(
            {"other_column": [1, 2, 3]},
            index=pd.date_range("2022-05-08T00:00:00Z", periods=3, freq="15min"),
        )
        fig = app.chart({"WrongCol": df}, "ust_price", "Missing Col Test", historical=False)
        assert fig is not None

    def test_chart_handles_all_nan_column(self):
        """chart() handles all-NaN columns without crashing."""
        import app
        df = pd.DataFrame(
            {"ust_price": [np.nan, np.nan, np.nan]},
            index=pd.date_range("2022-05-08T00:00:00Z", periods=3, freq="15min"),
        )
        fig = app.chart({"AllNaN": df}, "ust_price", "All NaN Test", historical=False)
        assert fig is not None

    def test_chart_handles_out_of_range_window(self):
        """chart() with window outside trajectory bounds does not raise errors."""
        import app
        traj = app.load_scenario_run_trajectory("sc01_baseline_no_rescue")
        window = (pd.Timestamp("2025-01-01T00:00:00Z"), pd.Timestamp("2025-01-02T00:00:00Z"))
        fig = app.chart({"SC01": traj}, "ust_price", "Out of bounds window", window=window, historical=False)
        assert fig is not None

    def test_chart_corridor_rendering_toggle(self):
        """Verify show_corridor=True renders green corridor shape, False does not."""
        import app
        traj = app.load_scenario_run_trajectory("sc01_baseline_no_rescue")

        fig_with = app.chart({"SC01": traj}, "ust_price", "With Corridor", show_corridor=True, historical=False)
        fig_without = app.chart({"SC01": traj}, "ust_price", "Without Corridor", show_corridor=False, historical=False)

        hrects_with = [s for s in fig_with.layout.shapes if getattr(s, "y0", None) == 0.98 and getattr(s, "y1", None) == 1.02]
        hrects_without = [s for s in fig_without.layout.shapes if getattr(s, "y0", None) == 0.98 and getattr(s, "y1", None) == 1.02]

        assert len(hrects_with) == 1, "Corridor shape missing when show_corridor=True"
        assert len(hrects_without) == 0, "Corridor shape unexpectedly present when show_corridor=False"
