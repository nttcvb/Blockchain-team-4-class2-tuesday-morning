# Kịch bản demo bài nhóm — 8 phút

## Chuẩn bị

Chạy `Start.ps1` trong thư mục dự án hoặc mở dashboard đang chạy tại http://127.0.0.1:8501. Bộ kết quả 140 lượt chạy đã lưu; không cần chạy hiệu chỉnh trong lúc thuyết trình. Mở thêm `outputs/REPORT_VI.md` và `MODEL_SPEC.md` để trả lời câu hỏi về công thức.

## 0–2 phút: câu hỏi và vòng phản hồi

“Chúng em mô phỏng người gửi rút Anchor, bán UST, arbitrage đổi UST sang LUNA, rồi bán LUNA. Giá LUNA giảm khiến lượng LUNA phát hành cho mỗi UST tăng. Mô hình có 1.000 người gửi đại diện và 20 tài khoản arbitrage, chạy bằng cadCAD với sáu khối cập nhật.”

Mở **Đối chiếu lịch sử**. Giải thích đường chấm là dữ liệu thật, đường màu là giá/tồn lượng do mô hình sinh. Nêu rõ hai ví A/B là cú sốc khởi phát có điều kiện, không là bằng chứng về tấn công.

## 2–3 phút: độ khớp trước khi nói về chính sách

Giữ lựa chọn **Khớp toàn sự kiện; chỉ đánh giá trong mẫu**. Đọc MAE UST khoảng 0.091 USD và sai số tiền gửi khoảng 11.1%. Mở kiểm định để xem bộ train riêng. Nói rõ bộ train khớp giai đoạn đầu nhưng không khái quát được toàn giai đoạn sụp đổ. Cấu trúc đã biết toàn sự kiện; kiểm định thời gian chỉ kiểm tra khả năng giữ nguyên tham số.

“Bản này minh họa cơ chế và thí nghiệm có điều kiện. Chúng em chưa chứng minh được rằng nó tái lập sát toàn sự kiện hay dự báo được chính sách trong thực tế.”

## 3–5 phút: chạy chính sách

Mở **Thử cứu trợ**, chọn **Mua UST**, ngưỡng 0,99, độ trễ 60 phút, thời hạn 120 giờ, hạn mức 50 triệu USD/giờ, biên quỹ muộn, LFG + TFL, seed 42 và bật phép thử thêm 7 ngày. Bấm **Chạy thí nghiệm**.

Xem giá, nguồn lực còn lại, hàng đợi và khả năng phục vụ. Đọc giá UST cuối kỳ, chi phí và phân loại từ kết quả đang hiển thị. Với bộ tham số v2 đã lưu, seed 42 trong preset mua UST có giá cuối khoảng 0,0246 USD và không đạt tiêu chí cứu vãn. Giải thích rằng giá gần 1 ở một thời điểm không đủ: phải đạt peg liên tục, rút/đổi hoạt động và bền sau khi ngừng hỗ trợ.

Đổi sang **Giới hạn rút Anchor** để minh họa quyền đòi vẫn tồn tại và hàng đợi có thể tăng. Hoặc chọn cả bốn chính sách để kiểm tra một cấu hình mới. Luôn so sánh cùng bộ tham số, seed và khoảng thời gian; không chỉnh mô hình riêng để một chính sách thắng.

## 5–7 phút: nhiều seed và độ nhạy

Mở **So sánh & báo cáo**. Bảng có 7 kịch bản, mỗi kịch bản 20 seed. Khoảng 5–95% cho thấy biến động giữa các seed trong cùng bộ tham số. Preset “Kết hợp” gồm mua UST, thanh khoản và native swap; gate được báo cáo riêng và có thể ghép trong giao diện.

“Không preset nào đạt đầy đủ tiêu chí trong các lần chạy này. Đây không phải chứng minh mọi chính sách đều không cứu được lịch sử.”

Mở kiểm tra bước thời gian. Sai số giữa bước 5/15 phút của log giá LUNA lớn: cơ chế native và thứ tự khớp giao dịch còn nhạy với cách rời rạc hóa. Nêu thêm hai biên quỹ sớm/muộn và các độ trễ 15/60/360 phút. Replay dùng quỹ sớm, chính sách mặc định dùng quỹ muộn; so sánh chứa cả giả định thời điểm tài sản khả dụng.

## 7–8 phút: kết luận và khả năng tái lập

Tải cấu hình JSON, kết quả CSV và sổ giao dịch. Mỗi lần chạy có tài sản hữu hạn: BTC phải bán theo giá BTC tại bước đó; TFL có trần đóng góp ròng; chuyển nội bộ không tăng quỹ; mua UST không tự đốt token.

“Đóng góp của bài nhóm là mô hình ABM + tồn lượng/dòng chảy, dashboard thử chính sách và quy trình đối chiếu minh bạch. Giới hạn lớn gồm giao dịch Jump thiếu lịch chi tiết, dừng Anchor thô trong replay, thị trường tổng hợp và sai số hiệu chỉnh. Cần cải thiện các phần đó trước khi đưa ra kết luận nhân quả về cứu trợ thật.”

## Câu hỏi thường gặp

- **Vì sao có USD của market maker ngoài LFG/TFL?** Đó là phía đối ứng thị trường, không phải tiền cứu trợ. 25 tỷ USD ban đầu của market maker, 150 triệu USD vốn arbitrage và 1 tỷ USD của người mua bên ngoài là giả định, không phải số liệu tài sản xác minh. Chúng được hạch toán và không cấp lại tự động.
- **Vì sao native swap không đảm bảo UST về 1?** Vì cần lợi nhuận sau phí, vốn mua UST và khả năng bán LUNA; LUNA phát hành cũng làm tăng áp lực bán.
- **Vì sao không dùng giá thật trong mỗi bước?** Vì chính sách phải có khả năng thay đổi kết quả. Giá thật chỉ dùng làm mục tiêu và đối chiếu; BTC là điều kiện thị trường ngoại sinh.
- **Có tái lập blockchain chính xác không?** Không. Virtual pool, oracle, gián đoạn và độ trễ arbitrage là xấp xỉ theo bước thời gian. Các validator, restart và thị trường từng sàn chưa được mô hình đầy đủ.
