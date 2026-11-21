# Đối chiếu holdout của lần hiệu chỉnh train đã sửa

Cập nhật 2026-10-10T14:54:26.612397+00:00. Tất cả thời điểm sự kiện bên dưới là UTC.

Bộ train hiện tại đạt 6/6 ngưỡng trước 11/5 nhưng chỉ 2/6 trên 11–15/5. Sai lệch chính là sụp LUNA quá sớm và phát hành quá mức; không phải thiếu UST hoặc USD ở sổ thị trường. Checkpoint toàn sự kiện cải thiện mạnh độ lớn sai số LUNA/cung, nhưng chuyển sang sụp muộn và cạn UST có thể đem đốt. Chưa có bằng chứng tái hiện đạt yêu cầu.

## 1. Danh tính đầu ra và cách kiểm tra

- Run train: `20261010T142316556295Z_train`; 266 lần đánh giá, objective 1.480936636964. `audit_calibration('train')` được chạy lại và xác nhận 959 bước, 479 bước hiệu chỉnh, metric/sổ cái/archive trùng khớp.
- Optimizer train dừng khi hết số vòng đã đặt; cả broad search và refinement ghi `success=false`, `Maximum number of iterations has been exceeded.` Hoàn tất chạy không đồng nghĩa đã hội tụ tối ưu.
- Replay fast xác định có quan sát quote từng phút trong một tiến trình riêng đã khớp toàn bộ quỹ đạo cadCAD train lưu sẵn (`rtol=1e-12`, `atol=1e-5`). Chỉ quan sát hàm thuần và trạng thái trước/sau; không đổi dữ liệu, tham số, core hoặc artifact hiệu chỉnh.
- Engine SHA-256: `0a89a9e690c7998d8fadaa1756466b6195b67219483320403672a441cd95f7ea`.
- Train parameter SHA-256: `9ac14ce4b52e9bf21c934789d99661177ae01343b3b2a31995ba09ce3b847f24`.
- Train report SHA-256: `a4c4966b29b1fad04fac1ca71698400cdad3cd45f23281bf797b6c9af574852d`.
- Train trajectory SHA-256: `b8883efbb9221ba41d4ee365d265d350b77006cca1a370b2fb1bd67028af4c2e`.
- Train ledger SHA-256: `c3c6d69cb9d81e4f1ef1e345570d811191b9bf08ee2cd474d964faeb988e4431`.
- Target toàn sự kiện SHA-256: `89e7a53d8d795cb48706657306144ee54e4306d667265520127cb31a3d59e4a9`; group SHA-256: `c606efc0cece8a608a4c1db7838854340069b37787da061d4c86f0c4a73f9865`. Nhóm chỉ được chấm đến bucket 14/5 00:00, tương ứng nhật ký cuối 13/5 23:59:39; holdout có 289 quan sát mỗi nhóm, không kéo dài sang phần thiếu dữ liệu.

## 2. Mốc sai lệch và mức độ

| Chỉ số | Train, trước 11/5 | Giữ tham số train, 11–15/5 | Checkpoint all trên 11–15/5 | Checkpoint all, toàn sự kiện |
|---|---:|---:|---:|---:|
| MAE UST | 0.021462 | 0.373431 | 0.199862 | 0.108195 |
| Anchor NRMSE | 0.083013 | 0.068412 | 0.068978 | 0.120201 |
| LUNA log RMSE | 0.072424 | 9.144414 | 1.665838 | 1.181266 |
| Cung LUNA log RMSE | 0.002396 | 8.500120 | 0.989621 | 0.700134 |
| Nhóm MAE lớn nhất | 0.070716 | 0.198077 | 0.202912 | 0.149765 |
| Lệch mất peg / giờ | 0.000000 | 0.000000 | 0.750000 | 0.750000 |

Giá/cung dùng RMSE log10. Mốc sai lệch từng điểm dưới đây là `abs(log10(mô phỏng/quan sát)) > 0.5`, tức lệch hơn hệ số 3.162; đây không phải gate RMSE của toàn mẫu.

| Quỹ đạo | Đại lượng | Điểm đầu vượt 0.5 log | Đầu tiên đủ 4 bucket liên tiếp | Prefix RMSE holdout đầu vượt 0.5 |
|---|---|---|---|---|
| Train giữ tham số | Giá LUNA | 11/05 00:00 | 11/05 00:45 | 11/05 00:00 |
| Train giữ tham số | Cung LUNA | 11/05 01:00 | 11/05 01:45 | 11/05 01:00 |
| Checkpoint all | Giá LUNA | 11/05 03:30 | 11/05 05:00 | 11/05 06:00 |
| Checkpoint all | Cung LUNA | 12/05 01:00 | 12/05 01:45 | 12/05 14:00 |

