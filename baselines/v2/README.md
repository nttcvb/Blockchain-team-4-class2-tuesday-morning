# Luna–UST: phòng thí nghiệm cadCAD + ABM + System Dynamics

Dashboard tiếng Việt cho bài nhóm môn học: đối chiếu khủng hoảng thật tháng 05/2022 và thử thay đổi chính sách trong giới hạn tài sản LFG/TFL.

Bản hiện tại đã có 140 lượt chạy và báo cáo sai số, nhưng **chưa đạt mục tiêu độ khớp toàn sự kiện**. Kết quả chính sách chỉ để khám phá cơ chế. [DEMO_VI.md](DEMO_VI.md) có kịch bản thuyết trình 8 phút.

## Mở dashboard

Trên máy hiện tại, mở PowerShell tại thư mục này và chạy:

```powershell
..\.venv\Scripts\python.exe -m streamlit run app.py
```

Mở `http://127.0.0.1:8501`. Hoặc chạy `Start.ps1`; script chọn môi trường đã có, không sửa Python hệ thống.

Máy khác: Python 3.11/3.12, tạo `.venv`, rồi cài `pip install -e ".[test]"`. Đặt bộ dữ liệu gốc cạnh dự án ở đường dẫn mặc định được mô tả trong `luna_sim/config.py`; có thể đặt biến `LUNA_SOURCE_DIR` trỏ đến thư mục có `data/` và `Datasets.md`.

## Chạy quy trình nghiên cứu

Thay `python` bằng `..\.venv\Scripts\python.exe` trên máy hiện tại.

```powershell
python -m luna_sim.cli prepare
python -m luna_sim.cli calibrate --generations 12 --popsize 4
python -m luna_sim.cli calibrate --split all --generations 10 --popsize 4
python -m luna_sim.cli run --scenario historical --deterministic
python -m luna_sim.cli suite --seeds 20
python -m luna_sim.cli sensitivity
python -m luna_sim.cli timestep-check
python -m luna_sim.cli diagnostics
python -m luna_sim.cli report
python -m luna_sim.cli audit
python -m pytest -q
```

`prepare` đọc Parquet của bộ tái lập, tải giá BTC chính thức Binance (kiểm tra SHA256), lưu báo cáo nguồn lực JS Held và kiểm tra các hạn mức. Các lần chạy sau hoạt động offline. Dữ liệu gốc không bị sửa.

Nếu bộ chạy nhiều seed bị gián đoạn, dùng `python -m luna_sim.cli suite --seeds 20 --resume`. Chỉ dùng lại kịch bản đã đủ seed khi mã engine và cấu hình khớp; các kịch bản chưa đủ seed chạy lại.

- `outputs/calibration/`: tham số, sai số trong/ngoài mẫu và chuỗi mô phỏng.
- `outputs/runs/`: cấu hình JSON, chuỗi kết quả CSV/Parquet, sổ giao dịch CSV, chỉ số JSON.
- `outputs/experiments/`: kết quả từng seed, trung vị, khoảng 5–95%, độ nhạy và bước thời gian.
- `outputs/REPORT_VI.md`: báo cáo và dàn ý trình bày bài nhóm.
- `outputs/historical_comparison.html`: biểu đồ tương tác, mở offline.
- `outputs/calibration/diagnostics.json`: đối chiếu riêng FTX, Curve/Binance và trước/sau mốc ngừng native.
- `outputs/REPRODUCIBILITY.json`: kiểm tra 140 lượt chạy, trần tài sản, checksum đầu vào và phiên bản thư viện.

## Cơ chế

ABM tạo hành vi người gửi: xác suất rút phụ thuộc tài sản trước khủng hoảng, mất peg, lượng rút gần đây, giá LUNA và hàng đợi. Độ trễ quan sát khác nhau theo quy mô và đặc điểm ví. Top 20 ví giữ riêng; phần còn lại lấy mẫu có trọng số và giữ tổng tài sản từng nhóm. Các ví A/B khởi phát là chuỗi hành động ngoại sinh có điều kiện, bị loại khỏi quyết định rút tự sinh trong cùng cửa sổ. Không dùng `full_maxusd` hoặc tổn thất thực tế làm đầu vào quyết định.

System Dynamics cập nhật tiền gửi/quyền đòi Anchor, thanh khoản, dư nợ, quỹ lãi, tồn kho USD/UST/LUNA, nguồn cung và dự trữ cứu trợ. Tiền gửi là **quyền đòi**, không cộng thêm vào nguồn cung token. Rút chỉ chuyển UST từ Anchor sang ví; native swap mới đốt UST/phát hành LUNA. Mua UST để hỗ trợ peg không tự đốt UST.

Giá do đường cầu ngược tổng hợp và lệnh mua/bán tạo ra. Độ sâu được hiệu chỉnh; LUNA chịu ảnh hưởng bán token mới phát hành và điều kiện thị trường BTC. Các đường giá thực tế chỉ là mục tiêu, không được ép vào bước mô phỏng. Virtual pool sử dụng bất biến constant-product ở đơn vị USD quy đổi; không dùng đồng nhất USDT/SDR ở tầng blockchain. Phí oracle/spread và thời gian reset pool được xấp xỉ theo bước thời gian.

