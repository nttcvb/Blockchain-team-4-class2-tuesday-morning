# Quyết định cải thiện v3 và bằng chứng

Tài liệu này ghi lý do chọn cơ chế. Kết quả cuối cùng phải đọc cùng `comparison.json` và các báo cáo hiệu chỉnh; một probe với tham số chưa hiệu chỉnh không phải nghiệm cuối.

## Các sửa đổi đã chọn

| Phần | Sửa đổi | Cách kiểm tra |
|---|---|---|
| Nguồn cung | Đưa tổng nguồn cung của bucket giờ đến cuối giờ tương ứng | Đối chiếu tăng nguồn cung với gross native mint, kiểm tra không nhìn trước |
| Nhóm người gửi | Theo dõi phần vốn đầu kỳ còn lại theo FIFO; lãi và gửi lại không phục hồi phần đã rút | Rút một phần, gửi lại và tích lũy lãi trong regression |
| BTC cứu trợ | Tách gross transfer khỏi hạn mức ròng; không khả dụng trước bằng chứng chuyển | Tổng 80.081 BTC, giữ 313 BTC; biên muộn cộng một giờ là giả định vận hành |
| Thị trường | Giữ ABM 15 phút, tích phân thị trường/native một phút | Token/cash conservation, tổng burn/mint, phí có chủ sở hữu, BTC return chỉ áp dụng một lần |
| Arbitrage | Lợi nhuận và tiền thu bán LUNA dùng cùng đường cầu tích phân VWAP; depth và giới hạn cash cố định đầu phút | 37 core tests; 500 trường hợp tối ưu ngẫu nhiên không âm profit hoặc vượt quantity limit; bisection 32 bước trả lower bound |
| Giao thức | Tách chain, Anchor và native; Anchor tiếp tục sau restart dù mint đã tắt | Các regression halt/restart và quyền đòi còn trong hàng đợi |
| Điều kiện cứu vãn | Tính cả yêu cầu rút tồn đọng đầu cửa sổ; yêu cầu Anchor còn hoạt động | Trường hợp peg=1 nhưng nợ rút 14 tỷ UST không được tính cứu vãn |
| Mua UST + LP | Controller tính cả độ sâu từ LP đang hoạt động | Cùng hạn mức quỹ, nhu cầu mua tăng tương ứng với độ sâu |
| Đối chứng | Chính sách so với no_rescue cùng seed/lịch quỹ/thời hạn; lịch sử trình bày riêng | Dashboard kiểm tra cấu hình đối chứng; không quy mọi khác biệt với replay cho chính sách |
| Hiệu chỉnh | Chuẩn hóa theo gate, cân bằng pha và phạt onset theo ngưỡng 6 giờ | Onset lệch 47 giờ không bị phạt yếu như v2; train objective không đọc giai đoạn sau 10/05 |
| Bằng chứng | Hash mã/dữ liệu/tham số, status/run archive, tính lại metric từ trajectory | Audit từ chối báo cáo cũ, chưa hoàn tất hoặc sai cấu hình |

## Giới hạn khoảng tìm kiếm đã sửa

Với pool 50 triệu USD quy đổi, recovery 3,6 phút và cap arbitrage cũ tối đa 10^9,5 UST/ngày, dòng đến đều theo phút tạo trần spread khoảng 25,55%. Dữ liệu có 61/576 bucket có swap vượt mức đó, chiếm khoảng 43,63% native volume. Bằng chứng và phép tính trong `search_constraints_native_v3.json`.

Mở upper bound `log_arb_capacity` đến 10,5 cho phép thử tốc độ cao hơn. Đây là tham số năng lực giao dịch, không tăng token, vốn arbitrage hoặc quỹ cứu trợ; mọi fill vẫn bị chặn bởi các tồn lượng và quote lợi nhuận. Probe cùng tham số nâng capacity lên 25,30 tỷ UST/ngày giảm objective 35,075 → 29,746, giảm log RMSE nguồn cung 1,710 → 0,979 và tăng native volume 3,34 → 6,11 tỷ UST; MAE UST và nhóm xấu đi. Do đó cần hiệu chỉnh chung, không chọn probe chỉ vì một metric tốt hơn.

## Những phương án chưa đưa vào bản chính

