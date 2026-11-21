# Rà soát stochastic ABM của bản tái dựng lịch sử

Bản core hiện tại chưa tái dựng lịch sử đạt các tiêu chí đã đặt ra. Bộ tham số full-fit deterministic đạt **2/6 gates**, nhưng **cả 20 seed stochastic 42–61 đều đạt 0/6**. Đây không phải sai khác do replay hay cadCAD: replay riêng của seed 42 và deterministic seed 42 khớp **chính xác mọi cột quỹ đạo, byte file Parquet và byte ledger CSV** của các artifact công khai. Vấn đề chính là chuyển một mô hình rút tiền phân số đã được hiệu chỉnh sang các lệnh rút toàn bộ số dư có trọng số, trong một hệ có phản hồi rất mạnh.

Phân tích này chỉ đọc core, raw inputs và kết quả công khai; replay hai cấu hình lịch sử đã có để ghi trace riêng; kiểm tra moment và chạy một bộ probe lịch sử riêng của giả thuyết rút từng phần. Không sửa core, không hiệu chỉnh mới, không chạy optimizer, không chạy chính sách và không chỉnh artifact công khai. Các file của `attention_fit` không được sửa.

![Đối chiếu replay và phản hồi rút tiền](<D:/New folder/luna-ust-sim/outputs/improvement/stochastic_review/seed42_feedback.png>)

## Kết quả và định danh replay

| Chỉ tiêu toàn sự kiện | Deterministic 42 | Stochastic 42 | Trung vị 20 seed stochastic |
|---|---:|---:|---:|
| UST MAE, gate ≤0,05 | 0,108195 | 0,133993 | 0,178259 |
| Deposit NRMSE, gate ≤0,10 | 0,120201 | 0,313287 | 0,276051 |
| LUNA price log RMSE, gate ≤0,5 | 1,181266 | 1,682489 | 2,487743 |
| LUNA supply log RMSE, gate ≤0,5 | 0,700134 | 0,969684 | 2,060647 |
| Group MAE max, gate ≤0,15 | 0,149765 | 0,336232 | 0,291601 |
| Onset sai lệch có dấu, giờ | +0,75 | −49,75 | +44,50 |

Onset được tính sau một giờ liên tiếp UST <0,98. Quan sát: **2022-05-09 18:15 UTC**; deterministic: **2022-05-09 19:00 UTC**; stochastic 42: **2022-05-07 16:30 UTC**. Trong 20 seed, onset trải từ **2022-05-07 05:00** đến **2022-05-15 10:45 UTC**, sai lệch −61,25 đến +136,50 giờ. Seed gần nhất vẫn lệch +8 giờ, ngoài gate 6 giờ. Không seed nào vượt qua bất kỳ gate nào.

Private replay dùng wrapper để ghi lại probability, các hạng logit, số dư trước quyết định và draw mà RNG gốc vừa trả về; wrapper không gọi thêm RNG. Các block và RNG trả cùng kết quả với bản công khai. File `seed42_replay_identity.json`, `deterministic42_replay_identity.json` chứng minh identity; `review.json` chứa hash core, raw inputs và public artifacts trước/sau; `private_artifact_hashes.json` chứa hash các file riêng.

| Artifact | SHA-256 quỹ đạo | SHA-256 ledger |
|---|---|---|
| Seed 42, public = private | `98403e20c235242f1c34dbe0708e96fde274c996890fe6bbb47cda50ec9039e4` | `845b611e6a59bc1d25c998ea266863b1a3289f9b04afd729bc0bdfc0449a732e` |
| Deterministic 42, public = private | `7f2f26f2ad57f9c475fff76bec6e7a33ad66c7e48e981d4e4443cf226d29d614` | `958bebbd321fec79098bd3b901b3f6a60dc10a3ed24a5d55098c2b2138a251e8` |

