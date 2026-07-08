from __future__ import annotations

from dataclasses import dataclass

from .models import CapitalControls, DeploymentStage, GateResult, GateSeverity, GateStatus, RolloutDecision
from .rollout import default_rollout_plan


@dataclass(frozen=True)
class CapitalApproval:
    decision: RolloutDecision
    approved_allocation_usd: float
    max_allocation_usd: float
    gates: list[GateResult]


class CapitalAllocationController:
    """Enforce capital, leverage, and staged rollout allocation limits."""

    def __init__(self, plan=None) -> None:
        self.plan = plan or default_rollout_plan()

    def evaluate(self, stage: DeploymentStage, controls: CapitalControls) -> CapitalApproval:
        stage_spec = self.plan.get_stage(stage)
        stage_cap_usd = controls.account_equity_usd * min(
            controls.max_allocation_pct, stage_spec.max_allocation_pct
        )
        approved = min(controls.requested_allocation_usd, stage_cap_usd)
        gates: list[GateResult] = []

        if controls.requested_allocation_usd > stage_cap_usd:
            gates.append(
                GateResult(
                    name="capital_allocation_cap",
                    status=GateStatus.WARN,
                    severity=GateSeverity.WARNING,
                    message="Requested allocation exceeds stage cap and was reduced.",
                    evidence={
                        "requested_usd": controls.requested_allocation_usd,
                        "stage_cap_usd": stage_cap_usd,
                        "approved_usd": approved,
                    },
                )
            )
        else:
            gates.append(
                GateResult(
                    name="capital_allocation_cap",
                    status=GateStatus.PASS,
                    severity=GateSeverity.INFO,
                    message="Requested allocation is within stage cap.",
                    evidence={"approved_usd": approved, "stage_cap_usd": stage_cap_usd},
                )
            )

        if controls.max_effective_leverage > stage_spec.max_effective_leverage:
            gates.append(
                GateResult(
                    name="stage_leverage_cap",
                    status=GateStatus.FAIL,
                    severity=GateSeverity.BLOCKING,
                    message="Configured leverage exceeds current rollout-stage cap.",
                    evidence={
                        "configured_leverage": controls.max_effective_leverage,
                        "stage_max_leverage": stage_spec.max_effective_leverage,
                    },
                )
            )
            return CapitalApproval(RolloutDecision.HOLD, 0.0, stage_cap_usd, gates)

        gates.append(
            GateResult(
                name="stage_leverage_cap",
                status=GateStatus.PASS,
                severity=GateSeverity.INFO,
                message="Leverage is within rollout-stage cap.",
                evidence={"configured_leverage": controls.max_effective_leverage},
            )
        )

        decision = RolloutDecision.APPROVE if not any(g.is_blocking_failure for g in gates) else RolloutDecision.HOLD
        if decision == RolloutDecision.APPROVE and any(g.status == GateStatus.WARN for g in gates):
            decision = RolloutDecision.APPROVE_WITH_LIMITS
        return CapitalApproval(decision, approved, stage_cap_usd, gates)
