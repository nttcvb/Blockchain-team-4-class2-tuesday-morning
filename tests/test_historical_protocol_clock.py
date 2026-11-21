"""Historical capacity stays configured until an evidenced parameter change."""
from dataclasses import replace
import json
import math

import pandas as pd
import pytest

from luna_sim import engine as E
from luna_sim.config import ModelParams, PolicyConfig, ROOT, ScenarioConfig


@pytest.mark.parametrize("dt", [5, 15])
def test_no_historical_capacity_jump_during_observed_window(dt):
    policy = PolicyConfig("native_swap", trigger="time", delay_minutes=0,
                          pool_multiplier=6., recovery_multiplier=.25)
    config = ScenarioConfig(dt_minutes=dt, n_depositors=40, stochastic=False,
                            policies=[policy])
    ctx = E.context(config)
    book = E.initialize(ctx)
    for _ in ctx["index"]:
        book = E.observation(ctx, book)
        assert book["pool_multiplier"] == 1.
        assert book["recovery_multiplier"] == 1.
        assert not book["active_policies"].any()

    proposal = json.loads((ROOT / "outputs/improvement/governance_1164_evidence/"
                           "proposal_1164.json").read_text(encoding="utf-8"))["proposal"]
    assert pd.Timestamp(proposal["voting_end_time"]) > ctx["index"][-1]
    assert pd.Timestamp(proposal["submit_time"]) < pd.Timestamp("2022-05-11T12:00:00Z")


@pytest.mark.parametrize("dt", [5, 15])
def test_market_uses_configured_pool_recovery_and_arbitrage_limit_across_may11(dt, monkeypatch):
    params = replace(ModelParams(), base_pool_usd=37e6, recovery_minutes=2.4,
                     arb_capacity_day=864e6, normal_demand_day=0.)
    ctx = E.context(ScenarioConfig(dt_minutes=dt, n_depositors=40,
                                  stochastic=False, params=params))
    quotes = []

    def no_order(limit, base, *unused):
        quotes.append((limit, base))
        return 0.

    monkeypatch.setattr(E, "native_vwap_optimum", no_order)
    for timestamp in ["2022-05-11T11:45:00Z", "2022-05-11T12:00:00Z",
                      "2022-05-12T00:00:00Z", "2022-05-15T23:45:00Z"]:
        book = E.initialize(ctx)
        book["step"] = ctx["index"].get_loc(pd.Timestamp(timestamp)) - 1
        book = E.observation(ctx, book)
        book["ust_price"] = .8
        book["virtual_delta"] = 1e6
        E._market_minute(ctx, book, 1., 0., 0., 0., 0.)
        assert quotes[-1] == (params.arb_capacity_day / 1440, params.base_pool_usd)
        assert book["virtual_delta"] == 1e6 * math.exp(-1 / params.recovery_minutes)
        E.invariants(ctx, book)


@pytest.mark.parametrize("mode", ["historical", "no_rescue", "counterfactual"])
def test_native_capacity_policy_applies_only_in_counterfactual_mode(mode):
    policy = PolicyConfig("native_swap", trigger="time",
                          start_time="2022-05-11T12:00:00Z", delay_minutes=0,
                          duration_hours=1, pool_multiplier=6., recovery_multiplier=.25)
    ctx = E.context(ScenarioConfig(mode=mode, n_depositors=40,
                                  stochastic=False, policies=[policy]))
    book = E.initialize(ctx)
    book["step"] = ctx["index"].get_loc(pd.Timestamp(policy.start_time)) - 1
    book = E.observation(ctx, book)
    if mode == "counterfactual":
        assert book["active_policies"].tolist() == [True]
        assert book["pool_multiplier"] == 6.
        assert book["recovery_multiplier"] == .25
    else:
        assert book["active_policies"].tolist() == [False]
        assert book["pool_multiplier"] == book["recovery_multiplier"] == 1.
    assert ctx["p"].arb_capacity_day == ctx["config"].params.arb_capacity_day

