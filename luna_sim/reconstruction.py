"""Audited historical reconstruction report, independent of policy experiments.

This module consumes completed calibration trajectories. It never fits parameters
or runs a simulator, and cannot publish stale or partially completed fits.
"""
from datetime import datetime, timedelta, timezone
from html import escape
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .audit import audit_calibration
from .calibrate import TRAIN_END, _frame_hash, _source_hashes
from .config import DEFAULT_SOURCE, ROOT
from .data import GROUPS, group_targets, load_targets
from .metrics import first_depeg, fit_metrics


ARTIFACTS = ("RECONSTRUCTION_VI.md", "reconstruction.html")
SCHEMA_VERSION = 1
GATE_SPECS = (
    ("ust_mae", "MAE giá UST / USD", .05),
    ("deposit_nrmse", "NRMSE tiền gửi Anchor", .10),
    ("luna_price_log_rmse", "RMSE log₁₀ giá LUNA", .5),
    ("luna_supply_log_rmse", "RMSE log₁₀ cung LUNA", .5),
    ("group_mae_max", "MAE lớn nhất của 6 nhóm", .15),
    ("depeg_error_hours", "Lệch thời điểm mất peg / giờ", 6.),
)


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _observations():
    # A previous in-process cache must not hide a changed input file.
    load_targets.cache_clear()
    group_targets.cache_clear()
    return load_targets(15).copy(), group_targets(15).copy()


def _historical_checks():
    """Use only independently verified, current cadCAD stability artifacts."""
    folder = ROOT / 'outputs' / 'reconstruction' / 'validation'
    if not (folder / 'manifest.json').exists():
        return None
    from .reconstruction_validation import reconstruction_checks_current
    if not reconstruction_checks_current():
        return None
    return {'manifest': _read_json(folder / 'manifest.json'),
            'timestep': _read_json(folder / 'timestep_check.json'),
            'runs': pd.read_csv(folder / 'runs.csv'),
            'bands': pd.read_parquet(folder / 'bands.parquet')}


def reconstruction_provenance():
    """Fingerprint all inputs used by the report, including archived executions."""
    target, groups = _observations()
    sources = _source_hashes()
    sources.update({name: _sha(ROOT / "luna_sim" / name)
                    for name in ("audit.py", "reconstruction.py")})
    paths = []
    folder = ROOT / "outputs" / "calibration"
    for split, parameter_file in (("train", "parameters.json"),
                                  ("all", "parameters_full_fit.json")):
        paths.extend(folder / name for name in (
            f"report_{split}.json", f"calibration_status_{split}.json",
            f"config_{split}.json", f"trajectory_{split}.parquet", parameter_file))
        report = _read_json(folder / f"report_{split}.json")
        run_id = report.get("optimizer", {}).get("run_id")
        if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError(f"{split}: thiếu định danh lần hiệu chỉnh hợp lệ")
        paths.extend(folder / "runs" / run_id / name
                     for name in ("report.json", "execution.json", "trajectory.parquet"))
    stability = _historical_checks()
    if stability is not None:
        sources['reconstruction_validation.py'] = _sha(ROOT / 'luna_sim' / 'reconstruction_validation.py')
        validation = ROOT / 'outputs' / 'reconstruction' / 'validation'
        paths.extend(validation / name for name in ('manifest.json', 'timestep_check.json',
                                                    'runs.csv', 'bands.parquet'))
    return {"source_sha256": sources,
            "target_sha256": _frame_hash(target),
            "group_sha256": _frame_hash(groups),
            "group_observation_coverage": groups.attrs.get("observation_coverage", {}),
            "historical_checks_current": stability is not None,
            "inputs_sha256": {path.relative_to(ROOT).as_posix(): _sha(path)
                              for path in paths}}