Core frozen: engine `0a89a9e6…`, config `610f1ed6…`, data `6331fab0…`, calibrate `7aa5ff34…`, metrics `c71e0345…`. Full hash nằm trong JSON. Mọi assertion `source_unchanged`, `raw_inputs_unchanged`, `public_artifacts_unchanged` đều true.

## Phản hồi gây onset sớm ở seed 42

Lệnh endogenous đầu tiên là **2022-05-06 02:45 UTC**: một wallet raw khoảng 9,9 nghìn USD được đại diện bằng một row weight **386,41** rút **3,634 triệu UST**, probability `3,0975e-5`, draw `1,3169e-5`. Lệnh ≥10 triệu đầu tiên lúc **04:45** cùng ngày là **33,764 triệu UST**, probability `1,1896e-4`, draw `1,9240e-5`. Row này là một phần của wallet >10M, weight **0,546**, không thuộc top20. Wallet raw đó có lần rút trực tiếp đầu tiên vào **May 8 00:40:17 UTC**; row trùng địa chỉ còn lại trong mô hình đến **May 7 16:15** mới kích hoạt. Hai row cùng một địa chỉ nhận draw độc lập, cách nhau 35,5 giờ.

Một mốc quyết định rõ hơn xuất hiện ngày **May 7 13:30 UTC**: whale thật thuộc top20, weight 1, rút **311,757 triệu UST** với probability **0,0006001** và draw **0,0003879**. Tổng lệnh endogenous kỳ vọng có điều kiện tại trạng thái đó chỉ **4,777 triệu UST**, nhưng lệnh thực tế là 311,757 triệu. Sau lệnh này, hạng logit do outflow một giờ của các tác nhân lag 15 phút tăng từ **0,120** lên **2,552**; kỳ vọng endogenous bước tiếp theo tăng lên **64,706 triệu UST**. Các draw whale tiếp theo lúc 15:15, 15:30, 15:45 đưa thêm 76,578; 83,742; 248,628 triệu UST vào dòng rút.

| May 7, UTC | UST sau bước | Lệnh endogenous kỳ vọng, triệu UST | Lệnh endogenous thực tế, triệu UST | Institution, triệu UST |
|---|---:|---:|---:|---:|
| 13:30 | 0,987229 | 4,777 | 311,757 | 0,435 |
| 13:45 | 0,986740 | 64,706 | 10,763 | 8,722 |
| 15:45 | 0,979187 | 54,852 | 255,354 | 4,848 |
| 16:00 | 0,970376 | 584,161 | 758,656 | 20,674 |
| 16:15 | 0,885102 | 7.119,493 | 7.146,097 | 1.300,547 |
| 16:30 | 0,876181 | 33,685 | 25,838 | 469,831 |

Lúc 16:15, probability của các row lớn đã gần 0,99–0,996; cash Anchor cạn ở 16:30, queue tăng lên 175,179 triệu UST. Cả ngày May 7 mô hình stochastic yêu cầu rút **13,742 tỷ**, deterministic chỉ **0,737 tỷ**; ngày May 9 deterministic mới bùng lên. Trace chứng minh chuỗi cơ chế trên chính đường chạy đã replay, nhưng không chứng minh rằng xóa riêng một draw sẽ sửa toàn bộ lịch sử hay rằng một draw giải thích tất cả 20 seed.

## Trọng số, địa chỉ trùng và exposure thực

`build_population` giữ top20 raw bằng weight 1, lấy phần còn lại **có hoàn lại** và chia gần đều 980 row cho sáu bin raw. Mỗi bin được rescale `prerun_usd` để tổng claim có trọng số đúng tổng raw của bin. Bin vẫn là bin raw ban đầu, trong khi hazard dùng `log_size` sau rescale. Seed 42 có 37 row đổi bin nếu phân loại lại bằng số tiền rescale. Đây là lệch nhỏ về đặc trưng kích thước, chưa phải nguyên nhân chính được chứng minh.

