# Project: Terra Luna - UST Simulation Bailout Redesign & Evaluation

## Architecture
The `luna-ust-sim` codebase is a hybrid Agent-Based Model (ABM) and System Dynamics engine for the Terra Classic / Anchor ecosystem during the May 2022 collapse.
- **Engine**: Dual cadCAD and Fast Python runner executing 6 Partial State Update Blocks (PSUBs) in fixed order:
  `observation` → `rescue` → `decisions` → `anchor` → `markets` → `accounting`
- **State Space**: Central `book` dictionary tracking ~50 monetary and protocol balances, 1,000 stratified depositor agents, and 20 VWAP arbitrageurs.
- **Conservation Invariants**: Verified every timestep in `invariants()`. Strictly conserves UST supply, LUNA supply, USD liquidity, Anchor claims, and BTC inventory (80,394 total, max 80,081 spendable, >=313 retained).
- **Finite Capital Ceiling**: LFG spendable BTC (80,081 BTC ≈ $2.4B-$2.8B) + LFG USD stables ($49.8M) + TFL net contribution cap ($613.6M) yields a hard finite external capital constraint of **~$3.0B - $3.5B USD**. No infinite funds assumed.

## Feature Inventory
Every feature identified during Survey is assigned to an implementation milestone.
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F01 | Finite Budget & Cap Invariant | Strict budget limits enforcing LFG/TFL caps (max 80,081 BTC, $613.6M TFL, ~$3.5B total) with invariant conservation | M1 | R1, Survey |
| F02 | Buyback & Immediate Supply Burn | `burn_acquired_ust = True` burning bought UST from `ust_supply` and `fund_ust` simultaneously without accounting error | M1 | R1, Survey |
| F03 | Concentrated Bid-Wall Support | Concentrated buy orders at `target_peg` (e.g. 0.985) providing targeted depth rather than chasing market slippage | M1 | R1, Survey |
| F04 | Staggered Tranches & Stop-Loss Waterfall | Phased deployment (stables first, BTC tranches next) and stop-loss cutoff preventing 100% reserve loss if insolvency is irreversible | M1 | R1, Survey |
| F05 | Tiered Anchor Withdrawal Gates | Dynamic gates throttling withdrawal allowance (100% -> 15% -> 5%/day) based on depeg severity | M1 | R1, Survey |
| F06 | Whale-Specific Throttling & Queue Delays | Absolute per-wallet daily withdrawal limits and unbonding cooldown queues to prevent sudden whale runs | M1 | R1, Survey |
| F07 | Emergency Redemption Haircut | Penalty haircut (10%-30%) on panic withdrawals, immediately burned from total UST liabilities | M1 | R1, Survey |
| F08 | Emergency Native Spread Hike | Progressive spread hike (`emergency_spread_rate` 10%-25%) during depeg to neutralize arbitrageur minting incentive | M1 | R1, Survey |
| F09 | Daily Arbitrage Capacity Throttling | Scaling down `arb_capacity_day` during crisis to choke off secondary market dumping and LUNA dilution | M1 | R1, Survey |
| F10 | Emergency Circuit Breaker | `circuit_breaker_threshold` halting Anchor and/or Native swaps during extreme shocks to stabilize market | M1 | R1, Survey |
| F11 | 7-Day Stress Simulation Matrix | Scenario runner for SC-01 (no rescue baseline) through SC-10 (combined realistic & extreme) across 10-day crisis + 7-day stress tail | M2 | R2, Survey |
| F12 | Trajectory & Metrics Pipeline | Collection and validation of step trajectories and `metrics.json` assessing [0.98, 1.02] peg, Anchor liquidity, LUNA hyperinflation | M2 | R2, Survey |
| F13 | Quantitative Mechanism Analysis Report | In-depth failure/success report in `outputs/` proving with empirical data whether finite capital can restore the peg and why | M3 | R3, Acceptance Criteria |
| F14 | Dashboard Visualization Modernization | Modernizing Streamlit `app.py` to compare Baseline vs Intervention trajectories with shaded [0.98, 1.02] peg corridors and liquidity charts | M3 | R3, Survey |
| F15 | Regression Test Compatibility | Maintaining full pass status of all existing 147 test cases in `pytest tests/` | M1, M2, M3 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Independent opaque-box test infra & 4-tier test suite (Tiers 1-4) creating `TEST_READY.md` | none | DONE |
| M1 | Policy Extensions & Engine Hooks | Extend `PolicyConfig`, implement F01-F10 in `config.py` and `engine.py`, ensure invariant conservation | none | DONE |
| M2 | Stress Test Matrix & Experiment Runner | Implement SC-01 to SC-10 presets in `experiments.py` & `cli.py`, run multi-seed simulations, produce trajectories | M1 | DONE |
| M3 | Quantitative Report & Dashboard Modernization | Generate detailed evaluation report in `outputs/` and modernize `app.py` dashboard for comparative visualization | M2 | DONE |
| M4 | Final Milestone: 100% E2E Pass & Tier 5 Hardening | Pass 100% of E2E tests (Tiers 1-4), then adversarial coverage hardening (Tier 5) with Challenger | E2E, M3 | IN_PROGRESS |

