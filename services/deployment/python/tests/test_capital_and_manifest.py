from __future__ import annotations

import json

from deployment import CapitalAllocationController, CapitalControls, DeploymentStage
from deployment.manifest import build_deployment_manifest, write_manifest


def test_capital_controller_approves_within_micro_stage_cap():
    controls = CapitalControls(account_equity_usd=100000, requested_allocation_usd=900, max_effective_leverage=1.0)
    approval = CapitalAllocationController().evaluate(DeploymentStage.MICRO_LIVE, controls)
    assert approval.decision == "approve"
    assert approval.approved_allocation_usd == 900


def test_capital_controller_reduces_above_stage_cap():
    controls = CapitalControls(account_equity_usd=100000, requested_allocation_usd=2000, max_effective_leverage=1.0)
    approval = CapitalAllocationController().evaluate(DeploymentStage.MICRO_LIVE, controls)
    assert approval.decision == "approve_with_limits"
    assert approval.approved_allocation_usd == 1000


def test_manifest_writer(tmp_path):
    manifest = build_deployment_manifest(
        commit_sha="abcdef1",
        image_tag="trading-bot:0.15.0",
        stage="micro_live",
        config_hash="sha256:deadbeef",
    )
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    loaded = json.loads(path.read_text())
    assert loaded["commit_sha"] == "abcdef1"
    assert loaded["stage"] == "micro_live"
    assert "generated_at" in loaded