def reconstruction_artifact_current():
    """Return False for missing, tampered, stale, or unfinished report artifacts."""
    folder = ROOT / "outputs" / "reconstruction"
    try:
        metadata = _read_json(folder / "manifest.json")
        if metadata.get("status") != "complete" or metadata.get("schema_version") != SCHEMA_VERSION:
            return False
        if set(metadata.get("artifacts_sha256", {})) != set(ARTIFACTS):
            return False
        checks = metadata.get("calibration_checks", {})
        if set(checks) != {"train", "all"}:
            return False
        for split in ("train", "all"):
            status = _read_json(ROOT / "outputs" / "calibration" / f"calibration_status_{split}.json")
            check = checks[split]
            if status.get("status") != "complete" or status.get("run_id") != check.get("run_id"):
                return False
            if not all(check.get(key) is True for key in (
                    "report_metrics_recomputed", "financial_metrics_recomputed",
                    "published_trajectory_matches_run_archive")):
                return False
        if metadata.get("provenance") != reconstruction_provenance():
            return False
        return all(_sha(folder / name) == digest
                   for name, digest in metadata["artifacts_sha256"].items())
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _value(value, digits=4):
    if value is None or (isinstance(value, (int, float)) and not np.isfinite(value)):
        return "không có quan sát"
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else str(value)


def _table(headers, rows):
    md = ["| " + " | ".join(headers) + " |",
          "| " + " | ".join("---" for _ in headers) + " |"]
    md.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    html = ("<div class='table-wrap'><table><thead><tr>" +
            "".join(f"<th>{escape(str(item))}</th>" for item in headers) +
            "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{escape(str(item))}</td>" for item in row) + "</tr>"
                    for row in rows) + "</tbody></table></div>")
    return "\n".join(md), html


def _comparison_figures(target, groups, full, train):
    """Plot actual values, retaining NaNs in observed cohort series as gaps."""
    core = make_subplots(rows=2, cols=2, subplot_titles=(
        "Giá UST / USD", "Giá LUNA / USD · thang log", "Tiền gửi Anchor / tỷ UST",
        "Tổng cung LUNA · thang log"), vertical_spacing=.14)
    series = ((target, "Quan sát", "#5b677a", "solid"),
              (full, "Khớp toàn sự kiện", "#d86c24", "solid"),
              (train, "Tham số trước 11/5", "#2677ad", "dash"))
    for row, col, field, scale in ((1, 1, "ust_price", 1), (1, 2, "luna_price", 1),
                                   (2, 1, "anchor_deposits", 1e9), (2, 2, "luna_supply", 1)):
        for frame, label, color, dash in series:
            core.add_trace(go.Scatter(x=frame.index, y=frame[field] / scale,
                name=label, legendgroup=label, showlegend=(row == 1 and col == 1),
                line={"color": color, "dash": dash}, connectgaps=False), row=row, col=col)
    core.update_yaxes(type="log", row=1, col=2)
    core.update_yaxes(type="log", row=2, col=2)
    core.update_layout(height=750, template="plotly_white", hovermode="x unified",
                       legend={"orientation": "h", "y": 1.12}, margin={"t": 100})

    native = go.Figure()
    for frame, field, label, color in ((target, "native_ust", "Quan sát", "#5b677a"),
            (full, "native_served", "Khớp toàn sự kiện", "#d86c24"),
            (train, "native_served", "Tham số trước 11/5", "#2677ad")):
        daily = frame[field].resample("1D").sum(min_count=1) / 1e9
        native.add_trace(go.Bar(x=daily.index, y=daily, name=label, marker_color=color))
    native.update_layout(title="Native swap UST → LUNA / tỷ UST mỗi ngày", barmode="group",
        height=420, template="plotly_white", yaxis_title="UST đầu vào, trước phí", hovermode="x unified")

    cohorts = make_subplots(rows=3, cols=2,
        subplot_titles=tuple(f"Nhóm {label} USD trước sự kiện" for label in GROUPS),
        vertical_spacing=.11)
    for i in range(6):
        row, col = i // 2 + 1, i % 2 + 1
        for values, label, color, dash in (
                (groups[i], "Quan sát", "#5b677a", "solid"),
                (full[f"group_{i}_remaining"], "Khớp toàn sự kiện", "#d86c24", "solid"),
                (train[f"group_{i}_remaining"], "Tham số trước 11/5", "#2677ad", "dash")):
            cohorts.add_trace(go.Scatter(x=values.index, y=values, name=label,
                legendgroup=label, showlegend=(i == 0), line={"color": color, "dash": dash},
                connectgaps=False), row=row, col=col)
    cohorts.update_yaxes(range=[0, 1.03], tickformat=".0%")
    cohorts.update_layout(height=870, template="plotly_white", hovermode="x unified",
        legend={"orientation": "h", "y": 1.10}, margin={"t": 100})
    for figure in (core, native, cohorts):
        figure.update_xaxes(title_text="Thời gian UTC")
    return core, native, cohorts


