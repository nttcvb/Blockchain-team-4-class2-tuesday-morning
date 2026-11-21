# Kiểm tra dữ liệu phục vụ cải thiện mô hình

Rà soát ngày 10/10/2026. Các số liệu dưới đây được đọc từ Parquet nguồn và mã tái lập; không dùng kết quả hiệu chỉnh mới để diễn giải chất lượng phiên bản đang cải thiện. Bộ dữ liệu gốc không bị sửa.

## Quan sát và đơn vị

- `epoch_state_fig10.deposit_b_ust` đã là tỷ UST; nhân `1e9` để lấy số UST. `aterra_supply` trong nguồn là micro-aUST; công thức nguồn đã chia `1e6` trước khi tạo `deposit_b_ust`.
- `Anchor_global_stats_fullnode.total_liabilities` và `prev_interest_buffer` là đơn vị micro-token; chia `1e6`. Giao dịch `anchor_run_tx_cleaned.ust_vol` và native `offer_amount/swap_amount/fee_amount` đã là token nguyên, không chia thêm.
- Giá UST/LUNA chính là cross-exchange VWAP USD theo phút. Panel giá dùng Figure 11 cho năm 2022 là FTX USD riêng, vì vậy giữ thành kiểm tra chéo, không coi nó là cùng một quan sát với VWAP tổng hợp.
- `native_fee = sum(fee_amount) / sum(swap_amount + fee_amount)` trong mỗi khoảng là tỷ lệ theo lượng LUNA; không phải tỷ lệ USD/UST hoặc số LUNA đã giao. Nguồn native có UST→LUNA, còn nguồn cung LUNA là net mint/burn tổng hợp. Vì vậy tổng gross mint một chiều không buộc phải bằng đúng thay đổi nguồn cung.

## Sửa thời điểm nguồn cung LUNA

`luna_total_supply_run` ghi cumulative mint/burn của một giờ dưới nhãn đầu giờ. Đối chiếu định lượng cho thấy nhãn không thể coi như snapshot tức thời ở đầu giờ:

| Kiểm tra | Kết quả từ dữ liệu nguồn |
|---|---:|
| Supply tăng tại nhãn 13/05 01:00 | 5,88225 nghìn tỷ LUNA |
| Gross mint UST→LUNA trong giờ 13/05 01:00–01:59 | 5,94364 nghìn tỷ LUNA |
| LUNA giao trong riêng 01:50–01:59 | 1,97126 nghìn tỷ LUNA |
| Log10 RMSE giữa increment supply và gross mint cùng giờ, 11/05–13/05 02:00 | 0,01571 |
| Log10 RMSE nếu dịch mint sớm một giờ | 0,44731 |
| Log10 RMSE nếu dịch mint muộn một giờ | 0,44778 |
| Tổng sai khác tuyệt đối / tổng gross mint, cùng giờ | 1,054% |

Khoảng 1,97 nghìn tỷ LUNA được giao lúc 01:50–01:59 đã nằm trong giá trị nguồn gắn nhãn 01:00. Forward-fill nhãn đó ở 01:15 hoặc 01:45 sẽ đưa thông tin tương lai trong giờ vào quan sát. `luna_supply_observations()` trong `luna_sim/data.py` nay dịch nhãn nguồn thêm một giờ rồi mới forward-fill. Khởi tạo cũng dùng đúng helper này: supply ban đầu 749.457.905,9555453 LUNA lấy từ giờ nguồn 05/05 23:00 đã hoàn tất trước 06/05 00:15.

Đây là quy ước quan sát hoàn tất giờ, không nội suy theo mục tiêu và không sửa đường nguồn cung mô phỏng. Dữ liệu `quality_report.json` ghi quy ước và bằng chứng. Các assert trực tiếp đã kiểm tra raw 13/05 01:00 chỉ khả dụng từ 02:00, mục tiêu 01:45 dùng raw 00:00, và initial facts không lấy giờ chưa hoàn tất.

## Onset và mục tiêu hiệu chỉnh

