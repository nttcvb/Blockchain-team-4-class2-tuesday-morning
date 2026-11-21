# Chọn cơ chế tái hiện sau khi sửa phạm vi quan sát

**Kết luận: giữ cơ chế token-depth hiện tại làm điểm bắt đầu cho lần hiệu chỉnh mới; chưa đưa USD-depth, cap ngoài 7B hoặc bán LUNA của người giữ cũ vào bản chính.** Trong các phép chạy cố định đã kiểm, cả ba thay đổi đều chưa cải thiện độ khớp toàn sự kiện. Bản core vẫn chưa tái hiện đủ sát: chỉ gate thời điểm mất neo đạt, còn các sai số giá, tiền gửi, nguồn cung và nhóm chưa đạt.

Đây là chẩn đoán cơ chế lịch sử, không có thí nghiệm chính sách. Hai checkpoint đều từ lần hiệu chỉnh bị ngắt; không gọi chúng là nghiệm đã hoàn tất. Core checkpoint là call 1342, loss gốc 7,809837; USD checkpoint tốt nhất là evaluation 171, loss gốc 10,322593, tiến trình dừng ở 172/220 evaluation. Các con số bên dưới được chạy lại và đo bằng chuẩn coverage mới, không lấy loss gốc làm điểm hiện tại.

## Bằng chứng và cách so sánh

Ba replay cùng lịch sử May6–15, 1000 người gửi tiền, 20 arbitrageur, seed42, deterministic, funding early, bước quyết định 15 phút và bước thị trường 1 phút. Cơ chế nền được nạp từ archive engine SHA256 `6cb4c607cf1337d9ebb9b225041f8fdae0f37f1c06b8ea1d980ffcb0ea4a7427`, nên các chỉnh sửa engine sau replay không âm thầm thay bằng chứng này. Các file data/metrics/calibrate dùng chuẩn quan sát đã sửa, với SHA tương ứng `6331fab0…378e9`, `c71e0345…d48b9`, `7aa5ff34…de583`.

Sáu cột mục tiêu dùng cho objective (`ust_price`, `luna_price`, `anchor_deposits`, `luna_supply`, `native_ust`, `native_fee`) khớp chính xác bản mục tiêu đã lưu của lần fit gốc. `observed_withdraw`/`observed_deposit` và nhóm được censor sau khi nguồn giao dịch hết quan sát. Group MAE hiện dùng 768 cặp thời điểm cho mỗi nhóm, kết thúc May14 00:00 UTC; 191 dòng sau đó không được coi là zero hoặc tồn lượng đã quan sát. Replay objective cũ trên OLD saved target/groups khớp loss gốc đến sai số dưới `1e-11`; objective mới được tính riêng.

Artifact đầy đủ: [comparison.json](<D:/New folder/luna-ust-sim/outputs/improvement/selection_diagnostic/20261010T141811513371Z/comparison.json>), [script](<D:/New folder/luna-ust-sim/outputs/improvement/checkpoint_selection_diagnostic.py>), các snapshot nguồn trong cùng thư mục `sources/`, trajectory, ledger và tồn lượng từng chủ theo phút. Script bản ba-replay nguyên gốc cũng đã lưu riêng trước khi bổ sung nhánh probe người giữ LUNA. Không có optimizer hoặc thay đổi core/input/checkpoint.

## Độ khớp toàn sự kiện

| Chỉ số | Core checkpoint | USD checkpoint | Core + cap ngoài 7B | Giới hạn gate |
|---|---:|---:|---:|---:|
| Objective mới | 7,833391 | 10,269433 | 38,404688 | — |
| UST MAE, USD | 0,108839 | 0,119873 | 0,102130 | ≤0,05 |
| Tiền gửi NRMSE | 0,123395 | 0,111287 | 0,123299 | ≤0,10 |
| LUNA price log10 RMSE | 1,184475 | 1,327187 | 3,208316 | ≤0,50 |
| LUNA supply log10 RMSE | 0,703187 | 0,629448 | 3,139806 | ≤0,50 |
| Group MAE max, chỉ cặp quan sát | 0,152754 | 0,143881 | 0,152743 | ≤0,15 |
| Onset lệch tuyệt đối, giờ | 0,25 | 1,50 | 0,25 | ≤6 |
| Native daily NRMSE | 0,177911 | 0,340221 | 0,178066 | Chẩn đoán thêm |
| Native fee MAE | 0,062963 | 0,072818 | 0,063016 | Chẩn đoán thêm |
| Số gate đạt | 1/6 | 2/6 | 1/6 | 6/6 |

