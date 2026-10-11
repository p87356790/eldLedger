"""add bills for expenses registered before they are paid

Revision ID: b3c8e1a74f20
Revises: a9f3c1d82b44
Create Date: 2026-10-08 00:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c8e1a74f20"
down_revision: Union[str, None] = "a9f3c1d82b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("billed_on", sa.Date(), nullable=False),
        sa.Column("pay_on", sa.Date(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("payment_account_id", sa.Integer(), nullable=True),
        sa.Column("repeats_monthly", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="bill_amount_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bills_organization_id", "bills", ["organization_id"])
    op.create_index("ix_bills_created_by_user_id", "bills", ["created_by_user_id"])
    op.create_index("ix_bills_category_id", "bills", ["category_id"])
    op.create_index("ix_bills_billed_on", "bills", ["billed_on"])
    op.create_index("ix_bills_payment_account_id", "bills", ["payment_account_id"])
    op.create_index("ix_bills_status", "bills", ["status"])
    op.create_index("ix_bills_transaction_id", "bills", ["transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_bills_transaction_id", table_name="bills")
    op.drop_index("ix_bills_status", table_name="bills")
    op.drop_index("ix_bills_payment_account_id", table_name="bills")
    op.drop_index("ix_bills_billed_on", table_name="bills")
    op.drop_index("ix_bills_category_id", table_name="bills")
    op.drop_index("ix_bills_created_by_user_id", table_name="bills")
    op.drop_index("ix_bills_organization_id", table_name="bills")
    op.drop_table("bills")
