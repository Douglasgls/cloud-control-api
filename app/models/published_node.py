from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.published_container import PublishedContainer


class PublishedNode(TimestampMixin, Base):
    __tablename__ = "published_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    published_container_id: Mapped[str] = mapped_column(
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    installed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    service_running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    machine_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    node_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    tailscale_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    
    online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    published_container: Mapped[PublishedContainer] = relationship(back_populates="published_node")
