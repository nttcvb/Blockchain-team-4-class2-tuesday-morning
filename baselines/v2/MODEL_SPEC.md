# Đặc tả mô hình để trình bày và sửa tiếp

## 1. Ranh giới, thời gian và dữ liệu

Khởi tạo từ snapshot 06/05/2022 lúc 00:14 UTC, cập nhật từ 00:15. Bước mặc định 15 phút; có đối chiếu 5 phút. Cửa sổ lịch sử kết thúc 16/05 lúc 00:00 (không gồm điểm cuối). Tail kéo dài 7 ngày giữ giá BTC cuối cửa sổ và ngừng giải ngân mới. Cấu hình bắt đầu muộn vẫn chạy warmup từ snapshot rồi mới xuất đoạn được chọn.

Giá UST/LUNA, tiền gửi Anchor, nguồn cung LUNA và native swaps từ bộ tái lập được dùng làm mục tiêu, không nhập trực tiếp làm giá ở mỗi bước. Giá BTC là điều kiện thị trường ngoại sinh. A/B là hai chuỗi hành động khởi phát quan sát được, không là mô hình suy diễn nguyên nhân khủng hoảng.

## 2. Tác nhân và tồn lượng

| Thành phần | Trạng thái và hành động |
|---|---|
| 1.000 người gửi đại diện | Quyền đòi UST, hàng đợi rút, UST trong ví, USD đã nhận; quyết định rút theo quan sát trễ |
| 20 arbitrageurs | USD và LUNA; mua UST, đổi native, bán LUNA hoặc giữ lại khi thiếu thanh khoản |
| Anchor | UST tiền mặt, dư nợ, UST của người vay, quỹ lãi; trả lãi, nhận hoàn nợ, phục vụ rút |
| Market maker tổng hợp | USD/UST/LUNA hữu hạn; là phía đối ứng của lệnh mua/bán |
| Nhà đầu tư bên ngoài | USD/UST hữu hạn; mua khi UST bị chiết khấu |
| LFG + TFL | BTC/USD bị khóa hoặc khả dụng, UST/LUNA mua về, chi phí tích lũy |

Top 20 ví giữ riêng. Các ví còn lại được lấy mẫu phân tầng 6 nhóm và mang trọng số để giữ tổng vốn trước khủng hoảng. Phần chênh lệch với tổng tiền gửi protocol là người gửi tổ chức tổng hợp. 20 arbitrageurs chia vốn và lệnh theo tỷ trọng vốn; chưa có chiến lược khác nhau giữa arbitrageurs, nên không diễn giải kết quả như nghiên cứu cạnh tranh vi mô.

USD thị trường ban đầu là giả định: market maker 25 tỷ, arbitrage 150 triệu và người mua bên ngoài 1 tỷ. Đây là vốn của phía đối ứng, tách hoàn toàn khỏi trần cứu trợ LFG/TFL; không phải quy mô thị trường đã xác minh. Độ sâu được hiệu chỉnh, nhưng nguồn vốn và cấu trúc phía đối ứng chưa được nhận dạng duy nhất bởi dữ liệu.

## 3. ABM: hành vi rút

Với tác nhân i, tín hiệu gồm chiết khấu UST, rút trong giờ gần nhất, giảm giá LUNA và hàng đợi, lấy theo độ trễ của ví:

```text
eta_i = h0 + h_size × (log_size_i − 3)
      + h_discount × discount_i + h_outflow × outflow_i
      + h_luna × luna_fall_i + h_queue × queue_fraction_i
p_i(dt) = 1 − (1 − logistic(eta_i))^(dt/15)
withdraw_i = max(claim_i − queued_i, 0) × Bernoulli(p_i)
```

Khi hiệu chỉnh, Bernoulli được thay bằng kỳ vọng p_i để mục tiêu tối ưu ổn định. Đây không phải cùng kết quả trung bình của mô hình phi tuyến ngẫu nhiên; bộ 20 seed kiểm tra khác biệt đó. Trong mỗi bước, mọi tác nhân nhận đúng một số ngẫu nhiên, giúp so sánh chính sách dùng cùng seed.

## 4. System Dynamics: tồn lượng và dòng chảy

```text
Anchor cash' = cash + loan repayments + funded interest − served withdrawals + redeposits
Anchor claims' = claims + funded interest − served withdrawals + redeposits
Loan balance' = loan balance − repayments
Yield reserve' = reserve + actual UST income − funded interest
Withdrawal queue' = queue + new requests − served withdrawals
UST supply' = UST supply − native UST burned
LUNA supply' = LUNA supply + gross native LUNA minted
```

Hoàn nợ được giới hạn bởi UST thật của người vay. Lãi được giới hạn bởi quỹ lãi. Rút được phục vụ theo tỷ lệ đồng đều, giới hạn bởi thanh khoản và chính sách gate. Tiền gửi là quyền đòi, không được đếm như token mới.

Virtual pool: base B, độ lệch x = B + delta, k = B². Với UST q đổi vào, giá trị LUNA nhận theo pool là `(k/x) × q/(x+q)`. LUNA phát hành gộp là `q/oracle_LUNA`; phần chênh với LUNA nhận được ghi vào tài khoản phí. delta phục hồi theo `exp(−dt/recovery_minutes)`. Đây là quy đổi USD tổng hợp của cơ chế Terra, không tái tạo SDR hay phí từng block.

