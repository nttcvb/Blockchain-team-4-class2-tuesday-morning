# Kế hoạch mô phỏng Luna–UST bằng cadCAD, kết hợp ABM và System Dynamics

## 1. Mục tiêu, phạm vi và dữ liệu

Xây dựng **mô hình nhỏ phục vụ bài nhóm môn học**, có dashboard để:

- Tái hiện quá trình rút tiền Anchor, mất peg UST và vòng xoáy phát hành LUNA.
- Đối chiếu kết quả mô phỏng với dữ liệu thật.
- Thay đổi chính sách **sau khi khủng hoảng bắt đầu**, trong giới hạn nguồn lực lịch sử của **LFG và TFL**.
- Đánh giá khả năng phục hồi peg và hoạt động rút/đổi, cùng chi phí và tác dụng phụ.

**Quy mô mặc định:** 1.000 tác nhân người gửi đại diện, 20 tác nhân arbitrage, một bộ phận tạo lập thị trường tổng hợp và hai bên cứu trợ LFG/TFL. Mô phỏng từ ngày **06–15/05/2022**, bước thời gian **15 phút**, dùng UTC để đồng bộ dữ liệu.

Cơ sở dữ liệu là bộ tái lập nghiên cứu trong thư mục hiện tại; nguồn gốc và đơn vị được mô tả trong [Datasets.md](</D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/Datasets.md>).

| Dữ liệu hiện có | Vai trò trong mô hình |
|---|---|
| Giá UST/LUNA theo phút | Khởi tạo, hiệu chỉnh và đánh giá đường giá |
| `epoch_state_fig10` | Đo tiền gửi Anchor thực tế và tỷ giá aUST/UST |
| Giao dịch deposit/withdraw của Anchor | Hiệu chỉnh thời điểm, cường độ rút tiền và cú sốc đầu kỳ |
| Tài sản trước khủng hoảng, thông tin ví | Tạo tác nhân khác nhau về quy mô và tốc độ phản ứng |
| Native swaps, nguồn cung LUNA | Hiệu chỉnh đổi UST–LUNA, phí và tốc độ phát hành |
| Curve/Binance ngày 07/05 | Kiểm tra tác động giao dịch và diễn biến mất peg ban đầu |
| Trạng thái và dòng tiền Anchor | Khởi tạo thanh khoản, dư nợ và quỹ trả lãi |

