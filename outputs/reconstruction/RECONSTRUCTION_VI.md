# Tái hiện lịch sử UST/LUNA, 6–15/5/2022

Tạo lúc 2026-10-11T07:38:43.161386+00:00.

Báo cáo tách kết quả khớp toàn sự kiện và kiểm định giữ nguyên tham số theo thời gian. Mở [biểu đồ tương tác](reconstruction.html) để đối chiếu từng giai đoạn.

## Kết quả đối chiếu

Hiệu chỉnh trước 11/5: 6/6 ngưỡng; Giữ tham số, từ 11/5: 2/6 ngưỡng; Khớp toàn sự kiện: 1/6 ngưỡng.

| Chỉ số | Ngưỡng | Hiệu chỉnh trước 11/5 | Giữ tham số, từ 11/5 | Khớp toàn sự kiện |
| --- | --- | --- | --- | --- |
| MAE giá UST / USD | ≤ 0.05 | 0.0215 · đạt | 0.3731 · chưa đạt | 0.0883 · chưa đạt |
| NRMSE tiền gửi Anchor | ≤ 0.1 | 0.0830 · đạt | 0.0684 · đạt | 0.1202 · chưa đạt |
| RMSE log₁₀ giá LUNA | ≤ 0.5 | 0.0724 · đạt | 9.1467 · chưa đạt | 0.8828 · chưa đạt |
| RMSE log₁₀ cung LUNA | ≤ 0.5 | 0.0024 · đạt | 8.5046 · chưa đạt | 0.5007 · chưa đạt |
| MAE lớn nhất của 6 nhóm | ≤ 0.15 | 0.0707 · đạt | 0.1986 · chưa đạt | 0.1533 · chưa đạt |
| Lệch thời điểm mất peg / giờ | ≤ 6 | 0.0000 · đạt | 0.0000 · đạt | 0.7500 · đạt |

## Thời điểm mất peg

Mất peg là giá UST dưới 0,98 USD liên tục một giờ. Sai lệch âm nghĩa là mô hình mất peg sớm.

| Bộ tham số / mẫu | Mô phỏng UTC | Quan sát UTC | Lệch có dấu / giờ |
| --- | --- | --- | --- |
| Hiệu chỉnh trước 11/5 | 2022-05-09T18:15:00+00:00 | 2022-05-09T18:15:00+00:00 | 0.00 |
| Giữ tham số, từ 11/5 | 2022-05-09T18:15:00+00:00 | 2022-05-09T18:15:00+00:00 | 0.00 |
| Khớp toàn sự kiện | 2022-05-09T19:00:00+00:00 | 2022-05-09T18:15:00+00:00 | 0.75 |

## Sai số theo giai đoạn

Sai số giai đoạn dùng cùng định nghĩa với bảng toàn mẫu; ngưỡng nhóm chỉ xét các bước có quan sát.

| Giai đoạn | Bộ tham số | UST MAE | Anchor NRMSE | LUNA log RMSE | Cung log RMSE | Nhóm MAE lớn nhất |
| --- | --- | --- | --- | --- | --- | --- |
| Trước mất peg | Toàn sự kiện | 0.0050 | 0.0646 | 0.0299 | 0.0009 | 0.0858 |
| Trước mất peg | Trước 11/5 | 0.0063 | 0.0348 | 0.0216 | 0.0011 | 0.0450 |
| Rút vốn, trước 11/5 | Toàn sự kiện | 0.0507 | 0.2913 | 0.1651 | 0.0031 | 0.4054 |
| Rút vốn, trước 11/5 | Trước 11/5 | 0.0674 | 0.1551 | 0.1404 | 0.0044 | 0.1485 |
| Từ 11/5 | Toàn sự kiện | 0.1600 | 0.0685 | 1.2449 | 0.7077 | 0.2016 |
| Từ 11/5 | Trước 11/5 | 0.3731 | 0.0684 | 9.1467 | 8.5046 | 0.1986 |

## Native swap

Khối lượng UST đầu vào được tính trước phí, tách khỏi lượng LUNA sau phí.