Arbitrageurs chọn kích thước q tối ưu theo marginal quote, rồi giới hạn bởi vốn, UST sẵn có, capacity và tác động giá UST. Lệnh không sinh lời ở quote bị hủy. LUNA chưa bán được nằm trong kho arbitrageur; không coi toàn bộ LUNA mint là tiền đã thu về.

Giá UST thay đổi theo lệnh bán ròng / độ sâu và biến động tín hiệu tin cậy `min(1, market_cap_LUNA / UST_supply)`. Tín hiệu này không phải tài sản bảo chứng. Giá LUNA thay đổi theo bán ròng / độ sâu token và lợi suất BTC. Khi native ngừng hoặc yên ≥6 giờ, có mức bid còn lại bằng một phần USD đang có của market maker / nguồn cung LUNA. Đây là giả định hành vi cần kiểm tra độ nhạy, không có USD mới.

## 5. Sổ tài sản và thứ tự cadCAD

Sáu PSUB có thứ tự cố định: quan sát → cứu trợ → hành vi → Anchor → thị trường → kế toán. cadCAD giữ một biến state `book` chứa các tồn lượng và mảng tác nhân. Trạng thái cũ không bị sửa tại chỗ. Bộ chạy nhanh gọi đúng các hàm này; chỉ dùng khi tối ưu tham số.

Kiểm tra mỗi bước:

- Tổng UST trong mọi tài khoản bằng nguồn cung UST.
- Tổng LUNA, gồm phí, bằng nguồn cung LUNA.
- USD bằng vốn đầu kỳ + vốn TFL được mở + USD từ bán BTC; phí được giữ trong tài khoản riêng.
- Anchor cash + loan balance = tổng quyền đòi.
- BTC bị khóa + khả dụng + đã bán = 80.394; ít nhất 313 BTC được giữ.
- Tồn lượng không âm; đóng góp ròng TFL ≤613.616.889 USD.

Giá thay đổi không tạo USD. LFG/TFL/Jump chuyển nội bộ không tạo ngân sách mới. Kiểm tra dùng cả sai số tuyệt đối và tương đối để chịu được số rất lớn khi LUNA siêu lạm phát.

## 6. Giao diện chính sách

Chính sách lấy trigger giá hoặc thời gian UTC, số bước xác nhận, độ trễ, thời hạn, nguồn LFG/TFL và phân bổ. Bốn hành động là mua UST, cam kết vốn thanh khoản, đổi pool/recovery và hạn chế rút. Khi kết hợp mua UST/thanh khoản, mỗi hành động lấy tối đa tỷ lệ đã chọn của quỹ khả dụng ở đầu bước, đồng thời chịu hạn mức tốc độ chi riêng. Tỷ lệ chi tích lũy còn phụ thuộc thời hạn và nhu cầu mua. Các hành động dùng chung tài khoản quỹ. Mua UST chỉ chuyển token sang quỹ; không đốt token.

Replay lịch sử có mốc thay capacity và ngừng giao dịch xấp xỉ; phản thực tế không bị ép các mốc dừng này. Vì bỏ qua validator và mức độ hoạt động blockchain thực, tiêu chí “cứu vãn” chỉ nói về tài chính và khả năng phục vụ trong mô hình.

Replay hiện dừng phục vụ rút Anchor cùng mốc đóng native, chưa mô hình các lần restart. Đây là giả định đơn giản hóa cần sửa khi nghiên cứu độ khớp cao hơn; xem sai số trước/sau mốc này trong báo cáo. Độ trễ thực thi chung của arbitrage được xấp xỉ bằng oracle một phút trong bước lớn; chưa có hàng đợi và độ trễ khác nhau từng arbitrageur.

Audit có chuyển 1.515.689.462 UST từ Jump sang TFL nhưng thiếu lịch từng giao dịch; mô hình chưa có riêng chuỗi lệnh cho số UST này. Replay cũng không mô hình khoản hoán đổi quản trị khoảng 883,5 triệu UST. Phải đọc các giới hạn này cùng sai số native/supply; không dùng kết quả để khẳng định nguyên nhân hay chính sách cứu được lịch sử thật.

## 7. Hiệu chỉnh và thí nghiệm

Hai bộ tham số: train 06–10/05 và kiểm tra tham số 11–15/05; full-fit 06–15/05 chỉ dùng trình diễn trong mẫu. Cấu trúc đã biết toàn sự kiện nên kiểm tra thời gian không phải cấu trúc ngoài mẫu độc lập. Hàm tối ưu v2 dùng giá UST, tiền gửi, log giá/nguồn cung LUNA, vốn nhóm còn lại, thời điểm depeg, khối lượng native theo ngày và phí tại những bước có swap thật.

7 kịch bản ×20 seed: replay, không cứu trợ, mua UST, thanh khoản, native, gate và kết hợp. Dùng cùng bộ tham số và seed giữa kịch bản. Độ nhạy: độ sâu, hành vi, quỹ sớm/muộn, delay, threshold và pool. Khoảng 5–95% chỉ phản ánh seed; không là khoảng tin cậy về lịch sử.

Cứu vãn đòi peg trong [0,98;1,02] liên tục 48h sau khởi phát, phục vụ rút/native ≥95% cửa sổ 24h, hàng đợi không tăng đáng kể, quỹ còn và toàn bộ 7 ngày ngừng hỗ trợ vẫn đạt điều kiện. Đóng rút để giữ giá đơn thuần không đạt tiêu chí. Kết quả không cứu được trong các preset không chứng minh mọi chính sách đều bất khả thi.
