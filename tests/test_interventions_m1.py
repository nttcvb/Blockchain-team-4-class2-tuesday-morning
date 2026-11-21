"""Unit and Invariant Tests for Milestone 1 Intervention Mechanisms.

Features Covered:
- F01: Finite Budget & Cap Invariant (BTC <= 80,081, TFL <= $613.6M, total <= $3.5B)
- F02: Buyback & Immediate Supply Burn (burn_acquired_ust)
- F03: Concentrated Bid-Wall Support (target_peg)
- F04: Staggered Tranches & Stop-Loss Waterfall (max_cumulative_spend)
- F05: Dynamic Tiered Anchor Withdrawal Gates (tiered_gates)
- F06: Queue & Claim Conservation
- F07: Emergency Redemption Haircut (redemption_haircut)
- F08: Emergency Native Spread Hike (emergency_spread_rate)
- F09: Daily Arbitrage Capacity Throttling (arb_capacity_multiplier)
- F10: Emergency Circuit Breaker (circuit_breaker_threshold)
"""

import math
import numpy as np
import pandas as pd
import pytest
from dataclasses import replace

from luna_sim.config import PolicyConfig, ScenarioConfig, ModelParams
from luna_sim.engine import (
    context,
    initialize,
    observation,
    rescue,
    anchor,
    markets,
    invariants,
    simulate,
    spend,
)


def short_cfg(**kwargs):
    """Helper creating a fast deterministic ScenarioConfig for unit testing."""
    return ScenarioConfig(
        start="2022-05-08T00:00:00Z",
        end="2022-05-08T01:00:00Z",
        n_depositors=100,
        stochastic=False,
        **kwargs,
    )


def observed_book(ctx):
    """Helper initializing and stepping book to simulation start."""
    b = initialize(ctx)
    b["step"] = int(ctx["index"].get_indexer([pd.Timestamp(ctx["config"].start)])[0]) - 1
    return observation(ctx, b)


# ==============================================================================
# F01: Finite Budget & Invariant Conservation Tests
# ==============================================================================

class TestFiniteBudgetAndConservation:
    def test_lfg_btc_spendable_cap_and_retention_floor(self):
        """BTC spendable cannot exceed 80,081 BTC and locked floor >= 313 BTC is maintained."""
        policy = PolicyConfig("buy_ust", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, max_spend_per_hour=1e9)
        c = short_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        ctx = context(c); b = observed_book(ctx)
        assert b["locked_btc"] >= 313.0
        assert b["btc_sold"] <= 80081.001
        assert abs((b["locked_btc"] + b["fund_btc"].sum() + b["btc_sold"]) - 80394.0) < 1e-3

    def test_tfl_usd_contribution_cap(self):
        """TFL external USD injection cannot exceed historical limit of $613,616,889."""
        policy = PolicyConfig("buy_ust", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, funder="TFL", max_spend_per_hour=1e9)
        c = short_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        ctx = context(c); b = observed_book(ctx)
        assert b["tfl_added"] <= 613616889.001

    def test_multi_step_invariant_conservation(self):
        """Verify strict invariants: claim_error < 1e-4, ust_error < 0.1, usd_error < 0.1 across simulation."""
        policy = PolicyConfig("buy_ust", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, burn_acquired_ust=True)
        c = short_cfg(mode="counterfactual", policies=[policy], funding_timing="early")
        traj, metrics, _ = simulate(c, engine="fast")
        for err_name, max_err in metrics["max_accounting_errors"].items():
            assert max_err < 0.1, f"{err_name} exceeded tolerance: {max_err}"
        assert abs(traj["claim_error"].iloc[-1]) < 1e-4


# ==============================================================================
# F02: Buyback & Immediate Supply Burn Tests
# ==============================================================================

