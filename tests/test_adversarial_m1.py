"""Empirical Adversarial Stress & Boundary Tests for Milestone 1 Interventions.

Authored by: M1 Stress & Boundary Challenger (challenger_m1_1)
Target: luna_sim.config & luna_sim.engine

Scope of Adversarial Challenge:
1. Extreme Parameter Inputs:
   - target_peg in {1e-6, 0.001, 0.5, 1.0, 1.5, 2.0}
   - redemption_haircut in {0.0, 0.10, 0.50, 0.89, 0.90}
   - emergency_spread_rate in {0.0, 0.10, 0.50, 0.89, 0.90}
   - max_cumulative_spend in {0.0, 1e-6, 100.0, 1e6}
   - arb_capacity_multiplier in {0.0, 1e-4, 0.01, 100.0}
   - circuit_breaker_threshold in {0.0, 0.50, 0.999, 1.0}
2. Extreme Depositor Panic Bank Runs + Tiered Gates:
   - 100% queue requests, severe depeg, tiered gate throttling (100% -> 15% -> 5%)
   - Interaction between haircut burns, tiered gates, and depositor claims
3. Invariant Conservation & Numerical Stability:
   - Every single timestep verifies claim_error, ust_error, usd_error, luna_error
   - No negative balances, no non-finite numbers, no AssertionErrors
"""

import math
import numpy as np
import pandas as pd
import pytest

from luna_sim.config import PolicyConfig, ScenarioConfig, ModelParams
from luna_sim.engine import (
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
    BLOCKS,
)


def make_test_cfg(**kwargs):
    """Helper creating a fast deterministic ScenarioConfig for unit testing."""
    end = kwargs.pop("end", "2022-05-08T03:00:00Z")
    start = kwargs.pop("start", "2022-05-08T00:00:00Z")
    n_depositors = kwargs.pop("n_depositors", 100)
    stochastic = kwargs.pop("stochastic", False)
    return ScenarioConfig(
        start=start,
        end=end,
        n_depositors=n_depositors,
        stochastic=stochastic,
        **kwargs,
    )


def step_to_start(ctx):
    """Helper initializing and stepping book to simulation start."""
    b = initialize(ctx)
    b["step"] = int(ctx["index"].get_indexer([pd.Timestamp(ctx["config"].start)])[0]) - 1
    return observation(ctx, b)


# ==============================================================================
# 1. Extreme Parameter Inputs: target_peg
# ==============================================================================

class TestExtremeTargetPeg:
    @pytest.mark.parametrize("target_peg", [1e-6, 0.001, 0.5, 1.0, 1.5, 2.0])
    def test_target_peg_numerical_stability(self, target_peg):
        """Verify rescue calculation is numerically stable and never violates invariants across extreme target pegs."""
        policy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            target_peg=target_peg,
            max_spend_per_hour=50e6,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        ctx = context(c)
        b = step_to_start(ctx)

        # Case A: UST price is lower than target peg -> should spend cleanly
        b["ust_price"] = min(0.95, target_peg * 0.9)
        out = rescue(ctx, b.copy())
        assert np.isfinite(out["policy_spent"][0])
        assert out["policy_spent"][0] >= 0.0
        errs = invariants(ctx, out)
        assert abs(errs["ust_error"]) < 0.1
        assert abs(errs["usd_error"]) < 0.1

        # Case B: UST price is higher than target peg -> should spend 0
        b["ust_price"] = target_peg * 1.1
        out2 = rescue(ctx, b.copy())
        assert out2["policy_spent"][0] == 0.0
        errs2 = invariants(ctx, out2)
        assert abs(errs2["ust_error"]) < 0.1

    def test_target_peg_upper_boundary_burn_simulation(self):
        """Full simulation with target_peg=2.0 and burn_acquired_ust=True."""
        policy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            target_peg=2.0,
            max_spend_per_hour=10e6,
            burn_acquired_ust=True,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        traj, metrics, _ = simulate(c, engine="fast")
        for err_name, max_err in metrics["max_accounting_errors"].items():
            assert max_err < 0.1, f"{err_name} exceeded tolerance: {max_err}"
        assert traj["ust_burned_by_rescue"].iloc[-1] > 0


