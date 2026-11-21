# So sánh cải thiện mô hình

Trạng thái: **provisional_ablation**. Tạo lúc 2026-10-10T02:02:44.926629+00:00.

Các hàng kiểm soát dùng cùng dữ liệu hiện tại, seed 42, 1.000 tác nhân, deterministic, quỹ early và cửa sổ 06–15/05. V2 rebased giữ mã/tham số cũ nhưng dùng lớp quan sát đã sửa; vì vậy nó tách sửa định nghĩa dữ liệu khỏi sửa cơ chế. Full-fit vẫn là kết quả trong mẫu.

| Chỉ số (càng thấp càng tốt) | Ngưỡng | V2, dữ liệu đã sửa | Engine mới, tham số cũ |
|---|---:|---:|---:|
| MAE giá UST, USD | 0.05 | 0.088052 · chưa đạt | 0.126125 · chưa đạt |
| NRMSE tiền gửi Anchor | 0.1 | 0.111286 · chưa đạt | 0.118317 · chưa đạt |
| RMSE log10 giá LUNA | 0.5 | 0.925433 · chưa đạt | 1.37439 · chưa đạt |
| RMSE log10 nguồn cung LUNA | 0.5 | 0.610703 · chưa đạt | 1.03364 · chưa đạt |
| MAE nhóm lớn nhất | 0.15 | 0.135462 · đạt | 0.152857 · chưa đạt |
| Sai lệch onset, giờ | 6 | 47.25 · chưa đạt | 45.25 · chưa đạt |
| NRMSE native theo ngày | chẩn đoán | 0.302699 | 0.0866562 |
| MAE phí native | chẩn đoán | 0.0575166 | 0.0683137 |

Giá trị V2 đã công bố được lưu riêng với định nghĩa quan sát cũ; không dùng hàng đó để đếm cải thiện:

| Chỉ số | V2 gốc | V2 dùng dữ liệu hiện tại |
|---|---:|---:|
| MAE giá UST, USD | 0.0908885 | 0.088052 |
| NRMSE tiền gửi Anchor | 0.111296 | 0.111286 |
| RMSE log10 giá LUNA | 0.861339 | 0.925433 |
| RMSE log10 nguồn cung LUNA | 0.419583 | 0.610703 |
| MAE nhóm lớn nhất | 0.144827 | 0.135462 |
| Sai lệch onset, giờ | 47.25 | 47.25 |
| NRMSE native theo ngày | 0.303074 | 0.302699 |
| MAE phí native | 0.0574063 | 0.0575166 |

Đối chiếu mỗi cơ chế và mỗi checkpoint với V2 rebased:
- Engine mới, tham số cũ: 2 sai số giảm, 6 tăng, 0 không đổi; đạt 0/6 gate lịch sử.

Nếu trạng thái provisional, báo cáo chưa chứng minh bộ tham số đã được hiệu chỉnh cho mã hiện tại. Mỗi trajectory, engine, bộ tham số và đầu vào có fingerprint trong comparison.json. Không kết luận chính sách cứu được lịch sử chỉ từ giảm sai số hoặc từ việc test phần mềm đạt.
