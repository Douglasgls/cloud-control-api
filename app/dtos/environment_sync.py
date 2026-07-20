from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class PublishedTailscaleNodeSnapshotDTO(BaseModel):
    installed: bool
    service_running: bool
    version: str | None = None
    machine_id: str | None = None
    node_key: str | None = None
    tailscale_ip: str | None = None
    online: bool
    last_sync: datetime | str | None = None


class PublishedAccessTokenSnapshotDTO(BaseModel):
    id: str
    token_hash: str
    created_at: datetime | str | None = None
    expires_at: datetime | str | None = None
    active: bool
    revoked_at: datetime | str | None = None


class PublishedContainerSnapshotDTO(BaseModel):
    api_local_container_id: str
    container_number: int
    name: str
    status: str
    tailscale: PublishedTailscaleNodeSnapshotDTO | None = None
    access_tokens: list[PublishedAccessTokenSnapshotDTO] = Field(default_factory=list)


class EnvironmentDetailsDTO(BaseModel):
    id: str | None = None
    registered_at: datetime | str | None = None


class EnvironmentSnapshotDTO(BaseModel):
    environment: EnvironmentDetailsDTO
    published_containers: list[PublishedContainerSnapshotDTO] = Field(default_factory=list)