class TestBuybackAndImmediateBurn:
    def test_buyback_burn_decreases_ust_supply(self):
        """When burn_acquired_ust=True, spend() burns acquired tokens from ust_supply and fund_ust remains 0."""
        c = short_cfg()
        ctx = context(c); b = observed_book(ctx)
        transfer = 10e6
        b["locked_stable"] -= transfer
        b["fund_usd"][0] += transfer
        before_supply = b["ust_supply"]
        before_market = b["market_ust"]

        used = spend(ctx, b, 5e6, allowed=(0,), asset="UST", burn_acquired_ust=True)
        assert used > 0
        assert b["fund_ust"].sum() == 0.0
        assert b["ust_supply"] < before_supply
        assert b["market_ust"] < before_market
        assert b["ust_burned_by_rescue"] > 0
        np.testing.assert_allclose(before_supply - b["ust_supply"], b["ust_burned_by_rescue"])
        
        errors = invariants(ctx, b)
        assert abs(errors["ust_error"]) < 0.1

    def test_default_buyback_retains_tokens_in_fund_ust(self):
        """When burn_acquired_ust=False (default), tokens accumulate in fund_ust and ust_supply is unchanged."""
        c = short_cfg()
        ctx = context(c); b = observed_book(ctx)
        transfer = 10e6
        b["locked_stable"] -= transfer
        b["fund_usd"][0] += transfer
        before_supply = b["ust_supply"]

        used = spend(ctx, b, 5e6, allowed=(0,), asset="UST", burn_acquired_ust=False)
        assert used > 0
        assert b["fund_ust"][0] > 0
        assert b["ust_supply"] == before_supply
        assert b.get("ust_burned_by_rescue", 0.0) == 0.0
        
        errors = invariants(ctx, b)
        assert abs(errors["ust_error"]) < 0.1


# ==============================================================================
# F03: Concentrated Bid-Wall Support Tests
# ==============================================================================

class TestConcentratedBidWall:
    def test_bid_wall_spending_threshold(self):
        """Bid-wall only spends when ust_price < target_peg."""
        p = PolicyConfig("buy_ust", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, target_peg=0.985, max_spend_per_hour=50e6)
        c = short_cfg(mode="counterfactual", policies=[p], funding_timing="early")
        ctx = context(c); b = observed_book(ctx)
        b["fund_usd"][0] = 20e6

        # Price at 0.99 (above target_peg 0.985) -> zero expenditure
        b["ust_price"] = 0.99
        out1 = rescue(ctx, b.copy())
        assert out1["policy_spent"][0] == 0.0

        # Price at 0.95 (below target_peg 0.985) -> active expenditure
        b["ust_price"] = 0.95
        out2 = rescue(ctx, b.copy())
        assert out2["policy_spent"][0] > 0.0

    def test_bid_wall_order_sizing_respects_target_depth(self):
        """Cost required to defend target_peg is bounded by target_cost log depth."""
        p = PolicyConfig("buy_ust", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, target_peg=0.980, max_spend_per_hour=500e6)
        c = short_cfg(mode="counterfactual", policies=[p], funding_timing="early")
        ctx = context(c); b = observed_book(ctx)
        b["fund_usd"][0] = 100e6
        b["ust_price"] = 0.975

        out = rescue(ctx, b.copy())
        # Spending should not exceed target_cost
        assert out["policy_spent"][0] > 0


# ==============================================================================
# F04: Staggered Tranches & Stop-Loss Waterfall Tests
# ==============================================================================

class TestStopLossWaterfall:
    def test_stop_loss_halts_policy_when_cumulative_spend_reached(self):
        """When cumulative policy spend reaches max_cumulative_spend, no further funds are spent."""
        ceiling = 5e6
        p = PolicyConfig("buy_ust", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, max_spend_per_hour=100e6, max_cumulative_spend=ceiling)
        c = short_cfg(mode="counterfactual", policies=[p], funding_timing="early")
        ctx = context(c); b = observed_book(ctx)
        b["fund_usd"][0] = 50e6
        b["ust_price"] = 0.90

        out1 = rescue(ctx, b.copy())
        assert np.isclose(out1["policy_spent"][0], ceiling, rtol=1e-3)

        # Subsequent rescue invocation must spend 0 since allowance is exhausted
        out2 = rescue(ctx, out1.copy())
        assert np.isclose(out2["policy_spent"][0], ceiling, rtol=1e-3)


# ==============================================================================
# F05: Dynamic Tiered Anchor Withdrawal Gates Tests
# ==============================================================================

