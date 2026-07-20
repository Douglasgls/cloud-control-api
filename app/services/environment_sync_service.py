import logging
from sqlalchemy.orm import Session

from app.dtos.environment_sync import EnvironmentSnapshotDTO
from app.services.published_container_sync_service import PublishedContainerSyncService

logger = logging.getLogger(__name__)


class EnvironmentSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.container_sync_service = PublishedContainerSyncService(db)

    def sync(self, environment_id: str, snapshot: EnvironmentSnapshotDTO) -> None:
        logger.info(f"Starting environment sync for environment_id: {environment_id}")

        try:
            # Wrap all synchronization inside a single database transaction / savepoint.
            with self.db.begin_nested():
                self.container_sync_service.sync_containers(environment_id, snapshot.published_containers)
            
            self.db.commit()
            logger.info(f"Environment synchronized successfully for environment_id: {environment_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Environment sync failed for environment_id {environment_id}: {str(e)}", exc_info=True)
            raise e
