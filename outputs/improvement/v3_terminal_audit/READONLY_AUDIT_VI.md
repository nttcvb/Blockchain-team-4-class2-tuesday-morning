# Audit terminal v3 trên hồ sơ đã lưu

Audit này chỉ đọc hồ sơ và tính lại scoring/đối chiếu sổ cái. **Không chạy simulation hoặc optimizer mới.** Kết quả máy đọc: `audit.json`; mã thực hiện: `audit_saved.py`. Binding là archive `baselines/v3_frozen_20261011T010500Z`, engine `0a89a9e690c7998d8fadaa1756466b6195b67219483320403672a441cd95f7ea`. Không tuyên bố source hiện hành vẫn giữ hash này và không retag artifact v3 thành kết quả của core mới.

## Terminal và file còn thiếu

| Job đã ghi nhận | Ngân sách/counter cuối | Trạng thái hồ sơ | PID còn chạy |
|---|---:|---|---|
| Public train v3 | 266 calls | complete | 28168: không |
| Public all v3 | 460 calls | complete | 33152: không |
| Private coupled | 350/350 evaluations | complete | 38456: không |
| Private attention | 350/350 evaluations | complete | 32044: không |
| Protocol capacity review | 9/9 primary probes, 9/11 hard budget | complete, active_run=null | không có active run |

Lần Win32 process query trước khi root khởi chạy v4 profile không thấy Python process mang command line `luna-ust-sim`. Snapshot đó và các PID terminal ở trên **chỉ xác nhận các job v3 đã ghi**, không khẳng định hiện tại không có job khác. Root đã khởi chạy v4 profile sau lần quét này (session81078, source beb375…); job mới nằm ngoài phạm vi audit v3 này. Handle 19004/exit 0 đã được báo trong phiên trước nhưng audit này không có persistent exit log để xác minh riêng mã thoát đó.

**`attention_fit/runs/20261011T003911455486Z/audit.json` và `RUN_REVIEW.md` thực sự chưa tồn tại. `outputs/improvement/PROTOCOL_CAPACITY_REVIEW_VI.md` cũng chưa tồn tại.** Không đánh dấu các deliverable thiếu này là passed. `protocol_capacity_review/postprocessing_audit.json` có sẵn. Audit bổ sung ở thư mục này có trạng thái qualified_saved_artifact_checks_passed; không sửa auditor gốc hoặc bất kỳ file trong run.

Archive có 148 file khớp manifest. Protected source/raw/private source/coupling/effective helper bindings đã kiểm bằng hash trên file lưu. Các file transient/diagnostic không được archive gồm candidate_all, checkpoint_all_v3, checkpoint_train_v3, cross_venue_15min, diagnostics; audit không tuyên bố chúng đã được xác minh tại vị trí archive. Warm checkpoint trong private run có hash khớp byte với best_all được archive.

## Attention: cải thiện nhỏ, cơ chế được chọn cần mô tả đúng

350 records liên tiếp, đủ 17 chiều, named search values và physical parameters/parameter hashes khớp. Không có evaluation error được ghi. Stage counters: warm 2; uniform_ceiling_control 1; structured_exploration 30; joint_de 180; joint_local 135; verification 2. Final trajectory 959 bước; final fast/cadCAD trajectory **và ledger** khớp chính xác. Warm disabled khớp public warm và trajectory all trong archive.

| Control/candidate | Loss |
|---|---:|
| Frozen public warm | 7.711416118570 |
| Disabled warm | 7.711416118570 |
| Enabled uniform cap96/beta0 control | 8.579530500234 |
| Selected evaluation 324 | **7.498371876405** |

Candidate được chọn: attention enabled=true; cap=96/day; wealth elasticity=0; holder_exit_day=0; outside_max_ust=12 tỷ UST. Beta=0 tạo **trần đồng đều**, không là attention phân biệt theo wealth. Cap96 vẫn đổi xác suất: tại dt=15 phút, xác suất tối đa 1-exp(-1)=0.632120559, còn luật sigmoid legacy có thể tiến tới 1. Trên tín hiệu quỹ đạo cuối, 594260/958806 cơ hội ví sau loại conditional seed boundary có thay đổi xác suất; chênh lệch tối đa 0.367879441. Đây chỉ là đối chiếu xác suất trên tín hiệu đã lưu, không suy ra exposure, request amount hoặc causal loss contribution.

Hai core parameters cũng thay đổi so với warm: hazard_outflow 109.793245222926→109.519196780019 và luna_depth_growth 0.453412950202→0.476444092071. Vì là joint fit, không gán toàn bộ loss improvement cho attention. Holder sales thực tế bằng 0 trên trajectory và ledger. Ngoài cap 12 tỷ không bị chạm: external_ust max 10.154242380 tỷ. Không dùng các cơ chế bất hoạt hoặc constraint chưa chạm để giải thích improvement.

| Fidelity metric | Selected | Gate |
|---|---:|---|
| UST MAE | 0.107928303 | fail (≤0.05) |
| Deposit NRMSE | 0.119474314 | fail (≤0.10) |
| LUNA price log RMSE | 1.158360618 | fail (≤0.50) |
| LUNA supply log RMSE | 0.675149000 | fail (≤0.50) |
| Group MAE max | 0.141532477 | pass (≤0.15) |
| Depeg onset error | 1.0 hour | pass (≤6 hours) |

