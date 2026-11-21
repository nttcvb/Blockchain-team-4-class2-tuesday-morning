# BÁO CÁO ĐÁNH GIÁ ĐỊNH LƯỢNG CHÍNH SÁCH CỨU TRỢ TERRA LUNA – UST
## Đánh giá khả năng bảo vệ Peg, thanh khoản Anchor và ngăn chặn vòng xoáy tử thần dưới ràng buộc vốn hữu hạn

**Ngày lập**: 08/11/2026  
**Đơn vị thực hiện**: Nhóm Nghiên cứu & Mô phỏng Định lượng cadCAD / Fast ABM (`luna-ust-sim`)  
**Tập dữ liệu & Mô phỏng**: Khủng hoảng tháng 05/2022 (06/05/2022 – 23/05/2022, 17 ngày = 1.631 bước thời gian 15 phút)  
**Trần vốn hữu hạn nghiên cứu**: $3,0 tỷ – $3,5 tỷ USD (Theo kiểm toán thực tế JS Held: 80.081 BTC khả dụng + 49,8 triệu USD stablecoin + 613,6 triệu USD hạn mức TFL)

---

## 1. TÓM TẮT ĐIỀU HÀNH & KẾT LUẬN DỨT KHOÁT (EXECUTIVE SUMMARY & DEFINITIVE CONCLUSION)

### 1.1. Câu hỏi cốt lõi
> *Liệu hệ sinh thái Terra Luna – UST có thể được cứu vãn (giữ peg UST trong dải $[0,98; 1,02]$ USD, bảo toàn khả năng thanh toán của Anchor Protocol và ngăn chặn vòng xoáy siêu lạm phát LUNA) bằng bất kỳ gói chính sách can thiệp cứu trợ nào dưới các ràng buộc vốn bên ngoài thực tế và hữu hạn?*

### 1.2. Kết luận dứt khoát
**HỆ THỐNG KHÔNG THỂ CỨU VÃN (INSOLVENT / UNSALVAGEABLE).**

Dưới các ràng buộc vốn hữu hạn thực tế ($3,0B – $3,5B USD), **toàn bộ 10 kịch bản can thiệp (SC-01 đến SC-10)** — từ các biện pháp phòng vệ thanh khoản đơn lẻ, mua lại và tiêu hủy (buyback & burn), tường mua tập trung (concentrated bid-wall), bơm vốn đột kích đầu kỳ (frontloaded shock), đến các gói kiểm soát vốn cực đoan kết hợp ngắt mạch khẩn cấp (circuit breaker) và áp thuế rút tiền (haircut) — **đều thất bại hoàn toàn trong việc cứu vãn hệ thống (`rescued = False`, tỷ lệ sống sót 0%)**.

1. **Thâm hụt bảng cân đối kế toán không thể bù đắp**: Tại thời điểm khởi phát khủng hoảng, tổng nghĩa vụ nợ phải trả của Anchor Protocol là **$14,0 tỷ – $14,5 tỷ UST**, trong khi tổng lượng tài sản dự trữ cứu trợ tối đa của Luna Foundation Guard (LFG) và Terraform Labs (TFL) chỉ đạt tối đa **~$3,2 tỷ USD**. Lỗ hổng thanh khoản ròng vượt quá **$10,8 tỷ USD**.
2. **Vận tốc tháo chạy áp đảo độ sâu thị trường**: Áp lực rút tiền ròng từ Anchor đạt mức **$1,0 tỷ – $2,5 tỷ USD/ngày**. Trong khi đó, thanh khoản thứ cấp trên Curve 3pool và Binance chỉ có thể hấp thụ tối đa vài chục đến vài trăm triệu USD trước khi trượt giá nghiêm trọng. Bất kỳ nguồn vốn cứu trợ nào cũng bị thiêu rụi nhanh chóng trước khi chặn đứng được đà bán tháo.
3. **Cái bẫy thuật toán Mint/Burn (Algorithmic Death Spiral)**: Ngay khi nguồn vốn cứu trợ hữu hạn cạn kiệt, mọi yêu cầu quy đổi UST buộc phải quay trở lại cơ chế Native Swap trên chuỗi. Khi giá LUNA bắt đầu sụt giảm, số lượng LUNA được đúc ra để quy đổi 1 UST tăng theo cấp số nhân:
   $$\Delta S_{\text{LUNA}} = \frac{\Delta Q_{\text{UST}}}{P_{\text{LUNA}}}$$
   Đồ thị pha chuyển sang trạng thái phân kỳ kỳ dị (singularity), dẫn đến siêu lạm phát hàng chục nghìn tỷ LUNA và sụp đổ hoàn toàn về 0.

