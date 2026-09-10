import logging
from sqlalchemy.orm import Session
from app.models.published_container import PublishedContainer
from app.repositories.published_container_repository import PublishedContainerRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.headscale_node_repository import HeadscaleNodeRepository
from app.repositories.headscale_user_repository import HeadscaleUserRepository
from app.repositories.headscale_preauth_key_repository import HeadscalePreAuthKeyRepository
from app.services.headscale.node_service import HeadscaleNodeService
from app.services.headscale.preauthkey_service import HeadscalePreAuthKeyService
from app.integrations.headscale.exceptions import HeadscaleNotFoundError, HeadscaleRequestError

logger = logging.getLogger(__name__)

class ContainerCleanupService:
    """Service dedicated to the lifecycle cleanup of orphaned containers."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.container_repo = PublishedContainerRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.node_repo = HeadscaleNodeRepository(db)
        self.user_repo = HeadscaleUserRepository(db)
        self.key_repo = HeadscalePreAuthKeyRepository(db)
        self.headscale_node_service = HeadscaleNodeService(db)
        self.headscale_key_service = HeadscalePreAuthKeyService(db)

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
                self._cleanup_single_container(environment_id, container)
            except Exception as e:
                logger.error(
                    f"[CLEANUP] Failed to cleanup container {container.api_local_container_id} ({container.name}): {e}",
                    exc_info=True
                )
                # We raise the exception to fail the entire sync transaction, ensuring that
                # if Headscale API fails, we don't accidentally remove the container from our DB.
                # The next environment.sync will retry the cleanup.
                raise

    def _cleanup_single_container(self, environment_id: str, container: PublishedContainer) -> None:
        logger.info(f"[CLEANUP] Purging container '{container.name}' (ID: {container.id})")

        nodes_to_delete = set()
        
        # Determine the Headscale user for this environment
        headscale_user_name = None
        db_user = self.user_repo.get_by_environment(environment_id)
        if db_user:
            headscale_user_name = db_user.name
        else:
            logger.warning(f"[CLEANUP] No Headscale user found in DB for environment {environment_id}")

        # LAYER 1: Collect node IDs from database
        container_nodes = self.node_repo.list_by_container(container.id)
        for node in container_nodes:
            if node.headscale_node_id:
                nodes_to_delete.add(node.headscale_node_id)

        conns = self.connection_repo.list_by_container(container.id)
        for conn in conns:
            if conn.headscale_node_id:
                # Need to resolve DB node ID to Headscale node ID
                db_conn_node = self.node_repo.get_by_id(conn.headscale_node_id)
                if db_conn_node and db_conn_node.headscale_node_id:
                    nodes_to_delete.add(db_conn_node.headscale_node_id)

        # LAYER 2 & 3: Fallback by hostname directly in Headscale API
        if headscale_user_name:
            try:
                # Fetch all nodes for this user from the API
                api_nodes = self.headscale_node_service.list(user=headscale_user_name)
                for api_node in api_nodes:
                    hostname = getattr(api_node, 'given_name', None) or api_node.name
                    if not hostname:
                        continue
                        
                    # Match Layer 2: Exact container name
                    if hostname == container.name:
                        nodes_to_delete.add(str(api_node.id))
                        logger.info(f"[CLEANUP] Found orphaned container node by name: {hostname} (ID: {api_node.id})")
                        
                    # Match Layer 3: Client nodes format client-{container.name}-*
                    elif hostname.startswith(f"client-{container.name}"):
                        nodes_to_delete.add(str(api_node.id))
                        logger.info(f"[CLEANUP] Found orphaned client node by name: {hostname} (ID: {api_node.id})")
            except Exception as e:
                logger.error(f"[CLEANUP] Failed to fetch nodes from API for user {headscale_user_name}: {e}")
                # We continue to delete at least the nodes we found in the DB (Layer 1)

        # LAYER 4: Expire unused preauth keys in Headscale
        if headscale_user_name:
            db_keys = self.key_repo.get_by_container(container.id)
            for key in db_keys:
                if not key.used:
                    try:
                        self.headscale_key_service.expire(headscale_user_name, key.key_name)
                        logger.info(f"[CLEANUP] Expired unused PreAuthKey for container '{container.name}'")
                    except Exception as e:
                        logger.error(f"[CLEANUP] Failed to expire PreAuthKey on Headscale API: {e}")

        # Delete nodes from Headscale API (Idempotent)
        for node_id in nodes_to_delete:
            logger.info(f"[CLEANUP] Deleting Headscale node {node_id}")
            try:
                self.headscale_node_service.delete(node_id)
            except HeadscaleNotFoundError:
                logger.info(f"[CLEANUP] Headscale node {node_id} already removed (404). Continuing cleanup.")
            except HeadscaleRequestError as e:
                if e.status_code == 400:
                    logger.info(f"[CLEANUP] Headscale node {node_id} returned 400 (invalid/already removed). Continuing cleanup.")
                else:
                    raise

        # Delete the container from the database (Cascades will delete tokens, endpoints, and connections)
        self.container_repo.delete(container)
        logger.info(f"[CLEANUP] Container '{container.name}' successfully purged from DB.")
