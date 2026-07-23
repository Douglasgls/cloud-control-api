import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.models.environment import Environment
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.models.published_container import PublishedContainer
from app.models.published_node import PublishedNode
from app.models.provisioning_status import ProvisioningStatus

logger = logging.getLogger(__name__)


class ProvisioningDecision(str, Enum):
    PROVISION = "PROVISION"
    DISPATCH_EVENT = "DISPATCH_EVENT"
    RESET_AND_PROVISION = "RESET_AND_PROVISION"
    SKIP = "SKIP"


class ProvisioningDecisionService:
    """Pure domain service responsible for determining container provisioning eligibility.
    
    Contains ZERO database queries, network calls, or WebSocket interactions.
    Operates strictly on pre-loaded domain entities.
    """

    @staticmethod
    def evaluate_container(
        container: PublishedContainer,
        environment: Environment,
        active_key: Optional[HeadscalePreAuthKey] = None,
        node: Optional[PublishedNode] = None,
        now: Optional[datetime] = None,
    ) -> ProvisioningDecision:
        if now is None:
            now = datetime.now(timezone.utc)

        # Rule 1: Container must belong to an online Environment
        if not environment.status_online:
            logger.debug(f"[DECISION] Skipping container '{container.id}': Environment '{environment.id}' is offline.")
            return ProvisioningDecision.SKIP

        # Rule 2: Container status must be 'running'
        if container.status != "running":
            logger.debug(f"[DECISION] Skipping container '{container.id}': Container status is '{container.status}' (must be 'running').")
            return ProvisioningDecision.SKIP

        # Rule 7 Check: Validate if container is fully CONNECTED and functional
        is_node_connected = (
            node is not None
            and bool(node.machine_id)
            and bool(node.node_key)
            and bool(node.tailscale_ip)
            and node.online is True
        )

        if container.provisioning_status == ProvisioningStatus.CONNECTED:
            if is_node_connected:
                logger.debug(f"[DECISION] Skipping container '{container.id}': Already fully CONNECTED.")
                return ProvisioningDecision.SKIP
            else:
                logger.info(f"[DECISION] Container '{container.id}' marked CONNECTED but node state is inconsistent. Resetting to PENDING.")
                return ProvisioningDecision.RESET_AND_PROVISION

        # Check active key validity (Rule 4 & Consistency check)
        is_key_valid = (
            active_key is not None
            and not active_key.used
            and active_key.expiration is not None
            and (
                active_key.expiration.tzinfo is not None 
                and active_key.expiration > now 
                or active_key.expiration.replace(tzinfo=timezone.utc) > now
            )
        )

        # Handle KEY_CREATED / WAITING_AGENT state consistency
        if container.provisioning_status in (ProvisioningStatus.KEY_CREATED, ProvisioningStatus.WAITING_AGENT):
            if is_key_valid:
                logger.debug(f"[DECISION] Container '{container.id}' has valid key created in DB. Action: DISPATCH_EVENT.")
                return ProvisioningDecision.DISPATCH_EVENT
            else:
                logger.info(f"[DECISION] Container '{container.id}' in state '{container.provisioning_status}' but key is invalid/expired. Resetting.")
                return ProvisioningDecision.RESET_AND_PROVISION

        # State PENDING or unknown
        if not is_key_valid:
            logger.info(f"[DECISION] Container '{container.id}' is PENDING without valid key. Action: PROVISION.")
            return ProvisioningDecision.PROVISION
        else:
            return ProvisioningDecision.DISPATCH_EVENT