Tổng retail ban đầu **12,206 tỷ UST**; institution **1,848 tỷ**, tương đương **13,151%** tổng claim Anchor. Top20 giữ **3,002 tỷ**, tương đương **21,360%** tổng claim. 1.000 row chỉ gồm **902 địa chỉ khác nhau**.

| Bin raw | Địa chỉ raw | Row mẫu | Địa chỉ mẫu riêng | Weight phần mẫu | Row có địa chỉ trùng | Phương sai row/raw ở trạng thái đầu |
|---|---:|---:|---:|---:|---:|---:|
| <1K | 118.183 | 164 | 164 | 720,628 | 0 | 916,81× |
| 1K–10K | 63.372 | 164 | 164 | 386,415 | 0 | 380,38× |
| 10K–100K | 40.689 | 163 | 163 | 249,626 | 0 | 251,20× |
| 100K–1M | 10.406 | 163 | 162 | 63,840 | 2 | 63,02× |
| 1M–10M | 1.231 | 163 | 152 | 7,552 | 20 | 7,92× |
| >10M | 109 | 183 | 97 | 0,546; top20 =1 | 133 | 0,969× |

Bin >10M chỉ còn 89 địa chỉ ngoài top20 nhưng được lấy 163 row: 47 địa chỉ bị lặp, có địa chỉ xuất hiện 5 lần, 12 địa chỉ raw không xuất hiện. Các bản sao rút độc lập. Nếu coi row là wallet thật, tương quan cùng địa chỉ bị bỏ qua và vốn một wallet bị chia/lặp với multiplicity khác nhau. Nếu coi row là cohort nhân tạo, danh tính địa chỉ không còn là danh tính của toàn cohort; khi đó phải ghi rõ và không đối chiếu thời điểm row với wallet như quan sát trực tiếp.

Phương sai tổng ban đầu chỉ tăng **1,081×** so với Bernoulli trên từng wallet raw: SD **7,916 triệu** so với **7,614 triệu UST**, do **top20 chiếm 85,27% phương sai row**, nhóm >10M chiếm 88,70%. Vì vậy, sửa variance của weighted cohorts riêng lẻ chưa đủ. Gộp các row cùng địa chỉ và cho chúng một draw chung sẽ tăng phương sai tổng hiện tại thêm khoảng **1,092×**; sửa tương quan không tự động làm quá trình mượt hơn.

Chỉ bốn feature `log_volume_adj`, `cex_degree`, `used_bridge`, `log_age_months` được đọc để rút ngắn lag, không dùng `full_maxusd`, realized loss hay `log_wealth`. Seed 42 có 889 row đủ bốn feature, bao phủ khoảng 99,998% vốn retail; 166 row thuộc các nhóm nhỏ được rút ngắn lag xuống 15 phút, đại diện 1,593 tỷ UST. Lag cuối cùng: 512 row 15 phút, 215 row 60 phút, 273 row 120 phút. Tài liệu raw cho biết các feature là sophistication từ các panel gốc không được ship; điều này không biến lag của core thành tần suất kiểm tra ví đã được đo thực nghiệm.

Institution luôn dùng rút phân số ngay cả khi `stochastic=true`, dùng discount hiện tại và outflow bước trước, không dùng cùng lag/luna/queue như retail. Đây là một aggregate continuum khác với retail; ở 16:15 nó đóng góp 1,301 tỷ UST vào avalanche. Cần định nghĩa institution là continuum hay các chủ thể cụ thể trước khi diễn giải toàn mô hình là ABM stochastic theo wallet.

## Lần rút trực tiếp đầu tiên trong dữ liệu

Cửa sổ: **May 6 00:15 đến May 13 23:59:39 UTC**, là timestamp cuối của extract. Đo `UST của giao dịch rút dương đầu tiên / prerun_usd`; đây là tỷ số mô tả với vốn trước sự kiện tại gần dollar parity, **không phải phần trăm của claim chính xác ngay trước khi rút**. Lãi, nạp thêm, chuyển aUST và exchange rate có thể làm claim thay đổi. Giữ nguyên tỷ số >1; ví không có giao dịch rút được ghi riêng, không gán tỷ số bằng 0. Một giao dịch cũng có thể chỉ là một phần của một quyết định thực hiện qua nhiều giao dịch.