Sáu PSUB cadCAD: quan sát → cứu trợ → quyết định → Anchor → thị trường/native swap → kế toán. Bộ chạy nhanh dùng **đúng cùng sáu hàm** để hiệu chỉnh, được kiểm tra khớp cadCAD. Dashboard và thí nghiệm báo cáo chạy cadCAD.

## Chính sách và giới hạn

Mua UST, bổ sung thanh khoản UST, đổi tham số native swap, hoặc giới hạn rút Anchor tạm thời. Chọn ngưỡng giá/thời điểm, độ trễ 15/60/360 phút và thời hạn. Chính sách **thay thế** cứu trợ lịch sử; không cộng tiền cứu trợ hai lần.

Dự trữ LFG: 80.394 BTC ban đầu, tối đa 80.081 BTC được triển khai, 313 BTC giữ lại; 49.837.261 USD stablecoin. TFL: tối đa 613.616.889 USD đóng góp ròng. Khoản TFL đó là giới hạn chi đã ghi nhận, **không chứng minh toàn bộ khả dụng từ đầu**. Tiền chuyển LFG/TFL/Jump được ghi nhận theo chủ cuối cùng, không tạo nguồn lực mới. BTC được đổi theo giá tại bước hiện tại, trừ phí và trượt giá.

Khoảng giải ngân thiếu thông tin được lưu trong `data/sources.json`. Biên muộn là mặc định; biên sớm là giả định thuận lợi. Tài sản BNB/AVAX không được dùng để tăng hạn mức cứu trợ ngoài khoản đã triển khai lịch sử. UST/LUNA nắm giữ không được coi là tiền USD bảo chứng.

Hỗ trợ thanh khoản là vốn cam kết vào bộ phận tạo lập thị trường; nó tăng tiền xử lý giao dịch và độ sâu trong thời hạn chính sách. Không hoàn lại vốn mặc định khi hết hạn. LP có rủi ro mất vốn; kết quả “support_spent” gồm cả cam kết LP. Hạn chế rút giữ nguyên quyền đòi và hàng đợi, không xóa nghĩa vụ.

## Hiệu chỉnh và diễn giải

Đặc tả công thức, tác nhân, luồng tài sản và giới hạn ở [MODEL_SPEC.md](MODEL_SPEC.md). Dashboard mặc định dùng bộ khớp toàn sự kiện nếu có: đây là trình diễn trong mẫu, không gọi là kiểm định ngoài mẫu. Bộ train riêng vẫn được công bố. Các chính sách giữ nguyên tham số, không hiệu chỉnh lại để tạo kết quả thuận lợi.

Tham số dùng dữ liệu 06–10/05; kiểm định 11–15/05. Tiêu chí đặt trước: MAE UST ≤0,05 USD; NRMSE tiền gửi ≤10%; RMSE log₁₀ LUNA/nguồn cung ≤0,5; sai lệch mất peg ≤6h; MAE nhóm ≤15 điểm %. Dashboard công bố cả các ngưỡng thất bại.

Nhóm so sánh là **phần vốn trước khủng hoảng còn lại sau rút**, theo quy tắc FIFO; tiền gửi thêm không làm phồng mẫu số. Vì dữ liệu ví không bao gồm toàn bộ chuyển tài sản, chỉ số này khác biểu đồ aUST balance trong bài gốc.

Thành công: peg 0,98–1,02 trong 48h; phục vụ rút/đổi ≥95% từng cửa sổ 24h; hàng đợi không tăng; quỹ không hết; đạt điều kiện cả 7 ngày không hỗ trợ mới. Stress tail giữ BTC cuối kỳ, không nhập giá UST/LUNA tương lai.

Các khoảng “5–95%” là biến động seed trong một bộ tham số, **không bao trùm bất định cấu trúc**. Xem thêm phân tích độ nhạy về hành vi, thanh khoản, lịch quỹ, độ trễ và bước 5/15 phút. Nếu chưa đạt ngưỡng ngoài mẫu, kết quả phản thực tế là minh họa khám phá, không là chứng minh lịch sử có thể được cứu.

Không mô phỏng đầy đủ CEX/Curve, tài sản thế chấp từng khoản vay hoặc validator. Lịch tham chiếu dùng thay đổi capacity xấp xỉ ngày 11/05 và mốc native swap cuối khoảng 02:00 UTC 13/05; thiếu giao dịch Jump và vốn lưu động TFL nên có thể còn ý định mua không thực hiện, được báo cáo riêng. Không ép các mốc ngừng lịch sử lên phản thực tế.

## Nguồn và quyền sử dụng

Liu, Makarov & Schoar, *Anatomy of a Run: The Terra Luna Crash*. Bộ dữ liệu gốc ghi CC-BY-4.0 cho dữ liệu/biểu đồ và MIT cho mã; các trích xuất bên thứ ba có điều khoản riêng. Dự án đọc dữ liệu từ bản gốc và giữ ghi nhận tác giả/provider; xem LICENSE gốc.

- [Báo cáo JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf)
- [Terra Market module](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html)
- [Binance public data](https://github.com/binance/binance-public-data)
- [cadCAD documentation](https://github.com/cadCAD-org/cadCAD/blob/master/documentation/README.md)