---

## 2. BẢNG SO SÁNH KẾT QUẢ ĐỊNH LƯỢNG TOÀN DIỆN (COMPREHENSIVE RESULTS MATRIX)

Dữ liệu dưới đây được trích xuất trực tiếp từ kết quả mô phỏng thực nghiệm 17 ngày (`outputs/experiments/summary.csv` và `runs.csv`, seed chuẩn hóa 42, 1.631 bước tính toán):

| Mã kịch bản | Tên chính sách | Giờ giữ Peg (`peg_hours`) | Giờ vận hành (`operational_hours`) | Giá UST cuối kỳ (USD) | Giá UST thấp nhất (USD) | Tiền gửi Anchor cuối kỳ (USD) | Hàng đợi rút tồn đọng (UST) | Cung LUNA cuối kỳ (Tokens) | Giá LUNA cuối kỳ (USD) | Vốn cứu trợ đã chi (USD) | Số BTC đã bán | Đóng góp TFL (USD) | Tổn thất người gửi | Tỷ lệ phục vụ rút | Tỷ lệ cứu vãn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **SC-01** | `sc01_baseline_no_rescue` | 9,75 | 9,75 | 0,002325 | 0,000027 | 7.401.157 | 7.401.121 | 14.014.988.409.715 | 0,000266 | 0 | 0,00 | 613.616.889 | 21,03% | 99,95% | **0% (False)** |
| **SC-02** | `sc02_staggered_tranches` | 11,75 | 11,75 | 0,001193 | 0,000018 | 7.928.854 | 7.928.816 | 3.356.422.960.215 | 0,001151 | 1.500.000.000 | 45.394,09 | 613.616.889 | 21,08% | 99,94% | **0% (False)** |
| **SC-03** | `sc03_concentrated_bidwall` | 11,00 | 11,00 | 0,001083 | 0,000016 | 8.268.341 | 8.268.301 | 2.650.756.148.189 | 0,001522 | 2.500.000.000 | 77.137,42 | 613.616.889 | 21,44% | 99,94% | **0% (False)** |
| **SC-04** | `sc04_buyback_burn` | 11,75 | 11,75 | 0,001580 | 0,000023 | 8.547.249 | 8.547.208 | 4.953.541.806.805 | 0,000792 | 2.000.000.000 | 61.272,32 | 613.616.889 | 21,69% | 99,94% | **0% (False)** |
| **SC-05** | `sc05_tiered_gates` | 11,00 | 8,75 | 0,001212 | 0,000020 | 17.421.869 | 17.421.785 | 4.576.746.186.617 | 0,000749 | 0 | 0,00 | 613.616.889 | 29,17% | 99,88% | **0% (False)** |
| **SC-06** | `sc06_market_defense` | 8,50 | 8,50 | 0,011093 | 0,000036 | 39.013.438 | 39.013.251 | 494.149.176.140.388 | 0,000005 | 0 | 0,00 | 613.616.889 | 17,85% | 99,72% | **0% (False)** |
| **SC-07** | `sc07_combined_realistic` | 10,25 | 8,75 | 0,002274 | 0,000041 | 50.457.163 | 50.456.921 | 15.725.792.964.870 | 0,000187 | 2.500.000.000 | 77.137,42 | 613.616.889 | **17,61%** | 99,64% | **0% (False)** |
| **SC-08** | `sc08_frontloaded_shock` | **45,50** | **45,50** | 0,001569 | 0,000024 | 12.011.633 | 12.011.576 | 6.361.279.628.605 | 0,000513 | 663.454.150 | 0,00 | 613.616.889 | 21,12% | 99,91% | **0% (False)** |
| **SC-09** | `sc09_circuit_breaker` | 9,75 | 9,75 | 0,002102 | 0,000034 | 13.510.404 | 13.510.339 | 14.198.913.850.447 | 0,000216 | 0 | 0,00 | 613.616.889 | 19,43% | 99,90% | **0% (False)** |
| **SC-10** | `sc10_maximum_extreme` | 42,25 | 18,50 | 0,002033 | 0,000033 | **221.322.901** | **221.321.838** | 10.423.578.396.079 | 0,000313 | **3.198.847.562** | **80.081,00** | 613.616.889 | 23,21% | 98,43% | **0% (False)** |

