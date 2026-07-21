import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from app.models.access_token import AccessToken
from app.repositories.access_token_repository import AccessTokenRepository


class AccessTokenResolver:
    """Resolves a raw access token string to a database AccessToken entity."""

    def __init__(self, db: Session) -> None:
        self.repository = AccessTokenRepository(db)

    def hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def resolve(self, raw_token: str) -> tuple[str, Optional[AccessToken]]:
        token_hash = self.hash_token(raw_token)
        access_token = self.repository.get_by_hash(token_hash)
        return token_hash, access_token
