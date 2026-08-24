from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class NetworkCatalogPortDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    port: int
    protocol: str = "tcp"


class NetworkCatalogItemDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    hostname: str
    fqdn: str = Field(..., description="FQDN derivado (<hostname>.interno)")
    tailscale_ip: Optional[str] = None
    status: str = "unknown"
    ports: list[NetworkCatalogPortDTO] = Field(default_factory=list)


class NetworkCatalogResponseDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    version: int = 1
    updated_at: Optional[datetime | str] = None
    endpoints: list[NetworkCatalogItemDTO] = Field(default_factory=list)
