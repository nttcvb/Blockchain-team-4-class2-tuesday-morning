# Luna–UST: phòng thí nghiệm cadCAD + ABM + System Dynamics

Mô hình nhỏ cadCAD + ABM + System Dynamics để tái hiện vụ sụp đổ UST/LUNA tháng 05/2022 và đối chiếu với dữ liệu thật. Theo yêu cầu hiện hành, việc cải thiện mô hình đã dừng; dashboard trình bày bản tốt nhất đã hoàn tất và dữ liệu đã lưu.

[Hướng dẫn Word cho người mới](docs/Huong_dan_mo_hinh_Luna_UST.docx) gồm 14 trang và 10 hình, ưu tiên sơ đồ hoạt động của hệ thống, quyết định của tác nhân, dòng tài sản và vòng phản hồi. Mỗi sơ đồ phân biệt agent, trạng thái, hành động, cơ chế và đầu vào ngoại sinh; các bảng định nghĩa nêu đơn vị, ý nghĩa và cách cập nhật trạng thái. Không cần biết cadCAD để đọc tài liệu.

Bản được chọn là v4 toàn sự kiện, run `20261011T071942831158Z_all`, objective **6,06007483**. Đây là bản đã hoàn tất có sai số tổng hợp thấp nhất trong các kết quả tương thích với nguồn hiện hành, đạt **1/6 ngưỡng lịch sử**. Fit toàn sự kiện là tái hiện trong mẫu; tùy chọn train 06–10/05 vẫn được giữ để đối chiếu với giai đoạn 11–15/05. Không cần hoàn thành ensemble đang đề xuất để mở hoặc sử dụng dashboard.

Nguồn v4 bỏ capacity step chưa có bằng chứng thực thi và cố định đồng hồ quan sát LUNA 15 phút. Kết quả và hạn chế ở [báo cáo tái hiện](outputs/reconstruction/RECONSTRUCTION_VI.md) và [WORK_STATUS_VI.md](outputs/improvement/WORK_STATUS_VI.md). [IMPROVEMENT_PLAN_VI.md](IMPROVEMENT_PLAN_VI.md) cùng các nội dung nghiên cứu trong `outputs/improvement/` được giữ làm lịch sử công việc. Các archive v2/v3 và checkpoint bị gián đoạn không phải kết quả của nguồn hiện hành.

## Mở dashboard

Trên máy hiện tại, mở PowerShell tại thư mục này và chạy:

```powershell
..\.venv\Scripts\python.exe -m streamlit run app.py
```

Mở `http://127.0.0.1:8501`. Hoặc chạy `Start.ps1`; script chọn môi trường đã có, không sửa Python hệ thống.

Dashboard mặc định tải bản v4 đã chọn từ `outputs/calibration/trajectory_all.parquet`, `report_all.json`, `config_all.json` và `ledger_all.csv`. Mở dashboard không chạy simulator hoặc optimizer. Biểu đồ đối chiếu mô phỏng với dữ liệu thật, công bố các ngưỡng chưa đạt và cho phép xem bản train để so sánh. Các kết quả giữ nguyên; bộ ensemble riêng chưa fit không được dùng để trình bày.

Máy khác: Python 3.11/3.12, tạo `.venv`, rồi cài `pip install -e ".[test]"`. Đặt bộ dữ liệu gốc cạnh dự án ở đường dẫn mặc định được mô tả trong `luna_sim/config.py`; có thể đặt biến `LUNA_SOURCE_DIR` trỏ đến thư mục có `data/` và `Datasets.md`.

## Chạy quy trình nghiên cứu

Thay `python` bằng `..\.venv\Scripts\python.exe` trên máy hiện tại.

```powershell
python -m luna_sim.cli prepare
python -m luna_sim.cli calibrate --split train --generations 12 --popsize 4 --workers 2 --refinement-iterations 160
python -m luna_sim.cli calibrate --split all --generations 12 --popsize 4 --workers 2 --refinement-iterations 160
python -c "from luna_sim.improvements import run_comparison; run_comparison()"
python -m luna_sim.cli run --scenario historical --deterministic --stress-days 0
python -m luna_sim.cli reconstruction-check --seeds 20
python -m luna_sim.cli diagnostics
python -m luna_sim.cli reconstruction-report
python -m pytest -q
```

`prepare` đọc Parquet của bộ tái lập, tải giá BTC chính thức Binance (kiểm tra SHA256), lưu báo cáo nguồn lực JS Held và kiểm tra các hạn mức. Các lần chạy sau hoạt động offline. Dữ liệu gốc không bị sửa. `reconstruction-report` chỉ xuất báo cáo khi cả fit train và full-fit đã hoàn tất và khớp mã/dữ liệu hiện tại. `reconstruction-check` kiểm tra nhiều seed cadCAD lịch sử và bước 5/15 phút, ghi tồn kho/sổ cái, các ngưỡng thất bại và checksum kết quả vào `outputs/reconstruction/validation/`.

