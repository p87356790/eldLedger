"""wallet fields on accounts

Revision ID: a4c9e2b81f10
Revises: 2880c71070d7
Create Date: 2026-09-01 17:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c9e2b81f10"
down_revision: Union[str, None] = "2880c71070d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("instrument_kind", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("currency", sa.String(length=3), nullable=False, server_default="KRW"))
        batch_op.add_column(sa.Column("opening_balance", sa.BigInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("institution", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("card_payment_day", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("settlement_account_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_accounts_instrument_kind"), ["instrument_kind"], unique=False)
        batch_op.create_index(batch_op.f("ix_accounts_settlement_account_id"), ["settlement_account_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_accounts_settlement_account_id_accounts"),
            "accounts",
            ["settlement_account_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_accounts_settlement_account_id_accounts"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_accounts_settlement_account_id"))
        batch_op.drop_index(batch_op.f("ix_accounts_instrument_kind"))
        batch_op.drop_column("settlement_account_id")
        batch_op.drop_column("card_payment_day")
        batch_op.drop_column("institution")
        batch_op.drop_column("opening_balance")
        batch_op.drop_column("currency")
        batch_op.drop_column("instrument_kind")
