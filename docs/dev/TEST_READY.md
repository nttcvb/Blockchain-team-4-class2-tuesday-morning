# TEST_READY.md — E2E Testing Track Verification & Readiness

## 1. Test Runner Command

To run the comprehensive E2E Interventions Test Suite:
```bash
# From repository directory (d:\New folder\luna-ust-sim):
pytest tests/test_e2e_interventions.py -v

# From project root (d:\New folder):
pytest luna-ust-sim/tests/test_e2e_interventions.py -v
```

To run the complete test suite (regression + E2E):
```bash
# From repository directory (d:\New folder\luna-ust-sim):
pytest tests/ -v
```

---

## 2. Coverage Summary Table

| Test Tier | Focus & Scope | Target | Actual Tests | Pass Count | Pass Rate | Status |
|---|---|---|---|---|---|---|
| **Tier 1** | **Feature Coverage** (F01–F14, $\ge 5$ tests each) | $\ge 70$ | 70 | 70 | 100% | **PASSED** |
| **Tier 2** | **Boundary & Corner Cases** (F01–F14, $\ge 5$ tests each) | $\ge 70$ | 70 | 70 | 100% | **PASSED** |
| **Tier 3** | **Cross-Feature Combinations** (Multi-policy interactions) | $\ge 15$ | 15 | 15 | 100% | **PASSED** |
| **Tier 4** | **Real-World Application Scenarios** (Stress matrix & CLI) | $\ge 10$ | 13 | 13 | 100% | **PASSED** |
| **TOTAL** | **Comprehensive E2E Suite** | $\ge 165$ | **168** | **168** | **100%** | **READY** |

Execution performance: **168 passed in 3.46 seconds**.

---

## 3. Feature Checklist (PROJECT.md § Feature Inventory)

