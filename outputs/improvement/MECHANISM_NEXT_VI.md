# Cơ chế cần xử lý nếu frozen fit còn thất bại

Rà soát 10/10/2026. Không sửa core đang fit, targets, sources.json hoặc checkpoints. Các probe dùng một snapshot bất biến của checkpoint all tại call 4, SHA tham số `296743be6636f1915c9b1e68d51569e2fcf510a61916ee64e89b77f89c0353c8`; engine SHA `6cb4c607cf1337d9ebb9b225041f8fdae0f37f1c06b8ea1d980ffcb0ea4a7427`. Không chạy optimizer. Đầu ra dưới đây chưa được hiệu chỉnh lại và không thay thế kết quả cuối của hai fit đang chạy.

## 1. Native stall là thiếu token sẵn bán, không thiếu USD hay LUNA tồn kho của arbitrage

Diagnostic của đúng engine/snapshot ghi các tồn lượng trước native quote từng phút. Lúc **11/05 18:00 UTC**, `market_ust=0`, người mua ngoài giữ **8,7603 tỷ UST**, còn **927,83 triệu USD**; dealer còn **15,966 tỷ USD**, arbitrage còn **316,02 triệu USD** và **0 LUNA**. Native vẫn mở nhưng `desired_arb=0`. Đến 12/05 12:00, người ngoài giữ **9,5185 tỷ UST**, market UST vẫn bằng 0. Không phải ngân sách quote, restriction residual bid, arb working capital hay chưa bán được LUNA khiến lần đổi này dừng.

Nguyên nhân trong mô hình: outside UST buys chạy trước arbitrage, với demand theo USD/ngày; số token mua bằng USD chia giá. Khi UST xuống gần 0, một khoản chi nhỏ mua nhiều tỷ token. Outside không có exit hoặc redemption, nên các UST này vĩnh viễn không còn sẵn cho native. UST vừa được người gửi bán ra sau đó cũng bị outside hấp thụ trước arb. Đây là thiếu hành vi/ownership trong mô hình, **không phải lỗi bảo toàn token hoặc cash**.

Bằng chứng tái lập: [stall_diagnostic.json](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/stall_diagnostic.json>), [minute_quotes.parquet](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/minute_quotes.parquet>), [diagnose_stall.py](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/diagnose_stall.py>). Baseline được tính lại và khớp loss/metric của snapshot, không đọc mục tiêu trong policy hoặc market.

### Mở rộng tối thiểu ưu tiên: giới hạn inventory và cho outside thoát vị thế

Thêm một capacity UST danh nghĩa cho **pool người mua ngoài cụ thể**, cùng target inventory giảm khi peg suy yếu. Mua giới hạn bởi target còn thiếu, cash còn sở hữu và UST có sẵn. Khi lượng nắm vượt target, đặt lệnh bán có hazard theo thời gian vật lý; dealer trả USD hữu hạn, UST quay lại market và có thể được arbitrage mua/đổi. Giữ queue nếu không khớp; không tự burn, không tạo grant. Tên tham số phải riêng, như `outside_max_ust`; không đổi nghĩa `external_ust_inventory` trong core.

