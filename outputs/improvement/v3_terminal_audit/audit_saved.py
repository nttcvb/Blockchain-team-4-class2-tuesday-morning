"""Read saved v3 artifacts; no simulation, optimizer, or public/run mutation."""
from pathlib import Path
from dataclasses import asdict, replace
from datetime import datetime, timezone
from collections import Counter
import ast
import ctypes
import hashlib
import inspect
import json
import math
import os
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FROZEN = ROOT / "baselines/v3_frozen_20261011T010500Z"
ATT = ROOT / "outputs/improvement/attention_fit/runs/20261011T003911455486Z"
PRO = ROOT / "outputs/improvement/protocol_capacity_review"
RAW = Path(r"D:\New folder\terra-luna-run-replication (1)\terra-luna-run-replication")
os.environ["LUNA_SOURCE_DIR"] = str(RAW)
sys.path.insert(0, str(FROZEN))
import numpy as np
import pandas as pd
from scipy.special import expit
from luna_sim import calibrate as C, metrics as M, data as D, engine as E
from luna_sim.config import ModelParams, ScenarioConfig
from luna_sim.reconstruction_validation import trajectory_checks


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_hashes(base, records):
    checks = {name: sha(base / name) == (value["sha256"] if isinstance(value, dict) else value)
              for name, value in records.items()}
    assert all(checks.values()), [name for name, passed in checks.items() if not passed]
    return {"files": len(checks), "all_match": True}


def exact(a, b):
    pd.testing.assert_frame_equal(a, b, check_exact=True, check_dtype=True)
    return {"exact": True, "rows": len(a), "columns": len(a.columns)}


def frame_identity(saved, rebuilt, expected):
    pd.testing.assert_frame_equal(saved, rebuilt, check_exact=True, check_dtype=True, check_freq=False)
    differences = []
    for col in saved:
        if saved[col].dtype == np.dtype("float64"):
            left, right = saved[col].to_numpy(), rebuilt[col].to_numpy()
            mismatch = left.view("uint64") != right.view("uint64")
            for i in np.flatnonzero(mismatch):
                assert np.isnan(left[i]) and np.isnan(right[i])
                differences.append({"column": str(col), "time": saved.index[i].isoformat(),
                                    "saved_nan_bits": hex(int(left.view("uint64")[i])),
                                    "rebuilt_nan_bits": hex(int(right.view("uint64")[i]))})
    canonical = saved.copy()
    canonical_rebuilt = rebuilt.copy()
    for frame in (canonical, canonical_rebuilt):
        for col in frame.select_dtypes(include="floating"):
            frame.loc[frame[col].isna(), col] = np.nan
    assert C._frame_hash(canonical) == C._frame_hash(canonical_rebuilt)
    assert C._frame_hash(rebuilt) == expected
    return {"expected_in_memory_frame_sha256": expected,
            "parquet_round_trip_frame_sha256": C._frame_hash(saved),
            "rebuilt_from_hashed_raw_frame_sha256": C._frame_hash(rebuilt),
            "direct_saved_hash_matches": C._frame_hash(saved) == expected,
            "exact_values_dtypes_index_and_missingness": True,
            "index_frequency_metadata": {"saved": str(saved.index.freq), "rebuilt": str(rebuilt.index.freq)},
            "canonical_missing_value_hash_matches": True,
            "canonical_missing_value_hash": C._frame_hash(canonical),
            "bitpattern_differences": differences,
            "qualification": "Legacy _frame_hash is sensitive to floating NaN bit patterns. Saved artifacts are not rewritten or retagged."}


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


