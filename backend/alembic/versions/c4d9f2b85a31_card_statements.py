"""add monthly card statements

Revision ID: c4d9f2b85a31
Revises: b3c8e1a74f20
Create Date: 2026-10-13 00:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d9f2b85a31"
down_revision: Union[str, None] = "b3c8e1a74f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("card_account_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("pay_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("amount_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="card_statement_amount_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "created_by_user_id",
            "card_account_id",
            "period_start",
            name="uq_card_statement_user_card_period",
        ),
    )
    op.create_index("ix_card_statements_organization_id", "card_statements", ["organization_id"])
    op.create_index("ix_card_statements_created_by_user_id", "card_statements", ["created_by_user_id"])
    op.create_index("ix_card_statements_card_account_id", "card_statements", ["card_account_id"])
    op.create_index("ix_card_statements_bank_account_id", "card_statements", ["bank_account_id"])
    op.create_index("ix_card_statements_status", "card_statements", ["status"])
    op.create_index("ix_card_statements_transaction_id", "card_statements", ["transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_card_statements_transaction_id", table_name="card_statements")
    op.drop_index("ix_card_statements_status", table_name="card_statements")
    op.drop_index("ix_card_statements_bank_account_id", table_name="card_statements")
    op.drop_index("ix_card_statements_card_account_id", table_name="card_statements")
    op.drop_index("ix_card_statements_created_by_user_id", table_name="card_statements")
    op.drop_index("ix_card_statements_organization_id", table_name="card_statements")
    op.drop_table("card_statements")
