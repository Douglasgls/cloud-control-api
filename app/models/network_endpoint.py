from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.network_endpoint_port import NetworkEndpointPort
    from app.models.published_container import PublishedContainer


class NetworkEndpoint(TimestampMixin, Base):
    __tablename__ = "network_endpoints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    published_container_id: Mapped[str] = mapped_column(
        ForeignKey("published_containers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    hostname: Mapped[str] = mapped_column(String(255), nullable=False)

    dns_name: Mapped[str] = mapped_column(String(255), nullable=False)

    tailscale_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")

    published_container: Mapped[PublishedContainer] = relationship(
        back_populates="network_endpoint"
    )

    ports: Mapped[list[NetworkEndpointPort]] = relationship(
        back_populates="network_endpoint",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("dns_name", name="uq_network_endpoints_dns_name"),
    )
