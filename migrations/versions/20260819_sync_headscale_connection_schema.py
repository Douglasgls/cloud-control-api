"""sync_headscale_connection_schema

Revision ID: 20260819_sync
Revises: e72de3f871fc
Create Date: 2026-08-19 13:50:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260819_sync'
down_revision: Union[str, Sequence[str], None] = 'e72de3f871fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add public_id to connections as nullable first to populate existing rows
    op.add_column('connections', sa.Column('public_id', sa.String(length=36), nullable=True))
    
    # Populate existing rows with random UUIDs if any exist
    connection_table = sa.table('connections', sa.column('id', sa.Integer), sa.column('public_id', sa.String))
    conn = op.get_bind()
    results = conn.execute(sa.select(connection_table.c.id)).fetchall()
    for row in results:
        conn.execute(
            connection_table.update()
            .where(connection_table.c.id == row[0])
            .values(public_id=str(uuid.uuid4()))
        )

    op.alter_column('connections', 'public_id', nullable=False)
    op.create_index(op.f('ix_connections_public_id'), 'connections', ['public_id'], unique=True)

    # 2. Add headscale_node_id and disconnected_at to connections
    op.add_column('connections', sa.Column('headscale_node_id', sa.String(length=36), nullable=True))
    op.add_column('connections', sa.Column('disconnected_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_connections_headscale_node_id'), 'connections', ['headscale_node_id'], unique=False)
    op.create_foreign_key('fk_connections_headscale_node_id', 'connections', 'headscale_nodes', ['headscale_node_id'], ['id'], ondelete='SET NULL')

    # 3. Add online and tailscale_ip to headscale_nodes
    op.add_column('headscale_nodes', sa.Column('tailscale_ip', sa.String(length=45), nullable=True))
    op.add_column('headscale_nodes', sa.Column('online', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('headscale_nodes', 'online')
    op.drop_column('headscale_nodes', 'tailscale_ip')

    op.drop_constraint('fk_connections_headscale_node_id', 'connections', type_='foreignkey')
    op.drop_index(op.f('ix_connections_headscale_node_id'), table_name='connections')
    op.drop_column('connections', 'disconnected_at')
    op.drop_column('connections', 'headscale_node_id')

    op.drop_index(op.f('ix_connections_public_id'), table_name='connections')
    op.drop_column('connections', 'public_id')
