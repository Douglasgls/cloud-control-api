"""initial cloud control schema

Revision ID: 20260717_0001
Revises:
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "environments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment_token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("status_online", sa.Boolean(), nullable=False),
        sa.Column("last_ping", sa.DateTime(), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "containers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("environment_id", sa.String(36), sa.ForeignKey("environments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_local_container_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("last_known_ip", sa.String(45), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("container_id", sa.Integer(), sa.ForeignKey("containers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("container_id", sa.Integer(), sa.ForeignKey("containers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_token_id", sa.Integer(), sa.ForeignKey("access_tokens.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "headscale_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("container_id", sa.Integer(), sa.ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("node_id", sa.String(255), nullable=False),
        sa.Column("machine_key", sa.String(255), nullable=True),
        sa.Column("node_key", sa.String(255), nullable=True),
        sa.Column("last_ip", sa.String(45), nullable=True),
        sa.Column("online", sa.Boolean(), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        *timestamps(),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("headscale_nodes")
    op.drop_table("connections")
    op.drop_table("access_tokens")
    op.drop_table("containers")
    op.drop_table("environments")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