---

## 3. PHÂN TÍCH CHI TIẾT CƠ CHẾ THẤT BẠI CỦA CÁC CHÍNH SÁCH (DETAILED MECHANISM FAILURE ANALYSIS)

### 3.1. Cái bẫy "Mua lại không tiêu hủy" (Unburned Buyback Trap) vs "Mua lại & Tiêu hủy ngay lập tức" (Buyback & Burn - SC-04)

- **Cơ chế cái bẫy Unburned Buyback Trap**:
  Trong lịch sử ngày 08–10/05/2022, tổ chức cứu trợ (LFG và các Market Maker đối tác như Jump Crypto) đã giải ngân hơn $1,5 tỷ USD để mua gom UST trên các sàn giao dịch tập trung (Binance, FTX) và Curve. Tuy nhiên, lượng UST mua vào không được đốt khỏi nguồn cung lưu hành trên chuỗi (`ust_supply`), mà chỉ được chuyển vào ví dự trữ của TFL hoặc giữ trên tài khoản sàn.
  Về mặt kế toán tiền tệ, hành vi này không hề làm giảm tổng nghĩa vụ nợ (liabilities) của hệ sinh thái Terra. Lượng UST này vẫn tồn tại trong trạng thái tiềm năng, sẵn sàng bị xả ngược trở lại thị trường hoặc bị các chủ nợ thanh lý.
- **Tại sao ngay cả khi Tiêu hủy ngay lập tức (SC-04) vẫn thất bại?**:
  Trong SC-04, mô hình áp dụng tính năng bắt buộc `burn_acquired_ust = True`: mỗi đơn vị UST mua được từ $2,0 tỷ USD ngân sách cứu trợ đều bị lập tức tiêu hủy vĩnh viễn khỏi `ust_supply` và trừ khỏi sổ kế toán tài sản quỹ (`fund_ust`).
  Kết quả thực nghiệm cho thấy:
  1. $2,0 tỷ USD vốn cứu trợ đã bán 61.272,32 BTC để mua và tiêu hủy khoảng ~2,0 tỷ UST.
  2. Nguồn cung LUNA cuối kỳ được kiềm chế ở mức 4,95 nghìn tỷ token (thấp hơn nhiều so với 14,01 nghìn tỷ token của SC-01).
  3. **Tuy nhiên**, tổng lượng UST đang lưu hành trước khủng hoảng là **18,7 tỷ UST**, trong đó Anchor Protocol nắm giữ hơn **14,0 tỷ UST**. Tiêu hủy 2,0 tỷ UST chỉ làm giảm **~10,7%** tổng áp lực nợ. Khi 12 tỷ UST còn lại tiếp tục tháo chạy khỏi Anchor, không còn bất kỳ dòng tiền cứu trợ nào đỡ giá, UST vẫn rớt thẳng về **$0,00158 USD** và thời gian giữ peg chỉ kéo dài thêm đúng **2,0 giờ** (từ 9,75h lên 11,75h).

### 3.2. Quy mô tường mua tập trung (Concentrated Bid-Wall Sizing - SC-03)

- **Ý tưởng thiết kế**:
  Thay vì đuổi theo giá thị trường (market orders) gây hao hụt vốn do trượt giá (slippage), SC-03 tập trung toàn bộ hạn mức $2,5 tỷ USD để lập một tường mua khổng lồ (concentrated bid-wall) tại ngưỡng `target_peg = 0.985 USD`.
