"""create_network_endpoints_tables

Revision ID: 20260824_network_endpoints
Revises: 4ded5136c6fe
Create Date: 2026-08-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260824_network_endpoints'
down_revision: Union[str, Sequence[str], None] = '20260819_sync'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'network_endpoints',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('published_container_id', sa.String(length=36), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('dns_name', sa.String(length=255), nullable=False),
        sa.Column('tailscale_ip', sa.String(length=45), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='unknown'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['published_container_id'], ['published_containers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('published_container_id', name='uq_network_endpoints_container'),
        sa.UniqueConstraint('dns_name', name='uq_network_endpoints_dns_name')
    )
    op.create_table(
        'network_endpoint_ports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('network_endpoint_id', sa.String(length=36), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(length=20), nullable=False, server_default='tcp'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['network_endpoint_id'], ['network_endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('network_endpoint_ports')
    op.drop_table('network_endpoints')
