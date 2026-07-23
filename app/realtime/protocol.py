from typing import Any
from pydantic import BaseModel, Field


class WebSocketMessage(BaseModel):
    request_id: str | None = None
    origin: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WebSocketResponse(BaseModel):
    request_id: str
    origin: str
    success: bool = True
    type: str = "ack"
    payload: dict[str, Any] = Field(default_factory=dict)


class WebSocketErrorDetail(BaseModel):
    code: str
    message: str


class WebSocketError(BaseModel):
    request_id: str
    origin: str
    success: bool = False
    error: WebSocketErrorDetail
