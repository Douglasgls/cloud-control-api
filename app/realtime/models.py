import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from fastapi import WebSocket


@dataclass
class Connection:
    environment_id: str
    user_id: int
    connected_at: datetime
    last_heartbeat: datetime
    websocket: WebSocket
    pending_requests: dict[str, asyncio.Future] = field(default_factory=dict)
    
    async def request(self, message_type: str, payload: dict) -> dict:
        # Import local to avoid circular imports during startup
        from app.realtime.protocol import WebSocketMessage
        
        req_id = str(uuid4())
        fut = asyncio.Future()
        self.pending_requests[req_id] = fut
        
        msg = WebSocketMessage(
            request_id=req_id,
            type=message_type,
            payload=payload,
            origin="cloud"
        )
        await self.websocket.send_text(msg.model_dump_json())
        
        # Await the response (which will be set by the manager)
        return await fut
