# Rà soát bàn giao bản cải thiện Luna–UST

Rà soát chỉ đọc ngày 10/10/2026. Engine tại thời điểm rà soát: `6cb4c607cf1337d9ebb9b225041f8fdae0f37f1c06b8ea1d980ffcb0ea4a7427`. Không dùng báo cáo v2 để xác nhận kết quả v3.

## Kết luận hiện tại

Phạm vi trong `PLAN_APPROVED.md` vẫn phù hợp yêu cầu: mô hình nhỏ cadCAD, ABM người gửi/arbitrage, tồn lượng và dòng tài sản, giá nội sinh, bốn chính sách cùng nguồn lực hữu hạn, dashboard tiếng Việt và phép thử bảy ngày ngừng hỗ trợ mới. `IMPROVEMENT_PLAN_VI.md` giữ nguyên gates và yêu cầu cải thiện có bằng chứng.

Chưa đủ bằng chứng hoàn tất. `report_train.json`, `report_all.json` và metadata bộ nhiều seed đang lưu vẫn thuộc engine v2 `407acc…82b7`; `outputs/improvement/comparison.json` còn `provisional_ablation`. Ba probe mới chỉ chọn warm start, không phải hiệu chỉnh đã hoàn tất. Warm all tốt nhất sau sửa VWAP có objective 32,0456 và trượt mọi gate toàn sự kiện; warm train khớp đầu kỳ nhưng sai giá/nguồn cung toàn sự kiện. Các fit v3 đang được thực hiện riêng; phải đọc đầu ra đã xuất cuối cùng trước khi kết luận.

## Điểm cần xử lý hoặc xác nhận

| Mức | Điểm rà soát | Hành động và bằng chứng hoàn tất |
|---|---|---|
| P1 | Độ khớp và cải thiện chưa được chứng minh | Đọc report train/all mới với provenance hiện hành; so sánh v2/v3 trên cùng định nghĩa quan sát. Báo cả gate thất bại và metric xấu đi. Nếu chưa đạt kế hoạch, tiếp tục xử lý cơ chế; không lấy 140 lần chạy hay kiểm thử phần mềm làm bằng chứng sát lịch sử. |
| P1 | Ancillary có thể cũ trong bảng hiện hành | Diagnostics, sensitivity và timestep cần provenance riêng theo nguồn/tham số/trajectory hoặc configuration. Root đang bổ sung guards này. Sau fit phải tạo lại các đầu ra, đọc metrics và xác minh guards từ chối artifact cũ. Suite mới không tự làm mới ba artifact này. |
| P2 | Cấu hình chính sách đã lưu có thể khác bộ selector | `app.py` giữ `session_state['scenario']` sau đổi selector hoặc import JSON. Trial/control được ghép đúng với cấu hình đó, nhưng headline và cảnh báo của bộ đang chọn có thể gây hiểu nhầm. Hiển thị rõ khi hash params trong scenario khác bộ đang chọn; giữ nguyên cấu hình import có chủ ý. Kiểm tra bằng một lần chạy chính sách rồi đổi selector. |
| P2 | Nút tải báo cáo chưa kiểm identity của chính report | `app.py` hiện gate việc tải `REPORT_VI.md` bằng metadata suite. Sau suite mới nhưng trước report mới, file báo cáo cũ vẫn có thể được tải. Bind metadata report với engine/params/calibration/suite và hash file, hoặc guard tương đương. Kiểm tra bằng artifact report cũ có suite hiện hành. |
| P2 | Hồ sơ bàn giao còn câu xác nhận của v2 | `outputs/COMPLETION_AUDIT.md` ghi hiệu chỉnh v2, 18 tests và 0/140 cứu vãn; `outputs/REPORT_VI.md` còn số v2; `DEMO_VI.md` nói bộ 140 lượt đã lưu. Chỉ cập nhật bằng kết quả v3 đã đọc. Kế hoạch cải thiện còn trạng thái đang triển khai là đúng hiện tại. |
| P2 | Audit tái lập không tự chứng minh mọi yêu cầu bàn giao | Audit hiện kiểm nguồn, objectives/metrics/financials và archive rất tốt, đồng thời tách reproduction/fidelity. Nhưng hash XML, screenshot, tài liệu và tồn tại file không xác nhận tests chạy với mã mới, nội dung trình bày hay UI thực tế. Completion audit vẫn cần đọc XML, mở dashboard, kiểm thao tác và ảnh mới; file cần thiết không nên bị bỏ qua âm thầm bởi điều kiện `if p.is_file()`. |

## Trình tự hoàn tất sau fit

1. Xác minh hai fit kết thúc thành công, source/target/group/parameter hashes đúng, full-event trajectory đầy đủ và parity fast/cadCAD đạt. Đọc cả train, validation và all; kiểm onset có dấu, native volume/fee, các cửa sổ trước/sau ngừng native và conservation.
2. Tạo comparison và ablation hiện hành trên cùng mục tiêu; kiểm quyết định chọn bộ mới có cơ sở. Nếu còn sai lệch lớn, tiếp tục phân tích cơ chế trước khi tuyên bố hoàn tất cải thiện.
3. Đóng băng tham số chung, chạy lại bảy kịch bản × 20 seed, sensitivity, timestep và diagnostics. Đọc kết quả cứu vãn, chi phí, hàng đợi và service; không đổi tham số riêng cho chính sách thắng. Kiểm no_rescue cùng điều kiện và bảy ngày không hỗ trợ mới.
4. Tạo lại report và biểu đồ offline; cập nhật README/demo/completion audit/kế hoạch bằng kết quả thật. Giữ giới hạn Jump, lịch quỹ TFL, sổ lệnh tổng hợp và validator; full-fit là trong mẫu, holdout chỉ kiểm tham số với cấu trúc đã biết sự kiện.
5. Chạy tests cuối, kiểm dashboard cả ba tab, thay selector, import/export JSON/CSV/ledger, cảnh báo artifact cũ và file báo cáo tải được. Lưu screenshot hiện hành và đọc XML thực tế.
6. Chạy audit tái lập sau khi artifacts/documents đã hoàn tất. Đọc `reproduction_pass`, `fidelity_pass` và `failed_gates` riêng; đối chiếu completion audit từng yêu cầu. Không dùng `audit: passed` một mình làm kết luận mô hình đã sát lịch sử.

Việc thiếu từng giao dịch Jump hay sổ lệnh đầy đủ là giới hạn dữ liệu được công bố, không phải lý do tự cấp vốn hoặc ép giá theo quan sát. Nếu các giới hạn này còn ảnh hưởng kết quả, chính sách chỉ cho biết khả năng phục hồi có điều kiện trong mô hình.