def _phase_rows(full, train, target):
    onset = first_depeg(target.ust_price)
    start = target.index[0]
    end = pd.Timestamp(target.index[-1].to_pydatetime() + timedelta(minutes=15))
    break_time = onset if onset is not None else TRAIN_END
    phases = (("Trước mất peg", start, break_time),
              ("Rút vốn, trước 11/5", max(start, break_time), TRAIN_END),
              ("Từ 11/5", max(start, TRAIN_END, break_time), end))
    rows = []
    for label, beginning, ending in phases:
        if beginning >= ending:
            continue
        for trajectory, model in ((full, "Toàn sự kiện"), (train, "Trước 11/5")):
            metric = fit_metrics(trajectory, dt=15, split="all", start=beginning, end=ending)
            if metric:
                rows.append([label, model] + [_value(metric.get(key)) for key, _, _ in GATE_SPECS[:5]])
    return rows


def _stability_sections(stability):
    if stability is None:
        return [('Độ ổn định giữa seed và bước thời gian',
                 'Chưa có bộ kiểm tra cadCAD nhiều seed và bước 5/15 phút hiện hành. '
                 'Các đường xác định ở trên chưa chứng minh độ ổn định của ABM.', '', '')]
    manifest, timestep, runs = stability['manifest'], stability['timestep'], stability['runs']
    count = manifest['seed_count']
    text = (f"{manifest['seed_runs_passing_all_gates']}/{count} lượt ngẫu nhiên đạt đủ sáu ngưỡng. "
            'Sổ cái và tồn kho được kiểm tra độc lập; đạt các kiểm tra tài chính không đồng nghĩa khớp lịch sử. '
            + manifest['qualification'])
    rows = []
    for key, label, limit in GATE_SPECS:
        values = pd.to_numeric(runs[key], errors='coerce').dropna()
        rows.append([label, f'≤ {limit:g}', f"{manifest['gate_pass_counts'][key]}/{count}"] +
                    [_value(values.quantile(q)) if len(values) else 'không xuất hiện'
                     for q in (.05, .5, .95)])
    seed_md, seed_html = _table(['Chỉ số', 'Ngưỡng lịch sử', 'Số seed đạt',
                                'p05 sai số', 'Trung vị sai số', 'p95 sai số'], rows)
    mapping = (('ust_mae', 'ust_mae_between_steps'),
               ('deposit_nrmse', 'deposit_nrmse_between_steps'),
               ('luna_price_log_rmse', 'luna_price_log_rmse_between_steps'),
               ('luna_supply_log_rmse', 'luna_supply_log_rmse_between_steps'))
    rows = [[dict((k, label) for k, label, _ in GATE_SPECS)[metric],
             _value(timestep['15min_fit'][metric]), _value(timestep['5min_fit'][metric]),
             _value(timestep[between])] for metric, between in mapping]
    cadence_md, cadence_html = _table(['Chỉ số', 'Sai số với quan sát: 15 phút',
                                      'Sai số với quan sát: 5 phút', 'Sai lệch giữa hai bước'], rows)
    return [('Biến thiên giữa các seed lịch sử', text, seed_md, seed_html),
            ('Đối chiếu bước 5/15 phút',
             'Giữ cùng tham số và so đúng thời điểm UTC, không nội suy. '
             'Sai lệch lớn giữa hai bước cho thấy đường mô phỏng còn nhạy với nhịp cập nhật; '
             'không dùng đường xác định 15 phút để khẳng định mô hình đã ổn định.',
             cadence_md, cadence_html)]


