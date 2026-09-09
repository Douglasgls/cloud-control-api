from typing import Any

from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage, WebSocketResponse, WebSocketError


import hashlib
import time

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, Connection] = {}
        self._last_sent_hashes: dict[str, float] = {}

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
            json_msg = message.model_dump_json()
            
            # Simple deduplication: Ignore identical messages (excluding request_id) sent within 5 seconds
            # Create a copy of the payload without request_id to calculate the hash
            msg_dict = message.model_dump()
            if "request_id" in msg_dict:
                msg_dict["request_id"] = "fixed-for-hash"
                
            msg_hash = hashlib.md5(str(msg_dict).encode()).hexdigest()
            now = time.time()
            
            if msg_hash in self._last_sent_hashes and (now - self._last_sent_hashes[msg_hash]) < 5.0:
                return  # Skip sending duplicate
                
            self._last_sent_hashes[msg_hash] = now
            
            # Clean up old hashes occasionally to prevent memory leaks
            if len(self._last_sent_hashes) > 1000:
                self._last_sent_hashes = {k: v for k, v in self._last_sent_hashes.items() if now - v < 10.0}

            await connection.websocket.send_text(json_msg)

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

    async def request_environment_sync(self, connection: Connection) -> dict:
        return await connection.request("environment.sync", {})

