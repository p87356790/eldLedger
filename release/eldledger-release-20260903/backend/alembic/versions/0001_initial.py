"""Initial Alembic baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-01

Domain tables are added in later phases. This revision proves that
SQLite + Alembic migrations run on container start.
"""

from typing import Sequence, Union

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