Ở train, LUNA chạm sàn 1e-12 USD lúc **11/5 01:00**. Tại chính bucket đó, quan sát LUNA là **16.504982 USD**; cung mô phỏng **107.988 tỷ LUNA** so với **0.804346 tỷ** quan sát. Đến 06:00 cung mô phỏng thành **3.0924e18 LUNA**, trong khi quan sát mới **0.842451 tỷ**.

| Bucket | Giá LUNA train / USD | Quan sát / USD | Cung train / LUNA | Cung quan sát / LUNA |
|---|---:|---:|---:|---:|
| 11/05 00:00 | 2.63194 | 17.1766 | 8.1572e+08 | 7.99076e+08 |
| 11/05 01:00 | 1e-12 | 16.505 | 1.07988e+11 | 8.04346e+08 |
| 11/05 02:00 | 1e-12 | 14.2814 | 2.3883e+16 | 8.10923e+08 |
| 11/05 06:00 | 1e-12 | 9.23007 | 3.09241e+18 | 8.42451e+08 |
| 12/05 12:00 | 1e-12 | 0.0296213 | 1.30173e+20 | 1.0898e+10 |
| 15/05 23:45 | 1.13016e-11 | 0.000213296 | 1.44893e+20 | 6.80042e+12 |

Cuối kỳ, train cho giá LUNA bằng 5.29858e-08 lần quan sát, còn cung lớn hơn 21,306,401 lần. Nhóm `<1K` có holdout MAE 0.198077; tổng tiền gửi đạt NRMSE 0.068412 không che được sai lệch nhóm.

## 3. Khối lượng native: hai nút thắt khác nhau

| Ngày | Native thật / tỷ UST | Train giữ tham số / tỷ UST | Checkpoint all / tỷ UST |
|---|---:|---:|---:|
| 2022-05-09 | 0.172755 | 0.153518 | 0.312582 |
| 2022-05-10 | 1.211995 | 0.867234 | 1.011299 |
| 2022-05-11 | 4.144992 | 0.213130 | 1.990517 |
| 2022-05-12 | 1.794354 | 0.034735 | 2.513860 |
| 2022-05-13 | 0.080576 | 0.002297 | 0.000000 |

Holdout train đốt 0.250162 tỷ UST trên 6.019922 tỷ quan sát (4.156%). Checkpoint all đạt 4.504377 tỷ ở đoạn này. Native NRMSE ngày lần lượt 0.464839 và 0.245226; native fee MAE lần lượt 0.216653 và 0.158531.

**Train: không cạn inventory hoặc cash.** Trong 194 bucket native còn mở của holdout, không bucket nào có market UST dưới 1 hoặc native served dưới 1. Tại 11/5 06:00 có 11.927 tỷ market UST, 16.029 tỷ market USD và 199.685 triệu arb USD; arb LUNA tồn cuối bucket bằng 0. Đến cuối kỳ market UST còn 11.910 tỷ. Outside UST lớn nhất chỉ 2.240 tỷ, ngoài còn 447.504 triệu USD.

Quan sát từng phút xác nhận không lần nào lệnh trên 1 UST bị chặn bởi profit guard sau khi chọn optimum, và không phút nào thiếu stock sau outside buy khi native mở. Trần công suất là giới hạn nhỏ nhất của ba trần inventory/capital/protocol trong cả 2.910 phút mở, nhưng khối lượng chọn theo lợi nhuận VWAP thường thấp hơn nhiều trần đó. Tổng khối lượng trước profit guard bằng khối lượng thực thi; do đó không thể quy lỗi cho guard cuối lệnh.

| Ngày | Phút native mở | Phút stock thiếu | Phút optimum ≤1 | Phút discount không dương | Lệnh chọn / UST | Native thực thi / UST |
|---|---:|---:|---:|---:|---:|---:|
| 11/5 | 1440 | 0 | 4 | 0 | 213,130,460 | 213,130,460 |
| 12/5 | 1350 | 0 | 48 | 6 | 34,734,881 | 34,734,881 |
| 13/5 | 120 | 0 | 0 | 0 | 2,296,803 | 2,296,803 |

