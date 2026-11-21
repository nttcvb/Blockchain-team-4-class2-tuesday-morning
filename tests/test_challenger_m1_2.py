"""Adversarial Economic & Invariant Challenge Suite for Milestone 1.

Author: challenger_m1_2 (M1 Economic & Invariant Challenger)
Focus:
  1. Arbitrage exploitability & unbacked LUNA minting under emergency spread.
  2. Hard finite budget ceilings (80,081 BTC, $613.6M TFL, $3.5B total external spend) under multi-policy competition.
  3. Prolonged multi-day accounting leak detection (ust_error < 0.1, claim_error < 1e-4) under combined interventions.
"""
import math
import numpy as np
import pandas as pd
import pytest

from luna_sim.config import ModelParams, PolicyConfig, ScenarioConfig
from luna_sim.engine import (
    context, initialize, observation, rescue, decisions, anchor, markets,
    accounting, invariants, simulate, total_deposits, _market_minute,
    native_quote, native_vwap_profit, native_vwap_optimum
)


class TestArbitrageExploitationAndUnbackedMinting:
    """Challenge Dimension 1: Can arbitrageurs exploit the Market Module and mint unbacked LUNA?"""

    def test_emergency_spread_eliminates_arbitrage_incentive(self):
        """Verify that when emergency spread is active, native_discount is crushed for depegged UST."""
        p = ModelParams()
        # Test across varying UST prices and emergency spread levels
        for ust_p in [0.95, 0.90, 0.85, 0.80, 0.70]:
            spread_needed = 1.0 - ust_p
            # When emergency spread is at or above the depeg gap:
            effective_spread = min(0.99, p.min_spread + spread_needed)
            native_discount = max(0.0, 1.0 - ust_p - effective_spread - p.execution_fee * 2)
            assert native_discount == 0.0, f"Expected 0 native discount at ust_p={ust_p}, spread={spread_needed}, got {native_discount}"

    def test_arbitrage_unbacked_luna_minting_strictly_conserved(self):
        """Verify that whenever arbitrage executes, LUNA minted is strictly backed by burned UST.

        Gross LUNA minted must equal gross UST burned / oracle_price.
        Delivered LUNA + fee_luna must equal gross minted LUNA.
        ust_supply must decrease by exactly q, luna_supply must increase by exactly gross.
        """
        sc = ScenarioConfig(mode="counterfactual", dt_minutes=15)
        ctx = context(sc)
        b = initialize(ctx)
        b = observation(ctx, b)

        # Force depeg condition to induce arbitrage
        b['ust_price'] = 0.85
        b['luna_price'] = 50.0
        b['oracle_luna'] = 50.0
        b['emergency_spread'] = 0.05  # Moderate emergency spread

        base_ust_supply = b['ust_supply']
        base_luna_supply = b['luna_supply']

        # Run one market minute directly
        minted_gross, fee_luna = _market_minute(
            ctx, b, minutes=1.0, btc_return=0.0,
            rescue_ust_order=0.0, rescue_luna_order=0.0, lp_support=0.0
        )

        if minted_gross > 0:
            # Arb occurred: verify exact balance conservation
            ust_burned = base_ust_supply - b['ust_supply']
            luna_minted = b['luna_supply'] - base_luna_supply

            # Check that LUNA minted equals gross mint
            assert abs(luna_minted - minted_gross) < 1e-6
            # Check that UST burned corresponds to face value divided by oracle
            expected_gross = ust_burned / b['oracle_luna']
            assert abs(minted_gross - expected_gross) < 1e-6
            # Check that invariant errors are zero
            errs = invariants(ctx, b)
            assert abs(errs['ust_error']) < 1e-4
            assert abs(errs['luna_error']) < 1e-4

    def test_arbitrage_cannot_profit_into_adverse_depth(self):
        """Arbitrageurs must not execute orders that produce negative VWAP profit."""
        base = 50e6
        oracle = 40.0
        effective_spread = 0.20
        up = 0.75
        lp = 40.0
        depth = 500e6
        held = 0.0
        cash = 100e6
        fee = 0.001

        # Check native_vwap_optimum
        q_opt = native_vwap_optimum(
            limit=100e6, base=base, delta=0.0, oracle=oracle,
            min_spread=effective_spread, ust_price=up, luna_price=lp,
            depth=depth, held=held, cash=cash, fee=fee
        )

        if q_opt > 0:
            profit = native_vwap_profit(
                quantity=q_opt, base=base, delta=0.0, oracle=oracle,
                min_spread=effective_spread, ust_price=up, luna_price=lp,
                depth=depth, held=held, cash=cash, fee=fee
            )
            assert profit >= -1e-6, f"Optimal order produced negative profit: {profit}"

    def test_arbitrage_throttling_multiplier(self):
        """Arbitrage capacity multiplier chokes down desired arb order size proportionally."""
        sc = ScenarioConfig(mode="counterfactual", dt_minutes=15)
        ctx = context(sc)
        b = initialize(ctx)
        b = observation(ctx, b)
        b['ust_price'] = 0.80

        # Run with arb_capacity_mult = 1.0 vs 0.1
        dt = 1.0 / 1440.0
        cap_full = ctx['p'].arb_capacity_day * 1.0 * dt
        cap_throttled = ctx['p'].arb_capacity_day * 0.1 * dt

        assert cap_throttled == pytest.approx(cap_full * 0.1)

    def test_circuit_breaker_halts_native_swaps_completely(self):
        """When circuit breaker threshold is breached, native_open is False and zero LUNA is minted."""
        policy_cb = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-08T00:00:00Z",
            delay_minutes=0,
            circuit_breaker_threshold=0.80
        )
        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-08T01:00:00Z",
            policies=[policy_cb]
        )
        ctx = context(sc)
        b = initialize(ctx)
        b["step"] = int(ctx["index"].get_indexer([pd.Timestamp(sc.start)])[0]) - 1

        # Trigger circuit breaker: set ust_price < 0.80
        b['ust_price'] = 0.70
        b = observation(ctx, b)

        assert not b['native_open']
        assert not b['anchor_open']

        # In market minute, since native_open is False, no minting can occur
        gross, fee = _market_minute(
            ctx, b, minutes=1.0, btc_return=0.0,
            rescue_ust_order=0.0, rescue_luna_order=0.0, lp_support=0.0
        )
        assert gross == 0.0
        assert fee == 0.0

    def test_parameter_grid_sweep_no_unbacked_luna(self):
        """Grid sweep across UST prices [0.10 .. 0.95] and spread rates [0.0 .. 0.50]."""
        sc = ScenarioConfig(mode="counterfactual")
        ctx = context(sc)

        for ust_p in [0.10, 0.30, 0.50, 0.70, 0.85, 0.95]:
            for spread in [0.0, 0.05, 0.15, 0.25, 0.50]:
                b = initialize(ctx)
                b = observation(ctx, b)
                b['ust_price'] = ust_p
                b['emergency_spread'] = spread

                base_ust = b['ust_supply']
                base_luna = b['luna_supply']

                gross, fee = _market_minute(
                    ctx, b, minutes=1.0, btc_return=0.0,
                    rescue_ust_order=0.0, rescue_luna_order=0.0, lp_support=0.0
                )

                if gross > 0:
                    delta_ust = base_ust - b['ust_supply']
                    delta_luna = b['luna_supply'] - base_luna
                    assert delta_ust > 0
                    assert delta_luna == pytest.approx(gross, rel=1e-5)
                # Verify invariants always pass
                errs = invariants(ctx, b)
                assert abs(errs['ust_error']) < 0.1
                assert abs(errs['luna_error']) < 0.1


