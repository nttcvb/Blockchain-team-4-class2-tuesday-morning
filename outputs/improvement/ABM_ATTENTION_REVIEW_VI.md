# Rà soát tần suất quyết định rút tiền

**Có bằng chứng để nghiên cứu một trần tần suất quyết định phụ thuộc đặc điểm trước run. Độ trễ quan sát 15–120 phút hiện tại không diễn tả được người giữ tiền nhiều ngày.** Tuy nhiên, không nên đưa thêm cơ chế vào engine đang fit hoặc coi tỷ lệ ví chưa rút là tỷ lệ người không kiểm tra tài khoản đã được đo. Đề xuất bên dưới là giả thuyết ABM cần hiệu chỉnh chung và so sánh, không phải correction theo đường mục tiêu.

Đã đọc nguồn raw và hai trajectory lưu sẵn; không chạy mô phỏng, optimizer, chính sách hay sửa engine/config/calibrate/data/metrics. Phạm vi quan sát được giữ đúng như bản coverage đã sửa: 768 thời điểm mỗi nhóm, từ May6 00:15 đến bucket cuối **May14 00:00 UTC**, 289 thời điểm validation từ May11. Không dùng phần nhóm kéo dài giả sang May14–15.

## Bảng kiểm tra cohort

Tỷ lệ là **phần vốn đầu kỳ còn chưa rút theo FIFO**, không phải tỷ lệ địa chỉ. Cột warm là replay của all-checkpoint call1342 trên engine6cb, trước sửa seed-window; nó là warm-start đã chọn, không phải trajectory của lần fit mới đang chạy. Cột train là trajectory 723-call train cũ, chấm lại trên coverage đúng.

| Nhóm | Quan sát bucket cuối | Train cũ | Warm full-event6cb | % vốn đầu kỳ ở ví không có direct withdrawal | % địa chỉ không có direct withdrawal |
|---|---:|---:|---:|---:|---:|
| <1K | 56,594% | 36,651% | 28,452% | 54,617% | 80,740% |
| 1K–10K | 34,200% | 32,215% | 28,211% | 30,468% | 34,809% |
| 10K–100K | 19,900% | 23,946% | 25,037% | 15,684% | 17,943% |
| 100K–1M | 11,651% | 17,627% | 21,200% | 8,040% | 9,591% |
| 1M–10M | 8,049% | 6,226% | 1,394% | 4,895% | 5,524% |
| >10M | 10,293% | 3,264% | 1,932% | 4,150% | 5,505% |

Raw cohort <1K có 118.183 địa chỉ và 18,265 triệu UST đầu kỳ. Có 95.421 địa chỉ không có direct withdrawal trong toàn tệp; vốn của các địa chỉ này bằng **96,506% phần vốn còn lại** của nhóm. Đối chiếu độc lập `max(initial−total_direct_withdrawal,0)` từng địa chỉ khớp giá trị cuối của `group_targets` tới sai số dưới `1e-12`. Do đó độ lệch nhóm nhỏ sau censor không còn là lỗi flow/FIFO/cohort đơn thuần.

Ngày May11 00:00, quan sát <1K còn 78,023%, train cũ 57,495%; May12 là 66,829% so với 45,620%; May14 00:00 là 56,594% so với 36,651%. Validation MAE nhóm này vẫn **0,190238**, vượt gate 0,15. Tổng tiền gửi validation NRMSE train cũ chỉ 0,069324 vì nhóm <1K chiếm khoảng 0,13% tổng tiền gửi Anchor ban đầu: độ khớp tổng dễ che sai lệch hành vi ở rất nhiều ví nhỏ.

