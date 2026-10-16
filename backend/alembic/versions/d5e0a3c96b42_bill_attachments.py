"""bill invoices share the attachment table

Revision ID: d5e0a3c96b42
Revises: c4d9f2b85a31
Create Date: 2026-10-13 01:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e0a3c96b42"
down_revision: Union[str, None] = "c4d9f2b85a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("attachments", schema=None) as batch_op:
        batch_op.alter_column("transaction_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("bill_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_attachments_bill_id_bills"),
            "bills",
            ["bill_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(batch_op.f("ix_attachments_bill_id"), ["bill_id"], unique=False)
        batch_op.create_check_constraint(
            "attachment_owner_exactly_one",
            "(transaction_id IS NOT NULL AND bill_id IS NULL) OR (transaction_id IS NULL AND bill_id IS NOT NULL)",
        )


def downgrade() -> None:
    op.execute("DELETE FROM attachments WHERE bill_id IS NOT NULL")
    with op.batch_alter_table("attachments", schema=None) as batch_op:
        batch_op.drop_constraint("attachment_owner_exactly_one", type_="check")
        batch_op.drop_index(batch_op.f("ix_attachments_bill_id"))
        batch_op.drop_constraint(batch_op.f("fk_attachments_bill_id_bills"), type_="foreignkey")
        batch_op.drop_column("bill_id")
        batch_op.alter_column("transaction_id", existing_type=sa.Integer(), nullable=False)
