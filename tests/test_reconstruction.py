"""Historical reporting: file identity, audit boundaries, and observed-data gaps."""
from dataclasses import asdict
import json
import re

import numpy as np
import pandas as pd
import pytest

from luna_sim import calibrate, config, metrics, reconstruction


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch):
    original = config.ROOT
    for relative in ("luna_sim/calibrate.py", "luna_sim/engine.py", "luna_sim/config.py",
            "luna_sim/data.py", "luna_sim/metrics.py", "luna_sim/audit.py",
            "luna_sim/reconstruction.py", "data/sources.json",
            "luna_sim/reconstruction_validation.py",
            "data/external/btc_usdt_minute.parquet", "data/external/btc_metadata.json"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((original / relative).read_bytes())
    monkeypatch.setattr(reconstruction, "ROOT", tmp_path)
    monkeypatch.setattr(calibrate, "ROOT", tmp_path)
    monkeypatch.setattr(reconstruction, "DEFAULT_SOURCE", tmp_path / "raw")
    index = pd.date_range("2022-05-10T21:30:00Z", periods=12, freq="15min")
    target = pd.DataFrame({"ust_price": [1.] * 4 + [.90] * 8,
        "luna_price": np.linspace(20, 1, 12), "luna_supply": np.linspace(1e9, 2e9, 12),
        "anchor_deposits": np.linspace(8e9, 2e9, 12),
        "native_ust": [1e8] * 12, "native_fee": [.01] * 12}, index=index)
    groups = pd.DataFrame({i: np.linspace(1, .3, 12) for i in range(6)}, index=index)
    groups.iloc[-3:, :] = np.nan
    groups.attrs["observation_coverage"] = {"raw_end_utc": index[-4].isoformat()}

    def load_target(dt=15):
        assert dt == 15
        return target.copy()

    def load_groups(dt=15):
        assert dt == 15
        return groups.copy()

    load_target.cache_clear = load_groups.cache_clear = lambda: None
    for module in (reconstruction, metrics):
        monkeypatch.setattr(module, "load_targets", load_target)
        monkeypatch.setattr(module, "group_targets", load_groups)
    full = target.drop(columns=["native_ust"]).assign(native_served=target.native_ust)
    train = full.copy()
    # Temporal holdout really is worse, rather than copying a status flag.
    train.loc[train.index >= calibrate.TRAIN_END, "luna_price"] = 1e-8
    for i in range(6):
        full[f"group_{i}_remaining"] = np.linspace(1, .3, 12)
        train[f"group_{i}_remaining"] = np.linspace(1, .3, 12)
    folder = tmp_path / "outputs" / "calibration"
    folder.mkdir(parents=True)
    for split, frame in (("train", train), ("all", full)):
        parameter_name = "parameters.json" if split == "train" else "parameters_full_fit.json"
        write_json(folder / parameter_name, asdict(config.ModelParams()))
        cfg = config.ScenarioConfig(mode="historical", stochastic=False, funding_timing="early")
        write_json(folder / f"config_{split}.json", cfg.to_dict())
        report = {"optimizer": {"run_id": f"run_{split}"}, "objective": 1., "calls": 20,
            **{name: metrics.fit_metrics(frame, split=name) for name in ("train", "validation", "all")},
            "financial_metrics": {"max_accounting_errors": dict.fromkeys(
                ["ust_error", "luna_error", "usd_error", "claim_error"], .0001)}}
        status = {"status": "complete", "run_id": f"run_{split}"}
        write_json(folder / f"report_{split}.json", report)
        write_json(folder / f"calibration_status_{split}.json", status)
        frame.to_parquet(folder / f"trajectory_{split}.parquet")
        archive = folder / "runs" / f"run_{split}"
        write_json(archive / "report.json", report)
        write_json(archive / "execution.json", status)
        frame.to_parquet(archive / "trajectory.parquet")

    audited = []

    def audit_stub(split, current_sources):
        # Simulator/audit correctness has separate integration tests. Here the
        # authority boundary is explicit; chart/report code must invoke it.
        audited.append(split)
        assert current_sources == calibrate._source_hashes()
        return {"run_id": f"run_{split}", "rows": len(index), "fit_rows": 10,
            "report_metrics_recomputed": True, "financial_metrics_recomputed": True,
            "published_trajectory_matches_run_archive": True}

    monkeypatch.setattr(reconstruction, "audit_calibration", audit_stub)
    return {"root": tmp_path, "target": target, "groups": groups, "full": full,
            "train": train, "audited": audited}


def test_report_builds_without_experiments_and_distinguishes_holdout(project):
    result = reconstruction.build_reconstruction_report()
    assert project["audited"] == ["train", "all"]
    assert not (project["root"] / "outputs" / "experiments").exists()
    assert result["fidelity"] == {"full_fit_passes_all": True, "parameter_holdout_passes_all": False}
    assert reconstruction.reconstruction_artifact_current()
    folder = project["root"] / "outputs" / "reconstruction"
    written = (folder / "RECONSTRUCTION_VI.md").read_text(encoding="utf-8")
    html = (folder / "reconstruction.html").read_text(encoding="utf-8")
    assert "Giữ tham số, từ 11/5" in written and "6/6 ngưỡng" in written
    # Both the inaccurate late LUNA price and completely unobserved late
    # cohorts prevent a falsely passing temporal holdout.
    assert "4/6 ngưỡng" in written and "tái hiện trong mẫu" in written
    assert "không kéo dài đường dữ liệu thật" in written
    assert "Native swap" in html and "Giữ tham số, từ 11/5" in html
    assert not re.search(r"<script\b[^>]*\bsrc=", html, re.IGNORECASE)


def test_observed_group_lines_preserve_missing_data(project):
    core, native, groups = reconstruction._comparison_figures(
        project["target"], project["groups"], project["full"], project["train"])
    assert core.layout.yaxis2.type == "log" and core.layout.yaxis4.type == "log"
    assert core.data[2].name == "Tham số trước 11/5"
    assert len(native.data) == 3
    for i in range(6):
        observed = groups.data[i * 3]
        assert observed.name == "Quan sát" and observed.connectgaps is False
        assert np.isnan(np.asarray(observed.y, dtype=float)[-3:]).all()
        assert np.isfinite(np.asarray(observed.y, dtype=float)[:-3]).all()


def stability_stub(project):
    scores = metrics.fit_metrics(project['full'])
    runs = pd.DataFrame([{key: 2*limit for key, _, limit in reconstruction.GATE_SPECS}]*2)
    manifest = {'seed_count':2, 'seed_runs_passing_all_gates':0,
                'gate_pass_counts':{key:0 for key, _, _ in reconstruction.GATE_SPECS},
                'qualification':'Biến thiên seed không phải bất định cấu trúc.'}
    timestep = {'15min_fit':scores, '5min_fit':scores,
        'ust_mae_between_steps':.02, 'deposit_nrmse_between_steps':.27,
        'luna_price_log_rmse_between_steps':1.07, 'luna_supply_log_rmse_between_steps':.39}
    bands = pd.concat([
        project['target'][['ust_price','luna_price','anchor_deposits','luna_supply']]
        .rename_axis('time').reset_index().assign(quantile=q)
        for q in ('p05','median','p95')], ignore_index=True)
    return {'manifest':manifest, 'timestep':timestep, 'runs':runs, 'bands':bands}


def test_unverified_seed_outputs_are_not_reported_as_stability(project, monkeypatch):
    folder=project['root']/'outputs'/'reconstruction'/'validation'
    write_json(folder/'manifest.json', {'status':'running','seed_count':20})
    from luna_sim import reconstruction_validation
    monkeypatch.setattr(reconstruction_validation,'reconstruction_checks_current',lambda:False)
    assert reconstruction._historical_checks() is None
    reconstruction.build_reconstruction_report()
    written=(folder.parent/'RECONSTRUCTION_VI.md').read_text(encoding='utf-8')
    assert 'Chưa có bộ kiểm tra cadCAD nhiều seed' in written
    assert '0/20 lượt ngẫu nhiên' not in written


def test_verified_seed_failures_and_cadence_errors_are_published(project, monkeypatch):
    stability=stability_stub(project)
    folder=project['root']/'outputs'/'reconstruction'/'validation'
    write_json(folder/'manifest.json',stability['manifest'])
    write_json(folder/'timestep_check.json',stability['timestep'])
    stability['runs'].to_csv(folder/'runs.csv',index=False)
    stability['bands'].to_parquet(folder/'bands.parquet',index=False)
    monkeypatch.setattr(reconstruction,'_historical_checks',lambda:stability)
    result=reconstruction.build_reconstruction_report()
    written=(folder.parent/'RECONSTRUCTION_VI.md').read_text(encoding='utf-8')
    assert '0/2 lượt ngẫu nhiên đạt đủ sáu ngưỡng' in written
    assert '0.2700' in written and '1.0700' in written
    assert result['fidelity']['seed_runs_passing_all_gates']==0
    assert reconstruction.reconstruction_artifact_current()
    with (folder/'runs.csv').open('ab') as handle: handle.write(b' ')
    assert not reconstruction.reconstruction_artifact_current()


def test_seed_band_plot_uses_each_observation_and_each_quantile(project):
    figure=reconstruction._stability_figure(project['target'],stability_stub(project)['bands'])
    assert len(figure.data)==16
    assert figure.layout.yaxis2.type=='log' and figure.layout.yaxis4.type=='log'
    for i in range(4):
        assert [trace.name for trace in figure.data[i*4:(i+1)*4]]==['Quan sát','p95','p05','median']
        assert figure.data[i*4+2].fill=='tonexty'


@pytest.mark.parametrize("failed_split", ["train", "all"])
def test_rejected_audit_prevents_publication(project, monkeypatch, failed_split):
    normal = reconstruction.audit_calibration

    def fail(split, current_sources):
        if split == failed_split:
            raise AssertionError(f"{split}: stale or unfinished calibration")
        return normal(split, current_sources)

    monkeypatch.setattr(reconstruction, "audit_calibration", fail)
    with pytest.raises(AssertionError, match="stale or unfinished"):
        reconstruction.build_reconstruction_report()
    assert not (project["root"] / "outputs" / "reconstruction").exists()


@pytest.mark.parametrize("change", ["source", "parameter", "trajectory", "report", "archive",
                                    "target", "group", "artifact", "status"])
def test_guard_rejects_current_state_or_artifact_changes(project, change):
    reconstruction.build_reconstruction_report()
    assert reconstruction.reconstruction_artifact_current()
    root = project["root"]
    folder = root / "outputs" / "calibration"
    paths = {"source": root / "luna_sim" / "engine.py",
        "parameter": folder / "parameters_full_fit.json", "trajectory": folder / "trajectory_all.parquet",
        "report": folder / "report_all.json", "archive": folder / "runs" / "run_all" / "execution.json",
        "artifact": root / "outputs" / "reconstruction" / "reconstruction.html"}
    if change in paths:
        with paths[change].open("ab") as handle:
            handle.write(b" ")
    elif change == "target":
        project["target"].iloc[0, 0] += .02
    elif change == "group":
        project["groups"].iloc[0, 0] = .5
    else:
        write_json(folder / "calibration_status_all.json", {"status": "running", "run_id": "run_all"})
    assert not reconstruction.reconstruction_artifact_current()


@pytest.mark.parametrize("change", ["missing_artifact", "missing_audit", "unverified_audit", "invalid_json", "wrong_json_shape"])
def test_guard_needs_complete_independent_identity(project, change):
    reconstruction.build_reconstruction_report()
    folder = project["root"] / "outputs" / "reconstruction"
    path = folder / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if change == "missing_artifact":
        payload["artifacts_sha256"].pop("RECONSTRUCTION_VI.md")
    elif change == "missing_audit":
        payload["calibration_checks"].pop("all")
    elif change == "unverified_audit":
        payload["calibration_checks"]["all"]["published_trajectory_matches_run_archive"] = False
    elif change == "wrong_json_shape":
        payload = []
    else:
        path.write_text("{not json", encoding="utf-8")
        assert not reconstruction.reconstruction_artifact_current()
        return
    write_json(path, payload)
    assert not reconstruction.reconstruction_artifact_current()


def test_input_change_during_render_prevents_publication(project, monkeypatch):
    normal = reconstruction._comparison_figures

    def changed(*args):
        figures = normal(*args)
        path = project["root"] / "luna_sim" / "engine.py"
        path.write_bytes(path.read_bytes() + b"\n# changed during report\n")
        return figures

    monkeypatch.setattr(reconstruction, "_comparison_figures", changed)
    with pytest.raises(ValueError, match="đã thay đổi"):
        reconstruction.build_reconstruction_report()
    assert not (project["root"] / "outputs" / "reconstruction").exists()


@pytest.mark.parametrize("change", ["source", "status"])
def test_change_between_audit_and_report_snapshot_prevents_publication(project, monkeypatch, change):
    normal = reconstruction.audit_calibration

    def changed(split, current_sources):
        check = normal(split, current_sources)
        if split == "all":
            if change == "source":
                path = project["root"] / "luna_sim" / "engine.py"
                path.write_bytes(path.read_bytes() + b"\n# restarted model\n")
            else:
                write_json(project["root"] / "outputs" / "calibration" / "calibration_status_all.json",
                           {"status": "running", "run_id": "run_all"})
        return check

    monkeypatch.setattr(reconstruction, "audit_calibration", changed)
    with pytest.raises(ValueError, match="sau khi kiểm toán|sau kiểm toán"):
        reconstruction.build_reconstruction_report()
    assert not (project["root"] / "outputs" / "reconstruction").exists()