| Mẫu | Mô phỏng / tỷ UST | Quan sát / tỷ UST | NRMSE khối lượng ngày | MAE tỷ lệ phí |
| --- | --- | --- | --- | --- |
| Hiệu chỉnh trước 11/5 | 1.172 | 1.471 | 0.1286 | 0.0162 |
| Giữ tham số, từ 11/5 | 0.252 | 6.020 | 0.4647 | 0.2152 |
| Khớp toàn sự kiện | 3.199 | 7.491 | 0.2589 | 0.0575 |

## Sáu nhóm người gửi

Quan sát 6 nhóm có 768 bước 15 phút, từ 2022-05-06T00:15:00+00:00 đến 2022-05-14T00:00:00+00:00 UTC. Phần không có quan sát được để trống; không kéo dài đường dữ liệu thật bằng giá trị cuối cùng. Bản trích giao dịch kết thúc tại 2022-05-13T23:59:39+00:00.



## Cấu hình và kiểm toán

Hai lần hiệu chỉnh đã hoàn tất, đúng nguồn hiện tại; các chỉ số và quỹ đạo được đối chiếu lại với bản lưu của từng run.

| Bộ tham số | Run ID | Người gửi | Arbitrageur | Bước / phút | Seed | Số bước | Số lần đánh giá | Hàm mất mát |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Trước 11/5 | 20261011T071942383237Z_train | 1000 | 20 | 15 | 42 | 959 | 14 | 1.4809 |
| Toàn sự kiện | 20261011T071942831158Z_all | 1000 | 20 | 15 | 42 | 959 | 274 | 6.0601 |

## Sai lệch sổ cái lớn nhất

Sai lệch tuyệt đối qua các bước, tính bằng token hoặc USD tương ứng; cần đọc cùng quy mô cung và tài sản.

| Bộ tham số | UST | LUNA | USD | Quyền đòi Anchor |
| --- | --- | --- | --- | --- |
| Trước 11/5 | 0.000259 | 475136.000000 | 0.000233 | 0.000032 |
| Toàn sự kiện | 0.000164 | 0.000006 | 0.000420 | 0.000021 |

## Nguồn dữ liệu

Các đường quan sát được dựng từ dữ liệu ngoại tuyến bên dưới.

| Nguồn | Vị trí trong bộ dữ liệu |
| --- | --- |
| Dữ liệu gốc ngoại tuyến | D:\New folder\terra-luna-run-replication (1)\terra-luna-run-replication\data |
| Giá UST/LUNA | prices/ust_price_may2022.parquet; prices/luna_price_may2022.parquet |
| Anchor | anchor_run/epoch_state_fig10.parquet; anchor_run/anchor_run_tx_cleaned.parquet |
| Cung LUNA và native swap | native_swaps/luna_total_supply_run.parquet; native_swaps/ust_luna_swaps_run.parquet |
| Quy mô người gửi trước sự kiện | loss/depositor_prerun_size.parquet; labels/interdm_addresses.parquet |