| Cohort | Có rút / tổng | Không có rút | p25 / median / p75 tỷ số | Số tỷ số >1 | % ≤0,10 / ≤0,25 / ≤0,50 |
|---|---:|---:|---|---:|---|
| Top20, bỏ A/B được supplied | 17/18 | 1 | 0,00682 / **0,03325** / 0,13530 | 0 | 64,71 / 88,24 / 100,00 |
| <1K | 22.757/118.183 | 95.426 | 1,00000 / 1,00176 / 1,00309 | 17.041 | 2,75 / 6,52 / 11,70 |
| 1K–10K | 41.312/63.372 | 22.060 | 0,46033 / 1,00132 / 1,00220 | 26.375 | 10,85 / 18,85 / 26,51 |
| 10K–100K | 33.386/40.689 | 7.303 | 0,15629 / 1,00093 / 1,00218 | 18.306 | 21,55 / 29,43 / 36,92 |
| 100K–1M | 9.408/10.406 | 998 | 0,06811 / 0,93968 / 1,00176 | 4.498 | 28,47 / 36,42 / 44,52 |
| 1M–10M | 1.163/1.231 | 68 | 0,06356 / 0,61706 / 1,00132 | 535 | 30,01 / 38,09 / 47,38 |
| >10M | 103/109 | 6 | 0,00834 / **0,06737** / 0,77228 | 23 | 51,46 / 61,17 / 69,90 |

Các quantile và tỷ lệ ≤ ngưỡng chỉ tính trên ví có lần rút quan sát. Toàn retail: 108.129/233.990 ví có rút; 125.861 không có rút trong extract. Median tỷ số là 1,00132 và 66.778 trường hợp >1. Điều này cho thấy giả thuyết rút gần toàn bộ có cơ sở hơn ở nhiều ví nhỏ; với whale, dữ liệu giao dịch đầu tiên hỗ trợ kiểm tra rút từng phần thay vì mặc định full-wallet tại lần kích hoạt đầu tiên. Không thể suy trực tiếp từ median 3,3% ra một tranche cố định đúng cho mọi lần rút.

## Các lựa chọn stochastic hợp lệ cần phân biệt

Đặt `m_i` là vốn một thành viên, `w_i` là số thành viên cohort, `A_i=w_i m_i` là claim khả dụng. Core dùng `R_i=A_i B_i`, `B_i~Bernoulli(p_i)`, do đó `E[R_i]=A_i p_i`, `Var(R_i)=A_i² p_i(1-p_i)`. Đây là **whole-cluster Bernoulli** hợp lệ nếu mọi thành viên trong cohort tham gia đồng thời và tương quan hoàn hảo. Với `w_i` lớn, nó không đại diện các ví độc lập có cùng đặc trưng.

Nếu cohort có `w_i` thành viên độc lập và bằng vốn nhau, dùng `K_i~Binomial(w_i,p_i)`, `R_i=m_i K_i`; cùng kỳ vọng nhưng phương sai `m_i² w_i p_i(1-p_i)`, giảm `w_i` lần so với whole-cluster. Phải duy trì số người/vốn còn lại và queue để không cho thành viên đã tham gia rút lần nữa như thành viên mới. Với weight không nguyên, một xấp xỉ giữ kỳ vọng là `w=n+r`, `R=m[Binomial(n,p)+r Bernoulli(p)]`; variance là `m²(n+r²)p(1-p)`. Đây là cohort tổng hợp, không tự khôi phục danh tính ví. Weight <1 đặc biệt cần xem lại cách tạo population thay vì gọi `Binomial(0,546,p)` không hợp lệ.

