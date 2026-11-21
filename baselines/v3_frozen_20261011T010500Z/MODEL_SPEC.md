# Đặc tả mô hình để trình bày và sửa tiếp

Phạm vi hiện hành theo yêu cầu người dùng là tái hiện sự kiện lịch sử. Các công cụ chính sách đã có được giữ như phần tùy chọn; bộ7 kịch bản và tail cứu trợ không còn là điều kiện bàn giao. Public core hiện `0a89a9e6…`; các prototype attention, partial liquidation, đồng hồ quan sát cố định, holder EMA và protocol capacity vẫn ở thư mục riêng, chưa tích hợp.

Mức độ đã kiểm chứng: train06–10/05 đạt6/6 gate, holdout11–15/05 chỉ2/6; full-fit trong mẫu2/6. Hai fits đã có audit toàn kỳ fast/cadCAD và dữ liệu gốc. Cả20 seed stochastic42–61 đều0/6; Anchor NRMSE giữa bước5/15 phút bằng0,270695. Mô hình hiện chưa phải bản tái hiện đủ gần hoặc ổn định. Báo cáo hiện hành: [RECONSTRUCTION_VI.md](<D:/New folder/luna-ust-sim/outputs/reconstruction/RECONSTRUCTION_VI.md>).

## 1. Ranh giới, thời gian và dữ liệu

Khởi tạo từ snapshot 06/05/2022 lúc 00:14 UTC, cập nhật từ 00:15. Bước quyết định ABM mặc định 15 phút; có đối chiếu 5 phút. Thị trường/native tích phân bên trong mỗi bước theo một phút để phù hợp pool phục hồi nhanh và oracle. Cửa sổ lịch sử kết thúc 16/05 lúc 00:00 (không gồm điểm cuối); replay hiện hành không dùng tail. Tail tùy chọn cũ kéo dài7 ngày, giữ giá BTC cuối cửa sổ và ngừng giải ngân mới. Cấu hình bắt đầu muộn vẫn chạy warmup từ snapshot rồi mới xuất đoạn được chọn. Nhãn bước đầu đang đi kèm một lần cập nhật5 hoặc15 phút; khác biệt khởi động này còn cần tách khỏi cadence trong bản sửa sau.

Chuỗi nguồn cung LUNA trong nguồn là cumulative tới cuối bucket giờ; lớp quan sát dịch nhãn thêm một giờ trước khi forward-fill. Khởi tạo chỉ dùng giờ đã hoàn thành. Dữ liệu gốc giữ nguyên; bằng chứng so sánh mint theo giờ nằm trong `outputs/improvement/DATA_AUDIT_VI.md`.

Giá UST/LUNA, tiền gửi Anchor, nguồn cung LUNA và native swaps từ bộ tái lập được dùng làm mục tiêu, không nhập trực tiếp làm giá ở mỗi bước. Giá BTC là điều kiện thị trường ngoại sinh. A/B là hai chuỗi hành động khởi phát quan sát được, không là mô hình suy diễn nguyên nhân khủng hoảng.

## 2. Tác nhân và tồn lượng

| Thành phần | Trạng thái và hành động |
|---|---|
| 1.000 người gửi đại diện | Quyền đòi UST, hàng đợi rút, UST trong ví, USD đã nhận; quyết định rút theo quan sát trễ |
| 20 arbitrageurs | USD và LUNA; mua UST, đổi native, bán LUNA hoặc giữ lại khi thiếu thanh khoản |
| Anchor | UST tiền mặt, dư nợ, UST của người vay, quỹ lãi; trả lãi, nhận hoàn nợ, phục vụ rút |
| Market maker tổng hợp | USD/UST/LUNA hữu hạn; là phía đối ứng của lệnh mua/bán |
| Nhà đầu tư bên ngoài | USD/UST hữu hạn; mua khi UST bị chiết khấu |
| LFG + TFL | BTC/USD bị khóa hoặc khả dụng, UST/LUNA mua về, chi phí tích lũy |

Top 20 ví giữ riêng. Các ví còn lại được lấy mẫu phân tầng 6 nhóm và mang trọng số để giữ tổng vốn trước khủng hoảng. Phần chênh lệch với tổng tiền gửi protocol là người gửi tổ chức tổng hợp. 20 arbitrageurs chia vốn và lệnh theo tỷ trọng vốn; chưa có chiến lược khác nhau giữa arbitrageurs, nên không diễn giải kết quả như nghiên cứu cạnh tranh vi mô.

