from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.container import Container


class HeadscaleNode(TimestampMixin, Base):
    __tablename__ = "headscale_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    container_id: Mapped[str] = mapped_column(
        ForeignKey("containers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    node_id: Mapped[str] = mapped_column(String(255), nullable=False)

    machine_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    node_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    last_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    
    online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    container: Mapped[Container] = relationship(back_populates="headscale_node")