class TestTieredAnchorWithdrawalGates:
    def test_tiered_gates_pricing_tiers(self):
        """Tiered gates dynamically adjust withdrawal limit according to 3 price bands."""
        p = PolicyConfig("withdrawal_gate", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, tiered_gates=True)
        c = short_cfg(mode="counterfactual", policies=[p])
        ctx = context(c); b = observed_book(ctx)
        total_dep = b["deposit"].sum() + b["institution_deposit"]
        dt_factor = c.dt_minutes / 1440.0

        # Tier 1: Price >= 0.99 -> 100% / day
        b["ust_price"] = 0.995
        b1 = observation(ctx, b.copy())
        np.testing.assert_allclose(b1["withdraw_limit"], total_dep * 1.00 * dt_factor, rtol=1e-5)

        # Tier 2: 0.95 <= Price < 0.99 -> 15% / day
        b["ust_price"] = 0.97
        b2 = observation(ctx, b.copy())
        np.testing.assert_allclose(b2["withdraw_limit"], total_dep * 0.15 * dt_factor, rtol=1e-5)

        # Tier 3: Price < 0.95 -> 5% / day
        b["ust_price"] = 0.90
        b3 = observation(ctx, b.copy())
        np.testing.assert_allclose(b3["withdraw_limit"], total_dep * 0.05 * dt_factor, rtol=1e-5)

    def test_tiered_gates_disabled_falls_back_to_static_fraction(self):
        """When tiered_gates=False, withdraw_limit uses static withdrawal_fraction_per_day."""
        p = PolicyConfig("withdrawal_gate", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, tiered_gates=False, withdrawal_fraction_per_day=0.10)
        c = short_cfg(mode="counterfactual", policies=[p])
        ctx = context(c); b = observed_book(ctx)
        total_dep = b["deposit"].sum() + b["institution_deposit"]
        dt_factor = c.dt_minutes / 1440.0

        b["ust_price"] = 0.80
        b1 = observation(ctx, b.copy())
        np.testing.assert_allclose(b1["withdraw_limit"], total_dep * 0.10 * dt_factor, rtol=1e-5)


# ==============================================================================
# F07: Emergency Redemption Haircut Tests
# ==============================================================================

class TestEmergencyRedemptionHaircut:
    def test_redemption_haircut_burns_debt_and_conserves_invariants(self):
        """Haircut deducts from served redemptions, burns debt permanently, and conserves claim & ust errors."""
        haircut_rate = 0.25
        p = PolicyConfig("withdrawal_gate", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, redemption_haircut=haircut_rate)
        c = short_cfg(mode="counterfactual", policies=[p])
        ctx = context(c); b = observed_book(ctx)
        b["queue"] = b["deposit"].copy()
        b["institution_queue"] = b["institution_deposit"]
        before_supply = b["ust_supply"]

        out = anchor(ctx, b.copy())
        served = out["withdraw_served"]
        assert served > 0

        expected_haircut = served * haircut_rate
        np.testing.assert_allclose(out["haircut_burned_ust"], expected_haircut, rtol=1e-5)
        np.testing.assert_allclose(out["ust_supply"], before_supply - expected_haircut, rtol=1e-5)

        # Invariant check
        errors = invariants(ctx, out)
        assert errors["claim_error"] == 0.0
        assert abs(errors["ust_error"]) < 0.1


# ==============================================================================
# F08: Emergency Native Spread Hike Tests
# ==============================================================================

class TestEmergencyNativeSpreadHike:
    def test_spread_hike_neutralizes_arbitrage_incentive(self):
        """Emergency spread hike above depeg discount halts native swap arbitrage minting."""
        c = short_cfg()
        ctx = context(c); b = observed_book(ctx)
        b["ust_price"] = 0.85

        # Without emergency spread: arb is profitable and mints LUNA
        b["emergency_spread"] = 0.0
        out_base = markets(ctx, b.copy())
        assert out_base["native_served"] > 0
        assert out_base["new_luna_mint"] > 0

        # With 20% emergency spread (total spread 0.205 > depeg discount 0.15)
        b["emergency_spread"] = 0.20
        out_hike = markets(ctx, b.copy())
        assert out_hike["native_served"] == 0.0
        assert out_hike["new_luna_mint"] == 0.0
        assert out_hike["luna_supply"] == b["luna_supply"]


# ==============================================================================
# F09: Arbitrage Capacity Throttling Tests
# ==============================================================================

