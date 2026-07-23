import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.environment import Environment
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.models.published_container import PublishedContainer
from app.models.provisioning_status import ProvisioningStatus
from app.realtime.connection_manager import ConnectionManager
from app.realtime.protocol import WebSocketMessage
from app.repositories.headscale_preauth_key_repository import HeadscalePreAuthKeyRepository
from app.services.headscale.provisioning_decision_service import (
    ProvisioningDecision,
    ProvisioningDecisionService,
)
from app.services.headscale.provisioning_service import HeadscaleProvisioningService

logger = logging.getLogger(__name__)


class ProvisioningOrchestrator:
    """Orchestration service for Headscale container provisioning.
    
    Single entry point for loading entities, guaranteeing Environment Headscale User,
    evaluating domain decisions, triggering Headscale provisioning, updating state,
    and dispatching WebSocket events to Agents.
    """

    def __init__(
        self,
        db: Session,
        connection_manager: Optional[ConnectionManager] = None,
        provisioning_service: Optional[HeadscaleProvisioningService] = None,
    ) -> None:
        self.db = db
        self.connection_manager = connection_manager
        self.provisioning_service = provisioning_service or HeadscaleProvisioningService(db)
        self.key_repo = HeadscalePreAuthKeyRepository(db)
        self.settings = get_settings()

    async def orchestrate(self, environment_id: str) -> list[str]:
        logger.info(f"[ORCHESTRATOR] Starting provisioning orchestration for environment '{environment_id}'")
        
        environment = self.db.query(Environment).filter(Environment.id == environment_id).first()
        if not environment:
            logger.error(f"[ORCHESTRATOR] Environment '{environment_id}' not found in database.")
            return []

        # Guarantee Environment Headscale User (deterministic format: env_<environment_id>)
        headscale_user_name = f"env_{environment.id}"
        db_user = self.provisioning_service.ensure_environment_user(environment.id, headscale_user_name)
        logger.info(f"[ORCHESTRATOR] Environment Headscale User guaranteed: '{db_user.name}' (DB ID: {db_user.id})")

        containers = self.db.query(PublishedContainer).filter(PublishedContainer.environment_id == environment_id).all()
        provisioned_container_ids = []

        for container in containers:
            # Find active key if available and valid
            now = datetime.now(timezone.utc)
            existing_keys = self.key_repo.get_by_container(container.id)
            active_key: Optional[HeadscalePreAuthKey] = None
            for key in existing_keys:
                if not key.used and key.expiration is not None:
                    exp = key.expiration if key.expiration.tzinfo is not None else key.expiration.replace(tzinfo=timezone.utc)
                    if exp > now:
                        active_key = key
                        break

            node = container.published_node

            # Evaluate decision using pure domain service
            decision = ProvisioningDecisionService.evaluate_container(
                container=container,
                environment=environment,
                active_key=active_key,
                node=node,
            )

            logger.info(f"[ORCHESTRATOR] Container '{container.id}' ({container.name}) decision evaluated: {decision.value}")

            if decision == ProvisioningDecision.RESET_AND_PROVISION:
                container.provisioning_status = ProvisioningStatus.PENDING
                self.db.commit()
                active_key = None
                decision = ProvisioningDecision.PROVISION

            if decision == ProvisioningDecision.PROVISION:
                logger.info(f"[ORCHESTRATOR] Provisioning PreAuthKey for container '{container.id}'...")
                db_key = self.provisioning_service.ensure_container_preauth_key(
                    environment_id=environment.id,
                    published_container_id=container.id,
                    reusable=False,
                    ephemeral=False,
                )
                container.provisioning_status = ProvisioningStatus.KEY_CREATED
                self.db.commit()
                active_key = db_key
                logger.info(f"[ORCHESTRATOR] PreAuthKey generated for container '{container.id}'. State set to KEY_CREATED.")
                decision = ProvisioningDecision.DISPATCH_EVENT

            if decision == ProvisioningDecision.DISPATCH_EVENT and active_key:
                is_agent_online = self.connection_manager is not None and self.connection_manager.is_connected(environment.id)

                if is_agent_online:
                    logger.info(f"[ORCHESTRATOR] Agent online. Dispatching 'container.provision' event for container '{container.id}'")
                    payload = {
                        "published_container_id": container.id,
                        "api_local_container_id": container.api_local_container_id,
                        "container_number": container.container_number,
                        "preauth_key": active_key.key_name,
                        "headscale_url": self.settings.headscale_url,
                        "headscale_user": db_user.name,
                    }
                    message = WebSocketMessage(
                        request_id=str(uuid4()),
                        origin="cloud",
                        type="container.provision",
                        payload=payload,
                    )
                    await self.connection_manager.send(environment.id, message)
                    
                    container.provisioning_status = ProvisioningStatus.WAITING_AGENT
                    self.db.commit()
                    provisioned_container_ids.append(container.id)
                    logger.info(f"[ORCHESTRATOR] container.provision event dispatched successfully. State set to WAITING_AGENT.")
                else:
                    logger.info(
                        f"[ORCHESTRATOR] Agent offline for environment '{environment.id}'. "
                        f"Provisioning ready for container '{container.id}', state retained as KEY_CREATED."
                    )

            elif decision == ProvisioningDecision.SKIP:
                logger.debug(f"[ORCHESTRATOR] Provisioning skipped for container '{container.id}' (current status: {container.provisioning_status})")

        return provisioned_container_ids
