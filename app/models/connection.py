from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.access_token import AccessToken
    from app.models.published_container import PublishedContainer


class Connection(TimestampMixin, Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    published_container_id: Mapped[int] = mapped_column(
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        nullable=False,
    )

    access_token_id: Mapped[int] = mapped_column(
        ForeignKey("access_tokens.id", ondelete="RESTRICT"),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    published_container: Mapped[PublishedContainer] = relationship(back_populates="connections")
    access_token: Mapped[AccessToken] = relationship(back_populates="connections")