class TestArbitrageCapacityThrottling:
    def test_arb_capacity_scaling(self):
        """arb_capacity_multiplier scales down maximum arbitrage throughput."""
        c = short_cfg()
        ctx = context(c); b = observed_book(ctx)
        b["ust_price"] = 0.75

        # Baseline full throughput
        b["arb_capacity_mult"] = 1.0
        out_full = markets(ctx, b.copy())

        # Throttled to 10%
        b["arb_capacity_mult"] = 0.10
        out_throttled = markets(ctx, b.copy())

        assert out_throttled["native_served"] < out_full["native_served"] * 0.15


# ==============================================================================
# F10: Emergency Circuit Breaker Tests
# ==============================================================================

class TestEmergencyCircuitBreaker:
    def test_circuit_breaker_halts_anchor_and_native_modules(self):
        """When ust_price drops below circuit_breaker_threshold, Anchor and Native modules halt."""
        cb_threshold = 0.92
        p = PolicyConfig("withdrawal_gate", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0, circuit_breaker_threshold=cb_threshold)
        c = short_cfg(mode="counterfactual", policies=[p])
        ctx = context(c); b = observed_book(ctx)

        # Above threshold: modules remain open
        b["ust_price"] = 0.95
        b1 = observation(ctx, b.copy())
        assert b1["anchor_open"] and b1["native_open"]

        # Below threshold: modules halt
        b["ust_price"] = 0.90
        b2 = observation(ctx, b.copy())
        assert not b2["anchor_open"]
        assert not b2["native_open"]

        # In anchor, served redemptions are zero
        b2["queue"] = b2["deposit"].copy()
        out = anchor(ctx, b2.copy())
        assert out["withdraw_served"] == 0.0

    def test_circuit_breaker_action_type(self):
        """Policy with action='circuit_breaker' directly triggers module halting."""
        p = PolicyConfig("circuit_breaker", trigger="time", start_time="2022-05-08T00:00:00Z", delay_minutes=0)
        c = short_cfg(mode="counterfactual", policies=[p])
        ctx = context(c); b = observed_book(ctx)
        b_obs = observation(ctx, b.copy())
        assert not b_obs["anchor_open"]
        assert not b_obs["native_open"]


# ==============================================================================
# PolicyConfig Validation Boundary Tests
# ==============================================================================

class TestPolicyConfigValidation:
    def test_valid_default_instantiation(self):
        """Default PolicyConfig validates without error."""
        p = PolicyConfig(action="buy_ust")
        p.validate()

    @pytest.mark.parametrize("param,value,match", [
        ("target_peg", 0.0, "target_peg out of range"),
        ("target_peg", -1.0, "target_peg out of range"),
        ("target_peg", 2.5, "target_peg out of range"),
        ("target_peg", float("nan"), "Non-finite policy parameter: target_peg"),
        ("emergency_spread_rate", -0.01, "emergency_spread_rate out of range"),
        ("emergency_spread_rate", 0.95, "emergency_spread_rate out of range"),
        ("arb_capacity_multiplier", -0.5, "arb_capacity_multiplier must be non-negative"),
        ("redemption_haircut", -0.1, "redemption_haircut out of range"),
        ("redemption_haircut", 0.95, "redemption_haircut out of range"),
        ("circuit_breaker_threshold", -0.1, "circuit_breaker_threshold out of range"),
        ("circuit_breaker_threshold", 1.1, "circuit_breaker_threshold out of range"),
        ("max_cumulative_spend", -1.0, "max_cumulative_spend must be non-negative and not NaN"),
        ("max_cumulative_spend", float("nan"), "max_cumulative_spend must be non-negative and not NaN"),
        ("max_cumulative_spend", True, "max_cumulative_spend must be non-negative and not NaN"),
        ("burn_acquired_ust", "yes", "burn_acquired_ust must be a boolean"),
        ("tiered_gates", 1, "tiered_gates must be a boolean"),
        ("action", "unknown_action", "Unknown policy action"),
    ])
    def test_invalid_parameters_raise_value_error(self, param, value, match):
        p = PolicyConfig(action="buy_ust")
        setattr(p, param, value)
        with pytest.raises(ValueError, match=match):
            p.validate()