Giới hạn capacity thuần của các phút này xấp xỉ 5.978 / 8.968 / 0.797 tỷ UST, nên quy mô tham số arb_capacity_day một mình không giải thích mức thiếu volume. Mô hình rơi LUNA quá sớm, dùng oracle LUNA mô phỏng rất nhỏ để tính mint `gross LUNA = UST/oracle`, và từng mức nhỏ UST đã sinh cực nhiều LUNA. UST trong mô hình còn phục hồi gần peg từ 12/5, làm discount và optimum nhỏ, trong khi quan sát tiếp tục depeg. Đây là vấn đề đường giá–thanh khoản–mint và kỳ vọng cầu, không phải bằng chứng cần thêm USD.

Native service ratio tổng 0.058711 trong financial_metrics còn bao gồm native_requested sau khi native đóng; requested hiện được đếm theo discount/optimum trước điều kiện native_open. Nó không đo riêng thiếu thực thi trước halt. Trước halt trong replay train, served khớp các lệnh đã chọn.

**Checkpoint all: stock UST chuyển sang outside holder.** Cơ chế `outside_ust_buy` mua trước arbitrage, dùng một nhu cầu cố định theo USD/ngày và giữ UST vĩnh viễn; khi UST rất rẻ, cùng một USD thu được lượng token rất lớn. Trường params `external_ust_inventory=4e9` hiện không được dùng như trần mua/holdings trong engine. Không có bán ngược hay exit của outside holder.

| Bucket checkpoint | UST MM / tỷ | Outside UST / tỷ | Outside USD / tỷ | MM USD / tỷ | Arb USD / tỷ | Arb LUNA | Native mở | Native served / UST |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 12/05 12:00 | 8.750386 | 0.103583 | 0.911605 | 15.829751 | 0.399492 | 0 | có | 4.38454e+07 |
| 12/05 16:00 | -0.000000 | 8.309060 | 0.886799 | 15.503854 | 0.707962 | 0 | có | 8.5584e+06 |
| 13/05 01:45 | 0.000000 | 8.735152 | 0.886528 | 15.503854 | 0.707962 | 0 | có | 0 |
| 15/05 23:45 | 0.000000 | 10.175501 | 0.885550 | 15.503854 | 0.707962 | 0 | đóng | 0 |

Inventory market cuối bucket dưới 1 UST tại 2022-05-12T16:00:00+00:00; có 34/194 bucket mở như vậy, 33 bucket native dưới 1. End-stock bằng 0 không suy ra bucket đó chưa từng đốt: 12/5 16:00 vẫn đốt UST trước khi hết stock. Từ sau bucket đó đến native halt, khối lượng gần 0. Tại 13/5 01:45, MM và arb còn USD, arb không bị kẹt LUNA, nhưng stock có thể đem đốt không còn. Đây là bằng chứng trực tiếp về phân bổ stock trong mô hình; không đồng nghĩa outside holder ngoài đời đã giữ cùng số UST.

## 4. Mức cải thiện của checkpoint và phần chưa hoàn tất

Snapshot checkpoint: call 453, stage `refinement`, objective **7.711416118570**, run `20261010T142315780978Z_all`; execution status quan sát sau replay là `running`. SHA-256 snapshot `1ffed33162bdeae694a263f415f3534bd5e06e316fbaa832d2480497fbe0cb88`; parameter SHA-256 `9c142b3d03a131a55d5382a1d19b5aa7efbfaef2227a13a7da1a20cfd9a2c6ed`. Replay riêng dùng fast với cùng nguồn/target/group, không chạy optimizer và không công bố thành report_all.

Checkpoint đạt 2/6 gate toàn sự kiện, chỉ 2/6 trên đoạn 11–15/5. Việc so với train holdout thể hiện cải thiện tái hiện bằng dữ liệu cả sự kiện, không phải cải thiện dự báo ngoài mẫu. Full-fit đã nhìn thấy 11–15/5 trong objective.

Cuối kỳ checkpoint: cung 453.538 tỷ LUNA so với 6800.424 tỷ quan sát; giá 0.008352996 USD so với 0.000213296, tỷ lệ 39.16 lần. Độ khớp cải thiện nhiều bậc log so với train, nhưng chưa đủ gần sự kiện.

