# Đối chiếu bàn giao với plan đã chọn

Ngày kiểm tra: 09/10/2026. Phạm vi đối chiếu: `PLAN_APPROVED.md`, giữ nguyên mô hình môn học, quy trình kiểm chứng và dashboard thử cứu trợ sau khởi phát. Đây là kiểm tra đầu ra triển khai; không phải xác nhận độ đúng lịch sử của mô hình.

Hiệu chỉnh v2 đã hoàn tất, đưa trực tiếp khối lượng và phí native vào hàm mục tiêu. Toàn bộ 140 lượt thí nghiệm, độ nhạy, kiểm tra bước thời gian và báo cáo đã được chạy lại với bộ tham số này.

## Các bước và đầu ra

| Yêu cầu | Bằng chứng đã đọc/chạy | Kết quả |
|---|---|---|
| Dự án riêng, giữ nguyên nguồn | `luna-ust-sim`; các hàm `read_source` chỉ đọc nguồn, toàn bộ xuất ở dự án mới | Đã triển khai |
| UTC, token/microtoken, snapshot và aUST | `data/processed/quality_report.json`, `initial_facts.json`, `historical_15min.parquet`; test đơn vị/khởi tạo | 959 bước lịch sử; không thiếu bốn mục tiêu chính |
| Bảng nguồn lực và mốc sự kiện | `data/sources.json`, `data/processed/event_timeline.csv`, PDF JS Held và BTC cache | Có nguồn, hạn mức, khoảng sớm/muộn và nhãn xấp xỉ |
| 1.000 người gửi, 20 arbitrage; sáu nhóm và top20 | `data.py`, `context/initialize`, `population.parquet`; test tổng vốn và số tác nhân | Đã triển khai; arbitrage chia vốn, dùng quote/độ trễ chung xấp xỉ |
| Khác biệt quy mô/quan sát trễ, logistic và lây lan | `decisions`; wealth trước sự kiện, outflow giờ, giá/queue trễ | Đã triển khai; không dựng mạng ví giả |
| System Dynamics và vốn hữu hạn | `anchor`, `markets`, `spend`, `invariants`; ledger từng kịch bản | Tồn lượng có chủ sở hữu; rút/mua không tạo token/USD |
| Virtual pool, oracle, mint/burn | `markets`, kiểm tra native mint/burn; đối chiếu khối lượng/phí | Có cơ chế tổng hợp, chưa tái lập SDR/block chính xác |
| Sáu PSUB cadCAD có thứ tự | `BLOCKS`, `simulate` và parity tests ngẫu nhiên/kỳ vọng | cadCAD 0.5.3; runner hiệu chỉnh dùng cùng hàm |
| ScenarioConfig, PolicyConfig, simulate và xuất | `config.py`, `engine.py`, `export_run`; 7 thư mục seed42 đủ JSON/CSV/Parquet/ledger | Đã chạy và xuất thực tế |
| Replay và phản thực tế thay thế | `rescue`, `observation`; test dừng lịch sử không áp vào phản thực tế | Đã tách; các mốc replay còn là xấp xỉ |
| 4 chính sách và kết hợp | `app.py`, `scenario_presets`; UI test bốn điều khiển, chia ngân sách | Có mua UST, thanh khoản, native và gate |
| Trigger 0,99/hai bước, thời gian, delay và thời hạn | `PolicyConfig/observation`; form và test delay | Có delay 15/60/360 phút; chỉ dùng trạng thái đã có |
| Hạn mức LFG/TFL, BTC phải bán và không đếm trùng | `sources.json`, `spend`, funding release; test BTC/phí/ownership; 140-run audit | BTC ≤80.081, TFL ≤613.616.889, quỹ không âm |
| Quỹ Anchor riêng, tiền mua không đốt UST | `anchor/initialize`, zero-budget và buy-not-burn tests | Đã kiểm tra |
| Hiệu chỉnh 06–10/05, kiểm tra 11–15/05 và bộ full-fit riêng | `parameters*.json`, `report_train/all.json`, `trajectory_train/all.parquet` | Đã chạy; tham số đóng băng giữa các chính sách |
| Giá, rút và nguồn cung không bị ép theo lịch sử | Engine context không nhập chuỗi mục tiêu; BTC và A/B là biên ngoại sinh có công bố | Đã kiểm tra mã; A/B là thí nghiệm có điều kiện |
| Không dùng full_maxusd hoặc chuyển aUST như rút | Khởi tạo trước sự kiện trong `data.py`; targets phân loại deposit/withdraw | Đã triển khai |
| FTX riêng; Curve/Binance 07/05; trước/sau gián đoạn | `diagnostics.json`, `cross_venue_15min.parquet`, report mục đối chiếu bổ sung | Đã chạy; không gộp quote 3Crv vào giá USD |
| Ngưỡng sai số đặt trước và báo thất bại | Bảng train/validation/full-fit, JSON gates và cảnh báo dashboard | **Ngưỡng độ khớp chưa đạt**; plan cho phép báo thất bại và giảm độ chắc chắn |
| 20 seed/kịch bản, seed chung, trung vị và khoảng | `runs.csv` 140 dòng, `summary.csv` 7 dòng, `bands.parquet` 21 nhóm kịch bản/quantile | Mỗi kịch bản có seed42–61, không trùng; tất cả engine cadcad |
| Độ nhạy và 5/15 phút | `sensitivity.csv` 22 cấu hình, `timestep_check.json` | Đã chạy; giá LUNA nhạy mạnh với bước thời gian |
| Peg + phục vụ rút/native + quỹ + 7 ngày không hỗ trợ | `evaluate`, tiêu chí rolling24h, queue, native_open; 7 traces seed42 và 140-run audit | Đã kiểm tra; 0/140 lượt đạt tiêu chí |
| Không nhầm gate làm giảm rút với cứu vãn | Giữ quyền đòi và queue; test gate; tiêu chí dựa cả khả năng phục vụ | Đã kiểm tra |
| Chính sách phi tiền tệ cũng có thể đủ điều kiện | Test chuỗi tổng hợp có native policy hoạt động, quỹ còn và tail bền, chiUSD=0 | Đã kiểm tra; không bắt buộc chi tiền để được phân loại |
| Dashboard 3 màn hình, chỉ chạy chính sách khi bấm | `app.py`; AppTest; browser localhost chạy mua UST và đọc bảng kết quả | Đã xác nhận runtime |
| Quỹ/queue/service/loss, export và tái lập | Cards, biểu đồ, ledger, nút tải; file exports; `REPRODUCIBILITY.json` | Đã có; cùng tham số/seed/horizon trong đối chiếu UI |
| Demo, hướng dẫn, báo cáo và kết luận bài nhóm | `Start.ps1`, `README.md`, `DEMO_VI.md`, `REPORT_VI.md`, offline HTML, ảnh dashboard | Đã tạo và kiểm tra |

