import logging
from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage, WebSocketResponse, WebSocketError, WebSocketErrorDetail
from app.realtime.dto.event import EventPublishDTO

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, realtime_manager) -> None:
        self.realtime_manager = realtime_manager

    async def handle(self, connection: Connection, message: WebSocketMessage) -> None:
        req_id = message.request_id or "legacy"

        # 1. Validate JWT / Connection identity
        if not connection.environment_id or not connection.user_id:
            logger.error("Connection lacks environment_id or user_id (unauthorized/invalid JWT)")
            error_response = WebSocketError(
                request_id=req_id,
                origin="cloud",
                success=False,
                error=WebSocketErrorDetail(
                    code="UNAUTHORIZED",
                    message="Connection is not authenticated"
                )
            )
            await connection.websocket.send_text(error_response.model_dump_json())
            return

        # 2. Validate Connection is active
        if not self.realtime_manager.connection_manager.is_connected(connection.environment_id):
            logger.error(f"Connection for environment {connection.environment_id} is not active")
            error_response = WebSocketError(
                request_id=req_id,
                origin="cloud",
                success=False,
                error=WebSocketErrorDetail(
                    code="DISCONNECTED",
                    message="Connection is not active"
                )
            )
            await connection.websocket.send_text(error_response.model_dump_json())
            return

        # 3. Validate Payload (if type is event.publish)
        if message.type == "event.publish":
            try:
                EventPublishDTO.model_validate(message.payload)
                print(f"\n[EVENT RECEBIDO] Evento: {message.payload.get('event')} | Recurso: {message.payload.get('resource')} | Metadata: {message.payload.get('metadata')}")
                print(f"Dados do evento: {message.model_dump_json()}\n")
            except Exception as e:
                logger.error(f"Payload validation failed for event.publish: {e}")
                error_response = WebSocketError(
                    request_id=req_id,
                    origin="cloud",
                    success=False,
                    error=WebSocketErrorDetail(
                        code="VALIDATION_ERROR",
                        message=f"Invalid event publish payload: {str(e)}"
                    )
                )
                await connection.websocket.send_text(error_response.model_dump_json())
                return
        elif message.type == "environment.changed":
            print(f"\n[EVENT RECEBIDO] Evento: environment.changed")
            print(f"Dados do evento: {message.model_dump_json()}\n")

        # 4. Respond ACK immediately
        ack = WebSocketResponse(
            request_id=req_id,
            origin="cloud",
            success=True,
            payload={}
        )
        await connection.websocket.send_text(ack.model_dump_json())
        logger.info(f"ACK sent for {message.type} (request_id={req_id})")

        # 5. Trigger environment sync asynchronously
        logger.info(f"Triggering environment sync for environment {connection.environment_id}")
        self.realtime_manager.trigger_environment_sync(connection)
