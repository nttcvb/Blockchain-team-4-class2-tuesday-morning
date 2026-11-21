# TEST_INFRA.md — E2E Testing Infrastructure Specification

## 1. Test Philosophy

The E2E Testing Track for the Terra Luna - UST Bailout Redesign & Evaluation project establishes an independent, opaque-box, requirement-driven verification harness.

### Key Principles
- **Opaque-Box Verification**: Tests interact strictly through public interfaces (`PolicyConfig`, `ScenarioConfig`, `simulate()`, `evaluate()`, `experiments`, `cli`), invariant checks, and serialized output artifacts (`trajectory.parquet`, `metrics.json`, `summary.csv`). Tests do not couple to private simulation internals, arbitrary variable naming, or specific optimizer loops.
- **Requirement-Driven Traceability**: Every test case directly traces back to:
  - **R1 (Bailout Policy Design & Implementation)**: Finite capital constraints, withdrawal gates, liquidity provision, concentrated peg defense, burn mechanisms, and emergency throttles.
  - **R2 (Stress Simulation Execution)**: Multi-day crisis stress testing (May 2022 collapse + mandatory 7-day post-crisis tail verification) testing individual and combined interventions.
  - **R3 (Mechanism Analysis & Evaluation)**: Clear classification of whether the peg can be sustained in $[0.98, 1.02]$ USD without reserve exhaustion and LUNA hyperinflation, supported by empirical metrics and dashboard visualizations.
  - **F01–F15 (Feature Inventory)**: Rigorous mapping to all features in `PROJECT.md`.
- **Conservation & Invariant Integrity**: Zero tolerance for unbacked monetary generation. Invariants verify:
  - UST supply conservation ($\Delta \text{ust\_supply} = -\text{burn} \implies \text{ust\_error} = 0$).
  - LUNA supply conservation ($\Delta \text{luna\_supply} = \text{gross\_mint} \implies \text{luna\_error} = 0$).
  - USD balance sheet conservation ($\text{market\_usd} + \text{fund\_usd} + \dots = \text{initial} + \text{released} \implies \text{usd\_error} = 0$).
  - Anchor claim parity ($\text{anchor\_cash} + \text{loan\_balance} = \text{claims} \implies \text{claim\_error} = 0$).
  - Finite Capital Limits: LFG spendable BTC $\le 80,081$ BTC ($\ge 313$ retained of $80,394$ total); TFL net contribution $\le \$613,616,889$; total finite external bailout budget ceiling $\approx \$3.0\text{B} - \$3.5\text{B}$ USD.
- **Authoritative Expected Output Derivation**:
  - Formulas for invariant tolerances ($< 10^{-6}$ relative error).
  - Prescribed operational bounds ($[0.98, 1.02]$ USD peg range, 48 hours minimum sustained stability).
  - Explicit finite budget caps from verified historical records (`sources.json`).
- **Progressive Testability**:
  - Tests verify interface contracts, schema validation, budget enforcement invariants, finite capital limits, trajectory schemas, metric calculation formulas, and CLI runners.
  - As implementation milestones progress (M1 policy hooks, M2 scenario runner, M3 analytical reports), tests adaptively verify capabilities and validate interface compliance without regression of existing test suites.

---

## 2. Methodology

The test suite employs four complementary software testing methodologies:

### A. Category-Partition Method
The input domain is partitioned into disjoint equivalence classes:
1. **Policy Action Types**:
   - `buy_ust`: Secondary market UST purchase / bid-wall defense.
   - `liquidity`: Virtual / AMM liquidity injection.
   - `native_swap`: Protocol mint/burn parameters adjustment (pool multiplier, recovery rate, spread fee).
   - `withdrawal_gate`: Anchor withdrawal throttling / haircut penalties.
2. **Trigger Modes**:
   - `price`: Triggered when UST price breaks below threshold (e.g., $0.99, 0.98, 0.95$).
   - `time`: Scheduled calendar execution (UTC timestamp).
3. **Funder Allocations**:
   - `LFG`: Consumes BTC and stable reserves.
   - `TFL`: Consumes TFL treasury cash within legal cap.
   - `both`: Shared joint disbursement pool.
4. **Market Regimes**:
   - Normal ($P \ge 0.98$), Mild depeg ($0.95 \le P < 0.98$), Severe depeg ($0.80 \le P < 0.95$), Death Spiral ($P < 0.80$).

