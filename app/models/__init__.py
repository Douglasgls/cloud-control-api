"""Importa todos os modelos para registrá-los no metadata do Alembic."""

from app.models.access_token import AccessToken
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.connection import Connection
from app.models.published_container import PublishedContainer
from app.models.environment import Environment
from app.models.published_node import PublishedNode
from app.models.user import User
from app.models.headscale_user import HeadscaleUser
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.models.headscale_node import HeadscaleNode
from app.models.provisioning_status import ProvisioningStatus

__all__ = [
    "AccessToken",
    "AuditLog",
    "Base",
    "Connection",
    "PublishedContainer",
    "Environment",
    "PublishedNode",
    "User",
    "HeadscaleUser",
    "HeadscalePreAuthKey",
    "HeadscaleNode",
    "ProvisioningStatus",
]

