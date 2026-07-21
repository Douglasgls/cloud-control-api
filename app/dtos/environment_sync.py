from datetime import datetime
from typing import Any, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PublishedTailscaleNodeSnapshotDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    installed: bool = False
    service_running: bool = False
    version: Optional[str] = None
    machine_id: Optional[str] = None
    node_key: Optional[str] = None
    tailscale_ip: Optional[str] = None
    online: bool = False
    last_sync: Optional[datetime | str] = None


class PublishedAccessTokenSnapshotDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(validation_alias=AliasChoices("id", "api_local_token_id", "token_id"))
    token_hash: str
    created_at: Optional[datetime | str] = None
    expires_at: Optional[datetime | str] = None
    active: bool = True
    revoked_at: Optional[datetime | str] = None


class PublishedContainerSnapshotDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    api_local_container_id: str = Field(
        validation_alias=AliasChoices("api_local_container_id", "id", "container_id", "api_local_id")
    )
    container_number: int = Field(
        default=0,
        validation_alias=AliasChoices("container_number", "vmid", "number")
    )
    name: str
    status: str = "unknown"
    tailscale: Optional[PublishedTailscaleNodeSnapshotDTO] = None
    access_tokens: list[PublishedAccessTokenSnapshotDTO] = Field(default_factory=list)


class EnvironmentDetailsDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: Optional[str] = None
    registered_at: Optional[datetime | str] = None


class EnvironmentSnapshotDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    environment: EnvironmentDetailsDTO = Field(default_factory=EnvironmentDetailsDTO)
    published_containers: list[PublishedContainerSnapshotDTO] = Field(
        default_factory=list,
        validation_alias=AliasChoices("published_containers", "containers")
    )
