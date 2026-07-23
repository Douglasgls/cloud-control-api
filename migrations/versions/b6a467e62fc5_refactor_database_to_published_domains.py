"""refactor_database_to_published_domains

Revision ID: b6a467e62fc5
Revises: 20260720_0002
Create Date: 2026-07-22 15:29:17.762342

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6a467e62fc5'
down_revision: Union[str, Sequence[str], None] = '20260720_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to use UUID strings for published_containers."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    # 1. Drop foreign key constraints pointing to published_containers
    if is_postgres:
        op.drop_constraint("access_tokens_published_container_id_fkey", "access_tokens", type_="foreignkey")
        op.drop_constraint("connections_published_container_id_fkey", "connections", type_="foreignkey")
        op.drop_constraint("published_nodes_published_container_id_fkey", "published_nodes", type_="foreignkey")
        op.drop_constraint("uq_published_containers_env_local_id", "published_containers", type_="unique")

    # 2. Rename old table
    op.rename_table("published_containers", "tmp_published_containers")

    # 3. Create new published_containers with String(36) ID
    op.create_table(
        "published_containers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_local_container_id", sa.String(), nullable=False),
        sa.Column("container_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("environment_id", "api_local_container_id", name="uq_published_containers_env_local_id")
    )

    # 4. Read old containers and map to new UUIDs
    old_containers = bind.execute(sa.text(
        "SELECT id, environment_id, api_local_container_id, container_number, name, status, created_at, updated_at "
        "FROM tmp_published_containers"
    )).fetchall()

    id_mapping = {}
    for row in old_containers:
        old_id = row[0]
        new_id = str(uuid.uuid4())
        id_mapping[old_id] = new_id

        bind.execute(
            sa.text(
                "INSERT INTO published_containers (id, environment_id, api_local_container_id, container_number, name, status, created_at, updated_at) "
                "VALUES (:id, :env_id, :api_local_id, :num, :name, :status, :created_at, :updated_at)"
            ),
            {
                "id": new_id,
                "env_id": row[1],
                "api_local_id": row[2],
                "num": row[3],
                "name": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7]
            }
        )

    # 5. Modify access_tokens column type and update values
    with op.batch_alter_table("access_tokens") as batch_op:
        batch_op.alter_column("published_container_id", existing_type=sa.INTEGER(), type_=sa.String(length=36), existing_nullable=False)

    for old_id, new_id in id_mapping.items():
        bind.execute(
            sa.text("UPDATE access_tokens SET published_container_id = :new_id WHERE published_container_id = :old_id"),
            {"new_id": new_id, "old_id": str(old_id)}
        )

    # 6. Modify connections column type and update values
    with op.batch_alter_table("connections") as batch_op:
        batch_op.alter_column("published_container_id", existing_type=sa.INTEGER(), type_=sa.String(length=36), existing_nullable=False)

    for old_id, new_id in id_mapping.items():
        bind.execute(
            sa.text("UPDATE connections SET published_container_id = :new_id WHERE published_container_id = :old_id"),
            {"new_id": new_id, "old_id": str(old_id)}
        )

    # 7. Modify published_nodes column type and update values
    with op.batch_alter_table("published_nodes") as batch_op:
        batch_op.alter_column("published_container_id", existing_type=sa.INTEGER(), type_=sa.String(length=36), existing_nullable=False)

    for old_id, new_id in id_mapping.items():
        bind.execute(
            sa.text("UPDATE published_nodes SET published_container_id = :new_id WHERE published_container_id = :old_id"),
            {"new_id": new_id, "old_id": str(old_id)}
        )

    # 8. Recreate foreign key constraints
    if is_postgres:
        op.create_foreign_key(
            "published_nodes_published_container_id_fkey",
            "published_nodes", "published_containers",
            ["published_container_id"], ["id"],
            ondelete="CASCADE"
        )
        op.create_foreign_key(
            "access_tokens_published_container_id_fkey",
            "access_tokens", "published_containers",
            ["published_container_id"], ["id"],
            ondelete="CASCADE"
        )
        op.create_foreign_key(
            "connections_published_container_id_fkey",
            "connections", "published_containers",
            ["published_container_id"], ["id"],
            ondelete="CASCADE"
        )

    # 9. Clean up temporary table
    op.drop_table("tmp_published_containers")


def downgrade() -> None:
    """Downgrade schema back to Integer keys."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    if is_postgres:
        op.drop_constraint("access_tokens_published_container_id_fkey", "access_tokens", type_="foreignkey")
        op.drop_constraint("connections_published_container_id_fkey", "connections", type_="foreignkey")
        op.drop_constraint("published_nodes_published_container_id_fkey", "published_nodes", type_="foreignkey")
        op.drop_constraint("uq_published_containers_env_local_id", "published_containers", type_="unique")

    op.rename_table("published_containers", "tmp_published_containers")

    op.create_table(
        "published_containers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("environment_id", sa.String(length=36), sa.ForeignKey("environments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_local_container_id", sa.String(), nullable=False),
        sa.Column("container_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_known_ip", sa.String(length=45), nullable=True),
        sa.UniqueConstraint("environment_id", "api_local_container_id", name="uq_published_containers_env_local_id")
    )

    old_containers = bind.execute(sa.text(
        "SELECT id, environment_id, api_local_container_id, container_number, name, status, created_at, updated_at "
        "FROM tmp_published_containers"
    )).fetchall()

    id_mapping = {}
    for idx, row in enumerate(old_containers, start=1):
        old_uuid = row[0]
        new_int_id = idx
        id_mapping[old_uuid] = new_int_id

        bind.execute(
            sa.text(
                "INSERT INTO published_containers (id, environment_id, api_local_container_id, container_number, name, status, created_at, updated_at) "
                "VALUES (:id, :env_id, :api_local_id, :num, :name, :status, :created_at, :updated_at)"
            ),
            {
                "id": new_int_id,
                "env_id": row[1],
                "api_local_id": row[2],
                "num": row[3],
                "name": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7]
            }
        )

    # Revert access_tokens values and alter column
    for old_uuid, new_int_id in id_mapping.items():
        bind.execute(
            sa.text("UPDATE access_tokens SET published_container_id = :new_id WHERE published_container_id = :old_id"),
            {"new_id": str(new_int_id), "old_id": old_uuid}
        )

    with op.batch_alter_table("access_tokens") as batch_op:
        batch_op.alter_column("published_container_id", existing_type=sa.String(length=36), type_=sa.INTEGER(), existing_nullable=False, postgresql_using="published_container_id::integer")

    # Revert connections values and alter column
    for old_uuid, new_int_id in id_mapping.items():
        bind.execute(
            sa.text("UPDATE connections SET published_container_id = :new_id WHERE published_container_id = :old_id"),
            {"new_id": str(new_int_id), "old_id": old_uuid}
        )

    with op.batch_alter_table("connections") as batch_op:
        batch_op.alter_column("published_container_id", existing_type=sa.String(length=36), type_=sa.INTEGER(), existing_nullable=False, postgresql_using="published_container_id::integer")

    # Revert published_nodes values and alter column
    for old_uuid, new_int_id in id_mapping.items():
        bind.execute(
            sa.text("UPDATE published_nodes SET published_container_id = :new_id WHERE published_container_id = :old_id"),
            {"new_id": str(new_int_id), "old_id": old_uuid}
        )

    with op.batch_alter_table("published_nodes") as batch_op:
        batch_op.alter_column("published_container_id", existing_type=sa.String(length=36), type_=sa.INTEGER(), existing_nullable=False, postgresql_using="published_container_id::integer")

    if is_postgres:
        op.create_foreign_key(
            "published_nodes_published_container_id_fkey",
            "published_nodes", "published_containers",
            ["published_container_id"], ["id"],
            ondelete="CASCADE"
        )
        op.create_foreign_key(
            "access_tokens_published_container_id_fkey",
            "access_tokens", "published_containers",
            ["published_container_id"], ["id"],
            ondelete="CASCADE"
        )
        op.create_foreign_key(
            "connections_published_container_id_fkey",
            "connections", "published_containers",
            ["published_container_id"], ["id"],
            ondelete="CASCADE"
        )

    op.drop_table("tmp_published_containers")