Trước khi chạy lại một job, kiểm tra trạng thái và tiến trình thực tế. `reconstruction-check` hiện chưa hỗ trợ resume; không dùng bộ `suite` cũ để thay thế audit/manifest của reconstruction. Mỗi lần kiểm tra phải giữ nguyên nguồn và bộ tham số đến khi terminal.

Hiệu chỉnh tìm kiếm rộng rồi refinement, ghi checkpoint theo tên tham số và fingerprint mã/dữ liệu. Dùng `--warm-start outputs/calibration/checkpoint_all_v3.json` để lấy tham số từ lần trước; tham số được đánh giá lại, không mang theo điểm số cũ. Train chỉ tối ưu 06–10/05; nghiệm cuối chạy toàn sự kiện để kiểm tra 11–15/05. `calibration_status_*.json` ghi rõ đang chạy, thất bại hoặc hoàn tất.

- `outputs/calibration/`: tham số, sai số trong/ngoài mẫu và chuỗi mô phỏng.
- `outputs/reconstruction/`: báo cáo tiếng Việt, biểu đồ tương tác offline và manifest kiểm tra nguồn của bản tái hiện lịch sử.
- `outputs/improvement/`: audit dữ liệu, so sánh với v2 trên cùng định nghĩa quan sát và ablation cơ chế.
- `baselines/v2/`: mã và kết quả v2 được giữ nguyên để đối chứng.
- `baselines/v3_frozen_20261011T010500Z/`: nguồn, dữ liệu và kết quả v3 với manifest148 tệp.
- `outputs/calibration/diagnostics.json`: đối chiếu riêng FTX, Curve/Binance và trước/sau mốc ngừng native.
- `outputs/cleanup/`: nhật ký dọn dẹp, kiểm tra bản ZIP trùng dữ liệu và xác nhận các tệp cần giữ nguyên vẹn. Các kết quả thí nghiệm cũ, lần chạy không được chọn và tệp tạm đã được xoá; dữ liệu gốc, mã mô hình, bản đối chứng và kết quả hiện hành vẫn được giữ.

Các lệnh nghiên cứu có thể tạo lại `outputs/runs/` và `outputs/experiments/`; hai thư mục này không còn là kết quả được lưu sẵn sau đợt dọn dẹp.

## Cơ chế

ABM tạo hành vi người gửi: xác suất rút phụ thuộc tài sản trước khủng hoảng, mất peg, lượng rút gần đây, giá LUNA và hàng đợi. Độ trễ quan sát khác nhau theo quy mô và đặc điểm ví. Top 20 ví giữ riêng; phần còn lại lấy mẫu có trọng số và giữ tổng tài sản từng nhóm. Các ví A/B khởi phát là chuỗi hành động ngoại sinh có điều kiện, bị loại khỏi quyết định rút tự sinh trong cùng cửa sổ. Không dùng `full_maxusd` hoặc tổn thất thực tế làm đầu vào quyết định.

System Dynamics cập nhật tiền gửi/quyền đòi Anchor, thanh khoản, dư nợ, quỹ lãi, tồn kho USD/UST/LUNA, nguồn cung và dự trữ cứu trợ. Tiền gửi là **quyền đòi**, không cộng thêm vào nguồn cung token. Rút chỉ chuyển UST từ Anchor sang ví; native swap mới đốt UST/phát hành LUNA. Mua UST để hỗ trợ peg không tự đốt UST.

Giá do đường cầu ngược tổng hợp và lệnh mua/bán tạo ra. Độ sâu được hiệu chỉnh; LUNA chịu ảnh hưởng bán token mới phát hành và điều kiện thị trường BTC. Các đường giá thực tế chỉ là mục tiêu, không được ép vào bước mô phỏng. Virtual pool sử dụng bất biến constant-product ở đơn vị USD quy đổi; không dùng đồng nhất USDT/SDR ở tầng blockchain. Phí oracle/spread và phục hồi pool được tích phân theo phút; oracle trễ dùng giá mô phỏng phút trước.

Sáu PSUB cadCAD: quan sát → cứu trợ → quyết định → Anchor → thị trường/native swap → kế toán. Bộ chạy nhanh dùng **đúng cùng sáu hàm** để hiệu chỉnh, được kiểm tra khớp cadCAD. Các lần mô phỏng dùng cadCAD; dashboard hiện tại trình bày kết quả đã lưu.

## Cứu trợ đã xảy ra và giới hạn

Nhánh historical mô phỏng các ý định mua UST/LUNA và thời điểm tài sản LFG/TFL khả dụng theo bằng chứng. Các tính năng chính sách cũ vẫn còn trong mã, nhưng không được chạy hoặc dùng làm tiêu chí hoàn thành của phạm vi tái hiện hiện hành.

