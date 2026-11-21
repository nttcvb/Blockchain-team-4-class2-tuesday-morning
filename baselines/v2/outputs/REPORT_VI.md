# Báo cáo bài nhóm: mô phỏng Luna–UST bằng cadCAD

## 1. Câu hỏi và thiết kế

Mô hình kết hợp 1.000 tác nhân người gửi đại diện, 20 arbitrageurs và tồn lượng tài chính tổng hợp. Mỗi bước 15 phút lần lượt quan sát, kích hoạt chính sách, quyết định hành vi, xử lý Anchor, khớp giao dịch/native swap và kiểm tra kế toán. Thí nghiệm từ 06–15/05/2022 dùng UTC. Giá, rút tiền và nguồn cung được sinh nội sinh; dữ liệu lịch sử dùng làm mục tiêu hiệu chỉnh và đối chiếu.

Hai ví A/B là cú sốc khởi phát được tái lập có điều kiện. Không suy diễn rằng đây là bằng chứng tấn công hay thao túng. Vốn bổ sung để thực hiện các lần gửi lại của hai ví là suy ra từ chuỗi hành động, có hạch toán trong nguồn cung UST ban đầu.

## 2. Độ khớp và giới hạn

| Chỉ số | Hiệu chỉnh 06–10/05 | Kiểm định 11–15/05 | Mục tiêu |
|---|---:|---:|---:|
| MAE UST / USD | 0.0261 | 0.7541 | ≤ 0.05 |
| NRMSE tiền gửi | 0.0519 | 0.0761 | ≤ 0.1 |
| RMSE log₁₀ giá LUNA | 0.1439 | 6.3602 | ≤ 0.5 |
| RMSE log₁₀ nguồn cung LUNA | 0.0060 | 6.3004 | ≤ 0.5 |
| MAE nhóm lớn nhất | 0.0565 | 0.2343 | ≤ 0.15 |
| Sai lệch mất peg / giờ | 0.7500 | 0.7500 | ≤ 6.0 |

**Đạt toàn bộ ngưỡng ngoài mẫu: Chưa.**
Các chính sách chỉ là thí nghiệm có điều kiện trong mô hình khi các ngưỡng còn thất bại. Mức khớp trong mẫu không chứng minh mô hình dự báo được khủng hoảng. Cấu trúc được phát triển khi đã biết toàn sự kiện; đây là tách thời gian để kiểm tra tham số, không phải kiểm định cấu trúc mù.

Độ sâu giao dịch không được quan sát trực tiếp; sổ lệnh đầy đủ và giao dịch Jump chưa được công bố trong bộ dữ liệu. Lịch thay đổi năng lực native swap và thời điểm ngừng đổi là xấp xỉ, không phải tái lập từng block. Replay cũng đóng phục vụ Anchor cùng mốc ngừng native: đây là giả định thô, chưa tái hiện các lần restart hay rút còn diễn ra sau đó. Gián đoạn lịch sử không được ép vào phản thực tế. An ninh validator nằm ngoài phạm vi.


### Bộ khớp toàn sự kiện dùng cho dashboard và thí nghiệm

Bộ này dùng toàn bộ 06–15/05 và giữ cố định giữa các chính sách. Tất cả chỉ số dưới đây là trong mẫu; không thay thế bảng kiểm định theo thời gian bên trên.

| Chỉ số | Sai số toàn mẫu | Mục tiêu |
|---|---:|---:|
| MAE UST / USD | 0.0909 | ≤ 0.05 |
| NRMSE tiền gửi | 0.1113 | ≤ 0.1 |
| RMSE log₁₀ giá LUNA | 0.8613 | ≤ 0.5 |
| RMSE log₁₀ nguồn cung LUNA | 0.4196 | ≤ 0.5 |
| MAE nhóm lớn nhất | 0.1448 | ≤ 0.15 |
| Sai lệch mất peg / giờ | 47.2500 | ≤ 6.0 |

Đạt toàn bộ ngưỡng trong mẫu: **Chưa**.
Native swap: mô phỏng 6.499 tỷ UST, dữ liệu 7.491 tỷ; NRMSE khối lượng ngày 0.303. Hàm hiệu chỉnh v2 có khối lượng native theo ngày và phí tại những bước có swap thực tế.
Biểu đồ `historical_comparison.html` dùng bộ khớp toàn mẫu. Giá LUNA sau ngừng native có mức cầu còn lại được cấp bởi USD có sẵn của market maker, không tạo thêm tiền cứu trợ.

**Giới hạn cứu trợ lịch sử:** audit ghi nhận Jump chuyển 1.515.689.462 UST cho TFL, nhưng thiếu từng lệnh giao dịch. Khối lượng đó chưa được gán lịch mua riêng; lịch replay hiện chỉ có ý định mua gộp TFL và stablecoin LFG, bị chặn bởi quỹ thực tế. BTC của LFG vẫn nằm trong trần nguồn lực. Vì vậy so sánh phản thực tế không phải ước lượng nhân quả đầy đủ của một quyết định lịch sử.

## 3. Nguồn lực và chính sách

LFG: 80.394 BTC ban đầu, giới hạn dùng 80.081 BTC và giữ 313 BTC; 26.281.671 USDT + 23.555.590 USDC. TFL: giới hạn đóng góp ròng 613.616.889 USD; không coi khoản đó là tiền mặt có sẵn từ đầu. Khoản chuyển LFG/TFL/Jump được gom theo chủ sở hữu cuối cùng, không cộng trùng ngân sách. BTC bán theo giá BTCUSDT lịch sử, giả định USDT ≈ USD, trừ phí và trượt giá. BNB/AVAX và UST/LUNA không được tính thành nguồn USD bảo chứng.

