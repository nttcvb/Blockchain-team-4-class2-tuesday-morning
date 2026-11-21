from pathlib import Path
import json
import hashlib
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .config import ROOT, load_params
from .data import load_targets
from .experiments import experiment_sources, experiment_artifact_current
from .calibrate import _source_hashes, parameter_sha256
from .diagnostics import diagnostic_sources


def report_provenance():
    relative_paths=['luna_sim/report.py','outputs/calibration/report_train.json',
        'outputs/calibration/report_all.json','outputs/calibration/calibration_status_train.json',
        'outputs/calibration/calibration_status_all.json','outputs/calibration/diagnostics.json',
        'outputs/experiments/execution_metadata.json','outputs/experiments/summary.csv',
        'outputs/experiments/sensitivity.csv','outputs/experiments/sensitivity_metadata.json',
        'outputs/experiments/timestep_check.json','outputs/experiments/timestep_check_metadata.json','outputs/improvement/comparison.json',
        'outputs/improvement/COMPARISON_VI.md']
    return {'fitted_sources':_source_hashes(),'experiment_sources':experiment_sources(),
            'parameter_sha256':parameter_sha256(load_params()),
            'inputs_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() if (ROOT/name).exists() else None
                            for name in relative_paths}}


def report_artifact_current():
    output=ROOT/'outputs'
    metadata_path=output/'report_metadata.json'
    if not metadata_path.exists(): return False
    metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
    if metadata.get('provenance')!=report_provenance(): return False
    if set(metadata.get('artifacts_sha256',{}))!={'REPORT_VI.md','historical_comparison.html'}: return False
    return all((output/name).exists() and hashlib.sha256((output/name).read_bytes()).hexdigest()==digest
               for name,digest in metadata['artifacts_sha256'].items())