def _stability_figure(target, bands):
    figure = make_subplots(rows=2, cols=2, subplot_titles=(
        'Giá UST / USD', 'Giá LUNA / USD · thang log',
        'Tiền gửi Anchor / tỷ UST', 'Tổng cung LUNA · thang log'), vertical_spacing=.14)
    for row, col, field, scale in ((1, 1, 'ust_price', 1), (1, 2, 'luna_price', 1),
                                  (2, 1, 'anchor_deposits', 1e9), (2, 2, 'luna_supply', 1)):
        show = row == 1 and col == 1
        figure.add_trace(go.Scatter(x=target.index, y=target[field]/scale,
            name='Quan sát', legendgroup='Quan sát', showlegend=show,
            line={'color':'#5b677a'}), row=row, col=col)
        for quantile in ('p95', 'p05', 'median'):
            frame = bands.loc[bands['quantile']==quantile]
            figure.add_trace(go.Scatter(x=frame.time, y=frame[field]/scale,
                name=quantile, legendgroup=quantile, showlegend=show,
                line={'color':'#2677ad', 'width':2 if quantile=='median' else 0},
                fill='tonexty' if quantile=='p05' else None,
                fillcolor='rgba(38,119,173,.18)'), row=row, col=col)
    figure.update_yaxes(type='log', row=1, col=2)
    figure.update_yaxes(type='log', row=2, col=2)
    figure.update_layout(height=750, template='plotly_white', hovermode='x unified',
                        legend={'orientation':'h','y':1.12}, margin={'t':100})
    return figure


