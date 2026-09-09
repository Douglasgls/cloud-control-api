import logging
from datetime import datetime, timezone
from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage, WebSocketResponse, WebSocketError, WebSocketErrorDetail
from app.db.database import SessionLocal
from app.services.headscale.node_service import HeadscaleNodeService

logger = logging.getLogger(__name__)


class NodeSyncHandler:
    @staticmethod
    async def handle(connection: Connection, message: WebSocketMessage) -> None:
        if not connection.environment_id:
            logger.error("Connection lacks environment_id for node.sync.request")
            return
            
        req_id = message.request_id or "legacy"
        logger.info(f"Processing node.sync.request for environment {connection.environment_id}")
        
        try:
            with SessionLocal() as db:
                node_service = HeadscaleNodeService(db)
                # 1. Fetch from Headscale API directly for the environment user
                api_nodes = node_service.list(user=connection.environment_id)
                
                payload_nodes = []
                for node in api_nodes:
                    # Parse dates
                    last_seen_str = node.last_seen.isoformat().replace("+00:00", "Z") if node.last_seen else "N/A"
                    expiry_str = node.expiry.isoformat().replace("+00:00", "Z") if node.expiry else "N/A"
                    
                    # Verify expiration
                    is_expired = False
                    if node.expiry and node.expiry < datetime.now(timezone.utc):
                        is_expired = True

                    # IPv4 tailscale IP
                    tailscale_ip = None
                    for ip in node.ip_addresses:
                        if "." in ip:  # Basic IPv4 check
                            tailscale_ip = ip
                            break
                    if not tailscale_ip and node.ip_addresses:
                        tailscale_ip = node.ip_addresses[0]

                    # Note: We send null for api_local_container_id as per option 2
                    payload_nodes.append({
                        "headscale_node_id": node.id,
                        "hostname": node.given_name or node.name,
                        "name": node.name,
                        "machine_key": node.machine_key,
                        "node_key": node.node_key,
                        "user": connection.environment_id,
                        "tags": node.valid_tags + node.forced_tags,
                        "tailscale_ip": tailscale_ip,
                        "ephemeral": False,  # Not directly provided by node list natively, defaulting
                        "last_seen": last_seen_str,
                        "expiration": expiry_str,
                        "online": node.online,
                        "expired": is_expired,
                        "api_local_container_id": None
                    })
                
                response = WebSocketResponse(
                    request_id=req_id,
                    origin="cloud",
                    type="node.sync.response",
                    success=True,
                    payload={"nodes": payload_nodes}
                )
                
                await connection.websocket.send_text(response.model_dump_json())
                logger.info(f"Sent node.sync.response with {len(payload_nodes)} nodes for environment {connection.environment_id}")

        except Exception as e:
            logger.error(f"Failed to process node.sync.request: {e}", exc_info=True)
            error_response = WebSocketError(
                request_id=req_id,
                origin="cloud",
                success=False,
                error=WebSocketErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message=f"Failed to process node sync request: {str(e)}"
                )
            )
            await connection.websocket.send_text(error_response.model_dump_json())
