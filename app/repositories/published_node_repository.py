from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.published_node import PublishedNode


class PublishedNodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_container_id(self, published_container_id: int) -> PublishedNode | None:
        return self.db.scalar(
            select(PublishedNode).where(PublishedNode.published_container_id == published_container_id)
        )

    def create(
        self,
        *,
        published_container_id: int,
        installed: bool,
        service_running: bool,
        version: str | None = None,
        machine_id: str | None = None,
        node_key: str | None = None,
        tailscale_ip: str | None = None,
        online: bool = False,
        last_sync: datetime | None = None
    ) -> PublishedNode:
        node = PublishedNode(
            published_container_id=published_container_id,
            installed=installed,
            service_running=service_running,
            version=version,
            machine_id=machine_id,
            node_key=node_key,
            tailscale_ip=tailscale_ip,
            online=online,
            last_sync=last_sync
        )
        self.db.add(node)
        self.db.flush()
        return node

    def update(
        self,
        node: PublishedNode,
        *,
        installed: bool,
        service_running: bool,
        version: str | None = None,
        machine_id: str | None = None,
        node_key: str | None = None,
        tailscale_ip: str | None = None,
        online: bool = False,
        last_sync: datetime | None = None
    ) -> PublishedNode:
        node.installed = installed
        node.service_running = service_running
        node.version = version
        node.machine_id = machine_id
        node.node_key = node_key
        node.tailscale_ip = tailscale_ip
        node.online = online
        node.last_sync = last_sync
        self.db.flush()
        return node
