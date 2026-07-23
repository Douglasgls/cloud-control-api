import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.headscale import (
    IHeadscaleClient,
    RestHeadscaleClient,
    HeadscaleMapper,
    HeadscalePreAuthKey as IntegrationPreAuthKey,
)
from app.models.headscale_preauth_key import HeadscalePreAuthKey as DbHeadscalePreAuthKey
from app.repositories.headscale_preauth_key_repository import HeadscalePreAuthKeyRepository
from app.repositories.headscale_user_repository import HeadscaleUserRepository

logger = logging.getLogger(__name__)


class HeadscalePreAuthKeyService:
    def __init__(self, db: Session, client: Optional[IHeadscaleClient] = None) -> None:
        self.db = db
        self.repository = HeadscalePreAuthKeyRepository(db)
        if client is not None:
            self.client = client
        else:
            settings = get_settings()
            self.client = RestHeadscaleClient(
                base_url=settings.headscale_url,
                api_key=settings.headscale_api_key,
                timeout=float(settings.headscale_timeout),
            )

    def create(
        self,
        *,
        headscale_user_db_id: str,
        user_name: str,
        published_container_id: Optional[str] = None,
        reusable: bool = False,
        ephemeral: bool = False,
        expiration: Optional[datetime] = None,
    ) -> DbHeadscalePreAuthKey:
        user_repo = HeadscaleUserRepository(self.db)
        db_user = user_repo.get_by_id(headscale_user_db_id)
        user_identifier = db_user.headscale_user_id if db_user and db_user.headscale_user_id else user_name

        logger.info(f"Generating PreAuthKey in Headscale for user '{user_name}' (identifier: {user_identifier}, reusable={reusable}, ephemeral={ephemeral})")
        dto = self.client.create_preauth_key(
            user=user_identifier,
            reusable=reusable,
            ephemeral=ephemeral,
            expiration=expiration,
        )
        
        # Mask the generated key for logs
        key_snippet = dto.key[:8] + "..." if len(dto.key) > 8 else "..."
        logger.info(f"Persisting PreAuthKey {key_snippet} in database for user DB ID: {headscale_user_db_id}")
        
        db_key = self.repository.create(
            headscale_user_id=headscale_user_db_id,
            published_container_id=published_container_id,
            headscale_key_id=dto.id,
            key_name=dto.key,
            reusable=reusable,
            ephemeral=ephemeral,
            used=dto.used,
            expiration=expiration
        )
        self.db.commit()
        logger.info(f"PreAuthKey persisted successfully in database (DB ID: {db_key.id})")
        return db_key

    def expire(self, user_name: str, key_name: str) -> None:
        key_snippet = key_name[:8] + "..." if len(key_name) > 8 else "..."
        logger.info(f"Expiring PreAuthKey {key_snippet} for user '{user_name}'")
        self.client.expire_preauth_key(user_name, key_name)
        
        db_key = self.repository.get_by_headscale_id(key_name)
        if db_key:
            self.repository.update(db_key, used=True)
            self.db.commit()
            logger.info("PreAuthKey expired and updated in database successfully")
        else:
            logger.warning("PreAuthKey to expire was not found in database")

    def list(self, user_name: str) -> list[IntegrationPreAuthKey]:
        logger.info(f"Listing PreAuthKeys from API for user '{user_name}'")
        dto_list = self.client.list_preauth_keys(user_name)
        keys = [HeadscaleMapper.to_preauth_key(k) for k in dto_list.preauthKeys]
        logger.info(f"Retrieved {len(keys)} PreAuthKeys from Headscale API")
        return keys
