# Kịch bản Thuyết trình Mô hình Tái hiện Cuộc khủng hoảng Terra Luna – UST (8 phút)

Tài liệu này định hình cấu trúc buổi thuyết trình chuyên nghiệp trong vòng 8 phút, tập trung tái hiện cuộc khủng hoảng Terra (LUNA – UST) từ ngày 06/05 đến ngày 15/05/2022. Người trình bày mở dashboard tương tác (bằng script `Start.ps1` hoặc lệnh `streamlit run app.py`). Hai tab trọng tâm mặc định là Đối chiếu lịch sử và Báo cáo tái hiện. Trước buổi thuyết trình, cần đối soát tệp kiểm toán nguồn `outputs/improvement/WORK_STATUS_VI.md` để nắm vững xuất xứ dữ liệu. Lưu ý chỉ sử dụng các báo cáo có mã kiểm tra tính toàn vẹn (manifest) khớp với phiên bản thuật toán hiện hành; các báo cáo phiên bản cũ (v2/v3) lưu trong kho lưu trữ không đại diện cho kết quả của phiên bản v4.

---

## Phút 0 – 2: Khung bài toán và Vòng phản hồi vĩ mô

> *"Mô hình tái hiện cơ chế tháo chạy thanh khoản: người gửi tiền rút vốn ồ ạt khỏi Anchor Protocol, xả bán UST trên thị trường thứ cấp; lực lượng arbitrageur gom mua UST chiết khấu rồi đưa vào module Native Swap để đổi lấy LUNA và tiếp tục bán tháo LUNA. Động lực suy giảm của thị giá LUNA buộc thuật toán phải phát hành số lượng token LUNA ngày càng lớn cho mỗi UST bị đốt, kích hoạt vòng xoáy siêu lạm phát. Hệ thống bao gồm 1.000 tác nhân người gửi đại diện có trọng số, 20 tài khoản kinh doanh chênh lệch giá, và 6 khối công đoạn tuần tự của khung cadCAD."*

- Trực quan hóa trên tab **Đối chiếu lịch sử**: Đường nét đứt màu xám là dữ liệu quan sát thực tế; đường nét liền màu xanh là quỹ đạo mô phỏng được sinh ra hoàn toàn nội sinh từ tương tác giữa các tác nhân và dòng tồn lượng.
- Hai địa chỉ ví khởi phát (Ví A và B) được thiết lập như các xung lực ngoại sinh có điều kiện; diễn biến giá Bitcoin đóng vai trò là điều kiện biên thị trường.
- Nguyên tắc trung thực khoa học: Tuyệt đối không nhập cưỡng bức đường giá UST, giá LUNA hay khối lượng rút tiền thực tế vào luật mô phỏng để ép khớp quỹ đạo.

---

## Phút 2 – 4: Đánh giá độ khớp định lượng và Tiêu chuẩn kiểm định

- Giữ nguyên tùy chọn **Khớp toàn sự kiện (v4)** và phân tích cặn kẽ 6 chỉ số kiểm định: Thị giá UST (MAE), Khối lượng tiền gửi Anchor (NRMSE), Thị giá LUNA (Log-RMSE), Nguồn cung LUNA (Log-RMSE), Tỷ lệ bảo toàn vốn ban đầu của 6 nhóm nhà đầu tư, và Sai lệch thời điểm mất peg.
- Làm rõ sự khác biệt giữa "khớp điểm cuối" (endpoint fit) và "khớp toàn bộ đường đi" (trajectory fidelity): nguồn cung LUNA cuối kỳ có thể xấp xỉ dữ liệu thực tế nhưng thời điểm bùng nổ có thể bị phát hành sớm hơn.
- Mở tab **Báo cáo tái hiện**: Cấu hình khớp toàn sự kiện (in-sample) tối ưu hóa trên toàn bộ quan sát 06–15/05/2022. Trong khi đó, cấu hình huấn luyện (train split) chỉ tối ưu trên giai đoạn 06–10/05 rồi kiểm định ngoài mẫu (out-of-sample holdout) trên giai đoạn 11–15/05. Công bố minh bạch toàn bộ các ngưỡng đạt và chưa đạt chuẩn, không dùng việc giảm hàm mất mát (loss reduction) để che đậy các bài kiểm tra thất bại.

---

## Phút 4 – 6: Mô hình hóa tác nhân (ABM) và Tồn lượng/Dòng chảy (System Dynamics)

