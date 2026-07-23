import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.headscale_user import HeadscaleUser as DbHeadscaleUser
from app.models.headscale_preauth_key import HeadscalePreAuthKey as DbHeadscalePreAuthKey
from app.models.headscale_node import HeadscaleNode as DbHeadscaleNode
from app.repositories.headscale_user_repository import HeadscaleUserRepository
from app.repositories.headscale_preauth_key_repository import HeadscalePreAuthKeyRepository
from app.repositories.headscale_node_repository import HeadscaleNodeRepository
from app.services.headscale.user_service import HeadscaleUserService
from app.services.headscale.preauthkey_service import HeadscalePreAuthKeyService
from app.services.headscale.node_service import HeadscaleNodeService

logger = logging.getLogger(__name__)


class HeadscaleProvisioningService:
    def __init__(
        self,
        db: Session,
        user_service: Optional[HeadscaleUserService] = None,
        preauthkey_service: Optional[HeadscalePreAuthKeyService] = None,
        node_service: Optional[HeadscaleNodeService] = None,
    ) -> None:
        self.db = db
        self.user_service = user_service or HeadscaleUserService(db)
        self.preauthkey_service = preauthkey_service or HeadscalePreAuthKeyService(db)
        self.node_service = node_service or HeadscaleNodeService(db)
        
        self.user_repo = HeadscaleUserRepository(db)
        self.key_repo = HeadscalePreAuthKeyRepository(db)
        self.node_repo = HeadscaleNodeRepository(db)

    def ensure_environment_user(self, environment_id: str, name: str) -> DbHeadscaleUser:
        logger.info(f"Ensuring Headscale user '{name}' exists for environment '{environment_id}'")
        db_user = self.user_repo.get_by_environment(environment_id)
        
        if db_user:
            logger.info(f"Headscale user '{name}' found in database (DB ID: {db_user.id}). Verifying in Headscale API...")
            try:
                self.user_service.get_user(db_user.name)
                logger.info(f"Headscale user '{db_user.name}' verified active in Headscale API.")
                return db_user
            except Exception as e:
                logger.warning(
                    f"Headscale user '{db_user.name}' recorded in DB but missing in Headscale API ({e}). Recreating in Headscale API..."
                )
                try:
                    api_user = self.user_service.create_user(environment_id, db_user.name)
                    logger.info(f"Re-created missing Headscale user '{db_user.name}' in API.")
                    return db_user
                except Exception as create_err:
                    logger.error(f"Failed to recreate missing user in Headscale API: {create_err}")
                    raise create_err

        try:
            logger.info(f"Checking if user '{name}' exists in Headscale API...")
            api_user = self.user_service.get_user(name)
            logger.info(f"User '{name}' exists in Headscale API. Persisting in DB...")
            db_user = self.user_repo.create(
                environment_id=environment_id,
                headscale_user_id=api_user.id,
                name=name
            )
            self.db.commit()
            logger.info(f"Headscale user '{name}' persisted successfully in DB")
        except Exception:
            logger.info(f"User '{name}' does not exist in Headscale API. Creating new user...")
            db_user = self.user_service.create_user(environment_id, name)
            
        return db_user

    def ensure_container_preauth_key(
        self,
        *,
        environment_id: str,
        published_container_id: str,
        reusable: bool = False,
        ephemeral: bool = False,
        expiration: Optional[datetime] = None,
    ) -> DbHeadscalePreAuthKey:
        logger.info(f"Ensuring PreAuthKey exists for container '{published_container_id}' in environment '{environment_id}'")
        
        db_user = self.user_repo.get_by_environment(environment_id)
        if not db_user:
            raise ValueError(f"No Headscale user found registered for environment '{environment_id}'")

        existing_keys = self.key_repo.get_by_container(published_container_id)
        active_key = None
        now = datetime.now(timezone.utc)
        
        for k in existing_keys:
            if not k.used and k.expiration is not None:
                exp = k.expiration if k.expiration.tzinfo is not None else k.expiration.replace(tzinfo=timezone.utc)
                if exp > now:
                    active_key = k
                    break

        if active_key:
            key_snippet = active_key.key_name[:8] + "..." if len(active_key.key_name) > 8 else "..."
            logger.info(f"Found active PreAuthKey {key_snippet} for container '{published_container_id}' in database")
            return active_key

        if expiration is None:
            expiration = datetime.now(timezone.utc) + timedelta(hours=24)

        logger.info(f"No active PreAuthKey found for container '{published_container_id}'. Requesting new key from Headscale (expires: {expiration})...")
        db_key = self.preauthkey_service.create(
            headscale_user_db_id=db_user.id,
            user_name=db_user.name,
            published_container_id=published_container_id,
            reusable=reusable,
            ephemeral=ephemeral,
            expiration=expiration,
        )
        return db_key

    def sync_registered_node(
        self,
        *,
        headscale_user_db_id: str,
        published_container_id: Optional[str] = None,
        headscale_node_id: str,
        machine_key: Optional[str] = None,
        node_key: Optional[str] = None,
        hostname: str,
        given_name: Optional[str] = None,
        last_seen: Optional[datetime] = None,
        expiry: Optional[datetime] = None,
        registered: bool = False,
    ) -> DbHeadscaleNode:
        logger.info(f"Synchronizing registered node '{headscale_node_id}' in database (hostname: '{hostname}')")
        return self.node_service.sync_registered_node(
            headscale_user_db_id=headscale_user_db_id,
            published_container_id=published_container_id,
            headscale_node_id=headscale_node_id,
            machine_key=machine_key,
            node_key=node_key,
            hostname=hostname,
            given_name=given_name,
            last_seen=last_seen,
            expiry=expiry,
            registered=registered,
        )

    def remove_container(self, published_container_id: str) -> None:
        logger.info(f"Removing container registration: '{published_container_id}' from Headscale")
        
        db_node = self.node_repo.get_by_container(published_container_id)
        if db_node:
            logger.info(f"Removing node '{db_node.headscale_node_id}' from Headscale...")
            self.node_service.delete(db_node.headscale_node_id)
        else:
            logger.info(f"No HeadscaleNode found in DB for container '{published_container_id}'")

        db_keys = self.key_repo.get_by_container(published_container_id)
        for key in db_keys:
            if not key.used:
                key_snippet = key.key_name[:8] + "..." if len(key.key_name) > 8 else "..."
                logger.info(f"Expiring unused key {key_snippet} for container '{published_container_id}'...")
                try:
                    self.preauthkey_service.expire(key.headscale_user.name, key.key_name)
                except Exception as e:
                    logger.error(f"Failed to expire PreAuthKey on Headscale API: {e}")

        logger.info(f"Container '{published_container_id}' registration cleanup completed")

    def remove_environment(self, environment_id: str) -> None:
        logger.info(f"Removing environment '{environment_id}' from Headscale")
        
        db_user = self.user_repo.get_by_environment(environment_id)
        if db_user:
            logger.info(f"Deleting Headscale user '{db_user.name}' from API and database...")
            self.user_service.delete_user(db_user.name)
        else:
            logger.info(f"No Headscale user found in database for environment '{environment_id}'")

    def revoke_container_key(self, published_container_id: str, key_name: str) -> None:
        key_snippet = key_name[:8] + "..." if len(key_name) > 8 else "..."
        logger.info(f"Revoking key {key_snippet} for container '{published_container_id}'")
        
        db_key = self.key_repo.get_by_headscale_id(key_name)
        if not db_key:
            raise ValueError(f"PreAuthKey '{key_name}' not found in database to revoke")
            
        self.preauthkey_service.expire(db_key.headscale_user.name, key_name)
        logger.info("Key revoked successfully")

    def provision_environment(
        self,
        environment_id: str,
        user_name: str,
        reusable: bool = False,
        ephemeral: bool = False,
        expiration: Optional[datetime] = None,
    ) -> tuple[DbHeadscaleUser, DbHeadscalePreAuthKey]:
        logger.info(f"Provisioning environment: starting orchestration for user '{user_name}' (ID: '{environment_id}')")
        
        db_user = self.ensure_environment_user(environment_id, user_name)
        db_key = self.preauthkey_service.create(
            headscale_user_db_id=db_user.id,
            user_name=db_user.name,
            reusable=reusable,
            ephemeral=ephemeral,
            expiration=expiration,
        )
        return db_user, db_key
