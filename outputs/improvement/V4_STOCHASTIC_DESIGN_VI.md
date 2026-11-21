# Thiết kế stochastic v4 để hiệu chỉnh ensemble

**Đề nghị chọn trước một mode `synthetic_capital_cp_v1`, chỉ thêm một tham số β, rồi fit các realization stochastic.** Giữ population donor seed42, raw wealth và weight đã đóng băng; đặt kích thước tranche theo raw wealth và weight. Đây là mô hình vốn tổng hợp với institution là continuum, không phải các ví thực độc lập. Nếu yêu cầu diễn giải từng whale thật, chọn phương án giữ toàn bộ 109 whale weight1 trước khi fit; đó là thay đổi population riêng.

Tài liệu này chỉ thiết kế. Không sửa engine, không thực hiện helper, simulation, optimizer hoặc policy. Nguồn đọc là archive `baselines/v3_frozen_20261011T010500Z/luna_sim`, hai review stochastic và `partial_probe/probe_result.json`. Engine đang được sửa ở công việc khác; các số cũ dưới đây chỉ là bằng chứng của v3, không là kết quả của engine sau sửa.

## Vì sao cần cả tranche và representation

V3 deterministic chỉ đạt 2/6 gate; cả 20 seed stochastic 42–61 đạt 0/6. Top20 weight1 chiếm 85,27% phương sai ban đầu của các row: chỉ sửa weighted cohort nhỏ sẽ bỏ qua nguồn biến động chính. Probe partial-whale β=1 giảm score sáu gate ở cả seed42–46, nhưng 0/5 seed đạt đủ sáu gate; onset sai lệch có dấu lần lượt −5,5; +7; −18; −35; −11,75 giờ. Các probe này chưa hiệu chỉnh stochastic và chưa thử combined kernel.

Tại trạng thái cố định, deterministic `A p` là conditional mean; nó không bằng mean quỹ đạo stochastic trong hệ có logit, outflow, cash, queue và giá phản hồi. Vì vậy chuyển tham số deterministic sang Bernoulli, hoặc chọn seed đẹp nhất, không đáp ứng mục tiêu tái dựng stochastic.

## Contract tối thiểu của mode đề nghị

Với mỗi row, cố định `raw_wealth > 0`, `weight = w > 0`, group raw và donor address. Không tính lại tranche bằng claim sau rút hoặc wealth đã rescale. Đặt:

\[
f_{wallet}=\exp[-\beta\max(\log(raw\_wealth/100000),0)],\qquad
f=f_{wallet}/\max(w,1),\qquad 0\le\beta\le1.
\]

100K là normalization từ ranh giới group được khai báo trước, không là ngưỡng giao dịch suy ra từ lịch sử. Giữ nguyên tổng/group exposure và rule hazard `log_size` của population snapshot; raw wealth chỉ xác định tranche. Row weight0 không có exposure và không draw. Top20 giữ weight1. Row weight<1 vẫn là fractional exposure, không biến thành một phần ví thực có danh tính.

Từ logit hiện hành η, physical hazard tích phân trong một bước là `H = softplus(η) × dt_minutes / 15`. Lấy `N ~ Poisson(H/f)` và yêu cầu mới:

\[
A=\max(deposit-queue,0),\qquad X=A[1-(1-f)^N].
\]

Không lặp N lần: một Poisson draw và một phép tính fraction mỗi row/bước. Dùng `logaddexp`, `log1p` và `expm1`; xử lý riêng `H=0`, `A=0`, `f=1`. Với `f=1`, uniform threshold xác suất `−expm1(−H)` cho phân phối Bernoulli đúng. Kiểm tra finite rate và phạm vi Poisson; config cực đoan không dùng được phải báo lỗi, không thay bằng rút deterministic hoặc sàn tranche ngầm.

Tại risk cố định, không có dòng vốn khác trong khoảng đang xét:

\[
E[X]=A(1-e^{-H}),\qquad Var(X)=A^2e^{-2H}\operatorname{expm1}(Hf).
\]

Independent Poisson increments giữ đúng phân phối remaining khi chia physical time. Đây là identity ở hazard cố định; khi thông tin, interest, queue service hoặc feedback đổi theo thời gian, không có identity cả quỹ đạo giữa 5 và 15 phút. Clock thông tin LUNA cố định 15 phút và removal của capacity step phải được kiểm chứng riêng trên engine sau sửa.

Với `w>1`, vốn mỗi chunk ban đầu gần `A f`; variance có cùng bậc đầu khi hazard nhỏ với tổng các wallet bằng vốn độc lập. Khi w là số nguyên, ở thời gian hữu hạn synthetic CP có variance **nhỏ hơn hoặc bằng** tổng w wallet độc lập:

\[
\frac{Var_{synthetic}}{Var_{independent}}=
w\frac{\operatorname{expm1}(Hf_{wallet}/w)}{\operatorname{expm1}(Hf_{wallet})}\le1.
\]

Không gọi công thức này là binomial identity; nó không giữ count người đã tham gia hay trạng thái riêng của từng wallet. Donor address bị lặp là provenance của cohort, không là các ví thật độc lập. Không bổ sung correlation tự do để chỉnh onset.

β là tham số mới duy nhất. Mean trực tiếp phụ thuộc hazard; β thay jump size/variance, nhưng feedback vẫn có thể làm chúng confound. Fit ban đầu chỉ mở β cùng `hazard_base`, `hazard_discount`, `hazard_outflow`; sau đó mới mở các tham số v3 còn lại nếu các gate LUNA/UST yêu cầu. Profile loss theo β với nuisance parameters được re-fit, đồng thời ghi request-size/onset dispersion; plateau nghĩa là β chưa được nhận diện, không gán nó thành ước lượng thực nghiệm. Không dùng median first-transaction ratio 3,3% của top20 như claim fraction chính xác hoặc rate tham gia.

## Replay, RNG và kế toán

- Có mode `legacy` rõ ràng. Mode này giữ nguyên population, đường quyết định, thứ tự draw và RNG initialization của engine nền đã sửa; không gọi helper mới, không spawn stream mới. Deterministic cũng đi nhánh nền. Byte parity của v3 dùng archive v3; parity của engine sau sửa dùng một baseline mới của đúng engine đó, không đòi nó khớp artifact v3 đã có lỗi capacity/clock.
- **β=0 trong combined mode khác legacy:** `f_wallet=1` nhưng `f=1/w` khi w>1. Không tái dùng β0 parity contract của partial-whale probe.
- Enabled mode load một population snapshot bất biến tạo bằng sampling seed42/algorithm v3, rồi dùng decision seed riêng. Persist row_id ổn định, donor address, raw wealth, rescaled wealth, group, weight và SHA. Tách `sampling_seed` và `decision_seed`; stream quyết định có stable tag và bit-generator/version riêng. Reset cùng stream cho mỗi candidate và từng seed để có common random numbers. Poisson phụ thuộc rate nên cùng RNG seed không bảo đảm các draw ghép cặp tối ưu; một seed không định danh tác động nhân quả riêng của β.
- X chỉ chuyển claim chưa queue sang pending queue. Request không tạo UST và không giảm deposit; service mới giảm deposit/queue, tăng wallet UST và giảm Anchor cash. Giữ interest, redeposit bằng UST sở hữu, supplied A/B window và prefunding có nguồn. Không đưa target UST/LUNA/Anchor hay lần rút thực của ví vào decision helper.
- Anchor service của v3 là **pro-rata pending queue** giữa retail và institution. FIFO là giảm initial-principal từng row khi service, không phải global FIFO theo timestamp request. Nạp lại và lãi không phục hồi principal đã thoát. Không đổi hai semantics này ngầm khi thêm stochastic kernel.
- Institution giữ continuum deterministic được đặt tên rõ; toàn mô hình là hybrid. Ledger phải đối chiếu request/service totals với queue, UST ownership, USD/LUNA/claims; ledger/debug row attribution dùng row_id, không gộp duplicate donor thành một wallet thực. Identity gồm effective source/config/raw/population SHA, mode, β, normalization, RNG rule, runner và clock.

## Objective và validation có thể thực hiện

Giữ loss v3 `gate_phase_onset_native_v3_group_coverage_v1` cho **từng realization**: global/phase/worst gate, onset, soft depeg, native volume và fee. Với K seed cố định, dùng `J = mean(loss_s) + 0.25 × max(loss_s)`; hệ số 0,25 khai báo trước, không fit. Accounting fail hoặc output thiếu/không finite là candidate invalid. Không tính metric của đường trung bình rồi gọi nó là ensemble fit; đường median/p05/p95 chỉ là biểu đồ mô tả.

Đề nghị decision seeds train `[1042,1043,1044]`, mở rộng nội bộ thành `[1042,1043,1044,1045,1046]`; dùng cùng một population seed42. Hai seed thêm dùng để chọn candidate thì là nội bộ calibration. Chốt parameters/identity trước khi kiểm tra decision seeds mới `2001–2020`. Seed42–61 đã được xem nên không gọi là held-out. Mọi seed dùng một bộ tham số chung; không chọn subset seed sau khi xem kết quả. Nếu quay lại chỉnh parameters theo kết quả validation, cần một bộ seed mới cho kiểm tra cuối.