Core lấy mẫu có hoàn lại, rồi rescale vốn mỗi nhóm. Seed42 có1.000 row nhưng902 địa chỉ riêng; nhóm>10M có109 ví raw nhưng183 row,97 địa chỉ riêng, ngoài top20 weight khoảng0,546. Vì vậy row ngoài top20 là đại diện tổng hợp, không là mọi wallet thật. Tín hiệu kích thước dùng vốn sau rescale; đặc trưng raw và identity được lưu để audit. Người gửi tổ chức dùng hành động phân số ngay cả ở chế độ stochastic; không diễn giải nó như một ví thật bốc Bernoulli.

USD thị trường ban đầu là giả định: market maker 25 tỷ, arbitrage 150 triệu và người mua bên ngoài 1 tỷ. Đây là vốn của phía đối ứng, tách hoàn toàn khỏi trần cứu trợ LFG/TFL; không phải quy mô thị trường đã xác minh. Độ sâu được hiệu chỉnh, nhưng nguồn vốn và cấu trúc phía đối ứng chưa được nhận dạng duy nhất bởi dữ liệu.

## 3. ABM: hành vi rút

Với tác nhân i, tín hiệu gồm chiết khấu UST, rút trong giờ gần nhất, giảm giá LUNA và hàng đợi, lấy theo độ trễ của ví:

```text
eta_i = h0 + h_size × (log_size_i − 3)
      + h_discount × discount_i + h_outflow × outflow_i
      + h_luna × luna_fall_i + h_queue × queue_fraction_i
p_i(dt) = 1 − (1 − logistic(eta_i))^(dt/15)
withdraw_i = max(claim_i − queued_i, 0) × Bernoulli(p_i)
```

Khi hiệu chỉnh, Bernoulli được thay bằng kỳ vọng p_i để mục tiêu tối ưu ổn định. Đây không phải cùng kết quả trung bình của mô hình phi tuyến ngẫu nhiên; bộ 20 seed kiểm tra khác biệt đó. Trong mỗi bước, mọi tác nhân nhận đúng một số ngẫu nhiên, giúp so sánh chính sách dùng cùng seed.

Bernoulli của core áp dụng lên toàn vốn khả dụng của row có trọng số; các thành viên của một row vì thế cùng tham gia. Phương sai của nhóm nhỏ cao hơn cách cho từng wallet rút độc lập. Top20 weight1 vẫn chiếm85,27% phương sai ở trạng thái đầu của seed42: sửa riêng weighted cohort không xử lý toàn bộ whale risk. Lần rút đầu của17 whale ngoài A/B có median3,325% vốn trước run trong extract; đó chưa phải tỷ lệ claim ngay trước giao dịch. Prototype rút từng phần giữ conditional mean bằng compound Poisson, nhưng5 seed được kiểm vẫn không đạt toàn bộ gate. Chưa thay công thức public bằng prototype.

Tín hiệu giảm LUNA hiện cộng các log decline dương trong giờ trễ. Cắt phần tăng trước khi cộng khiến quan sát5 phút có tổng decline lớn hơn15 phút ngay cả khi hourly return bằng nhau. Prototype đồng hồ quan sát15 phút cố định giảm sai lệch UST/Anchor và giữ nguyên đường public15 phút, nhưng chưa chữa sai lệch giá/cung; xem [CADENCE_REVIEW_VI.md](<D:/New folder/luna-ust-sim/CADENCE_REVIEW_VI.md>).

Mỗi người gửi còn có bộ đếm vốn ban đầu chưa từng rút. Rút được phục vụ làm giảm bộ đếm theo FIFO; lãi và gửi lại tăng quyền đòi nhưng không phục hồi vốn ban đầu đã thoát. Biểu đồ theo nhóm và mục tiêu hiệu chỉnh dùng bộ đếm này để khớp cùng định nghĩa với dữ liệu quan sát.

## 4. System Dynamics: tồn lượng và dòng chảy

```text
Anchor cash' = cash + loan repayments + funded interest − served withdrawals + redeposits
Anchor claims' = claims + funded interest − served withdrawals + redeposits
Loan balance' = loan balance − repayments
Yield reserve' = reserve + actual UST income − funded interest
Withdrawal queue' = queue + new requests − served withdrawals
UST supply' = UST supply − native UST burned
LUNA supply' = LUNA supply + gross native LUNA minted
```

Hoàn nợ được giới hạn bởi UST thật của người vay. Lãi được giới hạn bởi quỹ lãi. Rút được phục vụ theo tỷ lệ đồng đều, giới hạn bởi thanh khoản và chính sách gate. Tiền gửi là quyền đòi, không được đếm như token mới.

