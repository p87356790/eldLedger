"""add merchant (사용처) on transactions

Revision ID: f6c2d8e45a11
Revises: e5a1c3d78b02
Create Date: 2026-09-14 23:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6c2d8e45a11"
down_revision: Union[str, None] = "e5a1c3d78b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("merchant", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("merchant")