| Gate giữ nguyên trên từng realization | Ngưỡng |
|---|---:|
| UST MAE | ≤0,05 |
| Anchor deposit NRMSE | ≤0,10 |
| LUNA price log10 RMSE | ≤0,5 |
| LUNA supply log10 RMSE | ≤0,5 |
| Group MAE max | ≤0,15 |
| Onset absolute error; UST <0,98 liên tiếp một giờ | ≤6 giờ |

Báo cả sáu metric/gate từng seed, joint 6/6 pass count, onset signed errors/dispersion và coverage. Mean loss giảm hoặc median curve đạt gate không đổi một seed fail thành pass. Không đặt acceptance rate thấp hơn để tuyên bố đã đạt mục tiêu. Kiểm tra seed mới chỉ là bất định quyết định trong một representation; không là uncertainty đầy đủ của lịch sử.

Mục tiêu chính là reconstruction toàn sự kiện May6–15. Chấm cả train/validation time slices với coverage gốc; censor group sau bucket quan sát cuối, không fill phần không có dữ liệu bằng số 0. Fit toàn sự kiện thì May11–15 là diagnostic slice, không được gọi là temporal holdout. Một kiểm tra temporal holdout thật cần run fit riêng chỉ May6–10 và giữ parameters cho May11–15; không thay thế mục tiêu full reconstruction.

## Tradeoff và ngân sách sau khi profile engine đã sửa

| Phương án | Lợi ích | Giá phải trả |
|---|---|---|
| A. Fixed donor population + synthetic CP | Giữ exposure, wiring claim/queue và chỉ thêm β; dễ kiểm tra kernel/ensemble | Underdispersion finite-time; whale weight<1 và duplicate donor vẫn là representation tổng hợp |
| B. Toàn bộ 109 raw whale >10M weight1; lower bins sample không hoàn lại | Danh tính/capital whale rõ hơn, bỏ omit và duplicate whale | Population mới; còn 891 lower-bin slots trong 1.000 row; phải chốt allocation, exposure reconciliation, seed mapping và re-fit; weighted lower bins vẫn cần participation semantics |

Ưu tiên A cho vòng sửa tối thiểu và so sánh có định danh; chọn B trước fit nếu diễn giải wallet thật là yêu cầu chính. Không thêm B như một tuning knob trong optimizer A và không trộn hai kết quả dưới cùng identity.

Sau khi engine capacity/clock đã sửa và mode được chọn: profile ít nhất ba full-event fast run trên cấu hình dễ/khó, đo toàn bộ objective gồm align/metrics, cold/warm cache, peak memory và throughput 1/2 workers. Chưa dùng runtime probe v3 để hứa ETA. Chỉ giữ ledger cho finalist/validation audit; cache target và population theo hash. Không dùng ít row hơn, deterministic screening hoặc coarse cadence làm objective tối ưu rồi gọi là exact full-population stochastic fit.

Một batch đầu có thể gồm: 5 giá trị β ×3 seed =15 run; 64 candidate calls ×3 =192; top5 candidate ×5 =25; frozen finalist ×20 seed mới =20; fast/cadCAD/clock audit dự trù 8 run. Tổng **260 full-event run**, cộng profile và các kiểm tra helper không có feedback. Batch joint-fit tiếp theo, nếu cần, dự trù 128 calls ×5 =640 run. Đây là ngân sách công việc, không là bảo đảm đạt sáu gate hoặc lý do thu hẹp mục tiêu.

Gọi `t95` là thời gian conservative/run thực đo và `q_w` là throughput thực đo với w worker: dự toán `T ≈ N/q_w + audit_overhead`; nếu chạy tuần tự dùng `N × t95`. Chốt batch size theo thời gian/memory thực tế rồi checkpoint từng ensemble evaluation. Chỉ tăng worker khi throughput tăng và memory còn dư. Kiểm tra cuối phải có helper mean/variance và partition ở hazard cố định, legacy disabled byte parity, deterministic parity, fast/cadCAD parity, inventory/claim/owner checks và cadence convergence với clock thông tin cố định. Mọi kết quả sau sửa cần identity mới.

Nguồn: [review stochastic v3](<D:/New folder/luna-ust-sim/outputs/improvement/STOCHASTIC_ABM_REVIEW_VI.md>), [review synthetic cohort](<D:/New folder/luna-ust-sim/outputs/improvement/stochastic_review/synthetic_cohort_review_vi.md>), [probe JSON](<D:/New folder/luna-ust-sim/outputs/improvement/stochastic_review/partial_probe/probe_result.json>), [probe script](<D:/New folder/luna-ust-sim/outputs/improvement/stochastic_review/partial_probe.py>). Contract máy đọc nằm ở [design_contract.json](<D:/New folder/luna-ust-sim/outputs/improvement/v4_stochastic_design/design_contract.json>).
