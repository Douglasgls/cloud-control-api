import json
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.realtime.models import Connection
from app.realtime.connection_manager import ConnectionManager
from app.realtime.dispatcher import Dispatcher
from app.realtime.protocol import WebSocketMessage
from app.services.environment_service import EnvironmentService


class RealtimeManager:
    def __init__(self, connection_manager: ConnectionManager, dispatcher: Dispatcher) -> None:
        self.connection_manager = connection_manager
        self.dispatcher = dispatcher

    def _update_environment_status(self, environment_id: str, is_online: bool, last_ping: datetime | None = None) -> None:
        # Abre uma sessão de banco de dados pontual para atualizar o status
        with SessionLocal() as db:
            service = EnvironmentService(db)
            service.update_status(environment_id, is_online, last_ping)

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
        
        # Atualiza status no banco para online
        self._update_environment_status(environment_id, is_online=True, last_ping=now)

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                    message = WebSocketMessage.model_validate(payload)
                except Exception as e:
                    print(f"Error parsing websocket message: {e}")
                    # Could send WebSocketError back here
                    continue
                
                # Update last ping globally when any valid message arrives
                now = datetime.now(timezone.utc)
                connection.last_heartbeat = now
                self._update_environment_status(environment_id, is_online=True, last_ping=now)

                await self.dispatcher.dispatch(connection, message)
                
        except WebSocketDisconnect:
            self.connection_manager.disconnect(environment_id)
            self._update_environment_status(environment_id, is_online=False)
