"""owner user on wallets, categories, tags, and rules

Revision ID: e5a1c3d78b02
Revises: d4b9e7f12c01
Create Date: 2026-09-03 01:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5a1c3d78b02"
down_revision: Union[str, None] = "d4b9e7f12c01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_owner(table: str, extra_where: str = "") -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {table}
            SET owner_user_id = (
                SELECT u.id FROM users u
                WHERE u.organization_id = {table}.organization_id
                ORDER BY u.id
                LIMIT 1
            )
            WHERE owner_user_id IS NULL
              AND EXISTS (
                  SELECT 1 FROM users u WHERE u.organization_id = {table}.organization_id
              )
              {extra_where}
            """
        )
    )


def upgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_accounts_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_accounts_owner_user_id_users"),
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_categories_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_categories_owner_user_id_users"),
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_constraint(batch_op.f("uq_categories_organization_id"), type_="unique")
        batch_op.create_unique_constraint(
            batch_op.f("uq_categories_organization_id_owner_user_id_name"),
            ["organization_id", "owner_user_id", "name"],
        )

    with op.batch_alter_table("tags", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_tags_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_tags_owner_user_id_users"),
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_constraint(batch_op.f("uq_tags_organization_id"), type_="unique")
        batch_op.create_unique_constraint(
            batch_op.f("uq_tags_organization_id_owner_user_id_name"),
            ["organization_id", "owner_user_id", "name"],
        )

    with op.batch_alter_table("auto_category_rules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_auto_category_rules_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_auto_category_rules_owner_user_id_users"),
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    _backfill_owner("accounts", "AND instrument_kind IS NOT NULL")
    _backfill_owner("categories")
    _backfill_owner("tags")
    _backfill_owner("auto_category_rules")


def downgrade() -> None:
    with op.batch_alter_table("auto_category_rules", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_auto_category_rules_owner_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_auto_category_rules_owner_user_id"))
        batch_op.drop_column("owner_user_id")

    with op.batch_alter_table("tags", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_tags_organization_id_owner_user_id_name"), type_="unique")
        batch_op.drop_constraint(batch_op.f("fk_tags_owner_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_tags_owner_user_id"))
        batch_op.drop_column("owner_user_id")
        batch_op.create_unique_constraint(batch_op.f("uq_tags_organization_id"), ["organization_id", "name"])

    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_categories_organization_id_owner_user_id_name"), type_="unique")
        batch_op.drop_constraint(batch_op.f("fk_categories_owner_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_categories_owner_user_id"))
        batch_op.drop_column("owner_user_id")
        batch_op.create_unique_constraint(batch_op.f("uq_categories_organization_id"), ["organization_id", "name"])

    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_accounts_owner_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_accounts_owner_user_id"))
        batch_op.drop_column("owner_user_id")