USD candidate có supply và tiền gửi tốt hơn cục bộ, nhưng giá UST/LUNA, timing và lịch native tổng thể xấu hơn. Giá LUNA cuối sự kiện đẹp hơn không đủ để chọn nó: LUNA price log RMSE sau May11 là 1,8721, so với 1,6705 của core. Trước mất neo, core LUNA log RMSE chỉ 0,03177; từ onset đến May11 là 0,21745. Sai lệch lớn tập trung vào đoạn sụp đổ sau May11.

## Hình dạng sụp đổ của core

Giá mô phỏng cao hơn thực tế trước đoạn hyperinflation: cuối May10 LUNA 42,94 USD so với 16,28 USD; cuối May11 21,33 USD so với 1,014 USD. LUNA xuống dưới 10 USD chậm 26,5 giờ và dưới 1 USD chậm 26 giờ. Supply vượt một tỷ LUNA chậm 25,5 giờ.

Sau đó mô hình lao dốc quá dồn: từ LUNA dưới 1 USD lúc May12 15:00 đến dưới 0,001 USD lúc 16:00 chỉ một giờ. Supply vượt 10 tỷ và 100 tỷ cùng timestamp 16:00. Trong thực tế, các mốc 10 tỷ và 100 tỷ cách nhau 11 giờ (May12 12:00 và 23:00), rồi vượt một nghìn tỷ May13 02:00. Core không vượt một nghìn tỷ.

Cuối sự kiện, core có 446,68 tỷ LUNA so với 6.800,42 tỷ quan sát; giá LUNA 0,008486 USD so với 0,0002133 USD, cao khoảng 40 lần. UST mô phỏng chỉ 0,000754 USD so với 0,151742 USD. Như vậy đúng onset một giờ không đồng nghĩa đúng toàn bộ sự kiện.

Native phục vụ 5,980 tỷ UST so với 7,491 tỷ quan sát. Đặc biệt May11 mô hình chỉ 1,952 tỷ so với 4,145 tỷ; May12 lại 2,530 tỷ so với 1,794 tỷ. Sai lệch cần sửa là lịch lan truyền/run và lượng mint theo pha, không chỉ điểm cuối.

## Outside UST trap và độ sâu thị trường

Core kết thúc với outside account giữ 10,155 tỷ UST và không có cơ chế bán lại. Sau May11, có 502 phút native đang mở theo trạng thái mô hình nhưng market UST rỗng; cả market USD, arbitrage USD và outside USD đều còn trên một triệu USD. Trạng thái halt được cập nhật ở bước outer 15 phút, nên số phút này là chẩn đoán vận hành của mô hình, không phải block-level chain reconstruction. Tại May13 00:00, market UST bằng zero trong khi market còn 15,506 tỷ USD và arbitrageur còn 701,76 triệu USD. Native ngừng vì token bị chuyển sang chủ thụ động, không phải vì hết USD hoặc còn một đống LUNA arbitrage chưa bán.

Đối chứng chỉ thêm cap ngoài 7 tỷ UST, giữ nguyên tất cả tham số core, loại bỏ các phút native-open thiếu market UST. Nhưng cuối supply thành `1,253×10^18` LUNA và giá `2,909×10^-9` USD; objective tăng lên 38,40. Cap không tự tạo bản đúng hơn. Nó làm lộ phản hồi giá–mint rất mạnh của bộ depth hiện tại, đồng thời chứng minh tồn lượng UST thụ động đang làm giảm phản hồi đó trong core.

Không suy ra từ một ablation rằng token-depth có giới hạn toán học khiến mọi bộ tham số đều không thể đạt. Dữ liệu ở đây chỉ chứng minh bộ tham số hiện có đang bù một thiếu hụt cơ chế bằng thiếu hụt khác; thêm một ràng buộc tồn lượng chưa hiệu chỉnh làm sai số lớn hơn. USD-depth được fit cục bộ 172 evaluation chưa vượt core, nên chưa có bằng chứng để thay cơ chế rồi bỏ qua refit.

