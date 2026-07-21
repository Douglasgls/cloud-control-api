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


class ClientConnectionRequestDTO(BaseModel):
    access_token: str = Field(..., description="Raw access token for container access")


class ConnectionInstructionsDTO(BaseModel):
    login_server: Optional[str] = None
    preauth_key: Optional[str] = None
    hostname: Optional[str] = None
    expires_at: Optional[str] = None


class ClientConnectionResponseDTO(BaseModel):
    authorized: bool
    code: Optional[ValidationCode] = None
    message: Optional[str] = None
    connection: ConnectionInstructionsDTO = Field(default_factory=ConnectionInstructionsDTO)


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