Ưu tiên giữ **mọi whale thật của tập nhỏ >10M bằng weight 1, địa chỉ riêng**, hoặc một ngưỡng whale xác định trước khi fit. Top20 hiện có phải tiếp tục weight 1. Không nên làm mượt whale bằng cách chia thành các row độc lập. Sample phần nhỏ còn lại không hoàn lại khi có thể; nếu lặp cùng wallet thật, dùng latent participation chung theo địa chỉ và giải thích trọng số survey. Nếu row đại diện cohort khác nhau, cần tách khóa cohort khỏi địa chỉ mẫu. Có thể bổ sung tương quan giữa nhiều ví nếu có bằng chứng, nhưng không gán tương quan tùy ý để khớp onset.

## Giả thuyết rút từng phần của whale: compound Poisson

Với probability 15 phút `p15`, đặt `µ=−96 log(1−p15)` theo ngày; tranche cố định `0<f≤1`, intensity `λ=µ/f`; trong `dt` ngày lấy `N~Poisson(λ dt)` và rút tỷ lệ `R=1−(1−f)^N` trên số claim chưa vào queue. Khi risk cố định:

`E[1−R]=exp(−µ dt)` và `Var(R)=exp[−µ dt(2−f)]−exp(−2µ dt)`.

Như vậy cùng conditional mean với deterministic, giữ moment qua chia thời gian vì số Poisson cộng lại và tỷ lệ vốn còn lại nhân lại. Khi risk nội sinh thay đổi, phải cập nhật intensity theo trạng thái và tích phân theo thời gian; identity fixed-risk không chứng minh quỹ đạo có phản hồi sẽ giống nhau giữa 5 và 15 phút.

Tại probability whale **0,0006001** của May 7 13:30, `f=0,1` cho lệnh một tranche khoảng **31,176 triệu** thay vì 311,757 triệu UST; xác suất/intensity xuất hiện tranche lớn hơn khoảng 10 lần để giữ mean. Variance ở mức risk nhỏ giảm gần 10 lần. Đây là thay đổi phân bố hành động, không chỉ giảm variance cohort, nên có thể xử lý đúng phần whale đang chi phối bất định; chưa có kết quả fit lịch sử cho giả thuyết này.

Private kiểm tra 48 trường hợp: `p15` bằng 0,0006001; 0,01; 0,1; 0,5; `f` bằng 1; 0,5; 0,25; 0,1; interval 5/15/60 phút, mỗi trường hợp 500.000 mẫu Monte Carlo. Tất cả mean nằm trong 6 standard errors của lý thuyết, moment chia thời gian đúng. Với `f=1`, dùng **nhánh uniform threshold gốc** đã kiểm tra equality; Poisson `N>0` chỉ bằng phân bố Bernoulli, không cho replay cùng seed do tiêu thụ RNG khác. Để tránh `p15` làm tròn thành 1, tính ổn định `µ=96 logaddexp(0,eta)` trước khi tạo rate; không truyền rate vô hạn vào Poisson.

Các kiểm tra 48 trường hợp trên là thử nghiệm moment ở risk cố định; probe lịch sử có phản hồi nội sinh được ghi riêng ở mục kế tiếp. File `compound_poisson_moments.csv`, `partial_liquidation_review.json` lưu dữ liệu và các assertion.

## Probe lịch sử riêng: tranche theo wealth, không optimizer

Đã tạo bản sao frozen và bản engine hiệu lực riêng tại `stochastic_review/partial_probe/`. Tham số thêm duy nhất là `β`, quy định `f_i=min[1,(raw_prerun_usd_i/100000)^(−β)]`; 100K là normalization chọn trước theo ranh giới cohort, không phải ngưỡng quyết định rút tiền được nhận diện từ giao dịch. `β≈0,5` cho f≈3,16% tại wallet 100 triệu USD, tương thích về quy mô với median mô tả của top20 nhưng không đo được tần suất quyết định. Probability vẫn do logit core quyết định; `µ=96 softplus(eta)` giữ hazard vật lý và tránh probability làm tròn bằng 1.