- **Diễn biến thực nghiệm**:
  - Tường mua tạo ra một điểm tựa tâm lý và thanh khoản cực mạnh trong những giờ đầu tiên, hấp thụ toàn bộ lực bán hoảng loạn từ Curve 3pool và giữ giá UST dao động trên 0,985 USD.
  - Tuy nhiên, tường mua nhanh chóng biến thành "vùng thanh khoản miễn phí" cho các cá voi Anchor rút vốn. Với tốc độ rút từ Anchor trung bình **$200M – $350M/giờ**, tường mua trị giá $2,5 tỷ USD bị bào mòn và **xuyên thủng hoàn toàn chỉ sau đúng 11,0 giờ** (tiêu tốn 77.137,42 BTC).
  - Ngay sau khi bức tường $2,5 tỷ USD bị quét sạch, sổ lệnh phía dưới hoàn toàn trống rỗng (liquidity vacuum). Giá UST lập tức lao dốc thẳng đứng không phanh xuống $0,00108 USD.
- **Bài học định lượng**:
  Tường mua thụ động không thể tạo ra trạng thái cân bằng mới nếu không có dòng vốn ngoại sinh liên tục bù đắp vào dự trữ. Tường mua hữu hạn chỉ đóng vai trò hoãn lại thời điểm sụp đổ (11,0 giờ so với 9,75 giờ baseline).

### 3.3. Đột kích bơm vốn đầu kỳ (Frontloaded Capital Injection - SC-08)

- **Cơ chế triển khai**:
  SC-08 áp dụng nguyên lý can thiệp sốc (shock therapy): thay vì giải ngân nhỏ giọt theo tranches kéo dài nhiều ngày, hệ thống tung ra hạn mức giải ngân cực đại **$800 triệu USD/giờ** ngay trong 4 giờ đầu tiên khi depeg vừa chớm xuất hiện (tổng giải ngân thực tế $663,45 triệu USD).
- **Kết quả vượt trội nhưng bi kịch**:
  - SC-08 đạt **thời gian giữ peg dài nhất trong toàn bộ các kịch bản can thiệp vốn đơn lẻ: 45,50 giờ** (gần 2 ngày trọn vẹn, gấp 4,6 lần so với kịch bản cơ sở 9,75h).
  - Cú can thiệp vũ lực ban đầu đã đè bẹp hoàn toàn đợt tấn công thanh khoản thứ nhất trên Curve, giữ giá UST bám sát 0,99 – 1,00 USD xuyên suốt ngày 07/05 và phần lớn ngày 08/05.
- **Tại sao vẫn thất bại?**:
  - Cơn hoảng loạn cơ cấu (structural bank run) không biến mất mà chỉ bị nén lại. Khi người gửi tiền Anchor nhận thấy tốc độ giải ngân dự trữ của LFG chạm trần trần hạn mức và không còn nguồn USD mới bổ sung, làn sóng rút tiền đợt 2 (Wave 2 Bank Run) bùng nổ dữ dội vào ngày 09/05.
  - Lúc này, dự trữ đầu kỳ đã tiêu tốn $663,5M, không còn đủ xung lực để chống đỡ đợt sóng rút tiền thứ hai trị giá hàng tỷ USD. Kết quả là sau 45,5 giờ, hệ thống gãy peg thảm khốc và rớt về $0,00157 USD.

### 3.4. Kiểm soát vốn và Phòng vệ thị trường (Capital Controls & Market Defense - SC-05, SC-06, SC-07, SC-09, SC-10)

Các chính sách cấu trúc và phi tiền tệ mang lại những tác động định lượng rõ rệt:

1. **Cổng rút tiền phân tầng (Tiered Withdrawal Gates - SC-05)**:
   - Thắt chặt hạn mức rút của Anchor từ 100% xuống 20%/ngày, và siết xuống 5%/ngày khi depeg sâu.
   - Giúp bảo toàn **$17,42 triệu USD** tiền gửi trong Anchor (gấp 2,35 lần so với $7,40M của baseline).
   - *Hạn chế*: Khiến tỷ lệ tổn thất người gửi tăng lên **29,17%** (cao nhất trong các kịch bản) do tiền gửi bị giam trong giao thức trong khi giá trị tài sản bốc hơi.