Các số stock lịch sử chỉ hỗ trợ prior và kiểm tra bên ngoài. Other UST tăng 1,075 tỷ ngày 06/05 lên 3,566 tỷ ngày 10/05 rồi về 1,495 tỷ ngày 15/05. CEX tăng 0,738 lên 2,930 tỷ; Other+CEX+DEX+DeFi+Bridge lần lượt 4,785 → 8,948 → 7,057 tỷ UST. Other không đồng nhất với người mua outside; custody CEX không nhận dạng beneficial owner. Không ép inventory của mô hình chạy theo các dòng này hoặc suy ra exit hazard từ chênh lệch ngày. Xem [OUTSIDE_HOLDERS_VI.md](<D:/New folder/luna-ust-sim/outputs/improvement/OUTSIDE_HOLDERS_VI.md>) và mapping Figure 2 của bộ tái lập. Nghiên cứu gốc ghi nhận mua bắt đáy ngày 09–10/05, nhưng không xác nhận fixed USD/day: [Liu, Makarov và Schoar, PDF trang 7 và 30](https://mitsloan.mit.edu/shared/ods/documents/?PublicationDocumentID=9764).

Sáu probe đã kiểm tra cùng snapshot, giữ các tham số khác. Inventory cap 4 tỷ là giả định thử, không số quan sát chính xác. Prototype đầu lấy giá trị 4 tỷ từ field config làm tiện ích số; source snapshot đã lưu nguyên dạng thực thi. Source candidate tiếp theo đã tách rõ `max_outside_ust=4e9`, được dùng trong bốn probe depth sau, không thay semantic core.

| Probe | UST MAE | LUNA log RMSE | Supply log RMSE | Native burn, tỷ UST | Supply cuối, LUNA |
|---|---:|---:|---:|---:|---:|
| Baseline | 0,14724 | 1,86906 | 1,09587 | 5,38090 | 9,660×10^10 |
| Cap 4 tỷ, không exit | 0,14971 | 4,72309 | 3,63863 | 5,39511 | 7,941×10^17 |
| Target ∝ sqrt(price), exit hazard 2/ngày | 0,14971 | 4,72170 | 3,63648 | 5,39511 | 7,857×10^17 |
| Target ∝ price, exit hazard 2/ngày | 0,14971 | 4,72172 | 3,63650 | 5,39511 | 7,858×10^17 |
| Target ∝ sqrt(price), exit hazard 0,5/ngày | 0,14971 | 4,72170 | 3,63649 | 5,39511 | 7,858×10^17 |
| Target sqrt(price), exit 2/ngày + LUNA bids 25 triệu USD/ngày | 0,14735 | 4,06636 | 3,63648 | 5,39511 | 7,857×10^17 |

Cap/exit giải quyết việc outside hút và giữ hơn 10 tỷ UST, nhưng **không đủ để khớp sự kiện** với tham số chưa refit: thanh khoản LUNA sụp, oracle gần floor và gross mint vượt nhiều bậc độ lớn. Không chọn một variant này làm bản thắng. [Ablation và ledger](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/ablation.json>) ghi đầy đủ asset errors và native theo ngày. Mỗi outer step chạy invariant USD/UST/LUNA và claims.

## 2. Khoảng tìm kiếm liquidity/growth có thể hạn chế hình dạng price–supply

Với token depth `D(S)=D0*(S/S0)^g`, net LUNA bán xấp xỉ `gamma*dS`, và bước rất nhỏ, native-only cho:

`ln(P/P0) = -gamma*(P0*S0/depthUSD)*F_g(S/S0) + betaBTC*ln(B/B0)`

`F_1(R)=ln(R)`; nếu `g!=1`, `F_g(R)=(R^(1-g)-1)/(1-g)`.

Observed supply tăng **9.073,79 lần**, giá 82,7295 → 0,0002133 USD, tương ứng exponent toàn kỳ **1,4121**. Native gross-weighted delivered fraction thực tế là **0,94703**, khác fee trung bình theo khối lượng UST. Sau trừ BTC với beta 2,25545 của snapshot, native cần log price fall khoảng 12,5217.

| Growth g | Initial USD depth xấp xỉ cần để khớp hai endpoint |
|---:|---:|
| 1,0 | 42,73 tỷ USD |
| 1,1 | 28,04 tỷ USD |
| 1,2 | 19,66 tỷ USD |
| 1,3 | 14,62 tỷ USD |

Search cũ chỉ cho depth tối đa 15,85 tỷ và growth tối đa 1,1. Trong phép xấp xỉ, tại upper bounds này giá cuối khoảng 1,4×10^-8 USD, thấp hơn quan sát hơn bốn bậc độ lớn. Growth 0,342 của snapshot làm elasticity tăng mạnh theo supply, phù hợp với hiện tượng cascade quá mạnh khi gỡ stock trap.

Đây là **chẩn đoán khoảng tìm kiếm, không proof universal infeasibility**: dùng gamma cố định, bán native liên tục, không outside LUNA orders và không floor; thực tế fees, cash, oracle và bước phút thay đổi. Bằng chứng số và script: [depth_theory.json](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/depth_theory.json>), [price_depth_theory.py](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/price_depth_theory.py>).

Bốn điểm depth/growth được chỉ định bổ sung, cùng outside cap 4 tỷ/no exit, cho kết quả:

| Depth USD / growth | UST MAE | LUNA log RMSE | Supply log RMSE | Native tỷ UST | Supply cuối | LUNA cuối USD |
|---|---:|---:|---:|---:|---:|---:|
| 30 tỷ / 1,0 | 0,32249 | 3,16325 | 2,15635 | 5,66819 | 8,719×10^8 | 44,20 |
| 45 tỷ / 1,1 | 0,32216 | 3,19009 | 2,15784 | 5,69465 | 8,667×10^8 | 48,97 |
| 60 tỷ / 1,1 | 0,32202 | 3,20247 | 2,15855 | 5,70245 | 8,643×10^8 | 51,33 |
| 45 tỷ / 1,2 | 0,32216 | 3,19044 | 2,15786 | 5,69489 | 8,667×10^8 | 49,04 |

Nâng depth quá cao ở cùng warm parameters ngăn collapse, nên không phải warm viable. Giá/supply trước 11/05 đòi elasticity lớn, còn toàn kỳ cần elasticity thấp hơn; growth >1 làm elasticity giảm theo supply và đáng tìm kiếm chung. Sau frozen fit, có thể nới `log_luna_depth` upper đến khoảng 10,8 và growth upper đến 1,8, giữ old point trong search, **không tăng vốn thực**. Các bounds này là range giả thuyết cần sensitivity, không độ sâu đo được. Phải refit chung với outside inventory/exit thay vì chọn một point theo endpoint. [Bốn probe](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/depth_bounds/comparison.json>) không thay checkpoint.

### Alternative liquidity theo USD thay vì tăng token depth theo nguồn cung

Bốn structural probes bổ sung được root chỉ định, ngoài buyer capacity **7 tỷ UST/no exit** (prior aggregate có uncertainty), với cùng checkpoint call 4. Đặt riêng các tham số prototype `initial_usd_depth`, `price_depth_power` và `cap_by_market_usd`:

`D_tokens = initial_usd_depth * (P/P0)^price_depth_power / P`.

Như vậy actual USD depth giảm khi giá/confidence giảm, nhưng không vô tình nhân USD depth bằng cả price collapse và một giả định token supply growth. Depth vẫn được frozen ở opening price cùng cash, dùng chung cho expected profit, VWAP execution và closing quote. Cash-scaled variant chặn USD depth theo cash dealer đang sở hữu. Không đổi nghĩa core `luna_depth_growth`; không đọc observed prices để điều khiển.

| Initial USD depth / power | UST MAE | LUNA log RMSE | Supply log RMSE | Native tỷ UST | Supply cuối | LUNA cuối USD |
|---|---:|---:|---:|---:|---:|---:|
| 6 tỷ / 0,8 | 0,12449 | 1,34996 | 0,65143 | 8,85800 | 1,244×10^12 | 0,003246 |
| 4 tỷ / 0,5 | 0,12985 | 1,70034 | 1,58447 | 13,08363 | 3,298×10^14 | 0,00001235 |
| 8 tỷ / 1,0 | 0,11960 | 1,52025 | 0,90172 | 7,75482 | 2,126×10^14 | 0,00001803 |
| 1 tỷ / 0,0, cash-scaled | 0,28328 | 1,72184 | 1,37180 | 13,71875 | 2,550×10^10 | 0,14465 |

**Điểm 6 tỷ/power 0,8 là warm hypothesis đáng ưu tiên refit**, cải thiện UST/LUNA/supply và group error trên baseline call 4; group MAE 0,14850 đạt gate, onset vẫn lệch 9,5 giờ, deposits NRMSE 0,13698. Native total cao hơn thực 18,25% và daily NRMSE 0,32655 xấu hơn baseline 0,14656. Vì vậy chưa đạt fidelity và không chọn vì endpoint supply gần hơn. Điểm 8 tỷ/power 1,0 gần native total hơn nhưng supply cao 31 lần.

USD errors tối đa của bốn probe ≤0,00055 USD; LUNA error lớn nhất 0,375 token trên supply khoảng 2,126×10^14, thuộc precision floating-point và nằm trong invariants. Các lần chi chỉ dùng vốn hiện có, BTC đã bán 45.027,83, không cấp quỹ mới. Ledger và minute source snapshot nằm tại [usd_depth/comparison.json](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/usd_depth/comparison.json>); script [usd_depth_probes.py](<D:/New folder/luna-ust-sim/outputs/improvement/posthalt_candidate/usd_depth_probes.py>) ghi đúng bốn điểm. Không có optimizer hoặc chạy bổ sung sau chúng.

## 3. Post-native thiếu lệnh mua LUNA có thể giải thích đường bật lại

Sau historical native shutdown, cứu trợ mua LUNA đã hết, `outside_luna` trong core không giao dịch. Giá chỉ phản ứng BTC, các arb sale còn lại và funded floor. Observed 13/05 11:45 → 14/05 11:00: LUNA tăng **38,12 lần**, supply giữ 6,8004 nghìn tỷ, BTC giảm 4%. Nếu core khớp giá/supply ở endpoint đầu, dòng USD dương vào dealer tối đa 250 triệu/ngày từ outside UST buys, residual fraction≤0,2 và betaBTC≤5 chỉ cho rebound tối đa khoảng **1,50 lần** trong cửa sổ đó. Đây là bound có điều kiện khớp endpoint, không khẳng định gate RMSE tổng thể bất khả thi.

Mở rộng thứ hai sau stock trap: một người mua LUNA với cash hữu hạn, phản ứng việc phát hành đã yên ít nhất vài giờ và depeg được quan sát. Dùng lại external USD có sẵn hoặc tiền bán tài sản thật; không tăng reserve. Mua token market đã sở hữu, tính giá thực nhận và price impact từ cùng inverse demand curve. Không tự bật lại giá bằng floor mới, không dùng ngày/giá rebound quan sát làm trigger. Prototype dùng `p_buy(q)=P*(1+q/D)`, tổng chi `P*(q+q²/(2D))`, giới hạn cash/tokens, giữ oracle lag hiện có. Một probe 25 triệu/ngày giảm LUNA log error 4,722→4,066 trong variant inventory, nhưng vẫn tệ hơn baseline vì supply đã sai; chưa tích hợp.

## 4. Governance swaps: bằng chứng mạnh, chưa phải phương án sửa gap nhiều bậc độ lớn

JS Held và table IA.1 xác nhận các bot TFL governance khoảng 785,5–825,6 triệu UST, tức midpoint khoảng **10,75%** native aggregate. LUNA được giữ/stake, không bán ngay; đây là loại intent khác arbitrage profit và có thể tranh chấp virtual pool. Xem [GOVERNANCE_REDEMPTIONS_VI.md](<D:/New folder/luna-ust-sim/outputs/improvement/GOVERNANCE_REDEMPTIONS_VI.md>) và [JS Held audit](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf).

Nếu thêm, chỉ burn `fund_ust` đang sở hữu, dùng cùng pool/oracle, giữ backlog thiếu token, ghi lịch 09–11/05 là giả định phân bổ trong cửa sổ evidence. Không thêm 805 triệu lên observed target, không đảo ngược target LUNA để ép mint, không tự burn ending LFG UST. Giờ từng bot swap, custody Jump và inventory TFL tại 06/05 còn thiếu. Governance có thể cải thiện native ownership/fees, nhưng quy mô 10,75% không tự giải thích chênh lệch price/supply hàng nghìn lần; ưu tiên stock trap và thanh khoản trước.

## Quyết định đề nghị sau khi hai fit hiện tại hoàn tất

1. Đọc toàn bộ gates/train/holdout và hidden stocks ở nghiệm cuối; không dùng checkpoint đang chạy làm final.
2. Nếu còn stall do outside ownership, triển khai riêng capacity + exit trong ABM, dùng prior có nhãn; đối chiếu token-supply depth rộng hơn với alternative opening USD-depth. Điểm 6 tỷ/power 0,8 đáng dùng làm warm hypothesis, rồi refit chung và kiểm tra cả native ngày/fee, conservation, zero-extension parity và 5/15-minute stability.
3. Nếu price rebound còn không tái hiện, thêm LUNA buyer cash/token đầy đủ. Governance chỉ là intent ownership bổ sung có evidence và lịch nhạy cảm.
4. Chỉ chọn model sau comparison trên cùng targets, phản hồi các metric xấu đi và policy rerun với tham số chung. Các probe ở đây xác định vấn đề và range tiếp theo, **chưa xác nhận mô hình đạt fidelity**.
