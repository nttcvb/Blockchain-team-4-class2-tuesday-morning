"""Historical validation exports, physical failures, and resolution alignment."""
from dataclasses import asdict
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from luna_sim import calibrate, config, metrics, reconstruction_validation as validation


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch):
    original = config.ROOT
    for relative in ("luna_sim/calibrate.py", "luna_sim/engine.py", "luna_sim/config.py",
            "luna_sim/data.py", "luna_sim/metrics.py", "luna_sim/audit.py",
            "luna_sim/reconstruction_validation.py", "data/sources.json",
            "data/external/btc_usdt_minute.parquet", "data/external/btc_metadata.json"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((original / relative).read_bytes())
    monkeypatch.setattr(validation, "ROOT", tmp_path)
    monkeypatch.setattr(calibrate, "ROOT", tmp_path)
    cfg = config.ScenarioConfig(end="2022-05-06T01:15:00Z", mode="historical",
        seed=42, stochastic=False, funding_timing="early", stress_days=0, policies=[])
    targets, groups = {}, {}
    for dt in (15, 5):
        index = pd.date_range(cfg.start, cfg.end, freq=f"{dt}min", inclusive="left")
        elapsed = (index - index[0]).total_seconds().to_numpy() / 900
        targets[dt] = pd.DataFrame({"ust_price": np.full(len(index), .90),
            "luna_price": 80 - elapsed, "luna_supply": 7e8 + elapsed * 1e6,
            "anchor_deposits": 14e9 - elapsed * 1e8, "native_ust": np.full(len(index), 1e8 * dt / 15),
            "native_fee": np.full(len(index), .005)}, index=index)
        groups[dt] = pd.DataFrame({i: .95 - elapsed * .03 for i in range(6)}, index=index)

    def target_loader(dt=15):
        return targets[dt].copy()

    def group_loader(dt=15):
        return groups[dt].copy()

    target_loader.cache_clear = group_loader.cache_clear = lambda: None
    for module in (metrics, validation):
        monkeypatch.setattr(module, "load_targets", target_loader)
        monkeypatch.setattr(module, "group_targets", group_loader)

    def trajectory(dt):
        frame = targets[dt].drop(columns=["native_ust"]).assign(native_served=targets[dt].native_ust)
        for column in validation.OWNED_COLUMNS:
            frame[column] = 1e6
        frame["market_usd"] = cfg.params.market_cash_usd
        frame["arbitrage_cash_usd"] = cfg.params.arb_capital_usd
        frame["anchor_cash"] = 10e9
        frame["ust_supply"] = 18e9
        frame["tfl_added"] = 0.
        for column in validation.ERROR_COLUMNS:
            frame[column] = 0.
        for i in range(6):
            frame[f"group_{i}_remaining"] = groups[dt][i]
        return frame

    folder = tmp_path / "outputs" / "calibration"
    folder.mkdir(parents=True)
    path_15 = trajectory(15)
    for split, parameter_name in (("train", "parameters.json"), ("all", "parameters_full_fit.json")):
        write_json(folder / parameter_name, asdict(cfg.params))
        write_json(folder / f"config_{split}.json", cfg.to_dict())
        report = {"optimizer": {"run_id": f"run_{split}"}, "all": metrics.fit_metrics(path_15)}
        status = {"status": "complete", "run_id": f"run_{split}"}
        write_json(folder / f"report_{split}.json", report)
        write_json(folder / f"calibration_status_{split}.json", status)
        path_15.to_parquet(folder / f"trajectory_{split}.parquet")
        archive = folder / "runs" / f"run_{split}"
        write_json(archive / "report.json", report)
        write_json(archive / "execution.json", status)
        path_15.to_parquet(archive / "trajectory.parquet")
    calls, audited = [], []
    controls = {"seed43_ust_delta": .005, "bad_owner": False, "change_5min_input": False,
                "empty_ledger": False}

    def fake_simulate(run_config, engine, keep_ledger):
        calls.append((run_config, engine, keep_ledger))
        frame = trajectory(run_config.dt_minutes)
        if run_config.stochastic and run_config.seed == 43:
            frame.ust_price += controls["seed43_ust_delta"]
        if controls["bad_owner"]:
            frame.arbitrage_luna = -1.
        if controls["change_5min_input"] and run_config.dt_minutes == 5:
            targets[5].iloc[0, 0] += .02
        execution = {"engine": engine, "runtime_seconds": .01,
            "engine_source_sha256": hashlib.sha256((tmp_path / "luna_sim" / "engine.py").read_bytes()).hexdigest()}
        ledger = pd.DataFrame([{"time": frame.index[0], "kind": "test_event", "owner": "market",
            "amount": 1., "asset": "UST"}]) if keep_ledger else pd.DataFrame()
        if controls["empty_ledger"]:
            ledger = pd.DataFrame()
        return frame, execution, ledger

    def audit_stub(split, sources):
        # The real read-only audit is tested separately. This fixture substitutes
        # only that expensive boundary and keeps file/provenance guards genuine.
        audited.append(split)
        assert sources == calibrate._source_hashes()
        return {"run_id": f"run_{split}", "rows": len(path_15),
            "report_metrics_recomputed": True, "financial_metrics_recomputed": True,
            "published_trajectory_matches_run_archive": True}

    monkeypatch.setattr(validation, "simulate", fake_simulate)
    monkeypatch.setattr(validation, "audit_calibration", audit_stub)
    return {"root": tmp_path, "config": cfg, "targets": targets, "groups": groups,
            "trajectory": trajectory, "calls": calls, "audited": audited, "controls": controls}


def test_historical_seeds_and_deterministic_resolution_are_exported(project):
    result = validation.run_reconstruction_checks(seeds=2)
    assert project["audited"] == ["train", "all"]
    assert [(cfg.seed, cfg.dt_minutes, cfg.stochastic, ledger) for cfg, _, ledger in project["calls"]] == [
        (42, 15, True, True), (43, 15, True, False), (42, 5, False, False)]
    for cfg, engine, _ in project["calls"]:
        assert engine == "cadcad" and cfg.mode == "historical" and cfg.funding_timing == "early"
        assert cfg.stress_days == 0 and cfg.policies == [] and cfg.params == project["config"].params
    assert result["seed_runs_passing_all_gates"] == 2
    assert set(result["gate_pass_counts"].values()) == {2}
    assert set(result["resolution_comparison"].values()) == {0.}
    assert validation.reconstruction_checks_current()
    folder = project["root"] / "outputs" / "reconstruction" / "validation"
    assert (folder / "seed42" / "ledger.csv").is_file()
    assert not (folder / "seed43" / "ledger.csv").exists()
    assert not (project["root"] / "outputs" / "experiments").exists()
    for seed in (42, 43):
        payload = json.loads((folder / f"seed{seed}" / "metrics.json").read_text(encoding="utf-8"))
        assert len(payload["fit"]["gates"]) == 6 and payload["physical_checks"]["passes"]
    bands = pd.read_parquet(folder / "bands.parquet")
    assert set(bands["quantile"]) == {"p05", "median", "p95"}
    first = bands[bands.time.eq(project["targets"][15].index[0])].set_index("quantile")
    assert first.loc["p05", "ust_price"] == pytest.approx(.90025)
    assert first.loc["median", "ust_price"] == pytest.approx(.9025)
    assert first.loc["p95", "ust_price"] == pytest.approx(.90475)
    assert "bất định cấu trúc" in result["qualification"] and "trong mẫu" in result["qualification"]


def test_fidelity_failure_is_reported_without_a_false_physical_failure(project):
    project["controls"]["seed43_ust_delta"] = .2
    result = validation.run_reconstruction_checks(seeds=2)
    assert result["seed_runs_passing_all_gates"] == 1
    assert result["gate_pass_counts"]["ust_mae"] == 1
    assert validation.reconstruction_checks_current()


@pytest.mark.parametrize("failure", ["nonfinite", "negative_owner", "missing_owner", "missing_time",
                                     "zero_price", "negative_supply", "accounting"])
def test_exported_trajectory_checks_detect_real_failures(project, failure):
    frame = project["trajectory"](15)
    if failure == "nonfinite":
        frame.loc[frame.index[0], "luna_price"] = np.inf
    elif failure == "negative_owner":
        frame.loc[frame.index[0], "arbitrage_cash_usd"] = -1.
    elif failure == "missing_owner":
        frame = frame.drop(columns="arbitrage_luna")
    elif failure == "missing_time":
        frame = frame.iloc[1:]
    elif failure == "zero_price":
        frame.loc[frame.index[0], "luna_price"] = 0.
    elif failure == "negative_supply":
        frame.loc[frame.index[0], "ust_supply"] = -1.
    else:
        frame.loc[frame.index[0], "ust_error"] = 50.
    with pytest.raises(ValueError):
        validation.trajectory_checks(frame, project["config"])


def test_accounting_errors_use_explicit_recorded_scales(project):
    frame = project["trajectory"](15)
    frame.ust_error = 2.
    frame.usd_error = .01
    assessed = validation.trajectory_checks(frame, project["config"])
    assert assessed["maximum_absolute_accounting_errors"]["ust_error"] == 2.
    assert assessed["maximum_relative_accounting_errors"]["ust_error"] == pytest.approx(2 / 18e9)
    assert "cận dưới" in assessed["accounting_reference_basis"]["usd_error"]
    lower_bound_ratio = assessed["maximum_relative_accounting_errors"]["usd_error"]
    frame["btc_cash_created"] = 2e9
    with_btc = validation.trajectory_checks(frame, project["config"])
    assert with_btc["maximum_relative_accounting_errors"]["usd_error"] < lower_bound_ratio
    assert "cận dưới" not in with_btc["accounting_reference_basis"]["usd_error"]


def test_resolution_comparison_has_known_errors_at_identical_times(project):
    path_15, path_5 = project["trajectory"](15), project["trajectory"](5)
    path_5.ust_price += .02
    path_5.anchor_deposits += 14e9 * .03
    path_5.luna_price *= 10
    path_5.luna_supply *= 100
    comparison = validation.resolution_comparison(path_15, path_5, initial_anchor_deposits=14e9)
    assert comparison["ust_mae_between_steps"] == pytest.approx(.02)
    assert comparison["deposit_nrmse_between_steps"] == pytest.approx(.03)
    assert comparison["luna_price_log_rmse_between_steps"] == pytest.approx(1.)
    assert comparison["luna_supply_log_rmse_between_steps"] == pytest.approx(2.)
    assert comparison["comparison_rows"] == len(path_15)


def test_resolution_comparison_never_fills_missing_timestamps(project):
    path_15, path_5 = project["trajectory"](15), project["trajectory"](5)
    with pytest.raises(ValueError, match="thiếu thời điểm"):
        validation.resolution_comparison(path_15, path_5.iloc[1:], 14e9)
    path_5.loc[path_5.index[0], "luna_supply"] = 0.
    with pytest.raises(ValueError, match="phải dương"):
        validation.resolution_comparison(path_15, path_5, 14e9)


def test_resolution_comparison_rejects_unlabelled_timezones(project):
    path_15, path_5 = project["trajectory"](15), project["trajectory"](5)
    path_15.index = path_15.index.tz_localize(None)
    path_5.index = path_5.index.tz_localize(None)
    with pytest.raises(ValueError, match="UTC"):
        validation.resolution_comparison(path_15, path_5, 14e9)


@pytest.mark.parametrize("change", ["source", "parameter", "archive", "target5", "group5",
                                    "result", "missing_seed_file", "running_status", "bad_manifest"])
def test_validation_guard_rejects_changed_inputs_or_partial_artifacts(project, change):
    validation.run_reconstruction_checks(seeds=2)
    root = project["root"]
    directory = root / "outputs" / "reconstruction" / "validation"
    if change == "source":
        path = root / "luna_sim" / "engine.py"
        path.write_bytes(path.read_bytes() + b"\n# other version\n")
    elif change == "parameter":
        path = root / "outputs" / "calibration" / "parameters_full_fit.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["hazard_base"] -= 1
        write_json(path, payload)
    elif change == "archive":
        write_json(root / "outputs" / "calibration" / "runs" / "run_all" / "execution.json", {"status": "changed"})
    elif change == "target5":
        project["targets"][5].iloc[0, 0] += .02
    elif change == "group5":
        project["groups"][5].iloc[0, 0] = .1
    elif change == "result":
        (directory / "timestep_check.json").write_text("{}", encoding="utf-8")
    elif change == "missing_seed_file":
        (directory / "seed43" / "trajectory.parquet").unlink()
    elif change == "running_status":
        write_json(root / "outputs" / "calibration" / "calibration_status_all.json", {"status": "running", "run_id": "run_all"})
    else:
        write_json(directory / "manifest.json", [])
    assert not validation.reconstruction_checks_current()


def test_negative_owned_stock_marks_run_failed(project):
    project["controls"]["bad_owner"] = True
    with pytest.raises(ValueError, match="chủ sở hữu âm"):
        validation.run_reconstruction_checks(seeds=2)
    manifest = json.loads((project["root"] / "outputs" / "reconstruction" / "validation" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed" and manifest["completed_seeds"] == []
    assert not validation.reconstruction_checks_current()


def test_seed42_needs_an_actual_event_ledger(project):
    project["controls"]["empty_ledger"] = True
    with pytest.raises(ValueError, match="bảng không rỗng"):
        validation.run_reconstruction_checks(seeds=2)
    assert not validation.reconstruction_checks_current()


def test_input_change_during_run_prevents_completion(project):
    project["controls"]["change_5min_input"] = True
    with pytest.raises(ValueError, match="đã thay đổi"):
        validation.run_reconstruction_checks(seeds=2)
    manifest = json.loads((project["root"] / "outputs" / "reconstruction" / "validation" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed" and manifest["completed_seeds"] == [42, 43]
    assert not validation.reconstruction_checks_current()


def test_failed_calibration_audit_prevents_validation_run(project, monkeypatch):
    def failed(*args):
        raise AssertionError("all: stale calibration")

    monkeypatch.setattr(validation, "audit_calibration", failed)
    with pytest.raises(AssertionError, match="stale calibration"):
        validation.run_reconstruction_checks(seeds=2)
    assert project["calls"] == []
    assert not (project["root"] / "outputs" / "reconstruction" / "validation").exists()


@pytest.mark.parametrize("seeds", [0, -1, True, 1.5])
def test_seed_count_must_be_positive_integer(project, seeds):
    with pytest.raises(ValueError, match="nguyên dương"):
        validation.run_reconstruction_checks(seeds=seeds)
    assert project["audited"] == [] and project["calls"] == []
