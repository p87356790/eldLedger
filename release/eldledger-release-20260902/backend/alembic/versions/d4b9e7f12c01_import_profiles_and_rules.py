"""import profiles and auto-category rules

Revision ID: d4b9e7f12c01
Revises: c8f2a1b34d90
Create Date: 2026-09-02 00:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4b9e7f12c01"
down_revision: Union[str, None] = "c8f2a1b34d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_profiles",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("preset_key", sa.String(length=32), nullable=True),
        sa.Column("date_column", sa.String(length=64), nullable=False),
        sa.Column("merchant_column", sa.String(length=64), nullable=False),
        sa.Column("memo_column", sa.String(length=64), nullable=True),
        sa.Column("amount_column", sa.String(length=64), nullable=True),
        sa.Column("outflow_column", sa.String(length=64), nullable=True),
        sa.Column("inflow_column", sa.String(length=64), nullable=True),
        sa.Column("type_column", sa.String(length=64), nullable=True),
        sa.Column("amount_mode", sa.String(length=32), nullable=False),
        sa.Column("is_preset", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_import_profiles_organization_id_organizations"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_profiles")),
        sa.UniqueConstraint("organization_id", "name", name=op.f("uq_import_profiles_organization_id_name")),
    )
    with op.batch_alter_table("import_profiles", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_import_profiles_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_import_profiles_preset_key"), ["preset_key"], unique=False)

    op.create_table(
        "auto_category_rules",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("merchant_keyword", sa.String(length=100), nullable=False),
        sa.Column("payment_account_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name=op.f("fk_auto_category_rules_category_id_categories"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_auto_category_rules_organization_id_organizations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_account_id"], ["accounts.id"], name=op.f("fk_auto_category_rules_payment_account_id_accounts"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auto_category_rules")),
    )
    with op.batch_alter_table("auto_category_rules", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_auto_category_rules_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_auto_category_rules_payment_account_id"), ["payment_account_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_auto_category_rules_category_id"), ["category_id"], unique=False)

    op.create_table(
        "auto_category_rule_tags",
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["auto_category_rules.id"], name=op.f("fk_auto_category_rule_tags_rule_id_auto_category_rules"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_auto_category_rule_tags_tag_id_tags"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rule_id", "tag_id", name=op.f("pk_auto_category_rule_tags")),
        sa.UniqueConstraint("rule_id", "tag_id", name=op.f("uq_auto_category_rule_tags_rule_id_tag_id")),
    )


def downgrade() -> None:
    op.drop_table("auto_category_rule_tags")
    with op.batch_alter_table("auto_category_rules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auto_category_rules_category_id"))
        batch_op.drop_index(batch_op.f("ix_auto_category_rules_payment_account_id"))
        batch_op.drop_index(batch_op.f("ix_auto_category_rules_organization_id"))
    op.drop_table("auto_category_rules")
    with op.batch_alter_table("import_profiles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_import_profiles_preset_key"))
        batch_op.drop_index(batch_op.f("ix_import_profiles_organization_id"))
    op.drop_table("import_profiles")