## Interface Contracts

### `luna_sim.config` ↔ `luna_sim.engine`
- `PolicyConfig` extension attributes:
  - `target_peg: float = 1.001` (target price threshold for concentrated bid-wall)
  - `burn_acquired_ust: bool = False` (burn acquired UST from supply immediately)
  - `emergency_spread_rate: float = 0.0` (additional spread fee applied to native swaps)
  - `arb_capacity_multiplier: float = 1.0` (multiplier on daily arb capacity)
  - `redemption_haircut: float = 0.0` (haircut deducted and burned on early withdrawals)
  - `circuit_breaker_threshold: float = 0.0` (price below which module actions halt)
  - `max_cumulative_spend: float = math.inf` (stop-loss maximum total spend)
  - `tiered_gates: bool = False` (enable tiered withdrawal gate based on UST price)
- Invariant equation:
  $$\Delta \text{ust\_supply} = -\text{qty\_burned} \iff \Delta (\text{fund\_ust} + \text{anchor\_cash} + \dots) = -\text{qty\_burned}$$
  $$\implies \text{ust\_error} = 0$$

### `luna_sim.experiments` ↔ `luna_sim.metrics` / `outputs`
- Scenarios SC-01 to SC-10 configured in `experiments.py`:
  - `name`: string identifier (`sc01_baseline_no_rescue`, `sc02_staggered_tranches`, `sc03_concentrated_bidwall`, `sc04_buyback_burn`, `sc05_tiered_gates`, `sc06_market_defense`, `sc07_combined_realistic`, `sc08_frontloaded_shock`, `sc09_circuit_breaker`, `sc10_maximum_extreme`)
  - `stress_days`: int = 7 (mandatory post-crisis tail)
  - `stochastic`: bool (runs across seeds 42..46)
- Output format:
  - `outputs/runs/<scenario>_seed<seed>/metrics.json`
  - `outputs/runs/<scenario>_seed<seed>/trajectory.parquet`
  - `outputs/experiments/summary.csv`
  - Required fields in `metrics.json`: `peg_hours_longest`, `operational_hours_longest`, `stress_tail_verified`, `final_ust_price`, `final_anchor_deposits`, `final_luna_supply`, `rescued`, `total_spent_usd`

### `app.py` ↔ `outputs/` / `luna_sim`
- `app.py` loads both cached simulation runs and supports on-demand comparison between Baseline (`no_rescue`), Historical (`historical`), and New Interventions (`sc07_combined_realistic`, `sc10_maximum_extreme`).
- Visualizations:
  - UST Price trajectory with shaded green corridor $[0.98, 1.02]$ USD
  - Anchor Cash and Deposit Claims trajectory
  - LUNA Price and Supply Inflation trajectory
  - Total Intervention Budget Spent vs Remaining

## Code Layout
- `d:\New folder\luna-ust-sim\`
  - `luna_sim/`
    - `config.py`: Configuration dataclasses (`PolicyConfig`, `ScenarioConfig`, `ModelParams`)
    - `engine.py`: Simulation state loop, PSUB blocks, invariant assertions, market dynamics
    - `experiments.py`: Scenario registry and runner
    - `metrics.py`: Metric collection and evaluation functions
    - `cli.py`: Command line interface
  - `tests/`: Existing pytest test suite
  - `app.py`: Streamlit interactive dashboard
  - `outputs/`: Output directory for trajectories, summaries, and analytical reports
