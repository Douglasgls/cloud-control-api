from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.access_token import AccessToken
    from app.models.connection import Connection
    from app.models.environment import Environment
    from app.models.published_node import PublishedNode


class PublishedContainer(TimestampMixin, Base):
    __tablename__ = "published_containers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )

    api_local_container_id: Mapped[str] = mapped_column(String, nullable=False)
    
    container_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    
    environment: Mapped[Environment] = relationship(back_populates="published_containers")

    published_node: Mapped[PublishedNode | None] = relationship(
        back_populates="published_container",
        cascade="all, delete-orphan",
        uselist=False,
    )
    
    access_tokens: Mapped[list[AccessToken]] = relationship(
        back_populates="published_container",
        cascade="all, delete-orphan",
    )
    
    connections: Mapped[list[Connection]] = relationship(
        back_populates="published_container",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("environment_id", "api_local_container_id", name="uq_published_containers_env_local_id"),
    )