Chỉ **2/6 gates**, như warm all. Loss đã tính lại khớp 1e-12; fit metrics tính lại khớp record. Native simulated 5.980435936 tỷ UST so observed 7.490671480 tỷ; native_daily_nrmse 0.174517322, native_fee_mae 0.062234409. Final UST 0.000763144, LUNA 0.007308958, LUNA supply 518.414819974 tỷ. Accounting errors lớn nhất: USD 0.000190735; UST 0.001787186; LUNA 0.000122070; claim 0.000022888. Recorded-owner stock/tolerance checks đều đạt; min market_ust -1.455e-11 là sai số số học trong tolerance, không nên gọi tất cả tồn kho là tuyệt đối ≥0.

Không có holdout của private attention, không chứng minh convergence/global optimum/identification. Giữ kết quả exploratory, không tự promote.

## Qualification của target hash: đúng 8 NaN bit patterns

Recorded target _frame_hash trước serialize: `89e7a53d8d795cb48706657306144ee54e4306d667265520127cb31a3d59e4a9`.

Hash target đọc lại Parquet: `11cd01e049e06eab0b224b4ee6623d6779ec1ee687e375dc609d27dafd8256b6`.

Reconstruct targets bằng frozen data code từ 12 raw files có hash đã ghi tái tạo **đúng hash trước serialize**. Saved và rebuilt có cùng mọi giá trị hữu hạn, dtypes, timestamps và missingness; khác đúng 8 NaN của cột native_fee: saved `0x7ff8000000000000`, rebuilt `0xfff8000000000000`. Canonical missing-value hash khớp `11cd...`. Parquet còn bỏ frequency metadata của index target (saved None, rebuilt 15 Minutes); timestamps không đổi. Group hash khớp trực tiếp `c606efc0...` và không có NaN bit difference.

Do đó direct saved hash check của auditor gốc vẫn **không đạt** nếu chạy nguyên văn; không đổi raw/source/targets/recorded hashes để ép pass. Audit này ghi rõ exception và kiểm exact semantic identity cùng raw reconstruction; không gọi original operator audit là đã hoàn thành.

## Protocol capacity: source priority dù fit xấu hơn

9 results/configs/source variants/trajectory/ledger đã đối chiếu với counters và frame/file hashes; all/train/holdout scoring và metrics tính lại từ saved artifacts khớp. AST của mọi function ngoài observation và _market_minute khớp frozen engine; AST ngoài functions khớp; hash hai function được sửa khớp source_ast_binding. Core control trajectory và ledger khớp public archived train/all chính xác. Owner/accounting checks của cả 9 probe đạt. Không có additional cadCAD: không candidate nào có all objective hoặc train-parameter holdout objective tốt hơn control tương ứng, đúng predeclared rule.

| All-parameter variant | All loss | Gate count | Native UST simulated (tỷ) | Final LUNA | Final LUNA supply (tỷ) |
|---|---:|---:|---:|---:|---:|
| Core legacy step | 7.711416119 | 2/6 | 5.959885721 | 0.008353 | 453.537717 |
| No bump | 43.556310046 | 2/6 | 3.134538634 | 27.933424 | 0.832099 |
| Proposal early + arb4 | 13.015170369 | 2/6 | 6.117390586 | 0.022440 | 161.387199 |
| Proposal early + arb1 | 43.468141763 | 2/6 | 3.507447406 | 22.980094 | 0.850954 |
| Arb4 whole event, no pool bump | 43.569879589 | 2/6 | 3.157797852 | 27.758011 | 0.832893 |

No-bump bỏ giả định pool4/arb4 từ 11/05 12:00UTC, làm native burn/mint tụt mạnh và LUNA collapse không được tái hiện dưới bộ params cũ. Đây là lỗi fidelity cần retune/phát triển mô hình sau sửa source, không là evidence lịch sử cho step cũ. Proposal early + arb4 tăng native quantity một chút so core nhưng LUNA price/supply RMSE xấu hơn; proposal early + arb1 giống vấn đề no-bump. Native quantity và weighted fee vẫn là fidelity trades, không thể chỉ báo gate count.

Nguồn governance đã lưu: provider response 1164 và node network columbus-5 được binding bằng hash. Submit/voting start 11/05/2022 07:45:19.205592562Z; **voting end 18/05/2022 07:45:19.205592562Z**. Proposal content BasePool100 triệu SDR, PoolRecoveryPeriod18blocks; không phải đồng thời nhân base USD/arb capacity×4 và giữ recovery.

Các tag classic-core v0.5.19 và v0.5.20 đều bind cùng Terra SDK revision 515df8b16c89 qua go.mod. Proof của hàng đợi bỏ phiếu đã kết thúc trong revision này có tên API thực tế **ActiveProposalQueue**, không có symbol tên EndedVotingQueue: proposal.go ActivateVotingPeriod đặt VotingEndTime rồi insert queue; keeper.go ActiveProposalQueueIterator chỉ duyệt queue hết hạn theo endTime; abci.go EndBlocker dùng block time, tally proposal rồi handler/cache write khi passed. vote.go AddVote chỉ lưu vote và hook/event, không thực thi khi đạt threshold. SubmitProposal gọi handler trong branch để validate nhưng không persist state. Vì vậy submission hay đạt số phiếu sớm không là execution timestamp.

Links nguồn/điểm đọc: [tag dependency v0.5.19](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/classic-core-v0.5.19-go.mod:130>), [proposal activation](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-proposal.go:186>), [bounded queue iterator](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-keeper.go:167>), [EndBlock execution](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-abci.go:46>). Dữ liệu nguồn còn nguyên.

Các variant áp nội dung1164 tại May11 được predeclare là **counterfactual early activation**, không là lịch sử đã xác minh. Provider JSON + tagged implementation không là signed historical state proof; chưa loại trừ manual/emergency parameter change riêng. Tuy nhiên **1164 không hỗ trợ activation May11** trong cửa sổ tái hiện May6–15. Core correction cần ưu tiên evidence đó bất kể loss xấu đi.
