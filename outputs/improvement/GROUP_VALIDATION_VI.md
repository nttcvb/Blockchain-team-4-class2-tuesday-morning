# Phạm vi quan sát nhóm rút tiền và cách chấm độ khớp

Cập nhật ngày 10/10/2026. Đây là sửa quy ước dữ liệu quan sát, không phải kết quả hiệu chỉnh mới của mô hình.

Tệp nguồn `anchor_run/anchor_run_tx_cleaned.parquet` có 293.276 giao dịch từ **06/05/2022 00:00:01 UTC** đến **13/05/2022 23:59:39 UTC**. Phần theo nhóm trước đây kéo dài số dư cuối cùng sang ngày 14–15/5; hai cột `observed_withdraw` và `observed_deposit` cũng tiếp tục điền 0. Các giá trị đó đã biến phần không có dữ liệu thành quan sát giả.

`group_targets` và hai cột giao dịch hiện giới hạn theo phạm vi của toàn bộ tệp giao dịch. Với bước 15 phút, bucket cuối có dấu thời gian cuối khoảng là **14/05/2022 00:00 UTC**; từ **00:15 UTC ngày 14/5** trở đi là `NaN`. Bucket nằm trong phạm vi dữ liệu mà không có giao dịch vẫn có dòng tiền 0 và phần vốn ban đầu còn lại giữ nguyên. Mốc đầu bucket được làm tròn xuống từ giao dịch đầu tiên, mốc cuối làm tròn lên từ giao dịch cuối; đây là quy ước bucket của tệp, không phải bằng chứng về hoạt động trong 21 giây cuối cùng chưa có giao dịch quan sát được.

Trong 959 hàng toàn sự kiện, mỗi nhóm có **768 quan sát**, 191 hàng cuối không có quan sát nhóm. Hai cột giao dịch cũng có 191 hàng không quan sát; bốn chuỗi chính là giá UST, giá LUNA, tiền gửi Anchor và nguồn cung LUNA vẫn có 959 giá trị. Validation từ 11/5 có **289 quan sát mỗi nhóm**, kết thúc tại bucket 14/5 00:00 UTC.

Phần vốn ban đầu còn lại vẫn theo FIFO: cumulative withdrawals từng địa chỉ được chặn tại vốn đầu kỳ; lãi và nạp lại không khôi phục vốn đầu kỳ đã rút. Cumulative flows được tính **trước** khi căn chỉnh với index đánh giá, để không làm rơi khoản rút trước timestamp đánh giá đầu tiên. Tệp thật có 140 giao dịch trước 06/5 00:15, nhưng tất cả được đưa vào bucket 00:15 nên không có flow bucket trước hàng đầu. Kiểm tra hồi quy riêng bao phủ trường hợp các bucket trước hàng đầu tồn tại.

Quan sát và population cùng chọn địa chỉ có `prerun_usd > 0`, `prerun_aust > 0`, loại các địa chỉ trung gian trong `interdm_addresses`, và chia các khoảng trái đóng/phải mở bằng cùng `BINS`. Nhãn `>10M` hiện gồm cả giá trị đúng 10M theo quy ước khoảng đó. Tệp nguồn không có trường hợp USD đầu kỳ dương nhưng aUST không dương và không có địa chỉ trùng trong bảng size hoặc bảng loại trừ. Cohort thực có 233.990 địa chỉ sau loại trừ:

| Nhóm | Số địa chỉ | Vốn đầu kỳ UST |
|---|---:|---:|
| <1K | 118.183 | 18.264.502 |
| 1K–10K | 63.372 | 235.816.438 |
| 10K–100K | 40.689 | 1.269.351.933 |
| 100K–1M | 10.406 | 2.713.013.259 |
| 1M–10M | 1.231 | 3.027.581.933 |
| >10M | 109 | 4.941.543.736 |

Population seed 42 đại diện đúng các tổng vốn này tới sai số dấu phẩy động. Claim tổ chức còn lại 1.848.208.787,56 UST là phần ngoài cohort sáu nhóm và vẫn nằm trong tổng tiền gửi Anchor. Vì vậy, độ khớp tổng tiền gửi tốt không bảo đảm sáu nhóm cùng rút đúng thời điểm.

`fit_metrics` hiện trả `group_metrics` với MAE, số cặp hữu hạn, số quan sát hữu hạn, mốc đầu/cuối quan sát và mốc đầu/cuối cặp cho từng nhóm. MAE chỉ dùng cặp mô phỏng/quan sát đều hữu hạn. Nếu toàn cửa sổ không có cặp hợp lệ, `group_mae_max = None`, gate nhóm không đạt. Objective hiệu chỉnh báo lỗi nếu toàn cửa sổ fit không có cặp nhóm, thay vì cho điểm 0. Một phase riêng không có quan sát nhóm chỉ tính bốn đại lượng còn quan sát được, không thêm lỗi nhóm 0 vào trung bình; cửa sổ rỗng bị từ chối. **Sáu gate và tất cả ngưỡng được giữ nguyên**, gồm MAE nhóm tối đa 0,15.

Chấm lại **quỹ đạo train cũ**, không chạy lại mô phỏng hay hiệu chỉnh, cho kết quả validation sau:

| Nhóm | MAE cũ với phần kéo dài giả | MAE chỉ trên quan sát thật |
|---|---:|---:|
| <1K | 0,232434 | 0,190238 |
| 1K–10K | 0,076481 | 0,057609 |
| 10K–100K | 0,051140 | 0,063034 |
| 100K–1M | 0,046237 | 0,063027 |
| 1M–10M | 0,063059 | 0,081557 |
| >10M | 0,095950 | 0,108678 |

Sai số nhóm nhỏ nhất giảm nhưng vẫn vượt 0,15. Các sai số giá UST, giá LUNA, nguồn cung LUNA của quỹ đạo đó không đổi và vẫn chưa đạt. Sửa dữ liệu này không chứng minh mô hình đã tái hiện đủ gần sự kiện; cần fit lại trên target đã sửa và cơ chế thị trường được chọn.

Hash frame mục tiêu 15 phút sau sửa: `89e7a53d8d795cb48706657306144ee54e4306d667265520127cb31a3d59e4a9`. Hash frame nhóm: `c606efc0cece8a608a4c1db7838854340069b37787da061d4c86f0c4a73f9865`. Target SHA và group SHA đã đổi; checkpoint/report fit cũ không còn được coi là fit trên dữ liệu hiện tại. `OBJECTIVE_VERSION` là `gate_phase_onset_native_v3_group_coverage_v1`. `prepare` sẽ ghi cả hai phạm vi quan sát vào `quality_report.json`; cần chạy lại bước chuẩn bị dữ liệu để cập nhật các tệp processed trước khi bàn giao.

Kiểm chứng: `tests/test_group_coverage.py` có **9 kiểm tra mới** về ngày cuối không quan sát, bucket cuối được giữ, số 0 trong bucket yên lặng, cumulative withdrawals trước start, redeposit/FIFO, boundaries/exclusions của nhóm, tập quan sát rỗng, cặp hữu hạn và phase rỗng quan sát. Chạy cùng 21 kiểm tra cơ chế/hiệu chỉnh hiện có: **30 passed**, exit 0; bằng chứng máy đọc tại `outputs/improvement/group-coverage-tests.xml`. Chưa chạy bộ kiểm tra toàn dự án vì parent đang phối hợp sửa engine rồi sẽ chạy kiểm tra chung trước khi đóng băng nguồn cho fit mới.
