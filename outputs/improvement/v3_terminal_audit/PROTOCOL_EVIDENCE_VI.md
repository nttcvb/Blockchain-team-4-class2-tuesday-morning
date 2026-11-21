# Protocol capacity: evidence đã lưu và chín ablation v3

**Proposal1164 không chứng minh activation ngày11/05/2022.** Hồ sơ provider ghi voting_end_time **18/05/2022 07:45:19.205592562Z**, nằm ngoài cửa sổ mô hình May6–15. Source governance chỉ persist execution khi hàng đợi bỏ phiếu đã kết thúc được EndBlocker xử lý. Vì vậy step pool4/arb4 từ May11 12:00UTC trong frozen v3 cần được sửa theo evidence, dù dùng lại params cũ khiến fit xấu hơn.

Báo cáo này chỉ tổng hợp raw response/source snapshots và **9 simulation đã lưu trước đó**; không chạy simulation/optimizer mới hoặc sửa public/core. Kết quả của frozen engine `0a89a9e6…` được audit theo `baselines/v3_frozen_20261011T010500Z`; không retag là fit của engine hiện hành. Machine audit: [audit.json](<D:/New folder/luna-ust-sim/outputs/improvement/v3_terminal_audit/audit.json>).

## Field governance và giới hạn evidence

| Field trong hồ sơ provider 1164 | Giá trị |
|---|---|
| Proposal ID | 1164 |
| Submit/voting_start_time | 2022-05-11T07:45:19.205592562Z |
| Voting_end_time | **2022-05-18T07:45:19.205592562Z** |
| Status được endpoint trả về | PROPOSAL_STATUS_PASSED |
| BasePool content | 100,000,000,000,000 microSDR = 100 triệu SDR |
| PoolRecoveryPeriod content | 18 blocks |
| Provider network | columbus-5 |
| Fetch time UTC | proposal01:01:53, node01:01:55 ngày11/10/2026 |

Saved proposal SHA256 `2eef11d39da8fd6a5faa94744d7a1e9bf8f1b205a47e9cab39e23ad8a27cc2d6`; node_info SHA256 `fbb1bfc8574287ca5e9c41b7e4056ff984b69b932ca3cf8ce35a9b0edeea6ee7`. Fetch metadata, response và network binding được hash-check. Xem [hồ sơ1164](<D:/New folder/luna-ust-sim/outputs/improvement/governance_1164_evidence/proposal_1164.json>), [node network](<D:/New folder/luna-ust-sim/outputs/improvement/governance_1164_evidence/node_info.json>) và [EVIDENCE_VI.md](<D:/New folder/luna-ust-sim/outputs/improvement/governance_1164_evidence/EVIDENCE_VI.md>).

Đây là publicnode JSON snapshot và tagged implementation, **không có signed historical state proof**. Không suy ra exact execution block chỉ từ status passed và voting_end; không chứng minh tuyệt đối không từng có manual/emergency upgrade hoặc parameter change khác. Kết luận hẹp có căn cứ là: **proposal1164 không hỗ trợ lấy ngày submit/May11 làm execution timestamp**. Cần hồ sơ parameter tại block hoặc nguồn execution riêng để xác nhận thay đổi khác.

## Proof của hàng đợi bỏ phiếu đã kết thúc

Classic-core v0.5.19 và v0.5.20 go.mod đều replace cosmos-sdk bằng Terra SDK revision515df8b16c89. Các file source/fetch SHA được giữ ở protocol_capacity_review/primary_sources.

1. [ActivateVotingPeriod](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-proposal.go:186>) đặt VotingEndTime=VotingStartTime+VotingPeriod và insert proposal vào active queue theo VotingEndTime.
2. [ActiveProposalQueueIterator](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-keeper.go:167>) giới hạn queue theo endTime; [EndBlocker](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-abci.go:47>) truyền block time rồi tally, gọi handler và persist cache khi passed.
3. [AddVote](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-vote.go:12>) lưu vote, hook/event; không có execution sớm do vượt threshold. [SubmitProposal](<D:/New folder/luna-ust-sim/outputs/improvement/protocol_capacity_review/primary_sources/terra-sdk-515df8b16c89-gov-proposal.go:18>) gọi handler trong cache để validate nhưng không persist state.

Tên symbol thực tế là ActiveProposalQueue, không phải EndedVotingQueue; “queue đã kết thúc” mô tả điều kiện thời gian được iterator/EndBlocker áp dụng. Nội dung1164 tương ứng BasePool50→100 triệu SDR và recovery36→18blocks; không trực tiếp chứng minh ×4 base USD và ×4 arb capacity trong engine.

## Chín probe terminal và kết quả

Review complete9/9 primary probes,9/11 hard budget,active_run=null. 0 cadCAD bổ sung: không candidate nào cải thiện strict all objective với all params hoặc holdout objective với train params so control tương ứng, đúng rule predeclared. Final source/config/trajectory/ledger hashes, unchanged AST, all/train/holdout metric recomputation và owner/accounting checks đều đã audit. Core controls khớp archived public trajectory/ledger chính xác. Không có probe mới trong audit này.

| Saved run | All loss | Holdout loss | All gates |
|---|---:|---:|---:|
| train_core | 145.613945479 | 282.822389952 | 3/6 |
| train_no_bump | 145.696699653 | 282.963117182 | 3/6 |
| train_proposal_arb4 | 145.614672597 | 282.823605122 | 3/6 |
| train_proposal_arb1 | 145.614672569 | 282.823605071 | 3/6 |
| all_core | 7.711416119 | 15.785833726 | 2/6 |
| all_no_bump | 43.556310046 | 109.696947380 | 2/6 |
| all_proposal_arb4 | 13.015170369 | 24.602583218 | 2/6 |
| all_proposal_arb1 | 43.468141763 | 110.024828447 | 2/6 |
| all_arb4_whole | 43.569879589 | 109.761785952 | 2/6 |

“Holdout” trên all params là diagnostic, vì all params đã fit cả event; không là test ngoài mẫu độc lập. Train params đúng temporal split có holdout rất xấu trong mọi variant. Onset metric dùng complete-event onset theo frozen fit_metrics; holdout objective có onset sau khi slice riêng nên hai đại lượng được báo tách biệt.

Core/no_bump/proposal variants trước May11 12:00UTC có527 rows khớp control chính xác; arb4_whole cố ý đổi arb capacity từ đầu event và diverges từMay9 18:45UTC. Proposal_arb4/arb1 áp BasePool×2,recovery×0.5 tại May11 là **counterfactual early activation**, đã predeclare như vậy, không là historically valid candidates. SDR/USD conversion và block/minute recovery vẫn là xấp xỉ frozen.

Với all params, bỏ bump tăng loss7.7114→43.5563, native UST volume5.9599→3.1345 tỷ (observed7.4907 tỷ), final LUNA0.008353→27.9334 và supply453.5377→0.8321 tỷ. Không tái hiện được native mint/collapse sau correction với params cũ. Proposal early+arb4 native6.1174 tỷ gần quantity hơn core nhưng LUNA price/supply log RMSE xấu hơn; còn arb1/no_bump giữ giá LUNA quá cao và mint quá ít. Đây là fidelity trades cần retune hoặc sửa cơ chế; fit thấp hơn của step cũ không thay thế historical evidence.

Các kết quả vẫn exploratory và failed fidelity; không auto promote hoặc gọi lịch sử đã tái hiện thành công. Missing original `outputs/improvement/PROTOCOL_CAPACITY_REVIEW_VI.md` được ghi rõ; báo cáo này là supplement ở folder audit sở hữu, không giả định file thiếu đã tồn tại.
