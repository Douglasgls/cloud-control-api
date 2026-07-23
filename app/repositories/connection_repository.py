from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connection import Connection
from app.models.connection_status import ConnectionStatus


class ConnectionRepository:
    """Repository for managing Connection entities in the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, connection_id: int) -> Optional[Connection]:
        return self.db.get(Connection, connection_id)

    def list_by_access_token(self, access_token_id: int) -> list[Connection]:
        stmt = select(Connection).where(Connection.access_token_id == access_token_id)
        return list(self.db.scalars(stmt).all())

    def create(
        self,
        *,
        published_container_id: str,
        access_token_id: int,
        headscale_preauth_key_id: str,
        status: str = ConnectionStatus.PENDING,
        expires_at: Optional[datetime] = None,
    ) -> Connection:
        connection = Connection(
            published_container_id=published_container_id,
            access_token_id=access_token_id,
            headscale_preauth_key_id=headscale_preauth_key_id,
            status=status,
            expires_at=expires_at,
        )
        self.db.add(connection)
        self.db.flush()
        return connection

    def mark_connected(
        self,
        connection: Connection,
        connected_at: datetime,
    ) -> Connection:
        connection.status = ConnectionStatus.CONNECTED
        connection.connected_at = connected_at
        self.db.flush()
        return connection