Định nghĩa `first_depeg` hiện tại là thời điểm xác nhận bốn quan sát liên tiếp ở bước 15 phút dưới 0,98. Với mục tiêu VWAP tổng hợp, thời điểm xác nhận là **09/05 18:15 UTC**. Đây không phải lần giao dịch đầu tiên dưới ngưỡng hoặc thời điểm hai ví A/B bắt đầu rút ngày 07/05. Giá phút đầu tiên dưới 0,98 là 09/05 16:11; các đợt ngắn bị tiêu chí xác nhận loại ra.

Phiên bản v2 cũ có onset full-fit 07/05 19:00, sớm 47,25 giờ; bộ train cũ là 09/05 17:30, sớm 0,75 giờ. Số này chỉ làm baseline của cải thiện. Penalty cũ `0.2 × min(20, abs(error_hours)/12)` chỉ cộng khoảng 0,7875 cho lỗi 47,25 giờ, tương đối yếu so với tổng loss 8,60 và gate 6 giờ. Cần cố định định nghĩa onset, tăng tính phân biệt trong objective; không đổi ngưỡng để khiến đường cũ vượt gate.

Có một khác biệt quan sát đáng xử lý: `group_targets` là phần **vốn ban đầu còn chưa thoát theo FIFO**, giảm đơn điệu theo cumulative withdrawals được chặn tại vốn đầu kỳ. `group_remaining` cũ trong model là toàn bộ claim hiện tại chia vốn ban đầu, bao gồm lãi và tiền gửi lại. Hai đại lượng không hoàn toàn tương đương. Đề xuất theo dõi riêng initial principal còn lại của từng tác nhân và giảm theo FIFO khi rút được phục vụ; lãi và redeposit không khôi phục counter vốn ban đầu. Không đưa realized loss hoặc `full_maxusd` vào hành vi để khắc phục sai số nhóm.

## BTC: bản ghi chuyển thật và ngân sách mô hình

[Báo cáo JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf), trang 12, Exhibit 1 và footnote của Exhibit 5 cung cấp các mốc chuyển BTC cụ thể:

| UTC | Chuyển nội bộ | BTC gross công bố | Tranche net được quy cho ngân sách mô hình |
|---|---|---:|---:|
| 09/05 03:45 | LFG → Jump | 22.189 | 22.189 |
| 09/05 18:42 | LFG → Jump | 30.000 | 24.687 |
| 10/05 01:20 | LFG → TFL | 28.206 | 28.205 |
| 10/05 08:03 | Jump → TFL | 4.000 | 4.000 |
| 10/05 08:37 | Jump → TFL | 1.000 | 1.000 |

Hai cột cuối có ý nghĩa khác nhau. Các số gross là bản ghi chuyển được báo cáo, làm tròn đến BTC nguyên. Các tranche net là phân bổ ngân sách **80.081 BTC khả chi**, giữ **313 BTC** từ reserve đầu kỳ **80.394 BTC**. Trừ 5.313 trong tranche thứ hai để dành 5.000 cho hai chuyển Jump→TFL sau đó và 313 retained; trừ một BTC so với số tròn 28.206 trong tranche TFL. Footnote 23 trang 11 nêu số BTC thực tế là 28.205,54; tranche 28.205 bảo thủ bỏ 0,54 BTC để giữ cap dự trữ đã công bố. Đây là phép quy ngân sách, không khẳng định phần trừ thực tế xảy ra ở giờ 18:42 hoặc 01:20.

`sources.json` nay tách `verified_btc_transfer_records` khỏi `funding_timing_intervals`. Early là mốc chuyển công bố; late là **early +60 phút độ trễ vận hành giả định**, không phải bound đã xác minh. Việc chuyển BTC không chứng minh giờ bán BTC hoặc mua UST. Account LFG tổng hợp tiếp tục bỏ qua custody chi tiết ở sàn. Tổng tranche được assert bằng 80.081; cap không tăng và các chuyển nội bộ không tạo tài sản mới.

