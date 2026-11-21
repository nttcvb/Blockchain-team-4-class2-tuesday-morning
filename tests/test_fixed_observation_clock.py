"""Regressions for the fixed UTC LUNA observation cadence."""
from dataclasses import replace
import hashlib
import importlib.util
import json
import math

import numpy as np
import pandas as pd
import pytest

from luna_sim import engine as E
from luna_sim.config import ROOT, ScenarioConfig


FROZEN = ROOT / "baselines/v3_frozen_20261011T010500Z"
V3_ENGINE_SHA = "0a89a9e690c7998d8fadaa1756466b6195b67219483320403672a441cd95f7ea"


def frozen_engine():
    path = FROZEN / "luna_sim/engine.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == V3_ENGINE_SHA
    spec = importlib.util.spec_from_file_location("luna_sim._v3_fixed_clock_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observation_book(dt):
    ctx = E.context(ScenarioConfig(dt_minutes=dt, n_depositors=40, stochastic=False,
                                  end="2022-05-06T05:00:00Z"))
    ctx["facts"] = {**ctx["facts"], "luna_price": 100.}
    return ctx, E.initialize(ctx)


def test_completed_quarter_hours_skip_interim_falls_and_recoveries():
    ctx, book = observation_book(5)
    prices = [95., 60., 120., 90., 30., 110., 99.]
    for time, price in zip(ctx["index"], prices):
        book["time"] = time
        book["luna_price"] = price
        book = E.accounting(ctx, book)
    expected = [math.log(100 / 95), 0., 0., math.log(95 / 90), 0., 0., 0.]
    np.testing.assert_array_equal(book["signals"][:, 2], expected)
    # The sparse LUNA signal does not alter discount, per-step outflow or price history.
    np.testing.assert_array_equal(book["signals"][:, 4], prices)


def test_clock_uses_utc_boundaries_even_for_offset_timestamp():
    ctx, book = observation_book(5)
    book["luna_price"] = 80.
    book["time"] = pd.Timestamp("2022-05-06T05:25:00+05:10")  # UTC 00:15.
    book = E.accounting(ctx, book)
    assert book["signals"][-1, 2] == math.log(100 / 80)
    book["luna_price"] = 40.
    book["time"] = pd.Timestamp("2022-05-06T05:30:00+05:10")  # UTC 00:20.
    book = E.accounting(ctx, book)
    assert book["signals"][-1, 2] == 0.


@pytest.mark.parametrize("lag_minutes", [15, 60, 120])
def test_same_market_path_has_same_hourly_luna_signal_at_same_physical_lag(lag_minutes, monkeypatch):
    # Endpoints alternate declines/recoveries; 5-minute quotes have large
    # temporary falls inside those same quarters. Only completed endpoints count.
    endpoints = np.array([100., 90., 99., 85., 95., 80., 88., 79., 86.,
                          74., 83., 70., 77., 65., 75., 62., 70., 60., 69.])
    captured = []
    normal_expit = E.expit

    def capture_expit(value):
        if isinstance(value, np.ndarray):
            captured.append(value.copy())
        return normal_expit(value)

    monkeypatch.setattr(E, "expit", capture_expit)
    signals = {}
    for dt in (15, 5):
        ctx, book = observation_book(dt)
        ctx["agents"] = ctx["agents"].copy()
        ctx["agents"]["lag_minutes"] = lag_minutes
        ctx["p"] = replace(ctx["p"], hazard_base=0., hazard_size=0.,
                           hazard_discount=0., hazard_outflow=0.,
                           hazard_queue=0., hazard_luna=1.)
        observations = {}
        decisions = {}
        for time in pd.date_range("2022-05-06T00:15:00Z", periods=18 * 15 // dt + 1,
                                  freq=f"{dt}min"):
            elapsed = int((time - ctx["index"][0]).total_seconds() // 60)
            quarter, offset = divmod(elapsed, 15)
            price = endpoints[quarter] if offset == 0 else endpoints[quarter] * (.4 if offset == 5 else 1.4)
            book["time"] = time
            E.decisions(ctx, book)
            if time.minute % 15 == 0:
                decisions[time] = captured[-1]
            book["luna_price"] = price
            book = E.accounting(ctx, book)
            if time.minute % 15 == 0:
                observations[time] = book["signals"][-1, 2]
        signals[dt] = observations, decisions
    assert signals[5][0] == signals[15][0]
    assert signals[5][1].keys() == signals[15][1].keys()
    for time in signals[15][1]:
        np.testing.assert_allclose(signals[5][1][time], signals[15][1][time],
                                   rtol=1e-14, atol=1e-14)
        # At 03:00, the observed hour ends exactly lag_minutes earlier.
        if time == pd.Timestamp("2022-05-06T03:00:00Z"):
            last = int((time - pd.Timedelta(minutes=lag_minutes) - ctx["index"][0]).total_seconds() // 900)
            expected = sum(max(0., math.log(endpoints[i - 1] / endpoints[i]))
                           for i in range(max(1, last - 3), last + 1))
            np.testing.assert_allclose(signals[15][1][time], expected, rtol=1e-14, atol=1e-14)


def test_fixed_observation_alone_preserves_entire_frozen_15min_trajectory(monkeypatch):
    # Restore the old protocol step only inside this regression, isolating the
    # observation-clock change from the separately required capacity correction.
    legacy = frozen_engine()
    monkeypatch.setattr(E, "observation", legacy.observation)
    monkeypatch.setattr(E, "BLOCKS", [legacy.observation, E.rescue, E.decisions,
                                     E.anchor, E.markets, E.accounting])
    config = ScenarioConfig.from_dict(json.loads((FROZEN / "outputs/calibration/config_all.json")
                                                 .read_text(encoding="utf-8")))
    expected = pd.read_parquet(FROZEN / "outputs/calibration/trajectory_all.parquet")
    actual, metrics, _ = E.simulate(config, engine="fast", keep_ledger=False)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    assert len(actual) == 959
    assert max(metrics["max_accounting_errors"].values()) < .1

