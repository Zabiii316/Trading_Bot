from __future__ import annotations

from .capital import CapitalAllocationController
from .models import (
    CapitalControls,
    DeploymentStage,
    GateResult,
    GateSeverity,
    GateStatus,
    OperationalSnapshot,
    ProductionReadinessReport,
    RolloutDecision,
)
from .rollout import default_rollout_plan


class ProductionReadinessValidator:
    """Evaluate whether the bot is allowed to progress into a deployment stage."""

    def __init__(self, plan=None) -> None:
        self.plan = plan or default_rollout_plan()
        self.capital_controller = CapitalAllocationController(self.plan)

    def evaluate(
        self, snapshot: OperationalSnapshot, controls: CapitalControls
    ) -> ProductionReadinessReport:
        gates: list[GateResult] = []
        stage_spec = self.plan.get_stage(snapshot.stage)

        gates.extend(self._validate_build(snapshot))
        gates.extend(self._validate_services(snapshot))
        gates.extend(self._validate_trading_state(snapshot, controls))
        gates.extend(self._validate_stage_evidence(snapshot, stage_spec.required_paper_trades, stage_spec.required_testnet_orders))
        gates.extend(self._validate_security(snapshot))
        gates.extend(self._validate_emergency_drills(snapshot))
        gates.extend(self._validate_manual_approval(snapshot, stage_spec.requires_manual_approval))

        capital = self.capital_controller.evaluate(snapshot.stage, controls)
        gates.extend(capital.gates)

        blocking = [g for g in gates if g.is_blocking_failure]
        warnings = [g for g in gates if g.status == GateStatus.WARN]
        if blocking:
            decision = RolloutDecision.HOLD
            approved_allocation = 0.0
            summary = f"Blocked by {len(blocking)} critical gate(s)."
        elif warnings:
            decision = RolloutDecision.APPROVE_WITH_LIMITS
            approved_allocation = capital.approved_allocation_usd
            summary = f"Approved with {len(warnings)} warning gate(s)."
        else:
            decision = RolloutDecision.APPROVE
            approved_allocation = capital.approved_allocation_usd
            summary = "All production readiness gates passed."

        if capital.decision == RolloutDecision.HOLD:
            decision = RolloutDecision.HOLD
            approved_allocation = 0.0

        return ProductionReadinessReport(
            stage=snapshot.stage,
            decision=decision,
            approved_allocation_usd=approved_allocation,
            max_allocation_usd=capital.max_allocation_usd,
            gates=gates,
            required_manual_approval=stage_spec.requires_manual_approval,
            summary=summary,
        )

    def _gate(self, name: str, ok: bool, message_ok: str, message_fail: str, evidence=None, severity=GateSeverity.BLOCKING) -> GateResult:
        return GateResult(
            name=name,
            status=GateStatus.PASS if ok else GateStatus.FAIL,
            severity=GateSeverity.INFO if ok else severity,
            message=message_ok if ok else message_fail,
            evidence=evidence or {},
        )

    def _validate_build(self, snapshot: OperationalSnapshot) -> list[GateResult]:
        return [
            self._gate(
                "ci_test_suite",
                snapshot.tests_passed and snapshot.test_count >= 100,
                "CI tests passed with sufficient coverage signal.",
                "CI tests are failing or test-count evidence is insufficient.",
                {"tests_passed": snapshot.tests_passed, "test_count": snapshot.test_count},
            ),
            self._gate(
                "immutable_release_reference",
                bool(snapshot.commit_sha and snapshot.image_tag),
                "Commit SHA and image tag are available.",
                "Deployment must reference immutable commit SHA and image tag.",
                {"commit_sha": snapshot.commit_sha, "image_tag": snapshot.image_tag},
            ),
        ]

    def _validate_services(self, snapshot: OperationalSnapshot) -> list[GateResult]:
        checks = [
            ("risk_engine_health", snapshot.risk_engine_healthy),
            ("monitoring_health", snapshot.monitoring_healthy),
            ("reconciliation_health", snapshot.reconciliation_healthy),
            ("order_book_sequence_health", snapshot.order_book_sequence_healthy),
            ("kill_switch_test", snapshot.kill_switch_tested),
        ]
        gates = [
            self._gate(
                name,
                ok,
                f"{name} gate passed.",
                f"{name} gate failed; deployment must fail closed.",
                {"ok": ok},
            )
            for name, ok in checks
        ]
        if snapshot.open_critical_alerts > 0:
            gates.append(
                GateResult(
                    name="critical_alerts",
                    status=GateStatus.FAIL,
                    severity=GateSeverity.BLOCKING,
                    message="Open critical alerts block deployment.",
                    evidence={"open_critical_alerts": snapshot.open_critical_alerts},
                )
            )
        else:
            gates.append(
                GateResult(
                    name="critical_alerts",
                    status=GateStatus.PASS,
                    severity=GateSeverity.INFO,
                    message="No open critical alerts.",
                )
            )
        if snapshot.stale_component_count > 0:
            gates.append(
                GateResult(
                    name="stale_components",
                    status=GateStatus.FAIL,
                    severity=GateSeverity.BLOCKING,
                    message="Stale components detected.",
                    evidence={"stale_component_count": snapshot.stale_component_count},
                )
            )
        else:
            gates.append(
                GateResult(
                    name="stale_components",
                    status=GateStatus.PASS,
                    severity=GateSeverity.INFO,
                    message="No stale components detected.",
                )
            )
        return gates

    def _validate_stage_evidence(self, snapshot: OperationalSnapshot, required_paper_trades: int, required_testnet_orders: int) -> list[GateResult]:
        gates = [
            self._gate(
                "paper_trade_count",
                snapshot.paper_trades >= required_paper_trades,
                "Required paper-trade evidence is available.",
                "Insufficient paper-trade evidence for this rollout stage.",
                {"paper_trades": snapshot.paper_trades, "required": required_paper_trades},
            ),
            self._gate(
                "testnet_order_count",
                snapshot.testnet_orders >= required_testnet_orders,
                "Required testnet-order evidence is available.",
                "Insufficient testnet-order evidence for this rollout stage.",
                {"testnet_orders": snapshot.testnet_orders, "required": required_testnet_orders},
            ),
        ]
        if snapshot.paper_profit_factor is not None and snapshot.paper_profit_factor < 1.05:
            gates.append(GateResult(
                name="paper_profit_factor",
                status=GateStatus.WARN,
                severity=GateSeverity.WARNING,
                message="Paper profit factor is weak; continue with reduced allocation only.",
                evidence={"paper_profit_factor": snapshot.paper_profit_factor},
            ))
        return gates

    def _validate_trading_state(self, snapshot: OperationalSnapshot, controls: CapitalControls) -> list[GateResult]:
        return [
            self._gate(
                "daily_loss_limit",
                snapshot.current_daily_loss_pct < controls.max_daily_loss_pct,
                "Daily loss is within limit.",
                "Daily loss limit reached or exceeded.",
                {"current": snapshot.current_daily_loss_pct, "limit": controls.max_daily_loss_pct},
            ),
            self._gate(
                "weekly_loss_limit",
                snapshot.current_weekly_loss_pct < controls.max_weekly_loss_pct,
                "Weekly loss is within limit.",
                "Weekly loss limit reached or exceeded.",
                {"current": snapshot.current_weekly_loss_pct, "limit": controls.max_weekly_loss_pct},
            ),
            self._gate(
                "portfolio_drawdown_limit",
                snapshot.current_drawdown_pct < controls.max_portfolio_drawdown_pct,
                "Portfolio drawdown is within limit.",
                "Portfolio drawdown limit reached or exceeded.",
                {"current": snapshot.current_drawdown_pct, "limit": controls.max_portfolio_drawdown_pct},
            ),
        ]

    def _validate_security(self, snapshot: OperationalSnapshot) -> list[GateResult]:
        gates = [
            self._gate(
                "withdrawal_permissions_disabled",
                snapshot.withdrawal_permissions_disabled,
                "Exchange API withdrawal permissions are disabled.",
                "Exchange API key must not have withdrawal permission.",
            ),
            self._gate(
                "secrets_manager",
                snapshot.secrets_loaded_from_manager,
                "Secrets are loaded from a managed secret source.",
                "Secrets must not be hardcoded or loaded from unsafe sources.",
            ),
        ]
        if snapshot.stage in {DeploymentStage.MICRO_LIVE, DeploymentStage.PILOT_LIVE, DeploymentStage.CONTROLLED_LIVE, DeploymentStage.FULL_LIVE}:
            gates.append(self._gate(
                "live_trading_flag",
                snapshot.live_trading_enabled,
                "Live trading flag is explicitly enabled for live stage.",
                "Live stage requires explicit live-trading opt-in flag.",
                {"live_trading_enabled": snapshot.live_trading_enabled},
            ))
        else:
            gates.append(self._gate(
                "live_trading_flag",
                not snapshot.live_trading_enabled,
                "Live trading is disabled for non-live stage.",
                "Live trading must remain disabled outside live stages.",
                {"live_trading_enabled": snapshot.live_trading_enabled},
            ))
        return gates

    def _validate_emergency_drills(self, snapshot: OperationalSnapshot) -> list[GateResult]:
        required = {"cancel_all", "emergency_flatten", "reconciliation_rebuild", "service_restart"}
        completed = {drill.name for drill in snapshot.emergency_drills if drill.completed}
        missing = sorted(required - completed)
        if missing:
            return [GateResult(
                name="emergency_drills",
                status=GateStatus.FAIL,
                severity=GateSeverity.BLOCKING,
                message="Required emergency drills are incomplete.",
                evidence={"missing": missing, "completed": sorted(completed)},
            )]
        slow = [d.name for d in snapshot.emergency_drills if d.latency_ms is not None and d.latency_ms > 5000]
        if slow:
            return [GateResult(
                name="emergency_drills",
                status=GateStatus.WARN,
                severity=GateSeverity.WARNING,
                message="Emergency drills completed but some exceeded latency target.",
                evidence={"slow_drills": slow},
            )]
        return [GateResult(
            name="emergency_drills",
            status=GateStatus.PASS,
            severity=GateSeverity.INFO,
            message="Required emergency drills completed.",
            evidence={"completed": sorted(completed)},
        )]

    def _validate_manual_approval(self, snapshot: OperationalSnapshot, required: bool) -> list[GateResult]:
        if not required:
            return [GateResult(
                name="manual_approval",
                status=GateStatus.SKIP,
                severity=GateSeverity.INFO,
                message="Manual approval not required for this stage.",
            )]
        return [self._gate(
            "manual_approval",
            snapshot.manual_approval,
            "Manual approval recorded.",
            "Manual approval is required before stage transition.",
            {"manual_approval": snapshot.manual_approval},
        )]
