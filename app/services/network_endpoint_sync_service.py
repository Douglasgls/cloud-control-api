import logging
import re
from sqlalchemy.orm import Session

from app.dtos.environment_sync import (
    NetworkEndpointPortSnapshotDTO,
    PublishedContainerSnapshotDTO,
    PublishedTailscaleNodeSnapshotDTO,
)
from app.models.network_endpoint import NetworkEndpoint
from app.repositories.network_endpoint_repository import NetworkEndpointRepository

logger = logging.getLogger(__name__)


def sanitize_hostname(name: str) -> str:
    """Sanitizes container name into RFC 1123 compliant hostname."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "container"


def derive_dns_name(hostname: str) -> str:
    """Derives standard logical FQDN for the platform namespace."""
    return f"{hostname}.interno"


class NetworkEndpointSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = NetworkEndpointRepository(db)

    def sync_container_endpoint(
        self,
        published_container_id: str,
        container_dto: PublishedContainerSnapshotDTO,
    ) -> NetworkEndpoint | None:
        # Determine hostname
        raw_hostname = container_dto.hostname
        if not raw_hostname and container_dto.tailscale and container_dto.tailscale.hostname:
            raw_hostname = container_dto.tailscale.hostname
        if not raw_hostname:
            raw_hostname = container_dto.name

        hostname = sanitize_hostname(raw_hostname)
        expected_dns_name = derive_dns_name(hostname)

        # Validate dns_name
        provided_dns_name = container_dto.dns_name
        if not provided_dns_name and container_dto.tailscale and container_dto.tailscale.dns_name:
            provided_dns_name = container_dto.tailscale.dns_name

        if provided_dns_name and provided_dns_name.lower() != expected_dns_name.lower():
            logger.warning(
                f"[NETWORK ENDPOINT] Mismatched dns_name '{provided_dns_name}' for hostname '{hostname}'. "
                f"Enforcing normalized domain '{expected_dns_name}'."
            )
        dns_name = expected_dns_name

        # Determine tailscale_ip & status
        tailscale_ip = None
        status = "offline"

        if container_dto.tailscale:
            tailscale_ip = container_dto.tailscale.tailscale_ip
            if container_dto.tailscale.online and (container_dto.status or "").lower() == "running":
                status = "online"
            elif container_dto.tailscale.online:
                status = "online"

        # Determine ports
        ports_dto: list[NetworkEndpointPortSnapshotDTO] = []
        if container_dto.ports:
            ports_dto = container_dto.ports
        elif container_dto.tailscale and container_dto.tailscale.ports:
            ports_dto = container_dto.tailscale.ports

        # Find existing endpoint
        existing = self.repository.get_by_container_id(published_container_id)

        if existing:
            # Update endpoint attributes
            self.repository.update(
                existing,
                hostname=hostname,
                dns_name=dns_name,
                tailscale_ip=tailscale_ip or existing.tailscale_ip,
                status=status,
            )
            self.repository.sync_ports(existing, ports_dto)
            logger.info(f"[NETWORK ENDPOINT] Updated endpoint '{dns_name}' ({status}) for container {published_container_id}")
            return existing
        else:
            # Create new endpoint
            new_endpoint = self.repository.create(
                published_container_id=published_container_id,
                hostname=hostname,
                dns_name=dns_name,
                tailscale_ip=tailscale_ip,
                status=status,
            )
            self.repository.sync_ports(new_endpoint, ports_dto)
            logger.info(f"[NETWORK ENDPOINT] Created endpoint '{dns_name}' ({status}) for container {published_container_id}")
            return new_endpoint