- **Cấu trúc vị thế người gửi tiền**: Mỗi tác nhân sở hữu bốn trạng thái vi mô: quyền đòi tiền gửi (`deposit`), giá trị lệnh chờ giải ngân (`queue`), lượng token thực nhận trong ví (`wallet_ust`), và dòng tiền mặt USD đã thực thu hồi (`realized_usd`). 
- **Quy trình giải ngân**: Việc gửi yêu cầu rút tiền đơn thuần chỉ làm gia tăng hàng đợi; chỉ khi Anchor thực tế xuất quỹ thanh khoản thì UST mới được chuyển về ví cá nhân. Các khoản lãi tích lũy hay gửi lại không được tính gộp để khôi phục phần vốn gốc ban đầu đã rút. Giao thức Anchor phân bổ thanh khoản theo tỷ lệ hàng đợi; cơ chế FIFO được áp dụng để theo dõi phần vốn gốc còn lại của từng nhóm chứ không phải hàng đợi toàn cục.
- **Phân tầng tác nhân**: Các nhóm tác nhân mang trọng số phản ánh quy mô vốn đại diện; nhóm tiền gửi tổ chức được mô hình hóa dưới dạng một khối tài chính liên tục (continuum). Ở chế độ ngẫu nhiên nhị thức Bernoulli, một cú sốc rút vốn của nhóm ví cá voi có thể kích hoạt tâm lý hoảng loạn dây chuyền sớm hơn dự kiến.
- **Kỷ luật kế toán trong System Dynamics**: Mô hình liên tục cập nhật và đối soát cân đối giữa quyền đòi, tiền mặt, dư nợ vay và quỹ dự phòng lãi suất; các kho lưu trữ USD, UST, LUNA; lượng đốt/đúc trên chuỗi và ngân sách các quỹ can thiệp. Tiền gửi được hạch toán đúng bản chất là nghĩa vụ nợ, không bị tính trùng như nguồn cung token mới. Mọi lệnh mua bán đều chịu ràng buộc bởi lượng vốn hữu hạn thực tế; các quỹ bình ổn LFG và TFL tuyệt đối không được cấp nguồn tiền vô hạn.

---

## Phút 6 – 7: Độ nhạy hạt giống ngẫu nhiên và Bước thời gian mô phỏng

- Trình bày số lượng đường mô phỏng đạt đủ 6/6 tiêu chí và các độ lệch phát sinh khi chuyển đổi giữa bước thời gian 5 phút và 15 phút trong báo cáo hiện hành.
- Dải biến thiên phân vị (p05 / median / p95) phản ánh tính bất định của hạt giống ngẫu nhiên (seed) trong cùng một cấu trúc tham số; việc quỹ đạo trung bình khớp với thực tế không đồng nghĩa mọi kịch bản ngẫu nhiên đều khớp hoàn hảo.
- Việc chuẩn hóa đồng hồ quan sát giá LUNA ở chu kỳ cố định 15 phút giúp loại bỏ sự phụ thuộc vào tần suất lấy mẫu, song vẫn đòi hỏi việc kiểm chứng tính hội tụ của toàn bộ hệ thống phản hồi phi tuyến.
- Nếu các kiểm tra về nguồn dữ liệu, hạt giống hoặc nhịp thời gian chưa hoàn tất, cần trình bày rõ ràng ở trạng thái chưa kiểm chứng, không sử dụng số liệu cũ từ kho lưu trữ để làm bằng chứng hiện hành.

---

## Phút 7 – 8: Tính tái lập, Giới hạn mô hình và Định hướng mở rộng

- Tải về và giới thiệu trực tiếp các tệp cấu hình tham số, kết quả quỹ đạo và sổ cái giao dịch (`ledger.csv`) đã được chứng thực. Nêu rõ các mã băm toàn vẹn (hash) của mã nguồn, tham số và dữ liệu thô, cũng như tính tương đồng tuyệt đối giữa bộ chạy nhanh (fast runner) và động cơ cadCAD.
- Nhấn mạnh tính khách quan: Các bài kiểm thử đơn vị và kiểm toán bảo toàn tài sản xác nhận tính nhất quán nội tại của mô hình toán học, nhưng không thay thế cho mức độ tương thích hoàn toàn với lịch sử thực tế.
- **Tổng kết giới hạn**:
  > *"Mô hình đã đơn giản hóa một số khía cạnh vi mô như cấu trúc sổ lệnh trên từng sàn giao dịch tập trung, cơ chế khớp lệnh của đơn vị tạo lập thị trường Jump Trading, và sự biểu quyết của các validator. Mục tiêu trọng tâm là tái hiện chuẩn xác động lực sụp đổ giá, làn sóng tháo chạy khỏi Anchor Protocol và vòng xoáy siêu lạm phát LUNA trên cùng một khung quan sát thực nghiệm. Những tiêu chí chưa đạt chuẩn được công bố đầy đủ và là cơ sở định hướng cho các cải tiến cấu trúc tiếp theo."*
