from dataclasses import dataclass
from datetime import datetime
from fastapi import WebSocket


@dataclass
class Connection:
    environment_id: str
    user_id: int
    connected_at: datetime
    last_heartbeat: datetime
    websocket: WebSocket
