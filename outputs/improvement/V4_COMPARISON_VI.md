# Đối chiếu v3 và v4 đã kiểm toán

V4 đã sửa capacity assumption và clock LUNA rồi fit lại trên cùng objective/target/group fingerprints. Hai lần tối ưu khác ngân sách và điểm khởi đầu; đây không là ablation nhận dạng riêng tác động của từng sửa.

| Chỉ số toàn sự kiện | Ngưỡng | V3 frozen | V4 hiện hành |
|---|---:|---:|---:|
| MAE UST | ≤0.05 | 0.10819536 | 0.08827628 |
| Anchor NRMSE | ≤0.1 | 0.12020140 | 0.12019209 |
| LUNA log RMSE | ≤0.5 | 1.18126567 | 0.88281837 |
| Supply log RMSE | ≤0.5 | 0.70013352 | 0.50070352 |
| Group MAE max | ≤0.15 | 0.14976530 | 0.15328608 |
| Onset / giờ | ≤6 | 0.75000000 | 0.75000000 |

Loss 7.71141612 → 6.06007483; số gate đạt 2/6 → 1/6. Supply0,5007035 vẫn lớn hơn0,5; group0,1532861 lớn hơn0,15. Không làm tròn để biến fail thành pass.

Native total 5.959886 → 3.198692 tỷ UST; observed 7.490671 tỷ. Daily NRMSE 0.174419 → 0.258943; fee MAE 0.062343 → 0.057509. Native quantity/daily fidelity kém hơn dù loss chung giảm.

V4 all run `20261011T071942831158Z_all`, 274 tracked objective calls, 744.60s. DE và refinement đều hết ngân sách, chưa chứng minh hội tụ. Train run `20261011T071942383237Z_train` có14 calls,6/6 trong mẫu và2/6 parameter holdout. Nguồn mới và raw12 đã kiểm lại; cả hai saved cadCAD trajectories/ledgers khớp exact/byte-exact với fast replay mới.

Legacy stochastic seed42–61: 0/20 đạt đủ sáu gate; chỉ seed43 đạt riêng supply gate. Đây vẫn là parameters deterministic chuyển sang Bernoulli, không là fit ensemble. Accounting/owned stocks đạt ở tất cả seed. Bước5/15 còn nhạy mạnh:

- ust_mae_between_steps: 0.12954360
- deposit_nrmse_between_steps: 0.06309901
- luna_price_log_rmse_between_steps: 2.31362231
- luna_supply_log_rmse_between_steps: 2.27964595

Báo cáo và biểu đồ mới: [RECONSTRUCTION_VI.md](<D:/New folder/luna-ust-sim/outputs/reconstruction/RECONSTRUCTION_VI.md>) và [reconstruction.html](<D:/New folder/luna-ust-sim/outputs/reconstruction/reconstruction.html>). Manifest source current được xác nhận; fidelity chưa đạt.

Bước tiếp: fit private synthetic-capital ensemble với population/decision seeds tách nhau; đồng thời thiết kế sửa cadence thật theo thời gian vật lý. Không chọn outside token-demand probe vì dù bỏ inventory depletion, loss tăng12,649→92,425 và nguồn cung vượt6e20. Không sửa price path theo quan sát, không cấp USD mới và không phát triển suite chính sách.