- [Nghiên cứu và nguồn bộ dữ liệu](https://mitsloan.mit.edu/shared/ods/documents/?PublicationDocumentID=9764)
- [Kiểm toán LFG/TFL](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf)
- [BTC phút](https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2022-05.zip)
- [Đặc tả native market](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html)

## Biến thiên giữa các seed lịch sử

0/20 lượt ngẫu nhiên đạt đủ sáu ngưỡng. Sổ cái và tồn kho được kiểm tra độc lập; đạt các kiểm tra tài chính không đồng nghĩa khớp lịch sử. Các dải p05/trung vị/p95 phản ánh biến thiên giữa seed của tác nhân trong cùng mô hình và bộ tham số đã khớp toàn sự kiện. Chúng không phải khoảng tin cậy về bất định cấu trúc. Đối chiếu lịch sử với bộ tham số này là kiểm tra trong mẫu; không thay thế kiểm định giữ tham số theo thời gian. Không có kịch bản chính sách trong bộ kiểm tra này.

| Chỉ số | Ngưỡng lịch sử | Số seed đạt | p05 sai số | Trung vị sai số | p95 sai số |
| --- | --- | --- | --- | --- | --- |
| MAE giá UST / USD | ≤ 0.05 | 0/20 | 0.1380 | 0.3090 | 0.3451 |
| NRMSE tiền gửi Anchor | ≤ 0.1 | 0/20 | 0.1743 | 0.2778 | 0.4732 |
| RMSE log₁₀ giá LUNA | ≤ 0.5 | 0/20 | 1.9004 | 3.0558 | 3.2327 |
| RMSE log₁₀ cung LUNA | ≤ 0.5 | 1/20 | 0.8660 | 2.1816 | 2.1942 |
| MAE lớn nhất của 6 nhóm | ≤ 0.15 | 0/20 | 0.1907 | 0.2934 | 0.3961 |
| Lệch thời điểm mất peg / giờ | ≤ 6 | 0/20 | 12.0375 | 48.7500 | 131.5500 |

## Đối chiếu bước 5/15 phút

Giữ cùng tham số và so đúng thời điểm UTC, không nội suy. Sai lệch lớn giữa hai bước cho thấy đường mô phỏng còn nhạy với nhịp cập nhật; không dùng đường xác định 15 phút để khẳng định mô hình đã ổn định.

| Chỉ số | Sai số với quan sát: 15 phút | Sai số với quan sát: 5 phút | Sai lệch giữa hai bước |
| --- | --- | --- | --- |
| MAE giá UST / USD | 0.0883 | 0.1244 | 0.1295 |
| NRMSE tiền gửi Anchor | 0.1202 | 0.1131 | 0.0631 |
| RMSE log₁₀ giá LUNA | 0.8828 | 2.5028 | 2.3136 |
| RMSE log₁₀ cung LUNA | 0.5007 | 2.1235 | 2.2796 |

## Giới hạn cách diễn giải

- Bộ khớp toàn sự kiện dùng dữ liệu từ 6–15/5/2022 để ước lượng tham số. Đây là tái hiện trong mẫu; chất lượng ngoài mẫu được đọc riêng ở cột giữ tham số từ 11/5.
- Các đồ thị dùng quỹ đạo lịch sử xác định, seed cố định. Kiểm toán xác nhận đồng nhất fast/cadCAD đã được ghi trong kết quả hiệu chỉnh; báo cáo không chạy lại hoặc chọn seed theo mức khớp.
- Giá, cung, tiền gửi và giao dịch native là mục tiêu đối chiếu. Chuỗi giá mục tiêu không được ép vào quỹ đạo mô phỏng. Cung tổng hợp theo giờ chỉ có hiệu lực từ cuối giờ; các thời điểm trên báo cáo đều là UTC.
- Sáu nhóm đo tỷ lệ vốn gốc ban đầu còn lại của người gửi trước sự kiện, theo FIFO, loại các ví trung gian có nhãn. Tiền gửi mới và lãi không làm tăng lại vốn gốc; đây là đại lượng khác tổng số dư Anchor.
- Nguồn lực LFG/TFL và các khoảng gián đoạn chain/native là đầu vào lịch sử. Mốc chuyển BTC không xác định thời điểm bán BTC hay mua UST; giao dịch Jump và các ví TFL chưa có lịch thực thi đầy đủ.
- Độ sâu thị trường, hành vi mua/bán và hàm phản ứng của tác nhân là giả định hiệu chỉnh. Sai số thấp của đường tổng hợp chưa xác định duy nhất cơ chế vi mô đã gây ra sự kiện thật.
- Chỉ số native bổ sung kiểm tra khối lượng theo ngày và phí. Đạt sáu ngưỡng không tự động bảo đảm từng giao dịch, mỗi ví, hay mọi thời điểm đều khớp.

Danh tính mã nguồn, dữ liệu đầu vào, quỹ đạo và hai tệp báo cáo được ghi trong `manifest.json`. Báo cáo chỉ được coi là hiện hành khi tất cả dấu SHA-256 còn trùng khớp.
