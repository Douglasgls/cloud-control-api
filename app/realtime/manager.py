import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

from app.db.database import SessionLocal
from app.dtos.environment_sync import EnvironmentSnapshotDTO
from app.realtime.models import Connection
from app.realtime.connection_manager import ConnectionManager
from app.realtime.dispatcher import Dispatcher
from app.realtime.protocol import WebSocketMessage, WebSocketResponse
from app.services.environment_service import EnvironmentService
from app.services.environment_sync_service import EnvironmentSyncService


logger = logging.getLogger(__name__)


class RealtimeManager:
    def __init__(self, connection_manager: ConnectionManager, dispatcher: Dispatcher) -> None:
        self.connection_manager = connection_manager
        self.dispatcher = dispatcher

    def _update_environment_status(self, environment_id: str, is_online: bool, last_ping: datetime | None = None) -> None:
        with SessionLocal() as db:
            service = EnvironmentService(db)
            service.update_status(environment_id, is_online, last_ping)

    async def _sync_environment(self, connection: Connection) -> None:
        try:
            print(f"\n[SYNC ENVIADO] Enviando pedido de sync (environment.sync) para o ambiente: {connection.environment_id}\n")
            logger.info(f"Sending environment.sync request to environment {connection.environment_id}")
            response = await self.connection_manager.request_environment_sync(connection)
            
            print(f"\n[SYNC RECEBIDO] Resposta de sync recebida com sucesso={response.get('success')} para o ambiente: {connection.environment_id}")
            print(f"Dados do Snapshot recebido: {response}\n")
            
            if response.get("success"):
                payload = response.get("payload", {})
                logger.info(f"Received environment.sync response for {connection.environment_id}. Payload keys: {list(payload.keys())}")
                snapshot = EnvironmentSnapshotDTO.model_validate(payload)
                print(f"[SYNC PARSED] Containers parsed from snapshot: {len(snapshot.published_containers)}")
                logger.info(f"Parsed snapshot with {len(snapshot.published_containers)} published containers for environment {connection.environment_id}")
                
                with SessionLocal() as db:
                    sync_service = EnvironmentSyncService(db)
                    sync_service.sync(connection.environment_id, snapshot)
            else:
                logger.error(f"Agent returned error on environment.sync: {response.get('error')}")
                
        except Exception as e:
            logger.error(f"Failed to sync environment {connection.environment_id}: {str(e)}", exc_info=True)

    def trigger_environment_sync(self, connection: Connection) -> None:
        asyncio.create_task(self._sync_environment(connection))

    async def start(self, websocket: WebSocket, environment_id: str, user_id: int) -> None:
        await websocket.accept()
        now = datetime.now(timezone.utc)
        connection = Connection(
            environment_id=environment_id,
            user_id=user_id,
            connected_at=now,
            last_heartbeat=now,
            websocket=websocket
        )
        
        self.connection_manager.connect(connection)
        self._update_environment_status(environment_id, is_online=True, last_ping=now)
        
        # Initiate environment sync as a background task
        self.trigger_environment_sync(connection)

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                except Exception as e:
                    logger.error(f"Error parsing websocket message JSON: {e}")
                    continue
                
                # Update last ping globally when any valid message arrives
                now = datetime.now(timezone.utc)
                connection.last_heartbeat = now
                self._update_environment_status(environment_id, is_online=True, last_ping=now)

                # Check if it's a Response (has 'success' field)
                if "success" in payload:
                    try:
                        response = WebSocketResponse.model_validate(payload)
                        future = connection.pending_requests.pop(response.request_id, None)
                        if future and not future.done():
                            future.set_result(payload)
                        else:
                            logger.warning(f"Received response for unknown or already completed request_id: {response.request_id}")
                    except Exception as e:
                        logger.error(f"Error validating WebSocketResponse: {e}")
                else:
                    # It is a Request from Agent
                    try:
                        message = WebSocketMessage.model_validate(payload)
                        await self.dispatcher.dispatch(connection, message)
                    except Exception as e:
                        logger.error(f"Error validating WebSocketMessage: {e}")
                
        except WebSocketDisconnect:
            self.connection_manager.disconnect(environment_id)
            self._update_environment_status(environment_id, is_online=False, last_ping=datetime.now(timezone.utc))
