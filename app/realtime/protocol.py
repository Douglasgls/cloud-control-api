from typing import Any
from pydantic import BaseModel, Field


class WebSocketMessage(BaseModel):
    request_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WebSocketResponse(BaseModel):
    request_id: str
    success: bool = True
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WebSocketErrorDetail(BaseModel):
    code: str
    message: str


class WebSocketError(BaseModel):
    request_id: str
    success: bool = False
    error: WebSocketErrorDetail
