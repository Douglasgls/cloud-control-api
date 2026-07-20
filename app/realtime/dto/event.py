from typing import Any
from pydantic import BaseModel, Field


class EventPublishDTO(BaseModel):
    event: str
    resource: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
