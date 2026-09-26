"""add line_kind on transaction items for income deductions

Revision ID: a9f3c1d82b44
Revises: f6c2d8e45a11
Create Date: 2026-09-23 10:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9f3c1d82b44"
down_revision: Union[str, None] = "f6c2d8e45a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transaction_items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "line_kind",
                sa.String(length=32),
                nullable=False,
                server_default="STANDARD",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("transaction_items") as batch_op:
        batch_op.drop_column("line_kind")
