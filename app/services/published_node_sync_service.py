import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.dtos.environment_sync import PublishedTailscaleNodeSnapshotDTO
from app.models.published_container import PublishedContainer
from app.models.published_node import PublishedNode
from app.models.provisioning_status import ProvisioningStatus
from app.repositories.published_node_repository import PublishedNodeRepository

logger = logging.getLogger(__name__)


def parse_datetime(val) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


class PublishedNodeSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PublishedNodeRepository(db)

    def sync_node(self, published_container_id: str, node_dto: PublishedTailscaleNodeSnapshotDTO | None) -> PublishedNode | None:
        existing = self.repository.get_by_container_id(published_container_id)

        if not node_dto:
            if existing and existing.online:
                logger.info(f"Published node for container {published_container_id} went offline (Tailscale removed).")
                self.repository.update(
                    existing,
                    installed=existing.installed,
                    service_running=existing.service_running,
                    version=existing.version,
                    machine_id=existing.machine_id,
                    node_key=existing.node_key,
                    tailscale_ip=existing.tailscale_ip,
                    online=False,
                    last_sync=existing.last_sync
                )
            return existing

        last_sync = parse_datetime(node_dto.last_sync)

        if existing:
            # Check for changes
            has_changes = (
                existing.installed != node_dto.installed or
                existing.service_running != node_dto.service_running or
                existing.version != node_dto.version or
                existing.machine_id != node_dto.machine_id or
                existing.node_key != node_dto.node_key or
                existing.tailscale_ip != node_dto.tailscale_ip or
                existing.online != node_dto.online or
                existing.last_sync != last_sync
            )

            if has_changes:
                self.repository.update(
                    existing,
                    installed=node_dto.installed,
                    service_running=node_dto.service_running,
                    version=node_dto.version,
                    machine_id=node_dto.machine_id,
                    node_key=node_dto.node_key,
                    tailscale_ip=node_dto.tailscale_ip,
                    online=node_dto.online,
                    last_sync=last_sync
                )
                logger.info(f"Published node updated for container ID: {published_container_id}")
            else:
                logger.debug(f"Published node synchronized (no changes) for container ID: {published_container_id}")
            result_node = existing
        else:
            new_node = self.repository.create(
                published_container_id=published_container_id,
                installed=node_dto.installed,
                service_running=node_dto.service_running,
                version=node_dto.version,
                machine_id=node_dto.machine_id,
                node_key=node_dto.node_key,
                tailscale_ip=node_dto.tailscale_ip,
                online=node_dto.online,
                last_sync=last_sync
            )
            logger.info(f"Published node created for container ID: {published_container_id}")
            result_node = new_node

        # Rule 7: Update PublishedContainer provisioning_status to CONNECTED if node is fully functional
        is_fully_connected = (
            bool(node_dto.machine_id)
            and bool(node_dto.node_key)
            and bool(node_dto.tailscale_ip)
            and node_dto.online is True
        )
        if is_fully_connected:
            container = self.db.query(PublishedContainer).filter(PublishedContainer.id == published_container_id).first()
            if container:
                if container.provisioning_status != ProvisioningStatus.CONNECTED:
                    logger.info(f"[NODE SYNC] Container '{published_container_id}' node is fully functional. Updating provisioning_status to CONNECTED.")
                    container.provisioning_status = ProvisioningStatus.CONNECTED
                
                # Sync HeadscaleNode entity into headscale_nodes DB table
                try:
                    from app.services.headscale.node_service import HeadscaleNodeService
                    from app.repositories.headscale_user_repository import HeadscaleUserRepository
                    
                    user_repo = HeadscaleUserRepository(self.db)
                    db_user = user_repo.get_by_environment(container.environment_id)
                    if db_user:
                        node_service = HeadscaleNodeService(self.db)
                        api_nodes = node_service.list(db_user.name)
                        for n in api_nodes:
                            if n.name.lower() == container.name.lower() or n.given_name.lower() == container.name.lower() or len(api_nodes) == 1:
                                node_service.sync_registered_node(
                                    headscale_user_db_id=db_user.id,
                                    published_container_id=container.id,
                                    headscale_node_id=n.id,
                                    hostname=n.name,
                                    given_name=n.given_name,
                                    registered=True,
                                )
                except Exception as err:
                    logger.warning(f"[NODE SYNC] Optional HeadscaleNode DB sync note: {err}")

        return result_node
