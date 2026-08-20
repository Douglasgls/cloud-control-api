from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.connection_status import ConnectionStatus

from uuid import uuid4

if TYPE_CHECKING:
    from app.models.access_token import AccessToken
    from app.models.headscale_preauth_key import HeadscalePreAuthKey
    from app.models.headscale_node import HeadscaleNode
    from app.models.published_container import PublishedContainer


class Connection(TimestampMixin, Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid4()),
        unique=True,
        index=True,
        nullable=False,
    )

    published_container_id: Mapped[str] = mapped_column(
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        nullable=False,
    )

    access_token_id: Mapped[int] = mapped_column(
        ForeignKey("access_tokens.id", ondelete="RESTRICT"),
        nullable=False,
    )

    headscale_preauth_key_id: Mapped[str] = mapped_column(
        ForeignKey("headscale_preauth_keys.id", ondelete="RESTRICT"),
        nullable=False,
    )

    headscale_node_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("headscale_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50), default=ConnectionStatus.PENDING, nullable=False
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    published_container: Mapped[PublishedContainer] = relationship(back_populates="connections")
    access_token: Mapped[AccessToken] = relationship(back_populates="connections")
    headscale_preauth_key: Mapped[HeadscalePreAuthKey] = relationship()
    headscale_node: Mapped[Optional[HeadscaleNode]] = relationship(back_populates="connections")