- Bán LUNA của người giữ cũ: có dòng tiền và token đầy đủ, nhưng các hazard đã thử với bộ tham số cố định làm độ khớp tổng thể xấu hơn. Xem `old_holder_candidate/` và `old_holder_candidate_checkpoint_all_v3/`.
- Giới hạn mua ngoài theo UST/ngày: giảm lượng UST mua ngoài từ 12,765 tỷ xuống 219,2 triệu trong cùng snapshot, nhưng làm native mint tăng tới 1,17×10^20 LUNA và sai số lớn hơn. Không tích hợp trực tiếp; xem `outside_quantity_checkpoint/`.
- Hai kết quả trên chỉ là ablation giữ nguyên tham số. Chúng không chứng minh các cơ chế đó luôn sai; chúng cho thấy việc thêm cơ chế chưa hiệu chỉnh không tự tạo bản tốt hơn.

## Bằng chứng governance native redemption và quyết định hiện tại

Đã ghi riêng [bằng chứng governance](<D:/New folder/luna-ust-sim/outputs/improvement/GOVERNANCE_REDEMPTIONS_VI.md>) từ [PDF kiểm toán JS Held](<D:/New folder/luna-ust-sim/data/external/LFG-Audit-2022-11-14.pdf>) và dữ liệu tái lập. Nguồn hỗ trợ một hành động native khác arbitrage: TFL đổi UST để nhận LUNA rồi giữ/stake nhằm phòng vệ quản trị. Cơ chế này chưa có trong engine đang đóng băng; chưa có probe chứng minh lợi ích đối với fidelity và không sửa source trong lúc hai fits chạy.

| Bằng chứng | Kết luận được phép |
|---|---|
| JS Held trang 14, đoạn 36-38: 10 bot, 5.286 swaps được khảo sát trong 09-11/05; 220.694.577 LUNA chuyển tới ví staking ngày 12/05 | Có native redemption phục vụ staking; ngày staking không phải ngày burn toàn bộ. LUNA được chuyển không phải gross mint gồm phí. |
| UST ước lượng 785.501.572-825.615.759; midpoint 805.558.665 | Thay số tweet cũ khoảng 883,5 triệu bằng range có qualification; không biến midpoint thành lượng burn chính xác hoặc nghiệm bắt buộc. |
| Bảng IA.1 nguồn: cùng 10 địa chỉ, tổng làm tròn 825 triệu UST, 502 triệu USD, 5.269 swaps | Kiểm tra chéo quy mô và danh tính. Count khác kiểm toán, log trader không được phát hành; chưa thể khớp từng swap hoặc nhận dạng lịch. USD là thị giá giao dịch, không phải vốn cấp thêm. |
| Midpoint / tổng native burn 07-13/05 = 10,7542% | Quy mô có thể quan trọng với phí/pool/supply. Flow này đã nằm trong observed aggregate; không cộng 805 triệu thêm lên target hoặc mặc định toàn bộ là flow mới phải thêm vào mô hình. |
| 1.796.182.310 UST TFL chuyển cho LFG; ending LFG UST 1.847.079.725 | Chuyển nội bộ khác mua thị trường và burn. Số dư UST cuối vẫn được giữ, không có bằng chứng burn toàn bộ. |

Phân biệt sổ TFL: gross purchases 08-10/05 là **1.901.559.334 UST / 1.773.199.279 USD**; net purchases là **1.464.738.304 UST / 1.375.600.151 USD**. Own net contributions vẫn có cap **345.172.619 USD** cho UST và **268.444.270 USD** cho LUNA. Số **1.086.051.513 UST** lấy estimated purchases thay mặt LFG trừ Jump không được gắn nhãn total net TFL. Gross sales/recycling không tạo grant mới.

Jump chuyển 1.515.689.462 UST sang TFL qua Binance nội bộ và on-chain, chủ yếu ngày 11/05; đó là chronology bàn giao, thiếu chronology mua. Thêm UST từ khoản chuyển sau khi đã mô phỏng mua bằng cùng BTC sẽ đếm tài sản hai lần. TFL Binance còn có 796.368.008,78 UST đầu 08/05, nhưng không đủ chứng minh quyền sở hữu tại snapshot 06/05. Nếu phân bổ ownership đầu kỳ sau này, phải chuyển từ UST đã có trong tổng supply và kiểm tra thời điểm, không cấp token hoặc backing USD mới.

