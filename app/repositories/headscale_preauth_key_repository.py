from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.models.headscale_user import HeadscaleUser


class HeadscalePreAuthKeyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, key_id: str) -> HeadscalePreAuthKey | None:
        return self.db.get(HeadscalePreAuthKey, key_id)

    def get_by_headscale_id(self, headscale_key_id: str) -> HeadscalePreAuthKey | None:
        return self.db.scalar(
            select(HeadscalePreAuthKey).where(HeadscalePreAuthKey.headscale_key_id == headscale_key_id)
        )

    def get_by_container(self, published_container_id: str) -> list[HeadscalePreAuthKey]:
        return list(
            self.db.scalars(
                select(HeadscalePreAuthKey).where(HeadscalePreAuthKey.published_container_id == published_container_id)
            ).all()
        )

    def get_by_environment(self, environment_id: str) -> list[HeadscalePreAuthKey]:
        return list(
            self.db.scalars(
                select(HeadscalePreAuthKey)
                .join(HeadscaleUser)
                .where(HeadscaleUser.environment_id == environment_id)
            ).all()
        )

    def create(
        self,
        *,
        headscale_user_id: str,
        published_container_id: Optional[str] = None,
        headscale_key_id: str,
        key_name: str,
        reusable: bool,
        ephemeral: bool,
        used: bool = False,
        expiration: Optional[datetime] = None
    ) -> HeadscalePreAuthKey:
        key = HeadscalePreAuthKey(
            headscale_user_id=headscale_user_id,
            published_container_id=published_container_id,
            headscale_key_id=headscale_key_id,
            key_name=key_name,
            reusable=reusable,
            ephemeral=ephemeral,
            used=used,
            expiration=expiration
        )
        self.db.add(key)
        self.db.flush()
        return key

    def update(self, key: HeadscalePreAuthKey, *, used: bool) -> HeadscalePreAuthKey:
        key.used = used
        self.db.flush()
        return key

    def delete(self, key: HeadscalePreAuthKey) -> None:
        self.db.delete(key)
        self.db.flush()
