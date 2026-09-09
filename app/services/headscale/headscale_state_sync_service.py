import logging
from datetime import datetime, timezone
from typing import Optional, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.headscale import (
    IHeadscaleClient,
    RestHeadscaleClient,
)
from app.integrations.headscale.exceptions import HeadscaleError, HeadscaleConnectionError
from app.integrations.headscale.mapper import parse_datetime

from app.models.connection_status import ConnectionStatus
from app.models.headscale_node import HeadscaleNode as DbHeadscaleNode
from app.realtime.connection_manager import ConnectionManager
from app.realtime.protocol import WebSocketMessage
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.headscale_node_repository import HeadscaleNodeRepository
from app.repositories.headscale_user_repository import HeadscaleUserRepository

logger = logging.getLogger(__name__)


class HeadscaleStateSyncService:
    """Service with single responsibility: synchronize persisted Cloud state with real state returned by Headscale Control Server."""

    def __init__(
        self,
        db: Session,
        client: Optional[IHeadscaleClient] = None,
        connection_manager: Optional[ConnectionManager] = None,
    ) -> None:
        self.db = db
        self.connection_manager = connection_manager
        self.node_repo = HeadscaleNodeRepository(db)
        self.user_repo = HeadscaleUserRepository(db)
        self.connection_repo = ConnectionRepository(db)

        if client is not None:
            self.client = client
        else:
            settings = get_settings()
            self.client = RestHeadscaleClient(
                base_url=settings.headscale_url,
                api_key=settings.headscale_api_key,
                timeout=float(settings.headscale_timeout),
            )

    def _resolve_proxmox_container_id(self, node: DbHeadscaleNode) -> Optional[int]:
        if node.published_container and node.published_container.container_number:
            return node.published_container.container_number
        if node.published_container_id:
            from app.models.published_container import PublishedContainer
            pc = self.db.get(PublishedContainer, node.published_container_id)
            if pc and pc.container_number:
                return pc.container_number
        return None

    async def sync(self) -> dict[str, Any]:
        logger.info("[HEADSCALE_SYNC] Starting global Headscale state synchronization...")
        
        # 1. Fetch ALL nodes from Headscale Control Server in 1 single global HTTP call
        try:
            node_list_dto = self.client.list_nodes(user=None)
            api_nodes = node_list_dto.nodes
        except (HeadscaleConnectionError, HeadscaleError, Exception) as e:
            logger.warning(
                f"[HEADSCALE_SYNC] Headscale service unavailable or returned error: {e}. "
                "Retaining previous DB state without marking nodes offline."
            )
            return {
                "total_api_nodes": 0,
                "created": 0,
                "updated": 0,
                "online": 0,
                "offline": 0,
                "connections_bound": 0,
                "events_sent": 0,
                "error": True,
            }

        logger.info(f"[HEADSCALE_SYNC] Retrieved {len(api_nodes)} nodes from Headscale API.")

        # 2. Bulk load existing DB mappings to prevent N+1 queries
        db_users = {u.name: u for u in self.user_repo.list_all()}
        existing_db_nodes = self.node_repo.bulk_get_all_mapped()

        created_count = 0
        updated_count = 0
        online_count = 0
        offline_count = 0
        connections_bound = 0

        # Track environment deltas: dict[environment_id, list[dict]]
        environment_deltas: dict[str, list[dict[str, Any]]] = {}

        for api_node in api_nodes:
            # Determine Headscale user & Environment
            user_name = api_node.user.name if api_node.user else ""
            db_user = db_users.get(user_name)

            if not db_user and user_name.startswith("env_"):
                env_id_part = user_name.replace("env_", "")
                db_user = self.user_repo.get_by_environment(env_id_part)
                if db_user:
                    db_users[user_name] = db_user

            environment_id = db_user.environment_id if db_user else None

            # Try matching existing DB node by headscale_node_id, machine_key, or node_key
            mkey = getattr(api_node, "machineKey", None) or getattr(api_node, "machine_key", None)
            nkey = getattr(api_node, "nodeKey", None) or getattr(api_node, "node_key", None)
            given_name = getattr(api_node, "givenName", None) or getattr(api_node, "given_name", None) or api_node.name
            ip_addresses = getattr(api_node, "ipAddresses", None) or getattr(api_node, "ip_addresses", [])
            last_seen_dt = parse_datetime(getattr(api_node, "lastSeen", None) or getattr(api_node, "last_seen", None))
            expiry_dt = parse_datetime(getattr(api_node, "expiry", None))
            is_registered = not getattr(api_node, "invalid", False)

            db_node = (
                existing_db_nodes.get(str(api_node.id))
                or (existing_db_nodes.get(mkey) if mkey else None)
                or (existing_db_nodes.get(nkey) if nkey else None)
            )

            tailscale_ip = ip_addresses[0] if ip_addresses else None
            is_online = bool(api_node.online)
            if is_online:
                online_count += 1
            else:
                offline_count += 1

            if db_node:
                # Check if any attributes changed
                changed = (
                    db_node.online != is_online
                    or db_node.tailscale_ip != tailscale_ip
                    or db_node.hostname != given_name
                    or db_node.registered != is_registered
                )
                if changed:
                    only_online_changed = (
                        db_node.online != is_online
                        and db_node.tailscale_ip == tailscale_ip
                        and db_node.hostname == given_name
                    )
                    action = "NODE_STATUS_CHANGED" if only_online_changed else "NODE_UPDATED"

                    self.node_repo.update(
                        db_node,
                        machine_key=mkey,
                        node_key=nkey,
                        hostname=given_name,
                        given_name=given_name,
                        tailscale_ip=tailscale_ip,
                        online=is_online,
                        last_seen=last_seen_dt,
                        expiry=expiry_dt,
                        registered=is_registered,
                    )
                    updated_count += 1

                    if environment_id:
                        p_container_id = self._resolve_proxmox_container_id(db_node)
                        environment_deltas.setdefault(environment_id, []).append({
                            "action": action,
                            "node_id": db_node.id,
                            "headscale_node_id": str(api_node.id),
                            "hostname": db_node.hostname,
                            "online": is_online,
                            "tailscale_ip": tailscale_ip,
                            "proxmox_container_id": p_container_id,
                            "last_seen": last_seen_dt.isoformat() if last_seen_dt else None,
                        })
            else:
                # Create new DbHeadscaleNode if db_user exists
                if db_user:
                    new_node = self.node_repo.create(
                        headscale_node_id=str(api_node.id),
                        headscale_user_id=db_user.id,
                        machine_key=mkey,
                        node_key=nkey,
                        hostname=given_name,
                        given_name=given_name,
                        tailscale_ip=tailscale_ip,
                        online=is_online,
                        last_seen=last_seen_dt,
                        expiry=expiry_dt,
                        registered=is_registered,
                    )
                    existing_db_nodes[str(api_node.id)] = new_node
                    if mkey:
                        existing_db_nodes[mkey] = new_node
                    created_count += 1

                    if environment_id:
                        p_container_id = self._resolve_proxmox_container_id(new_node)
                        environment_deltas.setdefault(environment_id, []).append({
                            "action": "NODE_CREATED",
                            "node_id": new_node.id,
                            "headscale_node_id": str(api_node.id),
                            "hostname": new_node.hostname,
                            "online": is_online,
                            "tailscale_ip": tailscale_ip,
                            "proxmox_container_id": p_container_id,
                            "last_seen": last_seen_dt.isoformat() if last_seen_dt else None,
                        })
                    db_node = new_node

            # Match Connection: Bind any PENDING connection for this container/environment to db_node
            if db_node and environment_id:
                active_conns = self.connection_repo.list_active_by_environment(environment_id)
                for conn in active_conns:
                    if conn.status == ConnectionStatus.PENDING and conn.headscale_node_id is None:
                        conn.headscale_node_id = db_node.id
                        connections_bound += 1

        self.db.commit()

        # 3. Dispatch WebSocket deltas selectively per environment
        events_sent = 0
        if self.connection_manager and environment_deltas:
            for env_id, deltas in environment_deltas.items():
                if self.connection_manager.is_connected(env_id):
                    message = WebSocketMessage(
                        request_id=str(uuid4()),
                        origin="cloud",
                        type="node.status_changed",
                        version=1,
                        payload={
                            "environment_id": env_id,
                            "deltas": deltas,
                        },
                    )
                    await self.connection_manager.send(env_id, message)
                    events_sent += 1


        summary = {
            "total_api_nodes": len(api_nodes),
            "created": created_count,
            "updated": updated_count,
            "online": online_count,
            "offline": offline_count,
            "connections_bound": connections_bound,
            "events_sent": events_sent,
            "error": False,
        }
        logger.info(
            f"[HEADSCALE_SYNC] Headscale sync completed: nodes={len(api_nodes)} "
            f"created={created_count} updated={updated_count} online={online_count} "
            f"offline={offline_count} connections_bound={connections_bound} events_sent={events_sent}"
        )
        return summary
