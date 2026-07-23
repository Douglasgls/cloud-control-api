import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.headscale import (
    IHeadscaleClient,
    RestHeadscaleClient,
    HeadscaleMapper,
    HeadscaleNode as IntegrationNode,
)
from app.models.headscale_node import HeadscaleNode as DbHeadscaleNode
from app.repositories.headscale_node_repository import HeadscaleNodeRepository

logger = logging.getLogger(__name__)


class HeadscaleNodeService:
    def __init__(self, db: Session, client: Optional[IHeadscaleClient] = None) -> None:
        self.db = db
        self.repository = HeadscaleNodeRepository(db)
        if client is not None:
            self.client = client
        else:
            settings = get_settings()
            self.client = RestHeadscaleClient(
                base_url=settings.headscale_url,
                api_key=settings.headscale_api_key,
                timeout=float(settings.headscale_timeout),
            )

    def list(self, user: Optional[str] = None) -> list[IntegrationNode]:
        logger.info(f"Listing nodes from Headscale API (user filter: {user})")
        dto_list = self.client.list_nodes(user)
        nodes = [HeadscaleMapper.to_node(n) for n in dto_list.nodes]
        logger.info(f"Retrieved {len(nodes)} nodes from Headscale API")
        return nodes

    def get(self, node_id: str) -> IntegrationNode:
        logger.info(f"Getting node '{node_id}' details from Headscale API")
        dto = self.client.get_node(node_id)
        node = HeadscaleMapper.to_node(dto)
        logger.info(f"Node '{node_id}' details retrieved successfully (Name: '{node.name}')")
        return node

    def delete(self, node_id: str) -> None:
        logger.info(f"Removing node '{node_id}' from Headscale")
        self.client.delete_node(node_id)
        
        # Remove from database
        db_node = self.repository.get_by_headscale_id(node_id)
        if db_node:
            self.repository.delete(db_node)
            self.db.commit()
            logger.info(f"Node '{node_id}' deleted successfully from database")
        else:
            logger.warning(f"Node '{node_id}' not found in database for deletion")

    def rename(self, node_id: str, new_name: str) -> IntegrationNode:
        logger.info(f"Renaming node '{node_id}' to '{new_name}' in Headscale")
        dto = self.client.rename_node(node_id, new_name)
        node = HeadscaleMapper.to_node(dto)
        
        # Update database representation if it exists
        db_node = self.repository.get_by_headscale_id(node_id)
        if db_node:
            self.repository.update(
                db_node,
                machine_key=db_node.machine_key,
                node_key=db_node.node_key,
                hostname=new_name,
                given_name=db_node.given_name,
                last_seen=db_node.last_seen,
                expiry=db_node.expiry,
                registered=db_node.registered
            )
            self.db.commit()
            logger.info("Node hostname updated successfully in database")
            
        return node

    def move(self, node_id: str, user: str) -> IntegrationNode:
        logger.info(f"Moving node '{node_id}' to user '{user}' in Headscale")
        dto = self.client.move_node(node_id, user)
        node = HeadscaleMapper.to_node(dto)
        logger.info(f"Node '{node_id}' moved successfully to user '{user}' (re-sync needed on DB)")
        return node

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
        registered: bool = False
    ) -> DbHeadscaleNode:
        logger.info(f"Synchronizing node '{headscale_node_id}' in DB (hostname: '{hostname}')")
        
        existing = self.repository.get_by_headscale_id(headscale_node_id)
        if existing:
            db_node = self.repository.update(
                existing,
                machine_key=machine_key,
                node_key=node_key,
                hostname=hostname,
                given_name=given_name,
                last_seen=last_seen,
                expiry=expiry,
                registered=registered
            )
            logger.info(f"Node '{headscale_node_id}' updated successfully in DB")
        else:
            db_node = self.repository.create(
                published_container_id=published_container_id,
                headscale_node_id=headscale_node_id,
                headscale_user_id=headscale_user_db_id,
                machine_key=machine_key,
                node_key=node_key,
                hostname=hostname,
                given_name=given_name,
                last_seen=last_seen,
                expiry=expiry,
                registered=registered
            )
            logger.info(f"Node '{headscale_node_id}' created successfully in DB")
            
        self.db.flush()
        return db_node
