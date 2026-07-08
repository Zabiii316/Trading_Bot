from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DeploymentStage(str, Enum):
    LOCAL = "local"
    TESTNET_SHADOW = "testnet_shadow"
    TESTNET_PAPER = "testnet_paper"
    TESTNET_EXECUTION = "testnet_execution"
    MICRO_LIVE = "micro_live"
    PILOT_LIVE = "pilot_live"
    CONTROLLED_LIVE = "controlled_live"
    FULL_LIVE = "full_live"


class GateStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class GateSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class RolloutDecision(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_LIMITS = "approve_with_limits"
    HOLD = "hold"
    ROLLBACK = "rollback"
    EMERGENCY_HALT = "emergency_halt"


class CapitalControls(StrictModel):
    account_equity_usd: float = Field(..., gt=0)
    requested_allocation_usd: float = Field(..., ge=0)
    max_allocation_pct: float = Field(default=0.10, gt=0, le=1)
    max_daily_loss_pct: float = Field(default=0.015, gt=0, le=1)
    max_weekly_loss_pct: float = Field(default=0.04, gt=0, le=1)
    max_portfolio_drawdown_pct: float = Field(default=0.08, gt=0, le=1)
    max_effective_leverage: float = Field(default=2.0, gt=0)
    max_symbol_exposure_pct: float = Field(default=0.30, gt=0, le=1)
    max_strategy_exposure_pct: float = Field(default=0.40, gt=0, le=1)
    max_correlated_cluster_pct: float = Field(default=0.35, gt=0, le=1)
    per_trade_risk_pct: float = Field(default=0.0025, gt=0, le=0.02)

    @model_validator(mode="after")
    def validate_requested_allocation(self) -> "CapitalControls":
        if self.requested_allocation_usd > self.account_equity_usd:
            raise ValueError("requested_allocation_usd cannot exceed account_equity_usd")
        return self

    @property
    def max_allocation_usd(self) -> float:
        return self.account_equity_usd * self.max_allocation_pct

    @property
    def approved_allocation_usd(self) -> float:
        return min(self.requested_allocation_usd, self.max_allocation_usd)


class StageSpec(StrictModel):
    stage: DeploymentStage
    duration_hours: int = Field(..., ge=0)
    max_allocation_pct: float = Field(..., ge=0, le=1)
    max_effective_leverage: float = Field(..., gt=0)
    required_paper_trades: int = Field(default=0, ge=0)
    required_testnet_orders: int = Field(default=0, ge=0)
    requires_manual_approval: bool = True
    description: str = Field(default="")


class RolloutPlan(StrictModel):
    stages: list[StageSpec]

    @model_validator(mode="after")
    def validate_stage_order(self) -> "RolloutPlan":
        seen: set[DeploymentStage] = set()
        previous_allocation = -1.0
        for spec in self.stages:
            if spec.stage in seen:
                raise ValueError(f"duplicate rollout stage: {spec.stage}")
            seen.add(spec.stage)
            if spec.max_allocation_pct < previous_allocation:
                raise ValueError("stage allocation percentages must be non-decreasing")
            previous_allocation = spec.max_allocation_pct
        return self

    def get_stage(self, stage: DeploymentStage) -> StageSpec:
        for spec in self.stages:
            if spec.stage == stage:
                return spec
        raise KeyError(stage)


class EmergencyDrillResult(StrictModel):
    name: str
    completed: bool
    latency_ms: int | None = Field(default=None, ge=0)
    evidence_ref: str | None = None
    notes: str | None = None


class OperationalSnapshot(StrictModel):
    stage: DeploymentStage
    commit_sha: str = Field(..., min_length=7)
    image_tag: str = Field(..., min_length=1)
    tests_passed: bool
    test_count: int = Field(..., ge=0)
    paper_trades: int = Field(default=0, ge=0)
    testnet_orders: int = Field(default=0, ge=0)
    paper_profit_factor: float | None = Field(default=None, ge=0)
    paper_max_drawdown_pct: float | None = Field(default=None, ge=0)
    backtest_profit_factor: float | None = Field(default=None, ge=0)
    backtest_max_drawdown_pct: float | None = Field(default=None, ge=0)
    risk_engine_healthy: bool
    monitoring_healthy: bool
    reconciliation_healthy: bool
    order_book_sequence_healthy: bool
    kill_switch_tested: bool
    emergency_drills: list[EmergencyDrillResult] = Field(default_factory=list)
    live_trading_enabled: bool = False
    withdrawal_permissions_disabled: bool = True
    secrets_loaded_from_manager: bool = True
    manual_approval: bool = False
    open_critical_alerts: int = Field(default=0, ge=0)
    stale_component_count: int = Field(default=0, ge=0)
    current_daily_loss_pct: float = Field(default=0.0, ge=0)
    current_weekly_loss_pct: float = Field(default=0.0, ge=0)
    current_drawdown_pct: float = Field(default=0.0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GateResult(StrictModel):
    name: str
    status: GateStatus
    severity: GateSeverity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_blocking_failure(self) -> bool:
        return self.status == GateStatus.FAIL and self.severity == GateSeverity.BLOCKING


class ProductionReadinessReport(StrictModel):
    stage: DeploymentStage
    decision: RolloutDecision
    approved_allocation_usd: float
    max_allocation_usd: float
    gates: list[GateResult]
    required_manual_approval: bool
    summary: str

    @property
    def blocking_failures(self) -> list[GateResult]:
        return [gate for gate in self.gates if gate.is_blocking_failure]

    @property
    def warnings(self) -> list[GateResult]:
        return [gate for gate in self.gates if gate.status == GateStatus.WARN]