Quyết định hiện tại là chờ kết quả fit của nguồn đã đóng băng rồi đánh giá phần sai số native/supply; không tích hợp lịch burn chưa kiểm tra. Nếu cần một mở rộng nhỏ, ưu tiên intent governance có cap thấp/midpoint/cao, chỉ phục vụ từ UST quỹ đã sở hữu, dùng chung virtual pool/oracle/phí và giữ hoặc stake LUNA. Thiếu token giữ backlog. Lịch đều/dồn muộn trong 09-11/05 phải là giả định độ nhạy. Không ép mint 220.694.577 LUNA, không thêm vốn giả, không hứa một loại chính sách thứ năm hoặc mô hình validator đầy đủ.

Độ khớp tổng native/supply không chứng minh được causal attribution riêng cho governance, Jump hay arbitrage. Không tự áp hành động lịch sử này vào phản thực tế hoặc quy mọi khác biệt replay/policy cho một biện pháp cứu trợ; kết quả vẫn phụ thuộc ownership, lịch thực thi chưa biết, độ sâu và hành vi trong mô hình nhỏ.

## Việc phải hoàn tất trước kết luận

Phạm vi đã đổi theo yêu cầu người dùng: chỉ tái hiện lịch sử, không hoàn thiện chính sách cứu vãn. Quote và execution bán LUNA của arbitrage đã được sửa, kiểm chứng tại `native_vwap_integrated_check.json`; bộ tham số cũ vẫn chưa đạt fidelity. Cần hiệu chỉnh lại sau khi đóng băng mã; so sánh v2/v3 trên cùng định nghĩa quan sát; kiểm tra nhiều seed lịch sử và bước thời gian. Báo riêng phần trong mẫu và holdout tham số.

## Quan sát và quyền sở hữu được sửa sau lần gián đoạn

- Hai optimizer đã dừng, không công bố là hoàn tất. Checkpoint và nguồn được giữ tại `interrupted_runs/20261010T141023Z`.
- Nhật ký Anchor kết thúc 13/05 23:59:39 UTC. Sau bucket 14/05 00:00, nhóm người gửi và observed deposit/withdraw là thiếu dữ liệu; không điền zero rồi chấm đường chuẩn giữ phẳng. Giữ 768 điểm mỗi nhóm, censor 191 điểm; validation có 289 điểm mỗi nhóm. Sáu gate không đổi.
- A/B chỉ bị loại khỏi quyết định tự sinh trong ngày có hành động ngoại sinh được cung cấp, gồm bucket cuối ngày theo quy ước right-end. Trước/sau ngày đó họ phản ứng như các ví cùng nhóm. Lỗi khóa họ suốt sự kiện được sửa mà không nhập các giao dịch tương lai của A/B vào mô hình.
- Kiểm conservation tổng chưa đủ nếu một chủ có số dư âm được chủ khác bù. Thêm kiểm riêng tồn lượng ngoài thị trường, market LUNA, LUNA phí và các tài khoản USD/UST; market inventory ban đầu không được vượt nguồn cung LUNA đã quan sát. Xuất tồn lượng ra trajectory để giải thích native bị thiếu token hay thiếu tiền.
- 6 kiểm tra quyền sở hữu/A-B cùng 9 coverage và 21 kiểm tra cơ chế hiện có đạt 36/36, ghi trong `historical-corrections-tests.xml`. Dữ liệu processed và quality report đã cập nhật từ nguồn gốc giữ nguyên.

## Chọn giữa hai checkpoint cơ chế

Replay nguồn engine bất biến `6cb4c607…` với metric coverage mới: core token-depth loss 7,83339, USD-depth riêng 10,26943. Chỉ thêm outside cap 7B với tham số core giữ nguyên tăng loss tới 38,40469; không chọn. USD-depth riêng còn trộn depth cũ khi mua LUNA cứu trợ với depth mới trên thị trường; không đưa vào engine chính chỉ vì một metric nguồn cung tốt hơn.

Core cuối 10/05 cho LUNA khoảng 42,94 USD so với 16,28 USD thực tế; cuối 11/05 khoảng 21,33 so với 1,014. Native bị thiếu market UST trong 502 phút dù còn vốn, outside account giữ khoảng 10,155 tỷ UST. Nguồn cung cuối 13/05 chỉ khoảng 446,68 tỷ so với 6,800 nghìn tỷ. Những sai lệch này hướng kiểm tra về cầu có tồn kho và áp lực bán LUNA, không hướng ép chuỗi giá thật vào quyết định. Bằng chứng ở `selection_diagnostic/20261010T141811513371Z` là diagnostic giữ nguyên tham số, không phải fit hoàn tất hoặc validation độc lập.