Những nhóm khác không cùng một dạng lỗi. Train cũ làm 10K–100K và 100K–1M giữ nhiều hơn quan sát ở cuối; >10M giữ quá ít. Warm full-event tại thời điểm xác nhận depeg May9 18:15 chỉ còn 3,607% ở nhóm >10M, trong khi quan sát còn 53,617%. Vì vậy chỉ làm chậm nhóm nhỏ rồi giữ nguyên sự rút quá sớm của nhóm lớn không giải quyết toàn bộ ABM. Cơ chế mới phải được chấm trên cả sáu nhóm, total withdrawals, timing, giá và native cùng lúc.

Slope survival phục vụ đã quan sát từ May11 đến bucket cuối, `−log(R_end/R_start)/3 ngày`, lần lượt khoảng **0,107; 0,211; 0,321; 0,425; 0,486; 0,383 mỗi ngày**. Đây là mô tả sự thoát vốn được phục vụ, không phải phép đo số lần check tài khoản hoặc một lịch phải ép mô hình làm theo. Nó còn bao gồm thời gian chain halt, hàng đợi và giới hạn phục vụ; không đồng nhất slope với rate chú ý tiềm ẩn. Sự khác biệt giữa nhóm nhỏ và nhóm lớn tồn tại nhiều ngày, vượt xa lag tối đa hai giờ.

## Vì sao probability hiện tại có thể xóa khác biệt hành vi

Hiện tại:

```text
s_i = sigmoid(eta_i)
p_i(dt) = 1 − (1 − s_i)^(dt/15)
mu_old_i = −96 log(1 − s_i) = 96 softplus(eta_i), đơn vị /ngày
```

Đây là một hazard theo thời gian vật lý, nhưng **không có trần** khi eta tăng. Với eta hữu hạn, hazard toán học vẫn hữu hạn; trong tính toán, sigmoid có thể làm tròn thành 1 và probability thành 1. Sau khi tín hiệu rủi ro được quan sát, mọi ví có thể muốn rút ngay, dù đã gán lag 120 phút. Lag chỉ dịch tín hiệu, không tạo khoảng nhiều ngày giữa những lần đưa ra quyết định.

Train cũ có `hazard_discount ≈55,5103`, không phải 160. Với ví 100 USD, chỉ discount 20% và đặt outflow/LUNA/queue signals bằng 0 đã cho p15≈0,845 và hazard≈179/ngày; discount 50% cho p15≈0,999999989. Warm full-event có `hazard_discount ≈160,3942`: với ví 100 USD, discount 10% đã cho p15≈0,988; discount 20% gần như bằng 1. Các tín hiệu run/LUNA khác còn tăng eta. Chênh `hazard_size` hoặc lag không thể giữ nhóm nhỏ chậm khi eta cùng bão hòa.

Không suy ra từ số dư còn lại rằng người gửi luôn vô lý hoặc bất động vĩnh viễn. Direct Anchor withdrawals không phân biệt được ít chú ý, chủ động hold, mất quyền truy cập khóa, hoặc chuyển aUST sang địa chỉ khác rồi người nhận rút. Mục tiêu hiện tại đo FIFO qua withdrawal events, không tái dựng mọi thay đổi beneficial ownership qua transfer. Bằng chứng phù hợp với thiếu cơ hội quyết định; chưa nhận dạng nguyên nhân duy nhất.

## Hai cách giới hạn hazard

Một quy tắc cơ hội Poisson rõ về diễn giải là `p=1−exp(−lambda_i×sigmoid(eta_i)×dt/1440)`: check đến với rate lambda, rồi tại lần check tác nhân quyết định rút theo logistic. Nó giữ rate hữu hạn khi panic tăng. Nhưng đổi sigmoid từ probability/15 phút thành conditional propensity; với cùng eta ít rủi ro và lambda=1/ngày, hazard yếu đi khoảng 96 lần. Giữ nguyên intercept/search bounds đã fit có thể làm mất normal/pre-depeg outflow. Nếu chọn quy tắc này cần khai báo thay đổi ý nghĩa tham số và fit lại cả baseline; không đổi công thức rồi chỉ thêm một cap.