def activity(trajectory, config, attention):
    ctx = E.context(config)  # Initial facts/population only; no state advance.
    a = ctx["agents"].copy()
    size = pd.read_parquet(RAW / "data/loss/depositor_prerun_size.parquet")
    wealth = a.address.map(size.drop_duplicates("address").set_index("address").prerun_usd).to_numpy()
    assert np.isfinite(wealth).all() and (wealth > 0).all()
    lag = np.maximum(1, np.ceil(a.lag_minutes.to_numpy() / config.dt_minutes).astype(int))
    seed = a.address.isin(ctx["wallets"]).to_numpy()
    p = config.params
    fixed = p.hazard_base + p.hazard_size * (a.log_size.to_numpy() - 3)
    history = np.empty((0, 5))
    prior_luna = ctx["facts"]["luna_price"]
    changed = binding = opportunities = 0
    maximum_difference = 0.
    window, memory = max(1, 60 // config.dt_minutes), max(40, 240 // config.dt_minutes)
    ceiling = attention["attention_cap_day"] * np.minimum(1., wealth / 100000.) ** attention["attention_wealth_elasticity"]
    for time, row in trajectory.iterrows():
        eta = fixed
        if len(history):
            positions = np.maximum(0, len(history) - lag)
            observed = history[positions, :4].copy()
            for j in (1, 2):
                observed[:, j] = np.convolve(history[:, j], np.ones(window), mode="full")[:len(history)][positions]
            discount, outflow, luna_fall, queue = observed.T
            eta = fixed + p.hazard_discount * discount + p.hazard_outflow * outflow + p.hazard_luna * luna_fall + p.hazard_queue * queue
        eligible = np.ones(len(a), dtype=bool)
        if pd.Timestamp("2022-05-07T00:00:00Z") <= time <= pd.Timestamp("2022-05-08T00:00:00Z"):
            eligible[seed] = False
        rate = np.minimum(96. * np.minimum(np.logaddexp(0., eta), 1.), ceiling)
        probability = -np.expm1(-rate * config.dt_minutes / 1440.)
        legacy = 1. - (1. - expit(eta)) ** (config.dt_minutes / 15)
        difference = np.abs(probability - legacy)
        opportunities += int(eligible.sum())
        changed += int(((difference > 1e-12) & eligible).sum())
        binding += int(((96. * np.logaddexp(0., eta) > ceiling + 1e-12) & eligible).sum())
        maximum_difference = max(maximum_difference, float(difference[eligible].max(initial=0.)))
        history = np.vstack([history, [max(0., 1. - row.ust_price), row.withdraw_served / max(ctx["facts"]["anchor_deposits"], 1.),
                                      max(0., math.log(max(prior_luna, 1e-12) / max(row.luna_price, 1e-12))),
                                      row.withdraw_queue / max(row.anchor_deposits, 1.), row.luna_price]])[-memory:]
        prior_luna = row.luna_price
    return {"potential_wallet_step_opportunities": opportunities, "changed_probability_opportunities": changed,
            "ceiling_binding_opportunities": binding, "maximum_absolute_probability_difference": maximum_difference,
            "wealth_dependent_ceilings_present": bool(np.ptp(ceiling) > 1e-12),
            "cap96_beta0_max_15min_probability": float(-np.expm1(-1.)),
            "qualification": "Probability reconstruction on archived signals only; no wallet balance exposure, changed request amounts, or causal loss attribution."}


def audit_attention():
    result, status, prov = read(ATT / "result.json"), read(ATT / "status.json"), read(ATT / "provenance.json")
    assert result["provenance"] == prov
    assert result["status"] == "complete_private_joint_fit_not_promoted" and status["status"] == "complete"
    records = [json.loads(line) for line in (ATT / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == result["evaluations"] == status["evaluations_including_controls_and_verification"] == 350
    assert result["hard_budget"] == status["hard_budget"] == prov["hard_evaluation_budget_including_every_full_event_simulation"] == 350
    assert [r["evaluation"] for r in records] == list(range(1, 351))
    assert not pid_live(status["process_id"])
    private = verify_hashes(ATT / "source", prov["private_source_sha256"])
    protected = {name if "/" in name else "luna_sim/" + name: value for name, value in prov["prepared_prototype"]["protected_source_sha256"].items()}
    frozen_sources = verify_hashes(FROZEN, protected)
    raw = verify_hashes(RAW / "data", prov["raw_input_sha256"])
    coupled_path = Path(prov["immutable_coupling_source"])
    coupling = verify_hashes(coupled_path, prov["coupling_provenance"]["private_source_sha256"])
    assert read(coupled_path.parent / "provenance.json") == prov["coupling_provenance"]
    archived_public = {}
    public_paths = {"config": "outputs/calibration/config_all.json", "report": "outputs/calibration/report_all.json",
                    "parameters": "outputs/calibration/parameters_full_fit.json"}
    for key, digest in prov["completed_public_artifact_sha256"].items():
        assert sha(ATT / ("completed_public_" + key + ".json")) == sha(FROZEN / public_paths[key]) == digest
        archived_public[key] = True
    # Archive preserves best_all, which is byte-identical to the launch checkpoint;
    # the launch checkpoint itself remains in the private run.
    assert sha(ATT / "warm_public_all_checkpoint.json") == sha(FROZEN / "outputs/calibration/best_all.json") == prov["warm_source_checkpoint_sha256"]
    base = ModelParams(**read(ATT / "completed_public_parameters.json"))
    search = prov["search"]
    base_dict = asdict(base)
    for record in records:
        point = np.asarray(record["normalized"])
        assert len(point) == 17 and np.isfinite(point).all() and ((point >= 0) & (point <= 1)).all()
        named = {name: float(lo + point[i] * (hi - lo)) for i, (name, lo, hi) in enumerate(search)}
        assert record["search_values"] == named
        values = dict(base_dict)
        for name, _, _ in search[:13]:
            field = C.LOG_PARAMETERS.get(name, name)
            original = math.log10(values[field]) if name in C.LOG_PARAMETERS else values[field]
            if abs(named[name] - original) > 1e-13:
                values[field] = 10. ** named[name] if name in C.LOG_PARAMETERS else named[name]
        assert record["parameters"] == values
        assert C.parameter_sha256(ModelParams(**values)) == record["parameter_sha256"]
        outside = 12e9 if abs(named["log_outside_max_ust"] - math.log10(12e9)) < 1e-13 else 10. ** named["log_outside_max_ust"]
        assert record["coupled_behavior"] == {"outside_max_ust": outside, "holder_exit_day": min(.01 * math.expm1(named["holder_exit_log1p_0p01"]), 2.)}
        assert record["attention"]["attention_cap_day"] == min(10. ** named["log_attention_cap_day"], 96.)
        assert record["attention"]["attention_wealth_elasticity"] == named["attention_wealth_elasticity"]
    target, group = pd.read_parquet(ATT / "targets.parquet"), pd.read_parquet(ATT / "groups.parquet")
    rebuilt, rebuilt_groups = D.load_targets().copy(), D.group_targets().reindex(target.index).copy()
    identities = {"target": frame_identity(target, rebuilt, prov["target_sha256"]),
                  "groups": frame_identity(group, rebuilt_groups, prov["group_sha256"])}
    # Saved scoring values are now used for recomputation, independent of current engine files.
    M.load_targets = lambda dt=15: target
    M.group_targets = lambda dt=15: group
    target.attrs["initial_deposits"] = float(target.anchor_deposits.iloc[0])
    fast, cad = pd.read_parquet(ATT / "final_fast.parquet"), pd.read_parquet(ATT / "final_cadcad.parquet")
    fast_ledger, cad_ledger = pd.read_parquet(ATT / "final_fast_ledger.parquet"), pd.read_parquet(ATT / "final_cadcad_ledger.parquet")
    parity = {"trajectory": exact(fast, cad), "ledger": exact(fast_ledger, cad_ledger)}
    warm, disabled = pd.read_parquet(ATT / "warm_public.parquet"), pd.read_parquet(ATT / "warm_disabled.parquet")
    exact(warm, disabled[warm.columns]); exact(warm, pd.read_parquet(FROZEN / "outputs/calibration/trajectory_all.parquet"))
    selected = result["best"]
    assert selected == records[selected["evaluation"] - 1]
    config = replace(ScenarioConfig.from_dict(prov["scenario"]), params=ModelParams(**selected["parameters"]))
    scoring = C.CalibrationObjective(config, target, group, base).components(fast)
    np.testing.assert_allclose(scoring["loss"], result["best_loss"], rtol=0, atol=1e-12)
    assert M.fit_metrics(fast) == result["final_fit"]
    assert result["fast_cadcad_exact"] is True
    assert np.isfinite(fast.select_dtypes(include="number").to_numpy()).all()
    checks = trajectory_checks(fast, config)
    assert checks["passes"]
    holders = fast_ledger.loc[fast_ledger.kind.eq("holder_luna_sale")]
    assert float(holders.amount.sum()) == float(fast.holder_luna_sold.iloc[-1]) == 0.
    assert float(fast.holder_usd_received.iloc[-1]) == 0.
    assert fast.external_ust.max() <= selected["coupled_behavior"]["outside_max_ust"] + 1e-4
    for name, value in result["conservation_error_max"].items():
        assert value == float(fast[name].abs().max())
    source = inspect.getsource(E.decisions)
    source = source.replace("    probability=1-(1-expit(eta))**(dt/15)",
                            "    probability=_attention_probability(eta, a.attention_raw_wealth_usd.to_numpy(), dt, _attention_mechanism)")
    assert source == (ATT / "source/effective_decisions.py").read_text(encoding="utf-8")
    controls = {name: read(ATT / (name + ".json"))["loss"] for name in ("warm_public", "warm_disabled", "cap96_beta0")}
    return {"terminal_status": status, "record_sequence_and_all_17_dimensions_verified": True,
            "source_binding": {"private": private, "frozen_public": frozen_sources, "coupling": coupling, "raw": raw,
                               "effective_decisions_reconstructed_exact": True, "completed_public_archives": archived_public},
            "scoring_input_identity": identities, "fast_cadcad_exact": parity,
            "warm_public_disabled_exact_and_matches_frozen_archive": True,
            "objective_recomputed": scoring["loss"], "final_fit_recomputed": result["final_fit"],
            "best_evaluation": selected["evaluation"], "best_attention": selected["attention"],
            "best_coupled_behavior": selected["coupled_behavior"],
            "changed_core_parameters": {name: {"warm": base_dict[name], "selected": value} for name, value in selected["parameters"].items() if value != base_dict[name]},
            "control_losses": controls, "evaluations_by_stage": dict(Counter(r["stage"] for r in records)),
            "errors": [{"evaluation": r["evaluation"], "error": r["error"]} for r in records if "error" in r],
            "final_accounting_and_owner_checks": checks, "holder_sales_zero": True,
            "outside_ust_max": float(fast.external_ust.max()), "activity": activity(fast, config, selected["attention"]),
            "original_audit_json_present": (ATT / "audit.json").exists(),
            "original_RUN_REVIEW_md_present": (ATT / "RUN_REVIEW.md").exists(),
            "qualification": "Terminal exploratory joint fit, not promoted. Only 2/6 full-event gates; no holdout, convergence or causal mechanism attribution. Separate original operator audit/report missing; this qualified audit does not retag the run."}


def audit_protocol():
    status, results, bindings = read(PRO / "status.json"), read(PRO / "results.json"), read(PRO / "source_ast_binding.json")
    records = results["probes"]
    assert status["status"] == "complete" and status["active_run"] is None
    assert status["attempted"] == len(records) == len(status["completed"]) == 9
    assert len(results["cadcad_verifications"]) == 0 and status["hard_budget"] == 11
    before = read(PRO / "provenance_before.json")
    assert before == read(PRO / "provenance_after.json")
    preserved = {name: digest for name, digest in before["protected"].items() if (FROZEN / name).is_file()}
    frozen = verify_hashes(FROZEN, preserved)
    frozen["launch_protected_paths_not_in_completed_public_archive"] = [name for name in before["protected"] if name not in preserved]
    frozen["qualification"] = "Archive intentionally preserves completed public deliverables; omitted transient/checkpoint/diagnostic paths are not falsely marked verified. Checkpoint identity is independently bound to byte-identical archived best files and the private run checkpoint."
    raw = verify_hashes(RAW / "data", before["raw_inputs"])
    tree = ast.parse((PRO / "source/engine.py").read_text(encoding="utf-8"))
    originals = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    outer = [ast.dump(n, include_attributes=False) for n in tree.body if not isinstance(n, ast.FunctionDef)]
    for name, binding in bindings.items():
        path = PRO / "source" / ("engine_" + name + ".py")
        assert sha(path) == binding["source_sha256"]
        variant = ast.parse(path.read_text(encoding="utf-8"))
        nodes = {n.name: n for n in variant.body if isinstance(n, ast.FunctionDef)}
        assert set(originals) == set(nodes)
        assert outer == [ast.dump(n, include_attributes=False) for n in variant.body if not isinstance(n, ast.FunctionDef)]
        for function in originals:
            dump = ast.dump(nodes[function], include_attributes=False)
            if function in ("observation", "_market_minute"):
                assert hashlib.sha256(dump.encode()).hexdigest() == binding["effective_function_ast_sha256"][function]
            else:
                assert dump == ast.dump(originals[function], include_attributes=False)
    verified = []
    for record in records:
        path = PRO / "runs" / record["run_id"]
        assert read(path / "result.json") == record
        assert sha(path / "config.json") == record["config_sha256"]
        assert sha(PRO / "source" / ("engine_" + record["variant"] + ".py")) == record["source_sha256"]
        trajectory, ledger = pd.read_parquet(path / "trajectory.parquet"), pd.read_parquet(path / "ledger.parquet")
        assert C._frame_hash(trajectory) == record["trajectory_frame_sha256"]
        assert C._frame_hash(ledger) == record["ledger_frame_sha256"]
        cfg = ScenarioConfig.from_dict(read(path / "config.json"))
        assert trajectory_checks(trajectory, cfg) == record["checks"]
        for split, api in (("all", "all"), ("train", "train"), ("holdout", "validation")):
            target = M.load_targets()
            target = target.copy() if split == "all" else target.loc[target.index < C.TRAIN_END if split == "train" else target.index >= C.TRAIN_END].copy()
            target.attrs["initial_deposits"] = float(M.load_targets().anchor_deposits.iloc[0])
            groups = M.group_targets().reindex(target.index)
            loss = C.CalibrationObjective(cfg, target, groups, cfg.params).components(trajectory)["loss"]
            np.testing.assert_allclose(loss, record["splits"][split]["objective"]["loss"], rtol=0, atol=1e-10)
            metrics = M.fit_metrics(trajectory, cfg.dt_minutes, api)
            for key, value in metrics.items():
                assert value == record["splits"][split]["metrics"][key]
        if record["variant"] == "core":
            exact(trajectory, pd.read_parquet(FROZEN / "outputs/calibration" / ("trajectory_" + record["parameters"] + ".parquet")))
            archived = pd.read_csv(FROZEN / "outputs/calibration" / ("ledger_" + record["parameters"] + ".csv"), float_precision="round_trip", low_memory=False)
            archived["time"] = pd.to_datetime(archived.time, utc=True)
            exact(ledger, archived)
        verified.append({"run_id": record["run_id"], "all_loss": record["splits"]["all"]["objective"]["loss"],
                         "holdout_loss": record["splits"]["holdout"]["objective"]["loss"],
                         "all_gates": sum(record["splits"]["all"]["metrics"]["gates"].values()), "artifact_identity_and_metrics_verified": True})
    evidence = read(PRO / "governance_evidence_binding.json")
    verify_hashes(ROOT / "outputs/improvement/governance_1164_evidence", evidence["files_sha256"])
    for metadata in (PRO / "primary_sources").glob("*.fetch.json"):
        fetch = read(metadata)
        filename = fetch.get("file") or ("classic-core-v0.5.19-go.mod" if "0.5.19" in metadata.name else None)
        if filename:
            assert sha(PRO / "primary_sources" / filename) == fetch["sha256"]
    assert sha(PRO / "primary_sources/classic-core-v0.5.20-go.mod") == read(PRO / "primary_sources/go_mod_fetch.json")["sha256"]
    return {"terminal_status": status, "frozen_archive_binding": frozen, "raw_binding": raw,
            "effective_source_AST_verified": True, "probes": verified,
            "postprocessing_audit_present": (PRO / "postprocessing_audit.json").exists(),
            "protocol_capacity_review_VI_present": (ROOT / "outputs/improvement/PROTOCOL_CAPACITY_REVIEW_VI.md").exists(),
            "cadcad_verifications": 0, "governance_binding": evidence,
            "source_priority_conclusion": "Proposal 1164 enters execution through the expired active voting queue; its voting end is May 18, outside this May 6–15 event. It cannot support the model's May 11 automatic pool4/arb4 step. Removing the unverified step worsens the frozen fit; that is a fidelity/retuning problem, not historical evidence for retaining the step.",
            "qualification": "Nine saved counterfactual probes, not promoted. May11 proposal variants are deliberately early activation; provider record plus tagged source is not a signed historical state proof and does not exclude manual emergency changes."}


def main():
    manifest = read(FROZEN / "ARCHIVE_MANIFEST.json")
    frozen_check = verify_hashes(FROZEN, manifest["files"])
    attention = audit_attention()
    protocol = audit_protocol()
    terminal = {}
    for split in ("train", "all"):
        status = read(FROZEN / "outputs/calibration" / ("calibration_status_" + split + ".json"))
        assert status["status"] == "complete" and not pid_live(status["process_id"])
        terminal[split] = {"status": "complete", "calls": status["calls"], "pid": status["process_id"], "pid_live": False}
    coupled_status = read(ROOT / "outputs/improvement/coupled_market_fit/runs/20261010T143122127042Z/status.json")
    assert coupled_status["status"] == "complete" and not pid_live(coupled_status["process_id"])
    terminal["coupled_private"] = {"status": "complete", "evaluations": coupled_status["evaluations"], "pid": coupled_status["process_id"], "pid_live": False}
    terminal["attention_private"] = {"status": "complete", "evaluations": 350, "pid": attention["terminal_status"]["process_id"], "pid_live": False}
    payload = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "status": "qualified_saved_artifact_checks_passed",
               "binding": str(FROZEN), "frozen_archive_manifest_verified": frozen_check,
               "current_engine_identity_claimed": False, "simulations_performed": 0, "optimizer_calls_performed": 0,
               "terminal_jobs": terminal, "attention": attention, "protocol_capacity": protocol,
               "missing_original_reports_are_not_marked_passed": True,
               "audit_source_sha256": sha(__file__)}
    (OUT / "audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "simulations": 0, "attention_evaluations": 350,
                      "attention_loss": attention["objective_recomputed"], "target_nan_bit_differences": len(attention["scoring_input_identity"]["target"]["bitpattern_differences"]),
                      "protocol_probes": len(protocol["probes"]), "all_recorded_pids_terminal": True}))


if __name__ == "__main__":
    main()