Chỉ nhánh stochastic với β>0 dùng compound Poisson. β=0 gọi chính dòng quyết định gốc; mọi nhánh deterministic gọi dòng gốc. Institution, seed window A/B, prefunding, queue, FIFO principal, cash và chủ sở hữu tài sản giữ nguyên. Raw wealth chỉ dùng để đặt tranche; UST/LUNA targets không vào override. Positive β thay cả phân bố lệnh và chuỗi RNG, nên không coi chênh lệch một đường seed là tác động nhân quả riêng của tranche.

Đã kiểm tra 12 cấu hình β/wealth của helper bằng 300.000 mẫu/cấu hình: moment, chia 15 phút thành ba đoạn 5 phút ở hazard cố định, duration 0, risk 0, risk cực lớn vẫn hữu hạn và các β không hợp lệ. β=0 stochastic seed42, β=0 deterministic42 và β=1 deterministic42 đều khớp public **mọi cột quỹ đạo và ledger byte**. Frozen baseline fast cũng khớp public cadCAD seed42. Mọi probe toàn sự kiện đều qua inventory/accounting checks.

| β, seed42 fast | UST MAE | Deposit NRMSE | LUNA price log | LUNA supply log | Group max | Onset sai lệch, giờ | Gates |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,25 | 0,124762 | 0,240206 | 1,514617 | 0,814246 | 0,243543 | −31,50 | 0/6 |
| 0,50 | 0,320303 | 0,270546 | 3,017627 | 2,164193 | 0,295715 | +61,00 | 0/6 |
| 0,75 | 0,117327 | 0,190612 | 1,526294 | 0,996801 | 0,191175 | −17,25 | 0/6 |
| 1,00 | 0,111512 | 0,143677 | 1,326735 | 0,843236 | 0,161068 | −5,50 | 1/6 |

Chọn β=1 theo quy tắc khai báo trước: số gate đạt cao nhất, rồi mean của sáu `metric/gate_threshold` thấp nhất, rồi β thấp hơn. Đây là chọn trong bốn probe đặt tên, không phải optimizer hay full-fit loss công khai. β=1 seed42 được replay bằng cadCAD toàn sự kiện, khớp **chính xác quỹ đạo và ledger byte** với fast. Nó chỉ đạt onset gate; onset là **May 9 12:45 UTC**. β=1 cho tranche 0,1% tại wallet 100 triệu USD, nên không được xem là ước lượng thực nghiệm từ median 3,3% của giao dịch đầu tiên.

Các seed 43–46 không tham gia chọn β. Đối chiếu small ensemble:

| Seed | Gate core / β=1 | Onset signed error core / β=1, giờ | Score sáu gate core / β=1 |
|---|---|---|---|
| 42 | 0 / 1 | −49,75 / −5,50 | 3,6084 / 1,6662 |
| 43 | 0 / 1 | −12,25 / +7,00 | 1,8854 / 1,8479 |
| 44 | 0 / 0 | −61,25 / −18,00 | 4,1005 / 2,1335 |
| 45 | 0 / 0 | +44,50 / −35,00 | 3,9456 / 2,9684 |
| 46 | 0 / 0 | +42,75 / −11,75 | 2,9136 / 2,0140 |

β=1 giảm score tổng hợp ở cả năm seed này, nhưng **0/5 seed đạt đủ sáu gate**. Seed43 chỉ đạt group gate, onset +7 giờ vẫn fail; một số chỉ tiêu LUNA của seed43 xấu hơn core. Mức dao động onset vẫn đáng kể. Vì vậy tranche riêng không giải quyết historical fidelity; weighted-cohort participation, attention và phản hồi vẫn cần được chốt cấu trúc và hiệu chỉnh stochastic bằng ensemble.

