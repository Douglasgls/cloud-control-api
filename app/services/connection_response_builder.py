from typing import Optional

from app.core.config import get_settings
from app.dto.client_connection import (
    AuthorizedConnectionContext,
    ClientConnectionResponseDTO,
    ConnectionInstructionsDTO,
    ValidationResult,
)
from app.models.connection import Connection
from app.models.headscale_preauth_key import HeadscalePreAuthKey


class ConnectionResponseBuilder:
    """Prepares the ClientConnectionResponseDTO containing client instructions based on authorization result and domain entities."""

    def build(
        self,
        result: ValidationResult,
        context: Optional[AuthorizedConnectionContext] = None,
        connection: Optional[Connection] = None,
        preauth_key: Optional[HeadscalePreAuthKey] = None,
    ) -> ClientConnectionResponseDTO:
        target_context = context or result.context

        if result.allowed:
            settings = get_settings()
            node = target_context.published_node if target_context else None
            hostname = (node.tailscale_ip or node.machine_id or node.node_key) if node else None

            key_str = preauth_key.key_name if preauth_key else None
            exp_time = (
                preauth_key.expiration
                if preauth_key and preauth_key.expiration
                else (connection.expires_at if connection else None)
            )
            expires_at_str = exp_time.isoformat() if exp_time else None

            conn_id = connection.id if connection else None
            instructions = ConnectionInstructionsDTO(
                connection_id=conn_id,
                login_server=settings.headscale_url,
                preauth_key=key_str,
                hostname=hostname,
                expires_at=expires_at_str,
            )
            return ClientConnectionResponseDTO(
                authorized=True,
                connection=instructions,
            )

        return ClientConnectionResponseDTO(
            authorized=False,
            code=result.code,
            message=result.message,
            connection=ConnectionInstructionsDTO(),
        )

