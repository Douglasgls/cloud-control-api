from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketException, Query, status
import jwt
from jwt.exceptions import InvalidTokenError

from app.auth.jwt import decode_access_token
from app.realtime.connection_manager import ConnectionManager
from app.realtime.dispatcher import Dispatcher
from app.realtime.manager import RealtimeManager
from app.realtime.handlers.heartbeat import HeartbeatHandler
from app.realtime.handlers.system import SystemHandler

router = APIRouter(prefix="/ws", tags=["Realtime"])


# Dependências globais do módulo
connection_manager = ConnectionManager()
dispatcher = Dispatcher()

# Registrar handlers
dispatcher.register("heartbeat", HeartbeatHandler.handle)
dispatcher.register("system.info", SystemHandler.handle_info)

realtime_manager = RealtimeManager(connection_manager, dispatcher)


async def get_token(
    token: Annotated[str | None, Query()] = None,
) -> str:
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
    return token


@router.websocket("/agent")
@router.websocket("/agent/")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Annotated[str, Depends(get_token)]
):
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "agent":
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type")
        
        environment_id = payload.get("environment_id")
        user_id = payload.get("user_id")
        
        if not environment_id or not user_id:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
            
    except InvalidTokenError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")

    await realtime_manager.start(websocket, environment_id, user_id)