def build_reconstruction_report():
    """Audit and publish historical charts/metrics without a policy or seed suite."""
    # Run both authoritative audits before touching the output directory.
    current_sources = _source_hashes()
    checks = {split: audit_calibration(split, current_sources) for split in ("train", "all")}
    provenance = reconstruction_provenance()
    if any(provenance["source_sha256"].get(name) != digest
           for name, digest in current_sources.items()):
        raise ValueError("Nguồn đã thay đổi sau khi kiểm toán hiệu chỉnh")
    calibration = ROOT / "outputs" / "calibration"
    for split in ("train", "all"):
        status = _read_json(calibration / f"calibration_status_{split}.json")
        if status.get("status") != "complete" or status.get("run_id") != checks[split]["run_id"]:
            raise ValueError(f"{split}: lần hiệu chỉnh chưa hoàn tất hoặc đã thay đổi sau kiểm toán")
    reports = {split: _read_json(calibration / f"report_{split}.json") for split in ("train", "all")}
    configurations = {split: _read_json(calibration / f"config_{split}.json") for split in ("train", "all")}
    train = pd.read_parquet(calibration / "trajectory_train.parquet")
    full = pd.read_parquet(calibration / "trajectory_all.parquet")
    target, groups = _observations()
    stability = _historical_checks()
    core, native, cohorts = _comparison_figures(target, groups, full, train)
    created = datetime.now(timezone.utc).isoformat()

    score_sets = (("Hiệu chỉnh trước 11/5", reports["train"]["train"]),
                  ("Giữ tham số, từ 11/5", reports["train"]["validation"]),
                  ("Khớp toàn sự kiện", reports["all"]["all"]))
    gate_rows = [[title, f"≤ {limit:g}"] +
        [f"{_value(scores.get(key))} · {'đạt' if scores.get('gates', {}).get(key) else 'chưa đạt'}"
         for _, scores in score_sets] for key, title, limit in GATE_SPECS]
    gate_md, gate_html = _table(["Chỉ số", "Ngưỡng"] + [name for name, _ in score_sets], gate_rows)
    result_text = "; ".join(f"{name}: {sum(bool(v) for v in scores['gates'].values())}/6 ngưỡng"
                            for name, scores in score_sets) + "."
    onset_rows = [[name, scores.get("predicted_depeg_utc") or "không xuất hiện",
                   scores.get("observed_depeg_utc") or "không xuất hiện",
                   _value(scores.get("depeg_signed_error_hours"), 2)]
                  for name, scores in score_sets]
    onset_md, onset_html = _table(["Bộ tham số / mẫu", "Mô phỏng UTC", "Quan sát UTC", "Lệch có dấu / giờ"], onset_rows)
    phase_md, phase_html = _table(["Giai đoạn", "Bộ tham số", "UST MAE", "Anchor NRMSE",
        "LUNA log RMSE", "Cung log RMSE", "Nhóm MAE lớn nhất"], _phase_rows(full, train, target))
    native_rows = [[name, _value(scores.get("native_ust_simulated_total", 0) / 1e9, 3),
                   _value(scores.get("native_ust_observed_total", 0) / 1e9, 3),
                   _value(scores.get("native_daily_nrmse")), _value(scores.get("native_fee_mae"))]
                  for name, scores in score_sets]
    native_md, native_html = _table(["Mẫu", "Mô phỏng / tỷ UST", "Quan sát / tỷ UST",
        "NRMSE khối lượng ngày", "MAE tỷ lệ phí"], native_rows)

    coverage = groups.attrs.get("observation_coverage", {})
    observed_index = groups.index[groups.notna().any(axis=1)]
    coverage_text = (f"Quan sát 6 nhóm có {len(observed_index)} bước 15 phút"
        + (f", từ {observed_index[0].isoformat()} đến {observed_index[-1].isoformat()} UTC." if len(observed_index)
           else "; chưa có quan sát hợp lệ."))
    coverage_text += " Phần không có quan sát được để trống; không kéo dài đường dữ liệu thật bằng giá trị cuối cùng."
    if coverage.get("raw_end_utc"):
        coverage_text += f" Bản trích giao dịch kết thúc tại {coverage['raw_end_utc']}."

    configuration_rows = []
    for split, label in (("train", "Trước 11/5"), ("all", "Toàn sự kiện")):
        cfg, fitted = configurations[split], reports[split]
        configuration_rows.append([label, checks[split]["run_id"], cfg.get("n_depositors"),
            cfg.get("n_arbitrageurs"), cfg.get("dt_minutes"), cfg.get("seed"),
            checks[split]["rows"], fitted.get("calls"), _value(fitted.get("objective"))])
    config_md, config_html = _table(["Bộ tham số", "Run ID", "Người gửi", "Arbitrageur",
        "Bước / phút", "Seed", "Số bước", "Số lần đánh giá", "Hàm mất mát"], configuration_rows)
    error_rows = []
    for split, label in (("train", "Trước 11/5"), ("all", "Toàn sự kiện")):
        financial = reports[split].get("financial_metrics", {})
        errors = financial.get("max_accounting_errors", {})
        error_rows.append([label] + [_value(errors.get(key), 6)
                                    for key in ("ust_error", "luna_error", "usd_error", "claim_error")])
    accounting_md, accounting_html = _table(["Bộ tham số", "UST", "LUNA", "USD", "Quyền đòi Anchor"], error_rows)

    sources = _read_json(ROOT / "data" / "sources.json")
    source_items = [
        ("Dữ liệu gốc ngoại tuyến", str(DEFAULT_SOURCE / "data")),
        ("Giá UST/LUNA", "prices/ust_price_may2022.parquet; prices/luna_price_may2022.parquet"),
        ("Anchor", "anchor_run/epoch_state_fig10.parquet; anchor_run/anchor_run_tx_cleaned.parquet"),
        ("Cung LUNA và native swap", "native_swaps/luna_total_supply_run.parquet; native_swaps/ust_luna_swaps_run.parquet"),
        ("Quy mô người gửi trước sự kiện", "loss/depositor_prerun_size.parquet; labels/interdm_addresses.parquet"),
    ]
    source_md, source_html = _table(["Nguồn", "Vị trí trong bộ dữ liệu"], source_items)
    links = [("Nghiên cứu và nguồn bộ dữ liệu", sources.get("paper")),
             ("Kiểm toán LFG/TFL", sources.get("audit")), ("BTC phút", sources.get("btc")),
             ("Đặc tả native market", sources.get("market_spec"))]
    link_md = "\n".join(f"- [{label}]({url})" for label, url in links if url)
    link_html = "<ul>" + "".join(f"<li><a href='{escape(url, quote=True)}'>{escape(label)}</a></li>"
                                  for label, url in links if url) + "</ul>"
    limits = [
        "Bộ khớp toàn sự kiện dùng dữ liệu từ 6–15/5/2022 để ước lượng tham số. Đây là tái hiện trong mẫu; chất lượng ngoài mẫu được đọc riêng ở cột giữ tham số từ 11/5.",
        "Các đồ thị dùng quỹ đạo lịch sử xác định, seed cố định. Kiểm toán xác nhận đồng nhất fast/cadCAD đã được ghi trong kết quả hiệu chỉnh; báo cáo không chạy lại hoặc chọn seed theo mức khớp.",
        "Giá, cung, tiền gửi và giao dịch native là mục tiêu đối chiếu. Chuỗi giá mục tiêu không được ép vào quỹ đạo mô phỏng. Cung tổng hợp theo giờ chỉ có hiệu lực từ cuối giờ; các thời điểm trên báo cáo đều là UTC.",
        "Sáu nhóm đo tỷ lệ vốn gốc ban đầu còn lại của người gửi trước sự kiện, theo FIFO, loại các ví trung gian có nhãn. Tiền gửi mới và lãi không làm tăng lại vốn gốc; đây là đại lượng khác tổng số dư Anchor.",
        "Nguồn lực LFG/TFL và các khoảng gián đoạn chain/native là đầu vào lịch sử. Mốc chuyển BTC không xác định thời điểm bán BTC hay mua UST; giao dịch Jump và các ví TFL chưa có lịch thực thi đầy đủ.",
        "Độ sâu thị trường, hành vi mua/bán và hàm phản ứng của tác nhân là giả định hiệu chỉnh. Sai số thấp của đường tổng hợp chưa xác định duy nhất cơ chế vi mô đã gây ra sự kiện thật.",
        "Chỉ số native bổ sung kiểm tra khối lượng theo ngày và phí. Đạt sáu ngưỡng không tự động bảo đảm từng giao dịch, mỗi ví, hay mọi thời điểm đều khớp.",
    ]
    sections = [
        ("Kết quả đối chiếu", result_text, gate_md, gate_html),
        ("Thời điểm mất peg", "Mất peg là giá UST dưới 0,98 USD liên tục một giờ. Sai lệch âm nghĩa là mô hình mất peg sớm.", onset_md, onset_html),
        ("Sai số theo giai đoạn", "Sai số giai đoạn dùng cùng định nghĩa với bảng toàn mẫu; ngưỡng nhóm chỉ xét các bước có quan sát.", phase_md, phase_html),
        ("Native swap", "Khối lượng UST đầu vào được tính trước phí, tách khỏi lượng LUNA sau phí.", native_md, native_html),
        ("Sáu nhóm người gửi", coverage_text, "", ""),
        ("Cấu hình và kiểm toán", "Hai lần hiệu chỉnh đã hoàn tất, đúng nguồn hiện tại; các chỉ số và quỹ đạo được đối chiếu lại với bản lưu của từng run.", config_md, config_html),
        ("Sai lệch sổ cái lớn nhất", "Sai lệch tuyệt đối qua các bước, tính bằng token hoặc USD tương ứng; cần đọc cùng quy mô cung và tài sản.", accounting_md, accounting_html),
        ("Nguồn dữ liệu", "Các đường quan sát được dựng từ dữ liệu ngoại tuyến bên dưới.", source_md + "\n\n" + link_md, source_html + link_html),
    ]
    stability_start = len(sections)
    sections.extend(_stability_sections(stability))
    md = ["# Tái hiện lịch sử UST/LUNA, 6–15/5/2022", "", f"Tạo lúc {created}.", "",
          "Báo cáo tách kết quả khớp toàn sự kiện và kiểm định giữ nguyên tham số theo thời gian. "
          "Mở [biểu đồ tương tác](reconstruction.html) để đối chiếu từng giai đoạn.", ""]
    html_sections = []
    for title, text, md_table, html_table in sections:
        md.extend([f"## {title}", "", text, "", md_table, ""])
        html_sections.append(f"<section><h2>{escape(title)}</h2><p>{escape(text)}</p>{html_table}</section>")
    md.extend(["## Giới hạn cách diễn giải", "", *(f"- {text}" for text in limits), "",
               "Danh tính mã nguồn, dữ liệu đầu vào, quỹ đạo và hai tệp báo cáo được ghi trong `manifest.json`. "
               "Báo cáo chỉ được coi là hiện hành khi tất cả dấu SHA-256 còn trùng khớp.", ""])
    plots = [figure.to_html(full_html=False, include_plotlyjs=(i == 0),
             config={"displaylogo": False, "responsive": True})
             for i, figure in enumerate((core, native, cohorts))]
    # Attach the corresponding charts to the relevant explanatory sections.
    html_sections[0] += plots[0]
    html_sections[3] += plots[1]
    html_sections[4] += plots[2]
    if stability is not None:
        html_sections[stability_start] += _stability_figure(target, stability['bands']).to_html(
            full_html=False, include_plotlyjs=False, config={'displaylogo':False, 'responsive':True})
    html_document = ("<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Tái hiện UST/LUNA · 6–15/5/2022</title><style>"
        "body{font:16px/1.6 system-ui,sans-serif;color:#182433;background:#f4f6f8;margin:0}"
        "main{max-width:1280px;margin:auto;padding:28px}section{background:white;border-radius:10px;padding:22px;margin:20px 0}"
        "h1{font-size:30px;line-height:1.3}h2{font-size:22px}a{color:#196ba0}.table-wrap{overflow-x:auto}"
        "table{border-collapse:collapse;font-size:14px;width:100%}th,td{padding:9px 12px;border-bottom:1px solid #dce1e8;text-align:left}"
        "th{background:#edf2f7}small{color:#526172}li{margin:10px 0}</style></head><body><main>"
        "<h1>Tái hiện lịch sử UST/LUNA, 6–15/5/2022</h1>"
        f"<small>Tạo lúc {escape(created)} · Thời gian UTC</small>"
        "<p>Đối chiếu dữ liệu thật với quỹ đạo ABM và System Dynamics chạy bằng cadCAD. "
        "Bộ khớp toàn sự kiện được trình bày riêng với kiểm định giữ nguyên tham số từ ngày 11/5.</p>"
        + "".join(html_sections) + "<section><h2>Giới hạn cách diễn giải</h2><ul>"
        + "".join(f"<li>{escape(text)}</li>" for text in limits)
        + "</ul><p>Danh tính mã nguồn, dữ liệu, quỹ đạo và báo cáo được ghi trong manifest.json.</p></section></main></body></html>")

    if reconstruction_provenance() != provenance:
        raise ValueError("Nguồn hoặc kết quả hiệu chỉnh đã thay đổi trong khi dựng báo cáo")
    folder = ROOT / "outputs" / "reconstruction"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ARTIFACTS[0]).write_text("\n".join(md), encoding="utf-8")
    (folder / ARTIFACTS[1]).write_text(html_document, encoding="utf-8")
    if reconstruction_provenance() != provenance:
        # Existing artifacts remain reviewable, but no current manifest certifies them.
        raise ValueError("Nguồn hoặc kết quả hiệu chỉnh đã thay đổi trước khi công bố báo cáo")
    manifest = {"schema_version": SCHEMA_VERSION, "status": "complete", "created_utc": created,
        "provenance": provenance, "calibration_checks": checks,
        "fidelity": {"full_fit_passes_all": bool(reports["all"]["all"]["passes_all"]),
                     "parameter_holdout_passes_all": bool(reports["train"]["validation"]["passes_all"])},
        "artifacts_sha256": {name: _sha(folder / name) for name in ARTIFACTS}}
    if stability is not None:
        manifest['fidelity'].update(
            seed_count=stability['manifest']['seed_count'],
            seed_runs_passing_all_gates=stability['manifest']['seed_runs_passing_all_gates'])
    temporary = folder / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(folder / "manifest.json")
    return {"report": str(folder / ARTIFACTS[0]), "charts": str(folder / ARTIFACTS[1]),
            "manifest": str(folder / "manifest.json"), "fidelity": manifest["fidelity"]}