**Ứng viên đầu tiên nên dùng trần cho hazard cũ**, để giữ hành vi ít rủi ro đang được mô tả:

```text
mu_old_i = 96 softplus(eta_i)
lambda_i = attention_cap_day × min(1, (raw_prerun_wealth_i / 100000)^attention_wealth_elasticity)
mu_eff_i = min(mu_old_i, lambda_i)
p_i(dt) = −expm1(−mu_eff_i × dt/1440)
```

Diễn giải Poisson tương đương: các cơ hội tới theo lambda_i, xác suất rút tại một cơ hội là `min(1,mu_old_i/lambda_i)`. Khi mu_old nằm dưới trần, probability cũ được giữ đúng về toán học; khi panic mạnh, tốc độ thoát vốn bị giới hạn bởi cơ hội hành động. Không có số dư sàn theo nhóm, lịch ngày thật hoặc vốn của ví cố định không bao giờ được rút. Với lambda>0 hữu hạn, xác suất sống sót vẫn tiếp tục giảm nếu stress kéo dài.

Đề xuất chỉ hai tham số mới:

| Tên | Ý nghĩa | Miền thử nghiệm, chưa phải ước lượng thực nghiệm |
|---|---|---|
| `attention_cap_day` | Trần rate cho ví từ 100K USD trở lên | Dương; thử log-scale khoảng 0,05–96/ngày |
| `attention_wealth_elasticity` | Độ giảm trần đối với ví nhỏ hơn 100K | 0–1,5 |

Mốc 100K là normalization cố định theo phân nhóm, không là một threshold check được đo. Wealth phải là mức **trước run** của ví thật; không dùng `weight` của mẫu đại diện làm wealth. `build_population` hiện rescale `prerun_usd` trong từng mẫu để giữ tổng; nếu triển khai, giữ riêng raw wealth trước rescaling cho opportunity rule, còn claims/trọng số vẫn theo quy tắc kế toán hiện tại.

Biến thể chỉ một tham số, fixed cap96/ngày và beta theo wealth, là probe gọn hợp lệ. Nhưng mức này neo trần cao ở 100K mà dữ liệu không xác minh. Khi panic bão hòa, beta khoảng 1 mới đưa trần ví ~100 USD xuống ~0,1/ngày, trong khi ví vài nghìn USD vẫn có trần vài lần/ngày; khó khớp đồng thời slope 0,107/ngày ở <1K và 0,211/ngày ở 1K–10K. Cho phép ước lượng cả scale và elasticity là cách nhỏ hơn so với sáu cap riêng theo nhóm, và tránh khóa ứng viên vào một prior quá mạnh.

**Beta=0 không phải exact legacy control** nếu vẫn dùng cap96/ngày: p15 có trần `1−exp(−1)≈0,6321`, trong khi legacy p15 có thể gần 1. So sánh zero-change phải có nhánh tắt attention cap riêng, hoặc coi beta0 là một ứng viên trần đồng nhất có thay đổi hành vi. Không ghi parity với legacy chỉ dựa vào beta0.

## Những feature có thể dùng trước sự kiện

`prerun_usd`/`prerun_aust` từ snapshot May5 là đầu vào an toàn. `log_volume_adj`, `cex_degree`, `used_bridge`, `log_age_months` được pipeline và provenance mô tả là sophistication trước run; code chỉ dùng chúng để rút ngắn observation lag, chưa có continuous decision-opportunity rate. Raw history dựng sophistication không được phát hành nên không tái kiểm toán toàn bộ cutoff locally. Không dùng `full_maxusd`, `log_wealth` dựa trên maximum trong run, `perc_loss`, survival `status/time` hay `log10_size` dựa trên full_maxusd làm feature hành vi.