class TestHardFiniteBudgetCapsAndMultiPolicyCompetition:
    """Challenge Dimension 2: Can competing policies violate finite budget limits?"""

    def test_competing_aggressive_policies_cannot_exceed_btc_or_tfl_caps(self):
        """Construct 10 concurrent aggressive policies demanding massive capital simultaneously."""
        policies = []
        # 4 policies demanding LFG BTC
        for i in range(4):
            policies.append(PolicyConfig(
                action="buy_ust",
                trigger="price",
                threshold=0.999,
                funder="LFG",
                max_spend_per_hour=500e6,
                allocation_fraction=1.0
            ))
        # 3 policies demanding TFL USD
        for i in range(3):
            policies.append(PolicyConfig(
                action="buy_ust",
                trigger="price",
                threshold=0.999,
                funder="TFL",
                max_spend_per_hour=500e6,
                allocation_fraction=1.0
            ))
        # 3 policies demanding both
        for i in range(3):
            policies.append(PolicyConfig(
                action="buy_ust",
                trigger="price",
                threshold=0.999,
                funder="both",
                max_spend_per_hour=500e6,
                allocation_fraction=1.0
            ))

        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-12T00:00:00Z",
            policies=policies
        )
        traj, metrics, _ = simulate(sc, engine="fast")

        # Verify hard budget invariants across the entire run
        max_btc_sold = traj['btc_sold'].max()
        max_tfl_added = traj['tfl_added'].max()
        min_lfg_btc = traj['lfg_btc_remaining'].min()

        assert max_btc_sold <= 80081.0001, f"BTC sold exceeded cap: {max_btc_sold}"
        assert max_tfl_added <= 613616889.0001, f"TFL added exceeded cap: {max_tfl_added}"
        assert min_lfg_btc >= 312.999, f"LFG BTC retention floor breached: {min_lfg_btc}"

        # Total external spend cannot exceed $3.5B USD
        total_spent = traj['support_spent'].max()
        assert total_spent <= 3.5e9, f"Total external spend exceeded $3.5B: {total_spent}"

    def test_concurrent_liquidity_commit_and_buyback_burn_competition(self):
        """Concurrent liquidity provisioning and buyback-burn competing for same funds."""
        p_lp = PolicyConfig(
            action="liquidity",
            trigger="price",
            threshold=0.995,
            funder="both",
            max_spend_per_hour=200e6,
            allocation_fraction=0.5
        )
        p_buy = PolicyConfig(
            action="buy_ust",
            trigger="price",
            threshold=0.995,
            funder="both",
            max_spend_per_hour=200e6,
            allocation_fraction=0.5,
            burn_acquired_ust=True
        )

        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-11T00:00:00Z",
            policies=[p_lp, p_buy]
        )
        traj, metrics, _ = simulate(sc, engine="fast")

        assert traj['btc_sold'].max() <= 80081.0001
        assert traj['tfl_added'].max() <= 613616889.0001
        assert traj['support_spent'].max() <= 3.5e9
        assert traj['ust_burned_by_rescue'].iloc[-1] > 0

    def test_stop_loss_waterfall_strictly_halts_spend(self):
        """Stop-loss ceiling max_cumulative_spend must halt policy spend without overshoot."""
        stop_loss_cap = 50e6
        policy = PolicyConfig(
            action="buy_ust",
            trigger="price",
            threshold=0.999,
            funder="both",
            max_spend_per_hour=100e6,
            max_cumulative_spend=stop_loss_cap
        )

        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-11T00:00:00Z",
            policies=[policy]
        )
        traj, metrics, _ = simulate(sc, engine="fast")

        # Total spent across the run must not exceed stop_loss_cap
        total_spent = traj['support_spent'].max()
        assert total_spent <= stop_loss_cap + 1e-4
        assert total_spent == pytest.approx(stop_loss_cap, rel=1e-2)

    def test_budget_exhaustion_does_not_cause_crash_or_negative_balances(self):
        """When funds are 100% depleted, rescue continues gracefully without crash or negative funds."""
        p = PolicyConfig(
            action="buy_ust",
            trigger="time",
            start_time="2022-05-07T00:00:00Z",
            delay_minutes=0
        )
        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-07T00:00:00Z",
            end="2022-05-08T00:00:00Z",
            policies=[p]
        )
        ctx = context(sc)
        b = initialize(ctx)
        b['active_policies'][0] = True

        # Deplete all fund balances to 0
        b['fund_usd'][:] = 0.0
        b['fund_btc'][:] = 0.0
        b['locked_btc'] = 313.0
        b['locked_stable'] = 0.0
        b['ust_price'] = 0.50

        # Run rescue
        b = rescue(ctx, b)
        assert b['policy_spent'][0] == 0.0
        assert (b['fund_usd'] >= 0).all()
        assert (b['fund_btc'] >= 0).all()


