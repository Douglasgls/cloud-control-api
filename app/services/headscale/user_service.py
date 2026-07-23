import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import get_settings
from app.integrations.headscale import (
    IHeadscaleClient,
    RestHeadscaleClient,
    HeadscaleMapper,
    HeadscaleUser as IntegrationUser,
)
from app.models.headscale_user import HeadscaleUser as DbHeadscaleUser
from app.repositories.headscale_user_repository import HeadscaleUserRepository

logger = logging.getLogger(__name__)


class HeadscaleUserService:
    def __init__(self, db: Session, client: Optional[IHeadscaleClient] = None) -> None:
        self.db = db
        self.repository = HeadscaleUserRepository(db)
        if client is not None:
            self.client = client
        else:
            settings = get_settings()
            self.client = RestHeadscaleClient(
                base_url=settings.headscale_url,
                api_key=settings.headscale_api_key,
                timeout=float(settings.headscale_timeout),
            )

    def create_user(self, environment_id: str, name: str) -> DbHeadscaleUser:
        logger.info(f"Creating Headscale user: '{name}' for environment '{environment_id}'")
        dto = self.client.create_user(name)
        db_user = self.repository.create(
            environment_id=environment_id,
            headscale_user_id=dto.id,
            name=name
        )
        self.db.commit()
        logger.info(f"User '{name}' created successfully in Headscale and DB (DB ID: {db_user.id})")
        return db_user

    def list_users(self) -> list[IntegrationUser]:
        logger.info("Listing Headscale users from API")
        dto_list = self.client.list_users()
        users = [HeadscaleMapper.to_user(u) for u in dto_list.users]
        logger.info(f"Retrieved {len(users)} users from Headscale API")
        return users

    def get_user(self, name: str) -> IntegrationUser:
        logger.info(f"Getting Headscale user from API: '{name}'")
        dto = self.client.get_user(name)
        user = HeadscaleMapper.to_user(dto)
        logger.info(f"User '{name}' retrieved successfully from API (API ID: {user.id})")
        return user

    def delete_user(self, name: str) -> None:
        logger.info(f"Deleting Headscale user: '{name}'")
        self.client.delete_user(name)
        db_user = self.repository.get_by_name(name)
        if db_user:
            self.repository.delete(db_user)
            self.db.commit()
            logger.info(f"User '{name}' deleted successfully from database")
        else:
            logger.warning(f"User '{name}' not found in database for deletion")

    def rename_user(self, old_name: str, new_name: str) -> DbHeadscaleUser:
        logger.info(f"Renaming Headscale user '{old_name}' to '{new_name}'")
        dto = self.client.rename_user(old_name, new_name)
        db_user = self.repository.get_by_name(old_name)
        if db_user:
            self.repository.update(db_user, name=new_name)
            self.db.commit()
            logger.info(f"User renamed successfully in database from '{old_name}' to '{new_name}'")
            return db_user
        else:
            raise ValueError(f"User '{old_name}' not found in database to rename")
