from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.access_token import AccessToken
from app.models.environment import Environment
from app.models.published_container import PublishedContainer
from app.models.published_node import PublishedNode


class ValidationCode(str, Enum):
    TOKEN_NOT_FOUND = "TOKEN_NOT_FOUND"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    ENVIRONMENT_NOT_FOUND = "ENVIRONMENT_NOT_FOUND"
    ENVIRONMENT_OFFLINE = "ENVIRONMENT_OFFLINE"
    CONTAINER_NOT_FOUND = "CONTAINER_NOT_FOUND"
    CONTAINER_OFFLINE = "CONTAINER_OFFLINE"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    TAILSCALE_NOT_INSTALLED = "TAILSCALE_NOT_INSTALLED"
    TAILSCALE_SERVICE_STOPPED = "TAILSCALE_SERVICE_STOPPED"
    NODE_OFFLINE = "NODE_OFFLINE"
    CONNECTION_NOT_FOUND = "CONNECTION_NOT_FOUND"
    CONNECTION_EXPIRED = "CONNECTION_EXPIRED"


class ClientConnectionRequestDTO(BaseModel):
    access_token: str = Field(..., description="Raw access token for container access")


class ConnectionInstructionsDTO(BaseModel):
    connection_id: Optional[int] = None
    login_server: Optional[str] = None
    preauth_key: Optional[str] = None
    hostname: Optional[str] = None
    tailscale_ip: Optional[str] = None
    tailscale_ipv6: Optional[str] = None
    expires_at: Optional[str] = None


class ClientConnectionResponseDTO(BaseModel):
    authorized: bool
    code: Optional[ValidationCode] = None
    message: Optional[str] = None
    connection: ConnectionInstructionsDTO = Field(default_factory=ConnectionInstructionsDTO)


class ClientConnectionConfirmRequestDTO(BaseModel):
    connection_id: int = Field(..., description="ID of the Connection record to confirm")


class ClientConnectionConfirmResponseDTO(BaseModel):
    success: bool
    connection_id: int
    status: str
    connected_at: Optional[str] = None
    code: Optional[ValidationCode] = None
    message: Optional[str] = None



@dataclass
class AuthorizedConnectionContext:
    raw_token: str
    token_hash: str
    access_token: Optional[AccessToken] = None
    published_container: Optional[PublishedContainer] = None
    environment: Optional[Environment] = None
    published_node: Optional[PublishedNode] = None


@dataclass
class ValidationResult:
    allowed: bool
    code: Optional[ValidationCode] = None
    message: Optional[str] = None
    context: Optional[AuthorizedConnectionContext] = None