## Kiểm thử và lệnh kiểm chứng

- Bộ kiểm thử mô hình/dashboard cuối: 18 passed trong `outputs/test-results.xml`, không lỗi/skip. Kiểm tra bảo toàn, không âm, caps, zero-budget, delay, mint/burn, quyền đòi, chia quỹ khả dụng 70/30 khi ngân sách ràng buộc và parity cadCAD; gồm hai kiểm thử dashboard với nhãn cuối.
- `python -m luna_sim.cli audit`: xác nhận 140 lượt chạy, 20 seed mỗi kịch bản, engine hash hiện hành, hạn mức tài sản và 7 tail seed42 có 672 bước không giải ngân mới.
- `prepare`, `calibrate --split train/all`, `suite --seeds 20`, `sensitivity`, `timestep-check`, `diagnostics`, `report` đã tạo đầu ra tương ứng. Cơ chế `suite --resume` từng xác minh checkpoint sau gián đoạn; bộ kết quả bàn giao được chạy mới đủ 7 kịch bản × 20 seed sau hiệu chỉnh v2.
- Browser: đã đọc ba tab, chạy chính sách mua UST, thấy phân loại/chi phí/quỹ/service và nút xuất; bảng 7×20 seed được chụp tại `outputs/dashboard-proof.jpg`.

## Kết luận kiểm tra

Các đầu ra triển khai và quy trình thí nghiệm của plan đã có bằng chứng chạy. **Độ khớp toàn sự kiện chưa đạt**: MAE UST 0,0909 USD, NRMSE tiền gửi 0,1113, RMSE log giá LUNA 0,8613, RMSE log nguồn cung 0,4196, MAE nhóm 0,1448, onset lệch 47,25 giờ. Khối lượng native mô phỏng 6,499 tỷ UST so với 7,491 tỷ UST quan sát; NRMSE theo ngày 0,3031 và MAE phí 0,0574. Không được chuyển “có dashboard và kiểm thử qua” thành “mô hình sát lịch sử”.

Nguồn Jump thiếu lịch giao dịch, việc đóng Anchor cùng native và chiến lược/độ trễ arbitrage tổng hợp là các giới hạn thật đã công bố. USD của phía đối ứng thị trường là giả định hữu hạn, không phải tài sản LFG/TFL hay dữ liệu thị trường xác minh. Nhóm chỉ có thể trình bày cơ chế, sai số và các kết quả chính sách có điều kiện; chưa có bằng chứng nhân quả để kết luận lịch sử có thể hoặc không thể được cứu.
