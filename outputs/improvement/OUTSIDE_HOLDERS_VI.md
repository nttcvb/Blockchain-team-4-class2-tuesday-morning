# Bằng chứng tồn kho và giao dịch của người giữ UST ngoài Anchor

Rà soát chỉ đọc ngày 10/10/2026. Chỉ thêm tài liệu này; không sửa engine, data, config, metrics, calibrate, sources.json, targets hoặc chạy optimizer. Dữ liệu hỗ trợ kiểm tra mức tồn kho và có hành vi mua lẫn thoát vị thế, nhưng **không nhận dạng duy nhất cầu UST hoặc tốc độ thoát của một nhóm outside buyers**.

## Hai nguồn chính

1. Bộ dữ liệu tái lập: [daily balances Columbus-5](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/data/daily_balances/columbus-5-lunaust-supply-breakdown-fullnode.parquet>), [nhãn entity](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/data/labels/terra_labels_4vol.parquet>), [mã Figure 2](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/code/figures/fig02_ust_supply_by_entity.py>) và [Datasets.md](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/Datasets.md>), mục 17, 27. Daily balances được dựng từ genesis cộng cumulative transfer/send/mint/burn; token balance đã là UST nguyên, không chia thêm 1e6. File có 159.939 hàng, 755 address values, hai denom `UST`/`LUNA`, ngày 30/09/2021-26/05/2022. `Other` là một address value tổng hợp có trong dữ liệu, ngoài các địa chỉ chưa được gán nhãn.
2. Liu, Makarov, Schoar, [Anatomy of a Run: The Terra Luna Crash, MIT primary PDF](https://mitsloan.mit.edu/shared/ods/documents/?PublicationDocumentID=9764), NBER Working Paper 31160. PDF trang 7 (printed 5) mô tả các ví nhỏ mua UST ngày 09/10 khi giá tạm ổn dưới peg. PDF trang 30 (printed 28) ghi Binance net buy khoảng 200 triệu UST ngày 07/05, đối lập Curve net sell khoảng 200 triệu; các lệnh mua có thể từ noise traders **hoặc TFL**, không tách được outside demand. PDF trang 33 (printed 31), section 4.3, phân tích portfolio và token inflow/outflow của người gửi; log portfolio đầy đủ không được phát hành trong bundle.

Paper Liu/Makarov/Schoar là w31160; w30256 là paper Uhlig khác, không thay ID của nguồn đó khi nó được dẫn cho mục đích riêng.

## Mapping, ngày và đơn vị

Tái tạo đúng `fig02_ust_supply_by_entity.py`: lọc `denom == UST`; chỉ giữ label types `Anchor`, `Admin`, `TFL`, `Bridge`, `CEX`, `DEX`, `DeFi`; mọi địa chỉ còn lại map sang `Other`; cộng `balance` theo `date, Entity` và chia 1e9. **Other không đồng nghĩa outside buyer.** Nó gồm địa chỉ chưa gán nhãn, contracts, các ví người gửi đã rút và marker tổng hợp. CEX là custody, không phải beneficial ownership riêng của market maker hoặc đầu cơ.

Trong bảng dưới đây, `date` là **nhãn ngày trên lịch UTC**, cùng quy ước ngày của bộ tái lập. Raw dtype `datetime64[us]` không mang timezone; giá trị hiển thị 00:00 là nhãn ngày, **chưa xác minh đây là snapshot tức thời đầu ngày hay cuối ngày**. Không dùng trực tiếp hàng 06/05 để khởi tạo 06/05 00:14 hoặc làm target intraday trước khi giải quyết quy ước bucket. Mã Figure 2 chỉ plot tới 10/05, nhưng file raw thực tế còn dữ liệu tới 26/05.

Đơn vị mọi cột là **tỷ UST**, không phải tỷ USD. `Tổng 5 nhóm` = Other + CEX + DEX + DeFi + Bridge; tên này không khẳng định toàn bộ UST có thể giao dịch ngay.

| Nhãn ngày UTC | Other | CEX | DEX | DeFi | Bridge | Tổng 5 nhóm |
|---|---:|---:|---:|---:|---:|---:|
| 2022-05-05 | 1.067545 | 0.760046 | 0.494244 | 1.171520 | 1.321895 | 4.815250 |
| 2022-05-06 | 1.075215 | 0.738351 | 0.492608 | 1.151836 | 1.327217 | 4.785227 |
| 2022-05-07 | 1.474999 | 0.744141 | 0.431369 | 1.155674 | 1.988061 | 5.794245 |
| 2022-05-08 | 1.838621 | 1.028902 | 0.417748 | 1.156946 | 2.435463 | 6.877680 |
| 2022-05-09 | 2.624713 | 1.828215 | 0.299364 | 1.264114 | 2.466608 | 8.483014 |
| 2022-05-10 | 3.566086 | 1.479334 | 0.241731 | 1.213771 | 2.446956 | 8.947877 |
| 2022-05-11 | 2.906750 | 1.827045 | 0.134308 | 1.175491 | 1.511584 | 7.555178 |
| 2022-05-12 | 2.670159 | 1.495813 | 0.075043 | 1.431088 | 1.050584 | 6.722687 |
| 2022-05-13 | 1.633946 | 2.767145 | 0.093238 | 1.299966 | 1.145182 | 6.939477 |
| 2022-05-14 | 1.521885 | 2.870574 | 0.102112 | 1.285787 | 1.188191 | 6.968550 |
| 2022-05-15 | 1.494856 | 2.929943 | 0.101353 | 1.281164 | 1.249455 | 7.056771 |

Làm tròn từng cột có thể tạo chênh vài nghìn UST khi cộng các số in. Phép tính unrounded cho thấy Other tăng **2.490.871.385,8909245 UST** từ 06/05 tới 10/05, rồi giảm **2.071.229.601,4600391 UST** tới 15/05. Số dư Other từ 13/05 tới 15/05 tiếp tục giảm trong khi CEX tăng. Đây là thay đổi custody/tồn lượng, không đo riêng lệnh bán UST đổi USD của speculative buyers.

## Giá UST hồi cuối cửa sổ không định danh cầu

Nguồn quote: [ust_price_may2022.parquet](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/data/prices/ust_price_may2022.parquet>) của bộ tái lập. Mỗi ngày bên dưới có đủ 1.440 quote VWAP phút theo thời gian UTC. Trung bình dưới đây là **trung bình số học của quote VWAP phút**, không phải daily VWAP theo tổng volume.

| Ngày UTC | Trung bình quote USD/UST | Median | Min | Max |
|---|---:|---:|---:|---:|
| 2022-05-12 | 0.521452 | 0.497947 | 0.273042 | 0.824590 |
| 2022-05-13 | 0.122159 | 0.113316 | 0.045067 | 0.387386 |
| 2022-05-14 | 0.158878 | 0.157479 | 0.106080 | 0.221352 |
| 2022-05-15 | 0.175044 | 0.176078 | 0.134089 | 0.266795 |

Có hồi quote sau 13/05. Không có dữ liệu signed trading volume/portfolio identity đủ cho 14-15/05 trong bundle để gán lực hồi cho outside buyers, xác định lượng USD bid, hoặc tách hiệu ứng thanh khoản/supply/giảm áp lực bán. Quote này tiếp tục là quan sát đánh giá, không là lịch cầu hoặc giá sàn đưa vào engine.

## Ràng buộc có thể dùng và điều chưa nhận dạng

- **Stock có thể quan sát:** các tổng holder theo nhãn ngày/entity, phạm vi Other khoảng 1,07-3,57 tỷ trong 05-15/05, tổng 5 nhóm khoảng 4,79-8,95 tỷ. Dùng kiểm tra chéo các mức inventory sau khi định nghĩa mapping giữa model owners và custody entities. Pool outside buyer mua rồi giữ 8-9,5 tỷ UST không tương đương với Other đo được; cũng chưa thể gọi đó là vi phạm hard cap nếu pool đại diện cả beneficial owners tại CEX/bridge/DeFi.
- **Turnover có bằng chứng, tốc độ chưa có:** buy-the-dip, bán/đổi/bridge và tái phân phối custody tồn tại. Chênh số dư không bằng gross orders. Other giảm có thể do native burn, bridge transfer, gửi lại Anchor, transfer sang CEX hoặc thay đổi nhãn; không được lấy net decline chia số ngày để ước tính exit hazard của một nhóm đầu cơ.
- **Không nhận dạng từ bundle:** outside USD capital, fixed USD/day, desired position, holding duration, confidence elasticity và separate outside entry/exit. Network CSV là volume cộng cả Columbus-5, không có timestamp để lấy riêng run turnover; Binance tick data chỉ có 07/05; native swaps thiếu trader. Các tham số này phải ghi là giả định/độ nhạy hoặc được hiệu chỉnh chung, không gọi là empirical estimates.

Prior có cơ sở cho một candidate nhỏ: nếu định nghĩa outside pool **hẹp** như speculative unlabelled holders, thử tổng inventory cap khoảng **1-4 tỷ UST** như dải giả định quanh stock Other quan sát, gồm 4 tỷ là trần làm tròn; không xem đó là một cap đã được đo hay lượng phải mua. Nếu outside bao gồm custody trên nhiều venue, cần mapping rộng hơn và diagnostic tổng 5 nhóm, không chọn cap hẹp bằng cách bỏ CEX. **Không có interval exit hazard được nhận dạng đủ để đề xuất một tốc độ turnover chính xác.** So sánh zero exit với positive exit có giới hạn thời gian vật lý là phép nhạy của giả định, không replay flow observed.

Một cơ chế tối thiểu có thể kiểm tra là desired UST inventory hữu hạn thay đổi theo tín hiệu mô phỏng (confidence, discount, trend), mua khi thiếu inventory và bán từ UST đã giữ khi desired inventory giảm. Quyết định phải có cùng cash/token owners, phí và constraints của market; nếu muốn mua không được fill thì giữ ý định, không cấp cash mới. Giá rất thấp không tự tạo nhu cầu token vô hạn chỉ vì còn USD. Việc chọn hàm desired inventory hoặc exit không được dùng ngày 10/05, daily holder target, quote cuối kỳ hoặc native/Supply observed để ép đường.

Đây là đề xuất cấu trúc, chưa phải một candidate thắng. Mở lại dòng UST cho arbitrage có thể làm mint tăng rất mạnh nếu các tham số độ sâu/quote còn sai; một ablation giữ tham số cố định chỉ chẩn đoán ownership trap, không chứng minh fidelity. Giữ cap, exit và liquidation depth trong đánh giá chung, xác minh conservation và sự ổn định timestep trước khi chọn bản chính.

## Dấu vết nguồn và phép tái lập

| File trong bộ tái lập gốc | SHA-256 |
|---|---|
| `data/daily_balances/columbus-5-lunaust-supply-breakdown-fullnode.parquet` | `c23cc9dbb40ea7cf77811bc16a20352a572f36a1b7765376eda12699282f114b` |
| `data/labels/terra_labels_4vol.parquet` | `93fd49edf63723a1c40242e0cb926137ae21b2c2dac1d34f6ba5e4bc362f8634` |
| `code/figures/fig02_ust_supply_by_entity.py` | `87ee9802b2b43d7a92ae97267262ae0c7434dc5de9b2d34f4b73f2249e59ce7d` |
| `Datasets.md` | `31a99697172dafc85f7c9ddb8eb2720ca4124c917ec6a579358051b125325b2d` |
| `data/prices/ust_price_may2022.parquet` | `043c03404a9e53c352df645e192a360b30ce6f853d2006fdec298e950ecdd869` |

Tái lập stock: `label_dict = labels[label_type.isin(VALID)].set_index('address').label_type`; `Entity = address.map(label_dict).fillna('Other')`; lọc UST, `groupby(['date','Entity']).balance.sum().unstack(fill_value=0) / 1e9`. Không forward-fill, không đổi target hoặc nguồn gốc. Tái lập quote: lọc 12-15/05, group theo `time.dt.date`, tính count/mean/median/min/max trên `ust_price`.
