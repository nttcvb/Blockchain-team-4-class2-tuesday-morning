# Bằng chứng hoán đổi UST phục vụ staking và quản trị

Rà soát ngày 10/10/2026 từ PDF kiểm toán JS Held và dữ liệu tái lập gốc. Tài liệu này ghi bằng chứng cho một cơ chế lịch sử có thể còn thiếu; không xác nhận lợi ích đối với sai số mô hình, không bổ sung grant USD/UST và không đưa số quan sát vào đường giá hoặc nguồn cung mô phỏng. Không sửa engine, cấu hình, sources.json hay dữ liệu phục vụ đợt fit đang được đóng băng.

## Nguồn và độ chắc chắn của số liệu

Nguồn chính: [JS Held, LFG Audit, November 9, 2022](https://www.lfg.org/audit/LFG-Audit-2022-11-14.pdf), bản local `data/external/LFG-Audit-2022-11-14.pdf`; phần trích chữ `data/external/lfg_audit.txt`. Số trang dưới đây là trang PDF, cùng số trang in trên phần nội dung 1-17. Exhibit 6 nằm tại trang PDF 31. Đã xem trực quan trang 31; biểu đồ theo tweet dùng các ước lượng cũ, nên không thay thế các điều chỉnh tại đoạn 36-38.

| Đại lượng | Bằng chứng | Diễn giải đúng |
|---|---|---|
| 220.694.577 LUNA | Trang 14, đoạn 36, footnote 29 | Tổng LUNA từ 10 bot TFL chuyển sang 5 địa chỉ delegator **ngày 12/05/2022** để stake. Đây là lượng LUNA được chuyển; không phải gross mint gồm phí. |
| 5.286 swaps | Trang 14, đoạn 37 | Tập giao dịch UST/LUNA của 10 bot được khảo sát trong **09-11/05/2022**. Bot còn burn/mint liên tục cho nhiều mục đích. |
| 785.501.572-825.615.759 UST | Trang 14, đoạn 38 | Khoảng ước lượng UST ứng với lượng LUNA phục vụ governance, phụ thuộc start/end của tập swaps; sai khác LUNA dưới 1.000. Không xác định được tập swaps khớp chính xác. |
| 805.558.665 UST | Trang 13, dòng balance và footnote 27; trang 14, đoạn 38 | Midpoint của khoảng trên. **Không phải lượng burn được đo chính xác** và không phải cap phải thực hiện bằng mọi giá trong mô hình. |
| 327.164 LUNA | Trang 13, bảng LUNA; trang 14, footnote 30 | LUNA stake không qua UST/LUNA swaps. Không được ghi như native mint. |
| 1.796.182.310 UST | Trang 12, đoạn 30; trang 13, đoạn 34 và footnote 27 | TFL chuyển UST cho LFG. Không có giờ chuyển cụ thể cho toàn bộ khoản này trong báo cáo. Không coi chuyển token là mua thị trường hoặc burn. |
| 1.847.079.725 UST | Trang 12-14, đoạn 30 và 34 | Số dư UST cuối LFG: 697.344 ban đầu + 50.200.071 mua qua Curve + 1.796.182.310 nhận từ TFL. **LFG vẫn giữ UST, không burn toàn bộ số này.** |

Báo cáo không cung cấp chứng cứ xác định lịch governance burn từng phút hoặc chia chính xác theo ngày. Cửa sổ 09-11/05 là cửa sổ giao dịch được khảo sát, còn 12/05 là ngày chuyển LUNA đi stake; không được đặt burn toàn bộ tại thời điểm staking. Khoảng ước lượng trên cũng không chứng minh rằng mọi native swap của 10 bot đều chỉ phục vụ governance.

## Đối chiếu 10 địa chỉ với bảng nguồn

Nguồn: `../terra-luna-run-replication (1)/terra-luna-run-replication/data/tables/tableIA1_native_swap_users_run.csv`. `Datasets.md`, mục 37, mô tả bảng các top UST->LUNA swappers trong 07-13/05/2022; dữ liệu theo trader đầy đủ không được phát hành. Các địa chỉ dưới đây trùng footnote 29 trang 14 của kiểm toán, sau khi chuẩn hóa chữ hoa và bỏ khoảng trắng do PDF line wrap. Nhãn bảng là `TFL bot/UST Peg Defender`.

| Địa chỉ | Volume triệu UST | Volume triệu USD | Số swaps |
|---|---:|---:|---:|
| terra14tlthgtg6ep6xnqptyg8dp3gcq4jxvgqmskwkd | 97 | 62 | 649 |
| terra1nexqdq252acp09m9eler7jhg9kd3rqfzkek9r0 | 83 | 50 | 526 |
| terra14ny376fe7hys2zqxwc87zp2achp9tju5q6jul4 | 81 | 50 | 504 |
| terra12qmfcxy8kahwt44tn4aq4t6kdmtyer38xnrh7m | 81 | 49 | 518 |
| terra1mer7nd843n5g3v37xxtd3hude6t5rf4cq3mnae | 81 | 49 | 516 |
| terra1lewnh53gt0hzgjejrtwdz8q7dennz09s6ds4k2 | 81 | 49 | 518 |
| terra1t8szgklntcwxyfyflucuq895gpjr8wn6tsqxye | 80 | 49 | 505 |
| terra17p4mqd7yl9m0r7cfv0nf9s9zae3d3gm4tmyg2a | 80 | 48 | 506 |
| terra1g5dmf4qpmdrcw77d3ty6djrgujt8r2n3lgyknj | 81 | 48 | 529 |
| terra1v49w0m38fe87edhqdv30w96wq0pz6u6548q9gj | 80 | 48 | 498 |
| **Tổng** | **825** | **502** | **5.269** |

Volume được làm tròn theo triệu trong bảng. USD là giá trị thị trường của UST giao dịch, không phải USD grant mới. Transaction count 5.269 không bằng 5.286 trong JS Held; cửa sổ và pipeline khác nhau, chưa có log trader để giải thích chính xác. Bảng chỉ kiểm tra chéo quy mô và danh tính, không đủ để khẳng định row-level reconciliation hoặc chọn một lịch burn chính xác.

Năm địa chỉ delegator trong footnote 29 là `terra13u3p30c2tn9m8dmru6mfyhmqs379qm43vrx7l7`, `terra10zzfuednzhkmwn4tqks2mukstr02r5jklpmh2f`, `terra1anllr0tt8r2my88kp6kmdwdnewnja5246djj99`, `terra13vpm23s7rw5gqp9ckhqngjesxcuzatytknqpfg`, `terra1zz2nf34fjkjygkg0kplkrr29ycxarmct6kafvj`.

## Quy mô so với native aggregate và giới hạn nhận diện

`data/native_swaps/ust_luna_swaps_run.parquet` trong bộ tái lập gốc có 277.342 hàng và **chỉ bốn cột**: `time`, `offer_amount`, `swap_amount`, `fee_amount`. `Datasets.md`, mục 31, gọi đây là trader-less extract; log theo trader phía sau bảng IA.1 không được phát hành. Vì thiếu địa chỉ và transaction hash, không thể join chắc chắn từng swap vào bot từ thời gian hoặc label table.

Tổng `offer_amount` trong 07-13/05/2022 (lọc `time >= 2022-05-07`, `time < 2022-05-14`) là **7.490.671.480,388941 UST**. Tổng trong cửa sổ 09-11/05 là **5.550.085.307,380704 UST**. Vì thế midpoint governance 805.558.665 tương đương **10,7542%** của toàn cửa sổ run hoặc **14,5143%** của 09-11/05. Đây là tỷ trọng ước lượng theo số midpoint, không chứng minh một phần aggregate đã được tách chính xác.

Governance swaps đã nằm trong native observed aggregate. Nếu bổ sung chủ thể thực thi vào mô hình, không cộng 805 triệu vào mục tiêu burn observed, không cộng 220,694 triệu lên observed supply. Cơ chế có thể thay đổi việc tranh chấp virtual pool giữa quỹ và arbitrageurs, phí và nguồn cung nội sinh, dù lượng LUNA của quỹ được giữ/stake thay vì bán ngay.

## Jump, TFL và quyền sở hữu UST đầu kỳ

Trang 10, đoạn 22, ghi Jump chuyển **1.515.689.462 UST** cho TFL thông qua Binance nội bộ và on-chain, rồi TFL chuyển UST cho LFG. Bảng thực tế có cả một khoản nhỏ ngày 10/05; không được diễn giải là Jump mua mọi UST trong ngày 11/05 hoặc mua toàn bộ lúc 14:36.

| UTC | Khoản chuyển UST Jump -> TFL |
|---|---:|
| 10/05 02:42 | 878 |
| 11/05 13:54 | 100.000.000 x 3 |
| 11/05 13:55 | 100.000.000 |
| 11/05 13:57 | 100.000.000 |
| 11/05 13:59 | 100.000.000 |
| 11/05 14:03 | 100.000.000 |
| 11/05 14:05 | 70.000.000 |
| 11/05 14:27 | 885 |
| 11/05 14:36 | 745.687.699 |
| **Tổng** | **1.515.689.462** |

Khoản chuyển UST không cấp thêm nguồn lực ngoại sinh nếu mô hình đã dùng cùng BTC của Jump/LFG để mua UST trước đó. Muốn mô phỏng custody phải chuyển UST giữa các owner đã sở hữu, không tạo token thứ hai hoặc grant USD dựa trên số chuyển.

Trang 8, đoạn 13, ghi TFL Binance nắm **796.368.008,78 UST** vào đầu 08/05. Báo cáo không xác lập TFL nắm chính xác lượng này vào thời điểm khởi tạo mô hình 06/05. Đây là inventory UST, không phải backing USD. Nếu mở rộng ownership đầu kỳ, phải phân bổ lại từ UST đã có trong tổng supply, chứng minh thời điểm hoặc kiểm tra độ nhạy; không thêm supply bằng cách cộng một khoản mới. Không tự gán toàn bộ số UST này là governance budget.

## Giữ đúng nhãn gross, net và phần thay mặt LFG

Trang 4, đoạn 5, và trang 9-10, đoạn 17-19:

- Gross TFL purchases 08-10/05: **1.901.559.334 UST**, giá trị **1.773.199.279 USD**.
- Net TFL purchases 08-10/05: **1.464.738.304 UST**, giá trị **1.375.600.151 USD**.
- Own net USD contribution mua UST: **345.172.619 USD**; own net LUNA purchases: **268.444.270 USD**. Turnover gross có sales/recycling, không bằng vốn mới.
- **2.601.740.975 UST** là estimated purchases on behalf of LFG trong footnote 27 trang 12-13 và các đoạn 34-38. Trừ Jump 1.515.689.462 cho **1.086.051.513 UST** suy ra. Không gọi số suy ra này là total net purchases của TFL; total net TFL thực sự là 1.464.738.304.

Exhibit 6 trang PDF 31 vẫn minh họa số tweet **883,526 triệu UST / 221,021 triệu LUNA**, được nội dung kiểm toán điều chỉnh. Bảng Exhibit 6 có ending LUNA 222.713.007, còn body trang 13 ghi 222.713.002 (tổng 1.691.261 + 220.694.577 + 327.164). Sai khác 5 LUNA không ảnh hưởng kết luận, nhưng không dùng table cũ để ép một target governance chính xác.

## Điều kiện cho một mở rộng cơ học trong tương lai

Chưa triển khai cơ chế mới trong đợt rà soát này. Chỉ cân nhắc sau kết quả frozen fit nếu gate native flow hoặc supply vẫn không đạt. Cách triển khai có căn cứ sẽ:

1. Tách intent governance khỏi điều kiện arbitrage profit, giới hạn trong cửa sổ historical 09-11/05 và cap ước lượng thấp/midpoint/cao. Phân bổ đều hay dồn muộn là **giả định lịch**, cần độ nhạy; không gọi đó là chronology quan sát.
2. Chỉ burn `fund_ust` đã sở hữu. Thiếu token giữ backlog; không ép cap phải được phục vụ và không lấy desired LUNA 220.694.577 để đảo ngược amount burn.
3. Dùng chung virtual pool, oracle mô phỏng và spread với arbitrage; tính mint gross/fee owner đúng conservation. LUNA giao cho quỹ được giữ/stake, không tự động đưa vào market sell queue.
4. Giữ số burn governance tách riêng trong ledger, tổng native flow gồm cả arbitrage và governance; kiểm tra ước lượng bot volume/LUNA như evidence bên ngoài đường giá và objective.
5. Không tự động áp lịch historical governance vào counterfactual. Sự khác nhau về ownership, chính sách staking/quản trị và lịch chưa biết phải được khai báo cụ thể trước khi diễn giải policy rescue.

Không có evidence trong các nguồn local này để bổ sung một lịch mua Jump theo phút, một chương trình burn thêm toàn bộ ending LFG UST, hay một grant USD mới. Số liệu hỗ trợ cơ chế missing với quy mô khoảng 10,75% native burn; độ chính xác execution timing và inventory ban đầu vẫn hạn chế.

## Dấu vết nguồn

SHA-256 của các file đã đọc:

| File | SHA-256 |
|---|---|
| `data/external/LFG-Audit-2022-11-14.pdf` | `9207017b7d097064bfb1ca96beeafb116a4cd6f191f54b7c0b135cc2f63a56e9` |
| `data/external/lfg_audit.txt` | `28c370d848c157453213e7abf11fd3680817365df309098f173d450fb3ebabfc` |
| Original `data/tables/tableIA1_native_swap_users_run.csv` | `23824beba2c59a882e8bd87956548a8b041ff12fca5fdaff01a2f1cb925fd2ca` |
| Original `data/native_swaps/ust_luna_swaps_run.parquet` | `ecd470c77c314a79fb784f85b436f62e69f636343abd8ab98e6ad60c9347d124` |

Các kết quả cộng và tỷ trọng có thể tái lập bằng pandas từ hai file CSV/Parquet trên. Chỉ tài liệu Markdown này được thêm; không thay đổi nguồn raw hoặc fingerprint fit.
