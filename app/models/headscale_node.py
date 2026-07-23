from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.headscale_user import HeadscaleUser
    from app.models.published_container import PublishedContainer


class HeadscaleNode(TimestampMixin, Base):
    __tablename__ = "headscale_nodes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    published_container_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        nullable=True,
    )

    headscale_node_id: Mapped[str] = mapped_column(String(255), nullable=False)

    headscale_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("headscale_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    machine_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    node_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    given_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    headscale_user: Mapped[HeadscaleUser] = relationship(back_populates="nodes")
    published_container: Mapped[Optional[PublishedContainer]] = relationship()
