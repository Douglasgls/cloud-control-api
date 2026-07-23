from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.environment import Environment
    from app.models.headscale_preauth_key import HeadscalePreAuthKey
    from app.models.headscale_node import HeadscaleNode


class HeadscaleUser(TimestampMixin, Base):
    __tablename__ = "headscale_users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    environment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("environments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    headscale_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    environment: Mapped[Environment] = relationship(back_populates="headscale_user")
    
    preauth_keys: Mapped[list[HeadscalePreAuthKey]] = relationship(
        back_populates="headscale_user",
        cascade="all, delete-orphan",
    )

    nodes: Mapped[list[HeadscaleNode]] = relationship(
        back_populates="headscale_user",
        cascade="all, delete-orphan",
    )
