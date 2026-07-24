import ipaddress
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


def parse_tailscale_ips(raw_ip_str: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not raw_ip_str:
        return None, None

    ipv4 = None
    ipv6 = None

    tokens = [t.strip() for t in raw_ip_str.replace(",", " ").replace("\n", " ").split() if t.strip()]
    for token in tokens:
        try:
            ip_obj = ipaddress.ip_address(token)
            if ip_obj.version == 4 and not ipv4:
                ipv4 = str(ip_obj)
            elif ip_obj.version == 6 and not ipv6:
                ipv6 = str(ip_obj)
        except ValueError:
            continue

    return ipv4, ipv6


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
            container = target_context.published_container if target_context else None
            node = target_context.published_node if target_context else None

            hostname = container.name if container else None
            tailscale_ip, tailscale_ipv6 = parse_tailscale_ips(node.tailscale_ip if node else None)

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
                tailscale_ip=tailscale_ip,
                tailscale_ipv6=tailscale_ipv6,
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


