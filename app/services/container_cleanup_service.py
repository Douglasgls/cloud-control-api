import logging
from sqlalchemy.orm import Session
from app.models.published_container import PublishedContainer
from app.repositories.published_container_repository import PublishedContainerRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.headscale_node_repository import HeadscaleNodeRepository
from app.services.headscale.node_service import HeadscaleNodeService

logger = logging.getLogger(__name__)

class ContainerCleanupService:
    """Service dedicated to the lifecycle cleanup of orphaned containers."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.container_repo = PublishedContainerRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.node_repo = HeadscaleNodeRepository(db)
        self.headscale_node_service = HeadscaleNodeService(db)

    def cleanup_orphaned_containers(self, environment_id: str, orphaned_containers: list[PublishedContainer]) -> None:
        """
        Orchestrates the cleanup of containers that are no longer present in the Agent's snapshot.
        This includes deleting associated Headscale nodes (both for the container and its clients)
        and removing the container from the database.
        """
        if not orphaned_containers:
            return

        logger.info(f"[CLEANUP] Starting cleanup for {len(orphaned_containers)} orphaned containers in environment {environment_id}")

        for container in orphaned_containers:
            try:
                self._cleanup_single_container(container)
            except Exception as e:
                logger.error(
                    f"[CLEANUP] Failed to cleanup container {container.api_local_container_id} ({container.name}): {e}",
                    exc_info=True
                )
                # We raise the exception to fail the entire sync transaction, ensuring that
                # if Headscale API fails, we don't accidentally remove the container from our DB.
                # The next environment.sync will retry the cleanup.
                raise

    def _cleanup_single_container(self, container: PublishedContainer) -> None:
        logger.info(f"[CLEANUP] Purging container '{container.name}' (ID: {container.id})")

        # 1. Collect all Headscale Node IDs associated with this container
        nodes_to_delete = []

        # 1a. The main container node
        container_node = self.node_repo.get_by_container(container.id)
        if container_node and container_node.headscale_node_id:
            nodes_to_delete.append(container_node.headscale_node_id)

        # 1b. The client nodes connected to this container
        conns = self.connection_repo.list_by_container(container.id)
        for conn in conns:
            if conn.headscale_node_id:
                nodes_to_delete.append(conn.headscale_node_id)

        # 2. Delete nodes from Headscale API (Idempotent)
        for node_id in set(nodes_to_delete):  # Use set to avoid duplicate deletions
            logger.info(f"[CLEANUP] Deleting Headscale node {node_id}")
            try:
                self.headscale_node_service.delete(node_id)
            except Exception as e:
                # If it's a 404 (Not Found), it means it's already deleted in Headscale.
                # However, HeadscaleNodeService handles exceptions internally or propagates them.
                # Re-raise to ensure we don't leave zombie Headscale nodes if it was a 500 error
                raise

        # 3. Delete the container from the database (Cascades will delete tokens, endpoints, and connections)
        self.container_repo.delete(container)
        logger.info(f"[CLEANUP] Container '{container.name}' successfully purged from DB.")
