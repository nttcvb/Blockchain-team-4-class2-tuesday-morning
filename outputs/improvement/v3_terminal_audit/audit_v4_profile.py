"""Saved-artifact profile audit: never invokes engine.simulate or an optimizer."""
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
import ctypes
import hashlib
import importlib
import json
import os
import sys
import types

sys.dont_write_bytecode = True
HELPER = Path(__file__).resolve()
ROOT = HELPER.parents[3]
PROFILE = ROOT / "outputs/improvement/v4_start_profile/20261011T071616931333Z"
FROZEN = ROOT / "baselines/v3_frozen_20261011T010500Z"
RAW = Path(r"D:\New folder\terra-luna-run-replication (1)\terra-luna-run-replication")
os.environ["LUNA_SOURCE_DIR"] = str(RAW)
package = types.ModuleType("_v4_profile_saved")
package.__path__ = [str(PROFILE / "source"), str(ROOT / "luna_sim")]
sys.modules[package.__name__] = package
K = importlib.import_module(package.__name__ + ".config")
K.ROOT = ROOT
C = importlib.import_module(package.__name__ + ".calibrate")
D = importlib.import_module(package.__name__ + ".data")
M = importlib.import_module(package.__name__ + ".metrics")
V = importlib.import_module(package.__name__ + ".reconstruction_validation")
import numpy as np
import pandas as pd


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_binding(expected):
    actual = {name: sha(ROOT / name if "/" in name else ROOT / "luna_sim" / name) for name in expected}
    assert actual == expected
    for name, value in expected.items():
        if "/" not in name:
            assert sha(PROFILE / "source" / name) == value
    assert sha(PROFILE / "source/driver.py") == sha(ROOT / "outputs/improvement/v4_start_profile.py")
    return {"current_source_matches_recorded_profile": True, "archived_five_modules_match": True,
            "driver_sha256": sha(PROFILE / "source/driver.py"), "source_sha256": actual}


def target_identity(saved, rebuilt, expected):
    pd.testing.assert_frame_equal(saved, rebuilt, check_exact=True, check_freq=False)
    assert C._frame_hash(rebuilt) == expected
    differences = []
    for col in saved.select_dtypes(include="float64"):
        a, b = saved[col].to_numpy(), rebuilt[col].to_numpy()
        for i in np.flatnonzero(a.view("uint64") != b.view("uint64")):
            assert np.isnan(a[i]) and np.isnan(b[i])
            differences.append({"column": str(col), "time_utc": saved.index[i].isoformat(),
                                "saved_bits": hex(int(a.view("uint64")[i])), "rebuilt_bits": hex(int(b.view("uint64")[i]))})
    return {"recorded_in_memory_frame_sha256": expected, "saved_parquet_frame_sha256": C._frame_hash(saved),
            "raw_rebuild_matches_recorded_hash": True, "values_dtypes_time_and_missingness_exact": True,
            "nan_bitpattern_differences": differences, "qualification": "Legacy frame hashing distinguishes NaN sign bits; files and original hashes remain untouched."}


def pid_live(pid):
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        assert ctypes.get_last_error() == 87
        return False
    code = wintypes.DWORD()
    try:
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259
    finally:
        kernel.CloseHandle(handle)


