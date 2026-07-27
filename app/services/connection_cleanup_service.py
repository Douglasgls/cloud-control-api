import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connection import Connection
from app.models.connection_status import ConnectionStatus

logger = logging.getLogger(__name__)


class ConnectionCleanupService:
    """Service to clean up expired or orphaned PENDING connections."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def cleanup_expired_pending_connections(self) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        stmt = (
            select(Connection)
            .where(Connection.status == ConnectionStatus.PENDING)
            .where((Connection.expires_at.isnot(None)) & (Connection.expires_at <= now))
        )
        expired_connections = list(self.db.scalars(stmt).all())

        if not expired_connections:
            return 0

        count = 0
        for conn in expired_connections:
            conn.status = ConnectionStatus.EXPIRED
            count += 1

        self.db.commit()
        logger.info("Cleaned up %d expired PENDING connection(s).", count)
        return count