Dự trữ LFG: 80.394 BTC ban đầu, tối đa 80.081 BTC được triển khai, 313 BTC giữ lại; 49.837.261 USD stablecoin. TFL: tối đa 613.616.889 USD đóng góp ròng. Khoản TFL đó là giới hạn chi đã ghi nhận, **không chứng minh toàn bộ khả dụng từ đầu**. Tiền chuyển LFG/TFL/Jump được ghi nhận theo chủ cuối cùng, không tạo nguồn lực mới. BTC được đổi theo giá tại bước hiện tại, trừ phí và trượt giá.

Khoảng giải ngân thiếu thông tin được lưu trong `data/sources.json`. Biên muộn là mặc định; biên sớm là giả định thuận lợi. Tài sản BNB/AVAX không được dùng để tăng hạn mức cứu trợ ngoài khoản đã triển khai lịch sử. UST/LUNA nắm giữ không được coi là tiền USD bảo chứng.

Hỗ trợ thanh khoản là vốn cam kết vào bộ phận tạo lập thị trường; nó tăng tiền xử lý giao dịch và độ sâu trong thời hạn chính sách. Không hoàn lại vốn mặc định khi hết hạn. LP có rủi ro mất vốn; kết quả “support_spent” gồm cả cam kết LP. Hạn chế rút giữ nguyên quyền đòi và hàng đợi, không xóa nghĩa vụ.

## Hiệu chỉnh và diễn giải

Đặc tả công thức, tác nhân, luồng tài sản và giới hạn ở [MODEL_SPEC.md](MODEL_SPEC.md). Dashboard mặc định dùng bộ khớp toàn sự kiện nếu có: đây là trình diễn trong mẫu, không gọi là kiểm định ngoài mẫu. Bộ train riêng vẫn được công bố. Các chính sách giữ nguyên tham số, không hiệu chỉnh lại để tạo kết quả thuận lợi.

Tham số dùng dữ liệu 06–10/05; kiểm định 11–15/05. Tiêu chí đặt trước: MAE UST ≤0,05 USD; NRMSE tiền gửi ≤10%; RMSE log₁₀ LUNA/nguồn cung ≤0,5; sai lệch mất peg ≤6h; MAE nhóm ≤15 điểm %. Dashboard công bố cả các ngưỡng thất bại.

Nhóm so sánh là **phần vốn trước khủng hoảng còn lại sau rút**, theo quy tắc FIFO; tiền gửi thêm không làm phồng mẫu số. Vì dữ liệu ví không bao gồm toàn bộ chuyển tài sản, chỉ số này khác biểu đồ aUST balance trong bài gốc.

Thành công trong mô hình: peg 0,98–1,02 trong 48h; xử lý ≥95% yêu cầu rút mới cộng tồn đọng đầu mỗi cửa sổ 24h và ≥95% lệnh native đã gửi; Anchor/native hoạt động; hàng đợi không tăng; quỹ còn; đạt điều kiện cả 7 ngày không hỗ trợ mới. Lệnh native tính sau giới hạn vốn và tốc độ giao dịch, không đo toàn bộ nhu cầu tiềm ẩn. Stress tail giữ BTC cuối kỳ, không nhập giá UST/LUNA tương lai.

Đối chứng chính sách là `no_rescue` cùng tham số, seed, lịch quỹ và thời hạn. Replay lịch sử có biên quỹ sớm và gián đoạn chain nên không dùng riêng chênh lệch với replay để quy tác động cho chính sách.

Các khoảng “5–95%” là biến động seed trong một bộ tham số, **không bao trùm bất định cấu trúc**. Xem thêm phân tích độ nhạy về hành vi, thanh khoản, lịch quỹ, độ trễ và bước 5/15 phút. Nếu chưa đạt ngưỡng ngoài mẫu, kết quả phản thực tế là minh họa khám phá, không là chứng minh lịch sử có thể được cứu.

Không mô phỏng đầy đủ CEX/Curve, tài sản thế chấp từng khoản vay hoặc validator. Capacity step11/05 cũ đã bỏ; governance1164 có voting end18/05, ngoài cửa sổ. Điều này không loại trừ mọi thay đổi emergency chưa có hồ sơ. Mốc native swap cuối khoảng02:00UTC13/05 là xấp xỉ; thiếu giao dịch Jump và vốn lưu động TFL nên có thể còn ý định mua không thực hiện, được báo cáo riêng. Không ép các mốc ngừng lịch sử lên phản thực tế.

## Nguồn và quyền sử dụng

Liu, Makarov & Schoar, *Anatomy of a Run: The Terra Luna Crash*. Bộ dữ liệu gốc ghi CC-BY-4.0 cho dữ liệu/biểu đồ và MIT cho mã; các trích xuất bên thứ ba có điều khoản riêng. Dự án đọc dữ liệu từ bản gốc và giữ ghi nhận tác giả/provider; xem LICENSE gốc.

- [Báo cáo JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf)
- [Terra Market module](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html)
- [Binance public data](https://github.com/binance/binance-public-data)
- [cadCAD documentation](https://github.com/cadCAD-org/cadCAD/blob/master/documentation/README.md)