def main():
    plan, result, status = read(PROFILE / "plan.json"), read(PROFILE / "result.json"), read(PROFILE / "status.json")
    before = source_binding(plan["source_sha256"])
    assert result["source_sha256"] == plan["source_sha256"]
    assert result["raw_sha256"] == plan["raw_sha256"]
    assert len(plan["raw_sha256"]) == 12
    for name, digest in plan["raw_sha256"].items():
        assert sha(RAW / "data" / name) == digest
    assert plan["primary_simulations"] == 17 and plan["verification_simulations"] == 1
    assert plan["hard_simulation_budget"] == result["budget"] == result["simulations"] == status["hard_budget"] == status["simulations"] == 18
    assert result["status"] == "complete_private_profile_not_promoted" and status["status"] == "complete"
    assert result["runtime_seconds"] <= status["elapsed_seconds"] < result["runtime_seconds"] + .1
    assert not pid_live(status["process_id"])
    base = K.ScenarioConfig.from_dict(plan["base_config"])
    assert plan["base_config"] == read(FROZEN / "outputs/calibration/config_all.json")
    assert not base.stochastic and base.dt_minutes == 15 and base.stress_days == 0 and not base.policies
    targets, groups = pd.read_parquet(PROFILE / "targets.parquet"), pd.read_parquet(PROFILE / "groups.parquet")
    target_identity_result = target_identity(targets, D.load_targets().copy(), plan["target_frame_sha256"])
    group_identity_result = target_identity(groups, D.group_targets().copy(), plan["group_frame_sha256"])
    M.load_targets = lambda dt=15: targets
    M.group_targets = lambda dt=15: groups
    V.load_targets = lambda dt=15: targets
    targets.attrs["initial_deposits"] = float(targets.anchor_deposits.iloc[0])
    objective = C.CalibrationObjective(base, targets, groups, base.params)
    assert len(result["all_results"]) == len(plan["candidates"]) == 17
    case_audits = []
    frames = {}
    for candidate, record in zip(plan["candidates"], result["all_results"]):
        assert candidate == {"name": record["name"], "parameters": record["parameters"]}
        assert "error" not in record
        name = record["name"]
        assert read(PROFILE / (name + ".json")) == record
        cfg = replace(base, params=K.ModelParams(**record["parameters"]))
        trajectory = pd.read_parquet(PROFILE / (name + ".parquet"))
        frames[name] = trajectory
        assert len(trajectory) == 959
        recomputed = objective.components(trajectory)
        assert recomputed == record["objective"]
        for split in ("all", "train", "validation"):
            assert M.fit_metrics(trajectory, 15, split) == record["metrics"][split]
        financial = M.evaluate(trajectory, cfg)
        assert financial == {k: v for k, v in record["financial"].items() if k not in ("runtime_seconds", "engine", "seed", "engine_source_sha256")}
        assert record["financial"]["engine"] == "fast" and record["financial"]["seed"] == 42
        assert record["financial"]["engine_source_sha256"] == plan["source_sha256"]["engine.py"]
        for col, value in record["final_stocks"].items():
            assert value == float(trajectory[col].iloc[-1])
        physical = V.trajectory_checks(trajectory, cfg)
        assert physical["passes"]
        case_audits.append({"name": name, "objective_recomputed_exact": True, "metrics_all_train_validation_exact": True,
                            "financial_recomputed_exact": True, "parameter_sha256": C.parameter_sha256(cfg.params),
                            "trajectory_file_sha256": sha(PROFILE / (name + ".parquet")),
                            "trajectory_frame_sha256": C._frame_hash(trajectory), "physical_checks": physical,
                            "loss": record["objective"]["loss"], "gate_counts": {s: sum(record["metrics"][s]["gates"].values()) for s in record["metrics"]}})
    best = min(result["all_results"], key=lambda r: r["objective"]["loss"])
    assert best == result["best"]
    assert status["best_name"] == best["name"] and status["best_loss"] == best["objective"]["loss"]
    assert read(PROFILE / "best_parameters.json") == best["parameters"]
    cfg = replace(base, params=K.ModelParams(**best["parameters"]))
    assert cfg.to_dict() == read(PROFILE / "best_config.json")
    fast, cad = frames[best["name"]], pd.read_parquet(PROFILE / "best_cadcad.parquet")
    pd.testing.assert_frame_equal(fast, cad, check_exact=True, check_freq=False)
    assert result["fast_cadcad_exact"] is True
    ignored = ("engine", "runtime_seconds")
    assert {k: v for k, v in best["financial"].items() if k not in ignored} == {k: v for k, v in result["cadcad_financial"].items() if k not in ignored}
    assert result["cadcad_financial"]["engine"] == "cadcad"
    ledger = pd.read_parquet(PROFILE / "best_ledger.parquet")
    assert len(ledger) > 0 and {"time", "kind", "owner", "amount", "asset"}.issubset(ledger.columns)
    assert ledger[["time", "kind", "owner", "amount", "asset"]].notna().all().all()
    assert np.isfinite(ledger.amount.to_numpy()).all() and ledger.amount.min() >= -.001
    assert ledger.time.isin(cad.index).all()
    native = ledger.loc[ledger.kind.eq("native_burn")]
    withdrawal = ledger.loc[ledger.kind.eq("anchor_withdrawal")]
    initial = D.initial_facts()
    totals = {"native_burn_ust": float(native.amount.sum()), "trajectory_native_served_ust": float(cad.native_served.sum()),
              "native_luna_minted": float(native.luna_minted.sum()), "supply_growth_luna": float(cad.luna_supply.iloc[-1] - initial["luna_supply"]),
              "native_fee_luna": float(native.fee_luna.sum()), "final_fee_luna": float(cad.fee_luna.iloc[-1]),
              "anchor_withdrawal_ust": float(withdrawal.amount.sum()), "trajectory_withdraw_served_ust": float(cad.withdraw_served.sum()),
              "native_luna_delivered": float(native.luna_delivered.sum())}
    reconciliation = {}
    for a, b in (("native_burn_ust", "trajectory_native_served_ust"), ("native_luna_minted", "supply_growth_luna"),
                 ("native_fee_luna", "final_fee_luna"), ("anchor_withdrawal_ust", "trajectory_withdraw_served_ust")):
        difference = totals[a] - totals[b]
        reference = float(cad.luna_supply.iloc[-1]) if a in ("native_luna_minted", "native_fee_luna") else abs(totals[b])
        tolerance = max(.1, reference * 1e-9)
        assert abs(difference) <= tolerance
        reconciliation[a] = {"ledger_minus_trajectory": difference, "reference": reference,
                             "tolerance": tolerance, "within_accounting_tolerance": True,
                             "exact": totals[a] == totals[b]}
    np.testing.assert_allclose(totals["native_luna_minted"], totals["native_luna_delivered"] + totals["native_fee_luna"], rtol=1e-11, atol=.001)
    phase = []
    for timestamp in ("2022-05-09T23:45:00Z", "2022-05-10T23:45:00Z", "2022-05-11T23:45:00Z", "2022-05-12T23:45:00Z", "2022-05-13T23:45:00Z", "2022-05-14T23:45:00Z", "2022-05-15T23:45:00Z"):
        time = pd.Timestamp(timestamp)
        phase.append({"time_utc": time.isoformat(), "sim_luna_price": float(fast.loc[time, "luna_price"]),
                      "observed_luna_price": float(targets.loc[time, "luna_price"]),
                      "sim_luna_supply": float(fast.loc[time, "luna_supply"]), "observed_luna_supply": float(targets.loc[time, "luna_supply"]),
                      "sim_ust_price": float(fast.loc[time, "ust_price"]), "observed_ust_price": float(targets.loc[time, "ust_price"])})
    phase_rmse = {}
    for name, mask in (("before_may11", fast.index < pd.Timestamp("2022-05-11T00:00:00Z")),
                       ("after_may11", fast.index >= pd.Timestamp("2022-05-11T00:00:00Z"))):
        phase_rmse[name] = {col: float(np.sqrt(np.mean((np.log10(fast.loc[mask, col].clip(lower=1e-12 if col == "luna_price" else 1)) -
                            np.log10(targets.loc[mask, col].clip(lower=1e-12 if col == "luna_price" else 1))) ** 2))) for col in ("luna_price", "luna_supply")}
    source_binding(plan["source_sha256"])
    payload = {"status": "qualified_saved_profile_audit_passed", "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "profile_id": PROFILE.name, "simulations_performed_by_audit": 0, "optimizer_calls_performed_by_audit": 0,
               "source_binding": before, "raw_input_hashes_verified": 12, "plan_budget_and_selection_verified": True,
               "terminal_status": status, "runtime_seconds": result["runtime_seconds"], "profile_pid_live": False,
               "other_live_fits_outside_audit_scope": True, "no_claim_that_all_current_jobs_are_terminal": True,
               "targets_identity": target_identity_result, "groups_identity": group_identity_result,
               "cases": case_audits, "best_name": best["name"], "corrected_baseline_loss": result["all_results"][0]["objective"]["loss"],
               "best_loss": best["objective"]["loss"], "best_metrics": best["metrics"], "best_parameters": best["parameters"],
               "fast_cadcad_trajectory_exact": True, "fast_cadcad_financial_exact_excluding_runner_and_runtime": True,
               "cadcad_ledger_file_sha256": sha(PROFILE / "best_ledger.parquet"), "cadcad_ledger_rows": len(ledger),
               "cadcad_ledger_reconciliation": {"totals": totals, "comparisons": reconciliation,
                   "qualification": "Ledger totals reconcile within declared physical accounting tolerances, not exact arithmetic equality. Native event recording suppresses events whose UST amount is at most 1e-9; per-minute omitted events are unavailable, so this audit does not attribute every residual to that filter."},
               "independent_fast_ledger_saved": False, "fast_cadcad_ledger_parity_verified": False,
               "ledger_parity_qualification": "All 17 primary fast profile calls used keep_ledger=False. Only the final cadCAD ledger was saved. Ledger reconciliation passes, but independent runner ledger parity cannot be established without an additional simulation, which this audit does not run.",
               "luna_phase_comparison": phase, "luna_phase_rmse": phase_rmse, "errors_in_primary_records": [],
               "audit_source_sha256": sha(HELPER), "qualification": "Predeclared full-event deterministic grid diagnostic with changed liquidity shape; failed historical fidelity, no independent holdout, stochastic validation, optimizer convergence, causal proof or automatic promotion."}
    (PROFILE / "audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({"audit_status": payload["status"], "simulations": 0, "cases": 17, "original_run_count": 18,
                      "baseline_loss": payload["corrected_baseline_loss"], "best_loss": payload["best_loss"],
                      "fast_cadcad_trajectory_exact": True, "fast_ledger_saved": False,
                      "ledger_reconciled": True, "phase": phase}, ensure_ascii=False))


if __name__ == "__main__":
    main()