**Bổ sung tối thiểu:** bảng tài sản và giao dịch cứu trợ từ báo cáo JS Held; giá BTC lịch sử từ [dữ liệu công khai Binance](https://github.com/binance/binance-public-data). Không cần xây lại toàn bộ blockchain.

Mô hình gom thị trường giao dịch thành thị trường UST và LUNA tổng hợp. Không mô phỏng đầy đủ mạng validator, mọi sàn giao dịch hay toàn bộ DeFi.

## 2. Thiết kế cơ chế ABM + System Dynamics

### ABM: ai hành động và vì sao?

**Người gửi Anchor**

- Chia thành sáu nhóm tài sản trước khủng hoảng: dưới 1.000; 1.000–10.000; 10.000–100.000; 100.000–1 triệu; 1–10 triệu; trên 10 triệu UST.
- Giữ riêng 20 ví lớn nhất trước sự kiện; lấy mẫu có trọng số cho các ví còn lại, bảo toàn tổng tiền gửi và mức tập trung tài sản.
- Mỗi tác nhân có tiền gửi, UST trong ví, mức nhạy với rủi ro và độ trễ quan sát.
- Các hành động gồm giữ tiền gửi, yêu cầu rút, giữ UST, bán UST và gửi lại khi rủi ro giảm.

Xác suất yêu cầu rút tiền sử dụng hàm logistic:

\[
p_{i,t}=\sigma\!\left[
\alpha+\beta_w\log(1+w_i)
+\beta_d(1-P^{UST}_{t-\ell_i})
+\beta_o O_{t-\ell_i}
+\beta_l R^{LUNA}_{t-\ell_i}
+\beta_q Q_{t-\ell_i}
\right]
\]

Trong đó:

- \(w_i\): tài sản trước khủng hoảng.
- \(\ell_i\): độ trễ quan sát.
- \(O\): tỷ lệ rút tiền trong một giờ gần nhất.
- \(R^{LUNA}\): mức giảm giá LUNA trong một giờ.
- \(Q\): tỷ lệ yêu cầu rút chưa được xử lý.

Hiệu ứng lây lan xuất hiện khi tác nhân quan sát người khác rút tiền. Không dựng mạng quan hệ ví giả khi dữ liệu không chứng minh được mạng đó. Nghiên cứu gốc cho thấy khác biệt về tài sản, mức độ hiểu biết và khả năng quan sát giao dịch có liên quan đến thứ tự rút tiền. [Nghiên cứu của Liu, Makarov và Schoar](https://mitsloan.mit.edu/cfi/anatomy-a-run-terra-luna-crash).

**Tác nhân arbitrage**

Mua UST giá thấp, đổi sang LUNA rồi bán LUNA khi lợi nhuận kỳ vọng sau phí và trượt giá dương. Mỗi tác nhân có vốn hữu hạn, độ trễ thực thi và giới hạn giao dịch.

**Tạo lập thị trường**

Cung cấp lực mua/bán với vốn và tồn kho hữu hạn. Giá phản ứng với chênh lệch lệnh mua–bán và độ sâu thị trường; không có lực tự động kéo UST về 1 USD miễn phí.

### System Dynamics: các tồn lượng và dòng chảy

Theo dõi các tồn lượng chính:

- Tiền gửi Anchor, thanh khoản Anchor, dư nợ và quỹ trả lãi.
- UST trong ví, trên thị trường và do bên cứu trợ nắm giữ.
- Nguồn cung LUNA và LUNA chưa bán của arbitrageurs.
- BTC, stablecoin và tài sản mua được của LFG/TFL.
- Hàng đợi rút tiền và đổi token.

Các dòng chảy gồm gửi/rút tiền, trả lãi, mua/bán, đổi UST–LUNA và giải ngân cứu trợ.

Quan hệ cốt lõi:

\[
D_{t+1}=D_t+\text{gửi mới}+\text{lãi được ghi nhận}
-\text{rút đã thực hiện}
\]

\[
S^{UST}_{t+1}=S^{UST}_t+\text{UST phát hành}-\text{UST bị đốt}
\]

\[
S^{LUNA}_{t+1}=S^{LUNA}_t+\text{LUNA phát hành}-\text{LUNA bị đốt}
\]

Lượng LUNA nhận khi đổi \(q\) UST được tính từ giá oracle và cơ chế phí/spread. Dùng cơ chế virtual pool của Terra ở mức tổng hợp, đối chiếu với dữ liệu swap; không coi native swap là đổi 1 USD không giới hạn. [Đặc tả Market module](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html).

**Vòng phản hồi cần tái hiện:**

> Rút Anchor → bán UST → UST giảm giá → arbitrage đổi UST thành LUNA → bán LUNA → LUNA giảm giá → phải phát hành nhiều LUNA hơn cho lần đổi tiếp theo → rủi ro tăng → rút tiền mạnh hơn.

Rút tiền Anchor chỉ chuyển vị trí nắm giữ UST, **không tự làm giảm nguồn cung UST**. Tương tự, cứu trợ mua UST chỉ chuyển token sang quỹ cứu trợ; không tự động đốt token.

## 3. Cách triển khai trong cadCAD

Tạo dự án riêng tại `D:\New folder\luna-ust-sim`, đọc dữ liệu nguồn và lưu dữ liệu xử lý/kết quả riêng.

Dùng **cadCAD 0.5.3** làm bộ máy mô phỏng; bản đang có trên máy đã chạy được kiểm tra tối thiểu. Giao diện dùng **Streamlit + Plotly**, chạy cục bộ.

Mỗi bước 15 phút gồm các Partial State Update Blocks theo thứ tự:

1. **Quan sát:** cập nhật thông tin trễ, cú sốc đầu kỳ và tài sản cứu trợ khả dụng.
2. **Chính sách:** xác định chính sách được kích hoạt và lệnh cứu trợ dự kiến.
3. **Quyết định ABM:** tạo yêu cầu rút, gửi và giao dịch.
4. **Anchor:** xử lý yêu cầu theo thanh khoản; giữ phần chưa phục vụ trong hàng đợi.
5. **Thị trường và native swap:** khớp lệnh theo vốn, tồn kho, phí và năng lực thực thi; cập nhật giá và mint/burn.
6. **Kế toán và chỉ số:** cập nhật các tồn lượng, kiểm tra bảo toàn và ghi kết quả.

Tách các khối có phụ thuộc theo đúng thứ tự; không sửa trực tiếp trạng thái đầu vào. Đây là cách tổ chức phù hợp với [tài liệu cadCAD](https://github.com/cadCAD-org/cadCAD/blob/master/documentation/README.md).

Các giao diện tối thiểu:

- `ScenarioConfig`: khoảng thời gian, bước thời gian, seed, tham số mô hình, danh sách chính sách.
- `PolicyConfig`: hành động, điều kiện kích hoạt, độ trễ, thời hạn, hạn mức mỗi bước và nguồn tài trợ.
- `simulate(config)`: trả về chuỗi trạng thái, chỉ số đánh giá và sổ giao dịch.
- Xuất cấu hình JSON, kết quả CSV và biểu đồ để nhóm tái lập bài trình bày.

**Hai chế độ tách biệt:**

- **Tái lập lịch sử:** dùng lịch can thiệp, thay đổi giao thức và gián đoạn hoạt động đã ghi nhận; giá và dòng tiền vẫn do mô hình sinh.
- **Thử chính sách:** thay thế các hành động cứu trợ tương ứng; không cộng chính sách mới lên toàn bộ khoản cứu trợ lịch sử.

Các lịch ngừng hoạt động được giữ trong chế độ tái lập. Trong phản thực tế, không ép hệ thống dừng chỉ vì đã đến ngày lịch sử; đánh giá khả năng hoạt động qua thanh khoản, hàng đợi và khả năng đổi token. Do không mô phỏng validator, kết luận phục hồi chỉ áp dụng cho cơ chế tài chính trong mô hình.

## 4. Chính sách cứu trợ và dashboard

### Giới hạn nguồn lực lịch sử

Khởi tạo tài sản theo thời điểm được xác minh. Báo cáo JS Held ghi nhận LFG có **80.394 BTC**, **26.281.671 USDT** và **23.555.590 USDC** vào ngày 07/05; khoản chi ròng riêng của TFL khoảng **613,62 triệu USD**, gồm hỗ trợ UST và LUNA. [Báo cáo JS Held](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf).

Áp dụng các quy tắc:

- BTC phải được bán theo giá tại thời điểm thực thi, có phí và trượt giá.
- Khoản chuyển LFG → TFL là chuyển nội bộ, không tạo ngân sách mới.
- Quỹ trả lãi Anchor được hạch toán riêng với quỹ bảo vệ peg.
- Khoản chi ròng TFL là giới hạn đóng góp đã ghi nhận, không phải bằng chứng rằng toàn bộ tiền sẵn có từ đầu.
- Phần chưa xác minh thời điểm khả dụng không được cấp ngân sách sớm; chạy thêm biên sớm/muộn trong khoảng thời gian mà nguồn chứng minh được.
- Không tính UST/LUNA do quỹ đang nắm giữ thành tiền USD bảo chứng ở giá danh nghĩa.

### Bộ chính sách v1

| Chính sách | Tham số người dùng điều chỉnh | Tác dụng phụ phải thể hiện |
|---|---|---|
| Mua UST bảo vệ peg | Ngưỡng giá, tốc độ mua, phân bổ quỹ | Hao hụt dự trữ, giá có thể giảm lại khi dừng mua |
| Bổ sung thanh khoản thị trường UST | Phân bổ vốn, thời hạn cung cấp | Vốn bị rút khỏi quỹ và có thể bị người bán hấp thụ |
| Điều chỉnh native swap | Quy mô virtual pool, tốc độ phục hồi pool | Đổi nhanh hơn nhưng có thể làm LUNA phát hành và giảm giá nhanh hơn |
| Giới hạn rút Anchor tạm thời | Tỷ lệ phục vụ, thời hạn giới hạn | Hàng đợi tăng, mất khả năng tiếp cận tài sản và tăng tín hiệu rủi ro |

Cho phép kết hợp chính sách, nhưng toàn bộ hành động dùng chung sổ tài sản LFG/TFL.

**Kích hoạt mặc định:** UST dưới 0,99 USD trong hai bước liên tiếp. Người dùng có thể chọn một thời điểm sau cú sốc đầu kỳ hoặc dùng ngưỡng giá; chính sách chỉ quan sát thông tin đã có tại thời điểm đó.

Mỗi chính sách hỗ trợ độ trễ **15 phút, 1 giờ hoặc 6 giờ**. Thay đổi giao thức và giới hạn rút tiền phải được ghi rõ là giả định về khả năng thực thi, không mặc định là hành động lịch sử đã xảy ra.

### Nội dung dashboard

Ba màn hình:

1. **Đối chiếu lịch sử:** dữ liệu thật và mô phỏng của giá UST, giá/nguồn cung LUNA, tiền gửi Anchor, native swaps và rút tiền theo nhóm.
2. **Thử cứu trợ:** chọn chính sách, thời điểm/ngưỡng, độ trễ và cách phân bổ tài sản lịch sử.
3. **So sánh:** lịch sử, chính sách thay thế và kịch bản bỏ cứu trợ để kiểm tra vai trò của can thiệp.

Hiển thị ngân sách còn lại, hàng đợi, tỷ lệ phục vụ, tổn thất người gửi và thời gian phục hồi. Chỉ chạy lại khi bấm nút; lưu cấu hình từng lần chạy.

**Tiêu chí “cứu vãn” mặc định:**

- UST nằm trong **0,98–1,02 USD liên tục ít nhất 48 giờ**.
- Ít nhất **95% khối lượng yêu cầu rút/đổi** được phục vụ trong từng cửa sổ 24 giờ, hàng đợi không tăng kéo dài.
- Không cạn nguồn lực cứu trợ hoặc phát sinh số dư âm.
- Sau khi dừng hỗ trợ chủ động, tiếp tục đạt các điều kiện trên trong phép thử kéo dài **7 ngày**.

Phần kéo dài là thí nghiệm ổn định với điều kiện thị trường cuối kỳ, không phải dữ liệu lịch sử. Nếu chỉ đạt khi tiếp tục mua hỗ trợ, dashboard ghi **“giữ peg tạm thời”**.

## 5. Các bước thực hiện và kiểm chứng

| Bước | Công việc | Đầu ra hoàn thành |
|---|---|---|
| **1. Chuẩn hóa dữ liệu** | Đồng bộ UTC, đơn vị token/microtoken, aUST/UST; lập bảng nguồn và khoảng thiếu | Bộ dữ liệu 15 phút, bảng mốc sự kiện, sổ nguồn lực cứu trợ |
| **2. Dựng System Dynamics** | Xây tồn lượng, dòng chảy, thanh khoản, native swap và cơ chế giá tổng hợp | Mô hình kế toán đúng, tái hiện được vòng xoáy mint–sell |
| **3. Ghép ABM** | Tạo tác nhân có trọng số, quyết định rút và arbitrage, quan sát trễ | Mô hình có khác biệt hành vi giữa nhóm tài sản |
| **4. Hiệu chỉnh lịch sử** | Ước lượng hành vi rút, tác động giá và độ sâu thị trường; đóng băng tham số | Báo cáo độ khớp và tập cấu hình chuẩn |
| **5. Thử chính sách** | Thay lịch cứu trợ bằng từng chính sách và tổ hợp, giữ cùng seed/cú sốc | Bảng hiệu quả, chi phí và tác dụng phụ |
| **6. Làm dashboard và bài trình bày** | Đưa mô hình đã kiểm tra vào giao diện, xuất thí nghiệm | Demo chạy cục bộ, hướng dẫn và kết luận bài nhóm |

### Hiệu chỉnh để bám sát sự kiện

- Chỉ dùng thông tin trước khủng hoảng để khởi tạo tác nhân; không dùng `full_maxusd` của cả sự kiện.
- Dùng `epoch_state` làm chuẩn tổng tiền gửi. Dòng chuyển aUST giữa ví không được coi toàn bộ là rút Anchor.
- Dùng chuỗi giá tổng hợp làm chuẩn chính; chuỗi FTX trong dữ liệu arbitrage được đánh giá riêng.
- Dùng các hành động ban đầu của hai ví A/B ngày 07/05 làm cú sốc khởi phát có điều kiện, loại phần đó khỏi dòng hành vi tự sinh để tránh đếm trùng.
- Không nhập toàn bộ đường giá, lượng rút hay nguồn cung lịch sử làm đầu vào điều khiển.

Hiệu chỉnh trên **06–10/05**, kiểm tra trên **11–15/05**; đánh giá phần trước/sau gián đoạn hoạt động riêng. Nếu hiệu chỉnh lại bằng toàn bộ sự kiện để trình diễn, phải gọi đúng là *độ khớp trong mẫu*.

Ngưỡng chấp nhận ban đầu cho mô hình môn học:

- MAE giá UST ≤ **0,05 USD**.
- RMSE tiền gửi Anchor ≤ **10% tiền gửi đầu kỳ**.
- RMSE trên thang `log10` của giá và nguồn cung LUNA ≤ **0,5**.
- Sai lệch thời điểm mất peg kéo dài ≤ **6 giờ**.
- Sai lệch tỷ lệ tiền gửi còn lại theo nhóm ≤ **15 điểm phần trăm**.

Đây là mục tiêu kiểm chứng, không phải độ chính xác đã đạt. Khi không đạt, phải báo sai lệch và giảm mức độ chắc chắn của kết luận chính sách.

### Kiểm tra bắt buộc

- Bảo toàn UST/LUNA ngoài mint/burn; bảo toàn tài sản qua mua bán và chuyển nội bộ.
- Không rút vượt tiền gửi, không mua vượt quỹ, không dùng dữ liệu tương lai.
- Quỹ bằng 0 thì không phát sinh mua cứu trợ; mua UST không tự làm giảm tổng cung.
- Hạn chế rút tiền không được coi là thành công chỉ vì lượng rút thực hiện giảm.
- So sánh bước 15 phút với 5 phút để kiểm tra sai lệch do rời rạc hóa.
- Chạy **20 seed** cho mỗi kịch bản báo cáo; dùng cùng seed giữa các chính sách và trình bày trung vị, khoảng kết quả cùng tỷ lệ đạt tiêu chí cứu vãn.
- Kiểm tra độ nhạy với thanh khoản, phản ứng đám đông, độ trễ và thời điểm khả dụng của quỹ. Không hiệu chỉnh lại mô hình riêng để làm một chính sách thắng.

**Kết quả bài nhóm cần trả lời:** với tài sản lịch sử và cơ chế đã hiệu chỉnh, chính sách nào phục hồi được peg cùng khả năng rút/đổi, chính sách nào chỉ trì hoãn sụp đổ, và kết luận đó còn đúng khi thay đổi các giả định quan trọng hay không.