Virtual pool: base B, độ lệch x = B + delta, k = B². Với UST q đổi vào, giá trị LUNA nhận theo pool là `(k/x) × q/(x+q)`. LUNA phát hành gộp là `q/oracle_LUNA`; phần chênh với LUNA nhận được ghi vào tài khoản phí. delta phục hồi theo `exp(−dt/recovery_minutes)`. Đây là quy đổi USD tổng hợp của cơ chế Terra, không tái tạo SDR hay phí từng block.

Quote, giao dịch, oracle trễ một phút và recovery cập nhật tại mỗi phút nội bộ. Hạn mức arbitrage/nhu cầu theo thời gian vật lý; tỷ lệ bán 15 phút s được chia thành `1−(1−s)^(dt/15)`. Return BTC được chia đều giữa bước con. Cứu trợ chuyển cash/token một lần ở PSUB trước, sau đó phân bổ tác động lệnh qua phút; không chi lại mỗi phút. Các lượng native/mint/burn cộng dồn, phí bình quân theo tổng gross mint.

Arbitrageurs chọn kích thước q theo lợi nhuận bán LUNA sau tác động giá, rồi giới hạn bởi vốn, UST sẵn có, capacity và tác động giá UST. Với giá mở P, độ sâu token D và lượng bán s, tiền thu gộp là `G(s)=P×D×log(1+s/D)`, giá biên `P/(1+s/D)`. Quote dùng chênh `G(H+n(q))−G(H)` với lượng LUNA đang giữ H, trừ phí bán và USD mua UST. Quote dùng ngân sách market trước khi nhận USD từ lệnh mua UST; đây là dự tính bảo thủ. Depth và điều kiện giới hạn phần cash dành cho bid được cố định đầu phút, execution dùng cùng đường cầu và giới hạn cash thực còn có. Nếu thiếu cash, đảo G để tìm lượng fill; LUNA chưa bán được giữ trong kho.

Lợi nhuận là hàm lõm theo q ở quote cố định. Bisection 32 bước trả cận dưới, tránh bỏ sót nghiệm nhỏ trong khoảng capacity lớn. Không bán toàn bộ LUNA mới phát hành ở giá trước giao dịch. Gross mint và khoản phí vẫn có chủ sở hữu, independent với tiền thu thực từ bán.

Giá UST thay đổi theo lệnh bán ròng / độ sâu và biến động tín hiệu tin cậy `min(1, market_cap_LUNA / UST_supply)`. Tín hiệu này không phải tài sản bảo chứng. Giá LUNA thay đổi theo bán ròng / độ sâu token và lợi suất BTC. Khi native ngừng hoặc yên ≥6 giờ, có mức bid còn lại bằng một phần USD đang có của market maker / nguồn cung LUNA. Đây là giả định hành vi cần kiểm tra độ nhạy, không có USD mới.

## 5. Sổ tài sản và thứ tự cadCAD

Sáu PSUB có thứ tự cố định: quan sát → cứu trợ → hành vi → Anchor → thị trường → kế toán. cadCAD giữ một biến state `book` chứa các tồn lượng và mảng tác nhân. Trạng thái cũ không bị sửa tại chỗ. Bộ chạy nhanh gọi đúng các hàm này; chỉ dùng khi tối ưu tham số.

Kiểm tra mỗi bước:

- Tổng UST trong mọi tài khoản bằng nguồn cung UST.
- Tổng LUNA, gồm phí, bằng nguồn cung LUNA.
- USD bằng vốn đầu kỳ + vốn TFL được mở + USD từ bán BTC; phí được giữ trong tài khoản riêng.
- Anchor cash + loan balance = tổng quyền đòi.
- BTC bị khóa + khả dụng + đã bán = 80.394; ít nhất 313 BTC được giữ.
- Tồn lượng không âm; đóng góp ròng TFL ≤613.616.889 USD.

Giá thay đổi không tạo USD. LFG/TFL/Jump chuyển nội bộ không tạo ngân sách mới. Kiểm tra dùng cả sai số tuyệt đối và tương đối để chịu được số rất lớn khi LUNA siêu lạm phát.

## 6. Giao diện chính sách