def build_report():
    output=ROOT/'outputs'; output.mkdir(exist_ok=True)
    metadata_path=output/'experiments'/'execution_metadata.json'
    metadata=json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    if metadata.get('status')=='running': raise ValueError('Wait for the seed suite to finish before publishing a report')
    current_engine=hashlib.sha256((ROOT/'luna_sim'/'engine.py').read_bytes()).hexdigest()
    if metadata.get('engine_source_sha256')!=current_engine or metadata.get('parameters')!=load_params().__dict__ or metadata.get('source_sha256')!=experiment_sources():
        raise ValueError('Run the seed suite with the current engine and parameters before publishing a report')
    calibration=output/'calibration'/'report_train.json'
    if not calibration.exists(): raise ValueError('Run calibration first')
    r=json.loads(calibration.read_text(encoding='utf-8'))
    full_path=output/'calibration'/'report_all.json'
    full=json.loads(full_path.read_text(encoding='utf-8')) if full_path.exists() else None
    for fitted in [r,full]:
        if fitted and fitted.get('provenance',{}).get('source_sha256')!=_source_hashes():
            raise ValueError('Calibration belongs to older model sources; refit before publishing a report')
        if fitted:
            status=json.loads((output/'calibration'/f"calibration_status_{fitted['fit_split']}.json").read_text(encoding='utf-8'))
            if status.get('status')!='complete' or status.get('run_id')!=fitted.get('optimizer',{}).get('run_id'):
                raise ValueError('Wait for completed calibration matching this report before publishing')
            param_path=output/'calibration'/('parameters.json' if fitted['fit_split']=='train' else 'parameters_full_fit.json')
            if fitted.get('parameter_sha256')!=parameter_sha256(load_params(param_path)):
                raise ValueError('Calibration and saved parameters differ; refit before publishing a report')
    t=pd.read_parquet(output/'calibration'/('trajectory_all.parquet' if full else 'trajectory_train.parquet'))
    observed=load_targets()
    fig=make_subplots(rows=2,cols=2,subplot_titles=['UST / USD','Tiền gửi Anchor / UST','LUNA / USD','Nguồn cung LUNA'])
    for i,column in enumerate(['ust_price','anchor_deposits','luna_price','luna_supply']):
        row,col=i//2+1,i%2+1
        fig.add_trace(go.Scatter(x=observed.index,y=observed[column],name='Dữ liệu thật',legendgroup='truth',showlegend=i==0,line={'color':'#cbd5e1','dash':'dot'}),row=row,col=col)
        fig.add_trace(go.Scatter(x=t.index,y=t[column],name='Mô phỏng',legendgroup='model',showlegend=i==0,line={'color':'#56c4ff'}),row=row,col=col)
    fig.update_yaxes(type='log',row=2,col=1); fig.update_yaxes(type='log',row=2,col=2)
    fig.update_layout(template='plotly_dark',title='Luna–UST: đối chiếu lịch sử (khớp toàn mẫu)' if full else 'Luna–UST: đối chiếu lịch sử (tham số 06–10/05)',height=760)
    fig.write_html(output/'historical_comparison.html',include_plotlyjs=True)
    lines=['# Báo cáo bài nhóm: mô phỏng Luna–UST bằng cadCAD','',
        '## 1. Câu hỏi và thiết kế','',
        'Mô hình kết hợp 1.000 tác nhân người gửi đại diện, 20 arbitrageurs và tồn lượng tài chính tổng hợp. Mỗi bước quyết định 15 phút lần lượt quan sát, kích hoạt chính sách, quyết định hành vi, xử lý Anchor, khớp giao dịch/native swap và kiểm tra kế toán; thị trường/native tích phân nội bộ một phút. Thí nghiệm từ 06–15/05/2022 dùng UTC. Giá, rút tiền và nguồn cung được sinh nội sinh; dữ liệu lịch sử dùng làm mục tiêu hiệu chỉnh và đối chiếu.','',
        'Hai ví A/B là cú sốc khởi phát được tái lập có điều kiện. Không suy diễn rằng đây là bằng chứng tấn công hay thao túng. Vốn bổ sung để thực hiện các lần gửi lại của hai ví là suy ra từ chuỗi hành động, có hạch toán trong nguồn cung UST ban đầu.','',
        '## 2. Độ khớp và giới hạn','',
        '| Chỉ số | Hiệu chỉnh 06–10/05 | Kiểm định 11–15/05 | Mục tiêu |','|---|---:|---:|---:|']
    specs=[('ust_mae','MAE UST / USD',.05),('deposit_nrmse','NRMSE tiền gửi',.10),('luna_price_log_rmse','RMSE log₁₀ giá LUNA',.5),('luna_supply_log_rmse','RMSE log₁₀ nguồn cung LUNA',.5),('group_mae_max','MAE nhóm lớn nhất',.15),('depeg_error_hours','Sai lệch mất peg / giờ',6.)]
    for key,title,limit in specs:
        tr,va=r['train'][key],r['validation'][key]
        fmt=lambda x:'không xác định' if x is None else f'{x:.4f}'
        lines.append(f'| {title} | {fmt(tr)} | {fmt(va)} | ≤ {limit} |')
    lines+=['',f"**Đạt toàn bộ ngưỡng ngoài mẫu: {'Có' if r['validation']['passes_all'] else 'Chưa'}.**",
        'Các chính sách chỉ là thí nghiệm có điều kiện trong mô hình khi các ngưỡng còn thất bại. Mức khớp trong mẫu không chứng minh mô hình dự báo được khủng hoảng. Cấu trúc được phát triển khi đã biết toàn sự kiện; đây là tách thời gian để kiểm tra tham số, không phải kiểm định cấu trúc mù.','',
        'Độ sâu giao dịch không được quan sát trực tiếp; sổ lệnh đầy đủ và giao dịch Jump chưa được công bố trong bộ dữ liệu. Lịch thay đổi năng lực native swap và thời điểm ngừng đổi là xấp xỉ, không phải tái lập từng block. Replay tách chain/Anchor/native: Anchor tiếp tục sau restart ngày 13/05 dù native mint đã tắt. Các cửa sổ gián đoạn được đối chiếu khoảng trống giao dịch, rời rạc hóa theo bước ABM. Gián đoạn lịch sử không được ép vào phản thực tế. An ninh validator nằm ngoài phạm vi.','',
        '## 3. Nguồn lực và chính sách','',
        'LFG: 80.394 BTC ban đầu, giới hạn dùng 80.081 BTC và giữ 313 BTC; 26.281.671 USDT + 23.555.590 USDC. TFL: giới hạn đóng góp ròng 613.616.889 USD; không coi khoản đó là tiền mặt có sẵn từ đầu. Khoản chuyển LFG/TFL/Jump được gom theo chủ sở hữu cuối cùng, không cộng trùng ngân sách. BTC bán theo giá BTCUSDT lịch sử, giả định USDT ≈ USD, trừ phí và trượt giá. BNB/AVAX và UST/LUNA không được tính thành nguồn USD bảo chứng.','',
        'Biên muộn là mặc định. BTC dựa trên timestamp chuyển đã công bố, thêm một giờ vận hành trong biên muộn là giả định. Gross transfer và net-budget attribution giữ cap được ghi riêng; chuyển không đồng nghĩa mua UST ngay. Khoảng khả dụng của đóng góp riêng TFL vẫn chưa xác minh chính xác. Bảng nguồn đầy đủ ở `data/sources.json`.','',
        'Bốn chính sách: mua UST, bổ sung thanh khoản, điều chỉnh virtual pool/native swap và hạn chế rút Anchor tạm thời. Mọi khoản mua cùng dùng một sổ tài sản. Thời điểm kích hoạt dựa trên thông tin tại thời điểm mô phỏng; không tối ưu với dữ liệu tương lai. Đánh giá tác động chính sách so với đối chứng no_rescue cùng tham số, seed, lịch quỹ và chế độ hoạt động. Replay lịch sử còn có biên quỹ sớm và gián đoạn chain, nên chênh lệch với replay không chỉ do chính sách.','',
        '## 4. Kết quả thí nghiệm','']
    if full:
        section=['','### Bộ khớp toàn sự kiện dùng cho dashboard và thí nghiệm','',
            'Bộ này dùng toàn bộ 06–15/05 và giữ cố định giữa các chính sách. Tất cả chỉ số dưới đây là trong mẫu; không thay thế bảng kiểm định theo thời gian bên trên.','',
            '| Chỉ số | Sai số toàn mẫu | Mục tiêu |','|---|---:|---:|']
        for key,title,limit in specs:
            value=full['all'][key]
            section.append(f'| {title} | {"không xác định" if value is None else f"{value:.4f}"} | ≤ {limit} |')
        fm=full['all']
        section+=['',f"Đạt toàn bộ ngưỡng trong mẫu: **{'Có' if fm['passes_all'] else 'Chưa'}**.",
            f"Native swap: mô phỏng {fm['native_ust_simulated_total']/1e9:.3f} tỷ UST, dữ liệu {fm['native_ust_observed_total']/1e9:.3f} tỷ; NRMSE khối lượng ngày {fm['native_daily_nrmse']:.3f}. Hàm hiệu chỉnh v3 có khối lượng native theo ngày và phí tại những bước có swap thực tế; phạt onset theo ngưỡng 6 giờ và cân bằng giai đoạn.",
            f"Mất peg kéo dài: mô hình {fm.get('predicted_depeg_utc')}, quan sát {fm.get('observed_depeg_utc')}; sai lệch có dấu {fm.get('depeg_signed_error_hours')} giờ (âm nghĩa là sớm).",
            'Biểu đồ `historical_comparison.html` dùng bộ khớp toàn mẫu. Giá LUNA sau ngừng native có mức cầu còn lại được cấp bởi USD có sẵn của market maker, không tạo thêm tiền cứu trợ.','',
            '**Giới hạn cứu trợ lịch sử:** audit ghi nhận Jump chuyển 1.515.689.462 UST cho TFL, nhưng thiếu từng lệnh giao dịch. Khối lượng đó chưa được gán lịch mua riêng; lịch replay hiện chỉ có ý định mua gộp TFL và stablecoin LFG, bị chặn bởi quỹ thực tế. BTC của LFG vẫn nằm trong trần nguồn lực. Vì vậy so sánh phản thực tế không phải ước lượng nhân quả đầy đủ của một quyết định lịch sử.','']
        position=lines.index('## 3. Nguồn lực và chính sách')
        lines[position:position]=section
    exp=output/'experiments'
    if (exp/'summary.csv').exists():
        summary=pd.read_csv(exp/'summary.csv')
        lines+=['| Kịch bản | Số seed | Tỷ lệ cứu vãn | UST cuối kỳ | Chi phí / tỷ USD | Tổn thất người gửi |','|---|---:|---:|---:|---:|---:|']
        for _,x in summary.iterrows():
            lines.append(f'| {x.scenario} | {int(x.n_runs)} | {x.rescue_rate:.0%} | {x.final_ust_price:.4f} | {x.support_spent_usd/1e9:.3f} | {x.depositor_loss_fraction:.1%} |')
        winners=summary.loc[summary.rescue_rate>0,'scenario'].tolist()
        lines+=['',('Có kịch bản đạt tiêu chí trong một số seed: '+', '.join(winners)) if winners else 'Không kịch bản mặc định nào đạt đầy đủ tiêu chí cứu vãn trong các lần chạy đã báo cáo. Điều này không chứng minh rằng mọi chính sách lịch sử đều bất khả thi.']
    else: lines+=['Chưa chạy bộ thí nghiệm nhiều seed.']
    if (exp/'sensitivity.csv').exists():
        if not experiment_artifact_current('sensitivity'):
            raise ValueError('Rebuild sensitivity analysis with current sources and parameters before publishing a report')
        s=pd.read_csv(exp/'sensitivity.csv')
        lines+=['',f"Độ nhạy đã kiểm tra {len(s)} cấu hình: độ sâu UST/LUNA, phản ứng mất peg và lây lan, lịch quỹ sớm/muộn, độ trễ 15/60/360 phút, ngưỡng kích hoạt và virtual pool."]
    if (exp/'timestep_check.json').exists():
        if not experiment_artifact_current('timestep_check'):
            raise ValueError('Rebuild timestep check with current sources and parameters before publishing a report')
        check=json.loads((exp/'timestep_check.json').read_text())
        lines+=['',f"So sánh bước 5/15 phút: MAE UST = {check['ust_mae_between_steps']:.4f} USD; NRMSE tiền gửi = {check['deposit_nrmse_between_steps']:.3f}; RMSE log₁₀ LUNA = {check['luna_log_rmse_between_steps']:.3f}. Sai lệch lớn cho thấy kết luận nhạy với cách rời rạc hóa."]
    diagnostic_path=output/'calibration'/'diagnostics.json'
    if diagnostic_path.exists():
        diagnostic=json.loads(diagnostic_path.read_text(encoding='utf-8'))
        if diagnostic.get('source_sha256')!=diagnostic_sources():
            raise ValueError('Rebuild diagnostics with the current fitted trajectory before publishing a report')
        lines+=['','### Đối chiếu bổ sung trong mẫu','',
            '| Giai đoạn | MAE UST | NRMSE tiền gửi | RMSE log giá LUNA | RMSE log nguồn cung |',
            '|---|---:|---:|---:|---:|']
        for key,label in [('before_native_stop','Trước 13/05 02:00 UTC'),('after_native_stop','Sau mốc ngừng native xấp xỉ')]:
            d=diagnostic[key]
            lines.append(f"| {label} | {d['ust_mae']:.4f} | {d['deposit_nrmse']:.4f} | {d['luna_price_log_rmse']:.4f} | {d['luna_supply_log_rmse']:.4f} |")
        lines+=['','| Nguồn giá riêng | MAE UST so với mô hình | MAE so với chuỗi giá tổng hợp |','|---|---:|---:|']
        for name,d in diagnostic['venues'].items():
            a=d.get('mae_model',d.get('ust_mae_model')); b=d.get('mae_aggregate_reference',d.get('ust_mae_aggregate_reference'))
            lines.append(f'| {name.upper()} | {a:.4f} | {b:.4f} |')
        lines+=['','Curve/Binance chỉ có ngày 07/05; FTX là nguồn riêng, không thay thế mục tiêu chính. Curve loại quote 3Crv; các stablecoin quote được giả định gần USD. Tương quan lệnh bán ròng với lợi suất được ghi trong `diagnostics.json`, chỉ là mô tả giao dịch, không xác định tác động nhân quả. Bảng mốc và mức độ chắc chắn nằm ở `data/processed/event_timeline.csv`.']
    lines+=['',
        'Tiêu chí cứu vãn: peg 0,98–1,02 USD liên tục ≥ 48 giờ, xử lý ≥95% yêu cầu rút mới cộng tồn đọng đầu cửa sổ 24 giờ, khớp ≥95% lệnh native đã gửi, hàng đợi không tăng kéo dài, Anchor/native còn hoạt động, quỹ còn, rồi vượt qua 7 ngày không giải ngân mới. Native fill ratio tính sau giới hạn vốn và tốc độ giao dịch của arbitrageurs; không đại diện toàn bộ nhu cầu đổi UST tiềm ẩn. Phép thử kéo dài giữ giá BTC cuối kỳ; đây là stress test, không phải lịch sử.','',
        '## 5. Cách trình bày và kết luận','',
        '1. Mở dữ liệu thật: tiền gửi Anchor, mất peg và nguồn cung LUNA.','2. Giải thích vòng phản hồi ABM ↔ tồn lượng/dòng chảy.','3. Trình bày sai số trong mẫu và ngoài mẫu trước khi nói về chính sách.','4. Chạy cùng seed với đối chứng không cứu trợ và chính sách, xem cả hàng đợi và quỹ; đối chiếu lịch sử riêng.','5. So sánh 20 seed, biên quỹ sớm/muộn và độ trễ.','6. Kết luận theo giới hạn của dữ liệu và độ khớp; không khẳng định một chính sách chắc chắn cứu được sự kiện thật.','',
        'Nguồn: Liu, Makarov & Schoar, *Anatomy of a Run: The Terra Luna Crash* và bộ dữ liệu tái lập; [JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf); [Terra Market](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html); [Binance public data](https://github.com/binance/binance-public-data).']
    lines+=['','## 6. Hướng cải thiện độ khớp','',
        'Bản v3 đã sửa quan sát nguồn cung theo cuối giờ, đo FIFO vốn ban đầu theo nhóm, tách Anchor khỏi native khi restart, tích phân thị trường một phút và tăng trọng số thời điểm mất peg. Lệnh native tối ưu lợi nhuận sau phí và trượt giá bán LUNA; quote và khớp lệnh dùng cùng đường giá trung bình tích phân (VWAP), vốn và tồn kho hữu hạn. Các nguồn và ablation nằm trong outputs/improvement. Nếu các gate còn thất bại, cần tiếp tục kiểm tra hành vi người giữ LUNA cũ, thanh khoản, chiến lược arbitrage và lịch mua Jump còn thiếu. Bộ chính sách mặc định dùng biên quỹ muộn; replay dùng biên sớm, nên chênh lệch bao gồm cả giả định thời điểm khả dụng.',
        'Audit JS Held ước lượng 785.501.572–825.615.759 UST cần để tạo 220.694.577 LUNA đã chuyển sang ví staking ngày 12/05; thiếu swap logs theo từng giao dịch nên chưa thể xác minh chính xác giờ đốt hoặc dùng khoảng này như một chuỗi điều khiển. Native swap tổng hợp đã bao gồm các ví quản trị, trong khi bản nhỏ hiện chỉ mô phỏng dòng arbitrage. Sai lệch về chủ sở hữu và LUNA giữ lại có thể ảnh hưởng độ khớp; xem outputs/improvement/GOVERNANCE_REDEMPTIONS_VI.md.']
    comparison=output/'improvement'/'COMPARISON_VI.md'
    evidence=output/'improvement'/'comparison.json'
    if comparison.exists() and evidence.exists():
        payload=json.loads(evidence.read_text(encoding='utf-8'))
        if payload.get('status')=='verified_parameters' and payload.get('current_engine_sha256')==current_engine:
            lines+=['','## 7. Đối chiếu với bản v2','',comparison.read_text(encoding='utf-8')]
    path=output/'REPORT_VI.md'; path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    metadata={'provenance':report_provenance(),
              'artifacts_sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                                  for name in ['REPORT_VI.md','historical_comparison.html']}}
    (output/'report_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return path
