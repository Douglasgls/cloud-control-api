import logging
from sqlalchemy.orm import Session

from app.dtos.environment_sync import PublishedContainerSnapshotDTO
from app.models.published_container import PublishedContainer
from app.repositories.published_container_repository import PublishedContainerRepository
from app.services.published_node_sync_service import PublishedNodeSyncService
from app.services.access_token_sync_service import AccessTokenSyncService

logger = logging.getLogger(__name__)


class PublishedContainerSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PublishedContainerRepository(db)
        self.node_sync_service = PublishedNodeSyncService(db)
        self.token_sync_service = AccessTokenSyncService(db)

    def sync_containers(self, environment_id: str, containers_dto: list[PublishedContainerSnapshotDTO]) -> list[PublishedContainer]:
        synced_containers = []

        for container_dto in containers_dto:
            existing = self.repository.get_by_api_local_id(environment_id, container_dto.api_local_container_id)

            if existing:
                has_changes = (
                    existing.name != container_dto.name or
                    existing.container_number != container_dto.container_number or
                    existing.status != container_dto.status
                )

                if has_changes:
                    self.repository.update(
                        existing,
                        name=container_dto.name,
                        container_number=container_dto.container_number,
                        status=container_dto.status
                    )
                    logger.info(
                        f"Published container updated: {container_dto.api_local_container_id} "
                        f"({container_dto.name})"
                    )
                else:
                    logger.debug(
                        f"Published container synchronized (no changes): {container_dto.api_local_container_id} "
                        f"({container_dto.name})"
                    )
                container = existing
            else:
                container = self.repository.create(
                    environment_id=environment_id,
                    api_local_id=container_dto.api_local_container_id,
                    name=container_dto.name,
                    container_number=container_dto.container_number,
                    status=container_dto.status
                )
                logger.info(
                    f"Published container created: {container_dto.api_local_container_id} "
                    f"({container_dto.name})"
                )

            # Sync Node associated with this Container
            self.node_sync_service.sync_node(container.id, container_dto.tailscale)

            # Sync Access Tokens associated with this Container
            self.token_sync_service.sync_tokens(container.id, container_dto.access_tokens)

            synced_containers.append(container)

        return synced_containers