JSH còn ghi Jump chuyển 1.515.689.462 UST cho TFL ngày 11/05, với chuỗi chuyển cuối ở 14:36. Đây là chronology bàn giao token, không chronology mua UST trên thị trường. Không suy ra rằng Jump mua toàn bộ số UST đó lúc 14:36. Gross purchases TFL và net own-contribution cũng phải giữ riêng: gross turnover có sales/recycling, không bằng nguồn USD cứu trợ mới. Hoán đổi UST→LUNA của TFL đã xuất hiện trong native aggregate nguồn; nếu bổ sung hành động quản trị, không cộng thêm toàn bộ lượng đó lên aggregate observed swaps lần nữa.

## Ngừng và hoạt động lại của chain

Khoảng trống dài giữa giao dịch source là bằng chứng cho mốc xấp xỉ trong replay, không bằng chứng chính xác về thời điểm consensus halt:

| Khoảng trống | Sự kiện cuối | Sự kiện sau |
|---|---|---|
| Anchor và native, 12/05 | 16:01:00 UTC | 17:45:18 UTC |
| Anchor, 13/05 | 01:58:49 UTC | 11:26:45 UTC |

Native extract không có swap sau 13/05 01:58:49. Anchor tiếp tục giao dịch sau khi hoạt động lại: từ 13/05 02:00 trở đi có **7.011 withdrawals, tổng 206,876 triệu UST**, và **1.336 deposits, tổng 22,652 triệu UST**. Snapshot Anchor sau restart và đến 15/05 tiếp tục giảm. Vì vậy đóng rút Anchor vĩnh viễn cùng native là giả định không được dữ liệu ủng hộ.

`sources.json.inferred_chain_activity_gaps` lưu cả timestamp nguồn và mốc tròn phút dùng cho replay: [12/05 16:01, 17:45) và [13/05 01:59, 11:27). `diagnostics.py` tạo timeline có hai restart và ngừng native riêng. Root triển khai việc tách native/Anchor trong engine; phần rà soát này không sửa engine.

## Covariates trước sự kiện

`build_population` dùng `prerun_usd`, `prerun_aust` và bốn field `log_volume_adj`, `cex_degree`, `used_bridge`, `log_age_months`. [Bài nghiên cứu nguồn](https://mitsloan.mit.edu/shared/ods/documents/?PublicationDocumentID=9764), section 4.1, PDF trang 32–34, định nghĩa sophistication từ giao dịch trước run: CEX đã sử dụng, bridge đã sử dụng, và volume token inflows chia balances trước run. `Datasets.md` mục 21 còn chỉ rõ input `sophistication_prerun_may5.parquet`; mục 28 và `prep_loss_panel.py` ghi pipeline tương ứng.

Không có evidence rằng bốn field đang dùng là đặc trưng full-window. Giữ chúng cùng provenance metadata `agent_feature_provenance`; raw transaction history không được phát hành nên không thể tái kiểm toán toàn bộ cửa sổ locally. `full_maxusd`, `log_wealth` theo wealth cực đại và `perc_loss` trong cùng file không được đưa vào hành vi.

## Giới hạn của xác minh và đề xuất

Các sửa quan sát/chronology cần được đánh giá bằng calibration và suite mới; báo cáo v2 cũ không chứng minh lợi ích số học của bản đang sửa. Giữ train 06–10/05 và kiểm tra thời gian 11–15/05; full fit chỉ là trong mẫu. Cấu trúc đã học từ toàn sự kiện nên temporal parameter holdout vẫn không phải blind structural validation.

Để giảm sai số mà không leakage: ưu tiên tích phân thị trường trong bước nhỏ, oracle trễ thật theo lịch sử mô phỏng, dịch vụ Anchor độc lập native, counter FIFO phù hợp group target, và objective phân biệt onset/native theo phase. Dữ liệu giá/withdrawals/supply observed chỉ làm mục tiêu hoặc diagnostic; không dùng để điều khiển đường giá nội sinh mỗi bước. Nếu bổ sung thông tin Jump, dùng ràng buộc tổng nguồn lực và khoảng thực thi có bằng chứng, giữ kịch bản độ nhạy cho chronology chưa biết.
