"""Importa todos os modelos para registrá-los no metadata do Alembic."""

from app.models.access_token import AccessToken
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.connection import Connection
from app.models.container import Container
from app.models.environment import Environment
from app.models.headscale_node import HeadscaleNode
from app.models.user import User

__all__ = [
    "AccessToken",
    "AuditLog",
    "Base",
    "Connection",
    "Container",
    "Environment",
    "HeadscaleNode",
    "User",
]
