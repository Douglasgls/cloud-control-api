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


class HeadscalePreAuthKey(TimestampMixin, Base):
    __tablename__ = "headscale_preauth_keys"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    headscale_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("headscale_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    published_container_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        nullable=True,
    )

    headscale_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    key_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reusable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ephemeral: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expiration: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    headscale_user: Mapped[HeadscaleUser] = relationship(back_populates="preauth_keys")
    published_container: Mapped[Optional[PublishedContainer]] = relationship()