# ==============================================================================
# 2. Extreme Parameter Inputs: redemption_haircut
# ==============================================================================

class TestExtremeRedemptionHaircut:
    @pytest.mark.parametrize("haircut", [0.0, 0.10, 0.50, 0.89, 0.90])
    def test_redemption_haircut_exact_conservation(self, haircut):
        """Haircut permanently reduces supply by exactly haircut * served and strictly conserves claims & supply."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            redemption_haircut=haircut,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy])
        ctx = context(c)
        b = step_to_start(ctx)

        # Set depeg price so that redeposit is inactive and haircut effect is pure
        b["ust_price"] = 0.90
        # Force massive withdrawal request
        b["queue"] = b["deposit"].copy()
        b["institution_queue"] = b["institution_deposit"]
        pre_supply = b["ust_supply"]
        pre_claims = b["deposit"].sum() + b["institution_deposit"]
        pre_wallets = b["wallet_ust"].sum() + b["institution_wallet"]

        out = anchor(ctx, b.copy())
        served = out["withdraw_served"]
        assert served > 0

        expected_burn = served * haircut
        np.testing.assert_allclose(out["haircut_burned_ust"], expected_burn, rtol=1e-5)
        np.testing.assert_allclose(out["ust_supply"], pre_supply - expected_burn, rtol=1e-5)

        # Depositor wallet net increase gets net fraction
        net_fraction = 1.0 - haircut
        post_wallets = out["wallet_ust"].sum() + out["institution_wallet"]
        np.testing.assert_allclose(post_wallets - pre_wallets, served * net_fraction, rtol=1e-5)

        # Deposit claims reduced by full served amount
        post_claims = out["deposit"].sum() + out["institution_deposit"]
        np.testing.assert_allclose(post_claims, pre_claims - served, rtol=1e-5)

        # Invariants strictly verified
        errs = invariants(ctx, out)
        assert abs(errs["claim_error"]) < 1e-4
        assert abs(errs["ust_error"]) < 0.1

    def test_haircut_multi_step_simulation(self):
        """Multi-step simulation with extreme 89% haircut under bank run conditions."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            redemption_haircut=0.89,
            withdrawal_fraction_per_day=0.50,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy])
        traj, metrics, _ = simulate(c, engine="fast")
        for err_name, max_err in metrics["max_accounting_errors"].items():
            assert max_err < 0.1, f"{err_name} exceeded tolerance: {max_err}"
        assert traj["haircut_burned_ust"].iloc[-1] > 0


# ==============================================================================
# 3. Extreme Parameter Inputs: emergency_spread_rate
# ==============================================================================

class TestExtremeEmergencySpreadRate:
    @pytest.mark.parametrize("spread_rate", [0.0, 0.10, 0.50, 0.89, 0.90])
    def test_spread_rate_numerical_stability(self, spread_rate):
        """Native swap quotes and markets execution are stable and fee calculations valid across spread rates."""
        c = make_test_cfg()
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = 0.80  # 20% discount
        b["emergency_spread"] = spread_rate

        out = markets(ctx, b.copy())
        assert np.isfinite(out["native_served"])
        assert np.isfinite(out["new_luna_mint"])
        assert np.isfinite(out["native_fee"])
        assert out["native_served"] >= 0.0
        assert out["new_luna_mint"] >= 0.0

        # If spread rate >= 0.20, native arbitrage is unprofitable -> native_served MUST be 0
        if spread_rate >= 0.20:
            assert out["native_served"] == 0.0
            assert out["new_luna_mint"] == 0.0

        errs = invariants(ctx, out)
        assert abs(errs["ust_error"]) < 0.1
        assert abs(errs["luna_error"]) < 0.1


# ==============================================================================
# 4. Extreme Parameter Inputs: max_cumulative_spend
# ==============================================================================

