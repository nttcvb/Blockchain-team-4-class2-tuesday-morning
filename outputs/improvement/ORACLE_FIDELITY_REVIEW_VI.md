# Rà soát độ đúng oracle trong tái dựng lịch sử

**Kết luận:** delay 1 phút có cơ sở như một xấp xỉ cơ chế, nhưng raw quote phút lùi 1 phút chưa đủ để tái dựng issuance trong pha sụp đổ. Trước May 11 sai số nhỏ; sau đó kết quả đổi mạnh theo venue, cách đặt trọng số và vài giờ cuối có giá cực nhỏ. Lag cho RMSE thấp nhất trong một bảng thống kê không xác định được lag oracle thực tế.

Rà soát này chỉ đọc dữ liệu và tạo thống kê/đồ thị. Không chạy mô hình mới, optimizer hay policy; không sửa core/raw/public fit; không đưa chuỗi oracle suy ngược hoặc native burn lịch sử vào engine. Báo cáo thống kê đầy đủ, code và hash nằm tại [oracle_fidelity_review](<D:/New folder/luna-ust-sim/outputs/improvement/oracle_fidelity_review>).

## Dữ liệu, đơn vị và coverage

`native_swaps/ust_luna_swaps_run.parquet` có 277.342 dòng của nhiều năm. Trong cửa sổ model May 6 00:15–May 16 00:00 UTC, có **235.710 swap**, từ **May 7 00:00:43 đến May 13 01:58:49 UTC**. Cả ba amount đều hữu hạn; offer, delivered và fee đều dương trong mẫu này, không loại dòng nào. Không có dữ liệu native swap sau thời điểm cuối; đây không phải bằng chứng rằng mọi giao dịch sau đó bằng 0.

Theo provenance tại `Datasets.md` và script bảng native swap, đây là UST→LUNA, amount đã là whole token: offer bằng UST, swap và fee bằng LUNA; không chia thêm 10⁶. File chỉ có bốn cột, không có trader, height, rate oracle truy vấn trực tiếp hay denom trong từng dòng. Công thức suy ngược:

\[
G_i=\mathrm{swap\_amount}_i+\mathrm{fee\_amount}_i,\qquad
O_i=\frac{\mathrm{offer\_amount}_i}{G_i}.
\]

`O` là **UST theo face value / LUNA**, được diễn giải như nominal USD/LUNA trong cơ chế đổi native. Đây không phải USD nhận được nếu bán UST ở spot khi mất peg. Không nhân thêm UST spot: làm vậy sẽ đổi câu hỏi và không còn là tỷ giá quy đổi native suy ngược.

Tổng mẫu: **7,490671 tỷ UST**, gross **6.872,102967 tỷ LUNA**, delivered **6.508,073804 tỷ LUNA**, fee **364,029164 tỷ LUNA**. Gross gồm fee bị giữ lại; delivered là phần người swap nhận.

Hai raw quote so sánh có định nghĩa khác nhau:

| Raw quote | Phạm vi UTC, độ phủ | Định nghĩa theo source prep |
|---|---|---|
| `prices/luna_price_may2022.parquet` | 21.600 phút May 1–15; không có gap; tất cả dương/hữu hạn | USD volume weighted price tổng hợp nhiều sàn |
| `prices/ust_luna_minute_price_run.parquet`, phần 2022 | 11.513 dòng May 7–14; 7 gap lớn hơn 1 phút | Quote USD spot FTX của May 2022 |

Với mỗi swap UTC, lấy quote tại **floor(time) − lag phút**, lag `[0,1,2,5,10,30,60]`. Không nội suy, ffill hay backfill mới. Dùng cùng tập swap có đủ cả bảy lag khi so RMSE giữa lag: cross-exchange phủ 100%; FTX phủ 235.624/235.710 swap (**99,9635%**), 99,9961% offer UST và gần 100% gross LUNA. Bảng pairwise coverage riêng vẫn được lưu. Quote FTX đã qua prep nguồn ban đầu; kiểm tra hiện tại không loại được mọi ảnh hưởng từ prep đó.

Lag 0 dùng bucket phút chứa swap, có thể gồm trade xảy ra sau swap trong phút đó. Nó là so sánh retrospective, không khẳng định quote đã khả dụng khi ra quyết định. Các lượng, timestamp và phase trong artifact đều UTC; pre/post May 11 chia tại **2022-05-11 00:00 UTC**.

## Quy ước gross fee và supply

