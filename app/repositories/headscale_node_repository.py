from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.headscale_node import HeadscaleNode
from app.models.headscale_user import HeadscaleUser


class HeadscaleNodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, node_id: str) -> HeadscaleNode | None:
        return self.db.get(HeadscaleNode, node_id)

    def get_by_headscale_id(self, headscale_node_id: str) -> HeadscaleNode | None:
        return self.db.scalar(
            select(HeadscaleNode).where(HeadscaleNode.headscale_node_id == headscale_node_id)
        )

    def get_by_container(self, published_container_id: str) -> HeadscaleNode | None:
        return self.db.scalar(
            select(HeadscaleNode).where(HeadscaleNode.published_container_id == published_container_id)
        )

    def get_by_environment(self, environment_id: str) -> list[HeadscaleNode]:
        return list(
            self.db.scalars(
                select(HeadscaleNode)
                .join(HeadscaleUser)
                .where(HeadscaleUser.environment_id == environment_id)
            ).all()
        )

    def get_by_machine_key(self, machine_key: str) -> HeadscaleNode | None:
        return self.db.scalar(
            select(HeadscaleNode).where(HeadscaleNode.machine_key == machine_key)
        )

    def get_by_node_key(self, node_key: str) -> HeadscaleNode | None:
        return self.db.scalar(
            select(HeadscaleNode).where(HeadscaleNode.node_key == node_key)
        )

    def bulk_get_all_mapped(self) -> dict[str, HeadscaleNode]:
        nodes = list(self.db.scalars(select(HeadscaleNode)).all())
        mapped = {}
        for n in nodes:
            if n.headscale_node_id:
                mapped[str(n.headscale_node_id)] = n
            if n.machine_key:
                mapped[n.machine_key] = n
            if n.node_key:
                mapped[n.node_key] = n
        return mapped

    def create(
        self,
        *,
        published_container_id: Optional[str] = None,
        headscale_node_id: str,
        headscale_user_id: str,
        machine_key: Optional[str] = None,
        node_key: Optional[str] = None,
        hostname: str,
        given_name: Optional[str] = None,
        tailscale_ip: Optional[str] = None,
        online: bool = False,
        last_seen: Optional[datetime] = None,
        expiry: Optional[datetime] = None,
        registered: bool = False
    ) -> HeadscaleNode:
        node = HeadscaleNode(
            published_container_id=published_container_id,
            headscale_node_id=headscale_node_id,
            headscale_user_id=headscale_user_id,
            machine_key=machine_key,
            node_key=node_key,
            hostname=hostname,
            given_name=given_name,
            tailscale_ip=tailscale_ip,
            online=online,
            last_seen=last_seen,
            expiry=expiry,
            registered=registered
        )
        self.db.add(node)
        self.db.flush()
        return node

    def update(
        self,
        node: HeadscaleNode,
        *,
        machine_key: Optional[str] = None,
        node_key: Optional[str] = None,
        hostname: str,
        given_name: Optional[str] = None,
        tailscale_ip: Optional[str] = None,
        online: bool = False,
        last_seen: Optional[datetime] = None,
        expiry: Optional[datetime] = None,
        registered: bool
    ) -> HeadscaleNode:
        node.machine_key = machine_key
        node.node_key = node_key
        node.hostname = hostname
        node.given_name = given_name
        node.tailscale_ip = tailscale_ip
        node.online = online
        node.last_seen = last_seen
        node.expiry = expiry
        node.registered = registered
        self.db.flush()
        return node


    def delete(self, node: HeadscaleNode) -> None:
        self.db.delete(node)
        self.db.flush()
