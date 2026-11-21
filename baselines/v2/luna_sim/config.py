from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import os
import math

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(os.environ.get('LUNA_SOURCE_DIR', str(ROOT.parent / "terra-luna-run-replication (1)" / "terra-luna-run-replication")))


@dataclass
class ModelParams:
    # All monetary stocks use whole tokens / dollars, never microtokens.
    hazard_base: float = -11.0
    hazard_size: float = 0.20
    hazard_discount: float = 12.0
    hazard_outflow: float = 18.0
    hazard_luna: float = 2.0
    hazard_queue: float = 3.0
    sell_fraction: float = 0.92
    ust_depth_usd: float = 30e9
    ust_depth_luna_beta: float = 1.0
    ust_confidence_beta: float = 0.18
    luna_depth_usd: float = 2.0e9
    luna_depth_growth: float = 0.80
    luna_beta_btc: float = 1.3
    luna_residual_bid_fraction: float = 0.08
    arb_capacity_day: float = 300e6
    arb_capital_usd: float = 150e6
    base_pool_usd: float = 50e6
    recovery_minutes: float = 3.6
    min_spread: float = 0.005
    market_cash_usd: float = 25e9
    external_ust_inventory: float = 4e9
    market_luna_inventory: float = 100e6
    normal_demand_day: float = 25e6
    redeposit_day: float = 0.015
    oracle_lag_minutes: int = 1
    btc_slippage: float = 0.003
    btc_fee: float = 0.001
    execution_fee: float = 0.001
    reserve_income_day: float = 2.0e6
    loan_repayment_days: float = 2.0
    seed_shock_sell_fraction: float = 0.95


@dataclass
class PolicyConfig:
    action: str
    trigger: str = "price"
    threshold: float = 0.99
    trigger_steps: int = 2
    start_time: str = "2022-05-08T00:00:00Z"
    delay_minutes: int = 60
    duration_hours: float = 72
    max_spend_per_hour: float = 50e6
    allocation_fraction: float = 1.0
    pool_multiplier: float = 2.0
    recovery_multiplier: float = 0.5
    withdrawal_fraction_per_day: float = 0.20
    funder: str = "both"

    def validate(self):
        import pandas as pd
        for key in ['threshold','delay_minutes','duration_hours','max_spend_per_hour','allocation_fraction','pool_multiplier','recovery_multiplier','withdrawal_fraction_per_day']:
            if not math.isfinite(getattr(self,key)): raise ValueError(f'Non-finite policy parameter: {key}')
        if not isinstance(self.trigger_steps,int) or isinstance(self.trigger_steps,bool) or self.trigger_steps<1:
            raise ValueError('trigger_steps must be a positive integer')
        if self.action not in {"buy_ust", "liquidity", "native_swap", "withdrawal_gate"}:
            raise ValueError("Unknown policy action")
        if self.trigger not in {"price", "time"} or self.funder not in {"both", "LFG", "TFL"}:
            raise ValueError("Invalid trigger or funder")
        if not 0 < self.threshold <= 1 or not 0 <= self.allocation_fraction <= 1:
            raise ValueError("Threshold/allocation out of range")
        if min(self.delay_minutes, self.duration_hours, self.max_spend_per_hour) < 0:
            raise ValueError("Negative policy limit")
        if not 0 < self.pool_multiplier <= 20 or not 0 < self.recovery_multiplier <= 10:
            raise ValueError("Invalid virtual pool parameters")
        if not 0 <= self.withdrawal_fraction_per_day <= 1:
            raise ValueError("Invalid withdrawal limit")
        if pd.Timestamp(self.start_time).tzinfo is None:
            raise ValueError('Policy start_time must specify UTC, e.g. 2022-05-08T00:00:00Z')


@dataclass
class ScenarioConfig:
    name: str = "historical"
    mode: str = "historical"
    start: str = "2022-05-06T00:15:00Z"
    end: str = "2022-05-16T00:00:00Z"
    dt_minutes: int = 15
    n_depositors: int = 1000
    n_arbitrageurs: int = 20
    seed: int = 42
    stochastic: bool = True
    funding_timing: str = "late"
    stress_days: int = 0
    params: ModelParams = field(default_factory=ModelParams)
    policies: list[PolicyConfig] = field(default_factory=list)

    def validate(self):
        import pandas as pd
        if self.mode not in {"historical", "counterfactual", "no_rescue"}:
            raise ValueError("Unknown scenario mode")
        if self.dt_minutes not in {5, 15} or self.n_depositors < 40 or self.n_arbitrageurs < 1:
            raise ValueError("Unsupported timestep / population")
        if self.funding_timing not in {"early", "late"} or not 0 <= self.stress_days <= 14:
            raise ValueError("Invalid funding timing / stress horizon")
        if pd.Timestamp(self.end) <= pd.Timestamp(self.start):
            raise ValueError("End must follow start")
        if pd.Timestamp(self.start).tzinfo is None or pd.Timestamp(self.end).tzinfo is None:
            raise ValueError('Scenario timestamps must include timezone')
        if pd.Timestamp(self.start)<pd.Timestamp('2022-05-06T00:15:00Z') or pd.Timestamp(self.end)>pd.Timestamp('2022-05-16T00:00:00Z'):
            raise ValueError('Historical window is May 6 00:15 to May 16 00:00 UTC; extend with stress_days')
        if self.seed<0: raise ValueError('Seed must be nonnegative')
        for key,value in asdict(self.params).items():
            if not math.isfinite(value): raise ValueError(f'Non-finite model parameter: {key}')
        for key in ['ust_depth_usd','luna_depth_usd','arb_capacity_day','arb_capital_usd','base_pool_usd','recovery_minutes','market_cash_usd','loan_repayment_days']:
            if getattr(self.params,key)<=0: raise ValueError(f'{key} must be positive')
        for key in ['min_spread','execution_fee','btc_slippage','btc_fee','luna_residual_bid_fraction']:
            if not 0<=getattr(self.params,key)<1: raise ValueError(f'Invalid fraction: {key}')
        if self.params.btc_slippage+self.params.btc_fee>=1: raise ValueError('BTC costs must be below 100%')
        for policy in self.policies:
            policy.validate()
            if policy.trigger == "time" and pd.Timestamp(policy.start_time) < pd.Timestamp("2022-05-07T00:00:00Z"):
                raise ValueError("Intervention must follow the beginning of the event")

    def to_dict(self):
        return asdict(self)

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, data):
        values = dict(data)
        values["params"] = ModelParams(**values.get("params", {}))
        values["policies"] = [PolicyConfig(**p) for p in values.get("policies", [])]
        obj = cls(**values)
        obj.validate()
        return obj


def load_params(path=None):
    default=ROOT / "outputs" / "calibration" / "parameters_full_fit.json"
    if not default.exists(): default=ROOT / "outputs" / "calibration" / "parameters.json"
    path = Path(path or default)
    return ModelParams(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else ModelParams()