Tài liệu market nêu độ trễ oracle khoảng một phút, nhưng prose về fee trong tài liệu không đủ để chốt tất cả ngữ nghĩa issuance. [Market specification chính thức](https://classic-docs.terra.money/docs/develop/module-specifications/spec-market.html) là mô tả cơ chế; source handler có version cụ thể hữu ích hơn cho ownership của coin.

Trong [handler chính thức classic-core v0.5.20](https://raw.githubusercontent.com/terra-money/classic-core/v0.5.20/x/market/keeper/msg_server.go), sau khi trừ fee khỏi swap coin, handler mint tổng delivered coin cộng fee coin, gửi delivered cho người swap và gửi fee vào oracle module. Hành vi code này hỗ trợ convention `gross = swap + fee` và fee có owner. Tag source không tự chứng minh mọi event raw chạy đúng phiên bản đó; kiểm tra amount và supply phía dưới là đối chiếu bổ sung.

Raw `luna_total_supply_run.parquet` có 337 dòng hourly. Theo `Datasets.md`, đây là **base supply + cumulative net native mint−burn từ swap parse**, không phải chuỗi total supply RPC độc lập. Vì vậy phép đối chiếu này kiểm tra tính nhất quán của unit, fee và bucket trong cùng họ dữ liệu, không xác nhận supply bằng một nguồn độc lập. Forward gross mint không phải net supply increment; reverse swaps và đường dẫn tạo extract chưa được ship đầy đủ.

Với raw hourly bucket label `t`, so `S[t]−S[t−1]` với swap nằm trong `[t,t+1h)`. Bucket này chứa cả giờ và chỉ hoàn chỉnh ở `t+1h`; không dùng nhãn giờ như availability ngay đầu giờ.

| May 11–13, chỉ giờ ghép có flow và ΔS dương | Giờ | log10 RMSE | Tổng flow / tổng ΔS |
|---|---:|---:|---:|
| Gross, cùng hourly bucket | 50 | **0,015710** | **1,010651** |
| Delivered, cùng hourly bucket | 50 | 0,135563 | 0,957116 |
| Gross, lệch −1 giờ | 49 | 0,447310 | 7,490995 |
| Gross, lệch +1 giờ | 50 | 0,447779 | 0,136539 |

Trong 50 giờ cùng bucket, gross forward mint 6,872050 nghìn tỷ và ΔS 6,799624 nghìn tỷ LUNA. Gross gần ΔS hơn delivered rõ rệt, hỗ trợ convention gross của core hiện tại. Chênh khoảng 1,1% không nên được biến thành fudge factor; tập ghép chỉ gồm giờ dương và ΔS là net. Tổng lệch giờ cũng có boundary khác, nên dùng RMSE và bucket inspection để đánh giá alignment, không diễn giải ratio tổng lệch giờ như lượng mất đi.

![Gross mint và net supply increment](<D:/New folder/luna-ust-sim/outputs/improvement/oracle_fidelity_review/gross_mint_supply_consistency.png>)

## Vì sao phải dùng hai loại trọng số

Đặt `e_i = log10(O_i / quote_lag_i)`. Bias, MAE, RMSE và p05/p25/p50/p75/p95 được tính riêng với `w=offer UST` và `w=gross LUNA`. Quantile là weighted quantile nội suy theo midpoint cumulative weight; không phải quantile của daily mean hay số lượng giao dịch. RMSE dưới đây có đơn vị log10.

| Ngày UTC | Swap | Offer, tỷ UST | Gross mint, tỷ LUNA | % tổng offer | % tổng gross |
|---|---:|---:|---:|---:|---:|
| May 7 | 2.310 | 0,015209 | 0,000217 | 0,203% | 0,000003% |
| May 8 | 8.580 | 0,071548 | 0,001113 | 0,955% | 0,000016% |
| May 9 | 8.693 | 0,181726 | 0,003761 | 2,426% | 0,000055% |
| May 10 | 44.169 | 1,229942 | 0,047446 | 16,420% | 0,000690% |
| May 11 | 87.110 | 4,138417 | 1,825264 | 55,248% | 0,026560% |
| May 12 | 77.481 | 1,786019 | 197,024886 | 23,843% | 2,867025% |
| May 13, đến 01:58:49 | 7.367 | 0,067811 | **6.673,200281** | **0,905%** | **97,106%** |

Pha dưới hai giờ cuối có ít offer nhưng gần toàn bộ số LUNA mint, vì denominator giá cực nhỏ. UST weighting mô tả độ lệch trên lượng capital đổi; gross-LUNA weighting nhấn mạnh rủi ro issuance. Chúng trả lời hai câu hỏi kinh tế khác nhau.

## Lag 1 phút và độ nhạy venue

Bảng dùng common support của cả bảy lag. Ratio là `O / quote_lag1`.

| Quote, phase | Weight | log10 RMSE | Ratio p05 | Ratio median | Ratio p95 |
|---|---|---:|---:|---:|---:|
| Cross-exchange, trước May 11 | UST | 0,006251 | 0,9845 | 1,0023 | 1,0256 |
| Cross-exchange, trước May 11 | Gross LUNA | 0,006711 | 0,9833 | 1,0029 | 1,0290 |
| Cross-exchange, từ May 11 | UST | 0,071704 | 0,9828 | 1,0427 | 1,2728 |
| Cross-exchange, từ May 11 | Gross LUNA | **0,992729** | **0,00494** | **0,6082** | **3,4943** |
| FTX, trước May 11 | UST | 0,008532 | 0,9841 | 1,0057 | 1,0412 |
| FTX, trước May 11 | Gross LUNA | 0,009485 | 0,9815 | 1,0070 | 1,0454 |
| FTX, từ May 11 | UST | 0,098883 | 0,9862 | 1,0750 | 1,5938 |
| FTX, từ May 11 | Gross LUNA | **0,381770** | **0,8662** | **1,5571** | **5,1524** |

Hai venue làm bias của issuance cuối sự kiện đổi dấu. Không thể quy mọi sai số thành một fixed delay. Lag 1 gần raw implied rate trong pha trước run mạnh; sai số gross có tail rất lớn sau May 11 dù lỗi UST weighting nhìn nhỏ hơn nhiều.

Chi tiết theo ngày của cross-exchange lag1; quantile đầy đủ cho cả hai venue và mọi lag nằm trong CSV/JSON:

| Ngày | Weight | RMSE | p05 ratio | p25 | median | p75 | p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| May 7 | UST | 0,001743 | 0,9907 | 0,9978 | 0,9998 | 1,0006 | 1,0019 |
| May 7 | Gross | 0,001784 | 0,9907 | 0,9978 | 0,9998 | 1,0006 | 1,0019 |
| May 8 | UST | 0,000951 | 0,9964 | 0,9989 | 0,9999 | 1,0006 | 1,0020 |
| May 8 | Gross | 0,000960 | 0,9964 | 0,9989 | 0,9999 | 1,0006 | 1,0020 |
| May 9 | UST | 0,007102 | 0,9829 | 0,9979 | 1,0007 | 1,0049 | 1,0290 |
| May 9 | Gross | 0,007732 | 0,9816 | 0,9977 | 1,0009 | 1,0053 | 1,0292 |
| May 10 | UST | 0,006329 | 0,9843 | 0,9988 | 1,0030 | 1,0089 | 1,0264 |
| May 10 | Gross | 0,006715 | 0,9831 | 0,9987 | 1,0034 | 1,0106 | 1,0292 |
| May 11 | UST | 0,040033 | 0,9897 | 1,0136 | 1,0388 | 1,1161 | 1,2078 |
| May 11 | Gross | 0,040637 | 0,9868 | 1,0158 | 1,0344 | 1,1085 | 1,2187 |
| May 12 | UST | 0,072139 | 0,9590 | 1,0161 | 1,0474 | 1,1430 | 1,4838 |
| May 12 | Gross | 0,120542 | 0,6476 | 1,0044 | 1,1328 | 1,2532 | 1,6692 |
| May 13 | UST | 0,468474 | 0,1460 | 0,9038 | 1,3731 | 1,8651 | 4,5762 |
| May 13 | Gross | **1,007198** | **0,00494** | **0,1046** | **0,5585** | **1,1396** | **3,5109** |

| Quote, phase | Weight | Lag thấp nhất trong grid | RMSE tại lag đó | RMSE lag1 |
|---|---|---|---:|---:|
| Cross-exchange, trước May 11 | UST | 2 phút | 0,004779 | 0,006251 |
| Cross-exchange, trước May 11 | Gross | 2 phút | 0,005034 | 0,006711 |
| Cross-exchange, từ May 11 | UST | 2 phút | 0,067188 | 0,071704 |
| Cross-exchange, từ May 11 | Gross | **30 phút** | 0,565688 | 0,992729 |
| FTX, trước May 11 | UST | 2 phút | 0,006776 | 0,008532 |
| FTX, trước May 11 | Gross | 2 phút | 0,007662 | 0,009485 |
| FTX, từ May 11 | UST | 5 phút | 0,090931 | 0,098883 |
| FTX, từ May 11 | Gross | **10 phút** | 0,318744 | 0,381770 |

Đây là minima mô tả trong bảy candidate, chưa có holdout hay confidence interval và không phải calibration. 30 phút thắng với một venue/weight không chứng minh oracle lag 30 phút: giá rất phi tuyến ở cuối cửa sổ, trộn venue và mean/median khác nhau có thể đổi minima.

![Độ nhạy lag theo weight và venue](<D:/New folder/luna-ust-sim/outputs/improvement/oracle_fidelity_review/lag_weight_sensitivity.png>)

Một đối chiếu arithmetic riêng giữ nguyên observed offer, tính tổng `offer/quote_lag1` rồi chia tổng gross quan sát: cross-exchange **1,004118** trước May 11 và **0,950041** sau; FTX **1,009418** trước và **2,326124** sau. Toàn sự kiện cross-exchange cho 6,528779 nghìn tỷ LUNA so với actual 6,872103 nghìn tỷ; FTX cho 15,98530 nghìn tỷ. Tổng gần nhau ở cross-exchange không phủ định tail error: các sai lệch dương/âm có thể triệt tiêu. Đó là phép chia quan sát để đo sensitivity, không phải output simulator và không có flow nào được đưa ngược vào model.

## Giới hạn suy luận và chọn cấu trúc tiếp theo

[Oracle specification chính thức](https://classic-docs.terra.money/docs/develop/module-specifications/spec-oracle.html) mô tả validator prevote/reveal và median có trọng số voting power, với cập nhật theo vote period. Cơ chế đó không đồng nhất với một single-venue quote lùi đúng 60 giây. Market specification ghi delay khoảng một phút với VotePeriod khoảng 30 giây; đó là cơ sở hợp lý cho baseline, không phải bằng chứng định lượng cho path oracle trong sự kiện.

Có **7.765 phút hoạt động**, 7.065 phút có nhiều swap; 6.465 phút có range implied rate trong phút lớn hơn `10⁻⁶ log10`. Median range trong phút `0,001173 log10`, p95 `0,026307`; chỉ 1,54% swap ở giây 00. Vì vậy một quote mỗi phút không đại diện chính xác mọi rate của swap trong phút. Rounding fee/token, timestamp block, median validator và bucket VWAP đều có thể góp phần; tỷ số implied không tách được đóng góp từng nguồn.

![Implied rate và quote theo thời gian](<D:/New folder/luna-ust-sim/outputs/improvement/oracle_fidelity_review/implied_oracle_vs_quotes.png>)

Core hiện tại có `oracle_lag_minutes=1`, oracle nội sinh từ quote mô phỏng trước đó ở bước market khoảng một phút. Rà soát này không kiểm tra một archived oracle feed độc lập. Nên ưu tiên xác minh historical validator rate/height và vote-period semantics trước khi đổi oracle cấu trúc; nếu không có archive, cần đánh giá sensitivity của update/aggregation rules và đo cả UST-weight lẫn gross-weight issuance bằng ensemble sau khi chốt cấu trúc. Không chọn một lag theo toàn sự kiện rồi gọi đó là causal parameter, và không thay native demand nội sinh bằng observed burn.

Pre/post May 11 chỉ là statistical phase split. Core observation hiện có capacity multiplier 4 từ May 11 12:00 UTC, đổi base pool 50→200 triệu **USD** và arb daily cap ×4, recovery giữ nguyên. Không dùng mốc này để giải thích oracle mismatch như một execution timestamp đã được xác minh. Proposal parameters và đơn vị **SDR** cần được kiểm chứng riêng; root đang rà timing/protocol. Báo cáo này giữ nguồn và tham số hiện có.

## Binding và audit

- Base/current engine SHA-256: `0a89a9e690c7998d8fadaa1756466b6195b67219483320403672a441cd95f7ea`.
- Diagnostic script `review.py`: `80581f9642e8bf90cf41c2bd22b242d288b9a8855c8f20429304e5dba6f87ddc`.
- Frozen public `config_all.json`: `b5b50361d49f5aa350174fab13f796b329be3918715821a4fb866af17f6fef94`; oracle lag1, base pool 50.000.000 USD, recovery 3,6 phút, minimum spread 0,005, arb capacity/day 1.052.290.610,0102551. Không refit tham số.
- Raw native swaps: `ecd470c77c314a79fb784f85b436f62e69f636343abd8ab98e6ad60c9347d124`.
- Raw cross-exchange quote: `2007339f3436f3b4690a6cfd3fa9bf324d2586eca081cdacaea5a42244027465`.
- Raw FTX quote: `5f61b579ab88b5c64bed7a1808e900c5d377d805761e4c8ee58f612db7522afd`.
- Raw hourly supply: `db340cb1cbdc8fb94d232fe114c990b11a047488ac6d4a61ba622edf99a173a1`.

`review.json` lưu hash toàn bộ core, raw, provenance docs và public artifacts; trước/sau assertion **source/raw/public unchanged đều true**. `private_artifact_hashes.json` định danh các bảng/Parquet/đồ thị. Final audit lưu riêng tại `final_audit.json`, bao gồm hash báo cáo và tính toàn vẹn manifest. Không tích hợp bất kỳ oracle override nào vào core.
