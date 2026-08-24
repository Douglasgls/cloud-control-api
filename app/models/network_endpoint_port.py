from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.network_endpoint import NetworkEndpoint


class NetworkEndpointPort(TimestampMixin, Base):
    __tablename__ = "network_endpoint_ports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    network_endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("network_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )

    port: Mapped[int] = mapped_column(Integer, nullable=False)

    protocol: Mapped[str] = mapped_column(String(20), nullable=False, default="tcp")

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    network_endpoint: Mapped[NetworkEndpoint] = relationship(back_populates="ports")