2. **Phòng vệ thị trường & Chặn Arbitrage (Market Defense - SC-06)**:
   - Nâng phí spread khẩn cấp lên 15% (`emergency_spread_rate = 0.15`) và bóp nghẹt công suất kinh doanh chênh lệch giá (`arb_capacity_multiplier = 0.167`).
   - Cắt đứt động lực của arbitrageurs mua UST rẻ trên sàn mang về chain đúc LUNA xả kiếm lời.
   - Giúp giá UST cuối kỳ đạt **$0,011093 USD (cao nhất trong tất cả 10 kịch bản, gấp 4,8 lần baseline)** và giữ lại được **$39,01 triệu USD** trong Anchor.
   - *Hạn chế*: Làm dồn ứ hàng đợi UST trên thị trường thứ cấp do thiếu lực cầu mua arbitrage, LUNA cuối cùng vẫn bị pha loãng lên 494 nghìn tỷ token qua các kênh thoát hiểm khác.
3. **Gói kết hợp thực tế (Combined Realistic - SC-07)**:
   - Kết hợp tường mua 0,985 + tiêu hủy UST mua được + cổng rút tiền phân tầng + spread khẩn cấp 15%.
   - Đạt **tỷ lệ tổn thất người gửi thấp nhất lịch sử: 17,61%** (so với 21,03% baseline).
   - Bảo toàn **$50,46 triệu USD** trong Anchor (gấp 6,8 lần baseline).
   - *Hạn chế*: Tiêu tốn sạch $2,5 tỷ USD ngân sách, sau 10,25h peg vẫn gãy hoàn toàn.
4. **Ngắt mạch thị trường khẩn cấp (Circuit Breaker - SC-09)**:
   - Đóng băng hoàn toàn Anchor và Native Swap trong 48 giờ ngay khi giá UST rớt dưới 0,90 USD.
   - Tỷ lệ phục vụ lệnh native giảm xuống **60,50%**, ngăn chặn việc đúc LUNA trong 2 ngày đóng băng.
   - *Hạn chế*: Ngay khi mở lại chuỗi sau 48h, tâm lý hoảng loạn tích tụ khiến dòng tiền tháo chạy với cường độ dữ dội hơn, đưa giá UST về lại quỹ đạo sụp đổ ban đầu.
5. **Gói can thiệp cực đoan tối đa (Maximum Extreme Package - SC-10)**:
   - Kết hợp toàn bộ các vũ khí: Bơm vốn sốc đầu kỳ + Tường mua + Đóng băng Circuit Breaker + Cổng rút tiền nghiêm ngặt + Áp thuế rút tiền khẩn cấp 20% (Redemption Haircut) để tiêu hủy trực tiếp nghĩa vụ nợ + Phí spread khẩn cấp.
   - Tiêu thụ trọn vẹn **$3,198 tỷ USD vốn cứu trợ (bán sạch 80.081 BTC - 100% trần dự trữ)**.
   - Đạt kết quả phòng vệ tài sản kỷ lục: **Bảo toàn $221,32 triệu USD trong Anchor (gấp 30 lần baseline $7,40M)**.
   - Duy trì giá UST trên các ngưỡng an toàn trong **42,25 giờ**.
   - *Kết luận*: Bất chấp mọi nỗ lực cực đoan nhất và đốt sạch toàn bộ kho tài sản dự trữ quốc gia, hệ thống vẫn không thể giữ peg sau khi nguồn vốn cạn kiệt. Giá UST cuối kỳ vẫn là $0,00203 USD, và tiêu chuẩn cứu vãn `rescued` vẫn là **False**.

---

## 4. CHỨNG MINH TOÁN HỌC & BẤT BIẾN KẾ TOÁN VỀ SỰ BẤT KHẢ CỨU (MATHEMATICAL & INVARIANT PROOF OF INSOLVENCY)