Ví dụ β=1 seed42 cadCAD: residual tương đối lớn nhất UST `1,3383e−13`, LUNA `4,3295e−15`, USD `1,1808e−14`, claim `1,7900e−14`, trong dung sai. Cần phân biệt độ đúng accounting với độ đúng lịch sử: accounting pass không làm những gate lịch sử còn thiếu trở thành pass.

Binding nguồn và tham số:

- Base engine SHA-256: `0a89a9e690c7998d8fadaa1756466b6195b67219483320403672a441cd95f7ea`.
- **Effective engine** SHA-256: `eda7a056248c26bef8d9297025f9d4d4ad49952c216b8eab134431de1a892e85`.
- Driver `partial_probe.py` SHA-256: `d00121d4ba2c44d8e433d8b9825415b8ab4159fdedf6dc0b33e36c0b897a4f35`.
- Base config all SHA-256: `b5b50361d49f5aa350174fab13f796b329be3918715821a4fb866af17f6fef94`; toàn bộ ModelParams giữ đúng bộ public này.
- Raw wealth snapshot SHA-256: `037a814b65c174e1a4b0090a6e1a29533e0e466ba2ea5ab0dc800fc81dba29c9`.
- Identity β=1/seed42/stochastic cadCAD: `4dcaf4c39194e34abc2e383fd3efc96e904cd9ebef7b0eb03d280b951b3931d0`; từng case lưu riêng beta, config, source và artifact hash trong JSON. Base engine hash một mình không định danh được variant.

Kết quả đầy đủ: `partial_probe/probe_result.json`, `mechanism_checks.json`, bản source frozen/effective, mọi trajectory/ledger và JSON của từng case. Sau probe, các assertion core/raw/public unchanged đều true. Không tích hợp cơ chế này vào core và không chạy thêm calibration.

## Hiệu chỉnh tối thiểu trước khi gọi là tái dựng stochastic

Trước optimizer, cố định đơn vị kinh tế của agent, quy tắc whale/partial liquidation, correlation theo địa chỉ và cách xử lý institution. Deterministic `A p` chỉ là **conditional mean tại một trạng thái cố định**; vì logit, queue, cash và giá có phản hồi phi tuyến, chạy deterministic không bằng kỳ vọng của quỹ đạo stochastic.

Sau đó cần một calibration stochastic riêng với ensemble seed cố định và common random numbers; tách stream sampling population khỏi stream participation để đo được hai nguồn bất định. Giữ tham số chung cho mọi seed; objective phải chấm lỗi từng realization/ensemble và phân bố onset, không chọn một seed đẹp hoặc chỉ fit đường mean. Dành seed mới để kiểm tra gate pass rate và độ ổn định onset. Cần giữ cả kiểm tra thời gian: fit May 6–10, giữ tham số cho May 11–15; đồng thời ghi đúng coverage của giao dịch và nhóm, censor sau May 13 23:59:39.

Ensemble 20 seed hiện tại chỉ kiểm tra bộ tham số được fit deterministic toàn sự kiện; các dải p05/p50/p95 là variation giữa seed trong cấu trúc đó, chưa là bất định đầy đủ của lịch sử. Attention fit riêng cũng cần kiểm tra stochastic sau khi chốt cơ chế; kết quả deterministic tốt hơn không tự chứng minh stochastic fidelity. Không có optimizer nào được chạy trong rà soát này.

Các artifact chính nằm tại [stochastic_review](<D:/New folder/luna-ust-sim/outputs/improvement/stochastic_review>): `review.json`, `trace_summary.json`, `population42_audit.parquet`, `population_seed_summary.csv`, `seed42_requests.parquet`, `seed42_decision_steps.parquet`, `may7_feedback.csv`, `top20_first_requests.csv`, `empirical_first_withdrawal_summary.csv`, `top20_empirical_first_withdrawal.csv`, `compound_poisson_moments.csv`, `partial_liquidation_review.json`, `partial_probe/probe_result.json`, cùng source script và hash. Không dùng các kết quả này để khẳng định mô hình đã đạt lịch sử.
