from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage, WebSocketResponse


class SystemHandler:
    @staticmethod
    async def handle_info(connection: Connection, message: WebSocketMessage) -> None:
        # Dummy implementation for future extension
        response = WebSocketResponse(
            request_id=message.request_id,
            success=True,
            type="system.info.response",
            payload={"status": "ok", "version": "1.0.0"}
        )
        await connection.websocket.send_text(response.model_dump_json())
