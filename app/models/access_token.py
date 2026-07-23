from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.connection import Connection
    from app.models.published_container import PublishedContainer


class AccessToken(TimestampMixin, Base):
    __tablename__ = "access_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    published_container_id: Mapped[str] = mapped_column(
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        nullable=False,
    )
    api_local_token_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_container: Mapped[PublishedContainer] = relationship(back_populates="access_tokens")
    connections: Mapped[list[Connection]] = relationship(back_populates="access_token")
