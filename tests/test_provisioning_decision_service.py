from datetime import datetime, timedelta, timezone
import pytest

from app.models.environment import Environment
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.models.published_container import PublishedContainer
from app.models.published_node import PublishedNode
from app.models.provisioning_status import ProvisioningStatus
from app.services.headscale.provisioning_decision_service import (
    ProvisioningDecision,
    ProvisioningDecisionService,
)


def test_rule_1_environment_offline_skips():
    env = Environment(id="env-1", status_online=False)
    container = PublishedContainer(id="cont-1", status="running", provisioning_status=ProvisioningStatus.PENDING)

    decision = ProvisioningDecisionService.evaluate_container(container, env)
    assert decision == ProvisioningDecision.SKIP


def test_rule_2_container_not_running_skips():
    env = Environment(id="env-1", status_online=True)
    container = PublishedContainer(id="cont-1", status="stopped", provisioning_status=ProvisioningStatus.PENDING)

    decision = ProvisioningDecisionService.evaluate_container(container, env)
    assert decision == ProvisioningDecision.SKIP


def test_rule_7_fully_connected_container_skips():
    env = Environment(id="env-1", status_online=True)
    container = PublishedContainer(id="cont-1", status="running", provisioning_status=ProvisioningStatus.CONNECTED)
    node = PublishedNode(
        machine_id="mach-123",
        node_key="key-456",
        tailscale_ip="100.64.0.5",
        online=True,
    )

    decision = ProvisioningDecisionService.evaluate_container(container, env, node=node)
    assert decision == ProvisioningDecision.SKIP


def test_rule_7_connected_container_inconsistent_node_resets():
    env = Environment(id="env-1", status_online=True)
    container = PublishedContainer(id="cont-1", status="running", provisioning_status=ProvisioningStatus.CONNECTED)
    # Node missing machine_id or offline
    node = PublishedNode(machine_id="", node_key="key-456", tailscale_ip="100.64.0.5", online=False)

    decision = ProvisioningDecisionService.evaluate_container(container, env, node=node)
    assert decision == ProvisioningDecision.RESET_AND_PROVISION


def test_key_created_with_valid_key_dispatches_event():
    now = datetime.now(timezone.utc)
    env = Environment(id="env-1", status_online=True)
    container = PublishedContainer(id="cont-1", status="running", provisioning_status=ProvisioningStatus.KEY_CREATED)
    key = HeadscalePreAuthKey(
        key_name="hs_pk_test",
        used=False,
        expiration=now + timedelta(hours=1),
    )

    decision = ProvisioningDecisionService.evaluate_container(container, env, active_key=key, now=now)
    assert decision == ProvisioningDecision.DISPATCH_EVENT


def test_key_created_with_expired_key_resets():
    now = datetime.now(timezone.utc)
    env = Environment(id="env-1", status_online=True)
    container = PublishedContainer(id="cont-1", status="running", provisioning_status=ProvisioningStatus.KEY_CREATED)
    key = HeadscalePreAuthKey(
        key_name="hs_pk_test",
        used=False,
        expiration=now - timedelta(hours=1),
    )

    decision = ProvisioningDecisionService.evaluate_container(container, env, active_key=key, now=now)
    assert decision == ProvisioningDecision.RESET_AND_PROVISION


def test_pending_container_provisions():
    env = Environment(id="env-1", status_online=True)
    container = PublishedContainer(id="cont-1", status="running", provisioning_status=ProvisioningStatus.PENDING)

    decision = ProvisioningDecisionService.evaluate_container(container, env)
    assert decision == ProvisioningDecision.PROVISION
