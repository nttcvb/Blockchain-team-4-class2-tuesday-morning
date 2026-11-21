# Hồ sơ governance1164 và mốc capacity trong mô hình

Truy vấn ngày11/10/2026,01:01UTC. Đây là dữ liệu ledger công khai trả qua publicnode; chưa xác minh bằng light client hoặc proof chữ ký. `node_info.json` xác nhận network`columbus-5`. Giữ nguyên response, thời điểm truy vấn và SHA trong thư mục này.

| Trường hồ sơ1164 | Giá trị |
|---|---|
| Submit/voting start | 2022-05-11T07:45:19.205592562Z |
| Voting end | 2022-05-18T07:45:19.205592562Z |
| Status hiện trả về | PROPOSAL_STATUS_PASSED |
| Parameter changes | BasePool100.000.000 SDR; PoolRecoveryPeriod18blocks |

Nguồn: [proposal1164 RPC/LCD record](https://terra-classic-lcd.publicnode.com/cosmos/gov/v1beta1/proposals/1164), [node network record](https://terra-classic-lcd.publicnode.com/cosmos/base/tendermint/v1beta1/node_info). `BasePool` lưu100.000.000.000.000 microSDR; không là100 triệu USD. [Nội dung đề xuất gốc](https://classic-agora.terra.money/t/proposal-help-ust-pegging-increase-estimated-minting-capacity-to-1200m/6287) ngày11/5 mô tả pool50→100 triệuSDR và recovery36→18blocks. [Bài TFL ngày12/5](https://classic-agora.terra.money/t/burn-the-remaining-ust-in-the-community-pool-cross-chain-liquidity-incentive-ust/6837) còn mô tả1164 là đề xuất đang live trên Station.

Core`0a89a9e6…` đặt `pool_multiplier=4` từ11/05 12:00UTC; field đó đồng thời nhân base pool và arb capacity, giữ recovery. Như vậy nó khác nội dung1164 ở cả mapping tham số lẫn mốc giả định. Kết thúc bỏ phiếu18/5 nằm ngoài cửa sổ tái hiện6–15/5. Không dùng ngày công bố hoặc comment về voting threshold làm execution timestamp.

Đang kiểm tagged governance EndBlocker và chạy9 ablation có nguồn riêng để đo ảnh hưởng; public core chưa sửa khi fit attention còn chạy. Các biến thể áp nội dung1164 tại11/5 là **phản thực tế kích hoạt sớm**, không là candidate tham số lịch sử đã xác minh. Biến thể bỏ bump chỉ bỏ giả định cũ; chưa khẳng định không có thay đổi thủ công/emergency upgrade nào khác trong lịch sử. Cần hồ sơ tham số tại block hoặc nguồn thực thi riêng để giải quyết phần đó.

Tệpresponse`proposal_1164.json` SHA256`2eef11d39da8fd6a5faa94744d7a1e9bf8f1b205a47e9cab39e23ad8a27cc2d6`; hash máy của`node_info.json` được lưu trong`node_fetch.json`. Snapshot được giữ để tránh coi nội dung endpoint hiện tại là dữ liệu bất biến.