USD candidate dùng `D_tokens = H0 × (P/P0)^eta / P`, với H0≈6,073 tỷ USD, eta≈0,7943 và outside cap≈6,940 tỷ UST. Historical LUNA rescue vẫn dùng depth cũ theo supply và khớp mua tại spot; đây là cơ chế lai cần sửa trước bất kỳ promotion nào. Trong ba replay này, tổng historical LUNA buy đều 268.444.270 USD, nên không gán phần chênh objective cho khác biệt tổng tiền cứu trợ. Quote/fill/closing không có cùng một cơ chế ở nhánh mua vẫn là qualification kỹ thuật.

## Giả thuyết người giữ LUNA ban đầu

Core có khoảng 649,46 triệu LUNA thuộc `outside_luna` ngay từ đầu, nhưng tồn lượng này hoàn toàn thụ động. Sai số dương và trì hoãn LUNA giảm trong May9–11 phù hợp về dấu/thời gian với khả năng thiếu áp lực bán từ người giữ cũ. Đây là giả thuyết nhân quả hợp lý, chưa phải bằng chứng về cường độ bán thực tế.

Ý tưởng đã từng được thử trong [old holder prototype](<D:/New folder/luna-ust-sim/outputs/improvement/old_holder_candidate_checkpoint_all_v3/PROTOTYPE_VI.md>) và ghi ở DECISIONS_VI.md; các hazard giữ tham số cố định trước bản VWAP hiện hành cũng xấu hơn. Phép kiểm bổ sung hiện tại chỉ đúng **một** cấu hình do parent chỉ định: cùng core checkpoint, cap UST ngoài 7B, hazard bán LUNA/ngày `0,5 × min(1, max(0,1−UST_price)/0,1)`. Lệnh bán khớp VWAP trước quote arbitrage; LUNA thực chuyển outside→market, USD thực chuyển market→outside và tài khoản phí. Spot chuyển tới endpoint đúng một lần, lệnh không được cộng lại vào net LUNA closing impact.

Kết quả [holder_cap_7B_result.json](<D:/New folder/luna-ust-sim/outputs/improvement/selection_diagnostic/20261010T141811513371Z/holder_cap_7B_result.json>): objective **364,8716**, UST MAE 0,37158, LUNA log RMSE 8,26562, supply log RMSE 5,82914, onset sớm **40,5 giờ**, native chỉ 1,233 tỷ UST; 0/6 gate. Bán 637,85 triệu LUNA cũ, gross 6,4523 tỷ USD lấy từ market. Chỉ hai ngày May6–7 đã bán 32,83 triệu LUNA và lấy khoảng 2,216 tỷ USD, rồi khuếch đại run quá sớm.

Từng giao dịch holder được kiểm lại bằng tích phân `P×D×log1p(q/D)` và endpoint `P/(1+q/D)`; tồn lượng các chủ đã capture không âm, engine invariants kiểm mỗi bước outer. Sai số conservation USD tối đa khoảng 0,000126 USD. Sai số LUNA tuyệt đối 2688 token xuất hiện ở nguồn cung `8,257×10^17`, cần đọc theo tỷ lệ máy tính, không coi đây là 2688 LUNA bị thiếu ở mức nguồn cung bình thường. Phép kiểm này không thiết lập parity cadCAD mới và không refit.

**Không promote hazard trên.** Kết quả không bác bỏ việc holder thật bán LUNA; nó bác bỏ việc thêm nguyên cường độ này vào bộ tham số đã bù thiếu áp lực bán. Thay hazard bằng một lịch theo giá thực để có hình đẹp sẽ không còn là ABM tái hiện nội sinh. Cần hiệu chỉnh chung hoặc quan sát độc lập trước khi chọn cơ chế mới, không thêm một loạt probe cố định nữa.

## Quyết định dùng ngay

Giữ checkpoint core làm warm start cho lần fit hoàn tất trên engine và chuẩn coverage hiện hành. Đo cùng các gate và giữ rõ sai lệch theo pha/native, không gọi fit là đạt chỉ vì optimizer kết thúc hoặc onset đúng. USD-depth/cap/holder vẫn là research artifacts; chưa có cả lợi ích toàn sự kiện lẫn parity cho promotion. Nếu lần fit mới vẫn giữ hình sụp đổ muộn-rồi-dồn, đó là bằng chứng cần thay cơ chế được hiệu chỉnh chung, không hạ gate hoặc ghép các trajectory tốt ở từng pha.
