import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.dtos.environment_sync import PublishedAccessTokenSnapshotDTO
from app.models.access_token import AccessToken
from app.repositories.access_token_repository import AccessTokenRepository

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


class AccessTokenSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AccessTokenRepository(db)

    def sync_tokens(self, published_container_id: str, tokens_dto: list[PublishedAccessTokenSnapshotDTO]) -> list[AccessToken]:
        synced_tokens = []

        for token_dto in tokens_dto:
            existing = self.repository.get_by_hash(token_dto.token_hash)
            expires_at = parse_datetime(token_dto.expires_at)
            revoked_at = parse_datetime(token_dto.revoked_at)

            # Mask hash for logs
            hash_prefix = f"{token_dto.token_hash[:8]}..." if len(token_dto.token_hash) > 8 else token_dto.token_hash

            if existing:
                has_changes = (
                    existing.published_container_id != published_container_id or
                    existing.api_local_token_id != token_dto.id or
                    existing.expires_at != expires_at or
                    existing.active != token_dto.active or
                    existing.revoked_at != revoked_at
                )

                if has_changes:
                    self.repository.update(
                        existing,
                        api_local_token_id=token_dto.id,
                        expires_at=expires_at,
                        active=token_dto.active,
                        revoked_at=revoked_at
                    )
                    # Re-associate if moved to a different container
                    if existing.published_container_id != published_container_id:
                        existing.published_container_id = published_container_id
                        self.db.flush()

                    logger.info(f"Access token {hash_prefix} updated for container ID: {published_container_id}")
                else:
                    logger.debug(f"Access token {hash_prefix} synchronized (no changes) for container ID: {published_container_id}")
                
                synced_tokens.append(existing)
            else:
                new_token = self.repository.create(
                    published_container_id=published_container_id,
                    api_local_token_id=token_dto.id,
                    token_hash=token_dto.token_hash,
                    expires_at=expires_at,
                    active=token_dto.active,
                    revoked_at=revoked_at
                )
                logger.info(f"Access token {hash_prefix} created for container ID: {published_container_id}")
                synced_tokens.append(new_token)

        return synced_tokens