| # | Feature | Description | E2E Coverage | Verification Method | Status |
|---|---------|-------------|--------------|---------------------|--------|
| **F01** | Finite Budget & Cap Invariant | Strict budget limits enforcing LFG/TFL caps (max 80,081 BTC, $613.6M TFL, ~$3.5B total) with invariant conservation | 10 tests (T1-1..5, T2-1..5) + T3 | Invariant equation checks, double-entry conservation, cap enforcement | **COVERED (100% Pass)** |
| **F02** | Buyback & Immediate Supply Burn | `burn_acquired_ust = True` burning bought UST from `ust_supply` and `fund_ust` simultaneously without accounting error | 10 tests (T1-6..10, T2-6..10) + T3 | Delta conservation equation $\Delta \text{supply} = -\text{burn} \implies \text{error}=0$ | **COVERED (100% Pass)** |
| **F03** | Concentrated Bid-Wall Support | Concentrated buy orders at `target_peg` (e.g. 0.985, 1.001) providing targeted depth rather than chasing market slippage | 10 tests (T1-11..15, T2-11..15) + T3 | Order sizing formula, slippage protection, peg threshold validation | **COVERED (100% Pass)** |
| **F04** | Staggered Tranches & Stop-Loss Waterfall | Phased deployment (stables first, BTC tranches next) and stop-loss cutoff preventing 100% reserve loss if insolvency is irreversible | 10 tests (T1-16..20, T2-16..20) + T3 | Deployment sequence, `max_cumulative_spend` enforcement, reserve preservation | **COVERED (100% Pass)** |
| **F05** | Tiered Anchor Withdrawal Gates | Dynamic gates throttling withdrawal allowance (100% -> 15% -> 5%/day) based on depeg severity | 10 tests (T1-21..25, T2-21..25) + T3 | Regime transitions (0.98, 0.95), daily fraction bounding, outflow limit | **COVERED (100% Pass)** |
| **F06** | Whale-Specific Throttling & Queue Delays | Absolute per-wallet daily withdrawal limits and unbonding cooldown queues to prevent sudden whale runs | 10 tests (T1-26..30, T2-26..30) + T3 | Single wallet daily limit, queue deferral, cash drain prevention | **COVERED (100% Pass)** |
| **F07** | Emergency Redemption Haircut | Penalty haircut (10%-30%) on panic withdrawals, immediately burned from total UST liabilities | 10 tests (T1-31..35, T2-31..35) + T3 | Haircut rate validation, burn accounting, claims vs payout delta check | **COVERED (100% Pass)** |
| **F08** | Emergency Native Spread Hike | Progressive spread hike (`emergency_spread_rate` 10%-25%) during depeg to neutralize arbitrageur minting incentive | 10 tests (T1-36..40, T2-36..40) + T3 | `native_quote()` fee integration, profit dampening, fee accumulation | **COVERED (100% Pass)** |
| **F09** | Daily Arbitrage Capacity Throttling | Scaling down `arb_capacity_day` during crisis to choke off secondary market dumping and LUNA dilution | 10 tests (T1-41..45, T2-41..45) + T3 | Proportional scaling, LUNA dilution suppression, daily quota enforcement | **COVERED (100% Pass)** |
| **F10** | Emergency Circuit Breaker | `circuit_breaker_threshold` halting Anchor and/or Native swaps during extreme shocks to stabilize market | 10 tests (T1-46..50, T2-46..50) + T3 | Trigger condition (`price < threshold`), module halt flags, invariant preservation | **COVERED (100% Pass)** |
| **F11** | 7-Day Stress Simulation Matrix | Scenario runner for SC-01 (no rescue baseline) through SC-10 (combined realistic & extreme) across 10-day crisis + 7-day stress tail | 10 tests (T1-51..55, T2-51..55) + T4 | Scenario presets validation, multi-seed variation, 17-day horizon validation | **COVERED (100% Pass)** |
| **F12** | Trajectory & Metrics Pipeline | Collection and validation of step trajectories and `metrics.json` assessing [0.98, 1.02] peg, Anchor liquidity, LUNA hyperinflation | 10 tests (T1-56..60, T2-56..60) + T4 | Trajectory schema validation, required fields in metrics, peg streak evaluation | **COVERED (100% Pass)** |
| **F13** | Quantitative Mechanism Analysis Report | In-depth failure/success report in `outputs/` proving with empirical data whether finite capital can restore the peg and why | 10 tests (T1-61..65, T2-61..65) + T4 | Directory structure verification, deficit proof ($3.5B vs $12B+), provenance checks | **COVERED (100% Pass)** |
| **F14** | Dashboard Visualization Modernization | Modernizing Streamlit `app.py` to compare Baseline vs Intervention trajectories with shaded [0.98, 1.02] peg corridors and liquidity charts | 10 tests (T1-66..70, T2-66..70) | Dashboard loadability, corridor bounds [0.98, 1.02], scenario comparison pairing | **COVERED (100% Pass)** |
| **F15** | Regression Test Compatibility | Maintaining full pass status of existing 147 test cases in `pytest tests/` | Existing suite (147 items) | 146 passed; 1 pre-existing calibration provenance mismatch identified & escalated | **VERIFIED (Escalated)** |

---

## 4. Discovered Implementation Defects (Escalated)

1. **Calibration Source Provenance Divergence (`outputs/calibration/calibration_status_all.json`)**:
   - **File Affected**: `luna-ust-sim/app.py` lines 88-94, `outputs/calibration/calibration_status_all.json`
   - **Symptom**: `app.py` displays error banner *"Kết quả đã lưu chưa được xác nhận cho mã, dữ liệu và bộ tham số hiện tại. Không thể trình bày bản này như kết quả đã kiểm chứng."* because `engine.py` and `config.py` SHA256 hashes differ from the recorded hashes in `report_all.json`.
   - **Impact**: In `tests/test_dashboard.py`, `test_dashboard_defaults_to_history_and_legacy_policy_opt_in_produces_result` encounters empty tabs because the app halts on unverified calibration provenance.
   - **Recommended Action**: Implementing agent for M3 (`app.py` modernization) should regenerate calibration artifacts or update the provenance checksum manifest once engine policy hooks are implemented.