Chính sách lấy trigger giá hoặc thời gian UTC, số bước xác nhận, độ trễ, thời hạn, nguồn LFG/TFL và phân bổ. Bốn hành động là mua UST, cam kết vốn thanh khoản, đổi pool/recovery và hạn chế rút. Khi kết hợp mua UST/thanh khoản, mỗi hành động lấy tối đa tỷ lệ đã chọn của quỹ khả dụng ở đầu bước, đồng thời chịu hạn mức tốc độ chi riêng. Tỷ lệ chi tích lũy còn phụ thuộc thời hạn và nhu cầu mua. Các hành động dùng chung tài khoản quỹ. Mua UST chỉ chuyển token sang quỹ; không đốt token.

Replay lịch sử có mốc thay capacity và ngừng giao dịch xấp xỉ; phản thực tế không bị ép các mốc dừng này. Vì bỏ qua validator và mức độ hoạt động blockchain thực, tiêu chí “cứu vãn” chỉ nói về tài chính và khả năng phục vụ trong mô hình.

Mốc capacity hiện ở11/05 12:00UTC đặt `pool_multiplier=4`, tác động cả base pool và arb capacity, giữ recovery. Đây là xấp xỉ cũ chưa có block thực thi xác nhận. [Đề xuất1164 gốc](https://classic-agora.terra.money/t/proposal-help-ust-pegging-increase-estimated-minting-capacity-to-1200m/6287) mô tả base pool50→100 triệuSDR và recovery36→18blocks; hai thay đổi này không đồng nhất với nhân base pool4. Ngày công bố/bỏ phiếu không xác định ngày thực thi. Probe riêng đang tách ba đại lượng để đánh giá ảnh hưởng, giữ nguyên mốc giả định khi so cơ chế; không gọi probe là replay tham số on-chain đã xác minh.

Replay tách `chain_open`, `anchor_open` và `native_open`. Hai khoảng gián đoạn xấp xỉ từ khoảng trống giao dịch là 12/05 16:01–17:45 UTC và 13/05 01:59–11:27 UTC. Anchor tiếp tục phục vụ sau restart; native vẫn tắt từ 13/05 02:00. Thời điểm rời rạc hóa theo bước ABM có thể lệch vài phút; đây không phải replay block chính xác. Phản thực tế không bị ép các khoảng ngừng lịch sử. Oracle/quote của arbitrage chung cập nhật một phút; chưa có độ trễ thực thi khác nhau từng arbitrageur.

Ngân sách BTC dùng timestamp chuyển đã công bố, với gross transfer và net-budget attribution được ghi riêng. Biên muộn BTC thêm một giờ là giả định thời gian vận hành, không phải timestamp giao dịch được xác minh. Net attribution giữ tổng 80.081 BTC; khoản chuyển nội bộ/hoàn lại không tạo quỹ mới. Khoảng khả dụng riêng TFL vẫn chưa được nhận dạng chính xác.

[Bằng chứng governance](<D:/New folder/luna-ust-sim/outputs/improvement/GOVERNANCE_REDEMPTIONS_VI.md>) đối chiếu [kiểm toán JS Held](<D:/New folder/luna-ust-sim/data/external/LFG-Audit-2022-11-14.pdf>), trang 10, 12-14, với bảng native theo địa chỉ trong nguồn. Jump chuyển 1.515.689.462 UST sang TFL, chủ yếu ngày 11/05; bảng còn có 878 UST ngày 10/05. Các giờ bàn giao token không xác định giờ mua UST trên thị trường. Mô hình chưa có chuỗi lệnh riêng của Jump, và không cấp thêm USD/UST từ khoản chuyển nếu đã dùng cùng BTC để mua token.

Replay hiện chưa có hành động quỹ tự đổi UST sang LUNA để stake/phòng vệ quản trị, độc lập với arbitrage có lợi nhuận. JS Held trang 14, đoạn 36-38, khảo sát swaps của 10 bot trong 09-11/05 và xác nhận 220.694.577 LUNA được chuyển tới ví staking ngày 12/05. Lượng UST tương ứng được ước lượng trong **785.501.572-825.615.759**, midpoint **805.558.665**; số 883,5 triệu trong tweet cũ đã được điều chỉnh. Không tìm được tập swaps khớp chính xác và không có lịch governance burn theo phút. Midpoint chiếm khoảng 10,75% tổng native burn quan sát 07-13/05, nhưng không phải lượng cần cộng thêm lên observed aggregate hoặc ép mô hình thực hiện. Khoản UST 1.796.182.310 TFL chuyển cho LFG vẫn nằm trong số dư UST cuối LFG 1.847.079.725; chuyển nội bộ không phải burn.

Giữ các đại lượng TFL riêng biệt: gross purchases 08-10/05 là **1.901.559.334 UST / 1.773.199.279 USD**; net purchases là **1.464.738.304 UST / 1.375.600.151 USD**. Số **1.086.051.513 UST** suy ra từ estimated purchases thay mặt LFG trừ khoản Jump chuyển không phải total net purchases TFL. Gross turnover có bán lại/tái sử dụng vốn, không phải ngân sách mới. Snapshot TFL Binance 796.368.008,78 UST đầu 08/05 không xác định ownership lúc khởi tạo 06/05; UST đã sở hữu không phải backing USD hoặc grant mới.

Cơ chế governance còn thiếu là giới hạn cấu trúc của bản nhỏ đang hiệu chỉnh. Nếu bằng chứng fidelity sau fit yêu cầu bổ sung, chỉ cân nhắc redemption từ UST quỹ đã sở hữu, dùng chung virtual pool và phí, giữ/stake LUNA nhận được; thiếu token giữ backlog. Cap thấp/midpoint/cao và lịch trong 09-11/05 là độ nhạy, không ép mint đúng 220.694.577 LUNA hoặc thêm tiền. Đợt fit hiện tại và bốn loại chính sách không được coi đã có cơ chế này. Độ khớp aggregate chưa nhận dạng được riêng tác động governance, Jump, độ sâu và hành vi; không dùng kết quả để khẳng định nguyên nhân hay chính sách cứu được lịch sử thật.

## 7. Hiệu chỉnh và thí nghiệm

Hai bộ tham số: train 06–10/05 và kiểm tra tham số 11–15/05; full-fit 06–15/05 chỉ dùng trình diễn trong mẫu. Cấu trúc đã biết toàn sự kiện nên kiểm tra thời gian không phải cấu trúc ngoài mẫu độc lập. Hàm tối ưu v3 chuẩn hóa theo sáu gate cũ, cân bằng các giai đoạn, phạt onset `2×(sai lệch giờ/6)^2` và thêm tín hiệu depeg mềm. Khối lượng native theo ngày và phí tại bước có swap thật tiếp tục là mục tiêu. Không nới ngưỡng.

Tìm kiếm rộng bằng differential evolution rồi refinement; khởi tạo 75% Latin hypercube toàn khoảng và 25% gần warm start. Simplex refinement đi 2% khoảng từng tham số và hướng vào trong tại biên. Upper capacity 10^10,5 UST/ngày cho phép kiểm tra các mức phí vượt trần do range cũ; đây không phải vốn cấp thêm. Checkpoint chỉ dùng khi hash nguồn/đầu vào, search, split và cấu hình khớp. Mỗi đợt ghi baseline, provenance, tham số và trạng thái thực thi. Nghiệm cuối được kiểm tra fast/cadCAD. `baselines/v2/` giữ bản cũ; so sánh kiểm soát dùng lại dữ liệu đã sửa để không gọi thay đổi định nghĩa mục tiêu là cải thiện cơ chế.

Nghiệm thu hiện hành chấm sáu ngưỡng lịch sử, coverage nhóm, nhiều seed, bước5/15 phút, conservation và parity; không chấm chính sách. Ensemble đã xuất chỉ phản ánh seed ở tham số fit deterministic. Sau khi chốt cơ chế stochastic cần fit ensemble với bộseed chung và kiểm bằng seed mới, tách sampling population khỏi participation nếu muốn giải thích hai nguồn biến động.

Phần tùy chọn cũ có7 kịch bản×20 seed: replay, không cứu trợ, mua UST, thanh khoản, native, gate và kết hợp; dùng cùng bộ tham số và seed giữa kịch bản. Độ nhạy gồm độ sâu, hành vi, quỹ sớm/muộn, delay, threshold và pool. Khoảng5–95% chỉ phản ánh seed; không là khoảng tin cậy về lịch sử. Đây không còn là phạm vi phát triển/nghiệm thu hiện hành.

Cứu vãn đòi peg trong [0,98;1,02] liên tục 48h sau khởi phát, xử lý ≥95% yêu cầu rút mới cộng tồn đọng đầu cửa sổ 24h, khớp ≥95% lệnh native đã gửi, Anchor/native hoạt động, hàng đợi không tăng đáng kể, quỹ còn và toàn bộ 7 ngày ngừng hỗ trợ vẫn đạt điều kiện. Lệnh native tính sau giới hạn vốn/tốc độ, không đo toàn bộ nhu cầu tiềm ẩn; cửa sổ không có lệnh được coi không có nghĩa vụ native chưa xử lý. Đóng rút để giữ giá đơn thuần không đạt tiêu chí. Kết quả không cứu được trong các preset không chứng minh mọi chính sách đều bất khả thi.
