import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.dto.client_connection import (
    ClientConnectionConfirmRequestDTO,
    ClientConnectionConfirmResponseDTO,
    ValidationCode,
)
from app.models.connection_status import ConnectionStatus
from app.repositories.connection_repository import ConnectionRepository

logger = logging.getLogger(__name__)


class ClientConnectionConfirmService:
    """Service responsible solely for confirming a client connection handshake after tailscale up."""

    def __init__(
        self,
        db: Session,
        connection_repo: Optional[ConnectionRepository] = None,
    ) -> None:
        self.db = db
        self.connection_repo = connection_repo or ConnectionRepository(db)

    def confirm(
        self, request: ClientConnectionConfirmRequestDTO
    ) -> ClientConnectionConfirmResponseDTO:
        logger.info(f"Processing client connection confirmation handshake for Connection ID: {request.connection_id}")

        connection = self.connection_repo.get_by_id(request.connection_id)
        if not connection:
            logger.warning(f"Connection confirmation failed: Connection ID {request.connection_id} not found.")
            return ClientConnectionConfirmResponseDTO(
                success=False,
                connection_id=request.connection_id,
                status="UNKNOWN",
                code=ValidationCode.CONNECTION_NOT_FOUND,
                message="Connection record not found.",
            )

        # Idempotency check: if already CONNECTED, return success without altering DB
        if connection.status == ConnectionStatus.CONNECTED:
            logger.info(f"Connection ID {connection.id} is already in CONNECTED status (idempotent request).")
            connected_at_str = connection.connected_at.isoformat() if connection.connected_at else None
            return ClientConnectionConfirmResponseDTO(
                success=True,
                connection_id=connection.id,
                status=connection.status,
                connected_at=connected_at_str,
                message="Connection already confirmed.",
            )

        # Expiration check: validate expires_at without altering DB status
        if connection.expires_at is not None:
            exp = connection.expires_at if connection.expires_at.tzinfo is not None else connection.expires_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if exp <= now:
                logger.warning(f"Connection confirmation failed: Connection ID {connection.id} has expired.")
                return ClientConnectionConfirmResponseDTO(
                    success=False,
                    connection_id=connection.id,
                    status=connection.status,
                    code=ValidationCode.CONNECTION_EXPIRED,
                    message="Connection authorization has expired.",
                )

        now = datetime.now(timezone.utc)
        self.connection_repo.mark_connected(connection, connected_at=now)
        self.db.commit()

        # Domain event publication / log
        logger.info(
            f"[Domain Event] ClientConnectionConfirmed - Connection ID: {connection.id} | "
            f"Container ID: {connection.published_container_id} | "
            f"Token ID: {connection.access_token_id} | "
            f"Connected At: {now.isoformat()}"
        )

        return ClientConnectionConfirmResponseDTO(
            success=True,
            connection_id=connection.id,
            status=ConnectionStatus.CONNECTED,
            connected_at=now.isoformat(),
        )
