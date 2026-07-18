from typing import Awaitable, Callable

from app.realtime.models import Connection
from app.realtime.protocol import WebSocketMessage


HandlerFunc = Callable[[Connection, WebSocketMessage], Awaitable[None]]


class Dispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFunc] = {}

    def register(self, message_type: str, handler: HandlerFunc) -> None:
        self._handlers[message_type] = handler

    async def dispatch(self, connection: Connection, message: WebSocketMessage) -> None:
        handler = self._handlers.get(message.type)
        if handler:
            await handler(connection, message)
        else:
            # Em um cenário real, você poderia registrar um log de aviso ou enviar uma mensagem de erro
            print(f"No handler registered for message type: {message.type}")