class TestExtremeMaxCumulativeSpend:
    def test_zero_cumulative_spend_strictly_blocks_any_spending(self):
        """max_cumulative_spend = 0.0 strictly blocks any spending even when policy is triggered."""
        policy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            max_spend_per_hour=50e6,
            max_cumulative_spend=0.0,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = 0.90

        out = rescue(ctx, b.copy())
        assert out["policy_spent"][0] == 0.0
        assert out["fund_spent"].sum() == 0.0

    def test_microscopic_cumulative_spend_respects_bound(self):
        """max_cumulative_spend = 1e-6 allows only at most 1e-6 USD expenditure."""
        micro_ceiling = 1e-6
        policy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            max_spend_per_hour=50e6,
            max_cumulative_spend=micro_ceiling,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = 0.90

        out1 = rescue(ctx, b.copy())
        assert out1["policy_spent"][0] <= micro_ceiling + 1e-12

        # Second call must spend 0
        out2 = rescue(ctx, out1.copy())
        assert out2["policy_spent"][0] <= micro_ceiling + 1e-12
        errs = invariants(ctx, out2)
        assert abs(errs["ust_error"]) < 0.1
        assert abs(errs["usd_error"]) < 0.1

    def test_staggered_spend_cutoff_multi_step_simulation(self):
        """Multi-step simulation verifying that policy halts exactly at cumulative budget limit."""
        ceiling = 5e6
        policy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            max_spend_per_hour=5e6,
            max_cumulative_spend=ceiling,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        traj, metrics, _ = simulate(c, engine="fast")
        assert traj["support_spent"].iloc[-1] <= ceiling + 1e-3
        for err_name, max_err in metrics["max_accounting_errors"].items():
            assert max_err < 0.1, f"{err_name} exceeded tolerance: {max_err}"


# ==============================================================================
# 5. Extreme Parameter Inputs: arb_capacity_multiplier & circuit_breaker
# ==============================================================================