### B. Boundary Value Analysis (BVA)
Tests probe exact limit surfaces:
- **Capital Boundaries**:
  - Spend $= 0$ USD (no intervention baseline).
  - Spend exactly at tranche boundaries ($50\text{M}, 100\text{M}, 500\text{M}$).
  - Spend at hard legal cap: LFG BTC $= 80,081$ BTC; TFL contribution $= \$613,616,889.00$; Retained BTC $= 313$ BTC.
  - Excess spend attempt ($> \text{budget}$) $\to$ Must trigger hard stop or clamp.
- **Price Corridor Boundaries**:
  - Peg thresholds: $0.979, 0.980, 1.000, 1.020, 1.021$ USD.
- **Withdrawal Fraction Boundaries**:
  - Allowance fraction: $0.00$ (complete freeze), $0.05$ (5% emergency gate), $0.15$ (15% tiered gate), $0.20$ (default limit), $1.00$ (unrestricted).
- **Spread & Haircut Boundaries**:
  - `emergency_spread_rate`: $0.00, 0.10, 0.25$.
  - `redemption_haircut`: $0.00, 0.10, 0.30$.
- **Temporal Boundaries**:
  - Crisis duration ($10$ days: 2022-05-06T00:15Z to 2022-05-16T00:00Z).
  - Stress tail: $0$ days vs. mandatory $7$ days post-crisis.

### C. Pairwise Combinations
Combinatorial testing across orthogonal policy dimensions:
- Bid-wall buyback (`buy_ust`) + Immediate supply burn (`burn_acquired_ust = True`).
- Dynamic tiered gates (`tiered_gates = True`) + Emergency redemption haircut (`redemption_haircut = 0.20`).
- Spread hike (`emergency_spread_rate = 0.15`) + Arbitrage throttling (`arb_capacity_multiplier = 0.50`).
- Circuit breaker (`circuit_breaker_threshold = 0.80`) + Stop-loss ceiling (`max_cumulative_spend = 1e9`).
- Combined multi-tranche realistic intervention (`sc07_combined_realistic`).

### D. Real-World Workload Scenarios
Simulations subject the model to empirical historical stress:
- Anchor depeg bank run initiated by whale exit shocks.
- Arbitrageur liquidity exhaustion on secondary curve pools.
- Algorithmic death spiral dynamics with hyperinflating LUNA token supply.
- 7-day post-crisis stress tail ($168$ hours) testing sustained peg stability without continued intervention injections.

---

## 3. Coverage Thresholds

The test suite enforces a 4-tier hierarchical test structure:

| Tier | Focus | Requirement Threshold |
|---|---|---|
| **Tier 1** | **Feature Coverage** | $\ge 5$ explicit tests per feature for F01 through F14 ($\ge 70$ tests total) |
| **Tier 2** | **Boundary & Corner Cases** | $\ge 5$ boundary/corner tests per feature for F01 through F14 ($\ge 70$ tests total) |
| **Tier 3** | **Cross-Feature Combinations** | $\ge 15$ multi-feature interaction and compound intervention tests |
| **Tier 4** | **Real-World Application Scenarios** | $\ge 10$ full-scale stress tests, multi-seed simulations, CLI invocations, and artifact evaluations |

### Summary of Targets:
- **Total Test Cases**: $\ge 165$ tests in `tests/test_e2e_interventions.py`.
- **Existing Suite**: $147$ tests in `tests/` must maintain 100% pass status (F15).

---

## 4. Test Runner Command & Pass/Fail Semantics

### Test Commands
1. **Run E2E Interventions Suite**:
   ```bash
   pytest tests/test_e2e_interventions.py -v
   ```
2. **Run Full Regression & E2E Suite**:
   ```bash
   pytest tests/ -v
   ```

### Pass/Fail Semantics
- **PASS (Exit Code 0)**:
  - All assertions succeed.
  - Zero invariant violations (no unbacked monetary printing, no budget overspend).
  - Zero unhandled exceptions.
  - Progressive testability gracefully skips or passes pending milestone features based on contract introspection.
- **FAIL (Exit Code $\ne 0$)**:
  - Any assertion error, invariant deviation exceeding tolerance ($10^{-6}$), or unhandled crash.
  - Any regression in the existing 147 test cases.