Feature coverage <1K là **37,114% số địa chỉ nhưng 98,933% vốn**; 74.319 địa chỉ dưới 100 USD phần lớn không có complete feature panel. Các nhóm từ 1K trở lên đều có complete feature coverage trong cohort này. Trong population1000 seed42, nhóm <1K có 150 agent lag120 và 14 agent lag15; 73,507% vốn đại diện thuộc lag120. Vì vậy missing sophistication nhiều về số ví nhưng rất ít về vốn, không giải thích được chênh ~20 điểm phần trăm survival bằng cách chỉ điền feature còn thiếu.

Ở ứng viên hai tham số đầu tiên nên dùng wealth trước run, giữ effect sophistication mới bằng 0. Sau đó chỉ thêm ảnh hưởng feature nếu có so sánh riêng và prior hợp lý; thiếu feature nên là missing/neutral, không tự gán ví bất động. Dữ liệu `hazard/survival_may6_12.parquet` hữu ích để kiểm chứng mô tả nhưng `log10_size` của nó dựa trên `full_maxusd`; không chép regression coefficients đó sang ABM rồi gọi là mô hình không nhìn tương lai.

Nguồn trực tiếp: [data.py](<D:/New folder/luna-ust-sim/luna_sim/data.py>), [engine.py](<D:/New folder/luna-ust-sim/luna_sim/engine.py>), [Datasets.md](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/Datasets.md>), [prep_loss_panel.py](<D:/New folder/terra-luna-run-replication (1)/terra-luna-run-replication/code/prep/prep_loss_panel.py>) và metadata `agent_feature_provenance` trong [sources.json](<D:/New folder/luna-ust-sim/data/sources.json>). Search các research artifacts/source đã có không tìm thấy bounded decision-opportunity hoặc attention ceiling prototype; old-holder probes là bán LUNA, không phải cơ hội rút Anchor.

## Kiểm chứng cần làm nếu chọn triển khai sau lần fit đang chạy

- Kiểm xác suất hữu hạn trong [0,1), monotonic risk/wealth đúng kỳ vọng, zero rate không tạo lệnh, và `mu_eff≤lambda_i`; trường hợp eta rất lớn không làm probability nhảy thành 1 vì overflow.
- Với tín hiệu/wealth/rate giữ cố định, survival tích lũy từ bước5 và15 phút phải cùng bằng `exp(−mu_eff×T)`. Khi tín hiệu nội sinh khác, dùng đối chiếu ensemble và timestep, không đòi hai đường ngẫu nhiên từng seed bằng nhau giữa hai cadence.
- Nhánh cap tắt phải khớp legacy toàn trajectory; fast/cadCAD phải khớp toàn trajectory cho cùng ứng viên/cấu hình. Bernoulli cùng semantics như deterministic expected request; không đọc mục tiêu survival để đưa ra quyết định.
- Requested UST chỉ lấy từ claim chưa xếp hàng; repeated opportunities không double-request, serviced withdrawal mới làm giảm FIFO initial principal; cash/UST/claims và ownership phải bảo toàn.
- Fit chung hazard và thị trường; báo cả sáu nhóm, total requests/served/queue, onset, native, giá và supply. Train parameters kiểm trên May11–13 có quan sát; full fit và current feature/target hashes riêng. Không chọn ứng viên chỉ vì <1K qua gate hoặc total deposits vẫn tốt.

Artifact máy đọc: [abm_attention_diagnostic.json](<D:/New folder/luna-ust-sim/outputs/improvement/abm_attention_diagnostic.json>), [daily CSV](<D:/New folder/luna-ust-sim/outputs/improvement/abm_attention_group_daily.csv>), [analysis script](<D:/New folder/luna-ust-sim/outputs/improvement/abm_attention_diagnostic.py>). JSON ghi SHA nguồn/target/input, các timestamp và score corrected của hai trajectory cũ, feature coverage, raw no-direct-withdrawal statistics. Các checkpoint mới đang chạy chỉ được lưu metadata, không được gán trajectory hoặc fidelity mới trong báo cáo này.