class TestExtremeArbAndCircuitBreaker:
    def test_zero_arb_capacity_shuts_down_native_arbitrage(self):
        """arb_capacity_multiplier = 0.0 completely suppresses arbitrage."""
        c = make_test_cfg()
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = 0.80
        b["arb_capacity_mult"] = 0.0

        out = markets(ctx, b.copy())
        assert out["native_served"] == 0.0
        assert out["new_luna_mint"] == 0.0
        errs = invariants(ctx, out)
        assert abs(errs["luna_error"]) < 0.1

    def test_extreme_high_arb_capacity_multiplier(self):
        """arb_capacity_multiplier = 100.0 is stable and bounded by arb cash and inventory."""
        c = make_test_cfg()
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = 0.80
        b["arb_capacity_mult"] = 100.0

        out = markets(ctx, b.copy())
        assert np.isfinite(out["native_served"])
        assert out["native_served"] <= b["market_ust"] + 1e-3
        errs = invariants(ctx, out)
        assert abs(errs["luna_error"]) < 0.1
        assert abs(errs["ust_error"]) < 0.1

    @pytest.mark.parametrize("cb_threshold", [0.50, 0.999, 1.0])
    def test_circuit_breaker_halts_modules_cleanly(self, cb_threshold):
        """circuit_breaker_threshold halts modules whenever ust_price < cb_threshold."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            circuit_breaker_threshold=cb_threshold,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy])
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = cb_threshold - 0.01

        b_obs = observation(ctx, b.copy())
        assert not b_obs["anchor_open"]
        assert not b_obs["native_open"]

        # Run anchor block: served must be 0
        b_obs["queue"] = b_obs["deposit"].copy()
        out_anchor = anchor(ctx, b_obs.copy())
        assert out_anchor["withdraw_served"] == 0.0

        # Run markets block: native_served must be 0
        out_markets = markets(ctx, b_obs.copy())
        assert out_markets["native_served"] == 0.0


# ==============================================================================
# 6. Extreme Depositor Panic Bank Runs + Tiered Gates
# ==============================================================================

class TestExtremeBankRunWithTieredGates:
    def test_tiered_gates_step_by_step_throttling_under_forced_bank_run(self):
        """Simulate aggressive 100% depositor withdrawal queue across all 3 tiered price bands."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            tiered_gates=True,
            redemption_haircut=0.20,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy])
        ctx = context(c)
        b = step_to_start(ctx)
        dt_factor = c.dt_minutes / 1440.0

        for price, expected_fraction in [(0.995, 1.00), (0.97, 0.15), (0.90, 0.05)]:
            b["ust_price"] = price
            # 1. Observation sets withdraw_limit
            b = observation(ctx, b)
            total_dep = b["deposit"].sum() + b["institution_deposit"]
            expected_limit = total_dep * expected_fraction * dt_factor
            np.testing.assert_allclose(b["withdraw_limit"], expected_limit, rtol=1e-5)

            # 2. Force 100% queue panic
            b["queue"] = b["deposit"].copy()
            b["institution_queue"] = b["institution_deposit"]

            # 3. Anchor executes redemptions
            b = anchor(ctx, b)
            # Served must not exceed limit
            assert b["withdraw_served"] <= expected_limit + 1e-4

            # 4. Invariant checks
            errs = invariants(ctx, b)
            assert abs(errs["claim_error"]) < 1e-4
            assert abs(errs["ust_error"]) < 0.1
            assert b["queue"].sum() <= b["deposit"].sum() + 0.1
            assert np.all(b["deposit"] >= -1e-6)
            assert b["anchor_cash"] >= -1e-6

    def test_compound_extreme_crisis_multi_step_simulation(self):
        """Multi-day stress simulation under extreme combined interventions:
        - Concentrated bid-wall at 1.05
        - Buyback & Burn active
        - Emergency spread 85%
        - Arb capacity 5%
        - Redemption haircut 85%
        - Tiered gates active
        - Stop-loss spend limit $20M
        """
        p_buy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            target_peg=1.05,
            burn_acquired_ust=True,
            max_cumulative_spend=20e6,
            max_spend_per_hour=5e6,
            funder="both",
        )
        p_gate = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            tiered_gates=True,
            redemption_haircut=0.85,
            emergency_spread_rate=0.85,
            arb_capacity_multiplier=0.05,
        )
        c = make_test_cfg(
            mode="counterfactual",
            policies=[p_buy, p_gate],
            funding_timing="early",
            end="2022-05-09T00:00:00Z",  # 24 hour run
        )
        traj, metrics, _ = simulate(c, engine="fast")
        for err_name, max_err in metrics["max_accounting_errors"].items():
            assert max_err < 0.1, f"{err_name} exceeded tolerance: {max_err}"
        assert abs(traj["claim_error"].max()) < 1e-4
        assert traj["ust_burned_by_rescue"].iloc[-1] > 0
        assert traj["haircut_burned_ust"].iloc[-1] > 0
        assert traj["support_spent"].iloc[-1] <= 20e6 + 1e-3


# ==============================================================================
# 7. Adversarial PolicyConfig Validation
# ==============================================================================

class TestAdversarialConfigValidation:
    @pytest.mark.parametrize("param,val", [
        ("target_peg", 0.0),
        ("target_peg", -0.001),
        ("target_peg", 2.0001),
        ("target_peg", float("inf")),
        ("target_peg", float("nan")),
        ("emergency_spread_rate", -0.001),
        ("emergency_spread_rate", 0.9001),
        ("arb_capacity_multiplier", -0.001),
        ("redemption_haircut", -0.001),
        ("redemption_haircut", 0.9001),
        ("circuit_breaker_threshold", -0.001),
        ("circuit_breaker_threshold", 1.0001),
        ("max_cumulative_spend", -0.001),
        ("max_cumulative_spend", float("nan")),
        ("burn_acquired_ust", 1),
        ("burn_acquired_ust", "true"),
        ("tiered_gates", 0),
        ("tiered_gates", None),
    ])
    def test_adversarial_rejected(self, param, val):
        p = PolicyConfig(action="buy_ust")
        setattr(p, param, val)
        with pytest.raises(ValueError):
            p.validate()


# ==============================================================================
# 8. Complex Compound Stress & Pathological Edge Cases
# ==============================================================================

