"""cadCAD seed and time-resolution checks for historical reconstruction only."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .audit import audit_calibration
from .calibrate import _frame_hash, _source_hashes
from .config import ROOT, ScenarioConfig
from .data import group_targets, load_targets
from .engine import simulate
from .metrics import fit_metrics


SCHEMA_VERSION = 1
MACRO_COLUMNS = ("ust_price", "luna_price", "luna_supply", "anchor_deposits")
OWNED_COLUMNS = ("anchor_cash", "anchor_reserve", "market_usd", "market_ust",
    "market_luna", "outside_luna", "external_cash", "external_ust", "fee_luna",
    "arbitrage_cash_usd", "arbitrage_luna", "rescuer_ust", "rescuer_luna", "fees_usd")
ERROR_COLUMNS = ("ust_error", "luna_error", "usd_error", "claim_error")
QUALIFICATION = (
    "Các dải p05/trung vị/p95 phản ánh biến thiên giữa seed của tác nhân trong cùng mô hình "
    "và bộ tham số đã khớp toàn sự kiện. Chúng không phải khoảng tin cậy về bất định cấu trúc. "
    "Đối chiếu lịch sử với bộ tham số này là kiểm tra trong mẫu; không thay thế kiểm định giữ "
    "tham số theo thời gian. Không có kịch bản chính sách trong bộ kiểm tra này."
)


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _seed_count(seeds):
    if not isinstance(seeds, int) or isinstance(seeds, bool) or seeds < 1:
        raise ValueError("seeds phải là số nguyên dương")
    return seeds


def reconstruction_validation_provenance():
    """Read current source, completed-fit input, archive, and observation identities."""
    load_targets.cache_clear()
    group_targets.cache_clear()
    sources = _source_hashes()
    sources.update({name: _sha(ROOT / "luna_sim" / name)
                    for name in ("audit.py", "reconstruction_validation.py")})
    paths = []
    folder = ROOT / "outputs" / "calibration"
    for split, parameter_name in (("train", "parameters.json"), ("all", "parameters_full_fit.json")):
        paths.extend(folder / name for name in (f"report_{split}.json", f"calibration_status_{split}.json",
            f"config_{split}.json", f"trajectory_{split}.parquet", parameter_name))
        run_id = _read_json(folder / f"report_{split}.json").get("optimizer", {}).get("run_id")
        if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError(f"{split}: định danh lần hiệu chỉnh không hợp lệ")
        paths.extend(folder / "runs" / run_id / name
                     for name in ("report.json", "execution.json", "trajectory.parquet"))
    return {"source_sha256": sources,
        "target_sha256": {f"{dt}min": _frame_hash(load_targets(dt)) for dt in (15, 5)},
        "group_sha256": {f"{dt}min": _frame_hash(group_targets(dt)) for dt in (15, 5)},
        "inputs_sha256": {path.relative_to(ROOT).as_posix(): _sha(path) for path in paths}}


def _artifact_names(seeds):
    names = {"runs.csv", "bands.parquet", "timestep_check.json"}
    for seed in range(42, 42 + seeds):
        names.update(f"seed{seed}/{name}" for name in ("config.json", "metrics.json", "trajectory.parquet"))
    names.add("seed42/ledger.csv")
    names.update(f"deterministic_5min/{name}" for name in ("config.json", "metrics.json", "trajectory.parquet"))
    return names


def reconstruction_checks_current():
    """Reject incomplete, changed, or tampered historical validation artifacts."""
    directory = ROOT / "outputs" / "reconstruction" / "validation"
    try:
        manifest = _read_json(directory / "manifest.json")
        seeds = _seed_count(manifest.get("seed_count"))
        expected_seeds = list(range(42, 42 + seeds))
        if (manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "complete"
                or manifest.get("engine") != "cadcad" or manifest.get("seeds") != expected_seeds
                or manifest.get("completed_seeds") != expected_seeds):
            return False
        if manifest.get("physical_checks_pass") is not True:
            return False
        checks = manifest.get("calibration_checks", {})
        if set(checks) != {"train", "all"}:
            return False
        for split in ("train", "all"):
            status = _read_json(ROOT / "outputs" / "calibration" / f"calibration_status_{split}.json")
            if status.get("status") != "complete" or status.get("run_id") != checks[split].get("run_id"):
                return False
            if not all(checks[split].get(key) is True for key in (
                    "report_metrics_recomputed", "financial_metrics_recomputed",
                    "published_trajectory_matches_run_archive")):
                return False
        if manifest.get("provenance") != reconstruction_validation_provenance():
            return False
        hashes = manifest.get("artifacts_sha256", {})
        if set(hashes) != _artifact_names(seeds):
            return False
        return all(_sha(directory / name) == digest for name, digest in hashes.items())
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def trajectory_checks(trajectory, config):
    """Check exported inventories and accounting residuals without masking failures."""
    required = set(MACRO_COLUMNS + OWNED_COLUMNS + ERROR_COLUMNS + ("ust_supply", "tfl_added"))
    missing = required.difference(trajectory.columns)
    if missing:
        raise ValueError(f"Quỹ đạo thiếu các cột kiểm tra: {', '.join(sorted(missing))}")
    if not isinstance(trajectory.index, pd.DatetimeIndex) or str(trajectory.index.tz) != "UTC":
        raise ValueError("Quỹ đạo phải có chỉ mục thời gian UTC")
    if trajectory.empty or not trajectory.index.is_unique or not trajectory.index.is_monotonic_increasing:
        raise ValueError("Quỹ đạo phải có thời gian duy nhất, tăng dần và không rỗng")
    expected = load_targets(config.dt_minutes).loc[pd.Timestamp(config.start):].index
    expected = expected[expected < pd.Timestamp(config.end)]
    if not trajectory.index.equals(expected):
        raise ValueError("Quỹ đạo không bao phủ đúng cửa sổ lịch sử và bước thời gian")
    numeric = trajectory.select_dtypes(include="number")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Quỹ đạo chứa số không hữu hạn")
    if not all(pd.api.types.is_numeric_dtype(trajectory[col]) for col in required):
        raise ValueError("Cột tài sản hoặc sai số phải là số")
    minima = {name: float(trajectory[name].min()) for name in OWNED_COLUMNS}
    negative = [name for name, minimum in minima.items() if minimum < -.001]
    if negative:
        raise ValueError(f"Tồn kho có chủ sở hữu âm: {', '.join(negative)}")
    if (trajectory[["ust_price", "luna_price", "ust_supply", "luna_supply"]] <= 0).any().any():
        raise ValueError("Giá và tổng cung phải dương để kiểm tra trên thang log")
    if trajectory.anchor_deposits.min() < -.001:
        raise ValueError("Quyền đòi Anchor âm")
    limits = _read_json(ROOT / "data" / "sources.json")["historical_resource_limits"]
    initial_usd = (config.params.market_cash_usd + config.params.arb_capital_usd + 1e9
                   + limits["lfg_usdt"] + limits["lfg_usdc"])
    usd_reference = initial_usd + trajectory.tfl_added
    if "btc_cash_created" in trajectory:
        usd_reference = usd_reference + trajectory.btc_cash_created
        usd_basis = "USD ban đầu + đóng góp TFL + USD từ bán BTC được ghi trong quỹ đạo"
    else:
        usd_basis = ("USD ban đầu + đóng góp TFL; không cộng USD từ bán BTC chưa được xuất trong quỹ đạo, "
                     "nên mẫu số này là cận dưới thận trọng của tổng USD")
    reference = {"ust_error": trajectory.ust_supply.clip(lower=1),
                 "luna_error": trajectory.luna_supply.clip(lower=1),
                 "usd_error": usd_reference.clip(lower=1),
                 "claim_error": trajectory.anchor_deposits.clip(lower=1)}
    absolute = {name: float(trajectory[name].abs().max()) for name in ERROR_COLUMNS}
    relative = {name: float((trajectory[name].abs() / reference[name]).max()) for name in ERROR_COLUMNS}
    for name in ERROR_COLUMNS:
        allowed = np.maximum(.1, reference[name] * 1e-9)
        if (trajectory[name].abs() > allowed).any():
            raise ValueError(f"Sai lệch sổ cái vượt dung sai: {name}")
    return {"passes": True, "recorded_owned_stock_minima": minima,
        "maximum_absolute_accounting_errors": absolute, "maximum_relative_accounting_errors": relative,
        "accounting_reference_basis": {"ust_error": "Tổng cung UST", "luna_error": "Tổng cung LUNA",
            "usd_error": usd_basis, "claim_error": "Quyền đòi Anchor hiện tại, tối thiểu 1 UST"},
        "absolute_tolerance": .1, "relative_tolerance": 1e-9,
        "qualification": "Đối chiếu các tồn kho đã xuất; engine kiểm tra thêm sổ cái tác nhân và quỹ trong từng bước."}


def resolution_comparison(trajectory_15min, trajectory_5min, initial_anchor_deposits):
    """Compare identical timestamps, with no interpolation or floor that hides zeros."""
    if not np.isfinite(initial_anchor_deposits) or initial_anchor_deposits <= 0:
        raise ValueError("Mẫu số Anchor ban đầu phải hữu hạn và dương")
    for frame in (trajectory_15min, trajectory_5min):
        if not isinstance(frame.index, pd.DatetimeIndex) or str(frame.index.tz) != "UTC":
            raise ValueError("Thời gian đối chiếu phải là UTC")
        if frame.empty or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
            raise ValueError("Quỹ đạo so sánh phải có chỉ mục duy nhất, tăng dần")
        if not np.isfinite(frame[list(MACRO_COLUMNS)].to_numpy(dtype=float)).all():
            raise ValueError("Quỹ đạo so sánh chứa giá trị không hữu hạn")
        if (frame[["luna_price", "luna_supply"]] <= 0).any().any():
            raise ValueError("Giá và cung LUNA phải dương khi so sánh log")
    if not trajectory_15min.index.isin(trajectory_5min.index).all():
        raise ValueError("Quỹ đạo 5 phút thiếu thời điểm đối chiếu 15 phút")
    aligned = trajectory_5min.reindex(trajectory_15min.index)
    return {"comparison_rows": len(trajectory_15min),
        "ust_mae_between_steps": float(abs(aligned.ust_price - trajectory_15min.ust_price).mean()),
        "deposit_nrmse_between_steps": float(np.sqrt(np.mean(
            (aligned.anchor_deposits - trajectory_15min.anchor_deposits) ** 2)) / initial_anchor_deposits),
        "luna_price_log_rmse_between_steps": float(np.sqrt(np.mean((np.log10(aligned.luna_price)
            - np.log10(trajectory_15min.luna_price)) ** 2))),
        "luna_supply_log_rmse_between_steps": float(np.sqrt(np.mean((np.log10(aligned.luna_supply)
            - np.log10(trajectory_15min.luna_supply)) ** 2))),
        "initial_anchor_deposits_for_normalization": float(initial_anchor_deposits),
        "alignment": "Chỉ so sánh cùng thời điểm UTC; không nội suy và không tự điền dữ liệu thiếu."}


def _canonical_config():
    config = ScenarioConfig.from_dict(_read_json(ROOT / "outputs" / "calibration" / "config_all.json"))
    if (config.mode != "historical" or config.funding_timing != "early" or config.dt_minutes != 15
            or config.stochastic or config.stress_days != 0 or config.policies):
        raise ValueError("Cấu hình full-fit phải là lịch sử xác định 15 phút, quỹ sớm, không có đuôi hoặc chính sách")
    return config


def _run(config, directory, provenance, keep_ledger):
    trajectory, execution, ledger = simulate(config, engine="cadcad", keep_ledger=keep_ledger)
    if (execution.get("engine") != "cadcad"
            or execution.get("engine_source_sha256") != provenance["source_sha256"]["engine.py"]):
        raise ValueError("Lần chạy không xác nhận cadCAD và đúng nguồn engine")
    physical = trajectory_checks(trajectory, config)
    fit = fit_metrics(trajectory, dt=config.dt_minutes, split="all")
    if len(fit.get("gates", {})) != 6:
        raise ValueError("Kết quả thiếu sáu ngưỡng độ khớp")
    metrics = {"seed": config.seed, "engine": "cadcad",
        "engine_source_sha256": execution["engine_source_sha256"],
        "runtime_seconds": execution.get("runtime_seconds"), "fit": fit,
        "physical_checks": physical, "qualification": QUALIFICATION}
    directory.mkdir(parents=True, exist_ok=True)
    config.save(directory / "config.json")
    trajectory.to_parquet(directory / "trajectory.parquet")
    _write_json(directory / "metrics.json", metrics)
    if keep_ledger:
        if (not isinstance(ledger, pd.DataFrame) or ledger.empty
                or not {"time", "kind", "owner", "amount", "asset"}.issubset(ledger.columns)):
            raise ValueError("Sổ sự kiện seed 42 phải là bảng không rỗng với đủ cột giao dịch")
        ledger_time = pd.to_datetime(ledger.time, errors="coerce", utc=True)
        ledger_amount = pd.to_numeric(ledger.amount, errors="coerce")
        if (ledger_time.isna().any() or not np.isfinite(ledger_amount.to_numpy(dtype=float)).all()
                or (ledger_time < pd.Timestamp(config.start)).any()
                or (ledger_time >= pd.Timestamp(config.end)).any()):
            raise ValueError("Sổ sự kiện seed 42 có thời gian hoặc lượng giao dịch không hợp lệ")
        ledger.to_csv(directory / "ledger.csv", index=False)
    return trajectory, metrics


def run_reconstruction_checks(seeds=20):
    """Run historical stochastic seeds and one deterministic 5-minute cadCAD path."""
    seeds = _seed_count(seeds)
    sources = _source_hashes()
    checks = {split: audit_calibration(split, sources) for split in ("train", "all")}
    provenance = reconstruction_validation_provenance()
    if any(provenance["source_sha256"].get(name) != digest for name, digest in sources.items()):
        raise ValueError("Nguồn đã thay đổi sau kiểm toán hiệu chỉnh")
    for split in ("train", "all"):
        status = _read_json(ROOT / "outputs" / "calibration" / f"calibration_status_{split}.json")
        if status.get("status") != "complete" or status.get("run_id") != checks[split]["run_id"]:
            raise ValueError("Lần hiệu chỉnh đã thay đổi hoặc chưa hoàn tất")
    canonical = _canonical_config()
    stored_15min = pd.read_parquet(ROOT / "outputs" / "calibration" / "trajectory_all.parquet")
    stored_15_checks = trajectory_checks(stored_15min, canonical)
    directory = ROOT / "outputs" / "reconstruction" / "validation"
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest = {"schema_version": SCHEMA_VERSION, "status": "running", "engine": "cadcad",
        "created_utc": datetime.now(timezone.utc).isoformat(), "seed_count": seeds,
        "seeds": list(range(42, 42 + seeds)), "completed_seeds": [],
        "provenance": provenance, "calibration_checks": checks, "qualification": QUALIFICATION}
    _write_json(manifest_path, manifest)
    records, trajectories, fits = [], [], []
    try:
        for seed in manifest["seeds"]:
            config = replace(canonical, seed=seed, stochastic=True, stress_days=0, policies=[])
            trajectory, metrics = _run(config, directory / f"seed{seed}", provenance, keep_ledger=(seed == 42))
            fit = metrics["fit"]
            fits.append(fit)
            record = {"seed": seed, "engine": "cadcad", "runtime_seconds": metrics["runtime_seconds"],
                "engine_source_sha256": metrics["engine_source_sha256"],
                **{key: value for key, value in fit.items() if not isinstance(value, (dict, list))},
                **{f"gate_{key}": value for key, value in fit["gates"].items()}}
            records.append(record)
            trajectories.append(trajectory[list(MACRO_COLUMNS)])
            manifest["completed_seeds"].append(seed)
            pd.DataFrame(records).to_csv(directory / "runs.csv", index=False)
            _write_json(manifest_path, manifest)
            print(f"historical seed {seed}: {len(records)}/{seeds}; "
                  f"gates={sum(bool(value) for value in fit['gates'].values())}/6", flush=True)

        stack = np.stack([frame.to_numpy(dtype=float) for frame in trajectories])
        bands = []
        for quantile, label in ((.05, "p05"), (.5, "median"), (.95, "p95")):
            frame = pd.DataFrame(np.quantile(stack, quantile, axis=0),
                index=trajectories[0].index, columns=MACRO_COLUMNS)
            frame.index.name = "time"
            frame["quantile"] = label
            bands.append(frame.reset_index())
        pd.concat(bands, ignore_index=True).to_parquet(directory / "bands.parquet", index=False)
        config_5min = replace(canonical, dt_minutes=5, stochastic=False, stress_days=0, policies=[])
        path_5min, metrics_5min = _run(config_5min, directory / "deterministic_5min", provenance, keep_ledger=False)
        comparison = resolution_comparison(stored_15min, path_5min,
            float(load_targets(15).anchor_deposits.iloc[0]))
        comparison.update({"15min_fit": _read_json(ROOT / "outputs" / "calibration" / "report_all.json")["all"],
            "5min_fit": metrics_5min["fit"], "15min_physical_checks": stored_15_checks,
            "5min_physical_checks": metrics_5min["physical_checks"], "qualification": QUALIFICATION,
            "note": "Sai lệch lớn giữa hai bước cho biết tái hiện còn nhạy với thứ tự xử lý hoặc nhịp quyết định tác nhân."})
        _write_json(directory / "timestep_check.json", comparison)
        if reconstruction_validation_provenance() != provenance:
            raise ValueError("Nguồn, tham số hoặc dữ liệu đã thay đổi trong khi kiểm tra lịch sử")
        manifest.update({"status": "complete", "finished_utc": datetime.now(timezone.utc).isoformat(),
            "physical_checks_pass": True, "seed_runs_passing_all_gates": sum(fit["passes_all"] for fit in fits),
            "gate_pass_counts": {key: sum(bool(fit["gates"][key]) for fit in fits) for key in fits[0]["gates"]},
            "resolution_comparison": {key: value for key, value in comparison.items()
                                      if key.endswith("between_steps")},
            "artifacts_sha256": {name: _sha(directory / name) for name in sorted(_artifact_names(seeds))}})
        _write_json(manifest_path, manifest)
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}",
                        finished_utc=datetime.now(timezone.utc).isoformat())
        _write_json(manifest_path, manifest)
        raise
    return {"manifest": str(manifest_path), "seed_count": seeds,
        "seed_runs_passing_all_gates": manifest["seed_runs_passing_all_gates"],
        "gate_pass_counts": manifest["gate_pass_counts"],
        "resolution_comparison": manifest["resolution_comparison"], "qualification": QUALIFICATION}
