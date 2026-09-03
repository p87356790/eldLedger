"""category tree and tag fields

Revision ID: b7e1d4c90a22
Revises: a4c9e2b81f10
Create Date: 2026-09-01 17:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e1d4c90a22"
down_revision: Union[str, None] = "a4c9e2b81f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "default_scope",
                sa.String(length=32),
                nullable=False,
                server_default="COMMON",
            )
        )
        batch_op.add_column(sa.Column("icon", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.create_index(batch_op.f("ix_categories_parent_id"), ["parent_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_categories_parent_id_categories"),
            "categories",
            ["parent_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_categories_parent_id_categories"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_categories_parent_id"))
        batch_op.drop_column("is_system")
        batch_op.drop_column("icon")
        batch_op.drop_column("default_scope")
        batch_op.drop_column("parent_id")