Biên muộn là mặc định. Biên sớm là giả định thuận lợi trong khoảng ngày mà nguồn chứng minh được, không phải thời điểm khả dụng đã xác nhận. Bảng nguồn đầy đủ ở `data/sources.json`.

Bốn chính sách: mua UST, bổ sung thanh khoản, điều chỉnh virtual pool/native swap và hạn chế rút Anchor tạm thời. Mọi khoản mua cùng dùng một sổ tài sản. Thời điểm kích hoạt dựa trên thông tin tại thời điểm mô phỏng; không tối ưu với dữ liệu tương lai.

## 4. Kết quả thí nghiệm

| Kịch bản | Số seed | Tỷ lệ cứu vãn | UST cuối kỳ | Chi phí / tỷ USD | Tổn thất người gửi |
|---|---:|---:|---:|---:|---:|
| buy_ust | 20 | 0% | 0.0370 | 2.831 | 15.5% |
| combined | 20 | 0% | 0.0282 | 3.152 | 19.4% |
| historical | 20 | 0% | 0.0307 | 2.091 | 21.1% |
| liquidity | 20 | 0% | 0.0149 | 1.162 | 17.5% |
| native_swap | 20 | 0% | 0.0276 | 0.000 | 23.1% |
| no_rescue | 20 | 0% | 0.0174 | 0.000 | 17.5% |
| withdrawal_gate | 20 | 0% | 0.0161 | 0.000 | 17.8% |

Không kịch bản mặc định nào đạt đầy đủ tiêu chí cứu vãn trong các lần chạy đã báo cáo. Điều này không chứng minh rằng mọi chính sách lịch sử đều bất khả thi.

Độ nhạy đã kiểm tra 22 cấu hình: độ sâu UST/LUNA, phản ứng mất peg và lây lan, lịch quỹ sớm/muộn, độ trễ 15/60/360 phút, ngưỡng kích hoạt và virtual pool.

So sánh bước 5/15 phút: MAE UST = 0.0530 USD; NRMSE tiền gửi = 0.090; RMSE log₁₀ LUNA = 1.469. Sai lệch lớn cho thấy kết luận nhạy với cách rời rạc hóa.

### Đối chiếu bổ sung trong mẫu

| Giai đoạn | MAE UST | NRMSE tiền gửi | RMSE log giá LUNA | RMSE log nguồn cung |
|---|---:|---:|---:|---:|
| Trước 13/05 02:00 UTC | 0.0732 | 0.1321 | 0.9624 | 0.4285 |
| Sau mốc ngừng native xấp xỉ | 0.1337 | 0.0117 | 0.5432 | 0.3970 |

| Nguồn giá riêng | MAE UST so với mô hình | MAE so với chuỗi giá tổng hợp |
|---|---:|---:|
| BINANCE | 0.0140 | 0.0003 |
| CURVE | 0.0146 | 0.0011 |
| FTX | 0.0987 | 0.0078 |

Curve/Binance chỉ có ngày 07/05; FTX là nguồn riêng, không thay thế mục tiêu chính. Curve loại quote 3Crv; các stablecoin quote được giả định gần USD. Tương quan lệnh bán ròng với lợi suất được ghi trong `diagnostics.json`, chỉ là mô tả giao dịch, không xác định tác động nhân quả. Bảng mốc và mức độ chắc chắn nằm ở `data/processed/event_timeline.csv`.

Tiêu chí cứu vãn: peg 0,98–1,02 USD liên tục ≥ 48 giờ, phục vụ ≥95% yêu cầu rút và native swap trong cửa sổ 24 giờ, hàng đợi không tăng kéo dài, quỹ còn, rồi vượt qua 7 ngày không giải ngân mới. Phép thử kéo dài giữ giá BTC cuối kỳ; đây là stress test, không phải lịch sử.

## 5. Cách trình bày và kết luận

1. Mở dữ liệu thật: tiền gửi Anchor, mất peg và nguồn cung LUNA.
2. Giải thích vòng phản hồi ABM ↔ tồn lượng/dòng chảy.
3. Trình bày sai số trong mẫu và ngoài mẫu trước khi nói về chính sách.
4. Chạy cùng seed với lịch sử và chính sách, xem cả hàng đợi và quỹ.
5. So sánh 20 seed, biên quỹ sớm/muộn và độ trễ.
6. Kết luận theo giới hạn của dữ liệu và độ khớp; không khẳng định một chính sách chắc chắn cứu được sự kiện thật.

Nguồn: Liu, Makarov & Schoar, *Anatomy of a Run: The Terra Luna Crash* và bộ dữ liệu tái lập; [JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf); [Terra Market](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html); [Binance public data](https://github.com/binance/binance-public-data).

## 6. Hướng cải thiện độ khớp

Ưu tiên tiếp theo là đối chiếu lịch giao dịch Jump và các lần blockchain hoạt động lại, tách trạng thái Anchor khỏi native swap, rồi kiểm tra chiến lược arbitrage và độ sâu với bước nhỏ hơn. Chưa có căn cứ để gọi bản hiện tại là tái lập sát toàn bộ sự kiện. Bộ chính sách mặc định dùng biên quỹ muộn; replay dùng biên sớm, nên chênh lệch bao gồm cả giả định thời điểm khả dụng.
