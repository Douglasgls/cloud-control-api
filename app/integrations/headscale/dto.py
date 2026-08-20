from typing import Optional
from pydantic import BaseModel, Field


class HeadscaleUserDTO(BaseModel):
    id: str
    name: str
    createdAt: str


class HeadscaleUserListDTO(BaseModel):
    users: list[HeadscaleUserDTO] = Field(default_factory=list)


class HeadscalePreAuthKeyDTO(BaseModel):
    id: str
    user: HeadscaleUserDTO | dict | str
    key: str
    reusable: bool
    ephemeral: bool
    used: bool
    createdAt: str
    expiration: Optional[str] = None


class HeadscalePreAuthKeyListDTO(BaseModel):
    preauthKeys: list[HeadscalePreAuthKeyDTO] = Field(default_factory=list)


class HeadscaleNodeUserDTO(BaseModel):
    id: str
    name: str
    createdAt: str


class HeadscaleNodeDTO(BaseModel):
    id: str
    name: str
    givenName: Optional[str] = None
    user: HeadscaleNodeUserDTO
    machineKey: Optional[str] = None
    nodeKey: Optional[str] = None
    ipAddresses: list[str] = Field(default_factory=list)
    online: bool = False
    invalid: bool = False
    validTags: list[str] = Field(default_factory=list)
    forcedTags: list[str] = Field(default_factory=list)
    createdAt: Optional[str] = None
    lastSeen: Optional[str] = None
    expiry: Optional[str] = None



class HeadscaleNodeListDTO(BaseModel):
    nodes: list[HeadscaleNodeDTO] = Field(default_factory=list)