class TestComplexAdversarialInteractions:
    def test_tiered_gates_rapid_boundary_oscillations(self):
        """Rapidly oscillate price across threshold boundaries: 0.99, 0.95, 0.90, 1.05."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            tiered_gates=True,
            redemption_haircut=0.15,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy])
        ctx = context(c)
        b = step_to_start(ctx)

        oscillating_prices = [0.991, 0.989, 0.951, 0.949, 1.02, 0.85, 0.995, 0.96, 0.92]
        for p in oscillating_prices:
            b["ust_price"] = p
            b = observation(ctx, b)
            b = decisions(ctx, b)
            b = anchor(ctx, b)
            b = accounting(ctx, b)
            errs = invariants(ctx, b)
            assert abs(errs["claim_error"]) < 1e-4
            assert abs(errs["ust_error"]) < 0.1
            assert np.all(b["deposit"] >= -1e-6)

    def test_complete_deposit_exhaustion_no_division_by_zero(self):
        """Simulate book when Anchor cash is drained to 0 via 100% depositor run. Verify no zero-division and invariants hold."""
        c = make_test_cfg(mode="counterfactual")
        ctx = context(c)
        b = step_to_start(ctx)
        b["ust_price"] = 0.90

        # Trigger 100% queue panic
        b["queue"] = b["deposit"].copy()
        b["institution_queue"] = b["institution_deposit"]

        # Run anchor to exhaust all available cash
        out_anchor = anchor(ctx, b.copy())
        assert out_anchor["withdraw_served"] > 0
        assert np.isclose(out_anchor["anchor_cash"], 0.0, atol=1e-3)
        assert out_anchor["queue"].sum() > 0  # Queue remains waiting for loan repayments

        # Next step with zero cash
        out_acct = accounting(ctx, out_anchor)
        errs = invariants(ctx, out_acct)
        assert abs(errs["claim_error"]) < 1e-4
        assert abs(errs["ust_error"]) < 0.1
        assert np.isfinite(out_acct["signals"][-1, 3])

    def test_zero_market_ust_inventory_handled_cleanly(self):
        """When market_ust is 0.0, rescue and market minutes must not crash or buy negative tokens."""
        policy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            target_peg=1.00,
            burn_acquired_ust=True,
        )
        c = make_test_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        ctx = context(c)
        b = step_to_start(ctx)
        b["market_ust"] = 0.0

        out_rescue = rescue(ctx, b.copy())
        assert out_rescue["policy_spent"][0] == 0.0
        assert out_rescue["market_ust"] >= 0.0

    @pytest.mark.parametrize("seed", [42, 43, 44])
    def test_all_policies_concurrent_48h_stochastic(self, seed):
        """Concurrent activation of all policy types over 48 hours under stochastic conditions:
        - buy_ust with concentrated bid-wall and immediate burn
        - liquidity commit
        - tiered withdrawal gate with haircut
        - native swap with emergency spread and arb capacity throttle
        - circuit breaker
        """
        p_buy = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            target_peg=0.985,
            burn_acquired_ust=True,
            max_cumulative_spend=30e6,
            max_spend_per_hour=10e6,
            allocation_fraction=0.60,
        )
        p_lp = PolicyConfig(
            action="liquidity",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            allocation_fraction=0.40,
            max_cumulative_spend=10e6,
        )
        p_gate = PolicyConfig(
            action="withdrawal_gate",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            tiered_gates=True,
            redemption_haircut=0.20,
            emergency_spread_rate=0.15,
            arb_capacity_multiplier=0.25,
            circuit_breaker_threshold=0.60,
        )
        c = make_test_cfg(
            mode="counterfactual",
            policies=[p_buy, p_lp, p_gate],
            funding_timing="early",
            stochastic=True,
            seed=seed,
            end="2022-05-10T00:00:00Z",  # 48 hours
        )
        traj, metrics, _ = simulate(c, engine="fast")
        for err_name, max_err in metrics["max_accounting_errors"].items():
            assert max_err < 0.1, f"Seed {seed}: {err_name} exceeded tolerance: {max_err}"
        assert abs(traj["claim_error"].max()) < 1e-4
        assert traj["support_spent"].iloc[-1] <= 40e6 + 1e-3
        assert np.all(np.isfinite(traj["ust_price"]))
        assert np.all(np.isfinite(traj["luna_price"]))
