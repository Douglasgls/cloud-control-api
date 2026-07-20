from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uuid import uuid4

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.published_container import PublishedContainer
    from app.models.user import User


class Environment(TimestampMixin, Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment_token_hash: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    status_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_ping: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="environments")
    published_containers: Mapped[list[PublishedContainer]] = relationship(
        back_populates="environment",
        cascade="all, delete-orphan",
    )