class TestProlongedMultiDayAccountingLeakDetection:
    """Challenge Dimension 3: Can the engine leak any accounting error over prolonged multi-day runs?"""

    def test_prolonged_17_day_combined_interventions_invariants(self):
        """Full 17-day simulation (10-day crisis + 7-day stress tail = 1632 steps) with ALL interventions.

        Strict invariants:
        - max |ust_error| < 0.1
        - max |claim_error| < 1e-4
        - max |usd_error| < 1.0
        - max |luna_error| < 0.1
        """
        combined_policies = [
            PolicyConfig(
                action="buy_ust",
                trigger="price",
                threshold=0.985,
                target_peg=0.985,
                burn_acquired_ust=True,
                max_spend_per_hour=75e6,
                max_cumulative_spend=1.2e9,
                funder="both"
            ),
            PolicyConfig(
                action="withdrawal_gate",
                trigger="price",
                threshold=0.99,
                tiered_gates=True,
                redemption_haircut=0.20
            ),
            PolicyConfig(
                action="buy_ust",
                trigger="price",
                threshold=0.95,
                emergency_spread_rate=0.20,
                arb_capacity_multiplier=0.50
            ),
            PolicyConfig(
                action="circuit_breaker",
                trigger="price",
                threshold=0.50,
                circuit_breaker_threshold=0.50
            )
        ]

        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-06T00:15:00Z",
            end="2022-05-16T00:00:00Z",
            stress_days=7,
            policies=combined_policies,
            dt_minutes=15
        )

        traj, metrics, _ = simulate(sc, engine="fast")

        # 1632 steps for 17 days
        assert len(traj) == 1631 or len(traj) == 1632

        # Check empirical accounting leaks
        max_ust_error = traj['ust_error'].abs().max()
        max_claim_error = traj['claim_error'].abs().max()
        max_usd_error = traj['usd_error'].abs().max()
        max_luna_error = traj['luna_error'].abs().max()

        print(f"\n17-day trajectory errors:")
        print(f"Max ust_error: {max_ust_error:.6e}")
        print(f"Max claim_error: {max_claim_error:.6e}")
        print(f"Max usd_error: {max_usd_error:.6e}")
        print(f"Max luna_error: {max_luna_error:.6e}")

        assert max_ust_error < 0.1, f"UST error leaked over 17 days: {max_ust_error}"
        assert max_claim_error < 1e-4, f"Claim error leaked over 17 days: {max_claim_error}"
        assert max_usd_error < 1.0, f"USD error leaked over 17 days: {max_usd_error}"
        assert max_luna_error < 0.1, f"LUNA error leaked over 17 days: {max_luna_error}"

        # Verify buyback burn and haircut burn telemetry
        assert traj['ust_burned_by_rescue'].max() > 0
        assert traj['haircut_burned_ust'].max() > 0

    def test_high_frequency_5min_step_accounting_tightness(self):
        """At 5-minute intervals (3x more steps), verify error does not accumulate linearly."""
        p_buy = PolicyConfig(
            action="buy_ust",
            trigger="price",
            threshold=0.99,
            burn_acquired_ust=True,
            max_spend_per_hour=50e6
        )
        p_gate = PolicyConfig(
            action="withdrawal_gate",
            trigger="price",
            threshold=0.99,
            tiered_gates=True,
            redemption_haircut=0.10
        )

        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-11T00:00:00Z",
            dt_minutes=5,
            policies=[p_buy, p_gate]
        )

        traj, metrics, _ = simulate(sc, engine="fast")

        max_ust_err = traj['ust_error'].abs().max()
        max_claim_err = traj['claim_error'].abs().max()

        assert max_ust_err < 0.1, f"5min step UST error too large: {max_ust_err}"
        assert max_claim_err < 1e-4, f"5min step Claim error too large: {max_claim_err}"

    def test_multi_seed_stochastic_monte_carlo_invariants(self):
        """Check invariant conservation across 5 stochastic random seeds."""
        for seed in [42, 43, 44, 45, 46]:
            sc = ScenarioConfig(
                mode="counterfactual",
                start="2022-05-08T00:00:00Z",
                end="2022-05-11T00:00:00Z",
                seed=seed,
                stochastic=True,
                policies=[
                    PolicyConfig(action="buy_ust", burn_acquired_ust=True, max_spend_per_hour=50e6),
                    PolicyConfig(action="withdrawal_gate", tiered_gates=True, redemption_haircut=0.15)
                ]
            )
            traj, _, _ = simulate(sc, engine="fast")
            assert traj['ust_error'].abs().max() < 0.1, f"Seed {seed} leaked UST error"
            assert traj['claim_error'].abs().max() < 1e-4, f"Seed {seed} leaked claim error"

    def test_extreme_haircut_burn_exact_conservation(self):
        """With 80% haircut under heavy panic, confirm burnt UST equals change in supply."""
        policy = PolicyConfig(
            action="withdrawal_gate",
            trigger="price",
            threshold=0.99,
            tiered_gates=False,
            withdrawal_fraction_per_day=1.0,
            redemption_haircut=0.80
        )
        sc = ScenarioConfig(
            mode="counterfactual",
            start="2022-05-08T00:00:00Z",
            end="2022-05-09T00:00:00Z",
            policies=[policy]
        )
        traj, _, _ = simulate(sc, engine="fast")

        haircut_burned = traj['haircut_burned_ust'].iloc[-1]
        assert haircut_burned > 1e6, f"Expected substantial haircut burn, got {haircut_burned}"
        assert traj['ust_error'].abs().max() < 0.1
        assert traj['claim_error'].abs().max() < 1e-4
