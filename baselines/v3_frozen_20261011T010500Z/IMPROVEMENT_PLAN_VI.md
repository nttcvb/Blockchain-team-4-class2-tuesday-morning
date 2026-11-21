# Kế hoạch cải thiện mô hình sau bản v2

Ngày bắt đầu: 10/10/2026. Phạm vi cập nhật theo yêu cầu người dùng: mô hình nhỏ cadCAD + ABM + System Dynamics, tái hiện gần đúng nhất sự kiện 06–15/05/2022. Không yêu cầu phát triển hay nghiệm thu các chính sách ngăn sụp đổ. Cứu trợ LFG/TFL đã xảy ra vẫn là một phần của lịch sử cần mô phỏng với nguồn lực hữu hạn.

## Điểm xuất phát đã đo

Bản v2 được giữ tại `baselines/v2/`, gồm mã, tham số, dữ liệu mục tiêu đã xử lý và kết quả. Full-fit v2 mất peg lúc 07/05 19:00 UTC; dữ liệu mục tiêu xác nhận mất peg kéo dài lúc 09/05 18:15 UTC. Sai lệch sớm 47,25 giờ. MAE UST 0,0909 USD; NRMSE tiền gửi 0,1113; RMSE log10 giá LUNA 0,8613 và nguồn cung 0,4196; MAE nhóm tối đa 0,1448. Bản train khớp đầu kỳ nhưng thất bại mạnh ở giá/nguồn cung LUNA ngoài mẫu.

## Thứ tự triển khai và kiểm chứng

1. **Kiểm tra định nghĩa quan sát và lịch nguồn lực.** Đối chiếu bucket nguồn cung với native mint; không dùng giá trị tổng hợp cuối giờ như quan sát có sẵn đầu giờ. Giữ dữ liệu gốc. Ghi lại timestamp chuyển BTC từ báo cáo JS Held, phân biệt chuyển tài sản, quỹ khả dụng và mua UST. Giữ trần 80.081 BTC, 313 BTC dự trữ và 613.616.889 USD TFL; không suy diễn lịch giao dịch Jump còn thiếu.
2. **Sửa tích phân thị trường/native.** Giữ sáu PSUB và bước ABM 15 phút; thị trường/native dùng bước nội bộ một phút, pool hồi theo thời gian vật lý, oracle trễ và lệnh mua/bán có vốn hữu hạn. Chia return BTC và tác động cứu trợ giữa bước con, tránh nhân lại tác động. So sánh 5/15 phút, kiểm tra conservation và parity fast/cadCAD.
3. **Tách gián đoạn blockchain, Anchor và native.** Replay phải cho rút Anchor tiếp sau chain restart dù native mint đã tắt. Lịch gián đoạn là biên giao thức ngoại sinh được ghi nguồn và mức xấp xỉ; phản thực tế không bị ép dừng theo ngày lịch sử. Thời điểm dùng trong mô hình được đối chiếu khoảng trống giao dịch, không nhập lượng rút thật vào quyết định.
4. **Hiệu chỉnh v3 đúng mục tiêu.** Dùng cùng ngưỡng đã đặt trước; tăng trọng số onset theo sai lệch/6 giờ, cân bằng các giai đoạn và dùng tín hiệu depeg mềm để tránh nghiệm khớp giá bình quân nhưng mất peg sai ngày. Khối lượng/phí native tiếp tục là mục tiêu. Search rộng, refinement và checkpoint có hash mã/dữ liệu; đánh giá baseline và ablation trước khi chọn bộ mới.
5. **Đánh giá hành vi và thị trường sau sửa cơ chế.** Kiểm tra cả người mua UST ngoài Anchor và người giữ LUNA ngoài arbitrage. Mua bằng một hạn mức USD cố định khi giá rất thấp có thể hút hết UST trên thị trường và khóa native swap dù còn tiền; cần đối chiếu tồn kho, nhu cầu bán lại và quote từng phút. Dữ liệu holder theo ngày hỗ trợ kiểm tra quy mô, nhưng nhãn “Other” không xác định riêng nhóm mua ngoài và thay đổi số dư không đồng nghĩa lệnh bán. Kiểm tra độ sâu LUNA ở đúng đơn vị token/USD, phản ứng khi mất thanh khoản và đường giá sau ngừng native. Với người gửi, kiểm tra hazard bão hòa có làm mọi nhóm rút ngay sau lag; thử trần cơ hội quyết định theo wealth trước run nếu cần, không dùng số dư sàn theo nhóm hay survival thực tế làm luật. Chỉ thêm tham số khi có cơ chế rõ, cải thiện đo được và không dùng thông tin tương lai. Không thêm lực kéo giá miễn phí.
6. **Kiểm chứng tái hiện và bàn giao.** Đóng băng tham số; train 06–10/05, holdout tham số 11–15/05, full-fit ghi rõ trong mẫu. Vẽ giá UST/LUNA, tiền gửi Anchor, nguồn cung và native swaps so với quan sát; chỉ chấm nhóm người gửi trong thời gian nhật ký giao dịch thật có dữ liệu. Kiểm tra nhiều seed lịch sử và bước 5/15 phút, conservation, parity fast/cadCAD, xuất cấu hình và báo cáo có hash nguồn. Báo đầy đủ sai lệch trước/sau và giới hạn ngoài mẫu. Bộ 7 kịch bản chính sách, độ nhạy chính sách và tail cứu trợ bảy ngày không còn là điều kiện bàn giao theo phạm vi mới.

