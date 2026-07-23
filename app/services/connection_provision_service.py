import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.dto.client_connection import AuthorizedConnectionContext
from app.models.connection import Connection
from app.models.connection_status import ConnectionStatus
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.repositories.connection_repository import ConnectionRepository
from app.services.headscale.provisioning_service import HeadscaleProvisioningService

logger = logging.getLogger(__name__)


class ConnectionProvisionService:
    """Service responsible for client connection provisioning.
    
    Guarantees the Headscale user, requests a new PreAuthKey from Headscale,
    persists the PreAuthKey, and creates a Connection authorization record.
    """

    def __init__(
        self,
        db: Session,
        provisioning_service: Optional[HeadscaleProvisioningService] = None,
        connection_repo: Optional[ConnectionRepository] = None,
    ) -> None:
        self.db = db
        self.provisioning_service = provisioning_service or HeadscaleProvisioningService(db)
        self.connection_repo = connection_repo or ConnectionRepository(db)

    def provision(
        self, context: AuthorizedConnectionContext
    ) -> Tuple[Connection, HeadscalePreAuthKey]:
        if not context.environment or not context.published_container or not context.access_token:
            raise ValueError("Context is missing required entities for connection provisioning.")

        logger.info(
            f"Provisioning client connection for container '{context.published_container.id}' "
            f"in environment '{context.environment.id}'..."
        )

        # 1 & 2: Guarantee Headscale user & request brand new PreAuthKey
        preauth_key = self.provisioning_service.create_preauth_key(
            environment_id=context.environment.id,
            published_container_id=context.published_container.id,
            reusable=False,
            ephemeral=False,
        )

        # 3 & 4: Create Connection record in DB (status=PENDING)
        connection = self.connection_repo.create(
            published_container_id=context.published_container.id,
            access_token_id=context.access_token.id,
            headscale_preauth_key_id=preauth_key.id,
            status=ConnectionStatus.PENDING,
            expires_at=preauth_key.expiration,
        )

        self.db.commit()
        logger.info(f"Client connection provisioned successfully (Connection ID: {connection.id}).")

        return connection, preauth_key