Khả năng cứu vãn của Terra Luna – UST không phải là một vấn đề xác suất hay tâm lý học hành vi đơn thuần, mà là một **sự bất khả thi toán học xuất phát từ sự mất cân đối cấu trúc bảng cân đối kế toán**.

### 4.1. Bất đẳng thức thâm hụt cơ bản (Fundamental Balance-Sheet Insolvency)
Gọi:
- $L_{\text{anchor}}(t)$: Tổng nghĩa vụ nợ của Anchor Protocol đối với người gửi tiền tại thời điểm $t$. Tại $t_0$ (06/05/2022), $L_{\text{anchor}}(t_0) \approx \$14,02 \times 10^9 \text{ UST}$.
- $Q_{\text{circ}}(t)$: Lượng UST lưu hành ngoài Anchor. $Q_{\text{circ}}(t_0) \approx \$4,70 \times 10^9 \text{ UST}$.
- Tổng nghĩa vụ quy đổi cam kết của hệ thống:
  $$L_{\text{total}}(t_0) = L_{\text{anchor}}(t_0) + Q_{\text{circ}}(t_0) \approx \$18,72 \times 10^9 \text{ USD equivalents}$$
- $R_{\max}$: Tổng nguồn vốn ngoại sinh hữu hạn tối đa của quỹ cứu trợ (LFG + TFL). Dựa trên biên bản kiểm toán của JS Held:
  $$R_{\max} = V_{\text{BTC}} + V_{\text{stables}} + V_{\text{TFL}}$$
  Với $V_{\text{BTC}} = 80.081 \times \bar{P}_{\text{BTC}} \approx 80.081 \times \$32.000 \approx \$2,56 \times 10^9 \text{ USD}$.
  $$V_{\text{stables}} \approx \$0,05 \times 10^9 \text{ USD}$$
  $$V_{\text{TFL}} \le \$0,613 \times 10^9 \text{ USD}$$
  $$\implies R_{\max} \approx \$3,22 \times 10^9 \text{ USD}$$

**Định lý 1 (Bất đẳng thức Thâm hụt Tuyệt đối)**:
$$\Delta_{\text{insolvency}} = L_{\text{anchor}}(t_0) - R_{\max} \ge \$14,02\text{B} - \$3,22\text{B} = \$10,80 \times 10^9 \text{ USD} > 0$$
Hệ thống thâm hụt tài sản bảo chứng tối thiểu **$10,80 tỷ USD** so với riêng nghĩa vụ Anchor, và thâm hụt **$15,50 tỷ USD** so với tổng cung UST.

### 4.2. Giới hạn thời gian cạn kiệt thanh khoản (Liquidity Exhaustion Time Bound)
Gọi $w(t)$ là tốc độ tháo chạy ròng (net withdrawal run velocity) từ Anchor ra thị trường thứ cấp.
Từ dữ liệu thực tế và mô phỏng ABM của 1.000 nhà đầu tư đại diện:
$$w(t) \ge \$1,20 \times 10^9 \text{ USD/ngày} = \$50 \times 10^6 \text{ USD/giờ}$$
Thời gian tối đa $T_{\text{exhaust}}$ mà bất kỳ chính sách can thiệp vốn nào có thể duy trì mua đỡ giá trước khi cạn kiệt hoàn toàn dự trữ $R_{\max}$ bị chặn trên bởi:
$$T_{\text{exhaust}} \le \frac{R_{\max}}{\int_{0}^{T_{\text{exhaust}}} w(t) dt} \le \frac{\$3,22 \times 10^9}{\$1,20 \times 10^9 / \text{ngày}} \approx 2,68 \text{ ngày} \approx 64,4 \text{ giờ}$$

Kết quả mô phỏng thực nghiệm đã kiểm chứng chính xác giới hạn lý thuyết này:
- Kịch bản SC-08 (bơm vốn sốc) kéo dài được **45,5 giờ**.
- Kịch bản SC-10 (can thiệp cực đoan tối đa) duy trì được **42,25 giờ**.
Không có kịch bản nào vượt qua được ngưỡng chặn trên lý thuyết 64,4 giờ.