## Tiêu chí quyết định

Không nới các gate cũ: UST MAE ≤0,05 USD; tiền gửi NRMSE ≤0,10; log10 RMSE giá/nguồn cung LUNA ≤0,5; group MAE ≤0,15; onset ≤6 giờ. Phải giảm đáng kể sai thời điểm v2 và cải thiện độ khớp tổng thể, đồng thời không phá accounting, tài sản hữu hạn, delay hay quyền đòi của người gửi. Báo đầy đủ held-out và sai lệch 5/15 phút; full-fit không phải validation độc lập. Gate chưa đạt phải ghi rõ và tiếp tục xử lý cơ chế thay vì chỉ chạy nhiều seed.

## Bằng chứng nguồn

- Bộ tái lập Liu, Makarov và Schoar trong thư mục dữ liệu gốc: giá, epoch state, giao dịch Anchor/native và nguồn cung.
- [JS Held audit](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf): tài sản, các lần chuyển BTC và hạn mức ròng.
- [Terra Market module](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html): virtual pool, spread và phục hồi.
- [Uhlig, A Luna-tic Stablecoin Crash](https://www.nber.org/papers/w30256): convertibility, gián đoạn/restart và cơ chế phản ứng khác nhau giữa người nắm giữ. Mốc báo tin và mốc giao dịch có thể khác; không coi thời gian bài/tweet là timestamp block chính xác.

## Trạng thái

Đang triển khai. Chỉ cập nhật thành hoàn tất sau khi đọc các đầu ra mới, kiểm chứng độ khớp và tính nhất quán của mô hình trên phạm vi tái hiện lịch sử.

Ngày 11/10/2026, 00:52 UTC: fit train hiện hành trên engine `0a89a9e6…` đã hoàn tất 266 đánh giá và audit, đạt 6/6 gate trong mẫu; holdout chỉ đạt 2/6. Fit toàn sự kiện đã hoàn tất 460 đánh giá, loss 7,711416 và 2/6 gate; cả hai fit đã có audit archive, nguồn dữ liệu, sổ cái và parity fast/cadCAD toàn kỳ. Chưa có bản tái hiện đủ độ khớp toàn sự kiện.

Bộ kiểm tra hiện hành dùng seed42–61: cả 20 đường đều 0/6 gate; đổi bước 15 xuống 5 phút làm Anchor NRMSE giữa hai đường bằng 0,270695. Báo cáo tái hiện đã xuất đầy đủ các lỗi này và dải seed, cùng ba kiểm thử báo cáo bổ sung (24/24 đạt). Kiểm thử mã và bảo toàn tài sản không thay thế kiểm chứng lịch sử.

Thứ tự thí nghiệm tiếp được thu hẹp theo bằng chứng:

1. Giữ public core bất biến khi fit attention17 chiều đang chạy; ngân sách tối đa350 đánh giá, kể cả controls và xác minh cuối. Chỉ chọn khi kết quả cuối cải thiện trên cùng mục tiêu và có nguồn/ledger/parity.
2. Sửa cadence bằng đồng hồ quan sát LUNA cố định15 phút. Probe riêng giữ đúng959 điểm public15 phút và giảm sai lệch UST/Anchor giữa bước, nhưng giá/nguồn cung LUNA còn sai. Chưa tích hợp vào core trong lúc fit chạy.
3. Kiểm tra rút từng phần dựa trên wealth raw. Dữ liệu giao dịch đầu tiên của17 whale có rút ngoài A/B có median bằng3,325% vốn trước run; đây là tỷ số mô tả, không phải claim tại thời điểm rút. Compound-Poisson giữ conditional mean và moment theo thời gian; β1 chỉ đưa seed42 tới onset−5,5 giờ, còn seeds43–46 lệch +7/−18/−35/−11,75 giờ. Không chọn chỉ theo seed42; cả5 vẫn không đạt tất cả gate.
4. Tách cơ chế cuối sự kiện: giới hạn inventory UST, phản ứng người giữ LUNA sau khi mất peg kéo dài, hình dạng liquidity theo price/supply và oracle. Probe holder dùng EMA60 phút, ngưỡngdiscount5%, giữ publicparams cố định; không dùng ngày sụp hay giá thật làm trigger. So sánh implicit oracle từ native swaps với quote để xác định mức phù hợp của giả định lag1 phút trước khi mở thêm tham số.
5. Sau khi chốt cấu trúc, hiệu chỉnh stochastic bằng ensemble seed chung rồi kiểm bằng seed mới; deterministic chỉ là conditional mean, không là kỳ vọng quỹ đạo có phản hồi. Mọi thay đổi nguồn phải chạy lại audit và báo cáo với hash mới.

Chưa chọn các giả thuyết cap/holder/USD-depth/attention/partial liquidation làm bản chính. Dashboard mặc định là đối chiếu lịch sử và báo cáo tái hiện, đã smoke-check không exception. Bộ chính sách không còn là điều kiện nghiệm thu theo phạm vi mới. Đây chưa phải hồ sơ nghiệm thu cuối.