Các lượng tiền vẫn có chủ; train USD/UST/claim sai lệch tuyệt đối lớn nhất chỉ 0.000240 / 0.000225 / 0.0000324. LUNA sai lệch tuyệt đối 147,456 token khi supply cực lớn, nhưng relative lớn nhất qua các bước là 5.31e-15. Điều này xác nhận sổ cái vẫn nhất quán số học, không xác nhận đường giá/cung đúng lịch sử.

Ưu tiên tiếp theo là kiểm tra một cấu trúc thanh khoản và hành vi holder chung có thể khớp đồng thời đường LUNA, cung và native ngày; xác định lại độ sâu theo token/USD và nguồn token bán có chủ. Không thêm outside cap đơn lẻ để coi là đã sửa train, vì train không có nút thắt đó. Giữ objective/quan sát thật, không ép giá hoặc burn thực tế vào mô phỏng, không đổi core trong lúc fit đang chạy. Chờ fit all và giả thuyết riêng kết thúc, rồi so nguồn tương ứng trước khi chọn.

### Snapshot tham số checkpoint để tái lập đối chiếu

```json
{
  "arb_capacity_day": 1052290610.0102551,
  "arb_capital_usd": 150000000.0,
  "base_pool_usd": 50000000.0,
  "btc_fee": 0.001,
  "btc_slippage": 0.003,
  "execution_fee": 0.001,
  "external_ust_inventory": 4000000000.0,
  "hazard_base": -11.24298061132017,
  "hazard_discount": 160.32391430316363,
  "hazard_luna": 20.7665038610079,
  "hazard_outflow": 109.79324522292586,
  "hazard_queue": 3.0,
  "hazard_size": 0.3558479366741082,
  "loan_repayment_days": 2.0,
  "luna_beta_btc": 2.564634752116533,
  "luna_depth_growth": 0.45341295020225203,
  "luna_depth_usd": 8262185179.653017,
  "luna_residual_bid_fraction": 0.18996727190891977,
  "market_cash_usd": 25000000000.0,
  "market_luna_inventory": 100000000.0,
  "min_spread": 0.005,
  "normal_demand_day": 25000000.0,
  "oracle_lag_minutes": 1,
  "recovery_minutes": 3.6,
  "redeposit_day": 0.015,
  "reserve_income_day": 2000000.0,
  "seed_shock_sell_fraction": 0.95,
  "sell_fraction": 0.92,
  "ust_confidence_beta": 0.4703666104789953,
  "ust_depth_luna_beta": 0.21387954435926126,
  "ust_depth_usd": 79945981953.60265
}
```

### Nguồn dùng trong đối chiếu

```json
{
  "calibrate.py": "7aa5ff3453a39669c321657894a352194bdfba6b8b797f0b629c6bd34c4de583",
  "config.py": "610f1ed6cc25301c1ca22f9305c736e6f94229f25cfc3619ba447875c1f13662",
  "data.py": "6331fab0b4e19fef798a6c6f593c3468ff36a17e5427e30c1dce3823a8b378e9",
  "data/external/btc_metadata.json": "fa24b2bcfed763e896f071deda59f8269f01939ab04af9c4300a60f00f0f9856",
  "data/external/btc_usdt_minute.parquet": "86ccb9bbcd9523d53c40b239f205f8628d5ad1780fe89e35ada46b2d5a218f3a",
  "data/sources.json": "2c9e3680e5c64a745090f6dc8ad0eecc2440d3da9ca6a9684e1a8b5894cbd359",
  "engine.py": "0a89a9e690c7998d8fadaa1756466b6195b67219483320403672a441cd95f7ea",
  "metrics.py": "c71e0345ca304bc22d025e15cd13a07c9d244b3659a1a2f2761508e67a1d48b9"
}
```

Chứng cứ file: outputs/reconstruction/train_audit.json, outputs/calibration/report_train.json, config_train.json, trajectory_train.parquet, ledger_train.csv, archive run train; checkpoint_all_v3.json được đọc thành snapshot trước replay. Đường giá/cung lấy từ load_targets(15), cohort từ group_targets(15), không dùng giá quan sát trong engine.

Các vị trí cơ chế trong nguồn engine hiện tại: outside buy trước arb (439–444), depth và quote/native optimum (448–473), gross mint và book transfer (474–482), LUNA sale/impact (488–515), confidence UST và oracle (516–523), invariants (543–564). Số dòng chỉ áp dụng cho SHA-256 engine đã ghi ở trên.
