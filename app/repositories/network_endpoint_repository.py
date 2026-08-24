from sqlalchemy.orm import Session
from sqlalchemy import select

from app.dtos.environment_sync import NetworkEndpointPortSnapshotDTO
from app.models.network_endpoint import NetworkEndpoint
from app.models.network_endpoint_port import NetworkEndpointPort


class NetworkEndpointRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_container_id(self, published_container_id: str) -> NetworkEndpoint | None:
        return self.db.scalar(
            select(NetworkEndpoint).where(NetworkEndpoint.published_container_id == published_container_id)
        )

    def get_by_dns_name(self, dns_name: str) -> NetworkEndpoint | None:
        return self.db.scalar(
            select(NetworkEndpoint).where(NetworkEndpoint.dns_name == dns_name)
        )

    def create(
        self,
        *,
        published_container_id: str,
        hostname: str,
        dns_name: str,
        tailscale_ip: str | None = None,
        status: str = "unknown"
    ) -> NetworkEndpoint:
        endpoint = NetworkEndpoint(
            published_container_id=published_container_id,
            hostname=hostname,
            dns_name=dns_name,
            tailscale_ip=tailscale_ip,
            status=status,
        )
        self.db.add(endpoint)
        self.db.flush()
        return endpoint

    def update(
        self,
        endpoint: NetworkEndpoint,
        *,
        hostname: str,
        dns_name: str,
        tailscale_ip: str | None = None,
        status: str = "unknown"
    ) -> NetworkEndpoint:
        endpoint.hostname = hostname
        endpoint.dns_name = dns_name
        endpoint.tailscale_ip = tailscale_ip
        endpoint.status = status
        self.db.flush()
        return endpoint

    def sync_ports(
        self,
        endpoint: NetworkEndpoint,
        ports_dto: list[NetworkEndpointPortSnapshotDTO]
    ) -> None:
        # Map incoming ports as tuple (port, protocol)
        target_ports = {(dto.port, (dto.protocol or "tcp").lower()) for dto in ports_dto}

        existing_ports = { (p.port, p.protocol.lower()): p for p in endpoint.ports }

        # Remove ports that are no longer present
        for (port_num, proto), port_entity in list(existing_ports.items()):
            if (port_num, proto) not in target_ports:
                self.db.delete(port_entity)

        # Add new ports
        for port_num, proto in target_ports:
            if (port_num, proto) not in existing_ports:
                new_port = NetworkEndpointPort(
                    network_endpoint_id=endpoint.id,
                    port=port_num,
                    protocol=proto,
                    enabled=True,
                )
                self.db.add(new_port)

        self.db.flush()
