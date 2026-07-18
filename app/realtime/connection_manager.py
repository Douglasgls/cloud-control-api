from typing import Any

from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage, WebSocketResponse, WebSocketError


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, Connection] = {}

    def connect(self, connection: Connection) -> None:
        self.active_connections[connection.environment_id] = connection

    def disconnect(self, environment_id: str) -> None:
        if environment_id in self.active_connections:
            del self.active_connections[environment_id]

    async def send(
        self,
        environment_id: str,
        message: WebSocketMessage | WebSocketResponse | WebSocketError,
    ) -> None:
        connection = self.active_connections.get(environment_id)
        if connection:
            await connection.websocket.send_text(message.model_dump_json())

    async def broadcast(
        self, message: WebSocketMessage | WebSocketResponse | WebSocketError
    ) -> None:
        json_msg = message.model_dump_json()
        for connection in self.active_connections.values():
            await connection.websocket.send_text(json_msg)

    def is_connected(self, environment_id: str) -> bool:
        return environment_id in self.active_connections

    def get_connection(self, environment_id: str) -> Connection | None:
        return self.active_connections.get(environment_id)

    def list_connections(self) -> list[Connection]:
        return list(self.active_connections.values())
