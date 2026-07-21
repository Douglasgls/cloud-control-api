import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.dto.client_connection import ValidationResult

logger = logging.getLogger(__name__)


class ConnectionAuditService:
    """Logs structured audit info and records connection attempts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_attempt(
        self,
        result: ValidationResult,
        raw_token: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        context = result.context
        token_hash = context.token_hash if context else None
        hash_prefix = f"{token_hash[:8]}..." if token_hash and len(token_hash) >= 8 else "unknown"

        env_id = context.environment.id if context and context.environment else None
        container_id = context.published_container.id if context and context.published_container else None
        node_id = context.published_node.id if context and context.published_node else None

        if result.allowed:
            logger.info(
                f"[Audit] Connection AUTHORIZED - Token Prefix: {hash_prefix} | "
                f"Env: {env_id} | Container: {container_id} | Node: {node_id} | IP: {ip_address}"
            )
        else:
            logger.warning(
                f"[Audit] Connection DENIED - Code: {result.code} - Message: '{result.message}' | "
                f"Token Prefix: {hash_prefix} | Env: {env_id} | Container: {container_id} | Node: {node_id} | IP: {ip_address}"
            )
