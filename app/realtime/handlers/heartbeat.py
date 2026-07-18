from datetime import datetime, timezone
from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage, WebSocketResponse


class HeartbeatHandler:
    @staticmethod
    async def handle(connection: Connection, message: WebSocketMessage) -> None:
        # Update last heartbeat time
        connection.last_heartbeat = datetime.now(timezone.utc)
        
        # Respond to heartbeat
        response = WebSocketResponse(
            request_id=message.request_id,
            success=True,
            type="heartbeat.response",
            payload={}
        )
        await connection.websocket.send_text(response.model_dump_json())
