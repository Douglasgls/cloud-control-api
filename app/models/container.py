from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.access_token import AccessToken
    from app.models.connection import Connection
    from app.models.environment import Environment
    from app.models.headscale_node import HeadscaleNode


class Container(TimestampMixin, Base):
    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )

    api_local_container_id: Mapped[str] = mapped_column(String, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    last_known_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    
    environment: Mapped[Environment] = relationship(back_populates="containers")

    headscale_node: Mapped[HeadscaleNode | None] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
        uselist=False,
    )
    
    access_tokens: Mapped[list[AccessToken]] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
    )
    
    connections: Mapped[list[Connection]] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
    )
