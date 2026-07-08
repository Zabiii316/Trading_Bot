from __future__ import annotations

from .models import DeploymentStage, RolloutPlan, StageSpec


def default_rollout_plan() -> RolloutPlan:
    """Return a conservative rollout plan for Binance USD-M live deployment."""
    return RolloutPlan(
        stages=[
            StageSpec(
                stage=DeploymentStage.TESTNET_SHADOW,
                duration_hours=24,
                max_allocation_pct=0.0,
                max_effective_leverage=1.0,
                description="Generate signals and risk decisions without order submission.",
            ),
            StageSpec(
                stage=DeploymentStage.TESTNET_PAPER,
                duration_hours=48,
                max_allocation_pct=0.0,
                max_effective_leverage=1.0,
                required_paper_trades=200,
                description="Paper execution against live reconstructed books.",
            ),
            StageSpec(
                stage=DeploymentStage.TESTNET_EXECUTION,
                duration_hours=48,
                max_allocation_pct=0.0,
                max_effective_leverage=1.0,
                required_testnet_orders=100,
                description="Signed Binance testnet order lifecycle validation.",
            ),
            StageSpec(
                stage=DeploymentStage.MICRO_LIVE,
                duration_hours=24,
                max_allocation_pct=0.01,
                max_effective_leverage=1.0,
                description="Mainnet enabled with micro allocation and strict kill-switch gates.",
            ),
            StageSpec(
                stage=DeploymentStage.PILOT_LIVE,
                duration_hours=72,
                max_allocation_pct=0.03,
                max_effective_leverage=1.25,
                description="Small pilot capital with monitored order/fill behaviour.",
            ),
            StageSpec(
                stage=DeploymentStage.CONTROLLED_LIVE,
                duration_hours=168,
                max_allocation_pct=0.10,
                max_effective_leverage=2.0,
                description="Controlled production allocation after stable pilot evidence.",
            ),
            StageSpec(
                stage=DeploymentStage.FULL_LIVE,
                duration_hours=0,
                max_allocation_pct=0.25,
                max_effective_leverage=2.0,
                description="Future stage; should require investment committee approval.",
            ),
        ]
    )
