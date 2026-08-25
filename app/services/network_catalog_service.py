from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dtos.network_catalog import (
    NetworkCatalogItemDTO,
    NetworkCatalogPortDTO,
    NetworkCatalogResponseDTO,
)
from app.models.environment import Environment
from app.models.network_endpoint import NetworkEndpoint
from app.models.published_container import PublishedContainer


class NetworkCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_catalog_for_user(self, user_id: int) -> NetworkCatalogResponseDTO:
        # Fetch all network endpoints for containers belonging to the user's environments
        stmt = (
            select(NetworkEndpoint)
            .join(PublishedContainer, NetworkEndpoint.published_container_id == PublishedContainer.id)
            .join(Environment, PublishedContainer.environment_id == Environment.id)
            .where(Environment.user_id == user_id)
            .options(joinedload(NetworkEndpoint.ports))
        )
        endpoints = self.db.scalars(stmt).unique().all()

        catalog_items: list[NetworkCatalogItemDTO] = []
        latest_updated_at: datetime | None = None

        for ep in endpoints:
            if latest_updated_at is None or (ep.updated_at and ep.updated_at > latest_updated_at):
                latest_updated_at = ep.updated_at

            ports_dto = [
                NetworkCatalogPortDTO(port=p.port, protocol=p.protocol)
                for p in ep.ports
                if p.enabled
            ]

            clean_ip = ep.tailscale_ip.split()[0] if ep.tailscale_ip else None
            catalog_items.append(
                NetworkCatalogItemDTO(
                    hostname=ep.hostname,
                    fqdn=ep.dns_name,
                    tailscale_ip=clean_ip,
                    status=ep.status,
                    ports=ports_dto,
                )
            )

        updated_at_val = latest_updated_at or datetime.now(timezone.utc)
        version_num = int(updated_at_val.timestamp()) if isinstance(updated_at_val, datetime) else 1

        return NetworkCatalogResponseDTO(
            version=version_num,
            updated_at=updated_at_val,
            endpoints=catalog_items,
        )

    def get_global_catalog(self) -> NetworkCatalogResponseDTO:
        stmt = select(NetworkEndpoint).options(joinedload(NetworkEndpoint.ports))
        endpoints = self.db.scalars(stmt).unique().all()

        catalog_items: list[NetworkCatalogItemDTO] = []
        latest_updated_at: datetime | None = None

        for ep in endpoints:
            if latest_updated_at is None or (ep.updated_at and ep.updated_at > latest_updated_at):
                latest_updated_at = ep.updated_at

            ports_dto = [
                NetworkCatalogPortDTO(port=p.port, protocol=p.protocol)
                for p in ep.ports
                if p.enabled
            ]

            clean_ip = ep.tailscale_ip.split()[0] if ep.tailscale_ip else None
            catalog_items.append(
                NetworkCatalogItemDTO(
                    hostname=ep.hostname,
                    fqdn=ep.dns_name,
                    tailscale_ip=clean_ip,
                    status=ep.status,
                    ports=ports_dto,
                )
            )

        updated_at_val = latest_updated_at or datetime.now(timezone.utc)
        version_num = int(updated_at_val.timestamp()) if isinstance(updated_at_val, datetime) else 1

        return NetworkCatalogResponseDTO(
            version=version_num,
            updated_at=updated_at_val,
            endpoints=catalog_items,
        )
