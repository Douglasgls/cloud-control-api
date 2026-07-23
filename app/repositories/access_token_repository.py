from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.access_token import AccessToken


class AccessTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_hash(self, token_hash: str) -> AccessToken | None:
        return self.db.scalar(
            select(AccessToken).where(AccessToken.token_hash == token_hash)
        )

    def create(
        self,
        *,
        published_container_id: str,
        api_local_token_id: str | None,
        token_hash: str,
        expires_at: datetime | None,
        active: bool,
        revoked_at: datetime | None
    ) -> AccessToken:
        token = AccessToken(
            published_container_id=published_container_id,
            api_local_token_id=api_local_token_id,
            token_hash=token_hash,
            expires_at=expires_at,
            active=active,
            revoked_at=revoked_at
        )
        self.db.add(token)
        self.db.flush()
        return token

    def update(
        self,
        token: AccessToken,
        *,
        api_local_token_id: str | None,
        expires_at: datetime | None,
        active: bool,
        revoked_at: datetime | None
    ) -> AccessToken:
        token.api_local_token_id = api_local_token_id
        token.expires_at = expires_at
        token.active = active
        token.revoked_at = revoked_at
        self.db.flush()
        return token
