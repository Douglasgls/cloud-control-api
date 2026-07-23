from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HeadscaleUser(BaseModel):
    id: str
    name: str
    created_at: datetime


class HeadscalePreAuthKey(BaseModel):
    id: str
    user: str
    key: str
    reusable: bool
    ephemeral: bool
    used: bool
    created_at: datetime
    expiration: Optional[datetime] = None


class HeadscaleNode(BaseModel):
    id: str
    name: str
    given_name: str
    user: HeadscaleUser
    ip_addresses: list[str] = Field(default_factory=list)
    online: bool
    valid_tags: list[str] = Field(default_factory=list)
    forced_tags: list[str] = Field(default_factory=list)
    created_at: datetime
    last_seen: Optional[datetime] = None
    expiry: Optional[datetime] = None