### 4.3. Bất biến quy đổi và Điểm kỳ dị siêu lạm phát (Hyperinflation Singularity)
Khi quỹ cứu trợ cạn kiệt ($R(t) = 0$), toàn bộ áp lực rút vốn còn lại ($> \$10\text{B}$) buộc phải xả qua cơ chế tạo lập thị trường tự động trên chuỗi (Terra Native Virtual AMM Pool).
Cơ chế bảo toàn danh nghĩa của Terra quy định: 1 UST luôn đổi được 1 USD giá trị LUNA:
$$\frac{d S_{\text{LUNA}}}{dt} = \frac{1}{P_{\text{LUNA}}(t)} \cdot \left( \frac{d Q_{\text{UST}}}{dt} \right)_{\text{swap}}$$
Trong đó giá thị trường của LUNA chịu tác động giảm giá từ áp lực pha loãng cung:
$$P_{\text{LUNA}}(t) = f\left(\frac{M_{\text{LUNA}}}{S_{\text{LUNA}}(t)}\right)$$
Khi $S_{\text{LUNA}}$ tăng mạnh, $P_{\text{LUNA}} \to 0$, kéo theo đạo hàm bậc nhất của cung tiền tiến tới vô cực:
$$\lim_{P_{\text{LUNA}} \to 0} \frac{d S_{\text{LUNA}}}{dt} = +\infty$$
Đây là điểm kỳ dị toán học (finite-time singularity). Số lượng LUNA tăng vọt từ 725 triệu token lên **14.014 tỷ token (SC-01)**, thậm chí **494.149 tỷ token (SC-06)**, phá hủy hoàn toàn giá trị của LUNA và triệt tiêu vĩnh viễn khả năng làm tài sản thế chấp cho UST.

---

## 5. ĐÁNH GIÁ TỔNG THỂ & KHUYẾN NGHỊ THIẾT KẾ HỆ THỐNG (SYSTEM DESIGN LESSONS)

1. **Thất bại của mô hình Stablecoin thuật toán thế chấp nội sinh (Endogenous Collateral)**:
   Một đồng tiền ổn định không thể được bảo đảm chỉ bằng một tài sản có giá trị phụ thuộc vào chính sự kỳ vọng của hệ sinh thái đó. Khi niềm tin suy giảm, tài sản bảo chứng nội sinh (LUNA) bốc hơi cùng lúc với tài sản nợ (UST), tước bỏ mọi khả năng tự cân bằng.
2. **Ảo tưởng về quỹ dự trợ ngoại sinh không đủ quy mô**:
   Khoản dự trữ $3,2 tỷ USD của LFG trông có vẻ khổng lồ trên phương tiện truyền thông, nhưng khi so sánh tương quan với quy mô tiền gửi của một "ngân hàng bóng tối" (Shadow Bank) không có bảo hiểm tiền gửi như Anchor Protocol ($14 tỷ USD), tỷ lệ dự trữ bắt buộc thực tế chỉ đạt **~22%**. Trong một cuộc tháo chạy hoảng loạn (bank run), tỷ lệ dự trữ này chỉ đủ cầm cự dưới 48 giờ.
3. **Sự đánh đổi khốc liệt của Cổng kiểm soát vốn (Capital Controls)**:
   Việc áp đặt cổng rút tiền khắt khe (SC-05, SC-10) tuy bảo vệ được một phần số dư tiền mặt trong giao thức ($221M so với $7M), nhưng lại biến giao thức thành một "con tin thanh khoản", làm gia tăng tỷ lệ thiệt hại của người gửi tiền và phá vỡ lời hứa cốt lõi về khả năng thanh toán tức thời theo mệnh giá của một stablecoin.

**KẾT LUẬN CUỐI CÙNG**:
Terra Luna – UST vào tháng 05/2022 là một cấu trúc tài chính mất khả năng thanh toán tiềm tàng (structurally insolvent). Khi quy mô hệ thống vượt quá $10 tỷ USD mà không có cơ chế tái cấp vốn vô hạn từ Ngân hàng Trung ương (Lender of Last Resort), **mọi nỗ lực cứu trợ bằng nguồn vốn hữu hạn tư nhân đều là vô ích**.
