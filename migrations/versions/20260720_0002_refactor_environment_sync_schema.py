"""refactor environment sync schema

Revision ID: 20260720_0002
Revises: 20260717_0001
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260720_0002"
down_revision = "20260717_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop foreign key constraints referencing the old containers table
    op.drop_constraint("access_tokens_container_id_fkey", "access_tokens", type_="foreignkey")
    op.drop_constraint("connections_container_id_fkey", "connections", type_="foreignkey")
    op.drop_constraint("headscale_nodes_container_id_fkey", "headscale_nodes", type_="foreignkey")

    # 2. Rename tables
    op.rename_table("containers", "published_containers")
    op.rename_table("headscale_nodes", "published_nodes")

    # 3. Add columns to published_containers
    op.add_column("published_containers", sa.Column("container_number", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("published_containers", sa.Column("status", sa.String(length=50), nullable=False, server_default="unknown"))
    
    # Create unique constraint on published_containers
    op.create_unique_constraint(
        "uq_published_containers_env_local_id",
        "published_containers",
        ["environment_id", "api_local_container_id"]
    )

    # 4. Refactor published_nodes (formerly headscale_nodes)
    op.alter_column("published_nodes", "container_id", new_column_name="published_container_id")
    op.alter_column("published_nodes", "last_ip", new_column_name="tailscale_ip")
    op.alter_column("published_nodes", "machine_key", new_column_name="machine_id")
    op.drop_column("published_nodes", "node_id")
    op.add_column("published_nodes", sa.Column("installed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("published_nodes", sa.Column("service_running", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("published_nodes", sa.Column("version", sa.String(length=50), nullable=True))
    op.add_column("published_nodes", sa.Column("last_sync", sa.DateTime(), nullable=True))

    # 5. Refactor access_tokens
    op.alter_column("access_tokens", "container_id", new_column_name="published_container_id")
    op.add_column("access_tokens", sa.Column("api_local_token_id", sa.String(length=255), nullable=True))

    # 6. Refactor connections
    op.alter_column("connections", "container_id", new_column_name="published_container_id")

    # 7. Recreate foreign key constraints pointing to published_containers
    op.create_foreign_key(
        "published_nodes_published_container_id_fkey",
        "published_nodes",
        "published_containers",
        ["published_container_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "access_tokens_published_container_id_fkey",
        "access_tokens",
        "published_containers",
        ["published_container_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "connections_published_container_id_fkey",
        "connections",
        "published_containers",
        ["published_container_id"],
        ["id"],
        ondelete="CASCADE"
    )


def downgrade() -> None:
    # Revert FKs
    op.drop_constraint("connections_published_container_id_fkey", "connections", type_="foreignkey")
    op.drop_constraint("access_tokens_published_container_id_fkey", "access_tokens", type_="foreignkey")
    op.drop_constraint("published_nodes_published_container_id_fkey", "published_nodes", type_="foreignkey")

    # Revert columns and table for connections
    op.alter_column("connections", "published_container_id", new_column_name="container_id")

    # Revert columns and table for access_tokens
    op.drop_column("access_tokens", "api_local_token_id")
    op.alter_column("access_tokens", "published_container_id", new_column_name="container_id")

    # Revert columns and table for published_nodes
    op.drop_column("published_nodes", "last_sync")
    op.drop_column("published_nodes", "version")
    op.drop_column("published_nodes", "service_running")
    op.drop_column("published_nodes", "installed")
    op.add_column("published_nodes", sa.Column("node_id", sa.String(length=255), nullable=False, server_default="unknown"))
    op.alter_column("published_nodes", "machine_id", new_column_name="machine_key")
    op.alter_column("published_nodes", "tailscale_ip", new_column_name="last_ip")
    op.alter_column("published_nodes", "published_container_id", new_column_name="container_id")

    # Revert columns and table for published_containers
    op.drop_constraint("uq_published_containers_env_local_id", "published_containers", type_="unique")
    op.drop_column("published_containers", "status")
    op.drop_column("published_containers", "container_number")

    # Rename tables back
    op.rename_table("published_nodes", "headscale_nodes")
    op.rename_table("published_containers", "containers")

    # Recreate original FKs
    op.create_foreign_key(
        "headscale_nodes_container_id_fkey",
        "headscale_nodes",
        "containers",
        ["container_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "access_tokens_container_id_fkey",
        "access_tokens",
        "containers",
        ["container_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "connections_container_id_fkey",
        "connections",
        "containers",
        ["container_id"],
        ["id"],
        ondelete="CASCADE"
    )
